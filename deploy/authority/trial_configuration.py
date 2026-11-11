"""Held native configuration for a newly provisioned disposable pair.

Reuse the operator's exact registry/credential/model/control coordinator. Neither
setup consent nor this result admits execution, human review or qualification.
"""
import copy
import json
import re
import secrets

import authority_release
import bootstrap
import operator_setup
from authority_protocol import validate_deployment
from codex_harness import profile
from trusted_ci_policy import digest, require
from trial_setup import Provision


def deployment(provision, pair, origin):
    """Derive only approved critical/runtime settings; never production credentials."""
    r = profile(origin)
    ids = pair['identities']
    p = copy.deepcopy(origin['policy'])
    epoch = secrets.token_hex(16)
    p.update(repository=pair['fixture_repository'], repository_id=pair['fixture_repository_id'],
        authority_repository=pair['authority_repository'], authority_repository_id=pair['authority_repository_id'],
        workflow_sha=pair['software_revision'], app_id=ids['apps']['issuer']['id'],
        coding_actors=[ids['apps']['coding']['actor_id']], merge_actors=[ids['apps']['merge']['actor_id']],
        epoch=epoch, check_name='AGENTIC acceptance ' + epoch, transitions=[])
    resources = {k: r[k] for k in ('model_auth', 'model_id', 'codex_sha', 'codex_version', 'coding_image', 'bundle_sha')}
    resources.update(authority=pair['authority_repository'], operation_id=secrets.token_hex(16),
        identity_digest=digest(ids), identity_record=json.dumps(ids, sort_keys=True, separators=(',', ':')),
        actions_resource='github-actions:' + pair['authority_repository'] + ':' + p['workflow'], container_runtime='docker',
        coding_slug=ids['apps']['coding']['slug'], coding_bot_id=str(ids['apps']['coding']['actor_id']))
    if origin['adapter'] != 'github-actions':
        import cloud
        from trusted_ci_policy import loads
        selected = cloud.validate(loads(r['cloud_configuration']))
        selected.update(authority=pair['authority_repository'],
            branch=provision.api.get('/repos/' + pair['authority_repository'])['default_branch'])
        selected['deployment'] = 'agentic-' + digest(selected)[:16]
        resources['cloud_configuration'] = json.dumps(cloud.validate(selected), sort_keys=True, separators=(',', ':'))
    d = validate_deployment(dict(schema_version=2, policy=p, adapter=origin['adapter'], account=origin['account'],
        resources=resources, generation=1, apps={k: v['id'] for k, v in ids['apps'].items()},
        state='setup', expires=min(origin['expires'], provision.preview['expires']), qualification=None))
    profile(d)
    return d


class _Boundary:
    """Bracket every transport effect/read with the original retained fence."""
    def __init__(self, api, guard, read_guard=None, before_effect=None, before_request=None, after_response=None):
        self._target, self._guard, self._read_guard = api, guard, read_guard or guard
        self._before_effect = before_effect or guard
        self._before_request = before_request
        self._after_response = after_response
    def __getattr__(self, name):
        call = getattr(self._target, name)
        def invoke(*args, **kwargs):
            method = kwargs.get('method', args[1] if name in ('api', 'fetch') and len(args) > 1 else 'GET')
            read = name in ('get', 'pages') or name in ('api', 'fetch') and method == 'GET'
            guard = self._read_guard if read else self._guard
            (guard if read else self._before_effect)()
            if not read and self._before_request is not None:
                self._before_request(name, args, kwargs)
            result = call(*args, **kwargs)
            if not read and self._after_response is not None:
                self._after_response(name, args, kwargs, result)
            try:
                guard()
            except BaseException:
                # A token minted before expiry is already a resource, even if the
                # post-call guard prevents returning it to installation_token.
                if name == 'post' and args and re.fullmatch('/app/installations/[1-9][0-9]*/access_tokens', args[0]):
                    bootstrap.revoke_token(result)
                raise
            return result
        return invoke


class Prepare:
    def __init__(self, provision): self.provision = provision

    def run(self, approve):
        authority_release.authorize('provision')
        require(isinstance(self.provision, Provision), 'native completed trial provision required')
        c = self.provision
        pair = c.completed()
        retained = copy.deepcopy(c.document)
        session = c.session
        origin_binding = session._check()
        origin = origin_binding['deployment']
        expected = tuple(origin_binding[k] for k in ('configuration_revision', 'deployment_digest', 'branch_head'))
        registry = session.registry
        ownership = copy.deepcopy((session.operation_id, session.sequence, session.owner, session.scope, session.software))
        active = []
        def local_guard():
            require(c.session is session and session.registry is registry and session.expected == expected and
                    (session.operation_id, session.sequence, session.owner, session.scope, session.software) == ownership and
                    c.preview == retained['value']['preview'] and c.document == retained and c.journal.read() == retained,
                    'original trial provisioning or configuration session changed')
            require(c.preview['created'] <= c.clock() < min(c.preview['expires'], origin['expires'],
                    origin_binding['fence']['pending']['execution_deadline']), 'original trial consent expired')
        def guard():
            local_guard()
            session._owned(origin_binding)
            registry.unchanged(origin_binding)
            local_guard()
        def before_effect():
            guard()
            if active:
                native = active[0]
                current = native._check()
                # _check ends with a blocking original readback. Recheck the
                # trial after it before the actual native effect, not just
                # before resolving its transport method.
                native.registry.unchanged(current)
            else:
                repo = c.api.get('/repos/' + pair['authority_repository'])
                require(repo.get('id') == pair['authority_repository_id'] and repo.get('private') is True and
                        repo.get('owner', {}).get('id') == pair['identities']['owner_id'], 'trial authority changed')
                require(c.api.get('/repos/' + pair['authority_repository'] + '/git/ref/heads/' +
                        repo['default_branch'])['object']['sha'] == pair['software_revision'], 'trial software changed')
            local_guard()
        # Full origin readbacks bracket native effects and each owning session
        # check. Its immutable registry reads need only local retention/expiry
        # checks; recursively authenticating the origin at every read is unbounded.
        def boundary(api): return _Boundary(api, guard, local_guard, before_effect)
        operator = operator_setup.Operator(boundary(c.api), boundary(c.gh), c.root / 'trial-operator',
            c.authority_files, c.clock, store_factory=c.store)
        operator.journal = c.store(operator.root)
        operator.document = operator.journal.read()
        connected = copy.deepcopy(retained['value']['connected'])
        def select(*args):
            guard()
            return deployment(c, pair, origin)
        def consent(value):
            guard()
            result = approve(copy.deepcopy(value))
            guard()
            return result
        result = operator_setup._configure_connected(operator, connected, origin['resources']['bundle_sha'],
            consent, select, before_call=guard, guard_api=boundary, retain_binding=True,
            on_session=lambda native: active.append(native))
        require(result['state'] == 'qualification' and result['enforcement_active'] is False and
                result['hosted_qualified'] is False and
                result['model_resources']['model_session'] != origin['resources'].get('model_session'),
                'trial must remain unqualified with distinct model authorization')
        require(c.completed() == pair, 'completed trial pair changed during configuration')
        return copy.deepcopy(result)
