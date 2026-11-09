import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {join} from 'node:path';
import {mkdtempSync,readFileSync,writeFileSync,unlinkSync,rmdirSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {launchParameters, preparedOutput, producerOutput, run} from './action.mjs';

const env = {INPUT_ROLE: 'credential', INPUT_CHALLENGE: '{"fixture":true}',
  pythonLocation: '/opt/hostedtoolcache/Python/3.13.9/x64', GITHUB_TOKEN: 'synthetic-reader',
  GITHUB_JOB: 'coding_credential_proof', AGENTIC_CODING_PRIVATE_KEY: 'synthetic-coding',
  AGENTIC_ADMIN_PRIVATE_KEY: 'must-not-cross', ACTIONS_RUNTIME_TOKEN: 'synthetic-artifact',
  ACTIONS_RESULTS_URL: 'https://results-receiver.actions.githubusercontent.com',
  PYTHONPATH: '/hostile', LD_PRELOAD: '/hostile', OPENAI_API_KEY: 'must-not-cross',
  AWS_ACCESS_KEY_ID: 'must-not-cross', PATH: '/usr/bin:/bin'};
for (const [role, job, keys] of [
  ['discover','discover',['READER']], ['prepare','prepare',['ADMIN']], ['verify','verify',['READER']],
  ['publication-controls','publication_controls',['ADMIN']], ['publish','publish',['ISSUER']],
  ['broker','broker',['MERGE','READER']], ['controls','controls',['ADMIN']],
  ['proof','coding_proof',['CODING']], ['final-proof','issuer_final_proof',['ISSUER']],
  ['finalize','finalize',['ADMIN']]]) {
  const source = {...env,INPUT_ROLE:role,GITHUB_JOB:job,INPUT_TASK:'{}',AGENTIC_RECOVERY_PIN:'{"fixture":true}'};
  for(const purpose of ['ADMIN','READER','ISSUER','CODING','MERGE']) source[`AGENTIC_${purpose}_PRIVATE_KEY`] = 'synthetic';
  const params = launchParameters(source,'linux');
  assert.equal(params.argv.at(-2),role);
  for(const purpose of ['ADMIN','READER','ISSUER','CODING','MERGE']) {
    assert.equal(Boolean(params.environment[`AGENTIC_${purpose}_PRIVATE_KEY`]),keys.includes(purpose));
  }
  assert.equal(Boolean(params.environment.AGENTIC_RECOVERY_PIN),role === 'finalize');
  if(role === 'verify') assert.equal(params.executable,'/usr/bin/sudo');
  assert.throws(()=>launchParameters({...source,GITHUB_JOB:'candidate'}));
}
const result = launchParameters(env);
for (const [role,job,keys] of [
  ['ready','trial_case_ready',[]],['prepare','prepare',[]],['handoff','trial_case_handoff',[]],
  ['verify','verify',['READER']],['proof','admin_proof',['ADMIN']],
  ['publication-controls','publication_controls',['ADMIN']],['publish','publish',['ISSUER']],
  ['host-denial','trial_host_denial',['CODING']],
  ['broker','broker',['MERGE','READER']],['controls','controls',['ADMIN']],
  ['final-proof','merge_final_proof',['MERGE']],['finalize','finalize',['ADMIN']]]) {
  const source={...env,INPUT_ROLE:'case-'+role,GITHUB_JOB:job,INPUT_TASK:'{}',
    AGENTIC_TRIAL_CASE_ORIGIN_TOKEN:'fresh-case',AGENTIC_TRIAL_ORIGIN_TOKEN:'revoked-worker',
    AGENTIC_RECOVERY_PIN:'{"fixture":true}',AGENTIC_MODEL_VAULT_KEY:'must-not-cross',AGENTIC_MODEL_DELIVERY_KEY:'must-not-cross'};
  for(const p of ['ADMIN','READER','ISSUER','CODING','MERGE']) source[`AGENTIC_${p}_PRIVATE_KEY`]='synthetic';
  const params=launchParameters(source,'linux');
  assert.equal(params.argv.at(-2),'case-'+role);
  assert.equal(params.environment.AGENTIC_TRIAL_CASE_ORIGIN_TOKEN,'fresh-case');
  assert.equal(params.environment.AGENTIC_TRIAL_ORIGIN_TOKEN,undefined);
  assert.equal(params.environment.AGENTIC_MODEL_VAULT_KEY,undefined);
  assert.equal(params.environment.AGENTIC_MODEL_DELIVERY_KEY,undefined);
  for(const p of ['ADMIN','READER','ISSUER','CODING','MERGE']) assert.equal(Boolean(params.environment[`AGENTIC_${p}_PRIVATE_KEY`]),keys.includes(p));
  assert.equal(params.executable==='/usr/bin/sudo',role==='verify');
  assert.equal(Boolean(params.environment.AGENTIC_RECOVERY_PIN),role==='finalize');
  assert.throws(()=>launchParameters({...source,GITHUB_JOB:'candidate'},'linux'));
}
for (const [role,job,expected] of [
  ['trial-handoff','trial_handoff',[]], ['trial-prepare','trial_prepare',[]],
  ['trial-model','trial_model_auth',['AGENTIC_MODEL_VAULT_KEY','AGENTIC_MODEL_DELIVERY_KEY']],
  ['trial-proof','trial_reader_proof',['AGENTIC_READER_PRIVATE_KEY']],
  ['trial-worker','qualification',['AGENTIC_CODING_PRIVATE_KEY','AGENTIC_MODEL_DELIVERY_KEY']],
  ['trial-controls','trial_task_controls',['AGENTIC_ADMIN_PRIVATE_KEY']]]) {
  const source = {...env, INPUT_ROLE:role,GITHUB_JOB:job,INPUT_TASK:'{}',INPUT_PROMPT:'prompt',
    AGENTIC_TRIAL_ORIGIN_TOKEN:'scoped-read',AGENTIC_MODEL_VAULT_KEY:'vault',AGENTIC_MODEL_DELIVERY_KEY:'delivery',
    AGENTIC_READER_PRIVATE_KEY:'reader',AGENTIC_ISSUER_PRIVATE_KEY:'issuer',AGENTIC_MERGE_PRIVATE_KEY:'merge'};
  const params = launchParameters(source,'linux');
  assert.equal(params.environment.AGENTIC_TRIAL_ORIGIN_TOKEN,'scoped-read');
  for(const name of ['AGENTIC_ADMIN_PRIVATE_KEY','AGENTIC_READER_PRIVATE_KEY','AGENTIC_ISSUER_PRIVATE_KEY',
    'AGENTIC_CODING_PRIVATE_KEY','AGENTIC_MERGE_PRIVATE_KEY','AGENTIC_MODEL_VAULT_KEY','AGENTIC_MODEL_DELIVERY_KEY']) {
    assert.equal(Boolean(params.environment[name]),expected.includes(name));
  }
  assert.equal(params.executable === '/usr/bin/sudo',role === 'trial-worker');
  assert.throws(()=>launchParameters({...source,GITHUB_JOB:'candidate'},'linux'));
}
assert.equal(producerOutput('{"pr":7}\n','discover'),'request={"pr":7}\n');
assert.equal(producerOutput('{"pr":null}','discover'),'request={"pr":null}\n');
for(const bad of ['{"pr":true}','{"pr":0}','{"pr":7,"key":"secret"}','{"pr":7}\nextra=value']) {
  assert.throws(()=>producerOutput(bad,'discover'));
}
assert.equal(result.executable, resolve('/opt/hostedtoolcache/Python/3.13.9/x64', 'bin/python3'));
assert.equal(result.argv[0], '-I');
assert.equal(result.argv[1], '-B');
assert.equal(result.argv[3], 'credential');
assert.equal(result.input.toString(), env.INPUT_CHALLENGE);
assert.equal(result.environment.AGENTIC_CODING_PRIVATE_KEY, 'synthetic-coding');
assert.equal(result.environment.ACTIONS_RUNTIME_TOKEN, 'synthetic-artifact');
for (const name of ['AGENTIC_ADMIN_PRIVATE_KEY', 'PYTHONPATH', 'LD_PRELOAD', 'OPENAI_API_KEY', 'AWS_ACCESS_KEY_ID']) {
  assert.equal(result.environment[name], undefined);
}
for (const change of [{INPUT_ROLE: 'arbitrary-command'}, {GITHUB_JOB: 'verify'},
                      {INPUT_CHALLENGE: 'x'.repeat(65537)}, {pythonLocation: 'relative'}]) {
  assert.throws(() => launchParameters({...env, ...change}));
}
const model = launchParameters({...env, INPUT_ROLE: 'model-authorization', GITHUB_JOB: 'model_auth',
  INPUT_TASK: '{"task_id":"fixture"}', AGENTIC_MODEL_VAULT_KEY: 'synthetic-vault',
  AGENTIC_MODEL_DELIVERY_KEY: 'synthetic-delivery'});
assert.equal(model.argv[3], 'model-authorization');
assert.equal(model.input.toString(), '{"task_id":"fixture"}');
assert.equal(model.environment.AGENTIC_MODEL_VAULT_KEY, 'synthetic-vault');
assert.equal(model.environment.AGENTIC_MODEL_DELIVERY_KEY, 'synthetic-delivery');
assert.equal(model.environment.AGENTIC_CODING_PRIVATE_KEY, undefined);
assert.equal(model.environment.AGENTIC_ADMIN_PRIVATE_KEY, undefined);
assert.throws(() => launchParameters({...env, INPUT_ROLE: 'model-authorization', INPUT_TASK: '{}'}));
const prepare = launchParameters({...env, INPUT_ROLE:'prepare-task',GITHUB_JOB:'prepare_task',
  INPUT_PROMPT:'Reviewed prompt',AGENTIC_READER_PRIVATE_KEY:'synthetic-reader'});
assert.equal(prepare.argv[3],'prepare-task');
assert.deepEqual(JSON.parse(prepare.input.toString()),{prompt:'Reviewed prompt'});
assert.equal(prepare.environment.AGENTIC_READER_PRIVATE_KEY,'synthetic-reader');
assert.equal(prepare.environment.AGENTIC_CODING_PRIVATE_KEY,undefined);
const task = launchParameters({...env,INPUT_ROLE:'task',GITHUB_JOB:'task',INPUT_TASK:'{"fixture":true}',
  AGENTIC_MODEL_DELIVERY_KEY:'synthetic-delivery'},'linux');
assert.equal(task.executable,'/usr/bin/sudo');
assert.equal(task.argv[0],'-n');
assert.ok(task.argv[1].startsWith('--preserve-env='));
assert.equal(task.argv.at(-2),'task');
assert.equal(task.environment.AGENTIC_CODING_PRIVATE_KEY,'synthetic-coding');
assert.equal(task.environment.AGENTIC_MODEL_DELIVERY_KEY,'synthetic-delivery');
assert.equal(task.environment.AGENTIC_ADMIN_PRIVATE_KEY,undefined);
assert.equal(task.environment.AGENTIC_MODEL_VAULT_KEY,undefined);
assert.throws(()=>launchParameters({...env,INPUT_ROLE:'task',GITHUB_JOB:'task',INPUT_TASK:'{}'},'win32'));
const controlsEnv = {...env,INPUT_ROLE:'task-controls',GITHUB_JOB:'task_controls',INPUT_TASK:'{"fixture":true}',
  AGENTIC_MODEL_DELIVERY_KEY:'must-not-cross',AGENTIC_ADMIN_PRIVATE_KEY:'synthetic-admin'};
const controls = launchParameters(controlsEnv,'linux');
assert.equal(controls.executable,resolve(env.pythonLocation,'bin/python3'));
assert.equal(controls.argv[3],'task-controls');
assert.equal(controls.environment.AGENTIC_ADMIN_PRIVATE_KEY,'synthetic-admin');
for(const key of ['AGENTIC_CODING_PRIVATE_KEY','AGENTIC_MODEL_DELIVERY_KEY','OPENAI_API_KEY']) {
  assert.equal(controls.environment[key],undefined);
}
assert.throws(()=>launchParameters({...controlsEnv,GITHUB_JOB:'task'},'linux'));
assert.equal(run(controlsEnv,(_executable,_argv,options)=>{
  assert.equal(options.timeout,900000);
  return {status:0};
}),0);
const request = JSON.stringify({schema_version:2,task:{task_id:'a'.repeat(32),run_id:99,attempt:1,deadline:1900,purpose:'task'},
  source_base:'b'.repeat(40),prompt:'line 1\nline 2',configuration_revision:'c'.repeat(40),deployment_digest:'d'.repeat(64)});
assert.equal(preparedOutput(request+'\n'),'request='+request+'\n');
for(const raw of [request+'\nextra=command', '{}',JSON.stringify({private_key:'must-not-cross'}),request.repeat(65536)]) {
  assert.throws(()=>preparedOutput(raw));
}
const folder = mkdtempSync(join(tmpdir(),'agentic-action-fixture-'));
const output = join(folder,'outputs');
writeFileSync(output,'existing=keep\n',{flag:'wx'});
try {
  const prepareEnv = {...env,INPUT_ROLE:'prepare-task',GITHUB_JOB:'prepare_task',INPUT_PROMPT:'Reviewed prompt',
    AGENTIC_READER_PRIVATE_KEY:'synthetic-reader',GITHUB_OUTPUT:output};
  let invoked = 0;
  const launch = (executable,argv,options)=>{
    invoked += 1;
    assert.equal(argv[3],'prepare-task');
    assert.equal(options.env.AGENTIC_READER_PRIVATE_KEY,'synthetic-reader');
    assert.equal(options.env.AGENTIC_CODING_PRIVATE_KEY,undefined);
    return {status:0,stdout:Buffer.from(request+'\n')};
  };
  assert.equal(run(prepareEnv,launch),0);
  assert.equal(invoked,1);
  assert.equal(readFileSync(output,'utf8'),'existing=keep\nrequest='+request+'\n');
  const caseRequest=JSON.stringify({schema_version:2,configuration_revision:'a'.repeat(40),deployment_digest:'b'.repeat(64),
    operation_id:'c'.repeat(32),sequence:1,snapshot:{pr:7},task:{},qualification:{},
    host_case:true,handoff:{origin:{schema_version:2,repository:'owner/original',repository_id:701,registry_branch:'agentic-registry'},revision:'d'.repeat(40)}});
  const caseEnv={...env,INPUT_ROLE:'case-prepare',GITHUB_JOB:'prepare',INPUT_TASK:'{}',
    AGENTIC_TRIAL_CASE_ORIGIN_TOKEN:'fresh-case',GITHUB_OUTPUT:output};
  assert.equal(run(caseEnv,(_exe,argv,options)=>{
    assert.equal(argv.at(-2),'case-prepare');
    assert.equal(options.env.AGENTIC_ADMIN_PRIVATE_KEY,undefined);
    assert.equal(options.env.AGENTIC_TRIAL_CASE_ORIGIN_TOKEN,'fresh-case');
    return {status:0,stdout:Buffer.from(caseRequest+'\n')};
  }),0);
  assert.equal(readFileSync(output,'utf8'),'existing=keep\nrequest='+request+'\nrequest='+caseRequest+'\nhost_case=true\n');
  for(const bad of [JSON.stringify({...JSON.parse(caseRequest),handoff:null}),caseRequest+'\nextra=value']) {
    assert.throws(()=>producerOutput(bad,'case-prepare'));
  }
  const before = readFileSync(output);
  assert.equal(run(prepareEnv,()=>({status:0,stdout:Buffer.from(request+'\nforged=output')})),1);
  assert.deepEqual(readFileSync(output),before);
} finally {
  unlinkSync(output);
  rmdirSync(folder);
}
console.log('fixed action launcher contracts passed');
