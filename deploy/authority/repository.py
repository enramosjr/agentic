"""Approved atomic software rollout in an independent private authority repository."""
from __future__ import annotations

import base64
import hashlib
from pathlib import Path, PurePosixPath
import re
import sys
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '.ai/scripts'))
from trusted_ci_policy import digest, loads, object_fields, require, sha
from authority_protocol import fingerprint

MARKER = '.agentic-authority/installation.json'


def valid_path(name):
    require(isinstance(name, str) and len(name) <= 240 and
            not PurePosixPath(name).is_absolute() and '\\' not in name and
            all(re.fullmatch('[A-Za-z0-9_.-]+', p) and p not in ('.', '..', '.git') for p in name.split('/')) and
            (name.startswith(('.ai/scripts/', 'deploy/authority/', '.github/workflows/')) or
             name in ('.github/CODEOWNERS', '.agentic-authority/bootstrap.json', '.agentic-authority/identities.json')),
            'release path escapes owned authority software')


class Repository:
    def __init__(self, api, name, identity, branch, session=None):
        require(re.fullmatch('[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', name) and
                all(p not in ('.', '..') for p in name.split('/')), 'invalid authority repository')
        require(type(identity) is int and identity > 0 and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_/-]{0,99}', branch) and
                '..' not in branch and '//' not in branch, 'invalid authority identity or branch')
        self.api, self.name, self.identity, self.branch = api, name, identity, branch
        self.root = '/repos/' + name
        self.session = session

    def guard(self):
        from configuration import require_session
        require_session(self.session, 'software', self.name + ':' + self.branch)

    def blob(self, identity):
        require(sha(identity), 'invalid remote blob identity')
        value = self.api.get(self.root + '/git/blobs/' + identity)
        require(value['encoding'] == 'base64' and len(value['content']) <= 2 * 1024 * 1024,
                'remote release blob exceeds limit')
        raw = base64.b64decode(value['content'], validate=False)
        require(len(raw) <= 1024 * 1024, 'remote release blob exceeds limit')
        return raw

    def inspect(self, revision=None):
        repo = self.api.get(self.root)
        require(repo['id'] == self.identity and repo['private'] is True and repo['default_branch'] == self.branch,
                'independent authority identity changed')
        base = revision if revision is not None else self.api.get(self.root + '/git/ref/heads/' + quote(self.branch, safe=''))['object']['sha']
        require(sha(base), 'authority base revision missing')
        tree = self.api.get(self.root + '/git/commits/' + base)['tree']['sha']
        value = self.api.get(self.root + '/git/trees/' + tree + '?recursive=1')
        require(value.get('truncated') is False and len(value['tree']) <= 20000, 'complete authority tree required')
        entries = {v['path']: (v['mode'], v['sha']) for v in value['tree'] if v['type'] != 'tree'}
        manifest = {'schema_version': 2, 'files': {}, 'enforcement_active': False}
        if MARKER in entries:
            require(entries[MARKER][0] == '100644', 'installation marker must be a plain file')
            manifest = loads(self.blob(entries[MARKER][1]))
            object_fields(manifest, ('schema_version', 'files', 'enforcement_active'), 'software inventory')
            require(type(manifest['schema_version']) is int and manifest['schema_version'] == 2 and
                    manifest['enforcement_active'] is False and isinstance(manifest['files'], dict) and
                    len(manifest['files']) <= 500, 'invalid software inventory')
        for name, expected in manifest['files'].items():
            valid_path(name)
            require(fingerprint(expected) and name in entries and entries[name][0] == '100644' and
                    hashlib.sha256(self.blob(entries[name][1])).hexdigest() == expected,
                    'installed software drift; preserve changes for explicit repair')
        return base, tree, entries, manifest

    def preview(self, files):
        require(isinstance(files, dict) and len(files) <= 500, 'bounded release file inventory required')
        for name, raw in files.items():
            valid_path(name)
            require(isinstance(raw, bytes) and len(raw) <= 1024 * 1024, 'bounded release file bytes required')
        require(sum(map(len, files.values())) <= 64 * 1024 * 1024, 'release exceeds limit')
        base, tree, entries, old = self.inspect()
        payload_paths = set(files) | {MARKER}
        for name in payload_paths:
            for other in set(entries) | payload_paths:
                require(name == other or not (name.startswith(other + '/') or other.startswith(name + '/')),
                        'release path collides with an existing file or directory')
        for name in files:
            require(name not in entries or name in old['files'], 'release would overwrite adopter-owned authority data')
        new = {'schema_version': 2, 'files': {k: hashlib.sha256(v).hexdigest() for k, v in files.items()},
               'enforcement_active': False}
        return {'schema_version': 2, 'repository_id': self.identity, 'repository': self.name,
                'branch': self.branch, 'base': base, 'tree': tree, 'previous': old, 'desired': new}

    def apply(self, files, approval):
        self.guard()
        plan = self.preview(files)
        require(digest(plan) == approval, 'fresh exact authority software preview approval required')
        if plan['previous'] == plan['desired']:
            return {'revision': plan['base'], 'changed': False, 'enforcement_active': False}
        import json
        payload = dict(files)
        payload[MARKER] = (json.dumps(plan['desired'], sort_keys=True) + '\n').encode()
        changes = []
        for name, raw in sorted(payload.items()):
            self.guard()
            value = self.api.post(self.root + '/git/blobs',
                                  {'encoding': 'base64', 'content': base64.b64encode(raw).decode()})
            require(sha(value['sha']), 'created blob identity missing')
            changes.append(dict(path=name, mode='100644', type='blob', sha=value['sha']))
        changes.extend(dict(path=name, mode='100644', type='blob', sha=None)
                       for name in sorted(set(plan['previous']['files']) - set(files)))
        self.guard()
        tree = self.api.post(self.root + '/git/trees', {'base_tree': plan['tree'], 'tree': changes})['sha']
        require(sha(tree), 'created tree identity missing')
        self.guard()
        commit = self.api.post(self.root + '/git/commits',
            {'message': 'AGENTIC approved software ' + digest(plan), 'tree': tree, 'parents': [plan['base']]})['sha']
        require(sha(commit), 'created commit identity missing')
        require(self.inspect()[0] == plan['base'], 'authority changed during software rollout')
        self.session.allow_software_revision(self.name, self.branch, commit)
        self.guard()
        self.api.fetch(self.root + '/git/refs/heads/' + quote(self.branch, safe=''), method='PATCH',
                       data={'sha': commit, 'force': False})
        observed = self.inspect()
        require(observed[0] == commit and observed[3] == plan['desired'], 'authority software readback differs')
        return {'revision': commit, 'changed': True, 'enforcement_active': False}

    def authenticate_transition(self, plan, revision):
        """Read-only proof of an exact prepared commit and its approved inventory."""
        object_fields(plan, ('schema_version', 'repository_id', 'repository', 'branch', 'base', 'tree', 'previous', 'desired'),
                      'approved software transition')
        require(type(plan['schema_version']) is int and plan['schema_version'] == 2 and
                plan['repository_id'] == self.identity and plan['repository'] == self.name and
                plan['branch'] == self.branch and sha(plan['base']) and sha(plan['tree']) and sha(revision),
                'approved software transition scope differs')
        old = self.inspect(plan['base'])
        new = self.inspect(revision)
        require(old[1] == plan['tree'] and old[3] == plan['previous'] and new[3] == plan['desired'],
                'prepared software inventory differs')
        commit = self.api.get(self.root + '/git/commits/' + revision)
        require(commit['sha'] == revision and [p['sha'] for p in commit['parents']] == [plan['base']] and
                commit['message'] == 'AGENTIC approved software ' + digest(plan), 'prepared software commit differs')
        affected = set(plan['previous']['files']) | set(plan['desired']['files']) | {MARKER}
        require({k: v for k, v in old[2].items() if k not in affected} ==
                {k: v for k, v in new[2].items() if k not in affected} and
                set(new[2]) == (set(old[2]) - affected) | set(plan['desired']['files']) | {MARKER},
                'prepared software changed unrelated authority files')
        return new

    def resume_transition(self, approved_plan, revision):
        """Resume only this prepared pointer, never rebuild a replacement commit."""
        self.guard()
        self.authenticate_transition(approved_plan, revision)
        current = self.inspect()[0]
        require(current in (approved_plan['base'], revision), 'authority changed outside the prepared transition')
        if current == approved_plan['base']:
            self.session.allow_software_revision(self.name, self.branch, revision)
            self.guard()
            try:
                self.api.fetch(self.root + '/git/refs/heads/' + quote(self.branch, safe=''), method='PATCH',
                               data={'sha': revision, 'force': False})
            except Exception:
                require(self.inspect()[0] == revision, 'prepared software pointer remains uncertain')
        observed = self.authenticate_transition(approved_plan, revision)
        require(self.inspect()[0] == revision, 'prepared software readback differs')
        return {'revision': observed[0], 'changed': current != revision, 'enforcement_active': False}
