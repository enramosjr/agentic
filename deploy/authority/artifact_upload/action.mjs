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
  const credential = role === 'credential' && Boolean(purpose);
  const model = role === 'model-authorization' && environment.GITHUB_JOB === 'model_auth';
  const prepare = role === 'prepare-task' && environment.GITHUB_JOB === 'prepare_task';
  const task = role === 'task' && environment.GITHUB_JOB === 'task' && platform === 'linux';
  const controls = role === 'task-controls' && environment.GITHUB_JOB === 'task_controls';
  const challenge = credential ? environment.INPUT_CHALLENGE : prepare
    ? JSON.stringify({prompt:environment.INPUT_PROMPT}) : environment.INPUT_TASK;
  if ((!credential && !model && !prepare && !task && !controls) || typeof challenge !== 'string' ||
      Buffer.byteLength(challenge) === 0 || Buffer.byteLength(challenge) > 65536 ||
      typeof environment.pythonLocation !== 'string' || !isAbsolute(environment.pythonLocation)) {
    throw new Error('fixed service role and bounded input required');
  }
  const secrets = credential
    ? [`AGENTIC_${purpose.toUpperCase()}_${purpose.startsWith('model_') ? 'KEY' : 'PRIVATE_KEY'}`]
    : model ? ['AGENTIC_MODEL_VAULT_KEY', 'AGENTIC_MODEL_DELIVERY_KEY']
    : prepare ? ['AGENTIC_READER_PRIVATE_KEY'] : controls ? ['AGENTIC_ADMIN_PRIVATE_KEY']
    : ['AGENTIC_CODING_PRIVATE_KEY','AGENTIC_MODEL_DELIVERY_KEY'];
  const childEnvironment = {};
  for (const [key, value] of Object.entries(environment)) {
    if (/^(GITHUB_|RUNNER_)[A-Z0-9_]+$/.test(key) || ['PATH', 'SystemRoot', 'SYSTEMROOT',
        'ACTIONS_RUNTIME_TOKEN', 'ACTIONS_RESULTS_URL', ...secrets].includes(key)) {
      childEnvironment[key] = value;
    }
  }
  const python = resolve(environment.pythonLocation, 'bin/python3');
  const argv = ['-I', '-B', resolve(root, 'deploy/authority/service.py'), role, process.execPath];
  return {executable: task ? '/usr/bin/sudo' : python,
    argv: task ? ['-n','--preserve-env='+Object.keys(childEnvironment).join(','),python,...argv] : argv,
    environment: childEnvironment, input: Buffer.from(challenge)};
}

export function preparedOutput(raw) {
  if (typeof raw !== 'string' || Buffer.byteLength(raw) > 65536) throw new Error('bounded output required');
  const text = raw.trim();
  if (/[\r\n]/.test(text)) throw new Error('single data output required');
  const value = JSON.parse(text);
  const fields = ['configuration_revision','deployment_digest','prompt','schema_version','source_base','task'];
  if (!value || Array.isArray(value) || Object.keys(value).sort().join() !== fields.join() ||
      value.schema_version !== 2 || typeof value.prompt !== 'string' || !value.prompt ||
      !['source_base','configuration_revision','deployment_digest'].every(key=>typeof value[key] === 'string') ||
      !/^[0-9a-f]{40}$/.test(value.source_base) || !/^[0-9a-f]{40}$/.test(value.configuration_revision) ||
      !/^[0-9a-f]{64}$/.test(value.deployment_digest) || !value.task || Array.isArray(value.task) ||
      Object.keys(value.task).sort().join() !== 'attempt,deadline,purpose,run_id,task_id' ||
      !/^[0-9a-f]{32}$/.test(value.task.task_id) || value.task.purpose !== 'task' ||
      !['attempt','deadline','run_id'].every(key=>Number.isInteger(value.task[key]) && value.task[key] > 0)) {
    throw new Error('closed prepared task output required');
  }
  return 'request='+text+'\n';
}

export function run(environment = process.env, launch = spawnSync) {
  try {
    const value = launchParameters(environment);
    const prepare = environment.INPUT_ROLE === 'prepare-task';
    const child = launch(value.executable, value.argv, {env: value.environment, cwd: root,
      input: value.input, stdio: ['pipe', prepare ? 'pipe' : 'ignore', 'ignore'],
      timeout: ['task','task-controls'].includes(environment.INPUT_ROLE) ? 900000 : 300000,
      maxBuffer: prepare ? 65537 : 1024});
    if (child.status !== 0 || child.error) return 1;
    if (prepare) {
      const path = environment.GITHUB_OUTPUT;
      if (typeof path !== 'string' || !isAbsolute(path)) return 1;
      const stat = lstatSync(path);
      if (!stat.isFile() || stat.isSymbolicLink() || stat.nlink !== 1) return 1;
      appendFileSync(path, preparedOutput(child.stdout.toString('utf8')), {encoding:'utf8'});
    }
    return 0;
  } catch { return 1; }
}

if (process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url) {
  process.exitCode = run();
  if (process.exitCode) process.stderr.write('authority consumer refused; no verified progress claimed\n');
}
