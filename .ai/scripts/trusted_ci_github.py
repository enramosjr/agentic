"""GitHub authority transport and merge-bound publication; no candidate execution."""
from __future__ import annotations

import base64
import hashlib
import io
import json
import re
from urllib import error, parse, request
import zipfile

from trusted_ci_policy import (Refusal, digest, loads, positive, require, sha,
                               validate_policy, validate_report, validate_snapshot)


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class HostRefusal(Refusal):
    def __init__(self, status, category='unknown', obligation=None):
        self.status, self.category, self.obligation = status, category, obligation
        super().__init__('GitHub API refused request (HTTP ' + str(status) + ')')


def denial_category(status, body):
    try:
        message = loads(body).get('message', '').strip().lower()
    except (Refusal, AttributeError):
        return 'unknown'
    if status == 422:
        scope_denials = {
            'the permissions requested are not granted to this installation': 'permission_scope',
            'there is at least one repository that does not exist or is not accessible to the parent installation': 'repository_scope',
        }
        category = scope_denials.get(message.rstrip('.'))
        if category:
            return category
    if status in (403, 405, 422) and re.search(r'required status check "[^"\r\n]+"', message):
        return 'required_check'
    if status in (403, 405, 422) and ('required approving review' in message or
            re.search(r'at least [1-9][0-9]* approving reviews? (is|are) required', message)):
        return 'required_review'
    if status in (403, 422) and ('changes must be made through a pull request' in message or
                                 message.startswith('cannot update this protected ref')):
        return 'protected_update'
    return 'unknown'


class GitHub:
    def __init__(self, token, opener=None):
        require(isinstance(token, str) and token and '\n' not in token, 'GitHub credential required')
        self.token = token
        self.opener = opener or request.build_opener(NoRedirect())

    def fetch(self, path, method='GET', data=None, binary=False, limit=1024 * 1024):
        require(path.startswith('/') and not path.startswith('//') and '\r' not in path and '\n' not in path,
                'invalid API path')
        url = 'https://api.github.com' + path
        headers = {'Authorization': 'Bearer ' + self.token, 'Accept': 'application/vnd.github+json',
                   'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'AGENTIC-trusted-ci'}
        body = json.dumps(data).encode() if data is not None else None
        if body is not None:
            headers['Content-Type'] = 'application/json'
        for redirects in range(4):
            try:
                with self.opener.open(request.Request(url, body, headers, method=method), timeout=30) as response:
                    raw = response.read(limit + 1)
                    require(len(raw) <= limit, 'API response exceeds limit')
                    return raw if binary else loads(raw)
            except error.HTTPError as exc:
                if binary and method == 'GET' and exc.code in (301, 302, 303, 307):
                    url = exc.headers.get('Location', '')
                    host = parse.urlparse(url)
                    require(host.scheme == 'https' and host.port in (None, 443) and not host.username and
                            (host.hostname == 'codeload.github.com' or
                             (host.hostname or '').endswith('.blob.core.windows.net') or
                             (host.hostname or '').endswith('.githubusercontent.com')),
                            'untrusted download redirect')
                    headers = {'User-Agent': 'AGENTIC-trusted-ci'}  # never forward bearer credentials
                else:
                    raw_error = exc.read(8193)
                    category = denial_category(exc.code, raw_error) if len(raw_error) <= 8192 else 'unknown'
                    obligation = None
                    if category == 'required_check':
                        match = re.search(r'required status check "([^"\r\n]+)"',
                                          loads(raw_error)['message'], re.IGNORECASE)
                        obligation = match.group(1) if match else None
                    raise HostRefusal(exc.code, category, obligation) from exc
            except (error.URLError, OSError, TimeoutError) as exc:
                raise Refusal('GitHub API unavailable') from exc
        raise Refusal('too many download redirects')

    def get(self, path):
        return self.fetch(path)

    def post(self, path, data):
        return self.fetch(path, 'POST', data)

    def pages(self, path, collection=None):
        result = []
        for page in range(1, 101):
            value = self.get(path + ('&' if '?' in path else '?') +
                             parse.urlencode(dict(per_page=100, page=page)))
            entries = value.get(collection) if collection and isinstance(value, dict) else value
            require(isinstance(entries, list) and len(entries) <= 100, 'invalid paginated response')
            result.extend(entries)
            if len(entries) < 100:
                if collection and 'total_count' in value:
                    require(value['total_count'] == len(result), 'incomplete API pagination')
                return result
        raise Refusal('API page limit exceeded')


def repo_path(p):
    validate_policy(p)
    return '/repos/' + p['repository']


def contents(api, repository, path, ref):
    data = api.get('/repos/' + repository + '/contents/' + parse.quote(path, safe='/') +
                   '?ref=' + parse.quote(ref, safe=''))
    require(data.get('encoding') == 'base64' and isinstance(data.get('content'), str), 'file content unavailable')
    try:
        return base64.b64decode(''.join(data['content'].split()), validate=True)
    except ValueError as exc:
        raise Refusal('invalid host file encoding') from exc


def current_snapshot(api, p, pr_number, run_id, attempt):
    root = repo_path(p)
    require(positive(pr_number), 'numeric PR required')
    require(api.get(root)['id'] == p['repository_id'], 'repository identity changed')
    require(api.get('/repos/' + p['authority_repository'])['id'] == p['authority_repository_id'],
            'authority identity changed')
    pr = api.get(root + '/pulls/' + str(pr_number))
    require(pr['state'] == 'open' and not pr['draft'] and pr['base']['ref'] == p['target'],
            'PR must be open, ready and on the approved target')
    head, base = pr['head']['sha'], pr['base']['sha']
    require(api.get(root + '/branches/' + p['target'])['commit']['sha'] == base, 'base changed')
    merge = api.get(root + '/git/ref/pull/' + str(pr_number) + '/merge')['object']['sha']
    parents = api.get(root + '/git/commits/' + merge)['parents']
    require([x['sha'] for x in parents] == [base, head], 'synthetic merge parents mismatch')
    marker = loads(contents(api, p['repository'], '.agentic-trusted-ci.json', base))
    require(marker == dict(epoch=p['epoch'], policy_digest=digest(p)), 'unapproved target policy epoch')
    candidate_marker = loads(contents(api, p['repository'], '.agentic-trusted-ci.json', merge))
    require(candidate_marker == marker or digest(candidate_marker) in p['transitions'],
            'candidate proposes an unapproved policy transition')
    s = dict(repository_id=p['repository_id'], pr=pr_number, head=head, base=base, merge=merge,
             epoch=p['epoch'], policy_digest=digest(p), verifier_sha=p['verifier_sha'], image=p['image'],
             authority_repository_id=p['authority_repository_id'], workflow_sha=p['workflow_sha'],
             run_id=run_id, run_attempt=attempt)
    return validate_snapshot(s, p)


def independent_approval(api, p, pr):
    reviews = api.pages(repo_path(p) + '/pulls/' + str(pr['number']) + '/reviews')
    latest = {}
    for review in reviews:
        actor = review['user']['id']
        if review['state'] == 'COMMENTED':
            continue
        require(positive(review['id']), 'invalid review identity')
        previous = latest.get(actor)
        if previous is None or review['id'] > previous['id']:
            latest[actor] = review
    require(not any(r['state'] == 'CHANGES_REQUESTED' for r in latest.values()), 'outstanding change request')
    approved = [r for actor, r in latest.items() if actor in p['reviewers'] and
                actor not in p['coding_actors'] and actor != pr['user']['id'] and
                r['state'] == 'APPROVED' and r['commit_id'] == pr['head']['sha']]
    require(approved, 'current independent approval required')
    return approved


def authority_run(api, p, run_id, attempt, completed=False):
    root = '/repos/' + p['authority_repository']
    run = api.get(root + '/actions/runs/' + str(run_id))
    path = run['path'].split('@', 1)
    require(path[0] == p['workflow'] and (len(path) == 1 or path[1] in
            (run.get('head_branch'), 'refs/heads/' + str(run.get('head_branch')), p['workflow_sha'])),
            'wrong authority workflow path or ref')
    require(positive(run['workflow_id']), 'workflow identity missing')
    workflow = api.get(root + '/actions/workflows/' + str(run['workflow_id']))
    require(workflow['id'] == run['workflow_id'] and workflow['path'] == p['workflow'], 'workflow identity mismatch')
    require(run['repository']['id'] == p['authority_repository_id'] and
            run['head_sha'] == p['workflow_sha'] and
            run['run_attempt'] == attempt and run['event'] in ('schedule', 'workflow_dispatch'),
            'wrong authority execution provenance')
    if completed:
        require(run['status'] == 'completed' and run['conclusion'] == 'success', 'authority run not successful')
    return run


def artifact_report(api, p, run_id, attempt, pr_number, negative=False):
    root = '/repos/' + p['authority_repository']
    authority_run(api, p, run_id, attempt)
    jobs = api.pages(root + '/actions/runs/' + str(run_id) + '/attempts/' + str(attempt) + '/jobs', 'jobs')
    required = [j for j in jobs if j['name'] == 'verify (' + str(pr_number) + ')']
    expected = 'failure' if negative else 'success'
    require(len(required) == 1 and required[0]['conclusion'] == expected, 'trusted verification job outcome mismatch')
    artifacts = api.pages(root + '/actions/runs/' + str(run_id) + '/artifacts', 'artifacts')
    expected = 'report-' + str(pr_number) + '-' + str(attempt)
    matches = [a for a in artifacts if a['name'] == expected]
    require(len(matches) == 1, 'missing or ambiguous authority artifact')
    a = matches[0]
    require(not a['expired'] and a['workflow_run']['id'] == run_id and
            a['workflow_run']['head_sha'] == p['workflow_sha'], 'artifact execution mismatch')
    raw = api.fetch(root + '/actions/artifacts/' + str(a['id']) + '/zip', binary=True, limit=2 * 1024 * 1024)
    require(a.get('digest') == 'sha256:' + hashlib.sha256(raw).hexdigest(), 'artifact digest mismatch')
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries = archive.infolist()
            require(len(entries) == 1 and entries[0].filename == 'report.json' and
                    entries[0].file_size <= 1024 * 1024 and
                    not (entries[0].external_attr >> 16 & 0o170000) == 0o120000,
                    'unsafe report artifact')
            return loads(archive.read(entries[0]))
    except (zipfile.BadZipFile, RuntimeError, OSError) as exc:
        raise Refusal('invalid report artifact') from exc


def publish(read_api, issuer, p, pr_number, run_id, attempt):
    """Run only in a fresh trusted job with an independently minted App token."""
    report = artifact_report(read_api, p, run_id, attempt, pr_number)
    current = current_snapshot(read_api, p, pr_number, run_id, attempt)
    validate_report(report, p, current)
    pr = read_api.get(repo_path(p) + '/pulls/' + str(pr_number))
    independent_approval(read_api, p, pr)
    require(current_snapshot(read_api, p, pr_number, run_id, attempt) == current, 'candidate changed during publication')
    result = issuer.post(repo_path(p) + '/check-runs', dict(
        name=p['check_name'], head_sha=current['merge'], status='completed', conclusion='success',
        external_id=digest(report), details_url='https://github.com/' + p['authority_repository'] +
        '/actions/runs/' + str(run_id), output=dict(title='Trusted critical acceptance passed',
        summary='Exact merge candidate and approved policy verified; independent host authorization remains required.')))
    require(result['app']['id'] == p['app_id'] and result['head_sha'] == current['merge'], 'wrong check issuer')
    return result
