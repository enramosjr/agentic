"""Exact exported-tree submission by the trusted coding parent, never the worker.

The caller authenticates the parent job/configuration and confirms worker cleanup.
Creating a PR alone does not establish task admission or merge authorization.
No candidate Git configuration, hooks, commands, or commit metadata are executed.
"""
import base64
from datetime import datetime, timezone
import hashlib
import io
import re
import tarfile
from urllib.parse import quote, urlencode

from authority_protocol import validate_deployment
from trusted_ci_github import HostRefusal
from trusted_ci_policy import Refusal, digest, object_fields, positive, require, sha

REQUEST_FIELDS = ('schema_version task_id configuration_revision deployment_digest base issued run_id attempt').split()
MAX_FILES, MAX_BYTES = 10000, 64 * 1024 * 1024


def path_parts(path, allow_git=False):
    require(isinstance(path, str) and 0 < len(path) <= 240 and not path.startswith('/') and
            not re.search(r'[\x00-\x1f\x7f<>"|?*\\:]', path) and
            not any(0xD800 <= ord(c) <= 0xDFFF for c in path), 'unsafe exported path')
    parts = path.split('/')
    require(all(p and p not in ('.', '..') and (allow_git or p.casefold() != '.git') and
                not p.endswith(('.', ' ')) and
                not re.fullmatch(r'(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?', p, re.I)
                for p in parts), 'unsafe exported path component')
    return parts


def read_export(raw):
    """Read a bounded plain OCI-copy TAR without extracting or following links."""
    require(isinstance(raw, bytes) and len(raw) <= MAX_BYTES, 'export archive exceeds limit')
    files, seen, total, count = {}, set(), 0, 0
    try:
        with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as archive:
            for member in archive:
                count += 1
                total += member.size
                require(count <= 20000 and member.size >= 0 and total <= MAX_BYTES,
                        'export archive entries exceed limit')
                name = member.name.rstrip('/')
                while name.startswith('./'):
                    name = name[2:]
                if name in ('', '.') and member.isdir():
                    continue
                parts = path_parts(name, allow_git=True)
                require(member.isdir() or (member.isreg() and getattr(member, 'sparse', None) is None),
                        'export archive links, devices and sparse files refused')
                require(name.casefold() not in seen, 'duplicate export archive path')
                seen.add(name.casefold())
                if member.isdir() or any(part.casefold() == '.git' for part in parts):
                    continue
                with archive.extractfile(member) as stream:
                    content = stream.read(member.size + 1)
                require(len(content) == member.size, 'incomplete exported file')
                files[name] = {'content': content, 'executable': bool(member.mode & 0o111)}
    except (tarfile.TarError, OSError, ValueError, UnicodeError):
        raise Refusal('invalid export archive') from None
    export_manifest(files)
    return files


def export_manifest(files):
    require(isinstance(files, dict) and len(files) <= MAX_FILES, 'bounded exported file map required')
    result, folded, total = {}, set(), 0
    for path, item in files.items():
        path_parts(path)
        require(path.casefold() not in folded, 'case-colliding exported paths')
        folded.add(path.casefold())
        object_fields(item, ('content', 'executable'), 'exported regular file')
        raw = item['content']
        require(isinstance(raw, bytes) and type(item['executable']) is bool, 'regular exported bytes and mode required')
        total += len(raw)
        require(total <= MAX_BYTES, 'exported tree exceeds byte limit')
        blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        result[path] = {'mode': '100755' if item['executable'] else '100644',
                        'sha': blob, 'sha256': hashlib.sha256(raw).hexdigest()}
    for path in result:
        require(not any('/'.join(path.split('/')[:i]).casefold() in folded
                        for i in range(1, len(path.split('/')))), 'exported file/directory collision')
    return result


def pack_export(files):
    export_manifest(files)
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w', format=tarfile.PAX_FORMAT) as archive:
        for name, item in sorted(files.items()):
            entry = tarfile.TarInfo(name)
            entry.size, entry.mode = len(item['content']), 0o755 if item['executable'] else 0o644
            archive.addfile(entry, io.BytesIO(item['content']))
    raw = output.getvalue()
    require(len(raw) <= MAX_BYTES, 'source export TAR exceeds limit')
    return raw


def capture_source(api, deployment, base, guard=lambda: None):
    """Copy exact Git objects without a checkout, hooks, attributes or Git config."""
    d = validate_deployment(deployment)
    require(sha(base), 'exact task source base required')
    p, root = d['policy'], '/repos/' + d['policy']['repository']
    guard()
    repository = api.get(root)
    require(repository.get('id') == p['repository_id'] and repository.get('default_branch') == p['target'] and
            existing_ref(api, root, p['target']) == base, 'task source repository or target changed')
    commit = api.get(root + '/git/commits/' + base)
    files = _read_tree(api, root, commit['tree']['sha'], guard)
    require(existing_ref(api, root, p['target']) == base, 'task target moved during source capture')
    return pack_export(files)


def _read_tree(api, root, revision, guard):
    """Bounded authenticated blobs shared by capture and exact completion recovery."""
    tree = tree_files(api, root, revision)
    files, total = {}, 0
    for name, entry in tree.items():
        guard()
        path_parts(name)
        blob = api.fetch(root + '/git/blobs/' + entry['sha'], limit=MAX_BYTES * 2)
        require(blob.get('sha') == entry['sha'] and blob.get('encoding') == 'base64' and
                isinstance(blob.get('content'), str) and len(blob['content']) <= MAX_BYTES * 2,
                'bounded exact source blob required')
        try: raw = base64.b64decode(''.join(blob['content'].split()), validate=True)
        except (ValueError, UnicodeError): raise Refusal('malformed source blob') from None
        total += len(raw)
        require(total <= MAX_BYTES and
                hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() == entry['sha'],
                'source blob digest or size differs')
        files[name] = dict(content=raw, executable=entry['mode'] == '100755')
    guard()
    return files


def tree_files(api, root, tree):
    require(sha(tree), 'submitted tree identity unavailable')
    response = api.get(root + '/git/trees/' + tree + '?recursive=1')
    require(response.get('sha') == tree and response.get('truncated') is False and
            isinstance(response.get('tree'), list) and len(response['tree']) <= 20000, 'complete bounded tree readback required')
    result, names = {}, set()
    directories = set()
    for item in response['tree']:
        path = item['path']
        require(path not in names, 'duplicate submitted tree path')
        names.add(path)
        if item['type'] == 'tree':
            require(item['mode'] == '040000' and sha(item['sha']), 'unsafe submitted directory')
            directories.add(path)
        else:
            require(item['type'] == 'blob' and item['mode'] in ('100644', '100755') and sha(item['sha']),
                    'submitted tree contains unsupported file types')
            result[path] = {'mode': item['mode'], 'sha': item['sha']}
    parents = {'/'.join(path.split('/')[:i]) for path in result for i in range(1, len(path.split('/')))}
    require(directories <= parents, 'unexpected submitted directories')
    return result


def existing_ref(api, root, branch):
    try:
        result = api.get(root + '/git/ref/heads/' + quote(branch, safe=''))
    except HostRefusal as error:
        require(error.status == 404, 'task branch lookup unavailable')
        return None
    value = result['object']['sha']
    require(sha(value), 'task branch identity unavailable')
    return value


def submit(api, deployment, request, files, now):
    """One attempt; reruns recover exact content-addressed objects/branch/PR."""
    d = validate_deployment(deployment)
    object_fields(request, REQUEST_FIELDS, 'protected submission request')
    require(type(request['schema_version']) is int and request['schema_version'] == 2 and
            isinstance(request['task_id'], str) and re.fullmatch('[0-9a-f]{32}', request['task_id']) and
            sha(request['configuration_revision']) and request['deployment_digest'] == digest(d) and sha(request['base']) and
            all(positive(request[k]) for k in ('issued', 'run_id', 'attempt')) and type(now) is int and
            request['issued'] <= now < d['expires'] and d['state'] == 'active', 'current protected task binding required')
    return _submit(api, d, request, files)


def _submit(api, d, request, files):
    """Exact content-addressed writes after the caller's domain admission."""
    manifest = export_manifest(files)  # Refuse malformed candidate bytes before any API mutation.
    p, root = d['policy'], '/repos/' + d['policy']['repository']
    repo = api.get(root)
    require(repo['id'] == p['repository_id'] and repo['default_branch'] == p['target'], 'submission repository changed')
    visible = api.pages('/installation/repositories', 'repositories')
    require([r['id'] for r in visible] == [p['repository_id']], 'coding token must target only the source repository')
    slug, bot = d['resources'].get('coding_slug', ''), d['resources'].get('coding_bot_id', '')
    require(re.fullmatch('[a-z0-9][a-z0-9-]{0,99}', slug) and re.fullmatch('[1-9][0-9]{0,19}', bot) and
            p['coding_actors'] == [int(bot)], 'registered coding bot required')
    actor = api.get('/users/' + quote(slug + '[bot]', safe=''))
    require(actor['id'] == int(bot) and actor.get('type') == 'Bot', 'coding bot identity changed')
    expected = {name: {'mode': item['mode'], 'sha': item['sha']} for name, item in manifest.items()}
    branch = 'agentic/task-' + request['task_id']
    message = 'AGENTIC task ' + request['task_id'] + '\n\n' + digest({'request': request, 'files': manifest})
    author = {'name': slug + '[bot]', 'email': bot + '+' + slug + '[bot]@users.noreply.github.com',
              'date': datetime.fromtimestamp(request['issued'], timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}

    def inspect_commit(head):
        value = api.get(root + '/git/commits/' + head)
        require(value.get('sha') == head and value.get('message') == message and
                [parent['sha'] for parent in value['parents']] == [request['base']] and
                value.get('author') == author and value.get('committer') == author,
                'task branch does not contain the exact authorized submission')
        tree = value['tree']['sha']
        require(tree_files(api, root, tree) == expected, 'submitted file tree differs from the validated export')
        return tree

    head = existing_ref(api, root, branch)
    if head is None:
        base_tree = api.get(root + '/git/commits/' + request['base'])['tree']['sha']
        require(tree_files(api, root, base_tree) != expected, 'task produced no source changes')
        entries = []
        for path, item in sorted(manifest.items()):
            blob = api.post(root + '/git/blobs', {'encoding': 'base64',
                'content': base64.b64encode(files[path]['content']).decode()})['sha']
            require(blob == item['sha'], 'created submission blob differs')
            entries.append({'path': path, 'mode': item['mode'], 'type': 'blob', 'sha': blob})
        tree = api.post(root + '/git/trees', {'tree': entries})['sha']
        require(tree_files(api, root, tree) == expected, 'created submission tree differs')
        head = api.post(root + '/git/commits', {'message': message, 'tree': tree, 'parents': [request['base']],
                                             'author': author, 'committer': author})['sha']
        inspect_commit(head)
        # Creation only. No force/update path can overwrite another task branch.
        api.post(root + '/git/refs', {'ref': 'refs/heads/' + branch, 'sha': head})
        require(existing_ref(api, root, branch) == head, 'task branch creation readback differs')
    tree = inspect_commit(head)
    owner = p['repository'].split('/')[0]
    query = urlencode({'state': 'all', 'head': owner + ':' + branch, 'base': p['target']})
    prs = api.pages(root + '/pulls?' + query)
    require(len(prs) <= 1, 'ambiguous task pull requests')
    marker = '<!-- agentic-task:' + digest(request) + ' -->'
    if prs:
        pr = prs[0]
    else:
        pr = api.post(root + '/pulls', {'head': branch, 'base': p['target'], 'draft': False,
            'title': 'AGENTIC task ' + request['task_id'], 'body': marker + '\nExport: ' + digest(manifest)})
    require(positive(pr['number']), 'task pull request identity unavailable')
    pr = api.get(root + '/pulls/' + str(pr['number']))
    require(pr['state'] == 'open' and pr.get('merged') is False and pr.get('draft') is False and
            pr['head']['ref'] == branch and pr['head']['sha'] == head and pr['head']['repo']['id'] == p['repository_id'] and
            pr['base']['ref'] == p['target'] and pr['base']['repo']['id'] == p['repository_id'] and
            pr['user']['id'] == int(bot) and pr['user'].get('type') == 'Bot' and marker in pr.get('body', ''),
            'task pull request does not match the registered submission')
    require(existing_ref(api, root, branch) == head, 'task branch moved during submission readback')
    return {'schema_version': 2, 'task_id': request['task_id'], 'branch': branch, 'head': head, 'tree': tree,
        'pr': pr['number'], 'export_digest': digest(manifest), 'configuration_revision': request['configuration_revision'],
        'deployment_digest': digest(d), 'app_id': d['apps']['coding'], 'bot_id': int(bot),
        'run_id': request['run_id'], 'attempt': request['attempt'], 'admission_established': False}
