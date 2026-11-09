"""Artifact-only child of the pinned authority action; no ambient App keys.

The action launcher must supply runtime capabilities, pinned Node/SDK files and
private disk scratch. This helper neither discovers credentials nor retries.
"""
import base64
import json
import re
from pathlib import Path
import subprocess
import tempfile
from urllib.parse import urlsplit

from trusted_ci_policy import Refusal, loads, object_fields, positive, require


def document_member(name):
    """Closed producer names map to fixed members, never caller-selected paths."""
    if not isinstance(name, str): return None
    if re.fullmatch(r'agentic-merge-[a-f0-9]{32}-s[1-9][0-9]{0,19}-a[1-9][0-9]{0,19}-(gate|dispatch|outcome|control-ready|not-submitted|host-denied)', name):
        return 'receipt.json'
    candidate = re.fullmatch(r'(evidence|controls|publication-controls|trial-broker-intent|trial-broker-denial)-[1-9][0-9]{0,19}-[1-9][0-9]{0,19}', name)
    proof = re.fullmatch(r'(proof|final-proof)-(admin|reader|issuer|coding|merge)-[1-9][0-9]{0,19}', name)
    if candidate: return candidate.group(1) + '.json'
    if proof: return proof.group(1) + '.json'
    trial = re.fullmatch(r'(trial-handoff|trial-case-handoff|trial-case-ready|trial-case-terminal|trial-host-intent|trial-host-denial|trial-task|trial-task-ready|trial-task-controls)-[a-f0-9]{32}-[1-9][0-9]{0,19}', name)
    if trial: return trial.group(1) + '.json'
    if re.fullmatch(r'credential-proof-(admin|reader|issuer|coding|merge|model_vault|model_delivery)-[1-9][0-9]{0,19}', name):
        return 'credential-proof.json'
    if re.fullmatch(r'task-[a-f0-9]{32}-[1-9][0-9]{0,19}', name): return 'task.json'
    task = re.fullmatch(r'(task-ready|task-controls)-[a-f0-9]{32}-[1-9][0-9]{0,19}', name)
    if task: return task.group(1) + '.json'
    if re.fullmatch(r'model-lease-[a-f0-9]{32}-[1-9][0-9]{0,19}', name): return 'model-lease.json'
    if re.fullmatch(r'qualification-[1-9][0-9]{0,19}', name): return 'qualification.json'
    return None


class NodeUploader:
    def __init__(self, node, environment):
        node = Path(node)
        require(node.is_absolute() and node.is_file() and not node.is_symlink(), 'pinned absolute Node executable required')
        token = environment.get('ACTIONS_RUNTIME_TOKEN')
        url = urlsplit(environment.get('ACTIONS_RESULTS_URL', ''))
        require(isinstance(token, str) and 0 < len(token) <= 64 * 1024 and not any(ord(c) < 32 for c in token) and
                url.scheme == 'https' and url.hostname == 'results-receiver.actions.githubusercontent.com' and
                url.port in (None, 443) and not url.username and not url.password and
                url.path in ('', '/') and not url.query and not url.fragment,
                'trusted Actions artifact runtime capability required')
        self.node = str(node)
        self.environment = {k: v for k, v in environment.items() if k in ('SystemRoot', 'SYSTEMROOT')}
        self.environment.update(ACTIONS_RUNTIME_TOKEN=token,
            ACTIONS_RESULTS_URL='https://results-receiver.actions.githubusercontent.com',
            GITHUB_SERVER_URL='https://github.com', ACTIONS_ARTIFACT_UPLOAD_CONCURRENCY='1',
            ACTIONS_ARTIFACT_UPLOAD_TIMEOUT_MS='25000')

    def __call__(self, name, raw):
        require(document_member(name) is not None and isinstance(raw, bytes) and 0 < len(raw) <= 1024 * 1024,
                'bounded authority document required')
        root = Path(__file__).parent / 'artifact_upload'
        with tempfile.TemporaryDirectory(prefix='agentic-upload-') as temporary:
            private = Path(temporary).resolve()
            ack = private / 'ack.json'
            env = dict(self.environment, TMPDIR=str(private), TMP=str(private), TEMP=str(private),
                       GITHUB_WORKSPACE=str(private))
            payload = json.dumps(dict(name=name, document=base64.b64encode(raw).decode('ascii'), ack=str(ack))).encode()
            try:
                result = subprocess.run([self.node, str(root / 'cli.mjs')], cwd=root, env=env,
                    input=payload, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
                require(result.returncode == 0 and ack.is_file() and not ack.is_symlink() and
                        ack.resolve().parent == private and 0 < ack.stat().st_size <= 1024,
                        'artifact upload acknowledgement unavailable; do not retry dispatch')
                value = loads(ack.read_bytes())
                object_fields(value, ('artifact_id',), 'artifact upload acknowledgement')
                require(positive(value['artifact_id']), 'numeric uploaded artifact identity required')
                return value['artifact_id']
            except (OSError, subprocess.TimeoutExpired):
                raise Refusal('artifact upload completion unknown; do not retry dispatch') from None
