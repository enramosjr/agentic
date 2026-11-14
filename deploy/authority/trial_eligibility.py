"""Native local eligibility attestation; only six historical tree choices."""
import copy
from functools import lru_cache
import hashlib
from pathlib import Path
import time

from trusted_ci_policy import CHECKS,digest,object_fields,positive,require,sha,validate_snapshot

KIND='native-trial-eligibility'
SCOPE=[['new-head','prior'],['new-base','prior'],['policy-transition','prior'],
       ['human-update','fixture'],['revoked-qualification','fixture'],['context-transition','fixture']]


@lru_cache(maxsize=20000)
def _file_syntax(path,mode,blob,checksum):
    # Only bounded immutable syntax is reusable. Every native grant, reference,
    # approval, manifest digest, provenance and deadline is checked afresh below.
    from submission import path_parts
    path_parts(path)
    require(mode in ('100644','100755') and sha(blob) and len(checksum)==64 and
            all(c in '0123456789abcdef' for c in checksum), 'eligibility file or executable mode differs')


def end(record):
    return min(record['expires'],record['trial']['deployment']['expires'],
               record['origin']['binding']['fence']['pending']['execution_deadline'])


def select(original,record,worker,link,name,phase,clock,source=None,authority=None):
    require([name,phase] in SCOPE,'eligibility grants only six historical or fixture tree selections')
    authenticate(original,record,worker,link,clock,source,authority)
    return worker['submitted']['tree']


def authenticate(original,record,worker,link,clock,source=None,authority=None):
    """Read-only domain validation. A grant never produces ordinary evidence."""
    from trial_transition import read_native
    value=read_native(original,link,record)
    object_fields(value,('schema_version kind name task_id execution record_digest preview approval').split(),'native eligibility grant')
    p=value['preview']; object_fields(p,('kind inputs observation scope').split(),'native eligible-tree preview')
    i=p['inputs']; o=p['observation']
    object_fields(i,('record_digest worker worker_proof manifest seed source_pin snapshot binding runtime image controller_sha256 issued expires').split(),
                  'native eligibility inputs')
    object_fields(o,('kind snapshot runtime image controller_sha256 started completed elapsed_ms outcomes cleanup_complete').split(),
                  'native local critical observation')
    validate_snapshot(i['snapshot'],record['trial']['deployment']['policy'])
    proof=i['worker_proof']; location=worker['locator']
    object_fields(proof,('job_id artifact_id artifact_digest run_id attempt role key job_started job_completed artifact_created').split(),
                  'CLOSED eligibility worker provenance')
    require({k:proof[k] for k in ('run_id','attempt','job_id','artifact_id')}==location and proof['role']=='trial-task' and
            proof['key']==record['task_id'] and location['run_id']==worker['submitted']['run_id'] and location['attempt']==1 and
            all(positive(proof[k]) for k in ('job_id','artifact_id','run_id','attempt','job_started','job_completed','artifact_created')) and
            proof['job_started']<=proof['artifact_created']<=proof['job_completed']<=i['issued'] and
            isinstance(proof['artifact_digest'],str) and len(proof['artifact_digest'])==71 and proof['artifact_digest'].startswith('sha256:'),
            'eligibility CLOSED worker provenance differs')
    for files in (i['manifest'],i['seed']['manifest']):
        require(isinstance(files,dict) and '.github/CODEOWNERS' in files,'eligibility seed and export owner manifests required')
        for path,item in files.items():
            object_fields(item,('mode','sha','sha256'),'eligibility file manifest')
            require(all(type(v) is str for v in (path,item['mode'],item['sha'],item['sha256'])),
                    'eligibility file manifest requires immutable strings')
            _file_syntax(path,item['mode'],item['sha'],item['sha256'])
    require(i['manifest']['.github/CODEOWNERS']==i['seed']['manifest']['.github/CODEOWNERS'], 'eligibility export changed original owners')
    require('.ai/scripts/trusted_ci_controller.py' in i['manifest'] and
            i['manifest']['.ai/scripts/trusted_ci_controller.py']['sha256']==i['controller_sha256'],
            'eligibility controller is not the exact pinned export controller')
    require(type(value['schema_version']) is int and value['schema_version']==1 and value['kind']==KIND and value['name']=='eligibility' and
            value['task_id']==record['task_id'] and value['execution'] is None and value['record_digest']==i['record_digest']==digest(record) and
            p['kind']=='native-eligible-tree-preview' and p['scope']==SCOPE and value['approval']==digest(p) and
            i['worker']==worker and i['binding']==record['trial'] and i['expires']==end(record) and
            sha(i['source_pin']) and sha(worker['submitted']['tree']) and digest(i['manifest'])==worker['submitted']['export_digest'] and
            i['runtime'] in ('docker','podman') and i['image']==record['trial']['deployment']['policy']['image'] and
            i['seed']['revision']==record['pair']['fixture_revision'] and
            i['snapshot']['base']==record['pair']['fixture_revision'] and i['snapshot']['head']==worker['submitted']['head'] and
            i['snapshot']['pr']==worker['submitted']['pr'] and i['snapshot']['run_id']==worker['submitted']['run_id'] and
            i['snapshot']['run_attempt']==1 and record['trial']['deployment']['policy']['checks']==list(CHECKS),
            'eligibility substituted original trial, worker, seed, manifest or scope')
    require(o['kind']=='native-local-critical-observation' and o['snapshot']==i['snapshot'] and o['runtime']==i['runtime'] and
            o['image']==i['image'] and o['controller_sha256']==i['controller_sha256'] and
            isinstance(i['controller_sha256'],str) and len(i['controller_sha256'])==64 and
            all(c in '0123456789abcdef' for c in i['controller_sha256']) and
            all(positive(v) for v in (i['issued'],o['started'],o['completed'])) and
            i['issued']<=o['started']<=o['completed']<=clock()<i['expires'] and
            type(o['elapsed_ms']) is int and o['elapsed_ms']>=0 and
            abs((o['completed']-o['started'])*1000-o['elapsed_ms'])<=2000 and
            o['cleanup_complete'] is True and o['outcomes']==[dict(id=check,status='success') for check in CHECKS],
            'native eligibility did not establish actual complete critical execution in the original interval')
    if authority is not None:
        import provenance
        actual=provenance.authenticated_document(authority,record['trial']['deployment'],location,'trial-task',record['task_id'],clock())
        require({k:v for k,v in actual.items() if k!='document'}==proof,'eligibility CLOSED archive was removed or substituted')
    if source is not None:
        import submission
        root='/repos/'+record['trial']['deployment']['policy']['repository']
        commit=source.get(root+'/git/commits/'+record['pair']['fixture_revision'])
        seed=submission._read_tree(source,root,commit['tree']['sha'],lambda:require(clock()<end(record),'eligibility seed read expired'))
        require(submission.export_manifest(seed)==i['seed']['manifest'],'eligibility seed manifest differs from original Git provenance')
    return value


def produce(native,prompt,source,source_root,source_pin,runtime,approve):
    import authority_release
    authority_release.authorize('qualify-live')
    return _produce(native,prompt,source,source_root,source_pin,runtime,approve)


def _produce(native,prompt,source,source_root,source_pin,runtime,approve):
    """Fixed native producer; accepts neither an execution report nor a verifier."""
    from trial_handoff import Native
    from trial_setup import Provision
    from trial_runtime import pinned_kit,verify
    from trial_specimen import compose,manifest
    from trial_transition import _publish_native,read_native
    from registry import trial_reference
    from authority_github import Readers,current_snapshot
    import submission,trusted_ci_controller
    require(type(native) is Native and type(native.provision) is Provision,'actual original native eligibility owner required')
    c=native.provision
    completed=native._completion(prompt,source)
    record=completed['record']; worker=completed['result']; binding=record['trial']; d=binding['deployment']; p=d['policy']
    require(p['checks']==list(CHECKS),'strict eligibility requires all four unchanged critical obligations')
    journal=c.store(c.root/'trial-eligibility'); document=journal.read()
    require(c.store(c.root/'trial-candidates').read() is None,'eligibility must precede all sixteen reservations')
    kit=pinned_kit(source_root,source_pin)
    _,expected=compose(kit)
    root='/repos/'+p['repository']
    seed_commit=source.get(root+'/git/commits/'+record['pair']['fixture_revision'])
    seed=submission._read_tree(source,root,seed_commit['tree']['sha'],lambda:require(c.clock()<end(record),'eligibility seed read expired'))
    require('.github/CODEOWNERS' in seed,'original seed CODEOWNERS required')
    expected['.github/CODEOWNERS']=copy.deepcopy(seed['.github/CODEOWNERS'])
    require(manifest(completed['files'])==manifest(expected),'CLOSED worker is not the approved exact KIT specimen')
    controller_hash=hashlib.sha256(Path(trusted_ci_controller.__file__).read_bytes()).hexdigest()
    require(controller_hash==hashlib.sha256(kit['.ai/scripts/trusted_ci_controller.py']['content']).hexdigest(),
            'fixed authority controller differs from the independent source pin')
    snapshot=current_snapshot(Readers(source,native.registry.api,d),d,worker['submitted']['pr'],worker['submitted']['run_id'],1)
    issued=c.clock() if document is None else document['value']['inputs']['issued']
    inputs=dict(record_digest=digest(record),worker=worker,worker_proof={k:v for k,v in completed['proof'].items() if k!='document'},
        manifest=manifest(completed['files']),seed=dict(revision=record['pair']['fixture_revision'],manifest=manifest(seed)),source_pin=source_pin,
        snapshot=snapshot,binding=binding,runtime=runtime,image=p['image'],controller_sha256=controller_hash,issued=issued,expires=end(record))
    workflow=c.store(c.root/'trial-workflow').read(); provisioning=c.document
    def guard():
        require(journal.read()==document and c.store(c.root/'trial-workflow').read()==workflow and c.document==provisioning and
                c.store(c.root/'trial').read()==provisioning and c.store(c.root/'trial-candidates').read() is None,
                'native eligibility ownership changed')
        c.session._owned(record['origin']['binding']); c.session.registry.unchanged(record['origin']['binding'])
        native.registry.unchanged(binding)
        require(current_snapshot(Readers(source,native.registry.api,d),d,snapshot['pr'],snapshot['run_id'],1)==snapshot,
                'eligibility source or tested merge changed')
        require(issued<=c.clock()<end(record),'original eligibility budget consumed by blocking reads')
    guard()
    if document is None:
        document=journal.write(None,dict(phase='execution-started',inputs=inputs,observation=None,claim=None,link=None))
        guard(); started=c.clock(); start=time.monotonic_ns()
        # The report's synthetic Actions execution metadata is never attested.
        # Only actual local controller outcomes/cleanup and separate CLOSED
        # worker provenance cross into this native-local observation.
        result=verify(source,d,snapshot,completed['proof']['job_id'],guard,c.clock,runtime)
        closed=native._worker_completion(record,prompt,source)
        require(closed['result']==worker and manifest(closed['files'])==inputs['manifest'],'CLOSED worker changed during eligibility')
        guard()
        observation=dict(kind='native-local-critical-observation',snapshot=snapshot,runtime=runtime,image=p['image'],
            controller_sha256=controller_hash,started=started,completed=c.clock(),elapsed_ms=(time.monotonic_ns()-start)//1000000,
            outcomes=result['report']['outcomes'],cleanup_complete=result['cleanup_complete'])
        require(result['report']['snapshot']==snapshot and result['report']['deployment_digest']==digest(d) and
                observation['outcomes']==[dict(id=check,status='success') for check in CHECKS] and observation['cleanup_complete'] is True,
                'native worker failed real strict eligibility')
        document=journal.write(document,dict(phase='verified',inputs=inputs,observation=observation,claim=None,link=None))
    value=copy.deepcopy(document['value'])
    require(value['inputs']==inputs and value['phase'] in ('verified','publication-started','complete'),
            'eligibility execution remains unknown; no replacement execution')
    if value['phase']=='verified':
        preview=dict(kind='native-eligible-tree-preview',inputs=inputs,observation=value['observation'],scope=copy.deepcopy(SCOPE))
        require(callable(approve) and approve(copy.deepcopy(preview))==digest(preview),'exact native eligibility approval required')
        guard()
        claim=dict(schema_version=1,kind=KIND,name='eligibility',task_id=record['task_id'],execution=None,
                   record_digest=digest(record),preview=preview,approval=digest(preview))
        value.update(phase='publication-started',claim=claim)
        document=journal.write(document,value)
        link=_publish_native(c,record,claim,guard)
    else:
        link=dict(kind=KIND,revision=c.session.registry.ref(trial_reference(value['claim'])))
        require(read_native(c.session.registry,link,record)==value['claim'],'eligibility publication remains unknown')
    select(c.session.registry,record,worker,link,'new-head','prior',c.clock)
    guard()
    if value['phase']!='complete':
        value.update(phase='complete',link=link)
        journal.write(document,value)
    return copy.deepcopy(link)
