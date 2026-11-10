// Fixed Python service launcher. No dispatch input selects an executable/path.
import {spawnSync} from 'node:child_process';
import {appendFileSync, lstatSync} from 'node:fs';
import {dirname, isAbsolute, resolve} from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
const purposes = ['admin', 'reader', 'issuer', 'coding', 'merge', 'model_vault', 'model_delivery'];

export function launchParameters(environment, platform = process.platform) {
  const purpose = purposes.find(p => environment.GITHUB_JOB === `${p}_credential_proof`);
  const role = environment.INPUT_ROLE;
  const caseRole = typeof role === 'string' && role.startsWith('case-') ? role.slice(5) : null;
  const caseJobs = {ready:'trial_case_ready',prepare:'prepare',handoff:'trial_case_handoff',verify:'verify',
    'publication-controls':'publication_controls',publish:'publish','host-denial':'trial_host_denial',broker:'broker',controls:'controls',finalize:'finalize'};
  const caseProof = ['proof','final-proof'].includes(caseRole) && ['admin','reader','issuer','coding','merge'].find(
    p=>environment.GITHUB_JOB === `${p}_${caseRole.replace('-','_')}`);
  const caseProducer = Boolean(caseProof) || Object.hasOwn(caseJobs,caseRole) && caseJobs[caseRole] === environment.GITHUB_JOB;
  const credential = role === 'credential' && Boolean(purpose);
  const model = role === 'model-authorization' && environment.GITHUB_JOB === 'model_auth';
  const prepare = role === 'prepare-task' && environment.GITHUB_JOB === 'prepare_task';
  const task = role === 'task' && environment.GITHUB_JOB === 'task' && platform === 'linux';
  const controls = role === 'task-controls' && environment.GITHUB_JOB === 'task_controls';
  const trialProof = role === 'trial-proof' && ['admin','reader','issuer','coding','merge'].find(
    p=>environment.GITHUB_JOB === `trial_${p}_proof`);
  const trialJobs = {'trial-handoff':'trial_handoff','trial-prepare':'trial_prepare',
    'trial-model':'trial_model_auth','trial-worker':'qualification','trial-controls':'trial_task_controls'};
  const trial = Boolean(trialProof) || Object.hasOwn(trialJobs,role) && trialJobs[role] === environment.GITHUB_JOB;
  const producers = {discover:['discover','READER'],prepare:['prepare','ADMIN'],verify:['verify','READER'],
    'publication-controls':['publication_controls','ADMIN'],publish:['publish','ISSUER'],
    broker:['broker','MERGE','READER'],controls:['controls','ADMIN'],finalize:['finalize','ADMIN']};
  const proof = ['proof','final-proof'].includes(role) && ['admin','reader','issuer','coding','merge'].find(
    p=>environment.GITHUB_JOB === `${p}_${role.replace('-','_')}`);
  const producer = Object.hasOwn(producers,role) && producers[role][0] === environment.GITHUB_JOB;
  const privileged = task || role === 'verify' && producer || role === 'trial-worker' && trial || caseProducer && caseRole === 'verify';
  const challenge = credential ? environment.INPUT_CHALLENGE : prepare
    ? JSON.stringify({prompt:environment.INPUT_PROMPT}) : role === 'trial-prepare' && trial
      ? JSON.stringify({handoff:JSON.parse(environment.INPUT_TASK),prompt:environment.INPUT_PROMPT}) : environment.INPUT_TASK;
  if ((!credential && !model && !prepare && !task && !controls && !producer && !proof && !trial && !caseProducer) ||
      privileged && platform !== 'linux' || typeof challenge !== 'string' ||
      Buffer.byteLength(challenge) === 0 || Buffer.byteLength(challenge) > 65536 ||
      typeof environment.pythonLocation !== 'string' || !isAbsolute(environment.pythonLocation)) {
    throw new Error('fixed service role and bounded input required');
  }
  const trialSecrets = role === 'trial-model' ? ['AGENTIC_MODEL_VAULT_KEY','AGENTIC_MODEL_DELIVERY_KEY'] :
    role === 'trial-worker' ? ['AGENTIC_CODING_PRIVATE_KEY','AGENTIC_MODEL_DELIVERY_KEY'] :
    role === 'trial-controls' ? ['AGENTIC_ADMIN_PRIVATE_KEY'] :
    trialProof ? [`AGENTIC_${trialProof.toUpperCase()}_PRIVATE_KEY`] : [];
  // Scheduling data selects which single key survives this launcher. Python
  // authenticates the exact case before constructing that App or minting tokens.
  const hostCase = caseProducer && caseRole === 'host-denial' ? JSON.parse(challenge).host_case : null;
  if(caseProducer && caseRole === 'host-denial' && !['direct-push','coding-update','missing-approval','bad-acceptance','replaced-checks','forged-records'].includes(hostCase)) {
    throw new Error('exact host case scheduling identity required');
  }
  const caseKeys = caseProof ? [caseProof.toUpperCase()] : caseRole === 'broker' ? ['MERGE','READER'] :
    ['publication-controls','controls','finalize'].includes(caseRole) ? ['ADMIN'] : caseRole === 'host-denial' ? [['missing-approval','bad-acceptance','replaced-checks','forged-records'].includes(hostCase)?'MERGE':'CODING'] : caseRole === 'publish' ? ['ISSUER'] : caseRole === 'verify' ? ['READER'] : [];
  const secrets = caseProducer ? ['AGENTIC_TRIAL_CASE_ORIGIN_TOKEN',...caseKeys.map(p=>`AGENTIC_${p}_PRIVATE_KEY`)] : trial ? ['AGENTIC_TRIAL_ORIGIN_TOKEN',...trialSecrets] : credential
    ? [`AGENTIC_${purpose.toUpperCase()}_${purpose.startsWith('model_') ? 'KEY' : 'PRIVATE_KEY'}`]
    : model ? ['AGENTIC_MODEL_VAULT_KEY', 'AGENTIC_MODEL_DELIVERY_KEY']
    : prepare ? ['AGENTIC_READER_PRIVATE_KEY'] : controls ? ['AGENTIC_ADMIN_PRIVATE_KEY']
    : producer ? producers[role].slice(1).map(p=>`AGENTIC_${p}_PRIVATE_KEY`)
    : proof ? [`AGENTIC_${proof.toUpperCase()}_PRIVATE_KEY`]
    : ['AGENTIC_CODING_PRIVATE_KEY','AGENTIC_MODEL_DELIVERY_KEY'];
  const childEnvironment = {};
  for (const [key, value] of Object.entries(environment)) {
    if (/^(GITHUB_|RUNNER_)[A-Z0-9_]+$/.test(key) || ['PATH', 'SystemRoot', 'SYSTEMROOT',
        'ACTIONS_RUNTIME_TOKEN', 'ACTIONS_RESULTS_URL', ...(['finalize','case-finalize'].includes(role) ? ['AGENTIC_RECOVERY_PIN'] : []), ...secrets].includes(key)) {
      childEnvironment[key] = value;
    }
  }
  const python = resolve(environment.pythonLocation, 'bin/python3');
  const argv = ['-I', '-B', resolve(root, 'deploy/authority/service.py'), role, process.execPath];
  return {executable: privileged ? '/usr/bin/sudo' : python,
    argv: privileged ? ['-n','--preserve-env='+Object.keys(childEnvironment).join(','),python,...argv] : argv,
    environment: childEnvironment, input: Buffer.from(challenge)};
}

export function preparedOutput(raw, trial = false) {
  if (typeof raw !== 'string' || Buffer.byteLength(raw) > 65536) throw new Error('bounded output required');
  const text = raw.trim();
  if (/[\r\n]/.test(text)) throw new Error('single data output required');
  const value = JSON.parse(text);
  const fields = ['configuration_revision','deployment_digest','prompt','schema_version','source_base','task'];
  if(trial) fields.splice(2,0,'handoff');
  if (!value || Array.isArray(value) || Object.keys(value).sort().join() !== fields.join() ||
      value.schema_version !== 2 || typeof value.prompt !== 'string' || !value.prompt ||
      !['source_base','configuration_revision','deployment_digest'].every(key=>typeof value[key] === 'string') ||
      !/^[0-9a-f]{40}$/.test(value.source_base) || !/^[0-9a-f]{40}$/.test(value.configuration_revision) ||
      !/^[0-9a-f]{64}$/.test(value.deployment_digest) || !value.task || Array.isArray(value.task) ||
      Object.keys(value.task).sort().join() !== 'attempt,deadline,purpose,run_id,task_id' ||
      !/^[0-9a-f]{32}$/.test(value.task.task_id) || value.task.purpose !== (trial ? 'qualification' : 'task') ||
      !['attempt','deadline','run_id'].every(key=>Number.isInteger(value.task[key]) && value.task[key] > 0)) {
    throw new Error('closed prepared task output required');
  }
  if(trial && (!value.handoff || Object.keys(value.handoff).sort().join() !== 'origin,revision' ||
      !/^[0-9a-f]{40}$/.test(value.handoff.revision) || !value.handoff.origin ||
      Object.keys(value.handoff.origin).sort().join() !== 'registry_branch,repository,repository_id,schema_version' ||
      value.handoff.origin.schema_version !== 2 || !Number.isSafeInteger(value.handoff.origin.repository_id) ||
      value.handoff.origin.repository_id <= 0 || typeof value.handoff.origin.repository !== 'string' ||
      typeof value.handoff.origin.registry_branch !== 'string')) throw new Error('closed handoff coordinates required');
  return 'request='+text+'\n';
}

export function producerOutput(raw, role) {
  if (typeof raw !== 'string' || Buffer.byteLength(raw) > 65536) throw new Error('bounded producer output required');
  const text = raw.trim();
  if (/[\r\n]/.test(text)) throw new Error('single producer output required');
  const value = JSON.parse(text);
  if (!value || Array.isArray(value)) throw new Error('producer object required');
  const expected = role === 'discover' ? 'pr' : role === 'case-prepare' ?
    'configuration_revision,deployment_digest,handoff,host_case,operation_id,qualification,schema_version,sequence,snapshot,task' :
    'configuration_revision,deployment_digest,operation_id,qualification,schema_version,sequence,snapshot,task';
  if (Object.keys(value).sort().join() !== expected ||
      (role === 'discover' ? value.pr !== null && (!Number.isSafeInteger(value.pr) || value.pr <= 0) :
        value.schema_version !== 2 || !/^[0-9a-f]{32}$/.test(value.operation_id) ||
        !Number.isSafeInteger(value.sequence) || value.sequence <= 0)) throw new Error('closed producer output required');
  if (role === 'case-prepare' && (!['none','direct-push','coding-update','missing-approval','bad-acceptance','replaced-checks','forged-records'].includes(value.host_case) || !value.handoff || Array.isArray(value.handoff) ||
      Object.keys(value.handoff).sort().join() !== 'origin,revision' || !/^[0-9a-f]{40}$/.test(value.handoff.revision))) {
    throw new Error('closed case lookup required');
  }
  return 'request='+text+'\n'+(role === 'case-prepare' ? 'host_case='+value.host_case+'\n' : '');
}

export function run(environment = process.env, launch = spawnSync) {
  try {
    const value = launchParameters(environment);
    const prepare = ['prepare-task','discover','prepare','trial-prepare','case-prepare'].includes(environment.INPUT_ROLE);
    const child = launch(value.executable, value.argv, {env: value.environment, cwd: root,
      input: value.input, stdio: ['pipe', prepare ? 'pipe' : 'ignore', 'ignore'],
      timeout: ['verify','case-verify'].includes(environment.INPUT_ROLE) ? 1800000 : ['task','task-controls','trial-worker','trial-controls'].includes(environment.INPUT_ROLE) ? 900000 : 300000,
      maxBuffer: prepare ? 65537 : 1024});
    if (child.status !== 0 || child.error) return 1;
    if (prepare) {
      const path = environment.GITHUB_OUTPUT;
      if (typeof path !== 'string' || !isAbsolute(path)) return 1;
      const stat = lstatSync(path);
      if (!stat.isFile() || stat.isSymbolicLink() || stat.nlink !== 1) return 1;
      const raw = child.stdout.toString('utf8');
      appendFileSync(path, ['prepare-task','trial-prepare'].includes(environment.INPUT_ROLE) ?
        preparedOutput(raw,environment.INPUT_ROLE === 'trial-prepare') :
        producerOutput(raw,environment.INPUT_ROLE), {encoding:'utf8'});
    }
    return 0;
  } catch { return 1; }
}

if (process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url) {
  process.exitCode = run();
  if (process.exitCode) process.stderr.write('authority consumer refused; no verified progress claimed\n');
}
