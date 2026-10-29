"""Input profile acceptance: specification-5.md R1-R7."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import disk_tmp  # noqa: E402,F401
import ledger  # noqa: E402
import assurance  # noqa: E402

# Handwritten read oracle, deliberately independent of the exporter's catalog.
COMMAND = ['python3', '-m', 'unittest', 'discover', '-s', '.ai/scripts/tests', '-p', 'test_run_tests.py']
READS = ['.ai/scripts/tests/test_run_tests.py', '.ai/scripts/tests/disk_tmp.py',
         '.ai/scripts/scratch.py', '.ai/scripts/run_tests.py']
EXCLUDE = '!knowledge/history/lifecycle/**'


def snapshot(root):
    return {str(p.relative_to(root)): (os.readlink(p) if p.is_symlink() else p.read_bytes())
            for p in root.rglob('*') if p.is_file() or p.is_symlink()}


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'repo with spaces'
        scripts = self.root / '.ai/scripts'
        scripts.mkdir(parents=True)
        for source in SCRIPTS.glob('*.py'):
            shutil.copy2(source, scripts / source.name)
        (scripts / 'tests').mkdir()
        for name in ('test_run_tests.py', 'disk_tmp.py'):
            shutil.copy2(SCRIPTS / 'tests' / name, scripts / 'tests' / name)
        self.env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'TMPDIR': self.temp.name,
                    'TMP': self.temp.name, 'TEMP': self.temp.name}
        for key in ('_AGENTIC_LIFECYCLE_RUN_ROOTS', 'REPO_ROOT', 'GIT_DIR', 'GIT_WORK_TREE'):
            self.env.pop(key, None)
        self.git('init', '-q')
        self.write('.agentic.json', '{"repository_kind":"framework"}')
        self.commit()

    def write(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)
        return path

    def process(self, argv, cwd=None):
        return subprocess.run(argv, cwd=cwd or self.root, env=self.env,
                              capture_output=True, text=True, timeout=120)

    def git(self, *args):
        result = self.process(['git', '-c', 'user.name=Test', '-c', 'user.email=test@test', *args])
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def commit(self):
        self.git('add', '-A')
        self.git('commit', '-qm', 'fixture')

    def export(self, argv=None, extra=(), cwd=None, json_output=True):
        flags = ['--json'] if json_output else []
        for value in extra:
            flags += ['--extra-input', value]
        return self.process([sys.executable, str(self.root / '.ai/scripts/assurance_inputs.py'),
                             *flags, '--', *(COMMAND if argv is None else argv)], cwd)

    def suggestion(self, **kwargs):
        result = self.export(**kwargs)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        value = json.loads(result.stdout)
        self.assertTrue(value['ok'])
        return value

    def refused(self, **kwargs):
        result = self.export(**kwargs)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        value = json.loads(result.stdout)
        self.assertFalse(value['ok'])
        self.assertTrue(value['reason'])
        self.assertIn('retain', value['remediation'].lower())
        for key in ('inputs', 'inputs_line', 'lifecycle_inputs_argv'):
            self.assertNotIn(key, value)
        return value

    def module(self):
        source = SCRIPTS / 'assurance_inputs.py'
        self.assertTrue(source.is_file(), 'input exporter is not implemented')
        spec = importlib.util.spec_from_file_location('input_export_under_test', source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def lc(self, *args, code=0):
        result = self.process([sys.executable, str(self.root / '.ai/scripts/lifecycle.py'), *args])
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return result.stdout

    def preflight(self):
        result = self.process(COMMAND)
        counts = re.findall(r'Ran (\d+) tests? in ', result.stdout + result.stderr)
        self.assertTrue(counts, 'no unittest execution count')
        self.assertGreater(int(counts[-1]), 0, 'empty discovery cannot verify the pilot')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return {name: hashlib.sha256((self.root / name).read_bytes()).hexdigest() for name in READS}

    def assert_inputs_unchanged(self, before):
        self.assertEqual(before, {name: hashlib.sha256((self.root / name).read_bytes()).hexdigest()
                                  for name in READS})


class ReadOnlyTests(Fixture):  # R1
    def test_success_and_refusal_neither_import_nor_execute_target(self):
        marker = self.root / 'executed'
        sentinel = f'from pathlib import Path\nPath({str(marker)!r}).write_text("bad")\nraise RuntimeError("imported")\n'
        for name in READS:
            self.write(name, sentinel)
        before = snapshot(self.root)
        self.suggestion()
        self.refused(argv=['python3', '-c', sentinel])
        self.assertEqual(snapshot(self.root), before)
        self.assertFalse(marker.exists())
        self.assertFalse(list(self.root.rglob('__pycache__')))


class ProfileTests(Fixture):  # R2
    def test_exact_command_and_root_only(self):
        self.suggestion()
        variants = [COMMAND + ['-v'], [sys.executable, *COMMAND[1:]],
                    COMMAND[:-1] + ['test_ledger.py'], ['python3', '.ai/scripts/tests/test_run_tests.py']]
        for argv in variants:
            with self.subTest(argv=argv):
                self.refused(argv=argv)
        self.refused(cwd=self.root / '.ai')

    def test_catalog_types_uniqueness_rationale_and_literal_identity(self):
        module = self.module()
        baseline = copy.deepcopy(module.PROFILES)
        for change in ('id', 'argv', 'inputs', 'rationale', 'cwd'):
            catalog = copy.deepcopy(baseline)
            catalog[0][change] = None
            with self.subTest(field=change), self.assertRaises(ValueError):
                module.suggest(self.root, COMMAND, profiles=catalog, cwd=self.root)
        for catalog in ([], [baseline[0], copy.deepcopy(baseline[0])]):
            with self.assertRaises(ValueError):
                module.suggest(self.root, COMMAND, profiles=catalog, cwd=self.root)
        catalog = copy.deepcopy(baseline)
        catalog[0]['rationale'] = {}
        with self.assertRaises(ValueError):
            module.suggest(self.root, COMMAND, profiles=catalog, cwd=self.root)


class DependencyCoverageTests(Fixture):  # R3
    def test_profile_covers_handwritten_four_file_read_oracle(self):
        value = self.suggestion()
        self.assertEqual(value['inputs'], READS)
        self.assertEqual(set(value['rationale']), set(READS))
        self.assertIn('subprocess', value['rationale'][READS[-1]].lower())
        self.assertIn('helper', value['rationale'][READS[1]].lower())
        self.refused(argv=['python3', READS[0]])


class RefusalTests(Fixture):  # R4
    def test_existing_ignored_or_directory_supplements_are_refused(self):
        self.write('secret.ini', 'known ignored data')
        self.write('.gitignore', 'secret.ini\n')
        self.write('assets/data.txt', 'directory input needs a pattern')
        for value in ('secret.ini', 'assets'):
            with self.subTest(value=value):
                self.refused(extra=(value,))

    def test_dash_prefixed_glob_cannot_be_exported_as_lifecycle_option(self):
        result = self.process([sys.executable, str(self.root / '.ai/scripts/assurance_inputs.py'),
                               '--json', '--extra-input=--other-option', '--', *COMMAND])
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertNotIn('lifecycle_inputs_argv', json.loads(result.stdout))

    def test_broad_and_invalid_requests_never_export_candidates(self):
        for argv in ([], ['python3', '-m', 'unittest', 'discover', '-s', '.ai/scripts/tests'],
                     *[['python3', '.ai/scripts/run_tests.py', '-j', str(n)] for n in (1, 8, 32)]):
            with self.subTest(argv=argv):
                self.refused(argv=argv)
        for value in ('', '!README.md', '/etc/passwd', '../x', 'x/../y', 'bad`path', 'bad\npath', 'bad\x00path'):
            with self.subTest(value=value):
                if '\x00' in value:
                    module = self.module()
                    with self.assertRaises(ValueError):
                        module.suggest(self.root, COMMAND, extra=(value,), cwd=self.root)
                else:
                    self.refused(extra=(value,))

    def test_missing_ignored_escaping_and_submodule_inputs(self):
        path = self.root / READS[0]
        original = path.read_bytes()
        path.unlink()
        self.refused()
        path.write_bytes(original)
        self.git('rm', '--cached', READS[0])
        self.write('.gitignore', READS[0] + '\n')
        self.refused()
        self.git('add', '-f', READS[0])
        outside = Path(self.temp.name) / 'outside.py'
        outside.write_bytes(original)
        path.unlink()
        path.symlink_to(outside)
        self.refused()
        path.unlink()
        path.write_bytes(original)
        (self.root / 'vendor').mkdir()
        self.git('update-index', '--add', '--cacheinfo', '160000,' + self.git('rev-parse', 'HEAD').strip() + ',vendor')
        self.refused(extra=('vendor',))

    def test_supplement_wildcard_prefix_cannot_escape(self):
        directory = Path(self.temp.name) / 'external'
        directory.mkdir()
        (directory / 'data.txt').write_text('external')
        (self.root / 'linked').symlink_to(directory, target_is_directory=True)
        self.refused(extra=('linked/**',))


class OutputTests(Fixture):  # R5
    def test_text_json_parser_and_argv_preserve_values(self):
        name = 'fixtures/space name.txt'
        self.write(name, 'data')
        value = self.suggestion(extra=(name,))
        self.assertEqual(value['schema_version'], 1)
        self.assertEqual(value['argv'], COMMAND)
        self.assertEqual(value['inputs'], READS + [name])
        self.assertEqual(value['lifecycle_inputs_argv'], ['--inputs', *READS, name])
        self.assertTrue(value['review_required'])
        self.assertTrue(value['limitations'])
        self.assertIn('runtime', ' '.join(value['limitations']).lower())
        raw = '- PILOT-R1: The runner MUST work.\n  - Verify: `' + ' '.join(COMMAND) + '`\n' + value['inputs_line'] + '\n'
        obligation = assurance.parse('PILOT-R1', 'capabilities/pilot.md', raw, root=self.root)
        self.assertIsNone(obligation.invalid)
        self.assertEqual(list(obligation.globs), value['inputs'])
        text = self.export(extra=(name,), json_output=False)
        self.assertEqual(text.returncode, 0, text.stderr)
        for item in (value['inputs_line'], json.dumps(value['lifecycle_inputs_argv']),
                     json.dumps(COMMAND), value['profile_id'], *value['rationale'].values(), *value['limitations']):
            self.assertIn(item, text.stdout)

    def test_syntax_errors_use_json_without_partial_candidate(self):
        script = str(self.root / '.ai/scripts/assurance_inputs.py')
        for flags in (['--json'], ['--json', '--bogus', '--', *COMMAND], ['--json', '--extra-input', '--', *COMMAND]):
            result = self.process([sys.executable, script, *flags])
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            value = json.loads(result.stdout)
            self.assertFalse(value['ok'])
            self.assertNotIn('inputs', value)


class CompatibilityTests(Fixture):  # R6
    def test_inference_and_declared_noncode_order_remain_explicit(self):
        self.assertEqual(ledger.default_inputs(COMMAND), ('python-tests', ['**']))
        module = self.module()
        catalog = copy.deepcopy(module.PROFILES)
        self.write('docs/contract.md', '# Required\n')
        catalog[0]['inputs'] += ['docs/**', '!docs/**']
        catalog[0]['rationale'].update({'docs/**': 'declared documentation', '!docs/**': 'excluded fixture'})
        value = module.suggest(self.root, COMMAND, extra=('docs/contract.md',), profiles=catalog, cwd=self.root)
        self.assertEqual(value['inputs'][-3:], ['docs/**', '!docs/**', 'docs/contract.md'])
        self.assertIn('docs/contract.md', ledger.input_paths(self.root, value['inputs']))
        self.assertNotIn(EXCLUDE, value['inputs'])
        guide = (SCRIPTS.parent / 'lifecycle.md').read_text()
        for phrase in ('assurance_inputs.py', 'python-runner-test', 'review', 'runtime'):
            self.assertIn(phrase, guide)


class EndToEndTests(Fixture):  # R7
    def test_framework_real_runner_reuse_and_each_input_invalidation(self):
        value = self.suggestion()
        before = self.preflight()
        self.lc('tier', 'L1', '--reason', 'framework profile fixture')
        self.lc('run', 'pilot', *value['lifecycle_inputs_argv'], '--', *COMMAND)
        self.assert_inputs_unchanged(before)
        self.assertIn('REUSE', self.lc('reuse', 'pilot'))
        path = self.root / '.ai/scripts/assurance.py'
        path.write_bytes(path.read_bytes() + b'\n# unrelated fixture edit\n')
        self.assertIn('REUSE', self.lc('reuse', 'pilot'))
        for name in READS:
            path = self.root / name
            original = path.read_bytes()
            path.write_bytes(original + b'\n# changed input\n')
            self.assertIn('RERUN', self.lc('reuse', 'pilot', code=1))
            path.write_bytes(original)
        self.assertFalse((self.root / 'knowledge').exists())
        import lifecycle
        state = lifecycle.load(self.root)
        entry = state['ledger'][-1]
        self.assertEqual((entry['argv'], entry['inputs'], entry['exit']), (COMMAND, READS, 0))

    def test_adopter_explicit_scope_freshness_and_identity(self):
        (self.root / '.agentic.json').unlink()
        self.lc('tier', 'L1', '--reason', 'adopter profile fixture')
        result = self.process([sys.executable, str(self.root / '.ai/scripts/okf.py'), 'init'])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.write('knowledge/project/sync-ignore', '*\n')
        value = self.suggestion()
        self.write('notes.txt', 'unrelated')
        prefix = '---\ntype: Capability\ntitle: Pilot\nnamespace: PILOT\nstatus: draft\n---\n# Pilot\n\n## Requirements\n\n- PILOT-R1: The runner MUST work.\n  - Verify: `' + ' '.join(COMMAND) + '`\n'
        capability = self.write('knowledge/capabilities/pilot.md', prefix + value['inputs_line'] + '\n')
        self.commit()
        before = self.preflight()
        self.lc('assure', '--run', 'PILOT-R1')
        self.assert_inputs_unchanged(before)

        def status():
            result = self.process([sys.executable, str(self.root / '.ai/scripts/lifecycle.py'), 'assure', '--json'])
            data = json.loads(result.stdout)
            return next(r for r in data['requirements'] if r['id'] == 'PILOT-R1')

        self.assertEqual(status()['status'], 'VERIFIED')
        self.write('notes.txt', 'still unrelated')
        self.assertEqual(status()['status'], 'VERIFIED')
        path = self.root / READS[-1]
        original = path.read_bytes()
        path.write_bytes(original + b'\n# declared input edit\n')
        self.assertEqual(status()['status'], 'STALE')
        path.write_bytes(original)
        value = self.suggestion(extra=('notes.txt',))
        capability.write_text(prefix + value['inputs_line'] + '\n')
        self.assertEqual(status()['status'], 'UNVERIFIED')
        records = list((self.root / 'knowledge/history/lifecycle').glob('*.json'))
        entries = [e for p in records for e in json.loads(p.read_text()).get('ledger', []) if e['label'] == 'req:PILOT-R1']
        self.assertEqual(entries[-1]['inputs'], READS + [EXCLUDE])


if __name__ == '__main__':
    unittest.main()
