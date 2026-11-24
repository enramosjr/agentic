"""Read authenticated protected-task receipts; never promote submission alone.

Only the pinned parent producer can establish these execution facts. Validation
does not create that producer, qualify its isolation, or run a model/harness.
"""
import re
from urllib.parse import quote

from app_proofs import identity_record
from authority_protocol import fingerprint, validate_deployment
from codex_harness import profile
from provenance import authenticated_document
from trusted_ci_policy import digest, object_fields, positive, require, sha, validate_snapshot

CREDENTIAL_PROBES = ('github_credentials', 'authority_checkout', 'admin_credentials', 'issuer_credentials',
                     'merge_credentials', 'cloud_credentials', 'metadata_route', 'host_home', 'engine_socket')
FIELDS = ('schema_version kind task_id configuration_revision deployment_digest source_base coding_installation_id '
          'submitted execution harness protocol isolation relay cleanup_complete issued completed expires').split()
SUBMISSION_FIELDS = ('schema_version task_id branch head tree pr export_digest configuration_revision '
                     'deployment_digest app_id bot_id run_id attempt admission_established').split()
ISOLATION_FIELDS = ('uid root_read_only cap_eff no_new_privs seccomp interfaces memory_max pids_max cpu_quota '
                    'cpu_period work_filesystem work_capacity writable_mounts host_mounts credential_probes').split()


def validate_isolation(facts, d):
    object_fields(facts, ISOLATION_FIELDS, 'effective task isolation')
    numeric = ('uid', 'no_new_privs', 'seccomp', 'memory_max', 'pids_max', 'cpu_quota', 'cpu_period', 'work_capacity')
    require(all(type(facts[k]) is int for k in numeric), 'integer task isolation facts required')
    limits = d['policy']['limits']
    require(facts['uid'] == 65534 and facts['root_read_only'] is True and facts['cap_eff'] == '0' * 16 and
            facts['no_new_privs'] == 1 and facts['seccomp'] == 2 and facts['interfaces'] == ['lo'] and
            facts['memory_max'] == limits['memory_mb'] * 1024 * 1024 and facts['pids_max'] == limits['processes'] and
            0 < facts['cpu_quota'] <= facts['cpu_period'] <= 1000000 and
            facts['work_filesystem'] in ('ext2/ext3', 'ext4', 'xfs', 'btrfs') and
            0 < facts['work_capacity'] <= limits['disk_mb'] * 1024 * 1024 and
            facts['writable_mounts'] == ['/work', '/tmp', '/home/agentic'] and
            facts['host_mounts'] == ['/run/agentic-model'], 'effective task isolation differs')
    object_fields(facts['credential_probes'], CREDENTIAL_PROBES, 'task credential probes')
    require(all(v == 'unavailable' for v in facts['credential_probes'].values()), 'task credential path is available')
    return facts


def validate(value, binding, identities, snapshot, proof, now):
    """Document semantics after authenticated_document; not a public attestation API."""
    d = validate_deployment(binding['deployment'])
    identity_record(d, identities)
    s = validate_snapshot(snapshot, d['policy'])
    resources = profile(d)
    object_fields(value, FIELDS, 'protected task receipt')
    require(type(value['schema_version']) is int and value['schema_version'] == 2 and
            value['kind'] == 'protected-task' and isinstance(value['task_id'], str) and
            re.fullmatch('[0-9a-f]{32}', value['task_id']) and
            value['task_id'] == proof['key'] and proof['role'] == 'task', 'protected task identity differs')
    require(d['state'] == 'active' and sha(binding['configuration_revision']) and
            value['configuration_revision'] == binding['configuration_revision'] and
            value['deployment_digest'] == binding['deployment_digest'] == digest(d) and
            value['coding_installation_id'] == identities['apps']['coding']['installation_id'] and
            sha(value['source_base']), 'protected task configuration differs')
    object_fields(value['execution'], ('run_id', 'attempt', 'job_id'), 'task execution')
    require(all(positive(v) for v in value['execution'].values()) and
            all(value['execution'][key] == proof[key] for key in ('run_id', 'attempt', 'job_id')),
            'task parent execution differs')
    require(all(positive(value[k]) for k in ('issued', 'completed', 'expires')) and type(now) is int and
            proof['job_started'] <= value['issued'] <= value['completed'] <= proof['artifact_created'] <=
            proof['job_completed'] <= now < value['expires'] <= d['expires'] and
            value['cleanup_complete'] is True, 'task expiry, interval or cleanup differs')
    submitted = value['submitted']
    object_fields(submitted, SUBMISSION_FIELDS, 'task submission')
    require(type(submitted['schema_version']) is int and submitted['schema_version'] == 2 and
            submitted['task_id'] == value['task_id'] and submitted['branch'] == 'agentic/task-' + value['task_id'] and
            submitted['head'] == s['head'] and submitted['pr'] == s['pr'] and sha(submitted['tree']) and
            fingerprint(submitted['export_digest']) and submitted['configuration_revision'] == value['configuration_revision'] and
            submitted['deployment_digest'] == value['deployment_digest'] and submitted['app_id'] == d['apps']['coding'] and
            submitted['bot_id'] == identities['apps']['coding']['actor_id'] and
            submitted['run_id'] == proof['run_id'] and submitted['attempt'] == proof['attempt'] and
            submitted['admission_established'] is False, 'task submission binding differs')
    object_fields(value['harness'], ('image', 'sha256', 'version', 'auth_profile'), 'task harness')
    require(value['harness'] == dict(image=resources['coding_image'], sha256=resources['codex_sha'],
            version=resources['codex_version'], auth_profile=resources['model_auth']), 'task harness pin differs')
    protocol = value['protocol']
    object_fields(protocol, ('kind', 'thread_id', 'turn_id', 'model_id', 'model_execution_qualified'), 'task harness result')
    require(protocol['kind'] == 'codex-protocol-result' and protocol['model_id'] == resources['model_id'] and
            protocol['model_execution_qualified'] is False and all(isinstance(protocol[k], str) and
            0 < len(protocol[k]) <= 200 and not any(ord(c) < 32 for c in protocol[k])
            for k in ('thread_id', 'turn_id')), 'completed pinned task protocol required')
    validate_isolation(value['isolation'], d)
    relay = value['relay']
    object_fields(relay, ('requests', 'completed', 'response_digests'), 'task inference relay result')
    require(positive(relay['requests']) and positive(relay['completed']) and
            relay['completed'] <= relay['requests'] <= 10000 and isinstance(relay['response_digests'], list) and
            len(relay['response_digests']) == relay['completed'] and
            all(fingerprint(v) for v in relay['response_digests']), 'completed task inference evidence required')
    return value


def read(source, authority, binding, identities, snapshot, locator, task_id, now):
    proof = authenticated_document(authority, binding['deployment'], locator, 'task', task_id, now)
    value = validate(proof['document'], binding, identities, snapshot, proof, now)
    d, submitted = binding['deployment'], value['submitted']
    p, root = d['policy'], '/repos/' + d['policy']['repository']
    pr = source.get(root + '/pulls/' + str(submitted['pr']))
    require(pr['state'] == 'open' and pr.get('draft') is False and pr.get('merged') is False and
            pr['number'] == snapshot['pr'] and pr['head']['sha'] == submitted['head'] and
            pr['head']['ref'] == submitted['branch'] and pr['head']['repo']['id'] == p['repository_id'] and
            pr['base']['ref'] == p['target'] and pr['base']['repo']['id'] == p['repository_id'] and
            pr['user']['id'] == submitted['bot_id'] and pr['user'].get('type') == 'Bot', 'current task PR differs')
    branch = source.get(root + '/git/ref/heads/' + quote(submitted['branch'], safe=''))
    require(branch['object']['sha'] == submitted['head'], 'submitted task branch moved')
    commit = source.get(root + '/git/commits/' + submitted['head'])
    require(commit.get('sha') == submitted['head'] and commit['tree']['sha'] == submitted['tree'] and
            [parent['sha'] for parent in commit['parents']] == [value['source_base']], 'submitted task commit differs')
    return {'document': value, 'provenance': {k: v for k, v in proof.items() if k != 'document'},
            'task_digest': digest(value), 'head': submitted['head'], 'expires': value['expires'],
            'admission_established': True}
