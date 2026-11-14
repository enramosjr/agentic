// Compatibility of the pinned real SDK's archive path, entirely offline.
import assert from 'node:assert/strict';
import {mkdtemp, writeFile, lstat, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, dirname, resolve} from 'node:path';
import {DefaultArtifactClient} from '@actions/artifact';
import {createZipUploadStream} from './node_modules/@actions/artifact/lib/internal/upload/zip.js';

assert.equal(typeof new DefaultArtifactClient().uploadArtifact, 'function');
const parent = resolve(tmpdir());
const directory = await mkdtemp(join(parent, 'agentic-sdk-test-'));
try {
  const path = join(directory, 'receipt.json');
  const content = Buffer.from('{"exact":"offline SDK archive fixture"}');
  await writeFile(path, content, {flag: 'wx', mode: 0o600});
  const stream = await createZipUploadStream([
    {sourcePath: path, destinationPath: 'receipt.json', stats: await lstat(path)}
  ], 0);
  const chunks = [];
  for await (const chunk of stream) chunks.push(chunk);
  const zip = Buffer.concat(chunks);
  assert.equal(zip.readUInt32LE(0), 0x04034b50);
  assert.ok(zip.includes(content));
  assert.ok(zip.includes(Buffer.from('receipt.json')));
  const end = zip.length - 22;
  assert.equal(zip.readUInt32LE(end), 0x06054b50);
  assert.equal(zip.readUInt16LE(end + 10), 1);
  console.log('real artifact SDK import and single-file archive PASS; no upload performed');
} finally {
  assert.equal(dirname(resolve(directory)), parent);
  await rm(directory, {recursive: true, force: true});
}
