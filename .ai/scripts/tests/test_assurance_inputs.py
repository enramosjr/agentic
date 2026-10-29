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


# Architecture profile: specification-5b.md R1-R6. These declarations are
# handwritten independently of the exporter; directory copies are not imports.
ARCH_COMMAND = ['python3', '.ai/scripts/tests/test_assurance_architecture.py', 'CompatibilityTests']
ARCH_TESTS = ['.ai/scripts/tests/' + name for name in
              ('test_assurance_architecture.py', 'test_assurance.py', 'test_assurance_gate.py', 'disk_tmp.py')]
ARCH_GUIDE = '.ai/lifecycle.md'
ARCH_INPUTS = ['.ai/scripts/**', '!.ai/scripts/tests/**', *ARCH_TESTS, ARCH_GUIDE]


class ArchitectureFixture(Fixture):
    def setUp(self):
        super().setUp()
        for name in ARCH_TESTS:
            shutil.copy2(SCRIPTS.parent.parent / name, self.root / name)
        shutil.copy2(SCRIPTS.parent / 'lifecycle.md', self.root / ARCH_GUIDE)
        self.commit()

    def export(self, argv=None, **kwargs):
        return super().export(argv=ARCH_COMMAND if argv is None else argv, **kwargs)

    def oracle(self):
        # Match the inspected all-top-level-script copies, not profile inputs.
        names = [str(p.relative_to(self.root)) for p in (self.root / '.ai/scripts').glob('*.py')]
        return {name: (self.root / name).read_bytes() for name in [*names, *ARCH_TESTS, ARCH_GUIDE]}

    def preflight(self):
        before = self.oracle()
        result = self.process(ARCH_COMMAND)
        output = result.stdout + result.stderr
        counts = re.findall(r'Ran (\d+) tests? in ', output)
        self.assertTrue(counts, 'architecture execution count missing: ' + output)
        self.assertEqual(int(counts[-1]), 2, 'architecture execution count must be two')
        self.assertEqual(result.returncode, 0, output)
        self.assertEqual(self.oracle(), before, 'architecture inputs changed during execution')
        return before

    def assert_inputs_unchanged(self, before):
        self.assertEqual(self.oracle(), before, 'architecture inputs changed during recording')

    def edit_and_restore(self, name, check):
        path = self.root / name
        original = path.read_bytes() if path.exists() else None
        self.write(name, (original.decode() if original is not None else '') + '\n# freshness edit\n')
        try:
            check()
        finally:
            if original is None:
                path.unlink()
            else:
                path.write_bytes(original)


class ArchitectureProfileTests(ArchitectureFixture):  # R1
    def test_exact_registration_and_original_profile(self):
        value = self.suggestion()
        self.assertEqual(value['profile_id'], 'python-architecture-compatibility')
        self.assertEqual(value['argv'], ARCH_COMMAND)
        old = self.suggestion(argv=COMMAND)
        self.assertEqual((old['profile_id'], old['inputs']), ('python-runner-test', READS))
        variants = [ARCH_COMMAND[:2], ARCH_COMMAND + ['-v'], ARCH_COMMAND[:2] + ['DeclarationTests'],
                    ARCH_COMMAND[:2] + ['CompatibilityTests.test_ungoverned_public_shape_stays_unchanged'],
                    [sys.executable, *ARCH_COMMAND[1:]],
                    ['python3', '-m', 'unittest', 'discover', '-s', '.ai/scripts/tests',
                     '-p', 'test_assurance_architecture.py']]
        for argv in variants:
            result = self.export(argv=argv)
            self.assertEqual(result.returncode, 2, 'unregistered argv exported: ' + repr(argv))
            self.assertNotIn('inputs', json.loads(result.stdout))
        self.refused(cwd=self.root / '.ai')


class ArchitectureDependencyTests(ArchitectureFixture):  # R2
    def test_order_scope_and_independent_read_oracle(self):
        value = self.suggestion()
        self.assertEqual(value['inputs'], ARCH_INPUTS)
        self.assertEqual(set(value['rationale']), set(ARCH_INPUTS))
        for reason in value['rationale'].values():
            self.assertTrue(reason.strip())
        self.write('.ai/scripts/future.py', '# copied in future\n')
        self.write('.ai/scripts/assets/data.txt', 'conservative descendant')
        self.write('.ai/scripts/tests/test_merge.py', '# unrelated\n')
        selected = set(ledger.input_paths(self.root, value['inputs']))
        self.assertTrue(set(self.oracle()).issubset(selected))
        self.assertIn('.ai/scripts/future.py', selected)
        self.assertIn('.ai/scripts/assets/data.txt', selected)
        self.assertNotIn('.ai/scripts/tests/test_merge.py', selected)
        self.assertNotIn(READS[0], selected)
        for name, phrases in {
                ARCH_TESTS[0]: ('from test_assurance import', 'from test_assurance_gate import',
                                "SCRIPTS.glob('*.py')", "SCRIPTS.parent / 'lifecycle.md'",
                                "['UNVERIFIED', 'VERIFIED', 'STALE', 'FAILED', 'VERIFIED']"),
                ARCH_TESTS[1]: ("SCRIPTS.glob('*.py')", 'import disk_tmp'),
                '.ai/scripts/assurance_demo.py': ('HERE.glob("*.py")',),
                '.ai/scripts/assurance_architecture_demo.py': ('from assurance_demo import',),
        }.items():
            source = (self.root / name).read_text()
            for phrase in phrases:
                self.assertIn(phrase, source, 'review architecture read oracle: ' + name)


class ArchitectureExportTests(ArchitectureFixture):  # R3
    def test_readonly_formats_supplements_and_parser(self):
        marker = self.root / 'executed'
        for name in [*ARCH_TESTS[:-1], '.ai/scripts/assurance_architecture_demo.py']:
            self.write(name, f'from pathlib import Path\nPath({str(marker)!r}).touch()\nraise RuntimeError("executed")\n')
        self.write('space file.txt', 'supplement')
        before = snapshot(self.root)
        value = self.suggestion(extra=('space file.txt',))
        text = self.export(extra=('space file.txt',), json_output=False)
        self.assertEqual(text.returncode, 0, text.stderr)
        self.assertEqual(value['inputs'], ARCH_INPUTS + ['space file.txt'])
        self.assertEqual(value['lifecycle_inputs_argv'], ['--inputs', *value['inputs']])
        for item in (value['profile_id'], value['inputs_line'], json.dumps(ARCH_COMMAND),
                     json.dumps(value['lifecycle_inputs_argv']), *value['rationale'].values(), *value['limitations']):
            self.assertIn(item, text.stdout)
        self.assertTrue(value['review_required'])
        self.assertIn('runtime', ' '.join(value['limitations']).lower())
        raw = '- ARCH-R1: The check MUST work.\n  - Verify: `' + ' '.join(ARCH_COMMAND) + '`\n' + value['inputs_line'] + '\n'
        parsed = assurance.parse('ARCH-R1', 'capabilities/arch.md', raw, root=self.root)
        self.assertIsNone(parsed.invalid)
        self.assertEqual(list(parsed.globs), value['inputs'])
        self.refused(argv=ARCH_COMMAND[:2])
        self.assertEqual(snapshot(self.root), before)
        self.assertFalse(marker.exists())

    def test_required_literals_and_unsafe_inputs_refuse(self):
        for name in [*ARCH_TESTS, ARCH_GUIDE]:
            path = self.root / name
            original = path.read_bytes()
            path.unlink()
            self.refused()
            path.write_bytes(original)
        name = ARCH_GUIDE
        self.git('rm', '--cached', name)
        self.write('.gitignore', name + '\n')
        self.refused()
        self.git('add', '-f', name)
        path = self.root / name
        original = path.read_bytes()
        outside = Path(self.temp.name) / 'outside.md'
        outside.write_bytes(original)
        path.unlink()
        path.symlink_to(outside)
        self.refused()
        path.unlink()
        path.write_bytes(original)
        for extra in ('!README.md', '../x', '/etc/passwd', '', 'x`bad', '--other-option'):
            self.refused(extra=(extra,))


class ArchitectureCompatibilityTests(ArchitectureFixture):  # R4
    def test_existing_contracts_and_guide(self):
        self.assertEqual(self.suggestion(argv=COMMAND)['inputs'], READS)
        self.assertEqual(ledger.default_inputs(COMMAND), ('python-tests', ['**']))
        self.assertIsNone(ledger.default_inputs(ARCH_COMMAND))
        for argv in (['python3', '-m', 'unittest', 'discover', '-s', '.ai/scripts/tests'],
                     *[['python3', '.ai/scripts/run_tests.py', '-j', str(n)] for n in (1, 8, 32)]):
            self.refused(argv=argv)
        self.assertNotIn(EXCLUDE, self.suggestion()['inputs'])
        guide = (self.root / ARCH_GUIDE).read_text()
        for phrase in ('python-architecture-compatibility', ' '.join(ARCH_COMMAND),
                       'copied', 'conservative', 'explicit', 'runtime', 'python-runner-test'):
            self.assertIn(phrase, guide)


class ArchitectureFrameworkEndToEndTests(ArchitectureFixture):  # R5
    def record(self):
        value = self.suggestion()
        before = self.preflight()
        self.lc('tier', 'L1', '--reason', 'architecture framework fixture')
        self.lc('run', 'architecture', *value['lifecycle_inputs_argv'], '--', *ARCH_COMMAND)
        self.assert_inputs_unchanged(before)
        import lifecycle
        entry = lifecycle.load(self.root)['ledger'][-1]
        self.assertEqual((entry['argv'], entry['inputs'], entry['exit']),
                         (ARCH_COMMAND, value['inputs'], 0))
        self.assertIn('REUSE', self.lc('reuse', 'architecture'))

    def test_each_input_and_addition_invalidates(self):
        self.record()
        self.write('.ai/scripts/tests/unrelated.py', '# unrelated\n')
        self.assertIn('REUSE', self.lc('reuse', 'architecture'))
        for name in [ARCH_GUIDE, *ARCH_TESTS, '.ai/scripts/assurance.py', '.ai/scripts/new_copy.py']:
            with self.subTest(name=name):
                def stale():
                    result = self.process([sys.executable, '.ai/scripts/lifecycle.py', 'reuse', 'architecture'])
                    self.assertEqual(result.returncode, 1, 'missing freshness invalidation: ' + name)
                    self.assertIn('RERUN', result.stdout)
                self.edit_and_restore(name, stale)
        self.assertFalse((self.root / 'knowledge').exists())


class ArchitectureAdopterEndToEndTests(ArchitectureFixture):  # R6
    def test_explicit_adoption_freshness_and_identity(self):
        (self.root / '.agentic.json').unlink()
        self.lc('tier', 'L1', '--reason', 'architecture adopter fixture')
        result = self.process([sys.executable, '.ai/scripts/okf.py', 'init'])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.write('knowledge/project/sync-ignore', '*\n')
        value = self.suggestion()
        prefix = ('---\ntype: Capability\ntitle: Architecture\nnamespace: ARCH\nstatus: draft\n---\n'
                  '# Architecture\n\n## Requirements\n\n- ARCH-R1: The check MUST work.\n'
                  '  - Verify: `' + ' '.join(ARCH_COMMAND) + '`\n')
        capability = self.write('knowledge/capabilities/arch.md', prefix + value['inputs_line'] + '\n')
        self.commit()
        before = self.preflight()
        self.lc('assure', '--run', 'ARCH-R1')
        self.assert_inputs_unchanged(before)

        def status():
            result = self.process([sys.executable, '.ai/scripts/lifecycle.py', 'assure', '--json'])
            data = json.loads(result.stdout)
            return next(r['status'] for r in data['requirements'] if r['id'] == 'ARCH-R1')

        self.assertEqual(status(), 'VERIFIED')
        self.write('.ai/scripts/tests/unrelated.py', '# excluded\n')
        self.assertEqual(status(), 'VERIFIED')
        for name in [ARCH_GUIDE, *ARCH_TESTS, '.ai/scripts/assurance.py', '.ai/scripts/new_copy.py']:
            with self.subTest(name=name):
                self.edit_and_restore(name, lambda: self.assertEqual(status(), 'STALE'))
        self.assertEqual(status(), 'VERIFIED')
        reordered = [*value['inputs'][:-2], value['inputs'][-1], value['inputs'][-2]]
        capability.write_text(prefix + '  - Inputs: ' + ' '.join('`' + p + '`' for p in reordered) + '\n')
        self.assertEqual(status(), 'UNVERIFIED')
        entries = [e for p in (self.root / 'knowledge/history/lifecycle').glob('*.json')
                   for e in json.loads(p.read_text()).get('ledger', []) if e['label'] == 'req:ARCH-R1']
        self.assertEqual(entries[-1]['inputs'], ARCH_INPUTS + [EXCLUDE])


class ArchitectureControlTests(ArchitectureFixture):  # R6
    def test_confirmed_broken_variants_fail_their_criteria(self):
        # Execute real acceptance cases against independent disposable sources.
        variants = [('guide', ArchitectureFrameworkEndToEndTests, 'test_each_input_and_addition_invalidates',
                     'missing freshness invalidation: ' + ARCH_GUIDE),
                    ('helper', ArchitectureFrameworkEndToEndTests, 'test_each_input_and_addition_invalidates',
                     'missing freshness invalidation: ' + ARCH_TESTS[1]),
                    ('loose', ArchitectureProfileTests, 'test_exact_registration_and_original_profile',
                     'unregistered argv exported'),
                    ('empty', ArchitectureFrameworkEndToEndTests, 'test_each_input_and_addition_invalidates',
                     'architecture execution count must be two')]
        for variant, cls, method, criterion in variants:
            with self.subTest(variant=variant):
                case = cls(method)
                setup = case.setUp

                def mutated_setup():
                    setup()
                    path = case.root / '.ai/scripts/assurance_inputs.py'
                    original = path.read_text()
                    if variant in ('guide', 'helper'):
                        module = case.module()
                        catalog = copy.deepcopy(module.PROFILES)
                        profile = next(p for p in catalog if p['id'] == 'python-architecture-compatibility')
                        omitted = ARCH_GUIDE if variant == 'guide' else ARCH_TESTS[1]
                        profile['inputs'].remove(omitted)
                        del profile['rationale'][omitted]
                        replacement = (original.split('PROFILES = ', 1)[0] + 'PROFILES = ' + repr(catalog)
                                       + '\nLIMITATIONS =' + original.split('\nLIMITATIONS =', 1)[1])
                        path.write_text(replacement)
                        case.assertNotIn(omitted, case.suggestion()['inputs'])
                    elif variant == 'loose':
                        old = "p['argv'] == list(argv)"
                        case.assertEqual(original.count(old), 1)
                        replacement = original.replace(old, "p['argv'] == list(argv)[:len(p['argv'])]")
                        path.write_text(replacement)
                    else:
                        path = case.root / ARCH_TESTS[0]
                        original = path.read_text()
                        replacement = 'import unittest\nunittest.main()\n'
                        path.write_text(replacement)
                    case.assertNotEqual(original, replacement, 'mutation was not applied')
                    case.assertEqual(path.read_text(), replacement, 'mutation bytes differ')

                case.setUp = mutated_setup
                result = unittest.TestResult()
                case.run(result)
                self.assertEqual(result.testsRun, 1)
                self.assertFalse(result.errors, result.errors)
                self.assertTrue(result.failures, 'broken variant survived: ' + variant)
                self.assertIn(criterion, '\n'.join(text for _, text in result.failures))


if __name__ == '__main__':
    unittest.main()
