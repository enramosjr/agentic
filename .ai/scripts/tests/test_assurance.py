"""Requirement assurance status, increment 1 (docs/assurance/specification.md R1-R9)."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import disk_tmp  # noqa: F401,E402
import ledger  # noqa: E402
import scratch  # noqa: E402

CAP = 'knowledge/capabilities/calc.md'
RECORDS = 'knowledge/history/lifecycle'
EXCLUDE = '!' + RECORDS + '/**'
SCOPED = ('- CALC-R1: The calculator MUST add.\n'
          '  - Verify: `python3 check.py`\n'
          '  - Inputs: `check.py` `src/**`\n'
          '  - Scenario add: 1 + 1 is 2.\n')
CHECK = ('import pathlib, sys\n'
         'print("SECRET-OUTPUT")\n'
         'sys.exit(0 if pathlib.Path("src/calc.py").read_text().startswith("ok") else 3)\n')


class Case(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'repo'
        self.scripts = self.root / '.ai/scripts'
        self.scripts.mkdir(parents=True)
        for source in SCRIPTS.glob('*.py'):
            shutil.copy2(source, self.scripts / source.name)
        self.env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}
        self.env.pop('_AGENTIC_LIFECYCLE_RUN_ROOTS', None)
        self.git('init', '-q')
        self.cli('okf.py', 'init')
        (self.root / 'knowledge/project/sync-ignore').write_text('*\n')
        self.write('check.py', CHECK)
        self.write('src/calc.py', 'ok\n')
        self.write('notes.txt', 'unrelated\n')
        self.capability(SCOPED)
        self.commit('fixture')

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def capability(self, requirements, namespace='CALC'):
        header = f'---\ntype: Capability\ntitle: Calc\nnamespace: {namespace}\nstatus: draft\n---\n\n'
        self.write(CAP, header + '# Calc\n\n## Requirements\n\n' + requirements + '\n## Notes\n\nProse.\n')
        self.cli('okf.py', 'reindex')

    def git(self, *args):
        return subprocess.run(['git', '-c', 'user.name=Test', '-c', 'user.email=t@t', *args],
                              cwd=self.root, capture_output=True, text=True, check=True).stdout

    def commit(self, message):
        self.git('add', '-A')
        self.git('commit', '-qm', message)

    def cli(self, script, *args, code=0):
        result = subprocess.run([sys.executable, str(self.scripts / script), *args], cwd=self.root,
                                env=self.env, capture_output=True, text=True, timeout=120)
        if code is not None:
            self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return result

    def lc(self, *args, code=0):
        return self.cli('lifecycle.py', *args, code=code)

    def task(self, new=False):
        self.lc('tier', 'L1', '--reason', 'assurance fixture', *(['--new'] if new else []))

    def report(self, *args, code=None):
        result = self.lc('assure', '--json', *args, code=code)
        return json.loads(result.stdout), result.returncode

    def status(self, rid, *args):
        data, _ = self.report(*args)
        return next(r for r in data['requirements'] if r['id'] == rid)

    def records(self):
        found = []
        for path in sorted((self.root / RECORDS).glob('*.json')):
            found.append(json.loads(path.read_text()))
        return found

    def req_entries(self):
        return [e for record in self.records() for e in record.get('ledger') or []
                if str(e.get('label', '')).startswith('req:')]


class ObligationSyntaxTests(Case):  # R1
    def test_valid_and_malformed_obligations(self):
        self.capability(
            SCOPED
            + '- CALC-R2: The calculator MUST look right.\n  - Verify: manual - needs a UX review\n'
            + '- CALC-R3: Duplicate verify MUST fail.\n  - Verify: `python3 check.py`\n  - Verify: `python3 check.py`\n'
            + '- CALC-R4: Late verify MUST fail.\n  - Scenario s: x.\n  - Verify: `python3 check.py`\n'
            + '- CALC-R5: Inputs alone MUST fail.\n  - Inputs: `src/**`\n'
            + '- CALC-R6: Empty command MUST fail.\n  - Verify: ``\n'
            + '- CALC-R7: Absolute glob MUST fail.\n  - Verify: `python3 check.py`\n  - Inputs: `/etc/passwd`\n'
            + '- CALC-R8: Parent glob MUST fail.\n  - Verify: `python3 check.py`\n  - Inputs: `../x`\n'
            + '- CALC-R9: Manual without reason MUST fail.\n  - Verify: manual\n'
            + '- CALC-R10: Duplicate inputs MUST fail.\n  - Verify: `python3 check.py`\n  - Inputs: `a`\n  - Inputs: `b`\n'
            + '- CALC-R11: Prose verify MUST fail.\n  - Verify: run the tests\n')
        data, code = self.report()
        statuses = {r['id']: r['status'] for r in data['requirements']}
        self.assertEqual(statuses['CALC-R1'], 'UNVERIFIED')
        self.assertEqual(statuses['CALC-R2'], 'MANUAL')
        for rid in ('CALC-R3', 'CALC-R4', 'CALC-R5', 'CALC-R6', 'CALC-R7', 'CALC-R8', 'CALC-R9', 'CALC-R10', 'CALC-R11'):
            self.assertEqual(statuses[rid], 'INVALID', rid)
        self.assertEqual(code, 1)
        reasons = {r['id']: r['reason'] for r in data['requirements']}
        self.assertIn('scenario', reasons['CALC-R4'])
        self.assertIn('Inputs', reasons['CALC-R5'])
        self.assertIn('needs a UX review', reasons['CALC-R2'])


class CompatibilityTests(Case):  # R2
    def test_obligation_free_and_prose_capabilities_stay_green(self):
        self.capability('- CALC-R1: The calculator MUST add.\n  - Scenario add: 1 + 1 is 2.\n')
        self.write('knowledge/capabilities/prose.md', '---\ntype: Capability\ntitle: Prose\nstatus: draft\n---\n\n# Prose\n\nNo IDs.\n')
        self.cli('okf.py', 'reindex')
        data, code = self.report()
        self.assertEqual(code, 0)
        self.assertEqual([(r['id'], r['status']) for r in data['requirements']], [('CALC-R1', 'UNDECLARED')])
        self.assertEqual(self.report('--strict')[1], 1)

    def test_obligation_lines_keep_validate_clean(self):
        self.cli('okf.py', 'validate')

    def test_repository_without_bundle_reports_nothing(self):
        shutil.rmtree(self.root / 'knowledge')
        data, code = self.report()
        self.assertEqual((data['requirements'], code), ([], 0))


class AssureRunTests(Case):  # R3
    def test_run_records_req_entry_with_declared_inputs(self):
        self.task()
        result = self.lc('assure', '--run')
        self.assertIn('req:CALC-R1', result.stdout)
        [entry] = self.req_entries()
        self.assertEqual(entry['label'], 'req:CALC-R1')
        self.assertEqual(entry['argv'], ['python3', 'check.py'])
        self.assertEqual(entry['inputs'], ['check.py', 'src/**', EXCLUDE])
        self.assertEqual(sorted(entry['input_files']), ['check.py', 'src/calc.py'])
        self.assertTrue(entry['runtime_sha256'])
        self.assertEqual(entry['exit'], 0)
        self.assertEqual(ledger.audit([entry]), [])

    def test_run_refuses_without_active_task(self):
        self.capability('- CALC-R1: Mark MUST be written.\n  - Verify: `python3 mark.py`\n')
        self.write('mark.py', 'open("marker", "w").close()\n')
        result = self.lc('assure', '--run', code=1)
        self.assertIn('nothing was run', result.stderr)
        self.assertFalse((self.root / 'marker').exists())

    def test_run_refuses_inside_lifecycle_run(self):
        self.task()
        outer = self.lc('run', 'outer', '--', sys.executable, '.ai/scripts/lifecycle.py', 'assure', '--run', code=None)
        self.assertNotEqual(outer.returncode, 0)
        self.assertEqual(self.req_entries(), [])

    def test_run_refuses_unknown_id(self):
        self.task()
        result = self.lc('assure', '--run', 'CALC-R99', code=1)
        self.assertIn('CALC-R99', result.stderr)
        self.assertEqual(self.req_entries(), [])


class StatusTests(Case):  # R4
    def setUp(self):
        super().setUp()
        self.task()
        self.lc('assure', '--run')

    def test_fresh_evidence_is_verified(self):
        self.assertEqual(self.status('CALC-R1')['status'], 'VERIFIED')

    def test_input_edit_is_stale_and_names_file(self):
        self.write('src/calc.py', 'ok, edited\n')
        item = self.status('CALC-R1')
        self.assertEqual(item['status'], 'STALE')
        self.assertIn('src/calc.py', item['reason'])

    def test_unrelated_edit_stays_verified(self):
        self.write('notes.txt', 'changed\n')
        self.commit('unrelated')
        self.assertEqual(self.status('CALC-R1')['status'], 'VERIFIED')

    def test_deleted_input_is_stale(self):
        (self.root / 'src/calc.py').unlink()
        item = self.status('CALC-R1')
        self.assertEqual(item['status'], 'STALE')
        self.assertIn('src/calc.py', item['reason'])

    def test_changed_command_is_unverified(self):
        self.capability(SCOPED.replace('`python3 check.py`', '`python3 check.py --strict`'))
        item = self.status('CALC-R1')
        self.assertEqual(item['status'], 'UNVERIFIED')
        self.assertIn('different command', item['reason'])

    def test_newer_failure_wins(self):
        self.write('src/calc.py', 'broken\n')
        self.lc('assure', '--run', code=1)
        self.assertEqual(self.status('CALC-R1')['status'], 'FAILED')

    def test_evidence_from_earlier_committed_record(self):
        first = sorted((self.root / RECORDS).glob('*.json'))[0].name
        self.commit('task one')
        self.task(new=True)
        item = self.status('CALC-R1')
        self.assertEqual(item['status'], 'VERIFIED')
        self.assertEqual(item['evidence']['record'], first)


class RuntimeTests(Case):  # R4 environment reason
    def test_changed_executable_is_stale(self):
        bin_dir = Path(self.temp.name) / 'bin'
        bin_dir.mkdir()
        tool = bin_dir / 'calc-check'
        tool.write_text('#!/bin/sh\nexit 0\n')
        tool.chmod(0o755)
        self.env['PATH'] = f"{bin_dir}{os.pathsep}{self.env.get('PATH', '')}"
        self.capability('- CALC-R1: Tool MUST pass.\n  - Verify: `calc-check`\n  - Inputs: `src/**`\n')
        self.task()
        self.lc('assure', '--run')
        self.assertEqual(self.status('CALC-R1')['status'], 'VERIFIED')
        tool.write_text('#!/bin/sh\n# upgraded\nexit 0\n')
        item = self.status('CALC-R1')
        self.assertEqual(item['status'], 'STALE')
        self.assertIn('runtime', item['reason'])


class IntegrityTests(Case):  # R5
    def forged(self, **extra):
        globs = ['check.py', 'src/**', EXCLUDE]
        entry = {'label': 'req:CALC-R1', 'argv': ['python3', 'check.py'], 'exit': 0, 'tree': 'x',
                 'head': self.git('rev-parse', 'HEAD').strip(), 'duration': 0.1, 'at': '2026-10-27T00:00:00Z',
                 'inputs': globs, 'inputs_sha256': ledger.inputs_digest(self.root, globs),
                 'input_files': ledger.inputs_snapshot(self.root, globs), **extra}
        return entry

    def test_invalid_and_output_bearing_records_contribute_nothing(self):
        self.write(f'{RECORDS}/bad.json', '{not json')
        self.write(f'{RECORDS}/forged.json', json.dumps({'ledger': [self.forged(output='SECRET-OUTPUT')]}))
        data, _ = self.report()
        item = next(r for r in data['requirements'] if r['id'] == 'CALC-R1')
        self.assertEqual(item['status'], 'UNVERIFIED')
        text = ' '.join(data['diagnostics'])
        self.assertIn('bad.json', text)
        self.assertIn('forged.json', text)
        self.assertNotIn('SECRET-OUTPUT', json.dumps(data))

    def test_schema_valid_hand_written_record_is_not_detected(self):
        """Documented limit: audit detects drift and schema violations, not a well-formed forgery."""
        self.write(f'{RECORDS}/forged.json', json.dumps({'ledger': [self.forged()]}))
        self.assertEqual(self.status('CALC-R1')['status'], 'VERIFIED')


class UnscopedTests(Case):  # R6
    def setUp(self):
        super().setUp()
        self.capability('- CALC-R1: The calculator MUST add.\n  - Verify: `python3 check.py`\n')
        self.commit('unscoped')
        self.task()
        self.lc('assure', '--run')

    def test_identical_tree_is_verified(self):
        self.assertEqual(self.status('CALC-R1')['status'], 'VERIFIED')

    def test_any_commit_makes_it_stale(self):
        self.write('notes.txt', 'changed\n')
        self.commit('unrelated')
        item = self.status('CALC-R1')
        self.assertEqual(item['status'], 'STALE')
        self.assertIn('whole tree', item['reason'])

    def test_uncommitted_source_edit_makes_it_stale(self):
        self.write('notes.txt', 'changed\n')
        self.assertEqual(self.status('CALC-R1')['status'], 'STALE')


class ChangedTests(Case):  # R7
    def setUp(self):
        super().setUp()
        self.capability(SCOPED
                        + '- CALC-R2: Docs MUST render.\n  - Verify: `python3 check.py`\n  - Inputs: `docs/**`\n'
                        + '- CALC-R3: Whole MUST pass.\n  - Verify: `python3 check.py`\n'
                        + '- CALC-R4: Core MUST pass.\n  - Verify: `python3 check.py`\n  - Inputs: `src/**` `!src/gen/**`\n'
                        + '- CALC-R5: Manual MUST be reviewed.\n  - Verify: manual - human review\n')
        self.commit('changed fixture')
        self.task()

    def listed(self, *args):
        data, code = self.report('--changed', '--base', 'HEAD', *args)
        return {r['id']: r for r in data['requirements']}, code

    def test_matched_unmatched_and_unscoped(self):
        before = self.req_entries()
        self.write('src/gen/out.py', 'generated\n')
        listed, _ = self.listed()
        self.assertEqual(sorted(listed), ['CALC-R1', 'CALC-R3', 'CALC-R5'])
        self.assertIn('src/gen/out.py', listed['CALC-R1']['reason'])
        self.assertIn('whole tree', listed['CALC-R3']['reason'])
        self.assertIn('whole tree', listed['CALC-R5']['reason'])
        self.write('src/calc.py', 'ok, edited\n')
        listed, _ = self.listed()
        self.assertEqual(sorted(listed), ['CALC-R1', 'CALC-R3', 'CALC-R4', 'CALC-R5'])
        self.assertEqual(self.req_entries(), before)

    def test_bad_base_is_refused(self):
        self.lc('assure', '--changed', '--base', 'no-such-rev', code=2)


class ReportFormatTests(Case):  # R8
    def test_text_and_json_fields_without_output(self):
        self.task()
        run = self.lc('assure', '--run')
        self.assertNotIn('SECRET-OUTPUT', run.stdout)
        text = self.lc('assure').stdout
        line = next(ln for ln in text.splitlines() if 'CALC-R1' in ln)
        head = self.git('rev-parse', 'HEAD').strip()[:7]
        for field in ('VERIFIED', 'calc.md', f'head={head}', 'at=20'):
            self.assertIn(field, line)
        data, _ = self.report()
        self.assertEqual(data['schema_version'], 1)
        [item] = data['requirements']
        self.assertEqual(set(item), {'id', 'capability', 'status', 'basis', 'evidence', 'reason'})
        self.assertEqual(item['capability'], CAP)
        self.assertEqual(item['basis'], 'mechanical')
        self.assertEqual(set(item['evidence']), {'record', 'head', 'at', 'exit'})
        for output in (text, json.dumps(data)) + tuple((self.root / RECORDS).glob('*.json')):
            self.assertNotIn('SECRET-OUTPUT', output if isinstance(output, str) else output.read_text())

    def test_basis_for_manual_and_missing_evidence(self):
        self.capability(SCOPED + '- CALC-R2: Looks MUST be right.\n  - Verify: manual - review\n')
        data, _ = self.report()
        basis = {r['id']: (r['basis'], r['evidence']) for r in data['requirements']}
        self.assertEqual(basis, {'CALC-R1': ('none', None), 'CALC-R2': ('declared', None)})


class ExitCodeTests(Case):  # R9
    def snapshot(self):
        files = {}
        for base in (self.root, scratch.location(self.root)):
            for path in base.rglob('*'):
                if path.is_file() and '.git' not in path.relative_to(self.root if base == self.root else base).parts[:1]:
                    files[str(path)] = path.read_bytes()
        return files

    def test_exit_codes_and_read_only_report(self):
        self.capability(SCOPED + '- CALC-R2: Looks MUST be right.\n  - Verify: manual - review\n'
                        + '- CALC-R3: Mark MUST stay unwritten.\n  - Verify: `python3 mark.py`\n  - Inputs: `mark.py`\n')
        self.write('mark.py', 'open("marker", "w").close()\n')
        self.task()
        self.assertEqual(self.report()[1], 1)  # UNVERIFIED
        self.lc('assure', '--run', 'CALC-R1', 'CALC-R3')
        (self.root / 'marker').unlink()
        before = self.snapshot()
        data, code = self.report()
        self.assertEqual(code, 0, data)  # VERIFIED plus MANUAL
        self.lc('assure')
        self.lc('assure', '--changed', '--base', 'HEAD')
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.root / 'marker').exists())
        self.write('src/calc.py', 'ok, edited\n')
        self.assertEqual(self.report()[1], 1)  # STALE
        self.lc('assure', '--changed', '--base', 'HEAD', code=1)

    def test_run_with_report_flags_is_refused(self):
        self.capability(SCOPED)
        self.task()
        before = self.snapshot()
        for flags in (('--changed',), ('--base', 'HEAD'), ('--strict',), ('--json',)):
            self.lc('assure', '--run', *flags, code=2)
        self.assertEqual(self.snapshot(), before)  # nothing ran, nothing recorded

    def test_strict_counts_undeclared(self):
        self.capability('- CALC-R1: The calculator MUST add.\n')
        self.assertEqual(self.report()[1], 0)
        self.assertEqual(self.report('--strict')[1], 1)

    def test_invalid_fails(self):
        self.capability('- CALC-R1: The calculator MUST add.\n  - Inputs: `src/**`\n')
        self.assertEqual(self.report()[1], 1)


if __name__ == '__main__':
    unittest.main()
