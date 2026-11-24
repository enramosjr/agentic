// Internal child of the pinned authority action, not an installed setup command.
import {writeFile} from 'node:fs/promises';
import {isAbsolute} from 'node:path';
import {upload} from './upload.mjs';

let size = 0;
const chunks = [];
try {
  for await (const chunk of process.stdin) {
    size += chunk.length;
    if (size > 1500000) throw new Error('input exceeds limit');
    chunks.push(chunk);
  }
  const value = JSON.parse(Buffer.concat(chunks).toString('utf8'));
  if (JSON.stringify(Object.keys(value).sort()) !== JSON.stringify(['ack', 'document', 'name']) ||
      typeof value.document !== 'string' || typeof value.ack !== 'string' || !isAbsolute(value.ack) ||
      !process.env.ACTIONS_RUNTIME_TOKEN || !process.env.ACTIONS_RESULTS_URL) {
    throw new Error('trusted runtime upload capability required');
  }
  const raw = Buffer.from(value.document, 'base64');
  if (raw.toString('base64') !== value.document) throw new Error('invalid receipt encoding');
  // The SDK writes diagnostics itself. The parent uses the private ack file;
  // suppress both streams before importing it so signed URLs cannot reach logs.
  process.stdout.write = () => true;
  process.stderr.write = () => true;
  const {DefaultArtifactClient} = await import('@actions/artifact');
  const id = await upload(value.name, raw, new DefaultArtifactClient());
  await writeFile(value.ack, JSON.stringify({artifact_id: id}), {flag: 'wx', mode: 0o600});
} catch {
  // Never echo SDK errors, signed URLs, runtime tokens, or receipt bodies.
  process.exitCode = 1;
}
