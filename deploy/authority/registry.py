"""Independent policy branch and CAS journal, separate from pinned software."""
from __future__ import annotations

import base64
import copy
import json
import hashlib
from pathlib import Path
import re
import sys
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '.ai/scripts'))
from authority_protocol import configuration_digest, validate_deployment
from trusted_ci_github import HostRefusal
from trusted_ci_policy import digest, loads, object_fields, positive, require, sha
import operation_fence

DOCUMENT = '.agentic-authority/deployment.json'
OPERATION = '.agentic-authority/operation.json'
TRIAL = '.agentic-authority/trial-handoff.json'
MAX_DOCUMENT = 512 * 1024


def trial_reference(record):
    suffix = '-case' if record.get('kind') == 'trial-case-handoff' else '-case-ready' if record.get('kind') == 'trial-case-ready' else ''
    if suffix and record.get('candidate',{}).get('name') in ('coding-update','missing-approval','expired-proof','authority-outage','bad-acceptance'):
        suffix += '-'+record['candidate']['name']
    return 'agentic-trial-' + record['task_id'] + suffix + ('-execution' if record['execution'] else '')


class Registry:
    """Mutations require a trusted setup caller; runtime receives a reader only."""

    def __init__(self, api, coordinates):
        object_fields(coordinates, ('schema_version', 'repository', 'repository_id', 'registry_branch'), 'registry coordinates')
        c = coordinates
        require(type(c['schema_version']) is int and c['schema_version'] == 2 and positive(c['repository_id']),
                'invalid registry identity')
        require(isinstance(c['repository'], str) and re.fullmatch('[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', c['repository']) and
                all(p not in ('.', '..') for p in c['repository'].split('/')), 'invalid registry repository')
        branch = c['registry_branch']
        require(isinstance(branch, str) and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_/-]{0,99}', branch) and
                '..' not in branch and '//' not in branch and not branch.endswith('/'), 'invalid registry branch')
        self.api, self.coordinates = api, dict(c)
        self.root = '/repos/' + c['repository']

    def ref(self, branch):
        value = self.api.get(self.root + '/git/ref/heads/' + quote(branch, safe=''))['object']['sha']
        require(sha(value), 'registry revision unavailable')
        return value

    def tree(self, revision):
        tree = self.api.get(self.root + '/git/commits/' + revision)['tree']['sha']
        require(sha(tree), 'registry tree identity unavailable')
        result = self.api.get(self.root + '/git/trees/' + tree + '?recursive=1')
        require(result.get('truncated') is False and isinstance(result.get('tree'), list) and
                len(result['tree']) <= 20000, 'complete bounded registry tree required')
        entries = {entry['path']: entry for entry in result['tree']}
        require(len(entries) == len(result['tree']), 'ambiguous registry tree paths')
        for name, entry in entries.items():
            if any(path.startswith(name + '/') for path in (DOCUMENT, OPERATION, TRIAL)):
                require(entry['type'] == 'tree' and entry['mode'] == '040000', 'registry ancestor is not a directory')
            require(not any(name.startswith(path + '/') for path in (DOCUMENT, OPERATION, TRIAL)),
                    'registry document collides with adopter-owned directory')
        return tree, entries

    def blob(self, revision, path):
        _, entries = self.tree(revision)
        entry = entries.get(path)
        require(entry is not None and entry['type'] == 'blob' and entry['mode'] == '100644' and sha(entry['sha']),
                'plain registry Git blob required')
        value = self.api.get(self.root + '/git/blobs/' + entry['sha'])
        require(value.get('sha') == entry['sha'] and value.get('encoding') == 'base64' and
                isinstance(value.get('content'), str) and len(value['content']) <= 768 * 1024,
                'bounded authenticated registry blob required')
        raw = base64.b64decode(value['content'], validate=False)
        require(len(raw) <= MAX_DOCUMENT and hashlib.sha1(
            b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() == entry['sha'],
            'registry blob size or identity differs')
        return loads(raw), entry['sha']

    def document(self, revision):
        return validate_deployment(self.blob(revision, DOCUMENT)[0])

    def binding(self, missing=False, check_software=True):
        c = self.coordinates
        repo = self.api.get(self.root)
        require(repo['id'] == c['repository_id'] and repo.get('private') is True and
                repo['default_branch'] != c['registry_branch'], 'private independent registry identity changed')
        software = self.ref(repo['default_branch'])
        exists = True
        try:
            revision = self.ref(c['registry_branch'])
        except HostRefusal as error:
            require(missing and error.status == 404, 'registry branch unavailable')
            exists, revision = False, software
        deployment, configuration, fence = None, None, operation_fence.empty()
        if exists:
            deployment, configuration = self.blob(revision, DOCUMENT)
            validate_deployment(deployment)
            fence = operation_fence.validate(self.blob(revision, OPERATION)[0])
            p = deployment['policy']
            require(fence['contexts'] and fence['contexts'][-1]['epoch'] == p['epoch'] and
                    fence['contexts'][-1]['check_name'] == p['check_name'] and
                    (deployment['state'] != 'active' or fence['contexts'][-1]['activated']),
                    'registry context history differs from configuration')
            require(p['authority_repository'] == c['repository'] and
                    p['authority_repository_id'] == c['repository_id'], 'registry deployment authority mismatch')
            require(not check_software or p['workflow_sha'] == software, 'authority software drift; explicit repinning required')
            require(self.ref(c['registry_branch']) == revision, 'registry changed during read')
        else:
            require(missing, 'registry not provisioned')
        require(self.ref(repo['default_branch']) == software, 'authority software changed during registry read')
        return {'deployment': deployment, 'configuration_revision': configuration,
                'deployment_digest': digest(deployment) if deployment is not None else None,
                'branch_head': revision, 'branch_exists': exists,
                'software_revision': software, 'fence': fence}

    def read(self):
        return self.binding()['deployment']

    def unchanged(self, binding):
        """Reobserve live pointers to an already authenticated immutable binding.

        This never authenticates caller data or admits a new configuration. Callers
        must first obtain binding() and retain that exact snapshot privately.
        """
        repo = self.api.get(self.root)
        require(repo.get('id') == self.coordinates['repository_id'] and repo.get('private') is True and
                repo.get('default_branch') != self.coordinates['registry_branch'] and
                self.ref(repo['default_branch']) == binding['software_revision'] and
                self.ref(self.coordinates['registry_branch']) == binding['branch_head'],
                'authenticated registry identity, software or configuration moved')
        require(self.ref(repo['default_branch']) == binding['software_revision'], 'registry software moved during readback')
        return repo['default_branch']

    def write(self, expected, value, operation_id=None, before_effect=None):
        validate_deployment(value)
        raw = (json.dumps(value, sort_keys=True, allow_nan=False) + '\n').encode()
        encoded = base64.b64encode(raw).decode()
        require(len(raw) <= MAX_DOCUMENT and len(encoded) <= 768 * 1024,
                'registry record exceeds readable serialization limit')
        c = self.coordinates
        require(value['policy']['authority_repository'] == c['repository'] and
                value['policy']['authority_repository_id'] == c['repository_id'], 'registry authority mismatch')
        before = self.binding(missing=True, check_software=False)
        old = before['deployment']
        if old == value:
            self.binding()
            return
        require((digest(old) if old is not None else None) == expected,
                'registry generation changed; reread before retry')
        require(value['generation'] == (old['generation'] + 1 if old else 1),
                'registry generation must advance exactly once')
        require(value['policy']['workflow_sha'] == before['software_revision'], 'new policy must pin current approved software')
        if before['branch_exists']:
            self.require_configuration_operation(before, operation_id)
            require(callable(before_effect), 'fresh configuration guard required for registry mutation')
        documents = {DOCUMENT: value}
        if not before['branch_exists']:
            documents[OPERATION] = operation_fence.empty(value)
        else:
            fence = copy.deepcopy(before['fence'])
            prior = fence['contexts'][-1]
            policy = value['policy']
            context_changed = policy['epoch'] != prior['epoch'] or policy['check_name'] != prior['check_name']
            authorization_changed = (configuration_digest(old) != configuration_digest(value) or
                value['state'] == 'active' or value['qualification'] not in (None, old['qualification']))
            if prior['activated'] and authorization_changed:
                require(context_changed, 'activated configuration changes require a new epoch and required context')
            if context_changed:
                require(all(policy['epoch'] != c['epoch'] and policy['check_name'] != c['check_name']
                            for c in fence['contexts']), 'epoch and required check context must never be reused')
                fence['contexts'].append(dict(epoch=policy['epoch'], check_name=policy['check_name'], activated=False))
            if value['state'] == 'active':
                fence['contexts'][-1]['activated'] = True
            if fence != before['fence']:
                operation_fence.validate(fence)
                documents[OPERATION] = fence
        after = self._replace(before, documents, before_effect=before_effect)
        require(after['deployment'] == value, 'registry write readback differs')

    def require_configuration_operation(self, binding, operation_id):
        """Call before EVERY configuration side effect, not only the final CAS."""
        pending = binding['fence']['pending']
        require(pending is not None and pending['kind'] == 'configuration' and
                pending['operation_id'] == operation_id, 'owned configuration fence required')
        return pending

    def acquire_operation(self, expected_head, expected_configuration, pending, before_effect=None):
        operation_fence.operation(pending)
        before = self.binding()
        require(before['branch_head'] == expected_head and
                before['configuration_revision'] == expected_configuration and
                before['fence']['pending'] is None, 'registry moved or another operation is pending')
        d, p = before['deployment'], before['deployment']['policy']
        require(pending['configuration_revision'] == expected_configuration and
                pending['deployment_digest'] == digest(d) and pending['workflow_sha'] == p['workflow_sha'] and
                pending['repository_id'] == p['repository_id'] and pending['target'] == p['target'],
                'operation configuration differs')
        fence = copy.deepcopy(before['fence'])
        fence['sequence'] += 1
        fence['pending'] = copy.deepcopy(pending)
        operation_fence.validate(fence)
        return self._replace(before, {OPERATION: fence}, before_effect=before_effect)

    def finalize_operation(self, expected_head, terminal, before_effect=None):
        """Admin only: authenticate terminal artifacts/source state before calling.

        A timeout, missing artifact or open PR is never a terminal receipt. This
        storage primitive verifies the CAS/binding, not remote artifact provenance.
        """
        operation_fence.terminal(terminal)
        before = self.binding(check_software=False)
        fence = copy.deepcopy(before['fence'])
        pending = fence['pending']
        require(before['branch_head'] == expected_head and pending is not None and
                terminal['operation_id'] == pending['operation_id'] and terminal['sequence'] == fence['sequence'],
                'terminal receipt does not own the current fence')
        require((pending['kind'] == 'merge' and terminal['kind'] in ('merged', 'not-submitted')) or
                (pending['kind'] == 'configuration' and terminal['kind'] == 'configuration-complete'),
                'terminal receipt kind differs')
        fence['completed'].append(dict(terminal))
        fence['pending'] = None
        operation_fence.validate(fence)
        return self._replace(before, {OPERATION: fence}, before_effect=before_effect, terminal_only=True)

    def authenticate_setup_progress(self, before, documents):
        """Authenticate one retained native CAS intent, never arbitrary latest state."""
        return self.authenticate_setup_transition(before, documents, self.binding(check_software=False))

    def authenticate_setup_transition(self, before, documents, current):
        """Authenticate an immutable exact transition; callers guard the live tip separately."""
        require(isinstance(documents, dict) and documents and set(documents) <= {DOCUMENT, OPERATION},
                'exact retained native registry documents required')
        old, revision = self.blob(before['branch_head'], DOCUMENT)
        require(revision == before['configuration_revision'] and old == before['deployment'] and
                digest(old) == before['deployment_digest'] and
                self.blob(before['branch_head'], OPERATION)[0] == before['fence'],
                'retained native registry parent differs')
        value, configuration = self.blob(current['branch_head'], DOCUMENT)
        require(value == current['deployment'] and configuration == current['configuration_revision'] and
                digest(value) == current['deployment_digest'] and current['branch_exists'] is True and
                self.blob(current['branch_head'], OPERATION)[0] == current['fence'],
                'retained native registry result differs')
        require(current['deployment'] == documents.get(DOCUMENT, before['deployment']) and
                current['fence'] == documents.get(OPERATION, before['fence']) and
                current['software_revision'] == before['software_revision'], 'native registry progress differs')
        commit = self.api.get(self.root + '/git/commits/' + current['branch_head'])
        require(commit.get('sha') == current['branch_head'] and
                [p['sha'] for p in commit['parents']] == [before['branch_head']] and
                commit['message'] == 'AGENTIC conditional registry ' + digest(documents),
                'native registry progress is not the retained conditional commit')
        _, old_entries = self.tree(before['branch_head'])
        _, new_entries = self.tree(current['branch_head'])
        def unrelated(entries):
            return {name: entry for name, entry in entries.items() if name not in documents and
                    not any(path.startswith(name + '/') for path in documents)}
        require(unrelated(old_entries) == unrelated(new_entries), 'unrelated native registry data changed')
        return current

    def authenticate_transition_write(self, before_head, configuration_revision, old_digest, value,
                                      before_fence, expected_fence):
        """Read-only lost-ack proof of our exact single registry commit, not a retry."""
        current = self.binding(check_software=False)
        require(current['deployment'] == value and current['fence'] == expected_fence,
                'committed transition record or fence differs')
        prior, prior_revision = self.blob(before_head, DOCUMENT)
        require(prior_revision == configuration_revision and digest(prior) == old_digest and
                self.blob(before_head, OPERATION)[0] == before_fence, 'approved prior registry binding differs')
        commit = self.api.get(self.root + '/git/commits/' + current['branch_head'])
        documents = {DOCUMENT: value, OPERATION: expected_fence}
        require(commit.get('sha') == current['branch_head'] and
                [p['sha'] for p in commit['parents']] == [before_head] and
                commit['message'] == 'AGENTIC conditional registry ' + digest(documents),
                'unexpected registry commit after transition')
        _, old_entries = self.tree(before_head)
        _, new_entries = self.tree(current['branch_head'])
        def unrelated(entries):
            return {name: entry for name, entry in entries.items() if name not in (DOCUMENT, OPERATION) and
                    not any(path.startswith(name + '/') for path in (DOCUMENT, OPERATION))}
        require(unrelated(old_entries) == unrelated(new_entries), 'unrelated registry data changed')
        return current

    def _replace(self, before, documents, before_effect=None, terminal_only=False, trial_branch=None):
        """Only fixed registry documents; sibling commits race by nonforce CAS."""
        c = self.coordinates
        require(set(documents) <= {DOCUMENT, OPERATION} or
                set(documents) == {TRIAL} and callable(before_effect) and
                before['deployment']['state'] == 'qualification' and before['deployment']['qualification'] is None and
                before['fence']['pending'] is not None and trial_branch == trial_reference(documents[TRIAL]),
                'unknown or unqualified registry document')
        require(trial_branch is None or set(documents) == {TRIAL}, 'trial branch only accepts its handoff record')
        require(not terminal_only or set(documents) == {OPERATION} and
                before['fence']['pending'] is not None and documents[OPERATION]['pending'] is None and
                documents[OPERATION]['completed'][:-1] == before['fence']['completed'] and
                len(documents[OPERATION]['completed']) == len(before['fence']['completed']) + 1 and
                documents[OPERATION]['sequence'] == before['fence']['sequence'] and
                documents[OPERATION]['contexts'] == before['fence']['contexts'], 'terminal-only fence write required')
        serialized = {}
        for path, value in documents.items():
            raw = (json.dumps(value, sort_keys=True, allow_nan=False) + '\n').encode()
            encoded = base64.b64encode(raw).decode()
            require(len(raw) <= MAX_DOCUMENT and len(encoded) <= 768 * 1024,
                    'registry record exceeds readable serialization limit')
            serialized[path] = encoded
        tree, entries = self.tree(before['branch_head'])
        require(before['branch_exists'] or not {DOCUMENT, OPERATION} & set(entries),
                'software branch contains unowned registry data')
        changes = []
        for path, encoded in serialized.items():
            if before_effect is not None:
                before_effect()
            blob = self.api.post(self.root + '/git/blobs', {'encoding': 'base64', 'content': encoded})['sha']
            require(sha(blob), 'registry blob identity unavailable')
            changes.append({'path': path, 'mode': '100644', 'type': 'blob', 'sha': blob})
        if before_effect is not None:
            before_effect()
        tree = self.api.post(self.root + '/git/trees', {'base_tree': tree, 'tree': changes})['sha']
        require(sha(tree), 'registry tree identity unavailable')
        if before_effect is not None:
            before_effect()
        commit = self.api.post(self.root + '/git/commits', {'message': 'AGENTIC conditional registry ' + digest(documents),
            'tree': tree, 'parents': [before['branch_head']]})['sha']
        require(sha(commit), 'registry commit identity unavailable')
        current = self.binding(missing=True, check_software=False)
        require(current == before, 'registry changed before conditional update')
        if before_effect is not None:
            before_effect()
        def terminal_readback():
            observed = self.binding(check_software=False)
            require(observed['branch_head'] == commit and observed['deployment'] == before['deployment'] and
                    observed['configuration_revision'] == before['configuration_revision'] and
                    observed['deployment_digest'] == before['deployment_digest'] and
                    observed['fence'] == documents[OPERATION], 'terminal update is uncertain; preserve recovery state')
            metadata = self.api.get(self.root + '/git/commits/' + commit)
            require(metadata['sha'] == commit and [p['sha'] for p in metadata['parents']] == [before['branch_head']] and
                    metadata['tree']['sha'] == tree and metadata['message'] == 'AGENTIC conditional registry ' + digest(documents),
                    'terminal commit identity differs')
            _, after_entries = self.tree(commit)
            def unrelated(values):
                return {name: entry for name, entry in values.items() if name != OPERATION and
                        not OPERATION.startswith(name + '/')}
            require(unrelated(entries) == unrelated(after_entries) and
                    self.blob(commit, OPERATION)[1] == changes[0]['sha'], 'terminal commit changed unrelated data')
            return observed
        try:
            if trial_branch is not None:
                self.api.post(self.root + '/git/refs', {'ref': 'refs/heads/' + trial_branch, 'sha': commit})
            elif before['branch_exists']:
                self.api.fetch(self.root + '/git/refs/heads/' + quote(c['registry_branch'], safe=''),
                               method='PATCH', data={'sha': commit, 'force': False})
            else:
                self.api.post(self.root + '/git/refs', {'ref': 'refs/heads/' + c['registry_branch'], 'sha': commit})
        except Exception:
            if not terminal_only: raise
            return terminal_readback()  # Never repeat the write or the merge.
        if terminal_only: return terminal_readback()
        if trial_branch is not None:
            require(self.ref(trial_branch) == commit and self.binding() == before and
                    self.blob(commit, TRIAL)[0] == documents[TRIAL], 'trial publication readback differs')
            return commit
        after = self.binding()
        require(after['branch_head'] == commit, 'registry write readback differs')
        for path, value in documents.items():
            require(after['deployment' if path == DOCUMENT else 'fence'] == value, 'registry document readback differs')
        return after
