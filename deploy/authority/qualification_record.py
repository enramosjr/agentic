"""Authenticated v2 qualification receipts; no synthetic qualification producer.

The pinned hosted producer must establish each recorded success/intended denial,
including actual mutations/failed obligations, prior authoritative successes and
changed stale coordinates. This reader authenticates a summary; it does not replay
those precursor probes. No producer currently emits these receipts.
A local document, model catalog, template or configuration presence cannot do so.
"""
from app_proofs import identity_record
from authority_protocol import configuration_digest, fingerprint, validate_deployment
from codex_harness import profile
from provenance import authenticated_document
from trusted_ci_policy import digest, object_fields, positive, require, sha
from trusted_ci_qualification import CASES as HOST_CASES

BROKER_DENIALS = {'expired-proof': 'proof_expired', 'revoked-qualification': 'qualification_revoked',
                 'authority-outage': 'readback_unavailable', 'context-transition': 'configuration_changed'}
CASES = (*(name for name in HOST_CASES if name != 'positive'),
         'human-update', 'coding-update', *BROKER_DENIALS, 'positive')
FIELDS = ('schema_version kind configuration_digest qualified_generation adapter account fixture_repository_id '
          'controls_digest execution model_probe cases issued completed expires').split()
CASE_FIELDS = ('name pr head base merge tree before after actor_id request_sent http_status denial_category '
               'denied_obligation broker_refusal merge_commit merge_parents merge_tree evidence_digest').split()


def validate(value, binding, identities, proof, controls_digest, now):
    d = validate_deployment(binding['deployment'])
    identity_record(d, identities)
    resources = profile(d)
    object_fields(value, FIELDS, 'hosted qualification receipt')
    require(type(value['schema_version']) is int and value['schema_version'] == 2 and
            value['kind'] == 'hosted-qualification' and d['state'] == 'active' and
            value['configuration_digest'] == configuration_digest(d) and positive(value['qualified_generation']) and
            value['qualified_generation'] + 1 == d['generation'] and digest(value) == d['qualification'] and
            binding['deployment_digest'] == digest(d), 'current qualified configuration or generation differs')
    p = d['policy']
    require(value['adapter'] == d['adapter'] and value['account'] == d['account'] and
            positive(value['fixture_repository_id']) and value['fixture_repository_id'] not in
            (p['repository_id'], p['authority_repository_id']) and fingerprint(controls_digest) and
            value['controls_digest'] == controls_digest, 'qualification target or control binding differs')
    execution = value['execution']
    object_fields(execution, ('run_id', 'attempt', 'job_id', 'resource', 'runtime_digest'), 'qualification execution')
    resource = (resources.get('actions_resource') if d['adapter'] == 'github-actions' else resources.get('compute_scope'))
    require(all(positive(execution[k]) and execution[k] == proof[k] for k in ('run_id', 'attempt', 'job_id')) and
            isinstance(resource, str) and resource and execution['resource'] == resource and
            fingerprint(resources.get('bundle_sha')) and execution['runtime_digest'] == resources['bundle_sha'] and
            proof['role'] == 'qualification' and proof['key'] is None, 'qualified execution identity differs')
    require(all(positive(value[k]) for k in ('issued', 'completed', 'expires')) and type(now) is int and
            proof['job_started'] <= value['issued'] <= value['completed'] <= proof['artifact_created'] <=
            proof['job_completed'] <= now < value['expires'] <= d['expires'], 'qualification interval or expiry differs')
    model = value['model_probe']
    object_fields(model, ('profile', 'model_id', 'codex_sha', 'coding_image', 'thread_id', 'turn_id',
                          'response_digest'), 'qualified model execution')
    require(model['profile'] == resources['model_auth'] and model['model_id'] == resources['model_id'] and
            model['codex_sha'] == resources['codex_sha'] and model['coding_image'] == resources['coding_image'] and
            fingerprint(model['response_digest']) and all(isinstance(model[k], str) and 0 < len(model[k]) <= 200 and
            not any(ord(c) < 32 for c in model[k]) for k in ('thread_id', 'turn_id')),
            'completed qualified model execution differs')
    cases = value['cases']
    require(isinstance(cases, list) and len(cases) == len(CASES), 'complete ordered hosted case inventory required')
    for case in cases:
        object_fields(case, CASE_FIELDS, 'hosted qualification case')
    require([c['name'] for c in cases] == list(CASES), 'complete ordered hosted case inventory required')
    require(len({c['pr'] for c in cases}) == len(cases) and len({c['head'] for c in cases}) == len(cases),
            'qualification cases require distinct PRs and heads')
    for case in cases:
        name = case['name']
        require(positive(case['pr']) and all(sha(case[k]) for k in ('head', 'base', 'merge', 'tree', 'before', 'after')) and
                case['before'] == case['base'] and fingerprint(case['evidence_digest']) and
                type(case['request_sent']) is bool, 'qualification fixture or evidence differs')
        if name == 'positive':
            require(case['actor_id'] == identities['apps']['merge']['actor_id'] and case['request_sent'] is True and
                    type(case['http_status']) is int and case['http_status'] == 200 and
                    case['denial_category'] is None and case['denied_obligation'] is None and
                    case['broker_refusal'] is None and sha(case['merge_commit']) and
                    case['after'] == case['merge_commit'] != case['before'] and
                    case['merge_parents'] == [case['base'], case['head']] and case['merge_tree'] == case['tree'],
                    'positive reviewed broker merge was not established')
            continue
        require(case['after'] == case['before'] and case['merge_commit'] is None and
                case['merge_parents'] == [] and case['merge_tree'] is None,
                'negative qualification changed the protected target')
        if name in BROKER_DENIALS:
            require(case['actor_id'] == identities['apps']['merge']['actor_id'] and case['request_sent'] is False and
                    case['http_status'] is None and case['denial_category'] is None and
                    case['denied_obligation'] is None and case['broker_refusal'] == BROKER_DENIALS[name],
                    'broker did not refuse the intended prerequisite before dispatch')
            continue
        category = ('protected_update' if name in ('direct-push', 'human-update', 'coding-update') else
                    'required_review' if name == 'missing-approval' else 'required_check')
        actor = (identities['apps']['coding']['actor_id'] if name in ('direct-push', 'coding-update') else
                 identities['apps']['merge']['actor_id'])
        require((case['actor_id'] in p['reviewers'] if name == 'human-update' else case['actor_id'] == actor) and
                case['request_sent'] is True and type(case['http_status']) is int and
                case['http_status'] in (403, 405, 422) and case['denial_category'] == category and
                case['denied_obligation'] == (p['check_name'] if category == 'required_check' else None) and
                case['broker_refusal'] is None, 'host did not establish the intended authorization denial')
    return value


def read(authority, binding, identities, locator, controls_digest, now):
    proof = authenticated_document(authority, binding['deployment'], locator, 'qualification', None, now)
    value = validate(proof['document'], binding, identities, proof, controls_digest, now)
    return {'document': value, 'provenance': {k: v for k, v in proof.items() if k != 'document'},
            'qualification_digest': digest(value), 'expires': value['expires']}
