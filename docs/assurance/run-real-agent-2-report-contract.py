"""Prepared follow-up entrypoint; do not invoke without fresh human authorization."""
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
namespace = ROOT / 'docs/assurance/operator-2-report-contract'
if sys.argv[1:] != ['--authorized']:
    raise SystemExit('No models launched. Fresh user authorization is required for two follow-up fixture cells.')
report = json.loads((namespace / 'preparation.json').read_text())
frozen = Path(report['frozen_source'])
if Path(report['result_path']).exists():
    raise SystemExit('follow-up result already exists; never overwrite or retry terminal cells')
for name, pin in report['files'].items():
    for path in (ROOT / name, frozen / name):
        if (hashlib.sha256(path.read_bytes()).hexdigest() != pin['sha256']
                or oct(stat.S_IMODE(path.stat().st_mode)) != pin['mode']):
            raise SystemExit('prepared source drift; no models launched: ' + name)
for name, digest in report['provenance']['agent']['inputs'].items():
    if hashlib.sha256(Path(name).read_bytes()).hexdigest() != digest:
        raise SystemExit('prepared agent/config input drift; no models launched')
env = dict(os.environ)
for key in ('ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'ANTHROPIC_BASE_URL',
            'CLAUDE_CODE_USE_BEDROCK', 'CLAUDE_CODE_USE_VERTEX', 'CLAUDE_CODE_USE_FOUNDRY'):
    env.pop(key, None)
result = subprocess.run(['/home/enramosjr/.local/bin/claude', 'auth', 'status'], cwd=frozen,
                        env=env, capture_output=True, text=True, check=True)
auth = json.loads(result.stdout)
summary = {key: auth.get(key) for key in ('loggedIn', 'authMethod', 'apiProvider', 'subscriptionType')}
(namespace / 'effective-auth.json').write_text(json.dumps(summary, indent=2) + '\n')
if not (summary['loggedIn'] and summary['authMethod'] == 'claude.ai'
        and summary['apiProvider'] == 'firstParty' and summary['subscriptionType'] == 'pro'):
    raise SystemExit('subscription-only authentication refused; no models launched')
argv = json.loads((namespace / 'planned-evaluation-command.json').read_text())
raise SystemExit(subprocess.run(argv, cwd=frozen, env=env).returncode)
