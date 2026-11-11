"""V2 pinned-parent evidence. API-backed proof is separate from document validity."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
import io
from pathlib import Path
import re
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '.ai/scripts'))
from authority_protocol import fingerprint, validate_deployment, validate_execution
from trusted_ci_deployment import timestamp
from trusted_ci_github import authority_run
from trusted_ci_policy import Refusal, loads, object_fields, positive, require, sha


def execution_job(api, d, run, attempt, name, completed=False):
    validate_deployment(d)
    require(positive(run) and positive(attempt) and isinstance(name, str) and len(name) <= 100,
            'invalid authority execution coordinates')
    p = d['policy']
    authority_run(api, p, run, attempt)
    jobs = api.pages('/repos/' + p['authority_repository'] + '/actions/runs/' + str(run) +
                     '/attempts/' + str(attempt) + '/jobs', 'jobs')
    matches = [j for j in jobs if j['name'] == name]
    require(len(matches) == 1, 'missing or ambiguous pinned authority job')
    job = matches[0]
    require(positive(job['id']) and job['run_id'] == run and job['head_sha'] == p['workflow_sha'],
            'authority job provenance differs')
    require((job['status'] == 'completed' and job['conclusion'] == 'success') if completed else
            (job['status'] == 'in_progress' and job['conclusion'] is None), 'authority job state is not admissible')
    return job


def admit_job(api, d, environment, name, now):
    validate_deployment(d)
    credential = re.fullmatch(r'credential proof \((admin|reader|issuer|coding|merge|model_vault|model_delivery)\)', name)
    task = re.fullmatch(r'task \([0-9a-f]{32}\)', name)
    task_controls = re.fullmatch(r'task controls \([0-9a-f]{32}\)', name)
    preparation = name == 'prepare task'
    require(type(now) is int and now < d['expires'] and
            (d['state'] == 'setup' if credential else d['state'] == 'active' if task or task_controls or preparation else
             d['state'] in ('qualification', 'active')),
            'current configured authority deployment required')
    p = d['policy']
    require(environment.get('GITHUB_REPOSITORY_ID') == str(p['authority_repository_id']) and
            environment.get('GITHUB_SHA') == p['workflow_sha'], 'not the pinned authority environment')
    key = {'discover': 'discover', 'prepare': 'prepare', 'hosted qualification': 'qualification',
           'model authorization': 'model_auth', 'prepare task': 'prepare_task', 'trial handoff': 'trial_handoff',
           'trial preparation':'trial_prepare', 'trial case handoff':'trial_case_handoff', 'trial case ready':'trial_case_ready',
           'trial host denial':'trial_host_denial'}.get(name)
    matrix = re.fullmatch(r'(verify|controls|publish|broker|publication controls) \([1-9][0-9]{0,19}\)', name)
    proof = re.fullmatch(r'(proof|final proof) \((admin|reader|issuer|coding|merge)\)', name)
    if matrix:
        key = matrix.group(1).replace(' ', '_')
    elif proof:
        key = proof.group(2) + ('_final_proof' if proof.group(1) == 'final proof' else '_proof')
        if d['state'] == 'qualification' and proof.group(1) == 'proof' and environment.get('GITHUB_JOB') == 'trial_' + key:
            key = 'trial_' + key
    elif credential:
        key = credential.group(1) + '_credential_proof'
    elif task:
        key = 'task'
    elif task_controls:
        key = 'task_controls'
    if name == 'model authorization' and d['state'] == 'qualification' and environment.get('GITHUB_JOB') == 'trial_model_auth':
        key = 'trial_model_auth'
    require(key is not None and environment.get('GITHUB_JOB') == key,
            'current authority job key differs from expected role')
    values = [environment.get(key, '') for key in ('GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT')]
    require(all(isinstance(v, str) and re.fullmatch('[1-9][0-9]{0,19}', v) for v in values),
            'numeric authority run and attempt required')
    return execution_job(api, d, int(values[0]), int(values[1]), name)


def artifact_document(api, d, run, attempt, pr, purpose):
    require(positive(pr) and purpose in ('evidence', 'controls'), 'unsupported authority artifact purpose')
    job = execution_job(api, d, run, attempt, ('verify' if purpose == 'evidence' else 'controls') +
                        ' (' + str(pr) + ')', completed=True)
    p = d['policy']
    root = '/repos/' + p['authority_repository']
    name = purpose + '-' + str(pr) + '-' + str(attempt)
    matches = [a for a in api.pages(root + '/actions/runs/' + str(run) + '/artifacts', 'artifacts') if a['name'] == name]
    require(len(matches) == 1, 'missing or ambiguous pinned authority artifact')
    artifact = matches[0]
    execution = artifact['workflow_run']
    require(positive(artifact['id']) and artifact.get('expired') is False and
            execution['id'] == run and execution['repository_id'] == p['authority_repository_id'] and
            execution['head_repository_id'] == p['authority_repository_id'] and
            execution['head_sha'] == p['workflow_sha'], 'artifact execution differs')
    require(timestamp(job['started_at']) <= timestamp(artifact['created_at']) <= timestamp(job['completed_at']),
            'artifact was not produced during the pinned job interval')
    raw = api.fetch(root + '/actions/artifacts/' + str(artifact['id']) + '/zip', binary=True, limit=2 * 1024 * 1024)
    require(isinstance(raw, bytes) and 0 < len(raw) <= 2 * 1024 * 1024 and
            artifact.get('digest') == 'sha256:' + hashlib.sha256(raw).hexdigest(), 'artifact digest differs')
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries = archive.infolist()
            require(len(entries) == 1, 'single authority document required')
            item = entries[0]
            require(item.filename == purpose + '.json' and not item.is_dir() and not item.flag_bits & 1 and
                    0 <= item.file_size <= 1024 * 1024 and
                    (item.external_attr >> 16 & 0o170000) in (0, 0o100000) and
                    item.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED), 'unsafe authority document archive')
            document = loads(archive.read(item))
    except (zipfile.BadZipFile, OSError, RuntimeError):
        raise Refusal('invalid authority artifact archive') from None
    return {'document': document, 'job_id': job['id'], 'artifact_id': artifact['id'],
            'artifact_digest': artifact['digest'], 'run_id': run, 'attempt': attempt}


def authenticated_document(api, d, locator, role, key, now):
    """Read a closed producer role at an exact historical successful attempt.

    Role/key are independently selected by the caller. The returned document is
    authenticated transport data, not a substitute for its domain validator.
    Unlike broker dispatch receipts, every role here requires a successful job.
    """
    require(role not in ('task-ready', 'trial-task-ready'), 'live readiness is not closed producer evidence')
    return _authenticated_document(api, d, locator, role, key, now)


def live_task_readiness(api, d, locator, key, now):
    """Exact live task artifact only; cannot authenticate admission or outcomes."""
    return _authenticated_document(api, d, locator, 'task-ready', key, now, live=True)


def live_trial_readiness(api, d, locator, key, now):
    """Qualification-parent cleanup readiness; never production task admission."""
    return _authenticated_document(api, d, locator, 'trial-task-ready', key, now, live=True)


def _authenticated_document(api, d, locator, role, key, now, live=False):
    validate_deployment(d)
    object_fields(locator, ('run_id', 'attempt', 'job_id', 'artifact_id'), 'authority artifact locator')
    require(all(positive(v) for v in locator.values()) and type(now) is int and 0 < now < d['expires'],
            'current authority artifact coordinates required')
    require(role in ('evidence', 'controls', 'publication-controls', 'proof', 'final-proof', 'task', 'task-ready', 'task-controls',
                    'model-lease', 'qualification', 'credential-proof', 'trial-task', 'trial-task-ready',
            'trial-task-controls', 'trial-handoff', 'trial-case-handoff', 'trial-case-certificate', 'trial-case-ready', 'trial-host-intent', 'trial-host-denial', 'trial-case-terminal', 'trial-broker-intent', 'trial-broker-denial', 'trial-publication-intent', 'trial-publication-denial', 'trial-publication-observation') and live == (role in ('task-ready', 'trial-task-ready')),
            'unknown authority producer role')
    if role.startswith('trial-'):
        require(d['state'] == 'qualification' and d['qualification'] is None and
                (positive(key) if role in ('trial-broker-intent','trial-broker-denial','trial-publication-intent','trial-publication-denial','trial-publication-observation') else
                 isinstance(key, str) and re.fullmatch('[0-9a-f]{32}', key)), 'unqualified trial producer required')
    if role in ('evidence', 'controls', 'publication-controls'):
        require(positive(key), 'numeric candidate producer required')
        job_name = ('verify' if role == 'evidence' else role.replace('-', ' ')) + ' (' + str(key) + ')'
        prefix = role + '-' + str(key)
    elif role in ('proof', 'final-proof'):
        require(key in ('admin', 'reader', 'issuer', 'coding', 'merge'), 'unknown App proof producer')
        job_name = ('final proof' if role == 'final-proof' else 'proof') + ' (' + key + ')'
        prefix = role + '-' + key
    elif role in ('task', 'task-ready', 'task-controls', 'model-lease'):
        require(isinstance(key, str) and re.fullmatch('[0-9a-f]{32}', key), 'fixed task identity required')
        job_name = ('task controls (' + key + ')' if role == 'task-controls' else
                    'model authorization' if role == 'model-lease' else 'task (' + key + ')')
        prefix = role + '-' + key
    elif role in ('trial-task', 'trial-task-ready', 'trial-task-controls'):
        job_name = 'trial task controls (' + key + ')' if role == 'trial-task-controls' else 'hosted qualification'
        prefix = role + '-' + key
    elif role == 'trial-handoff':
        job_name, prefix = 'trial handoff', 'trial-handoff-' + key
    elif role in ('trial-case-handoff','trial-case-certificate'):
        job_name, prefix = 'trial case handoff', role+'-' + key
    elif role == 'trial-case-ready':
        job_name, prefix = 'trial case ready', 'trial-case-ready-' + key
    elif role in ('trial-host-intent','trial-host-denial'):
        job_name, prefix = 'trial host denial', role + '-' + key
    elif role in ('trial-broker-intent','trial-broker-denial'):
        job_name, prefix = 'broker (' + str(key) + ')', role + '-' + str(key)
    elif role in ('trial-publication-intent','trial-publication-denial','trial-publication-observation'):
        job_name, prefix = 'publish (' + str(key) + ')', role + '-' + str(key)
    elif role == 'trial-case-terminal':
        job_name, prefix = 'finalize', role + '-' + key
    elif role == 'credential-proof':
        require(key in ('admin', 'reader', 'issuer', 'coding', 'merge', 'model_vault', 'model_delivery'),
                'unknown credential producer')
        job_name, prefix = 'credential proof (' + key + ')', 'credential-proof-' + key
    else:
        require(key is None, 'qualification producer has no candidate selector')
        job_name, prefix = 'hosted qualification', 'qualification'
    p = d['policy']
    root = '/repos/' + p['authority_repository']
    run_id, attempt = locator['run_id'], locator['attempt']
    run_root = root + '/actions/runs/' + str(run_id)
    run = api.get(run_root + '/attempts/' + str(attempt))
    require(run['id'] == run_id and run['repository']['id'] == p['authority_repository_id'] and
            run['head_sha'] == p['workflow_sha'] and run['run_attempt'] == attempt and
            run['event'] in ('schedule', 'workflow_dispatch') and positive(run['workflow_id']),
            'historical authority execution differs')
    path = run['path'].split('@', 1)
    require(path[0] == p['workflow'] and (len(path) == 1 or path[1] in
            (run.get('head_branch'), 'refs/heads/' + str(run.get('head_branch')), p['workflow_sha'])),
            'historical authority workflow path differs')
    workflow = api.get(root + '/actions/workflows/' + str(run['workflow_id']))
    require(workflow['id'] == run['workflow_id'] and workflow['path'] == p['workflow'],
            'historical authority workflow identity differs')
    jobs = [j for j in api.pages(run_root + '/attempts/' + str(attempt) + '/jobs', 'jobs') if j['name'] == job_name]
    require(len(jobs) == 1, 'missing or ambiguous closed producer job')
    job = jobs[0]
    require(job['id'] == locator['job_id'] and job['run_id'] == run_id and job['head_sha'] == p['workflow_sha'] and
            ((job['status'] == 'in_progress' and job['conclusion'] is None) if live else
             (job['status'] == 'completed' and job['conclusion'] == 'success')), 'producer job state differs')
    started = timestamp(job['started_at'])
    completed = datetime.fromtimestamp(now, timezone.utc) if live else timestamp(job['completed_at'])
    require(0 < int(started.timestamp()) <= int(completed.timestamp()) <= now,
            'closed producer job interval differs')
    name = prefix + '-' + str(attempt)
    artifacts = [a for a in api.pages(run_root + '/artifacts', 'artifacts') if a['name'] == name]
    require(len(artifacts) == 1, 'missing or ambiguous closed producer artifact')
    artifact = artifacts[0]
    execution = artifact['workflow_run']
    require(artifact['id'] == locator['artifact_id'] and artifact.get('expired') is False and
            execution['id'] == run_id and execution['repository_id'] == p['authority_repository_id'] and
            execution['head_repository_id'] == p['authority_repository_id'] and execution['head_sha'] == p['workflow_sha'],
            'closed producer artifact identity differs')
    require(started <= timestamp(artifact['created_at']) <= completed, 'closed producer artifact interval differs')
    raw = api.fetch(root + '/actions/artifacts/' + str(artifact['id']) + '/zip', binary=True, limit=2 * 1024 * 1024)
    require(isinstance(raw, bytes) and 0 < len(raw) <= 2 * 1024 * 1024 and
            artifact.get('digest') == 'sha256:' + hashlib.sha256(raw).hexdigest(), 'closed producer archive digest differs')
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries = archive.infolist()
            require(len(entries) == 1, 'single closed producer document required')
            item = entries[0]
            require(item.filename == role + '.json' and not item.is_dir() and not item.flag_bits & 1 and
                    0 < item.file_size <= 1024 * 1024 and
                    (item.external_attr >> 16 & 0o170000) in (0, 0o100000) and
                    item.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED), 'unsafe closed producer archive')
            document = loads(archive.read(item))
    except (zipfile.BadZipFile, OSError, RuntimeError):
        raise Refusal('invalid closed producer archive') from None
    return {'document': document, 'job_id': job['id'], 'artifact_id': artifact['id'],
            'artifact_digest': artifact['digest'], 'run_id': run_id, 'attempt': attempt,
            'role': role, 'key': key, 'job_started': int(started.timestamp()),
            'job_completed': int(completed.timestamp()),
            'artifact_created': int(timestamp(artifact['created_at']).timestamp())}


def validate_evidence(value, d, current, registry_revision, job_id, now):
    object_fields(value, ('schema_version', 'kind', 'registry_revision', 'result'), 'authority evidence')
    require(type(value['schema_version']) is int and value['schema_version'] == 2 and
            sha(registry_revision) and value['registry_revision'] == registry_revision and positive(job_id),
            'authority evidence registry binding differs')
    cloud = d['adapter'] in ('aws', 'azure')
    require(value['kind'] == ('cloud-parent' if cloud else 'actions'), 'wrong authority evidence kind')
    result = value['result']
    fields = ['schema_version', 'report', 'cleanup_complete', 'enforcement_active']
    if cloud:
        fields.append('lease_digest')
    object_fields(result, fields, 'authority execution result')
    require(type(result['schema_version']) is int and result['schema_version'] == 2 and
            result['cleanup_complete'] is True and result['enforcement_active'] is False,
            'authority cleanup did not complete')
    require(not cloud or fingerprint(result['lease_digest']), 'cloud parent lease digest missing')
    report = validate_execution(result['report'], d, current, now)
    resource = d['resources'].get('compute_scope') if cloud else (
        'github-actions:' + d['policy']['authority_repository'] + ':' + d['policy']['workflow'])
    require(cloud or d['resources'].get('actions_resource') == resource, 'Actions resource inventory differs')
    require(report['execution']['job_id'] == job_id and report['execution']['resource'] == resource,
            'execution report does not bind the authenticated parent job')
    return report
