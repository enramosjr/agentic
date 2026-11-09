import {mkdtemp, writeFile, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve, dirname} from 'node:path';

function documentMember(name) {
  if (typeof name !== 'string') return null;
  if (/^agentic-merge-[a-f0-9]{32}-s[1-9][0-9]{0,19}-a[1-9][0-9]{0,19}-(gate|dispatch|outcome|control-ready|not-submitted|host-denied)$/.test(name)) return 'receipt.json';
  const candidate = /^(evidence|controls|publication-controls)-[1-9][0-9]{0,19}-[1-9][0-9]{0,19}$/.exec(name);
  const proof = /^(proof|final-proof)-(admin|reader|issuer|coding|merge)-[1-9][0-9]{0,19}$/.exec(name);
  if (candidate) return `${candidate[1]}.json`;
  if (proof) return `${proof[1]}.json`;
  const trial = /^(trial-handoff|trial-case-ready|trial-case-handoff|trial-case-terminal|trial-host-intent|trial-host-denial|trial-task|trial-task-ready|trial-task-controls)-[a-f0-9]{32}-[1-9][0-9]{0,19}$/.exec(name);
  if (trial) return `${trial[1]}.json`;
  if (/^credential-proof-(admin|reader|issuer|coding|merge|model_vault|model_delivery)-[1-9][0-9]{0,19}$/.test(name)) return 'credential-proof.json';
  if (/^task-[a-f0-9]{32}-[1-9][0-9]{0,19}$/.test(name)) return 'task.json';
  const task = /^(task-ready|task-controls)-[a-f0-9]{32}-[1-9][0-9]{0,19}$/.exec(name);
  if (task) return `${task[1]}.json`;
  if (/^model-lease-[a-f0-9]{32}-[1-9][0-9]{0,19}$/.test(name)) return 'model-lease.json';
  if (/^qualification-[1-9][0-9]{0,19}$/.test(name)) return 'qualification.json';
  return null;
}

export async function upload(name, raw, client) {
  const member = documentMember(name);
  if (!member || !Buffer.isBuffer(raw) || raw.length === 0 || raw.length > 1024 * 1024) {
    throw new Error('invalid bounded authority document');
  }
  const parent = resolve(tmpdir());
  const directory = await mkdtemp(join(parent, 'agentic-receipt-'));
  try {
    const file = join(directory, member);
    await writeFile(file, raw, {flag: 'wx', mode: 0o600});
    // This interface deliberately exposes only creation. No delete/overwrite,
    // generic paths, repository token, or "find latest" fallback is accepted.
    const result = await client.uploadArtifact(name, [file], directory,
      {retentionDays: 7, compressionLevel: 0});
    if (!Number.isSafeInteger(result?.id) || result.id <= 0) {
      throw new Error('artifact upload acknowledgement missing');
    }
    return result.id;
  } finally {
    // Verify the absolute target before recursive cleanup, including on Windows.
    if (dirname(resolve(directory)) !== parent || !directory.startsWith(join(parent, 'agentic-receipt-'))) {
      throw new Error('receipt cleanup scope differs');
    }
    await rm(directory, {recursive: true, force: true});
  }
}
