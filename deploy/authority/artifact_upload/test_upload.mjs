import assert from 'node:assert/strict';
import {readFile, lstat} from 'node:fs/promises';
import {upload} from './upload.mjs';

const name = `agentic-merge-${'1'.repeat(32)}-s1-a1-dispatch`;
let seen = 0;
let uploadedPath;
const client = {
  async uploadArtifact(actual, files, root, options) {
    seen += 1;
    assert.equal(actual, name);
    assert.equal(files.length, 1);
    uploadedPath = files[0];
    assert.equal(files[0], `${root}/receipt.json`.replaceAll('/', (await import('node:path')).sep));
    assert.equal(await readFile(files[0], 'utf8'), '{"kind":"dispatch"}');
    assert.deepEqual(options, {retentionDays: 7, compressionLevel: 0});
    return {id: 123};
  }
};
assert.equal(await upload(name, Buffer.from('{"kind":"dispatch"}'), client), 123);
assert.equal(seen, 1);
await assert.rejects(lstat(uploadedPath), {code: 'ENOENT'});
for (const bad of ['../receipt', `${name}-extra`, name.replace('-s1-', '-s0-')]) {
  await assert.rejects(upload(bad, Buffer.from('{}'), client));
}
await assert.rejects(upload(name, Buffer.alloc(1024 * 1024 + 1), client));
await assert.rejects(upload(name, Buffer.from('{}'), {
  async uploadArtifact() { throw new Error('lost acknowledgement'); }
}));
assert.equal(seen, 1);
async function readyContract(uploadFunction, kind = 'control-ready') {
  const readyName = name.replace(/dispatch$/, kind);
  const raw = JSON.stringify({kind});
  const result = await uploadFunction(readyName, Buffer.from(raw), {
    async uploadArtifact(actual, files, root, options) {
      assert.equal(actual, readyName);
      assert.equal(await readFile(files[0], 'utf8'), raw);
      assert.equal(options.retentionDays, 7);
      return {id: 456};
    }
  });
  assert.equal(result, 456);
}
await readyContract(upload);
await readyContract(upload, 'not-submitted');
await readyContract(upload, 'host-denied');
await assert.rejects(readyContract(async (actual, ...rest) => {
  if (actual.endsWith('-not-submitted')) throw new Error('deliberately rejected terminal evidence');
  return upload(actual, ...rest);
}, 'not-submitted'), /deliberately rejected terminal evidence/);
// The same positive contract fails against the earlier rejecting behavior.
await assert.rejects(readyContract(async (actual, ...rest) => {
  if (actual.endsWith('-control-ready')) throw new Error('deliberately rejected readiness');
  return upload(actual, ...rest);
}), /deliberately rejected readiness/);
const documents = [
  ...['trial-handoff','trial-case-ready','trial-case-handoff','trial-case-terminal','trial-host-intent','trial-host-denial','trial-task','trial-task-ready','trial-task-controls'].map(role=>[`${role}-${'a'.repeat(32)}-1`,`${role}.json`]),
  ['evidence-7-1', 'evidence.json'], ['controls-7-1', 'controls.json'],
  ['publication-controls-7-1', 'publication-controls.json'],
  ['trial-publication-intent-7-1','trial-publication-intent.json'],
  ['trial-publication-denial-7-1','trial-publication-denial.json'],
  ['trial-publication-observation-7-1','trial-publication-observation.json'],
  ['task-' + 'a'.repeat(32) + '-1', 'task.json'], ['qualification-1', 'qualification.json'],
  ['task-ready-' + 'a'.repeat(32) + '-1', 'task-ready.json'],
  ['task-controls-' + 'a'.repeat(32) + '-1', 'task-controls.json'],
  ['model-lease-' + 'a'.repeat(32) + '-1', 'model-lease.json'],
  ...['proof', 'final-proof', 'credential-proof'].flatMap(role =>
    ['admin', 'reader', 'issuer', 'coding', 'merge'].map(purpose => [`${role}-${purpose}-1`, `${role}.json`])),
  ['credential-proof-model_vault-1', 'credential-proof.json'],
  ['credential-proof-model_delivery-1', 'credential-proof.json']
];
for (const [artifactName, member] of documents) {
  let path;
  assert.equal(await upload(artifactName, Buffer.from('{"document":"synthetic"}'), {
    async uploadArtifact(actual, files, root, options) {
      assert.equal(actual, artifactName);
      assert.equal(files.length, 1);
      path = files[0];
      assert.equal((await import('node:path')).basename(path), member);
      assert.equal(await readFile(path, 'utf8'), '{"document":"synthetic"}');
      assert.deepEqual(options, {retentionDays: 7, compressionLevel: 0});
      return {id: 789};
    }
  }), 789);
  await assert.rejects(lstat(path), {code: 'ENOENT'});
}
for (const invalid of ['credential-proof-owner-1', 'proof-model_vault-1', 'evidence-0-1',
  'credential-proof-admin-1-extra', 'task-../authority-1', 'qualification-0', 'evidence-7-1/secret']) {
  await assert.rejects(upload(invalid, Buffer.from('{}'), {
    async uploadArtifact() { throw new Error('invalid name reached the SDK'); }
  }), /invalid bounded/);
}
console.log('artifact upload boundary contracts PASS');
