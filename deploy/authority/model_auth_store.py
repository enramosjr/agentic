"""Separate encrypted auth-state branch. No refresh token is redeemed here.

The caller authenticates its dedicated job before supplying admitted_owner. Initial
credential installation additionally requires the approved configuration session.
Routine same-identity rotation uses its own CAS intent, never deployment generation
or a timeout-based unlock. Only encrypted vault envelopes enter Git.
"""
import base64
import copy
import hashlib
import json
import re
from urllib.parse import quote

from configuration import require_session
from model_vault import validate_encrypted
from registry import Registry
from trusted_ci_github import HostRefusal
from trusted_ci_policy import digest, object_fields, positive, require, sha

BRANCH = 'agentic-model-auth'
DOCUMENT = '.agentic-authority/model-auth.json'
MAX_STATE = 128 * 1024
OWNER_FIELDS = ('workflow_sha', 'run_id', 'attempt')
PENDING_FIELDS = ('workflow_sha run_id attempt operation_id started expected_generation expected_vault_digest').split()


def validate_state(value, authority_id):
    object_fields(value, ('schema_version', 'vault', 'pending'), 'encrypted auth state')
    require(type(value['schema_version']) is int and value['schema_version'] == 1, 'unsupported encrypted auth state')
    vault = validate_encrypted(value['vault'])
    require(vault['authority_repository_id'] == authority_id, 'encrypted auth authority differs')
    pending = value['pending']
    if pending is not None:
        object_fields(pending, PENDING_FIELDS, 'pending model refresh')
        require(sha(pending['workflow_sha']) and all(positive(pending[k]) for k in
                ('run_id', 'attempt', 'started', 'expected_generation')) and
                isinstance(pending['operation_id'], str) and re.fullmatch('[0-9a-f]{32}', pending['operation_id']) and
                pending['expected_generation'] == vault['generation'] and pending['expected_vault_digest'] == digest(vault),
                'pending refresh identity or generation differs')
    return value


class AuthStore:
    def __init__(self, api, repository, identity, workflow_sha, admitted_owner=None, session=None):
        require(sha(workflow_sha), 'pinned auth software revision required')
        self.git = Registry(api, dict(schema_version=2, repository=repository, repository_id=identity, registry_branch=BRANCH))
        self.api, self.repository, self.identity = api, repository, identity
        self.workflow_sha, self.owner, self.session = workflow_sha, copy.deepcopy(admitted_owner), session
        if self.owner is not None:
            object_fields(self.owner, OWNER_FIELDS, 'admitted model auth owner')
            require(self.owner['workflow_sha'] == workflow_sha and positive(self.owner['run_id']) and
                    positive(self.owner['attempt']), 'admitted model auth owner differs')

    def _context(self):
        repos = self.api.pages('/installation/repositories', 'repositories')
        require(len(repos) == 1 and positive(repos[0]['id']) and repos[0]['id'] == self.identity,
                'auth storage token must target only the authority repository')
        repo = self.api.get(self.git.root)
        branch = repo.get('default_branch')
        require(repo['id'] == self.identity and repo.get('private') is True and isinstance(branch, str) and
                re.fullmatch('[A-Za-z0-9][A-Za-z0-9_/-]{0,99}', branch) and branch != BRANCH and
                self.git.ref(branch) == self.workflow_sha, 'auth storage authority or software differs')

    def read(self):
        self._context()
        try:
            head = self.git.ref(BRANCH)
        except HostRefusal as error:
            require(error.status == 404, 'auth branch unavailable')
            head = None
        base = head or self.workflow_sha
        tree, entries = self.git.tree(base)
        for name, entry in entries.items():
            if DOCUMENT.startswith(name + '/'):
                require(entry['type'] == 'tree' and entry['mode'] == '040000', 'auth document ancestor is not a directory')
            require(not name.startswith(DOCUMENT + '/'), 'auth document collides with an existing directory')
        if head is None:
            require(DOCUMENT not in entries, 'auth bootstrap would overwrite an existing software file')
            state, blob = None, None
        else:
            state, blob = self.git.blob(head, DOCUMENT)
            validate_state(state, self.identity)
        return dict(branch_head=head, base=base, tree=tree, blob_sha=blob, state=state,
                    software_revision=self.workflow_sha)

    def _owner(self):
        require(self.owner is not None, 'admitted dedicated auth job required before refresh mutation')

    def _write(self, expected, state, effect):
        validate_state(state, self.identity)
        raw = (json.dumps(state, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()
        require(len(raw) <= MAX_STATE, 'encrypted auth state exceeds limit')
        def guard():
            effect()
            require(self.read() == expected, 'encrypted auth state changed; do not repeat the OAuth grant')
        guard()
        blob = self.api.post(self.git.root + '/git/blobs', {'encoding': 'base64', 'content': base64.b64encode(raw).decode()})['sha']
        require(blob == hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest(), 'auth blob identity differs')
        guard()
        tree = self.api.post(self.git.root + '/git/trees', {'base_tree': expected['tree'],
            'tree': [dict(path=DOCUMENT, mode='100644', type='blob', sha=blob)]})['sha']
        require(sha(tree), 'auth tree identity missing')
        guard()
        commit = self.api.post(self.git.root + '/git/commits', dict(message='AGENTIC encrypted model state ' + digest(state),
            tree=tree, parents=[expected['base']]))['sha']
        require(sha(commit), 'auth commit identity missing')
        guard()
        try:
            if expected['branch_head'] is None:
                self.api.post(self.git.root + '/git/refs', {'ref': 'refs/heads/' + BRANCH, 'sha': commit})
            else:
                self.api.fetch(self.git.root + '/git/refs/heads/' + quote(BRANCH, safe=''), method='PATCH',
                               data={'sha': commit, 'force': False})
        except Exception:
            # Recovery proves only this exact pointer update. It never repeats an
            # OAuth request, clears a pending intent, or accepts matching state on
            # a different commit with unrelated changes.
            observed = self.read()
            require(observed['branch_head'] == commit and observed['state'] == state and observed['blob_sha'] == blob,
                    'auth state update is uncertain; preserve the refresh intent')
            return observed
        observed = self.read()
        require(observed['branch_head'] == commit and observed['state'] == state and observed['blob_sha'] == blob,
                'auth state readback differs; preserve the refresh intent')
        return observed

    def initialize(self, vault):
        def effect(): require_session(self.session, 'credentials', self.repository + ':model-vault')
        effect()
        validate_encrypted(vault)
        require(vault['authority_repository_id'] == self.identity and vault['generation'] == 1,
                'initial encrypted auth generation must be one')
        before = self.read()
        state = dict(schema_version=1, vault=vault, pending=None)
        if before['state'] is not None:
            require(before['state'] == state, 'auth initialization cannot replace an existing session')
            return before
        return self._write(before, state, effect)

    def claim(self, expected, operation_id, now):
        self._owner()
        require(isinstance(operation_id, str) and re.fullmatch('[0-9a-f]{32}', operation_id) and positive(now),
                'model refresh operation and clock required')
        state = expected['state']
        require(state is not None and state['pending'] is None, 'another model refresh remains pending; expiry cannot unlock it')
        pending = dict(self.owner, operation_id=operation_id, started=now,
            expected_generation=state['vault']['generation'], expected_vault_digest=digest(state['vault']))
        return self._write(expected, dict(schema_version=1, vault=state['vault'], pending=pending), self._owner)

    def complete(self, expected, operation, replacement):
        self._owner()
        state = expected['state']
        require(state is not None and state['pending'] is not None and state['pending'] == operation and
                all(operation[k] == self.owner[k] for k in OWNER_FIELDS), 'owned pending model refresh required')
        validate_encrypted(replacement)
        old = state['vault']
        require(all(replacement[k] == old[k] for k in ('authority_repository_id', 'session_id', 'identity_digest')) and
                replacement['generation'] == old['generation'] + 1 and replacement['ciphertext'] != old['ciphertext'],
                'routine model refresh cannot switch identity or skip generations')
        return self._write(expected, dict(schema_version=1, vault=replacement, pending=None), self._owner)
