"""Prepare only: one Codex cell, exact source/operator pins, no native preflight/model."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
generic = ROOT / 'docs/assurance/prepare-native-2-review-enforcement.py'
spec = importlib.util.spec_from_file_location('codex_v6_preparation', generic)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.NAMESPACE_NAME = 'operator-2-mechanical-codex-v6'
module.RUNNER_FILE = 'run-native-2-mechanical-codex-v6.py'
module.AGENTS = (('codex', '0.162.1', 'gpt-6.1-sol'),)
module.CAMPAIGN_SUFFIX = 'v6'


def main():
    module.main()
    namespace = ROOT / 'docs/assurance' / module.NAMESPACE_NAME
    report_path = namespace / 'preparation.json'
    report = json.loads(report_path.read_text())
    for path in (Path(__file__).resolve(), generic,
                 ROOT / 'docs/assurance/test-native-prebranch-2-v6.py'):
        report['operator_inputs'][str(path)] = module.pin(path)
    report['prepared_branch'] = 'codex/named-greeting'
    report['scope'] = 'One temporary control-delta fixture/KIT payload to OpenAI ChatGPT subscription;300agent/330wall; exact invocation-local project/hook trust; no Claude/retries/APIbilling/bypass/globalpersistentchange.'
    report['requires_fresh_allocation'] = True
    report_path.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
