#!/usr/bin/env python3
"""Detect a forbidden dependency using a governed requirement in a throwaway repository."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import signal
import sys
import tempfile
from typing import Callable, Optional, TextIO

sys.dont_write_bytecode = True

from assurance_demo import Session, build, _base, DemoFailure, LIMIT

ADR = 'knowledge/project/decisions/layers.md'
DECLARATION = '  - Governed-by: [Layer boundary](../project/decisions/layers.md#boundary)'
CHECK = '''import ast
from pathlib import Path
import sys

nodes = ast.walk(ast.parse(Path('src/calc.py').read_text()))
for node in nodes:
    names = [alias.name for alias in node.names] if isinstance(node, ast.Import) else []
    if isinstance(node, ast.ImportFrom):
        names.append(node.module or '')
    if any(name.split('.')[0] == 'adapter' for name in names):
        raise SystemExit(3)
sys.exit(0)
'''
CAPABILITY = '''---
type: Capability
title: Layer boundary
namespace: DEMO
status: draft
---

# Layer boundary

## Requirements

- DEMO-R1: The core MUST avoid imports from adapter.
''' + DECLARATION + '''
  - Verify: `python3 check.py`
  - Inputs: `check.py` `src/**` `knowledge/project/decisions/layers.md`
  - Scenario boundary: A forbidden import fails the checker.
'''


def run(base: Optional[Path] = None, prepare: Optional[Callable[[Path], None]] = None,
        out: Optional[TextIO] = None, err: Optional[TextIO] = None) -> int:
    out = out or sys.stdout
    err = err or sys.stderr
    try:
        with tempfile.TemporaryDirectory(prefix='architecture-demo-', dir=base or _base()) as directory:
            session = Session(Path(directory) / 'repo', [])

            def configure(repo: Path) -> None:
                session.write('knowledge/capabilities/demo.md', CAPABILITY)
                session.write(ADR, '---\ntype: Decision\ntitle: Layers\nstatus: draft\n---\n'
                              '# Layers\n## Boundary\nCore avoids adapters.\n')
                session.write('check.py', CHECK)
                session.write('src/calc.py', 'value = 1\n')
                session.write('src/adapter.py', 'value = 2\n')
                session.tool('okf.py', 'reindex')
                if prepare:
                    prepare(repo)

            build(session, configure)
            out.write('Architecture assurance demo: using a throwaway repository.\n')
            for number, expected in enumerate(('UNVERIFIED', 'VERIFIED', 'STALE', 'FAILED', 'VERIFIED'), 1):
                if number in (2, 5):
                    if number == 5:
                        session.write('src/calc.py', 'value = 1\n')
                    session.lifecycle('assure', '--run', 'DEMO-R1')
                elif number == 3:
                    session.write('src/calc.py', 'import adapter\nvalue = 1\n')
                elif number == 4:
                    session.lifecycle('assure', '--run', 'DEMO-R1', ok=(1,))
                report = session.lifecycle('assure', '--json', ok=(0,) if expected == 'VERIFIED' else (1,))
                items = json.loads(report.stdout)['requirements']
                item = next((item for item in items if item['id'] == 'DEMO-R1'), None)
                if item is None or item['status'] != expected:
                    raise DemoFailure(f'step {number}: expected {expected}, observed {item}')
                governance = item.get('governed_by', {})
                if governance.get('basis') != 'declared' or governance.get('document') != ADR:
                    raise DemoFailure(f'step {number}: missing declared governance')
                if expected == 'STALE' and 'src/calc.py' not in item['reason']:
                    raise DemoFailure('stale evidence does not name the changed source')
                out.write(f'STEP {number}/5 {expected} - {item["reason"]}\n')
            out.write(LIMIT + ' Governance is declared provenance, not approval.\n')
        return 0
    except (DemoFailure, OSError, ValueError) as failure:
        err.write(f'assurance_architecture_demo: {failure}\n')
        return 1


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(143))
    return run()


if __name__ == '__main__':
    sys.exit(main())
