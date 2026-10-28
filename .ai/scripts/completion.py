"""Consolidated completion diagnostics; only explicit evidence-backed metadata writes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shlex
import subprocess
import sys

import ledger
import project_context


def okf(root, *args):
    return subprocess.run([sys.executable, str(root / '.ai/scripts/okf.py'), *args],
                          cwd=root, capture_output=True, text=True, timeout=60)


def report(root, state, tests):
    import lifecycle
    data = {'schema_version': 1, 'repository_kind': project_context.kind(root),
            'blockers': [], 'checks': [], 'verified': False, 'actions': []}
    blockers = data['blockers']
    if state is None:
        blockers.append('no active lifecycle task')
        return data
    for stage in ('intent', 'plan', 'review'):
        if stage in lifecycle.REQUIRED[state['tier']] and not lifecycle.complete(state, stage):
            blockers.append(f'missing stage: {stage}')
    try:
        if state['tier'] != 'L0' and lifecycle.learning.closure(state) is None:
            blockers.append('missing retrospective closure')
    except ValueError as error:
        blockers.append(f'retrospective: {error}')
    if state.get('kind') in lifecycle.TEST_FIRST_KINDS and not lifecycle.redgreen_ok(state):
        blockers.append('missing red/green evidence')
    for name, check in [('audit', lambda: lifecycle.record_audit(root, state)),
                        ('merge', lambda: lifecycle.merge_problem(root, state)),
                        ('converge', lambda: lifecycle.converge_problem(root, state)),
                        ('scan', lambda: lifecycle.scan_problem(root, state)),
                        ('evidence', lambda: ledger.verify_problem(root, state.get('ledger', []), lifecycle.tree_hash(root)))]:
        try:
            value = check()
        except (ValueError, OSError, lifecycle.LifecycleError) as error:
            value = str(error)
        values = value if isinstance(value, list) else [value] if value else []
        blockers.extend(f'{name}: {item}' for item in values)
        data['checks'].append({'name': name, 'ok': not values})
    stages = state.get('stages', {})
    spec, plan = stages.get('intent', {}).get('ref'), stages.get('plan', {}).get('ref')
    if spec and plan:
        if not tests:
            blockers.append('traceability: supply --tests paths to check requirement citations')
        else:
            try:
                findings = lifecycle.blocking(lifecycle.trace(root, root / spec, root / plan, tests))
                blockers.extend(f'traceability: {item}' for item in findings)
            except (ValueError, OSError) as error:
                blockers.append(f'traceability: {error}')
    if data['repository_kind'] != 'framework' and (root / 'knowledge/index.md').is_file():
        affected = okf(root, 'affected', '--json')
        data['affected'] = json.loads(affected.stdout) if affected.returncode == 0 else {'error': affected.stderr}
        for command in (['sync-check', '--base', state.get('head') or 'HEAD', '--json'], ['records']):
            result = okf(root, *command)
            data['checks'].append({'name': command[0], 'ok': result.returncode == 0})
            if result.returncode:
                if command[0] == 'sync-check':
                    try:
                        violations = json.loads(result.stdout).get('violations', [])
                        messages = [f"knowledge {v['rule']}: {v['path']}" for v in violations]
                    except (ValueError, AttributeError, TypeError, KeyError):
                        messages = []
                    blockers.extend(messages or ['knowledge sync-check: ' +
                                                 (result.stderr or result.stdout or 'check failed').strip()])
                else:
                    blockers.append('knowledge records: ' + (result.stdout + result.stderr).strip())
    data['evidence'] = [e['label'] for e in ledger.current_entries(root, state.get('ledger', []), lifecycle.tree_hash(root))]
    data['ready_for_verify'] = not blockers
    data['verified'] = lifecycle.complete(state, 'verify') and not blockers
    return data


def apply_bindings(root, state, bindings):
    """Validate the whole request first; never choose a check or rewrite body prose."""
    import lifecycle
    prepared = []
    if bindings and project_context.kind(root) == 'framework':
        raise ValueError('framework completion does not write adopter knowledge')
    for binding in bindings:
        doc, separator, label = binding.partition('=')
        path = (root / doc).resolve()
        if not separator or not path.is_relative_to((root / 'knowledge').resolve()):
            raise ValueError('binding must be knowledge/PATH=EVIDENCE_LABEL')
        if doc not in lifecycle.changed_names(root):
            raise ValueError(f'{doc}: review and update the document before refreshing verification')
        entries = state.get('ledger', [])
        entry = next((e for e in reversed(entries) if e['label'] == label), None)
        reusable, reason = ledger.verdict(root, entries, label, lifecycle.tree_hash(root))
        if not reusable or entry is None or not entry.get('inputs'):
            raise ValueError(f'{doc}: explicit current input-scoped evidence required: {reason}')
        result = okf(root, 'show', doc, '--meta', '--json')
        if result.returncode:
            raise ValueError(result.stderr.strip())
        meta = json.loads(result.stdout)['meta']
        if meta.get('evidence') == 'validated-runtime':
            prior = meta.get('verified', {}).get('by', '')
            tokens = shlex.split(prior.removeprefix('process:'))
            original = tokens
            if (tokens != entry['argv'] and len(tokens) == 4 and tokens[2] == 'reuse'
                    and (root / tokens[1]).resolve() == (root / '.ai/scripts/lifecycle.py').resolve()):
                original = shlex.split(tokens[3])
            same = original == entry['argv']
            if not prior.startswith('process:') or not same:
                raise ValueError(f'{doc}: runtime claims need their original check binding; not refreshed')
        changed = lifecycle.changed_names(root)
        sources = []
        for source in meta.get('sources', []):
            if not isinstance(source, dict):
                raise ValueError(f'{doc}: invalid source metadata')
            resource = source.get('resource', '')
            if '://' in resource:
                continue
            target = (path.parent / resource).resolve()
            if target.is_relative_to(root):
                name = target.relative_to(root).as_posix()
                sources.extend(p for p in changed if p == name or p.startswith(name + '/'))
        covered = set(ledger.input_paths(root, entry['inputs']))
        if not sources or not set(sources) <= covered:
            raise ValueError(f'{doc}: evidence does not cover its changed mapped sources')
        command = shlex.join(entry['argv'])
        reusable, reason = ledger.verdict(root, entries, command, lifecycle.tree_hash(root))
        if not reusable:
            raise ValueError(f'{doc}: original command evidence is not current: {reason}')
        prepared.append((doc, label, command))
    for doc, label, command in prepared:
        result = okf(root, 'stamp', 'verified', doc, '--run', sys.executable,
                     str(root / '.ai/scripts/lifecycle.py'), 'reuse', command)
        if result.returncode:
            raise ValueError(result.stdout + result.stderr)
    if prepared:
        result = okf(root, 'log', 'Completion metadata refreshed from existing PASS evidence: ' +
                     '; '.join(f'{doc}: lifecycle.py reuse {command} -> PASS' for doc, _, command in prepared))
        if result.returncode:
            raise ValueError(result.stderr)
    return [f'verified metadata: {doc} from {label}' for doc, label, _ in prepared]


def finish(args):
    import lifecycle
    root, state = lifecycle.repo_root(), lifecycle.load(lifecycle.repo_root())
    actions = []
    if args.apply and state is not None:
        actions = apply_bindings(root, state, args.bind)
    data = report(root, state, args.tests)
    if args.apply and data.get('ready_for_verify') and not data['verified']:
        note = ledger.note(ledger.current_entries(root, state.get('ledger', []), lifecycle.tree_hash(root)))
        # This invokes the existing verification gates, not product tests or a new reviewer.
        from contextlib import redirect_stdout
        import io
        with redirect_stdout(io.StringIO()):
            lifecycle.cmd_stage(argparse.Namespace(stage='verify', ref=None, note=note, approved_by=None))
        data = report(root, lifecycle.load(root), args.tests)
        actions.append('recorded Verify from existing evidence')
    data['actions'] = actions
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print('completion: ' + ('verified' if data['verified'] else 'ready for Verify' if not data['blockers'] else 'blocked'))
        for blocker in data['blockers']:
            print('- ' + blocker)
        for action in actions:
            print('+ ' + action)
    return 1 if data['blockers'] else 0
