"""Candidate-free read-only broker collection. No credential loading or merge API.

Preload is provisional: current administrative controls have not been observed.
Only finish can return a gate; it validates the completed warm-broker rendezvous,
all required evidence and current refs. Actual workflow/producer qualification is
separate and remains required. Nothing here changes release holds.
"""
import copy
from urllib.parse import quote

from authority_github import Readers, current_snapshot
from authority_protocol import validate_deployment
import app_proofs
import broker_proofs
from broker_refusal import BrokerRefusal, same
import checks
import control_rendezvous
from merge_receipts import ActionsReceipts
import merge_window
from provenance import authenticated_document, validate_evidence
import qualification_record
import task_admission
from trusted_ci_github import HostRefusal, independent_approval
from trusted_ci_policy import digest, object_fields, positive, require, sha


def _same(binding, original):
    same(binding, original, 'broker configuration or operation changed')


def preload(registry, source, authority, identities, job_id, locators, clock):
    binding = copy.deepcopy(registry.binding())
    d = validate_deployment(binding['deployment'])
    app_proofs.identity_record(d, identities)
    object_fields(locators, ('evidence', 'proofs', 'task', 'qualification'), 'broker evidence locators')
    op = binding['fence']['pending']
    require(op is not None and op['kind'] == 'merge' and d['state'] == 'active', 'active pending merge required')
    ActionsReceipts(authority, registry.binding, job_id, clock).current_job()
    api = Readers(source, authority, d)
    s = current_snapshot(api, d, op['pr'], op['run_id'], op['attempt'])
    broker_proofs.current_operation(binding, s)
    evidence_locator = locators['evidence']
    require(isinstance(evidence_locator, dict) and evidence_locator.get('run_id') == op['run_id'] and
            evidence_locator.get('attempt') == op['attempt'],
            'verification belongs to another broker attempt')
    evidence = authenticated_document(authority, d, evidence_locator, 'evidence', s['pr'], clock())
    validate_evidence(evidence['document'], d, s, binding['configuration_revision'], evidence['job_id'], clock())
    proofs = broker_proofs.read(authority, binding, identities, s, locators['proofs'], clock())
    object_fields(locators['task'], ('task_id', 'locator'), 'protected task locator')
    task = task_admission.read(source, authority, binding, identities, s,
                               locators['task']['locator'], locators['task']['task_id'], clock())
    qualification = authenticated_document(authority, d, locators['qualification'], 'qualification', None, clock())
    # Authenticate and validate the pinned summary now. Its comparison against
    # CURRENT controls is deliberately deferred until after the rendezvous.
    value = qualification['document']
    require(isinstance(value, dict) and 'controls_digest' in value, 'qualification summary required')
    qualification_record.validate(value, binding, identities, qualification, value['controls_digest'], clock())
    _same(registry.binding(), binding)
    return {'schema_version': 2, 'binding': binding, 'snapshot': s, 'job_id': job_id,
            'evidence': evidence, 'proofs': proofs, 'task': task, 'qualification': qualification}


def _artifact_readback(authority, d, references):
    """Recheck presence/digest/expiry; never treat deleted cached reports as current."""
    root = '/repos/' + d['policy']['authority_repository']
    inventories, observed = {}, []
    for ref in references:
        run_id = ref['run_id']
        if run_id not in inventories:
            path = root + '/actions/runs/' + str(run_id) + '/artifacts'
            try:
                inventories[run_id] = authority.pages(path, 'artifacts')
            except HostRefusal as error:
                if error.status not in (502, 503, 504):
                    raise
                raise BrokerRefusal('readback_unavailable', 'authority artifact readback unavailable',
                                    dict(path=path, status=error.status)) from error
        role, key = ref['role'], ref['key']
        prefix = role if role == 'qualification' else role + '-' + str(key)
        name = prefix + '-' + str(ref['attempt'])
        matches = [a for a in inventories[run_id] if a['name'] == name]
        if role == 'qualification' and not matches:
            raise BrokerRefusal('qualification_revoked', 'authenticated qualification artifact was removed',
                                {k: ref[k] for k in ('artifact_id', 'artifact_digest', 'run_id', 'attempt', 'job_id')})
        require(len(matches) == 1, 'required broker evidence is missing or ambiguous')
        a = matches[0]
        run = a['workflow_run']
        require(a['id'] == ref['artifact_id'] and a.get('expired') is False and a['digest'] == ref['artifact_digest'] and
                run['id'] == run_id and run['repository_id'] == d['policy']['authority_repository_id'] and
                run['head_repository_id'] == d['policy']['authority_repository_id'] and
                run['head_sha'] == d['policy']['workflow_sha'], 'required broker evidence was revoked or replaced')
        observed.append(dict(artifact_id=a['id'], name=name, digest=a['digest'], run_id=run_id))
    return digest(observed)


def _additional_checks(source, d, snapshot, required):
    own = (d['policy']['check_name'], d['policy']['app_id'])
    extra = [v for v in required if (v['context'], v['integration_id']) != own]
    if not extra:
        return []
    require(all(positive(v['integration_id']) for v in extra),
            'unsupported required check without an exact integration source')
    entries = source.pages('/repos/' + d['policy']['repository'] + '/commits/' + snapshot['merge'] +
                           '/check-runs?filter=all', 'check_runs')
    result = []
    for required_check in extra:
        matches = [v for v in entries if v.get('name') == required_check['context'] and
                   v.get('app', {}).get('id') == required_check['integration_id']]
        require(len(matches) == 1, 'missing or ambiguous additional required check')
        check = matches[0]
        require(positive(check['id']) and check.get('head_sha') == snapshot['merge'] and
                check.get('status') == 'completed' and check.get('conclusion') == 'success',
                'additional required check did not pass on the tested merge')
        result.append({'id': check['id'], **required_check})
    return result


def finish(registry, source, authority, identities, prepared, request, control_locator, final_proof_locators, clock):
    binding = registry.binding()
    _same(binding, prepared['binding'])
    d, expected = binding['deployment'], prepared['snapshot']
    op = broker_proofs.current_operation(binding, expected)
    ActionsReceipts(authority, registry.binding, prepared['job_id'], clock).current_job()
    control_rendezvous.validate_ready(request, binding, prepared['job_id'], clock())
    controls = control_rendezvous.read_response(authority, binding, request, control_locator, clock())
    qualification = prepared['qualification']
    qualification_record.validate(qualification['document'], binding, identities, qualification,
                                  controls['document']['result']['controls_digest'], clock())
    evidence, task = prepared['evidence'], prepared['task']
    proofs = broker_proofs.read_final(authority, binding, identities, expected, request, final_proof_locators, clock())
    validate_evidence(evidence['document'], d, expected, binding['configuration_revision'], evidence['job_id'], clock())
    task_proof = dict(task['provenance'], document=task['document'])
    task_admission.validate(task['document'], binding, identities, expected, task_proof, clock())
    api = Readers(source, authority, d)
    current = current_snapshot(api, d, op['pr'], op['run_id'], op['attempt'])
    require(current == expected, 'candidate changed before broker authorization')
    submitted = task['document']['submitted']
    branch = source.get('/repos/' + d['policy']['repository'] + '/git/ref/heads/' + quote(submitted['branch'], safe=''))
    require(branch['object']['sha'] == submitted['head'], 'task branch changed before authorization')
    coordinates = dict(configuration_revision=binding['configuration_revision'], operation=op,
        sequence=binding['fence']['sequence'], issuer_installation_id=identities['apps']['issuer']['installation_id'],
        evidence_job_id=evidence['job_id'], evidence_digest=digest(evidence['document']), task_digest=task['task_digest'])
    trusted_check = checks.current(source, d, current, coordinates, clock())
    root = '/repos/' + d['policy']['repository']
    pr = source.get(root + '/pulls/' + str(op['pr']))
    require(pr['head']['sha'] == current['head'] and pr['base']['sha'] == current['base'], 'reviewed PR changed')
    reviews = independent_approval(source, d['policy'], pr, human=True)
    additional = _additional_checks(source, d, current, controls['document']['result']['required_checks'])
    references = [evidence, qualification, task['provenance'],
                  *prepared['proofs']['provenance'].values(), *proofs['provenance'].values(), controls['provenance']]
    artifact_digest = _artifact_readback(authority, d, references)
    commit = source.get(root + '/git/commits/' + current['merge'])
    require(commit.get('sha') == current['merge'] and sha(commit['tree']['sha']) and
            [p['sha'] for p in commit['parents']] == [current['base'], current['head']],
            'tested merge tree or parents changed')
    require(current_snapshot(api, d, op['pr'], op['run_id'], op['attempt']) == current,
            'candidate moved during final authorization')
    _same(registry.binding(), binding)
    valid_until = dict(proofs['valid_until'], deployment=d['expires'], qualification=qualification['document']['expires'],
                       task=task['expires'])
    valid_until['admin'] = min(valid_until['admin'], controls['expires'])
    gate = dict(schema_version=2, operation_id=op['operation_id'], sequence=binding['fence']['sequence'],
        configuration_revision=binding['configuration_revision'], deployment_digest=binding['deployment_digest'],
        repository_id=current['repository_id'], authority_repository_id=current['authority_repository_id'],
        target=d['policy']['target'], pr=current['pr'], head=current['head'], base=current['base'], merge=current['merge'],
        tree=commit['tree']['sha'], workflow_sha=current['workflow_sha'], run_id=current['run_id'], attempt=current['run_attempt'],
        epoch=d['policy']['epoch'], check_name=d['policy']['check_name'], issued=request['issued'],
        expires=min(request['expires'], request['issued'] + 300, *valid_until.values()),
        readback_started=min(controls['readback_started'], *(v['issued'] for v in proofs['documents'].values())),
        readback_completed=max(controls['readback_completed'], *(v['completed'] for v in proofs['documents'].values())),
        valid_until=valid_until,
        evidence_digest=coordinates['evidence_digest'], task_digest=task['task_digest'],
        controls_digest=controls['controls_digest'], qualification_digest=d['qualification'],
        proofs_digest=digest(dict(capabilities=proofs['proofs_digest'], additional_checks=additional,
                                 artifact_readback=artifact_digest)), check_id=trusted_check['check_id'],
        review_ids=sorted(r['id'] for r in reviews))
    return merge_window.validate(gate, binding, clock())
