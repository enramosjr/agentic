"""Explicit snapshot treatment of successfully closed producer administration only."""
import json
from pathlib import Path

import review_guard


def closed_coordination_snapshot(root: Path, files: dict) -> dict:
    """Keep every product/receipt/capture byte; allow only closed owner administration.

    Callers opt in only for protected mutator refusal/no-op checks. Readers retain
    their complete raw filesystem snapshots. New borrower/launch/capture files remain
    visible, so a refused operation cannot hide command execution or approval changes.
    """
    namespace = review_guard.directory(root)
    policy = review_guard.read(root)
    if policy['writers']:
        raise AssertionError('protected invocation left live or unresolved owners')
    result = {}
    for name, value in files.items():
        path = root / name
        try:
            relative = path.relative_to(namespace)
        except ValueError:
            result[name] = value
            continue
        if relative.as_posix() == 'journal.json':
            continue  # Every field, including policy/history, is compared below.
        if relative.as_posix() == 'guard.lock':
            if path.stat().st_size:
                raise AssertionError('unexpected guard lock contents')
            continue
        if len(relative.parts) == 3 and relative.parts[0] == 'producers' and relative.name == 'owner.json':
            owner = review_guard.document(path)
            if (owner.get('phase') != 'closed' or owner.get('root') != str(root.resolve())
                    or not review_guard.borrowers_quiet(path.parent)):
                raise AssertionError('protected invocation did not close every producer grant')
            continue
        result[name] = value
    result['<review-policy-and-history>'] = json.dumps(policy, sort_keys=True)
    return result
