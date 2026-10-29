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


# Harness wiring: specification-5c.md R1-R6. Independent of the profile catalog.
WIRING_COMMAND = ['python3', '.ai/scripts/tests/test_lifecycle_conformance.py', 'HarnessWiring']
WIRING_TESTS = [WIRING_COMMAND[1], '.ai/scripts/tests/disk_tmp.py']
WIRING_JSON = ['.claude/settings.json', '.codex/hooks.json', '.cursor/hooks.json']
WIRING_INPUTS = ['.ai/scripts/**', '!.ai/scripts/tests/**', *WIRING_TESTS, *WIRING_JSON]
WIRING_IMPORTS = ['.ai/scripts/' + name + '.py' for name in
                  ('scratch', 'lifecycle', 'review_guard', 'ledger', 'brownfield', 'okf',
                   'learning', 'scan', 'project_context', 'assurance')]


class HarnessWiringFixture(Fixture):
    def setUp(self):
        super().setUp()
        for name in [WIRING_TESTS[0], *WIRING_JSON, *ARCH_TESTS[:-1], ARCH_GUIDE]:
            destination = self.root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(SCRIPTS.parent.parent / name, destination)
        self.commit()

    def export(self, argv=None, **kwargs):
        return super().export(argv=WIRING_COMMAND if argv is None else argv, **kwargs)

    def oracle(self):
        return {name: (self.root / name).read_bytes()
                for name in [*WIRING_TESTS, *WIRING_IMPORTS, *WIRING_JSON]}

    def selected_bytes(self):
        # Handwritten patterns, never the profile under test: detect writes to
        # conservative descendants as well as the currently imported files.
        return {name: (self.root / name).read_bytes()
                for name in ledger.input_paths(self.root, WIRING_INPUTS)}

    def preflight(self):
        before = self.selected_bytes()
        result = self.process(WIRING_COMMAND)
        output = result.stdout + result.stderr
        counts = re.findall(r'Ran (\d+) tests? in ', output)
        self.assertTrue(counts, 'wiring execution count missing: ' + output)
        self.assertEqual(int(counts[-1]), 3, 'wiring execution count must be three')
        self.assertEqual(result.returncode, 0, output)
        self.assert_inputs_unchanged(before)
        return before

    def assert_inputs_unchanged(self, before):
        self.assertEqual(self.selected_bytes(), before, 'wiring execution changed inputs')

    def edit_and_restore(self, name, check):
        path = self.root / name
        original = path.read_bytes() if path.exists() else None
        # Whitespace changes valid JSON without changing required declarations.
        self.write(name, (original.decode() if original is not None else '') + '\n ')
        try:
            check()
        finally:
            if original is None:
                path.unlink()
            else:
                path.write_bytes(original)


class HarnessWiringProfileTests(HarnessWiringFixture):  # R1
    def test_exact_registration_and_prior_profiles(self):
        value = self.suggestion()
        self.assertEqual(value['profile_id'], 'python-harness-wiring')
        self.assertEqual(value['argv'], WIRING_COMMAND)
        self.assert_prior_profiles()
        for argv in (WIRING_COMMAND[:2], WIRING_COMMAND + ['-v'],
                     WIRING_COMMAND[:2] + ['Distribution'],
                     WIRING_COMMAND[:2] + ['HarnessWiring.test_codex_gates_edits_commits_and_session_start'],
                     [sys.executable, *WIRING_COMMAND[1:]],
                     ['python3', '-m', 'unittest', 'discover', '-s', '.ai/scripts/tests',
                      '-p', 'test_lifecycle_conformance.py']):
            result = self.export(argv=argv)
            self.assertEqual(result.returncode, 2, 'unregistered wiring argv exported: ' + repr(argv))
            self.assertNotIn('inputs', json.loads(result.stdout))
        self.refused(cwd=self.root / '.ai')

    def assert_prior_profiles(self):
        # Compare unchanged catalog entries with the delivered, invoking HEAD.
        # This baseline is independent of the modified worktree catalog.
        result = subprocess.run(['git', 'show', 'HEAD:.ai/scripts/assurance_inputs.py'],
                                cwd=SCRIPTS.parent.parent, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        import ast
        tree = ast.parse(result.stdout)
        baseline = next(ast.literal_eval(node.value) for node in tree.body
                        if isinstance(node, ast.Assign)
                        and any(isinstance(t, ast.Name) and t.id == 'PROFILES' for t in node.targets))
        actual = self.module().PROFILES
        for identity, argv, inputs in [('python-runner-test', COMMAND, READS),
                                       ('python-architecture-compatibility', ARCH_COMMAND, ARCH_INPUTS)]:
            expected = next(p for p in baseline if p['id'] == identity)
            self.assertEqual(next(p for p in actual if p['id'] == identity), expected)
            exported = self.suggestion(argv=argv)
            self.assertEqual((exported['profile_id'], exported['argv'], exported['inputs'], exported['rationale']),
                             (identity, argv, inputs, expected['rationale']))


class HarnessWiringDependencyTests(HarnessWiringFixture):  # R2
    def test_order_scope_and_independent_oracle(self):
        value = self.suggestion()
        self.assertEqual(value['inputs'], WIRING_INPUTS)
        self.assertEqual(set(value['rationale']), set(WIRING_INPUTS))
        self.assertTrue(all(value['rationale'].values()))
        self.write('.ai/scripts/future_wiring.py', '# future production\n')
        self.write('.ai/scripts/assets/data.txt', 'conservative descendant')
        self.write('.ai/scripts/tests/unrelated.py', '# unrelated test\n')
        self.write('unrelated.md', 'non-input document')
        selected = set(ledger.input_paths(self.root, value['inputs']))
        self.assertTrue(set(self.oracle()).issubset(selected))
        for name in ('.ai/scripts/future_wiring.py', '.ai/scripts/assets/data.txt'):
            self.assertIn(name, selected)
        for name in ('.ai/scripts/tests/unrelated.py', *ARCH_TESTS[:-1], ARCH_GUIDE, 'unrelated.md'):
            self.assertNotIn(name, selected)
        sentinels = {
            WIRING_TESTS[0]: ('import disk_tmp', 'import lifecycle', '(ROOT / path).read_text()',
                              'class HarnessWiring', *WIRING_JSON, 'unittest.main()'),
            WIRING_TESTS[1]: ('import scratch', 'scratch.require_disk'),
            '.ai/scripts/lifecycle.py': ('import scratch', 'import review_guard', 'LazyLoader',
                                         'brownfield', 'project_context', 'assurance'),
            '.ai/scripts/review_guard.py': ('import ledger', 'import scratch'),
            '.ai/scripts/scratch.py': ('/proc/self/mountinfo',),
        }
        for name, phrases in sentinels.items():
            source = (self.root / name).read_text()
            for phrase in phrases:
                self.assertIn(phrase, source, 'review wiring dependency oracle: ' + name)


class HarnessWiringExportTests(HarnessWiringFixture):  # R3
    def test_readonly_formats_supplements_and_json_is_not_parsed(self):
        marker = self.root / 'executed'
        for name in WIRING_TESTS:
            self.write(name, f'from pathlib import Path\nPath({str(marker)!r}).touch()\nraise RuntimeError("executed")\n')
        for name in WIRING_JSON:
            self.write(name, '{malformed JSON')
        self.write('space file.txt', 'supplement')
        before = snapshot(self.root)
        value = self.suggestion(extra=('space file.txt',))
        text = self.export(extra=('space file.txt',), json_output=False)
        self.assertEqual(text.returncode, 0, text.stderr)
        self.assertEqual(value['inputs'], WIRING_INPUTS + ['space file.txt'])
        self.assertEqual(value['lifecycle_inputs_argv'], ['--inputs', *value['inputs']])
        for item in (value['profile_id'], value['inputs_line'], json.dumps(WIRING_COMMAND),
                     json.dumps(value['lifecycle_inputs_argv']), *value['rationale'].values(), *value['limitations']):
            self.assertIn(item, text.stdout)
        self.assertTrue(value['review_required'])
        raw = '- WIRE-R1: The check MUST work.\n  - Verify: `' + ' '.join(WIRING_COMMAND) + '`\n' + value['inputs_line'] + '\n'
        parsed = assurance.parse('WIRE-R1', 'capabilities/wiring.md', raw, root=self.root)
        self.assertIsNone(parsed.invalid)
        self.assertEqual(list(parsed.globs), value['inputs'])
        self.assertEqual(snapshot(self.root), before)
        self.assertFalse(marker.exists())

    def test_required_literals_and_unsafe_boundaries_refuse(self):
        for name in [*WIRING_TESTS, *WIRING_JSON]:
            path = self.root / name
            original = path.read_bytes()
            path.unlink()
            self.refused()
            path.write_bytes(original)
        name = WIRING_JSON[0]
        self.git('rm', '--cached', name)
        self.write('.gitignore', name + '\n')
        self.refused()
        self.git('add', '-f', name)
        path = self.root / name
        original = path.read_bytes()
        outside = Path(self.temp.name) / 'outside.json'
        outside.write_bytes(original)
        path.unlink()
        path.symlink_to(outside)
        self.refused()
        path.unlink()
        path.write_bytes(original)
        for extra in ('!README.md', '../x', '/etc/passwd', '', 'x`bad', '--other-option'):
            self.refused(extra=(extra,))


class HarnessWiringCompatibilityTests(HarnessWiringFixture):  # R4
    def test_advisory_guide_and_existing_contracts(self):
        HarnessWiringProfileTests.assert_prior_profiles(self)
        self.assertIsNone(ledger.default_inputs(WIRING_COMMAND))
        self.assertEqual(ledger.default_inputs(COMMAND), ('python-tests', ['**']))
        for argv in (['python3', '-m', 'unittest', 'discover', '-s', '.ai/scripts/tests'],
                     *[['python3', '.ai/scripts/run_tests.py', '-j', str(n)] for n in (1, 8, 32)]):
            self.refused(argv=argv)
        value = self.suggestion()
        self.assertNotIn(EXCLUDE, value['inputs'])
        self.assertTrue(value['review_required'])
        self.assertIn('runtime', ' '.join(value['limitations']).lower())
        guide = (self.root / ARCH_GUIDE).read_text()
        for phrase in ('python-harness-wiring', ' '.join(WIRING_COMMAND), 'static',
                       'conservative', 'explicit', 'native', *WIRING_JSON):
            self.assertIn(phrase, guide)


class HarnessWiringFrameworkEndToEndTests(HarnessWiringFixture):  # R5
    def record(self):
        value = self.suggestion()
        before = self.preflight()
        self.lc('tier', 'L1', '--reason', 'static wiring framework fixture')
        self.lc('run', 'wiring', *value['lifecycle_inputs_argv'], '--', *WIRING_COMMAND)
        self.assert_inputs_unchanged(before)
        import lifecycle
        entry = lifecycle.load(self.root)['ledger'][-1]
        self.assertEqual((entry['argv'], entry['inputs'], entry['exit']),
                         (WIRING_COMMAND, value['inputs'], 0))
        self.assertIn('REUSE', self.lc('reuse', 'wiring'))

    def test_each_input_and_addition_invalidates(self):
        self.record()
        for name in ('.ai/scripts/tests/unrelated.py', 'unrelated.md'):
            self.edit_and_restore(name, lambda: self.assertIn('REUSE', self.lc('reuse', 'wiring')))
        for name in [*WIRING_JSON, *WIRING_TESTS, '.ai/scripts/review_guard.py', '.ai/scripts/new_wiring.py']:
            with self.subTest(name=name):
                def stale():
                    result = self.process([sys.executable, '.ai/scripts/lifecycle.py', 'reuse', 'wiring'])
                    self.assertEqual(result.returncode, 1, 'missing wiring freshness invalidation: ' + name)
                    self.assertIn('RERUN', result.stdout)
                self.edit_and_restore(name, stale)
        self.assertIn('REUSE', self.lc('reuse', 'wiring'))
        self.assertFalse((self.root / 'knowledge').exists())


class HarnessWiringFailureTests(HarnessWiringFixture):  # R5
    def test_each_harness_malformed_and_missing_wiring_fails_actual_command(self):
        for name in WIRING_JSON:
            path = self.root / name
            original = path.read_text()
            data = json.loads(original)
            event = 'sessionStart' if name.startswith('.cursor/') else 'SessionStart'
            data['hooks'][event] = []
            for content, error in (('{malformed JSON', 'JSONDecodeError'),
                                   (json.dumps(data), 'AssertionError')):
                with self.subTest(name=name, error=error):
                    try:
                        path.write_text(content)
                        self.assertEqual(path.read_text(), content, 'failure control not applied')
                        self.suggestion()  # Export validates paths, not JSON/wiring.
                        before = self.selected_bytes()
                        result = self.process(WIRING_COMMAND)
                        output = result.stdout + result.stderr
                        counts = re.findall(r'Ran (\d+) tests? in ', output)
                        self.assertTrue(counts, output)
                        self.assertEqual(int(counts[-1]), 3, output)
                        self.assertNotEqual(result.returncode, 0, output)
                        self.assertIn(error, output)
                        harness = name.split('/')[0][1:]
                        self.assertIn('test_' + harness + '_', output)
                        self.assert_inputs_unchanged(before)
                    finally:
                        path.write_text(original)


class HarnessWiringAdopterEndToEndTests(HarnessWiringFixture):  # R6
    def test_explicit_adoption_freshness_identity_and_receipt(self):
        (self.root / '.agentic.json').unlink()
        self.lc('tier', 'L1', '--reason', 'static wiring adopter fixture')
        result = self.process([sys.executable, '.ai/scripts/okf.py', 'init'])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.write('knowledge/project/sync-ignore', '*\n')
        value = self.suggestion()
        prefix = ('---\ntype: Capability\ntitle: Wiring\nnamespace: WIRE\nstatus: draft\n---\n'
                  '# Wiring\n\n## Requirements\n\n- WIRE-R1: The static check MUST pass.\n'
                  '  - Verify: `' + ' '.join(WIRING_COMMAND) + '`\n')
        original = prefix + value['inputs_line'] + '\n'
        capability = self.write('knowledge/capabilities/wiring.md', original)
        self.commit()

        def status():
            result = self.process([sys.executable, '.ai/scripts/lifecycle.py', 'assure', '--json'])
            data = json.loads(result.stdout)
            state = next(r['status'] for r in data['requirements'] if r['id'] == 'WIRE-R1')
            self.assertEqual(result.returncode, 0 if state == 'VERIFIED' else 1, result.stdout + result.stderr)
            return state

        self.assertEqual(status(), 'UNVERIFIED')
        before = self.preflight()
        self.lc('assure', '--run', 'WIRE-R1')
        self.assert_inputs_unchanged(before)
        self.assertEqual(status(), 'VERIFIED')
        for name in ('.ai/scripts/tests/unrelated.py', 'unrelated.md'):
            self.edit_and_restore(name, lambda: self.assertEqual(status(), 'VERIFIED'))
        for name in [*WIRING_JSON, *WIRING_TESTS, '.ai/scripts/review_guard.py', '.ai/scripts/new_wiring.py']:
            with self.subTest(name=name):
                self.edit_and_restore(name, lambda: self.assertEqual(status(), 'STALE'))
        self.assertEqual(status(), 'VERIFIED')
        reordered = [*value['inputs'][:-2], value['inputs'][-1], value['inputs'][-2]]
        capability.write_text(prefix + '  - Inputs: ' + ' '.join('`' + p + '`' for p in reordered) + '\n')
        self.assertEqual(status(), 'UNVERIFIED')
        capability.write_text(original.replace('HarnessWiring`', 'HarnessWiring -v`'))
        self.assertEqual(status(), 'UNVERIFIED')
        capability.write_text(original)
        self.assertEqual(status(), 'VERIFIED')
        entries = [e for p in (self.root / 'knowledge/history/lifecycle').glob('*.json')
                   for e in json.loads(p.read_text()).get('ledger', []) if e['label'] == 'req:WIRE-R1']
        self.assertEqual(entries[-1]['inputs'], WIRING_INPUTS + [EXCLUDE])
        self.write('knowledge/history/lifecycle/extra-receipt.json', '{}\n')
        self.assertEqual(status(), 'VERIFIED')


class HarnessWiringControlTests(HarnessWiringFixture):  # R6
    def test_confirmed_broken_variants_fail_intended_criteria(self):
        method = 'test_each_input_and_addition_invalidates'
        variants = [(name, HarnessWiringFrameworkEndToEndTests, method,
                     'missing wiring freshness invalidation: ' + name) for name in WIRING_JSON]
        variants += [('loose', HarnessWiringProfileTests, 'test_exact_registration_and_prior_profiles',
                      'unregistered wiring argv exported'),
                     ('empty', HarnessWiringFrameworkEndToEndTests, method,
                      'wiring execution count must be three')]
        for variant, cls, test, criterion in variants:
            with self.subTest(variant=variant):
                case = cls(test)
                setup = case.setUp

                def mutated_setup():
                    setup()
                    path = case.root / '.ai/scripts/assurance_inputs.py'
                    original = path.read_text()
                    if variant in WIRING_JSON:
                        catalog = copy.deepcopy(case.module().PROFILES)
                        profile = next(p for p in catalog if p['id'] == 'python-harness-wiring')
                        profile['inputs'].remove(variant)
                        del profile['rationale'][variant]
                        replacement = (original.split('PROFILES = ', 1)[0] + 'PROFILES = ' + repr(catalog)
                                       + '\nLIMITATIONS =' + original.split('\nLIMITATIONS =', 1)[1])
                    elif variant == 'loose':
                        old = "p['argv'] == list(argv)"
                        case.assertEqual(original.count(old), 1)
                        replacement = original.replace(old, "p['argv'] == list(argv)[:len(p['argv'])]")
                    else:
                        path = case.root / WIRING_TESTS[0]
                        original = path.read_text()
                        replacement = 'import unittest\nunittest.main()\n'
                    path.write_text(replacement)
                    case.assertNotEqual(original, replacement, 'mutation was not applied')
                    case.assertEqual(path.read_text(), replacement, 'mutation bytes differ')
                    if variant in WIRING_JSON:
                        case.assertNotIn(variant, case.suggestion()['inputs'])

                case.setUp = mutated_setup
                result = unittest.TestResult()
                case.run(result)
                self.assertEqual(result.testsRun, 1)
                self.assertFalse(result.errors, result.errors)
                self.assertTrue(result.failures, 'broken wiring variant survived: ' + variant)
                self.assertIn(criterion, '\n'.join(detail for _, detail in result.failures))


# Reviewer report: specification-5d.md R1-R6. Independent reviewed declarations.
REPORT_COMMAND = ['python3', '.ai/scripts/tests/test_lifecycle_conformance.py',
                  'RolesAndSkills.test_reviewer_completion_report_contract']
REPORT_TESTS = [REPORT_COMMAND[1], '.ai/scripts/tests/disk_tmp.py']
REPORT_DOCS = ['.claude/agents/reviewer.md', '.codex/agents/reviewer.toml',
               '.ai/agents/reviewer.md', '.ai/lifecycle.md', '.claude/skills/review/SKILL.md']
REPORT_INPUTS = ['.ai/scripts/**', '!.ai/scripts/tests/**', *REPORT_TESTS, *REPORT_DOCS]
REPORT_IMPORTS = ['.ai/scripts/' + name + '.py' for name in
                  ('scratch', 'lifecycle', 'review_guard', 'ledger', 'brownfield', 'okf',
                   'learning', 'scan', 'project_context', 'assurance')]
REPORT_SETUP_PINS = {
    '.ai/scripts/tests/test_lifecycle_conformance.py': '50977be9e0fc2636e75b83eba96f267339efd91e89f3d035690d0a0e24e8a02b',
    '.ai/scripts/tests/disk_tmp.py': 'fff9eed82f770bce05c477c507ad3c00dae4a16c216521b004646837c0bdd02f',
    '.ai/scripts/scratch.py': '523cbb977066b41423329249d132d2dc27a2f963db15b71489c2579fdb093060',
    '.ai/scripts/lifecycle.py': '048f391c166ffb58b8ba1d769ca287adc78d5c155a28bebba043e0d93a30e1ca',
    '.ai/scripts/review_guard.py': '2d806b1c16cb028a8b2197aec8881b0a4db1a962125f5a5d50a8599b01c45d69',
    '.ai/scripts/ledger.py': 'fc2423e775969cdc28173f970d7c676e6ad254e8f5e120abb89a5c1244b80cab',
}


def report_setup_digest(path):
    """Pin import-time statements and bodies called by the reviewed setup path.

    Classes execute their bodies during import, so retain them conservatively.
    Other functions retain signatures/decorators but not uncalled bodies.
    """
    import ast
    source = path.read_text()
    lines = source.splitlines()
    called = {'test_lifecycle_conformance.py': {'text'},
              'scratch.py': {'require_disk'}, 'lifecycle.py': {'lazy'},
              'review_guard.py': {'protected'}}.get(path.name, set())
    segments = []
    for node in ast.parse(source).body:
        decorators = getattr(node, 'decorator_list', [])
        start = min([node.lineno, *[n.lineno for n in decorators]]) - 1
        end = node.end_lineno
        if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name not in called and node.body[0].lineno != node.lineno):
            end = node.body[0].lineno - 1
        segments.append('\n'.join(lines[start:end]))
    return hashlib.sha256('\n'.join(segments).encode()).hexdigest()


class ReviewerReportFixture(Fixture):
    def setUp(self):
        super().setUp()
        # Prior-profile data supports compatibility exports, not the read oracle.
        for name in dict.fromkeys([*REPORT_TESTS, *REPORT_DOCS, *WIRING_JSON, *ARCH_TESTS[:-1]]):
            destination = self.root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(SCRIPTS.parent.parent / name, destination)
        self.commit()

    def export(self, argv=None, **kwargs):
        return super().export(argv=REPORT_COMMAND if argv is None else argv, **kwargs)

    def selected_bytes(self):
        return {name: (self.root / name).read_bytes()
                for name in ledger.input_paths(self.root, REPORT_INPUTS)}

    def assert_inputs_unchanged(self, before):
        self.assertEqual(self.selected_bytes(), before, 'report execution changed inputs')

    def execution(self, passing=True):
        before = self.selected_bytes()
        result = self.process(REPORT_COMMAND)
        output = result.stdout + result.stderr
        counts = re.findall(r'Ran (\d+) tests? in ', output)
        self.assertEqual(len(counts), 1, 'report execution count missing or ambiguous: ' + output)
        self.assertEqual(int(counts[0]), 1, 'report execution count must be one: ' + output)
        if passing:
            self.assertEqual(result.returncode, 0, output)
            self.assertRegex(output, r'\nOK\s*$')
        else:
            self.assertNotEqual(result.returncode, 0, output)
            self.assertIn('AssertionError', output)
            self.assertIn('test_reviewer_completion_report_contract', output)
        self.assert_inputs_unchanged(before)
        return result

    def preflight(self):
        before = self.selected_bytes()
        self.execution()
        return before

    def edit_and_restore(self, name, check):
        path = self.root / name
        original = path.read_bytes() if path.exists() else None
        self.write(name, (original.decode() if original is not None else '') + '\n ')
        try:
            if name in REPORT_DOCS:
                self.execution()  # Freshness changes must preserve the static contract.
            check()
        finally:
            if original is None:
                path.unlink()
            else:
                path.write_bytes(original)

    def assert_prior_profiles(self):
        HarnessWiringProfileTests.assert_prior_profiles(self)
        result = subprocess.run(['git', 'show', 'HEAD:.ai/scripts/assurance_inputs.py'],
                                cwd=SCRIPTS.parent.parent, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        import ast
        tree = ast.parse(result.stdout)
        baseline = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                        and any(isinstance(t, ast.Name) and t.id == 'PROFILES' for t in n.targets))
        expected = next(p for p in baseline if p['id'] == 'python-harness-wiring')
        actual = next(p for p in self.module().PROFILES if p['id'] == expected['id'])
        self.assertEqual(actual, expected)
        value = self.suggestion(argv=WIRING_COMMAND)
        self.assertEqual((value['profile_id'], value['argv'], value['inputs'], value['rationale']),
                         (expected['id'], WIRING_COMMAND, WIRING_INPUTS, expected['rationale']))


class ReviewerReportProfileTests(ReviewerReportFixture):  # R1
    def test_exact_registration_and_prior_profiles(self):
        value = self.suggestion()
        self.assertEqual(value['profile_id'], 'python-reviewer-report-contract')
        self.assertEqual(value['argv'], REPORT_COMMAND)
        self.assert_prior_profiles()
        for argv in (REPORT_COMMAND[:2], REPORT_COMMAND[:2] + ['RolesAndSkills'],
                     REPORT_COMMAND[:2] + ['RolesAndSkills.test_every_documented_okf_show_command_resolves'],
                     REPORT_COMMAND + ['-v'], [sys.executable, *REPORT_COMMAND[1:]],
                     ['python3', './' + REPORT_COMMAND[1], REPORT_COMMAND[2]],
                     ['python3', '-m', 'unittest', 'discover', '-s', '.ai/scripts/tests',
                      '-p', 'test_lifecycle_conformance.py']):
            value = self.refused(argv=argv)
            self.assertIn('exact command', value['reason'])
        self.refused(cwd=self.root / '.ai')


class ReviewerReportDependencyTests(ReviewerReportFixture):  # R2
    def test_added_import_or_read_requires_review(self):
        for name, addition in [(REPORT_TESTS[0], '\nimport unreviewed_report_helper\n'),
                               (REPORT_TESTS[0], 'text-body'),
                               *[(p, '\nfrom pathlib import Path as AddedPath\nAddedPath("unrelated.md").read_text()\n')
                                 for p in [*REPORT_TESTS, *REPORT_IMPORTS[:4]]]]:
            with self.subTest(name=name, addition=addition):
                case = ReviewerReportDependencyTests('test_order_scope_and_independent_oracle')
                setup = case.setUp

                def changed_setup():
                    setup()
                    case.write('unrelated.md', 'new unreviewed input')
                    case.write('.ai/scripts/tests/unreviewed_report_helper.py',
                               'from pathlib import Path\nPath("unrelated.md").read_text()\n')
                    path = case.root / name
                    import ast
                    source = path.read_text()
                    # Insert before unittest.main can exit, after future imports.
                    if addition == 'text-body':
                        old = '    return (ROOT / path).read_text()'
                        case.assertEqual(source.count(old), 1)
                        changed = source.replace(old, '    (ROOT / "unrelated.md").read_text()\n' + old)
                    else:
                        after = max(n.end_lineno for n in ast.parse(source).body
                                    if isinstance(n, (ast.Import, ast.ImportFrom)))
                        lines = source.splitlines(keepends=True)
                        changed = ''.join(lines[:after]) + addition + ''.join(lines[after:])
                    path.write_text(changed)
                    case.assertEqual(path.read_text(), changed)
                    case.assertNotIn('unrelated.md', ledger.input_paths(case.root, REPORT_INPUTS))
                    case.execution()  # The new excluded read is reachable, not dead code.

                case.setUp = changed_setup
                result = unittest.TestResult()
                case.run(result)
                self.assertFalse(result.errors, result.errors)
                self.assertTrue(result.failures, 'unreviewed import-time dependency survived: ' + name)
                self.assertIn('review report import-time boundary',
                              '\n'.join(detail for _, detail in result.failures))

    def test_order_scope_and_independent_oracle(self):
        value = self.suggestion()
        actual_setup = {p: report_setup_digest(self.root / p)
                        for p in [*REPORT_TESTS, *REPORT_IMPORTS[:4]]}
        self.assertEqual(actual_setup, REPORT_SETUP_PINS,
                         'review report import-time boundary: ' + repr(actual_setup))
        self.assertEqual(value['inputs'], REPORT_INPUTS)
        self.assertEqual(set(value['rationale']), set(REPORT_INPUTS))
        for name, terms in {
            '.ai/scripts/**': ('import', 'lazy', 'conservative'),
            '!.ai/scripts/tests/**': ('exclude',),
            REPORT_TESTS[0]: ('method', 'static'), REPORT_TESTS[1]: ('helper',),
            **{p: ('direct',) for p in REPORT_DOCS},
        }.items():
            for term in terms:
                self.assertIn(term, value['rationale'][name].lower())
        self.write('.ai/scripts/future_report.py', '# future production\n')
        self.write('.ai/scripts/assets/report.txt', 'conservative descendant')
        self.write('.ai/scripts/tests/unrelated.py', '# unrelated\n')
        self.write('unrelated.md', 'non-input')
        selected = set(ledger.input_paths(self.root, value['inputs']))
        self.assertTrue(set([*REPORT_TESTS, *REPORT_DOCS, *REPORT_IMPORTS]).issubset(selected))
        for name in ('.ai/scripts/future_report.py', '.ai/scripts/assets/report.txt'):
            self.assertIn(name, selected)
        for name in ('.ai/scripts/tests/unrelated.py', 'unrelated.md', *WIRING_JSON, *ARCH_TESTS[:-1]):
            self.assertNotIn(name, selected)
        import ast
        source = (self.root / REPORT_TESTS[0]).read_text()
        tree = ast.parse(source)
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'RolesAndSkills')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                      and n.name == REPORT_COMMAND[2].split('.')[1])
        # Pin the reviewed source, not a second copy of the current implementation.
        reviewed = '\n'.join(source.splitlines()[method.lineno - 1:method.end_lineno])
        self.assertEqual(hashlib.sha256(reviewed.encode()).hexdigest(),
                         '81d3db1483a1c681224724f2817e43e6a59f603007f88bbaf4706c4e96eea1ee',
                         'review report method dependency boundary')
        literals = {n.value for n in ast.walk(method) if isinstance(n, ast.Constant)
                    and isinstance(n.value, str) and n.value.startswith(('.ai/', '.claude/', '.codex/'))}
        self.assertEqual(literals, set(REPORT_DOCS) | {'.ai/lifecycle.md#Stage3'})
        sentinels = {
            REPORT_TESTS[0]: ('import disk_tmp', 'import lifecycle', '(ROOT / path).read_text()',
                              'SHOW.findall', 'shlex.split', 'unittest.main()'),
            REPORT_TESTS[1]: ('import scratch', 'scratch.require_disk'),
            '.ai/scripts/lifecycle.py': ('import scratch', 'import review_guard', 'LazyLoader',
                                         'brownfield', 'project_context', 'assurance'),
            '.ai/scripts/review_guard.py': ('import ledger', 'import scratch'),
            '.ai/scripts/scratch.py': ('/proc/self/mountinfo',),
        }
        for name, phrases in sentinels.items():
            for phrase in phrases:
                self.assertIn(phrase, (self.root / name).read_text(), 'review report dependency: ' + name)


class ReviewerReportExportTests(ReviewerReportFixture):  # R3
    def test_readonly_formats_supplements_and_no_semantic_parsing(self):
        marker = self.root / 'executed'
        for name in REPORT_TESTS:
            self.write(name, f'from pathlib import Path\nPath({str(marker)!r}).touch()\nraise RuntimeError("executed")\n')
        for name in REPORT_DOCS:
            self.write(name, 'nonconforming document, including invalid TOML """')
        self.write('space file.txt', 'supplement')
        before = snapshot(self.root)
        value = self.suggestion(extra=('space file.txt',))
        text = self.export(extra=('space file.txt',), json_output=False)
        self.assertEqual(text.returncode, 0, text.stderr)
        self.assertEqual(value['inputs'], REPORT_INPUTS + ['space file.txt'])
        self.assertEqual(value['lifecycle_inputs_argv'], ['--inputs', *value['inputs']])
        for item in (value['profile_id'], value['inputs_line'], json.dumps(REPORT_COMMAND),
                     json.dumps(value['lifecycle_inputs_argv']), *value['rationale'].values(), *value['limitations']):
            self.assertIn(item, text.stdout)
        raw = '- REPORT-R1: The check MUST pass.\n  - Verify: `' + ' '.join(REPORT_COMMAND) + '`\n' + value['inputs_line'] + '\n'
        parsed = assurance.parse('REPORT-R1', 'capabilities/report.md', raw, root=self.root)
        self.assertIsNone(parsed.invalid)
        self.assertEqual(list(parsed.globs), value['inputs'])
        self.assertTrue(value['review_required'])
        self.assertEqual(snapshot(self.root), before)
        self.assertFalse(marker.exists())

    def test_required_literals_and_unsafe_boundaries_refuse(self):
        for name in [*REPORT_TESTS, *REPORT_DOCS]:
            path = self.root / name
            original = path.read_bytes()
            path.unlink()
            try:
                self.refused()
            finally:
                path.write_bytes(original)
        name = REPORT_DOCS[0]
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
        try:
            self.refused()
        finally:
            path.unlink()
            path.write_bytes(original)
        for extra in ('!README.md', '../x', '/etc/passwd', '', 'x`bad', '--other-option'):
            self.refused(extra=(extra,))


class ReviewerReportCompatibilityTests(ReviewerReportFixture):  # R4
    def test_advisory_guide_and_existing_contracts(self):
        self.assert_prior_profiles()
        self.assertIsNone(ledger.default_inputs(REPORT_COMMAND))
        self.assertEqual(ledger.default_inputs(COMMAND), ('python-tests', ['**']))
        for argv in (['python3', '-m', 'unittest', 'discover', '-s', '.ai/scripts/tests'],
                     *[['python3', '.ai/scripts/run_tests.py', '-j', str(n)] for n in (1, 8, 32)]):
            self.refused(argv=argv)
        value = self.suggestion()
        self.assertNotIn(EXCLUDE, value['inputs'])
        self.assertTrue(value['review_required'])
        self.assertIn('runtime', ' '.join(value['limitations']).lower())
        guide = (self.root / ARCH_GUIDE).read_text()
        for phrase in ('python-reviewer-report-contract', ' '.join(REPORT_COMMAND),
                       'static', 'conservative', 'explicit', 'manual', 'TOML',
                       'report production', *REPORT_DOCS):
            self.assertIn(phrase, guide)


class ReviewerReportFrameworkEndToEndTests(ReviewerReportFixture):  # R5
    def record(self):
        value = self.suggestion()
        before = self.preflight()
        self.lc('tier', 'L1', '--reason', 'static report framework fixture')
        self.lc('run', 'report', *value['lifecycle_inputs_argv'], '--', *REPORT_COMMAND)
        self.assert_inputs_unchanged(before)
        import lifecycle
        entry = lifecycle.load(self.root)['ledger'][-1]
        self.assertEqual((entry['argv'], entry['inputs'], entry['exit']),
                         (REPORT_COMMAND, value['inputs'], 0))
        self.assertIn('REUSE', self.lc('reuse', 'report'))

    def test_each_input_and_addition_invalidates(self):
        self.record()
        for name in ('.ai/scripts/tests/unrelated.py', 'unrelated.md'):
            self.edit_and_restore(name, lambda: self.assertIn('REUSE', self.lc('reuse', 'report')))
        for name in [*REPORT_DOCS, *REPORT_TESTS, '.ai/scripts/review_guard.py', '.ai/scripts/new_report.py']:
            with self.subTest(name=name):
                def stale():
                    result = self.process([sys.executable, '.ai/scripts/lifecycle.py', 'reuse', 'report'])
                    self.assertEqual(result.returncode, 1, 'missing report freshness invalidation: ' + name)
                    self.assertIn('RERUN', result.stdout)
                self.edit_and_restore(name, stale)
        self.assertIn('REUSE', self.lc('reuse', 'report'))
        self.assertFalse((self.root / 'knowledge').exists())


class ReviewerReportFailureTests(ReviewerReportFixture):  # R5
    def test_each_document_contract_fails_actual_command(self):
        variants = [(p, '--section "Completion report"', '--section Severity') for p in REPORT_DOCS[:2]]
        variants += [(REPORT_DOCS[2], '## Residual Risks', '## Missing Risks')]
        variants += [(p, 'complete returned Markdown body unchanged', 'altered body') for p in REPORT_DOCS[3:]]
        for name, old, new in variants:
            with self.subTest(name=name):
                path = self.root / name
                original = path.read_text()
                self.assertIn(old, original)
                changed = original.replace(old, new)
                path.write_text(changed)
                try:
                    self.assertEqual(path.read_text(), changed)
                    self.suggestion()
                    self.execution(passing=False)
                finally:
                    path.write_text(original)


class ReviewerReportAdopterEndToEndTests(ReviewerReportFixture):  # R6
    def test_explicit_adoption_freshness_identity_and_receipt(self):
        (self.root / '.agentic.json').unlink()
        self.lc('tier', 'L1', '--reason', 'static report adopter fixture')
        result = self.process([sys.executable, '.ai/scripts/okf.py', 'init'])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.write('knowledge/project/sync-ignore', '*\n')
        value = self.suggestion()
        prefix = ('---\ntype: Capability\ntitle: Report\nnamespace: REPORT\nstatus: draft\n---\n'
                  '# Report\n\n## Requirements\n\n- REPORT-R1: The static check MUST pass.\n'
                  '  - Verify: `' + ' '.join(REPORT_COMMAND) + '`\n')
        original = prefix + value['inputs_line'] + '\n'
        capability = self.write('knowledge/capabilities/report.md', original)
        self.commit()

        def status():
            result = self.process([sys.executable, '.ai/scripts/lifecycle.py', 'assure', '--json'])
            data = json.loads(result.stdout)
            state = next(r['status'] for r in data['requirements'] if r['id'] == 'REPORT-R1')
            self.assertEqual(result.returncode, 0 if state == 'VERIFIED' else 1, result.stdout + result.stderr)
            return state

        self.assertEqual(status(), 'UNVERIFIED')
        before = self.preflight()
        self.lc('assure', '--run', 'REPORT-R1')
        self.assert_inputs_unchanged(before)
        self.assertEqual(status(), 'VERIFIED')
        for name in ('.ai/scripts/tests/unrelated.py', 'unrelated.md'):
            self.edit_and_restore(name, lambda: self.assertEqual(status(), 'VERIFIED'))
        for name in [*REPORT_DOCS, *REPORT_TESTS, '.ai/scripts/review_guard.py', '.ai/scripts/new_report.py']:
            with self.subTest(name=name):
                self.edit_and_restore(name, lambda: self.assertEqual(status(), 'STALE'))
        self.assertEqual(status(), 'VERIFIED')
        reordered = [*value['inputs'][:-2], value['inputs'][-1], value['inputs'][-2]]
        capability.write_text(prefix + '  - Inputs: ' + ' '.join('`' + p + '`' for p in reordered) + '\n')
        self.assertEqual(status(), 'UNVERIFIED')
        capability.write_text(original.replace(REPORT_COMMAND[2] + '`', REPORT_COMMAND[2] + ' -v`'))
        self.assertEqual(status(), 'UNVERIFIED')
        capability.write_text(original)
        self.assertEqual(status(), 'VERIFIED')
        entries = [e for p in (self.root / 'knowledge/history/lifecycle').glob('*.json')
                   for e in json.loads(p.read_text()).get('ledger', []) if e['label'] == 'req:REPORT-R1']
        self.assertEqual(entries[-1]['inputs'], REPORT_INPUTS + [EXCLUDE])
        self.write('knowledge/history/lifecycle/extra-receipt.json', '{}\n')
        self.assertEqual(status(), 'VERIFIED')


class ReviewerReportControlTests(ReviewerReportFixture):  # R6
    def test_confirmed_broken_variants_fail_intended_criteria(self):
        method = 'test_each_input_and_addition_invalidates'
        variants = [(p, ReviewerReportFrameworkEndToEndTests, method,
                     'missing report freshness invalidation: ' + p) for p in REPORT_DOCS]
        variants += [('loose', ReviewerReportProfileTests, 'test_exact_registration_and_prior_profiles',
                      '0 != 2'), ('empty', ReviewerReportFrameworkEndToEndTests, method,
                                  'report execution count must be one')]
        for variant, cls, test, criterion in variants:
            with self.subTest(variant=variant):
                case = cls(test)
                setup = case.setUp

                def mutated_setup():
                    setup()
                    path = case.root / '.ai/scripts/assurance_inputs.py'
                    original = path.read_text()
                    if variant in REPORT_DOCS:
                        catalog = copy.deepcopy(case.module().PROFILES)
                        profile = next(p for p in catalog if p['id'] == 'python-reviewer-report-contract')
                        profile['inputs'].remove(variant)
                        del profile['rationale'][variant]
                        replacement = (original.split('PROFILES = ', 1)[0] + 'PROFILES = ' + repr(catalog)
                                       + '\nLIMITATIONS =' + original.split('\nLIMITATIONS =', 1)[1])
                    elif variant == 'loose':
                        old = "p['argv'] == list(argv)"
                        case.assertEqual(original.count(old), 1)
                        replacement = original.replace(old, "p['argv'] == list(argv)[:len(p['argv'])]")
                    else:
                        path = case.root / REPORT_TESTS[0]
                        original = path.read_text()
                        replacement = 'import sys\nimport unittest\nunittest.main(argv=[sys.argv[0]])\n'
                    path.write_text(replacement)
                    case.assertNotEqual(original, replacement, 'mutation was not applied')
                    case.assertEqual(path.read_text(), replacement, 'mutation bytes differ')
                    if variant in REPORT_DOCS:
                        case.assertNotIn(variant, case.suggestion()['inputs'])
                    if variant == 'empty':
                        result = case.process(REPORT_COMMAND)
                        case.assertRegex(result.stdout + result.stderr, r'Ran 0 tests? in ')

                case.setUp = mutated_setup
                result = unittest.TestResult()
                case.run(result)
                self.assertEqual(result.testsRun, 1)
                self.assertFalse(result.errors, result.errors)
                self.assertTrue(result.failures, 'broken report variant survived: ' + variant)
                self.assertIn(criterion, '\n'.join(detail for _, detail in result.failures))


# Installer documentation: specification-5e.md R1-R6. Reviewed independently of PROFILES.
INSTALLER_DOC_COMMAND = ['python3', '.ai/scripts/tests/test_lifecycle_conformance.py',
                         'Distribution.test_readme_and_playbook_document_the_installer']
INSTALLER_DOC_TESTS = [INSTALLER_DOC_COMMAND[1], '.ai/scripts/tests/disk_tmp.py']
INSTALLER_DOC_TEXT = ['.ai/README.md', '.ai/docs/install-and-upgrade.md', '.ai/VERSION']
INSTALLER_DOC_INPUTS = ['.ai/scripts/**', '!.ai/scripts/tests/**',
                        *INSTALLER_DOC_TESTS, *INSTALLER_DOC_TEXT]
INSTALLER_DOC_IMPORTS = ['.ai/scripts/' + name + '.py' for name in
                         ('scratch', 'lifecycle', 'review_guard', 'ledger', 'brownfield',
                          'okf', 'learning', 'scan', 'project_context', 'assurance')]


class InstallerDocFixture(Fixture):
    def setUp(self):
        super().setUp()
        # Compatibility files support old exports without expanding this read oracle.
        for name in dict.fromkeys([*INSTALLER_DOC_TESTS, *INSTALLER_DOC_TEXT,
                                   *REPORT_DOCS, *WIRING_JSON, *ARCH_TESTS[:-1]]):
            destination = self.root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(SCRIPTS.parent.parent / name, destination)
        self.commit()

    def export(self, argv=None, **kwargs):
        return super().export(argv=INSTALLER_DOC_COMMAND if argv is None else argv, **kwargs)

    def selected_bytes(self):
        return {name: (self.root / name).read_bytes()
                for name in ledger.input_paths(self.root, INSTALLER_DOC_INPUTS)}

    def assert_inputs_unchanged(self, before):
        self.assertEqual(self.selected_bytes(), before, 'installer doc execution changed inputs')

    def execution(self, failure=None):
        before = self.selected_bytes()
        result = self.process(INSTALLER_DOC_COMMAND)
        output = result.stdout + result.stderr
        counts = re.findall(r'Ran (\d+) tests? in ', output)
        self.assertEqual(len(counts), 1, 'installer doc execution count missing or ambiguous: ' + output)
        self.assertEqual(int(counts[0]), 1, 'installer doc execution count must be one: ' + output)
        if failure is None:
            self.assertEqual(result.returncode, 0, output)
            self.assertRegex(output, r'\nOK\s*$')
        else:
            self.assertNotEqual(result.returncode, 0, output)
            self.assertIn('AssertionError', output)
            self.assertIn(INSTALLER_DOC_COMMAND[2].split('.')[1], output)
            self.assertIn(failure, output)
        self.assert_inputs_unchanged(before)
        return result

    def preflight(self):
        before = self.selected_bytes()
        self.execution()
        return before

    def edit_and_restore(self, name, check):
        path = self.root / name
        original = path.read_bytes() if path.exists() else None
        changed = b'0.1.1\n' if name == '.ai/VERSION' else (original or b'') + b'\n '
        self.assertNotEqual(changed, original)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(changed)
        try:
            if name in INSTALLER_DOC_TEXT:
                self.execution()  # Freshness and deliberate static failures are separate.
            check()
        finally:
            if original is None:
                path.unlink()
            else:
                path.write_bytes(original)

    def assert_prior_profiles(self):
        result = subprocess.run(['git', 'show', 'HEAD:.ai/scripts/assurance_inputs.py'],
                                cwd=SCRIPTS.parent.parent, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        import ast
        baseline = next(ast.literal_eval(n.value) for n in ast.parse(result.stdout).body
                        if isinstance(n, ast.Assign)
                        and any(isinstance(t, ast.Name) and t.id == 'PROFILES' for t in n.targets))
        identities = ('python-runner-test', 'python-architecture-compatibility',
                      'python-harness-wiring', 'python-reviewer-report-contract')
        actual = self.module().PROFILES
        for identity in identities:
            expected = next(p for p in baseline if p['id'] == identity)
            self.assertEqual(next(p for p in actual if p['id'] == identity), expected)
            value = self.suggestion(argv=expected['argv'])
            self.assertEqual((value['profile_id'], value['argv'], value['inputs'], value['rationale']),
                             (identity, expected['argv'], expected['inputs'], expected['rationale']))


class InstallerDocProfileTests(InstallerDocFixture):  # R1
    def test_exact_registration_and_prior_profiles(self):
        value = self.suggestion()
        self.assertEqual(value['profile_id'], 'python-installer-doc-contract')
        self.assertEqual(value['argv'], INSTALLER_DOC_COMMAND)
        self.assert_prior_profiles()
        for argv in (INSTALLER_DOC_COMMAND[:2], INSTALLER_DOC_COMMAND[:2] + ['Distribution'],
                     INSTALLER_DOC_COMMAND[:2] + ['Distribution.test_eval_and_installer_share_one_kit_list'],
                     INSTALLER_DOC_COMMAND + ['-v'], [sys.executable, *INSTALLER_DOC_COMMAND[1:]],
                     ['python3', './' + INSTALLER_DOC_COMMAND[1], INSTALLER_DOC_COMMAND[2]],
                     ['python3', '-m', 'unittest', 'discover', '-s', '.ai/scripts/tests',
                      '-p', 'test_lifecycle_conformance.py']):
            self.assertIn('exact command', self.refused(argv=argv)['reason'])
        self.refused(cwd=self.root / '.ai')


class InstallerDocExportTests(InstallerDocFixture):  # R3
    def test_readonly_formats_supplements_and_no_semantic_parsing(self):
        marker = self.root / 'executed'
        for name in INSTALLER_DOC_TESTS:
            self.write(name, f'from pathlib import Path\nPath({str(marker)!r}).touch()\nraise RuntimeError("executed")\n')
        for name in INSTALLER_DOC_TEXT:
            self.write(name, 'nonconforming text, not a numeric version')
        for name in ('space file.txt', 'second.txt'):
            self.write(name, 'supplement')
        before = snapshot(self.root)
        extra = ('space file.txt', 'second.txt')
        value = self.suggestion(extra=extra)
        text = self.export(extra=extra, json_output=False)
        self.assertEqual(text.returncode, 0, text.stderr)
        self.assertEqual(value['inputs'], INSTALLER_DOC_INPUTS + list(extra))
        self.assertEqual(value['lifecycle_inputs_argv'], ['--inputs', *value['inputs']])
        for item in (value['profile_id'], value['inputs_line'], json.dumps(INSTALLER_DOC_COMMAND),
                     json.dumps(value['lifecycle_inputs_argv']), *value['rationale'].values(), *value['limitations']):
            self.assertIn(item, text.stdout)
        raw = ('- INSTALLER-R1: The check MUST pass.\n  - Verify: `'
               + ' '.join(INSTALLER_DOC_COMMAND) + '`\n' + value['inputs_line'] + '\n')
        parsed = assurance.parse('INSTALLER-R1', 'capabilities/installer.md', raw, root=self.root)
        self.assertIsNone(parsed.invalid)
        self.assertEqual(list(parsed.globs), value['inputs'])
        self.assertTrue(value['review_required'])
        self.assertEqual(snapshot(self.root), before)
        self.assertFalse(marker.exists())

    def test_required_literals_and_unsafe_boundaries_refuse(self):
        for name in [*INSTALLER_DOC_TESTS, *INSTALLER_DOC_TEXT]:
            path = self.root / name
            original = path.read_bytes()
            path.unlink()
            try:
                self.refused()
            finally:
                path.write_bytes(original)
        name = INSTALLER_DOC_TEXT[0]
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
        try:
            self.refused()
        finally:
            path.unlink()
            path.write_bytes(original)
        for extra in ('!README.md', '../x', '/etc/passwd', '', 'x`bad', '--other-option'):
            self.refused(extra=(extra,))


# These inspected setup files are unchanged from the shared eager/called path;
# keep independent pins rather than deriving expectations from current bytes.
INSTALLER_DOC_SETUP_PINS = {
    '.ai/scripts/tests/test_lifecycle_conformance.py': '50977be9e0fc2636e75b83eba96f267339efd91e89f3d035690d0a0e24e8a02b',
    '.ai/scripts/tests/disk_tmp.py': 'fff9eed82f770bce05c477c507ad3c00dae4a16c216521b004646837c0bdd02f',
    '.ai/scripts/scratch.py': '523cbb977066b41423329249d132d2dc27a2f963db15b71489c2579fdb093060',
    '.ai/scripts/lifecycle.py': '048f391c166ffb58b8ba1d769ca287adc78d5c155a28bebba043e0d93a30e1ca',
    '.ai/scripts/review_guard.py': '2d806b1c16cb028a8b2197aec8881b0a4db1a962125f5a5d50a8599b01c45d69',
    '.ai/scripts/ledger.py': 'fc2423e775969cdc28173f970d7c676e6ad254e8f5e120abb89a5c1244b80cab',
}


class InstallerDocDependencyTests(InstallerDocFixture):  # R2
    def test_order_scope_and_independent_oracle(self):
        value = self.suggestion()
        actual_setup = {p: report_setup_digest(self.root / p) for p in INSTALLER_DOC_SETUP_PINS}
        self.assertEqual(actual_setup, INSTALLER_DOC_SETUP_PINS,
                         'review installer doc dependency boundary: ' + repr(actual_setup))
        self.assertEqual(value['inputs'], INSTALLER_DOC_INPUTS)
        self.assertEqual(set(value['rationale']), set(INSTALLER_DOC_INPUTS))
        for name, terms in {
            '.ai/scripts/**': ('conservative', 'import', 'lazy'),
            '!.ai/scripts/tests/**': ('exclude',),
            INSTALLER_DOC_TESTS[0]: ('method', 'static'), INSTALLER_DOC_TESTS[1]: ('helper',),
            **{p: ('direct',) for p in INSTALLER_DOC_TEXT},
        }.items():
            for term in terms:
                self.assertIn(term, value['rationale'][name].lower())
        included = ['.ai/scripts/future_installer.py', '.ai/scripts/assets/installer.txt']
        excluded = ['.ai/scripts/tests/unrelated.py', 'unrelated.md',
                    *REPORT_DOCS, *WIRING_JSON, *ARCH_TESTS[:-1]]
        for name in included + excluded[:2]:
            self.write(name, '# independent inventory fixture\n')
        selected = set(ledger.input_paths(self.root, value['inputs']))
        self.assertTrue(set([*INSTALLER_DOC_TESTS, *INSTALLER_DOC_TEXT,
                             *INSTALLER_DOC_IMPORTS, *included]).issubset(selected))
        self.assertFalse(set(excluded) & selected)
        import ast
        source = (self.root / INSTALLER_DOC_TESTS[0]).read_text()
        cls = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef) and n.name == 'Distribution')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                      and n.name == INSTALLER_DOC_COMMAND[2].split('.')[1])
        reviewed = '\n'.join(source.splitlines()[method.lineno - 1:method.end_lineno])
        self.assertEqual(hashlib.sha256(reviewed.encode()).hexdigest(),
                         '4d40227d31017d0a10dfd3b0bc99ad51f5c108406bd9c70ce7d343131a107d90',
                         'review installer doc selected method boundary')
        reads = {n.args[0].value for n in ast.walk(method) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Name) and n.func.id == 'text'
                 and n.args and isinstance(n.args[0], ast.Constant)}
        self.assertEqual(reads, set(INSTALLER_DOC_TEXT))

    def test_reachable_added_dependencies_require_review(self):
        variants = [(p, ()) for p in INSTALLER_DOC_SETUP_PINS]
        variants += [(INSTALLER_DOC_TESTS[0], ('Distribution', INSTALLER_DOC_COMMAND[2].split('.')[1])),
                     (INSTALLER_DOC_TESTS[0], ('text',)),
                     ('.ai/scripts/scratch.py', ('require_disk',)),
                     ('.ai/scripts/lifecycle.py', ('lazy',)),
                     ('.ai/scripts/review_guard.py', ('protected',)),
                     ('.ai/scripts/review_guard.py', ('protected', 'decorate')),
                     (INSTALLER_DOC_TESTS[0], ('import-helper',))]
        self.assertEqual(len(variants), 13)
        for name, body in variants:
            with self.subTest(name=name, body=body):
                case = InstallerDocDependencyTests('test_order_scope_and_independent_oracle')
                setup = case.setUp

                def mutated_setup():
                    setup()
                    import ast
                    path = case.root / name
                    source = path.read_text()
                    tree = ast.parse(source)
                    addition = '__import__("pathlib").Path("unrelated.md").read_text()\n'
                    if body == ('import-helper',):
                        case.write('.ai/scripts/tests/unreviewed_installer_helper.py', addition)
                        addition = 'import unreviewed_installer_helper\n'
                    if body and body != ('import-helper',):
                        node = tree
                        for part in body:
                            node = next(n for n in node.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))
                                        and n.name == part)
                        first = node.body[0]
                        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                                and isinstance(first.value.value, str):
                            after = first.end_lineno
                        else:
                            after = min([first.lineno, *[n.lineno for n in
                                         getattr(first, 'decorator_list', [])]]) - 1
                        addition = ' ' * first.col_offset + addition
                    else:
                        after = max(n.end_lineno for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom)))
                    lines = source.splitlines(keepends=True)
                    changed = ''.join(lines[:after]) + addition + ''.join(lines[after:])
                    path.write_text(changed)
                    case.assertNotEqual(source, changed)
                    case.assertEqual(path.read_text(), changed)
                    case.assertNotIn('unrelated.md', ledger.input_paths(case.root, INSTALLER_DOC_INPUTS))
                    # Missing data must actually break this exact command, proving
                    # the injected read is reached rather than sitting in dead code.
                    missing = case.process(INSTALLER_DOC_COMMAND)
                    case.assertNotEqual(missing.returncode, 0)
                    case.assertIn('FileNotFoundError', missing.stdout + missing.stderr)
                    case.assertIn('unrelated.md', missing.stdout + missing.stderr)
                    case.write('unrelated.md', 'new excluded dependency')
                    case.execution()

                case.setUp = mutated_setup
                result = unittest.TestResult()
                case.run(result)
                self.assertEqual(result.testsRun, 1)
                self.assertFalse(result.errors, result.errors)
                self.assertTrue(result.failures, 'unreviewed installer dependency survived: ' + repr((name, body)))
                self.assertIn('review installer doc dependency boundary',
                              '\n'.join(detail for _, detail in result.failures))


class InstallerDocCompatibilityTests(InstallerDocFixture):  # R4
    def test_advisory_guide_and_existing_contracts(self):
        self.assert_prior_profiles()
        self.assertIsNone(ledger.default_inputs(INSTALLER_DOC_COMMAND))
        self.assertEqual(ledger.default_inputs(COMMAND), ('python-tests', ['**']))
        for argv in (['python3', '-m', 'unittest', 'discover', '-s', '.ai/scripts/tests'],
                     *[['python3', '.ai/scripts/run_tests.py', '-j', str(n)] for n in (1, 8, 32)]):
            self.refused(argv=argv)
        value = self.suggestion()
        self.assertNotIn(EXCLUDE, value['inputs'])
        self.assertEqual(value['schema_version'], 1)
        self.assertTrue(value['review_required'])
        self.assertIn('runtime', ' '.join(value['limitations']).lower())
        guide = (self.root / ARCH_GUIDE).read_text()
        for phrase in ('python-installer-doc-contract', ' '.join(INSTALLER_DOC_COMMAND),
                       'static', 'conservative', 'explicit', 'manual', 'numeric',
                       'semantic-version compatibility', *INSTALLER_DOC_TEXT):
            self.assertIn(phrase, guide)


class InstallerDocFrameworkEndToEndTests(InstallerDocFixture):  # R5
    def record(self):
        value = self.suggestion()
        before = self.preflight()
        self.lc('tier', 'L1', '--reason', 'static installer doc framework fixture')
        self.lc('run', 'installer-doc', *value['lifecycle_inputs_argv'], '--', *INSTALLER_DOC_COMMAND)
        self.assert_inputs_unchanged(before)
        import lifecycle
        entry = lifecycle.load(self.root)['ledger'][-1]
        self.assertEqual((entry['argv'], entry['inputs'], entry['exit']),
                         (INSTALLER_DOC_COMMAND, value['inputs'], 0))
        self.assertIn('REUSE', self.lc('reuse', 'installer-doc'))

    def test_each_input_and_addition_invalidates(self):
        self.record()
        for name in ('.ai/scripts/tests/unrelated.py', 'unrelated.md'):
            self.edit_and_restore(name, lambda: self.assertIn('REUSE', self.lc('reuse', 'installer-doc')))
            self.assertIn('REUSE', self.lc('reuse', 'installer-doc'))
        for name in [*INSTALLER_DOC_TEXT, *INSTALLER_DOC_TESTS,
                     '.ai/scripts/review_guard.py', '.ai/scripts/new_installer.py']:
            with self.subTest(name=name):
                def stale():
                    result = self.process([sys.executable, '.ai/scripts/lifecycle.py', 'reuse', 'installer-doc'])
                    self.assertEqual(result.returncode, 1, 'missing installer doc freshness invalidation: ' + name)
                    self.assertIn('RERUN', result.stdout)
                self.edit_and_restore(name, stale)
                self.assertIn('REUSE', self.lc('reuse', 'installer-doc'))
        self.assertFalse((self.root / 'knowledge').exists())


class InstallerDocFailureTests(InstallerDocFixture):  # R5
    def test_seven_static_failures_fail_actual_command(self):
        variants = [(INSTALLER_DOC_TEXT[0], '.ai/scripts/install.py', '.ai/scripts/missing.py')]
        variants += [(INSTALLER_DOC_TEXT[1], term, 'removed')
                     for term in ('--check', '--force', '--no-knowledge', 'conflict', '/hooks')]
        variants += [(INSTALLER_DOC_TEXT[2], '0.1.0\n', 'not-a-version\n')]
        self.assertEqual(len(variants), 7)
        for name, old, new in variants:
            with self.subTest(name=name, term=old):
                path = self.root / name
                original = path.read_bytes()
                self.assertIn(old.encode(), original)
                changed = original.replace(old.encode(), new.encode())
                path.write_bytes(changed)
                try:
                    self.assertEqual(path.read_bytes(), changed)
                    self.suggestion()
                    self.execution(failure='Regex didn\'t match' if name == '.ai/VERSION' else 'not found in')
                finally:
                    path.write_bytes(original)


class InstallerDocAdopterEndToEndTests(InstallerDocFixture):  # R6
    def test_explicit_adoption_freshness_identity_and_receipt(self):
        (self.root / '.agentic.json').unlink()
        self.lc('tier', 'L1', '--reason', 'static installer doc adopter fixture')
        result = self.process([sys.executable, '.ai/scripts/okf.py', 'init'])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.write('knowledge/project/sync-ignore', '*\n')
        value = self.suggestion()
        prefix = ('---\ntype: Capability\ntitle: Installer docs\nnamespace: INSTALLER\nstatus: draft\n---\n'
                  '# Installer docs\n\n## Requirements\n\n- INSTALLER-R1: The static check MUST pass.\n'
                  '  - Verify: `' + ' '.join(INSTALLER_DOC_COMMAND) + '`\n')
        original = prefix + value['inputs_line'] + '\n'
        capability = self.write('knowledge/capabilities/installer.md', original)
        self.commit()

        def status():
            result = self.process([sys.executable, '.ai/scripts/lifecycle.py', 'assure', '--json'])
            data = json.loads(result.stdout)
            state = next(r['status'] for r in data['requirements'] if r['id'] == 'INSTALLER-R1')
            self.assertEqual(result.returncode, 0 if state == 'VERIFIED' else 1, result.stdout + result.stderr)
            return state

        self.assertEqual(status(), 'UNVERIFIED')
        before = self.preflight()
        self.lc('assure', '--run', 'INSTALLER-R1')
        self.assert_inputs_unchanged(before)
        self.assertEqual(status(), 'VERIFIED')
        for name in ('.ai/scripts/tests/unrelated.py', 'unrelated.md'):
            self.edit_and_restore(name, lambda: self.assertEqual(status(), 'VERIFIED'))
            self.assertEqual(status(), 'VERIFIED')
        for name in [*INSTALLER_DOC_TEXT, *INSTALLER_DOC_TESTS,
                     '.ai/scripts/review_guard.py', '.ai/scripts/new_installer.py']:
            with self.subTest(name=name):
                self.edit_and_restore(name, lambda: self.assertEqual(status(), 'STALE'))
                self.assertEqual(status(), 'VERIFIED')
        reordered = [*value['inputs'][:-2], value['inputs'][-1], value['inputs'][-2]]
        capability.write_text(prefix + '  - Inputs: ' + ' '.join('`' + p + '`' for p in reordered) + '\n')
        self.assertEqual(status(), 'UNVERIFIED')
        capability.write_text(original.replace(INSTALLER_DOC_COMMAND[2] + '`', INSTALLER_DOC_COMMAND[2] + ' -v`'))
        self.assertEqual(status(), 'UNVERIFIED')
        capability.write_text(original)
        self.assertEqual(status(), 'VERIFIED')
        entries = [e for p in (self.root / 'knowledge/history/lifecycle').glob('*.json')
                   for e in json.loads(p.read_text()).get('ledger', []) if e['label'] == 'req:INSTALLER-R1']
        self.assertEqual(entries[-1]['inputs'], INSTALLER_DOC_INPUTS + [EXCLUDE])
        self.write('knowledge/history/lifecycle/extra-receipt.json', '{}\n')
        self.assertEqual(status(), 'VERIFIED')


class InstallerDocControlTests(InstallerDocFixture):  # R6
    def test_confirmed_broken_variants_fail_intended_criteria(self):
        method = 'test_each_input_and_addition_invalidates'
        variants = [(p, InstallerDocFrameworkEndToEndTests, method,
                     'missing installer doc freshness invalidation: ' + p) for p in INSTALLER_DOC_TEXT]
        variants += [('loose', InstallerDocProfileTests, 'test_exact_registration_and_prior_profiles', '0 != 2'),
                     ('empty', InstallerDocFrameworkEndToEndTests, method, 'installer doc execution count must be one')]
        self.assertEqual(len(variants), 5)
        for variant, cls, test, criterion in variants:
            with self.subTest(variant=variant):
                case = cls(test)
                setup = case.setUp

                def mutated_setup():
                    setup()
                    path = case.root / '.ai/scripts/assurance_inputs.py'
                    original = path.read_text()
                    if variant in INSTALLER_DOC_TEXT:
                        catalog = copy.deepcopy(case.module().PROFILES)
                        profile = next(p for p in catalog if p['id'] == 'python-installer-doc-contract')
                        profile['inputs'].remove(variant)
                        del profile['rationale'][variant]
                        replacement = (original.split('PROFILES = ', 1)[0] + 'PROFILES = ' + repr(catalog)
                                       + '\nLIMITATIONS =' + original.split('\nLIMITATIONS =', 1)[1])
                    elif variant == 'loose':
                        old = "p['argv'] == list(argv)"
                        case.assertEqual(original.count(old), 1)
                        replacement = original.replace(old, "p['argv'] == list(argv)[:len(p['argv'])]")
                    else:
                        path = case.root / INSTALLER_DOC_TESTS[0]
                        original = path.read_text()
                        replacement = 'import sys\nimport unittest\nunittest.main(argv=[sys.argv[0]])\n'
                    path.write_text(replacement)
                    case.assertNotEqual(original, replacement, 'mutation was not applied')
                    case.assertEqual(path.read_text(), replacement, 'mutation bytes differ')
                    if variant in INSTALLER_DOC_TEXT:
                        case.assertNotIn(variant, case.suggestion()['inputs'])
                    if variant == 'empty':
                        result = case.process(INSTALLER_DOC_COMMAND)
                        case.assertRegex(result.stdout + result.stderr, r'Ran 0 tests? in ')

                case.setUp = mutated_setup
                result = unittest.TestResult()
                case.run(result)
                self.assertEqual(result.testsRun, 1)
                self.assertFalse(result.errors, result.errors)
                self.assertTrue(result.failures, 'broken installer doc variant survived: ' + variant)
                self.assertIn(criterion, '\n'.join(detail for _, detail in result.failures))


# Validation policy: specification-5f.md R1-R6. Independent of PROFILES.
VALIDATION_POLICY_COMMAND = ['python3', '.ai/scripts/tests/test_lifecycle_conformance.py',
                             'Relocation.test_agents_md_points_to_the_policy_and_the_policy_keeps_its_must_rules']
VALIDATION_POLICY_TESTS = [VALIDATION_POLICY_COMMAND[1], '.ai/scripts/tests/disk_tmp.py']
VALIDATION_POLICY_DOCS = ['AGENTS.md', '.ai/validation-policy.md']
VALIDATION_POLICY_INPUTS = ['.ai/scripts/**', '!.ai/scripts/tests/**',
                           *VALIDATION_POLICY_TESTS, *VALIDATION_POLICY_DOCS]
VALIDATION_POLICY_IMPORTS = ['.ai/scripts/' + name + '.py' for name in
                            ('scratch', 'lifecycle', 'review_guard', 'ledger', 'brownfield',
                             'okf', 'learning', 'scan', 'project_context', 'assurance')]
VALIDATION_POLICY_RULES = (
    'MUST NOT rerun an unchanged failing check',
    '`--max` below 300 s is a violation',
    'MUST be split before work continues',
    'MUST NOT satisfy §8.1 by adding tests whose only purpose is more evidence',
)


class ValidationPolicyFixture(Fixture):
    def setUp(self):
        super().setUp()
        # Compatibility copies support prior exports, not the selected read oracle.
        for name in dict.fromkeys([*VALIDATION_POLICY_TESTS, *VALIDATION_POLICY_DOCS,
                                   *INSTALLER_DOC_TEXT, *REPORT_DOCS, *WIRING_JSON, *ARCH_TESTS[:-1]]):
            destination = self.root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(SCRIPTS.parent.parent / name, destination)
        self.commit()

    def export(self, argv=None, **kwargs):
        return super().export(argv=VALIDATION_POLICY_COMMAND if argv is None else argv, **kwargs)

    def selected_bytes(self):
        return {name: (self.root / name).read_bytes()
                for name in ledger.input_paths(self.root, VALIDATION_POLICY_INPUTS)}

    def assert_inputs_unchanged(self, before):
        self.assertEqual(self.selected_bytes(), before, 'validation policy execution changed inputs')

    def execution(self, failure=None):
        before = self.selected_bytes()
        result = self.process(VALIDATION_POLICY_COMMAND)
        output = result.stdout + result.stderr
        counts = re.findall(r'Ran (\d+) tests? in ', output)
        self.assertEqual(len(counts), 1, 'validation policy execution count missing or ambiguous: ' + output)
        self.assertEqual(int(counts[0]), 1, 'validation policy execution count must be one: ' + output)
        if failure is None:
            self.assertEqual(result.returncode, 0, output)
            self.assertRegex(output, r'\nOK\s*$')
        else:
            self.assertNotEqual(result.returncode, 0, output)
            self.assertIn('AssertionError', output)
            self.assertIn(VALIDATION_POLICY_COMMAND[2].split('.')[1], output)
            self.assertIn(failure, output)
            self.assertNotIn('ERROR:', output)
        self.assert_inputs_unchanged(before)
        return result

    def preflight(self):
        before = self.selected_bytes()
        self.execution()
        return before

    def edit_and_restore(self, name, check):
        path = self.root / name
        original = path.read_bytes() if path.exists() else None
        changed = (original or b'') + b'\n '
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(changed)
        try:
            self.assertNotEqual(original, changed)
            self.assertEqual(path.read_bytes(), changed)
            if name in VALIDATION_POLICY_DOCS:
                self.execution()  # Freshness edits must preserve the static assertions.
            check()
        finally:
            if original is None:
                path.unlink()
            else:
                path.write_bytes(original)

    def assert_prior_profiles(self):
        result = subprocess.run(
            ['git', 'show', '4b89221b6f1c416303452abd57fb4fb15816b2b3:.ai/scripts/assurance_inputs.py'],
            cwd=SCRIPTS.parent.parent, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        import ast
        baseline = next(ast.literal_eval(n.value) for n in ast.parse(result.stdout).body
                        if isinstance(n, ast.Assign)
                        and any(isinstance(t, ast.Name) and t.id == 'PROFILES' for t in n.targets))
        identities = ('python-runner-test', 'python-architecture-compatibility', 'python-harness-wiring',
                      'python-reviewer-report-contract', 'python-installer-doc-contract')
        self.assertEqual(tuple(p['id'] for p in baseline), identities)
        actual = self.module().PROFILES
        for expected in baseline:
            self.assertEqual(next(p for p in actual if p['id'] == expected['id']), expected)
            value = self.suggestion(argv=expected['argv'])
            self.assertEqual((value['profile_id'], value['argv'], value['inputs'], value['rationale']),
                             (expected['id'], expected['argv'], expected['inputs'], expected['rationale']))


class ValidationPolicyProfileTests(ValidationPolicyFixture):  # R1
    def test_exact_registration_and_prior_profiles(self):
        value = self.suggestion()
        self.assertEqual(value['profile_id'], 'python-validation-policy-contract')
        self.assertEqual(value['argv'], VALIDATION_POLICY_COMMAND)
        self.assert_prior_profiles()
        for argv in (VALIDATION_POLICY_COMMAND[:2], VALIDATION_POLICY_COMMAND[:2] + ['Relocation'],
                     VALIDATION_POLICY_COMMAND[:2] + ['Distribution.test_eval_and_installer_share_one_kit_list'],
                     VALIDATION_POLICY_COMMAND + ['-v'], [sys.executable, *VALIDATION_POLICY_COMMAND[1:]],
                     ['python3', './' + VALIDATION_POLICY_COMMAND[1], VALIDATION_POLICY_COMMAND[2]],
                     ['python3', '-m', 'unittest', 'discover', '-s', '.ai/scripts/tests',
                      '-p', 'test_lifecycle_conformance.py']):
            self.assertIn('exact command', self.refused(argv=argv)['reason'])
        self.refused(cwd=self.root / '.ai')


class ValidationPolicyExportTests(ValidationPolicyFixture):  # R3
    def test_readonly_formats_supplements_and_no_semantic_parsing(self):
        marker = self.root / 'executed'
        for name in VALIDATION_POLICY_TESTS:
            self.write(name, f'from pathlib import Path\nPath({str(marker)!r}).touch()\nraise RuntimeError("executed")\n')
        for name in VALIDATION_POLICY_DOCS:
            self.write(name, 'nonconforming static document')
        for name in ('space file.txt', 'second.txt'):
            self.write(name, 'supplement')
        before = snapshot(self.root)
        extra = ('space file.txt', 'second.txt')
        value = self.suggestion(extra=extra)
        text = self.export(extra=extra, json_output=False)
        self.assertEqual(text.returncode, 0, text.stderr)
        self.assertEqual(value['inputs'], VALIDATION_POLICY_INPUTS + list(extra))
        self.assertEqual(value['lifecycle_inputs_argv'], ['--inputs', *value['inputs']])
        for item in (value['profile_id'], value['inputs_line'], json.dumps(VALIDATION_POLICY_COMMAND),
                     json.dumps(value['lifecycle_inputs_argv']), *value['rationale'].values(), *value['limitations']):
            self.assertIn(item, text.stdout)
        raw = ('- POLICY-R1: The check MUST pass.\n  - Verify: `'
               + ' '.join(VALIDATION_POLICY_COMMAND) + '`\n' + value['inputs_line'] + '\n')
        parsed = assurance.parse('POLICY-R1', 'capabilities/policy.md', raw, root=self.root)
        self.assertIsNone(parsed.invalid)
        self.assertEqual(list(parsed.globs), value['inputs'])
        self.assertTrue(value['review_required'])
        self.assertEqual(snapshot(self.root), before)
        self.assertFalse(marker.exists())

    def test_required_literals_and_unsafe_boundaries_refuse(self):
        for name in [*VALIDATION_POLICY_TESTS, *VALIDATION_POLICY_DOCS]:
            path = self.root / name
            original = path.read_bytes()
            path.unlink()
            try:
                self.refused()
            finally:
                path.write_bytes(original)
        name = VALIDATION_POLICY_DOCS[0]
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
        try:
            self.refused()
        finally:
            path.unlink()
            path.write_bytes(original)
        for extra in ('!README.md', '../x', '/etc/passwd', '', 'x`bad', '--other-option'):
            self.refused(extra=(extra,))


# Fixed expectations for the independently inspected shared eager/called setup.
VALIDATION_POLICY_SETUP_PINS = {
    '.ai/scripts/tests/test_lifecycle_conformance.py': '50977be9e0fc2636e75b83eba96f267339efd91e89f3d035690d0a0e24e8a02b',
    '.ai/scripts/tests/disk_tmp.py': 'fff9eed82f770bce05c477c507ad3c00dae4a16c216521b004646837c0bdd02f',
    '.ai/scripts/scratch.py': '523cbb977066b41423329249d132d2dc27a2f963db15b71489c2579fdb093060',
    '.ai/scripts/lifecycle.py': '048f391c166ffb58b8ba1d769ca287adc78d5c155a28bebba043e0d93a30e1ca',
    '.ai/scripts/review_guard.py': '2d806b1c16cb028a8b2197aec8881b0a4db1a962125f5a5d50a8599b01c45d69',
    '.ai/scripts/ledger.py': 'fc2423e775969cdc28173f970d7c676e6ad254e8f5e120abb89a5c1244b80cab',
}


class ValidationPolicyDependencyTests(ValidationPolicyFixture):  # R2
    def test_order_scope_and_independent_oracle(self):
        value = self.suggestion()
        actual_setup = {p: report_setup_digest(self.root / p) for p in VALIDATION_POLICY_SETUP_PINS}
        self.assertEqual(actual_setup, VALIDATION_POLICY_SETUP_PINS,
                         'review validation policy dependency boundary: ' + repr(actual_setup))
        self.assertEqual(value['inputs'], VALIDATION_POLICY_INPUTS)
        self.assertEqual(set(value['rationale']), set(VALIDATION_POLICY_INPUTS))
        for name, terms in {
            '.ai/scripts/**': ('conservative', 'import', 'lazy'),
            '!.ai/scripts/tests/**': ('exclude',),
            VALIDATION_POLICY_TESTS[0]: ('method', 'static'), VALIDATION_POLICY_TESTS[1]: ('helper',),
            **{p: ('direct',) for p in VALIDATION_POLICY_DOCS},
        }.items():
            for term in terms:
                self.assertIn(term, value['rationale'][name].lower())
        included = ['.ai/scripts/future_policy.py', '.ai/scripts/assets/policy.txt']
        excluded = ['.ai/scripts/tests/unrelated.py', 'unrelated.md',
                    *INSTALLER_DOC_TEXT, *REPORT_DOCS, *WIRING_JSON, *ARCH_TESTS[:-1]]
        for name in included + excluded[:2]:
            self.write(name, '# independent inventory fixture\n')
        selected = set(ledger.input_paths(self.root, value['inputs']))
        self.assertTrue(set([*VALIDATION_POLICY_TESTS, *VALIDATION_POLICY_DOCS,
                             *VALIDATION_POLICY_IMPORTS, *included]).issubset(selected))
        self.assertFalse(set(excluded) & selected)
        import ast
        source = (self.root / VALIDATION_POLICY_TESTS[0]).read_text()
        cls = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef) and n.name == 'Relocation')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                      and n.name == VALIDATION_POLICY_COMMAND[2].split('.')[1])
        reviewed = '\n'.join(source.splitlines()[method.lineno - 1:method.end_lineno])
        self.assertEqual(hashlib.sha256(reviewed.encode()).hexdigest(),
                         'f3d3bf30e9c12ca4ba15ae57ba4a78de1bc01aa61b8e39b009e0a9a5d1471ed8',
                         'review validation policy selected method boundary')
        reads = {n.args[0].value for n in ast.walk(method) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Name) and n.func.id == 'text'
                 and n.args and isinstance(n.args[0], ast.Constant)}
        self.assertEqual(reads, set(VALIDATION_POLICY_DOCS))

    def test_reachable_added_dependencies_require_review(self):
        variants = [(p, ()) for p in VALIDATION_POLICY_SETUP_PINS]
        variants += [(VALIDATION_POLICY_TESTS[0], ('Relocation', VALIDATION_POLICY_COMMAND[2].split('.')[1])),
                     (VALIDATION_POLICY_TESTS[0], ('text',)),
                     ('.ai/scripts/scratch.py', ('require_disk',)),
                     ('.ai/scripts/lifecycle.py', ('lazy',)),
                     ('.ai/scripts/review_guard.py', ('protected',)),
                     ('.ai/scripts/review_guard.py', ('protected', 'decorate')),
                     (VALIDATION_POLICY_TESTS[0], ('import-helper',))]
        self.assertEqual(len(variants), 13)
        for name, body in variants:
            with self.subTest(name=name, body=body):
                case = ValidationPolicyDependencyTests('test_order_scope_and_independent_oracle')
                setup = case.setUp

                def mutated_setup():
                    setup()
                    import ast
                    path = case.root / name
                    source = path.read_text()
                    tree = ast.parse(source)
                    addition = '__import__("pathlib").Path("unrelated.md").read_text()\n'
                    if body == ('import-helper',):
                        case.write('.ai/scripts/tests/unreviewed_policy_helper.py', addition)
                        addition = 'import unreviewed_policy_helper\n'
                    if body and body != ('import-helper',):
                        node = tree
                        for part in body:
                            node = next(n for n in node.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))
                                        and n.name == part)
                        first = node.body[0]
                        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                                and isinstance(first.value.value, str):
                            after = first.end_lineno
                        else:
                            after = min([first.lineno, *[n.lineno for n in
                                         getattr(first, 'decorator_list', [])]]) - 1
                        addition = ' ' * first.col_offset + addition
                    else:
                        after = max(n.end_lineno for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom)))
                    lines = source.splitlines(keepends=True)
                    changed = ''.join(lines[:after]) + addition + ''.join(lines[after:])
                    path.write_text(changed)
                    case.assertNotEqual(source, changed)
                    case.assertEqual(path.read_text(), changed)
                    case.assertNotIn('unrelated.md', ledger.input_paths(case.root, VALIDATION_POLICY_INPUTS))
                    missing = case.process(VALIDATION_POLICY_COMMAND)
                    case.assertNotEqual(missing.returncode, 0)
                    case.assertIn('FileNotFoundError', missing.stdout + missing.stderr)
                    case.assertIn('unrelated.md', missing.stdout + missing.stderr)
                    case.write('unrelated.md', 'new excluded dependency')
                    case.execution()

                case.setUp = mutated_setup
                result = unittest.TestResult()
                case.run(result)
                self.assertEqual(result.testsRun, 1)
                self.assertFalse(result.errors, result.errors)
                self.assertTrue(result.failures, 'unreviewed validation policy dependency survived: ' + repr((name, body)))
                self.assertIn('review validation policy dependency boundary',
                              '\n'.join(detail for _, detail in result.failures))


class ValidationPolicyCompatibilityTests(ValidationPolicyFixture):  # R4
    def test_advisory_guide_and_existing_contracts(self):
        self.assert_prior_profiles()
        self.assertIsNone(ledger.default_inputs(VALIDATION_POLICY_COMMAND))
        self.assertEqual(ledger.default_inputs(COMMAND), ('python-tests', ['**']))
        for argv in (['python3', '-m', 'unittest', 'discover', '-s', '.ai/scripts/tests'],
                     *[['python3', '.ai/scripts/run_tests.py', '-j', str(n)] for n in (1, 8, 32)]):
            self.refused(argv=argv)
        value = self.suggestion()
        self.assertNotIn(EXCLUDE, value['inputs'])
        self.assertEqual(value['schema_version'], 1)
        self.assertTrue(value['review_required'])
        self.assertIn('runtime', ' '.join(value['limitations']).lower())
        guide = (self.root / ARCH_GUIDE).read_text()
        for phrase in ('python-validation-policy-contract', ' '.join(VALIDATION_POLICY_COMMAND),
                       'static', 'conservative', 'explicit', 'manual', 'text placement',
                       'policy enforcement', *VALIDATION_POLICY_DOCS):
            self.assertIn(phrase, guide)


class ValidationPolicyFrameworkEndToEndTests(ValidationPolicyFixture):  # R5
    def record(self):
        value = self.suggestion()
        before = self.preflight()
        self.lc('tier', 'L1', '--reason', 'static validation policy framework fixture')
        self.lc('run', 'validation-policy', *value['lifecycle_inputs_argv'], '--', *VALIDATION_POLICY_COMMAND)
        self.assert_inputs_unchanged(before)
        import lifecycle
        entry = lifecycle.load(self.root)['ledger'][-1]
        self.assertEqual((entry['argv'], entry['inputs'], entry['exit']),
                         (VALIDATION_POLICY_COMMAND, value['inputs'], 0))
        self.assertIn('REUSE', self.lc('reuse', 'validation-policy'))

    def test_each_input_and_addition_invalidates(self):
        self.record()
        for name in ('.ai/scripts/tests/unrelated.py', 'unrelated.md'):
            self.edit_and_restore(name, lambda: self.assertIn('REUSE', self.lc('reuse', 'validation-policy')))
            self.assertIn('REUSE', self.lc('reuse', 'validation-policy'))
        for name in [*VALIDATION_POLICY_DOCS, *VALIDATION_POLICY_TESTS,
                     '.ai/scripts/review_guard.py', '.ai/scripts/new_policy.py']:
            with self.subTest(name=name):
                def stale():
                    result = self.process([sys.executable, '.ai/scripts/lifecycle.py', 'reuse', 'validation-policy'])
                    self.assertEqual(result.returncode, 1, 'missing validation policy freshness invalidation: ' + name)
                    self.assertIn('RERUN', result.stdout)
                self.edit_and_restore(name, stale)
                self.assertIn('REUSE', self.lc('reuse', 'validation-policy'))
        self.assertFalse((self.root / 'knowledge').exists())


class ValidationPolicyFailureTests(ValidationPolicyFixture):  # R5
    def test_ten_static_failures_fail_actual_command(self):
        variants = [(VALIDATION_POLICY_DOCS[0], term, False)
                    for term in ('.ai/validation-policy.md', 'MUST load it by section')]
        variants += [(VALIDATION_POLICY_DOCS[1], term, False) for term in VALIDATION_POLICY_RULES]
        variants += [(VALIDATION_POLICY_DOCS[0], term, True) for term in VALIDATION_POLICY_RULES]
        self.assertEqual(len(variants), 10)
        for name, term, insertion in variants:
            with self.subTest(name=name, term=term, insertion=insertion):
                path = self.root / name
                original = path.read_bytes()
                token = term.encode()
                if insertion:
                    self.assertNotIn(token, original)
                    changed = original + b'\n' + token + b'\n'
                else:
                    self.assertIn(token, original)
                    changed = original.replace(token, b'removed')
                    self.assertNotIn(token, changed)
                path.write_bytes(changed)
                try:
                    self.assertNotEqual(original, changed)
                    self.assertEqual(path.read_bytes(), changed)
                    self.suggestion()
                    self.execution(failure='unexpectedly found in' if insertion else 'not found in')
                finally:
                    path.write_bytes(original)


class ValidationPolicyAdopterEndToEndTests(ValidationPolicyFixture):  # R6
    def test_explicit_adoption_freshness_identity_and_receipt(self):
        (self.root / '.agentic.json').unlink()
        self.lc('tier', 'L1', '--reason', 'static validation policy adopter fixture')
        result = self.process([sys.executable, '.ai/scripts/okf.py', 'init'])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.write('knowledge/project/sync-ignore', '*\n')
        value = self.suggestion()
        prefix = ('---\ntype: Capability\ntitle: Policy\nnamespace: POLICY\nstatus: draft\n---\n'
                  '# Policy\n\n## Requirements\n\n- POLICY-R1: The static check MUST pass.\n'
                  '  - Verify: `' + ' '.join(VALIDATION_POLICY_COMMAND) + '`\n')
        original = prefix + value['inputs_line'] + '\n'
        capability = self.write('knowledge/capabilities/policy.md', original)
        self.commit()

        def status():
            result = self.process([sys.executable, '.ai/scripts/lifecycle.py', 'assure', '--json'])
            data = json.loads(result.stdout)
            state = next(r['status'] for r in data['requirements'] if r['id'] == 'POLICY-R1')
            self.assertEqual(result.returncode, 0 if state == 'VERIFIED' else 1, result.stdout + result.stderr)
            return state

        self.assertEqual(status(), 'UNVERIFIED')
        before = self.preflight()
        self.lc('assure', '--run', 'POLICY-R1')
        self.assert_inputs_unchanged(before)
        self.assertEqual(status(), 'VERIFIED')
        for name in ('.ai/scripts/tests/unrelated.py', 'unrelated.md'):
            self.edit_and_restore(name, lambda: self.assertEqual(status(), 'VERIFIED'))
            self.assertEqual(status(), 'VERIFIED')
        for name in [*VALIDATION_POLICY_DOCS, *VALIDATION_POLICY_TESTS,
                     '.ai/scripts/review_guard.py', '.ai/scripts/new_policy.py']:
            with self.subTest(name=name):
                self.edit_and_restore(name, lambda: self.assertEqual(status(), 'STALE'))
                self.assertEqual(status(), 'VERIFIED')
        reordered = [*value['inputs'][:-2], value['inputs'][-1], value['inputs'][-2]]
        capability.write_text(prefix + '  - Inputs: ' + ' '.join('`' + p + '`' for p in reordered) + '\n')
        self.assertEqual(status(), 'UNVERIFIED')
        capability.write_text(original.replace(VALIDATION_POLICY_COMMAND[2] + '`', VALIDATION_POLICY_COMMAND[2] + ' -v`'))
        self.assertEqual(status(), 'UNVERIFIED')
        capability.write_text(original)
        self.assertEqual(status(), 'VERIFIED')
        entries = [e for p in (self.root / 'knowledge/history/lifecycle').glob('*.json')
                   for e in json.loads(p.read_text()).get('ledger', []) if e['label'] == 'req:POLICY-R1']
        self.assertEqual(entries[-1]['inputs'], VALIDATION_POLICY_INPUTS + [EXCLUDE])
        self.write('knowledge/history/lifecycle/extra-receipt.json', '{}\n')
        self.assertEqual(status(), 'VERIFIED')


class ValidationPolicyControlTests(ValidationPolicyFixture):  # R6
    def test_confirmed_broken_variants_fail_intended_criteria(self):
        method = 'test_each_input_and_addition_invalidates'
        variants = [(p, ValidationPolicyFrameworkEndToEndTests, method,
                     'missing validation policy freshness invalidation: ' + p) for p in VALIDATION_POLICY_DOCS]
        variants += [('loose', ValidationPolicyProfileTests, 'test_exact_registration_and_prior_profiles', '0 != 2'),
                     ('empty', ValidationPolicyFrameworkEndToEndTests, method, 'validation policy execution count must be one')]
        self.assertEqual(len(variants), 4)
        for variant, cls, test, criterion in variants:
            with self.subTest(variant=variant):
                case = cls(test)
                setup = case.setUp

                def mutated_setup():
                    setup()
                    path = case.root / '.ai/scripts/assurance_inputs.py'
                    original = path.read_text()
                    if variant in VALIDATION_POLICY_DOCS:
                        catalog = copy.deepcopy(case.module().PROFILES)
                        profile = next(p for p in catalog if p['id'] == 'python-validation-policy-contract')
                        profile['inputs'].remove(variant)
                        del profile['rationale'][variant]
                        replacement = (original.split('PROFILES = ', 1)[0] + 'PROFILES = ' + repr(catalog)
                                       + '\nLIMITATIONS =' + original.split('\nLIMITATIONS =', 1)[1])
                    elif variant == 'loose':
                        old = "p['argv'] == list(argv)"
                        case.assertEqual(original.count(old), 1)
                        replacement = original.replace(old, "p['argv'] == list(argv)[:len(p['argv'])]")
                    else:
                        path = case.root / VALIDATION_POLICY_TESTS[0]
                        original = path.read_text()
                        replacement = 'import sys\nimport unittest\nunittest.main(argv=[sys.argv[0]])\n'
                    path.write_text(replacement)
                    case.assertNotEqual(original, replacement, 'mutation was not applied')
                    case.assertEqual(path.read_text(), replacement, 'mutation bytes differ')
                    if variant in VALIDATION_POLICY_DOCS:
                        value = case.suggestion()
                        case.assertNotIn(variant, value['inputs'])
                        case.assertNotIn(variant, value['rationale'])
                    if variant == 'empty':
                        result = case.process(VALIDATION_POLICY_COMMAND)
                        case.assertRegex(result.stdout + result.stderr, r'Ran 0 tests? in ')

                case.setUp = mutated_setup
                result = unittest.TestResult()
                case.run(result)
                self.assertEqual(result.testsRun, 1)
                self.assertFalse(result.errors, result.errors)
                self.assertTrue(result.failures, 'broken validation policy variant survived: ' + variant)
                self.assertIn(criterion, '\n'.join(detail for _, detail in result.failures))


# Audit documentation: specification-5g.md R1-R6. Independent of PROFILES.
AUDIT_DOC_COMMAND = ['python3', '.ai/scripts/tests/test_lifecycle_conformance.py',
                     'Tiers.test_the_committed_audit_record_is_documented']
AUDIT_DOC_TESTS = [AUDIT_DOC_COMMAND[1], '.ai/scripts/tests/disk_tmp.py']
AUDIT_DOC_DOCS = ['.ai/lifecycle.md', '.ai/docs/lifecycle.md']
AUDIT_DOC_INPUTS = ['.ai/scripts/**', '!.ai/scripts/tests/**', *AUDIT_DOC_TESTS, *AUDIT_DOC_DOCS]
AUDIT_DOC_IMPORTS = ['.ai/scripts/' + name + '.py' for name in
                     ('scratch', 'lifecycle', 'review_guard', 'ledger', 'brownfield',
                      'okf', 'learning', 'scan', 'project_context', 'assurance')]
AUDIT_DOC_TOKENS = ('knowledge/history/lifecycle/', 'lifecycle.py audit')


class AuditDocFixture(Fixture):
    def setUp(self):
        super().setUp()
        # Prior-profile compatibility copies are not the selected read oracle.
        for name in dict.fromkeys([*AUDIT_DOC_TESTS, *AUDIT_DOC_DOCS, *VALIDATION_POLICY_DOCS,
                                   *INSTALLER_DOC_TEXT, *REPORT_DOCS, *WIRING_JSON, *ARCH_TESTS[:-1]]):
            destination = self.root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(SCRIPTS.parent.parent / name, destination)
        self.commit()

    def export(self, argv=None, **kwargs):
        return super().export(argv=AUDIT_DOC_COMMAND if argv is None else argv, **kwargs)

    def selected_bytes(self):
        return {name: (self.root / name).read_bytes()
                for name in ledger.input_paths(self.root, AUDIT_DOC_INPUTS)}

    def assert_inputs_unchanged(self, before):
        self.assertEqual(self.selected_bytes(), before, 'audit doc execution changed inputs')

    def execution(self, failure=None):
        before = self.selected_bytes()
        result = self.process(AUDIT_DOC_COMMAND)
        output = result.stdout + result.stderr
        counts = re.findall(r'Ran (\d+) tests? in ', output)
        self.assertEqual(len(counts), 1, 'audit doc execution count missing or ambiguous: ' + output)
        self.assertEqual(int(counts[0]), 1, 'audit doc execution count must be one: ' + output)
        if failure is None:
            self.assertEqual(result.returncode, 0, output)
            self.assertRegex(output, r'\nOK\s*$')
        else:
            self.assertNotEqual(result.returncode, 0, output)
            self.assertIn('AssertionError', output)
            self.assertIn(AUDIT_DOC_COMMAND[2].split('.')[1], output)
            self.assertIn(failure, output)
            self.assertNotIn('ERROR:', output)
        self.assert_inputs_unchanged(before)
        return result

    def preflight(self):
        before = self.selected_bytes()
        self.execution()
        return before

    def edit_and_restore(self, name, check):
        path = self.root / name
        original = path.read_bytes() if path.exists() else None
        changed = (original or b'') + b'\n '
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(changed)
        try:
            self.assertNotEqual(original, changed)
            self.assertEqual(path.read_bytes(), changed)
            if name in AUDIT_DOC_DOCS:
                self.execution()
            check()
        finally:
            if original is None:
                path.unlink()
            else:
                path.write_bytes(original)

    def assert_prior_profiles(self):
        result = subprocess.run(
            ['git', 'show', 'c50034260a8c7e8a5ff42b44296720081dc9c039:.ai/scripts/assurance_inputs.py'],
            cwd=SCRIPTS.parent.parent, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        import ast
        baseline = next(ast.literal_eval(n.value) for n in ast.parse(result.stdout).body
                        if isinstance(n, ast.Assign)
                        and any(isinstance(t, ast.Name) and t.id == 'PROFILES' for t in n.targets))
        identities = ('python-runner-test', 'python-architecture-compatibility', 'python-harness-wiring',
                      'python-reviewer-report-contract', 'python-installer-doc-contract',
                      'python-validation-policy-contract')
        self.assertEqual(tuple(p['id'] for p in baseline), identities)
        actual = self.module().PROFILES
        for expected in baseline:
            self.assertEqual(next(p for p in actual if p['id'] == expected['id']), expected)
            value = self.suggestion(argv=expected['argv'])
            self.assertEqual((value['profile_id'], value['argv'], value['inputs'], value['rationale']),
                             (expected['id'], expected['argv'], expected['inputs'], expected['rationale']))


class AuditDocProfileTests(AuditDocFixture):  # R1
    def test_exact_registration_and_prior_profiles(self):
        value = self.suggestion()
        self.assertEqual(value['profile_id'], 'python-audit-doc-contract')
        self.assertEqual(value['argv'], AUDIT_DOC_COMMAND)
        self.assert_prior_profiles()
        sibling = self.suggestion(argv=AUDIT_DOC_COMMAND[:2] + ['Tiers.test_analyze_and_converge_are_documented'])
        self.assertEqual(sibling['profile_id'], 'python-analysis-convergence-doc-contract')
        for argv in (AUDIT_DOC_COMMAND[:2], AUDIT_DOC_COMMAND[:2] + ['Tiers'],
                     AUDIT_DOC_COMMAND + ['-v'], [sys.executable, *AUDIT_DOC_COMMAND[1:]],
                     ['python3', './' + AUDIT_DOC_COMMAND[1], AUDIT_DOC_COMMAND[2]],
                     ['python3', '-m', 'unittest', 'discover', '-s', '.ai/scripts/tests',
                      '-p', 'test_lifecycle_conformance.py']):
            self.assertIn('exact command', self.refused(argv=argv)['reason'])
        self.refused(cwd=self.root / '.ai')


class AuditDocExportTests(AuditDocFixture):  # R3
    def test_readonly_formats_supplements_and_no_semantic_parsing(self):
        marker = self.root / 'executed'
        for name in AUDIT_DOC_TESTS:
            self.write(name, f'from pathlib import Path\nPath({str(marker)!r}).touch()\nraise RuntimeError("executed")\n')
        for name in AUDIT_DOC_DOCS:
            self.write(name, 'nonconforming static document')
        for name in ('space file.txt', 'second.txt'):
            self.write(name, 'supplement')
        before = snapshot(self.root)
        extra = ('space file.txt', 'second.txt')
        value = self.suggestion(extra=extra)
        text = self.export(extra=extra, json_output=False)
        self.assertEqual(text.returncode, 0, text.stderr)
        self.assertEqual(value['inputs'], AUDIT_DOC_INPUTS + list(extra))
        self.assertEqual(value['lifecycle_inputs_argv'], ['--inputs', *value['inputs']])
        for item in (value['profile_id'], value['inputs_line'], json.dumps(AUDIT_DOC_COMMAND),
                     json.dumps(value['lifecycle_inputs_argv']), *value['rationale'].values(), *value['limitations']):
            self.assertIn(item, text.stdout)
        raw = ('- AUDITDOC-R1: The check MUST pass.\n  - Verify: `'
               + ' '.join(AUDIT_DOC_COMMAND) + '`\n' + value['inputs_line'] + '\n')
        parsed = assurance.parse('AUDITDOC-R1', 'capabilities/audit-doc.md', raw, root=self.root)
        self.assertIsNone(parsed.invalid)
        self.assertEqual(list(parsed.globs), value['inputs'])
        self.assertTrue(value['review_required'])
        self.assertEqual(snapshot(self.root), before)
        self.assertFalse(marker.exists())

    def test_required_literals_and_unsafe_boundaries_refuse(self):
        for name in [*AUDIT_DOC_TESTS, *AUDIT_DOC_DOCS]:
            path = self.root / name
            original = path.read_bytes()
            path.unlink()
            try:
                self.refused()
            finally:
                path.write_bytes(original)
        name = AUDIT_DOC_DOCS[1]
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
        try:
            self.refused()
        finally:
            path.unlink()
            path.write_bytes(original)
        for extra in ('!README.md', '../x', '/etc/passwd', '', 'x`bad', '--other-option'):
            self.refused(extra=(extra,))


# Independently reviewed shared initialization and called-body boundary.
AUDIT_DOC_SETUP_PINS = {
    '.ai/scripts/tests/test_lifecycle_conformance.py': '50977be9e0fc2636e75b83eba96f267339efd91e89f3d035690d0a0e24e8a02b',
    '.ai/scripts/tests/disk_tmp.py': 'fff9eed82f770bce05c477c507ad3c00dae4a16c216521b004646837c0bdd02f',
    '.ai/scripts/scratch.py': '523cbb977066b41423329249d132d2dc27a2f963db15b71489c2579fdb093060',
    '.ai/scripts/lifecycle.py': '048f391c166ffb58b8ba1d769ca287adc78d5c155a28bebba043e0d93a30e1ca',
    '.ai/scripts/review_guard.py': '2d806b1c16cb028a8b2197aec8881b0a4db1a962125f5a5d50a8599b01c45d69',
    '.ai/scripts/ledger.py': 'fc2423e775969cdc28173f970d7c676e6ad254e8f5e120abb89a5c1244b80cab',
}


class AuditDocDependencyTests(AuditDocFixture):  # R2
    def test_order_scope_and_independent_oracle(self):
        value = self.suggestion()
        actual_setup = {p: report_setup_digest(self.root / p) for p in AUDIT_DOC_SETUP_PINS}
        self.assertEqual(actual_setup, AUDIT_DOC_SETUP_PINS,
                         'review audit doc dependency boundary: ' + repr(actual_setup))
        self.assertEqual(value['inputs'], AUDIT_DOC_INPUTS)
        self.assertEqual(set(value['rationale']), set(AUDIT_DOC_INPUTS))
        for name, terms in {
            '.ai/scripts/**': ('conservative', 'import', 'lazy'),
            '!.ai/scripts/tests/**': ('exclude',),
            AUDIT_DOC_TESTS[0]: ('method', 'static'), AUDIT_DOC_TESTS[1]: ('helper',),
            **{p: ('direct',) for p in AUDIT_DOC_DOCS},
        }.items():
            for term in terms:
                self.assertIn(term, value['rationale'][name].lower())
        included = ['.ai/scripts/future_audit.py', '.ai/scripts/assets/audit.txt']
        excluded = ['.ai/scripts/tests/unrelated.py', 'unrelated.md', *VALIDATION_POLICY_DOCS,
                    *INSTALLER_DOC_TEXT, *[p for p in REPORT_DOCS if p not in AUDIT_DOC_DOCS],
                    *WIRING_JSON, *ARCH_TESTS[:-1]]
        for name in included + excluded[:2]:
            self.write(name, '# independent inventory fixture\n')
        selected = set(ledger.input_paths(self.root, value['inputs']))
        self.assertTrue(set([*AUDIT_DOC_TESTS, *AUDIT_DOC_DOCS,
                             *AUDIT_DOC_IMPORTS, *included]).issubset(selected))
        self.assertFalse(set(excluded) & selected)
        import ast
        source = (self.root / AUDIT_DOC_TESTS[0]).read_text()
        cls = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef) and n.name == 'Tiers')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                      and n.name == AUDIT_DOC_COMMAND[2].split('.')[1])
        reviewed = '\n'.join(source.splitlines()[method.lineno - 1:method.end_lineno])
        self.assertEqual(hashlib.sha256(reviewed.encode()).hexdigest(),
                         'd1d692f3493f461404dc0d47826d785b950bccc774a175d96c61b14330c525ef',
                         'review audit doc selected method boundary')
        self.assertEqual(len(method.body), 1)
        loop = method.body[0]
        self.assertIsInstance(loop, ast.For)
        self.assertIsInstance(loop.iter, ast.Tuple)
        reads = ast.literal_eval(loop.iter)
        self.assertEqual(list(reads), AUDIT_DOC_DOCS)
        self.assertIsInstance(loop.target, ast.Name)
        calls = [n for n in ast.walk(method) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Name) and n.func.id == 'text']
        self.assertEqual(len(calls), 2)
        for call in calls:
            self.assertEqual(len(call.args), 1)
            self.assertIsInstance(call.args[0], ast.Name)
            self.assertEqual(call.args[0].id, loop.target.id)

    def test_reachable_added_dependencies_require_review(self):
        variants = [(p, ()) for p in AUDIT_DOC_SETUP_PINS]
        variants += [(AUDIT_DOC_TESTS[0], ('Tiers', AUDIT_DOC_COMMAND[2].split('.')[1])),
                     (AUDIT_DOC_TESTS[0], ('text',)),
                     ('.ai/scripts/scratch.py', ('require_disk',)),
                     ('.ai/scripts/lifecycle.py', ('lazy',)),
                     ('.ai/scripts/review_guard.py', ('protected',)),
                     ('.ai/scripts/review_guard.py', ('protected', 'decorate')),
                     (AUDIT_DOC_TESTS[0], ('import-helper',))]
        self.assertEqual(len(variants), 13)
        for name, body in variants:
            with self.subTest(name=name, body=body):
                case = AuditDocDependencyTests('test_order_scope_and_independent_oracle')
                setup = case.setUp

                def mutated_setup():
                    setup()
                    import ast
                    path = case.root / name
                    source = path.read_text()
                    tree = ast.parse(source)
                    addition = '__import__("pathlib").Path("unrelated.md").read_text()\n'
                    if body == ('import-helper',):
                        case.write('.ai/scripts/tests/unreviewed_audit_helper.py', addition)
                        addition = 'import unreviewed_audit_helper\n'
                    if body and body != ('import-helper',):
                        node = tree
                        for part in body:
                            node = next(n for n in node.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))
                                        and n.name == part)
                        first = node.body[0]
                        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                                and isinstance(first.value.value, str):
                            after = first.end_lineno
                        else:
                            after = min([first.lineno, *[n.lineno for n in
                                         getattr(first, 'decorator_list', [])]]) - 1
                        addition = ' ' * first.col_offset + addition
                    else:
                        after = max(n.end_lineno for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom)))
                    lines = source.splitlines(keepends=True)
                    changed = ''.join(lines[:after]) + addition + ''.join(lines[after:])
                    path.write_text(changed)
                    case.assertNotEqual(source, changed)
                    case.assertEqual(path.read_text(), changed)
                    case.assertNotIn('unrelated.md', ledger.input_paths(case.root, AUDIT_DOC_INPUTS))
                    missing = case.process(AUDIT_DOC_COMMAND)
                    case.assertNotEqual(missing.returncode, 0)
                    case.assertIn('FileNotFoundError', missing.stdout + missing.stderr)
                    case.assertIn('unrelated.md', missing.stdout + missing.stderr)
                    case.write('unrelated.md', 'new excluded dependency')
                    case.execution()

                case.setUp = mutated_setup
                result = unittest.TestResult()
                case.run(result)
                self.assertEqual(result.testsRun, 1)
                self.assertFalse(result.errors, result.errors)
                self.assertTrue(result.failures, 'unreviewed audit doc dependency survived: ' + repr((name, body)))
                self.assertIn('review audit doc dependency boundary',
                              '\n'.join(detail for _, detail in result.failures))


class AuditDocCompatibilityTests(AuditDocFixture):  # R4
    def test_advisory_guide_and_existing_contracts(self):
        self.assert_prior_profiles()
        self.assertIsNone(ledger.default_inputs(AUDIT_DOC_COMMAND))
        self.assertEqual(ledger.default_inputs(COMMAND), ('python-tests', ['**']))
        for argv in (['python3', '-m', 'unittest', 'discover', '-s', '.ai/scripts/tests'],
                     *[['python3', '.ai/scripts/run_tests.py', '-j', str(n)] for n in (1, 8, 32)]):
            self.refused(argv=argv)
        value = self.suggestion()
        self.assertNotIn(EXCLUDE, value['inputs'])
        self.assertEqual(value['schema_version'], 1)
        self.assertTrue(value['review_required'])
        self.assertIn('runtime', ' '.join(value['limitations']).lower())
        guide = (self.root / ARCH_GUIDE).read_text()
        for phrase in ('python-audit-doc-contract', ' '.join(AUDIT_DOC_COMMAND),
                       'static', 'conservative', 'explicit', 'manual', 'substring',
                       'tamper detection', *AUDIT_DOC_DOCS):
            self.assertIn(phrase, guide)


class AuditDocFrameworkEndToEndTests(AuditDocFixture):  # R5
    def record(self):
        value = self.suggestion()
        before = self.preflight()
        self.lc('tier', 'L1', '--reason', 'static audit doc framework fixture')
        self.lc('run', 'audit-doc', *value['lifecycle_inputs_argv'], '--', *AUDIT_DOC_COMMAND)
        self.assert_inputs_unchanged(before)
        import lifecycle
        entry = lifecycle.load(self.root)['ledger'][-1]
        self.assertEqual((entry['argv'], entry['inputs'], entry['exit']),
                         (AUDIT_DOC_COMMAND, value['inputs'], 0))
        self.assertIn('REUSE', self.lc('reuse', 'audit-doc'))

    def test_each_input_and_addition_invalidates(self):
        self.record()
        for name in ('.ai/scripts/tests/unrelated.py', 'unrelated.md'):
            self.edit_and_restore(name, lambda: self.assertIn('REUSE', self.lc('reuse', 'audit-doc')))
            self.assertIn('REUSE', self.lc('reuse', 'audit-doc'))
        for name in [*AUDIT_DOC_DOCS, *AUDIT_DOC_TESTS,
                     '.ai/scripts/review_guard.py', '.ai/scripts/new_audit.py']:
            with self.subTest(name=name):
                def stale():
                    result = self.process([sys.executable, '.ai/scripts/lifecycle.py', 'reuse', 'audit-doc'])
                    self.assertEqual(result.returncode, 1, 'missing audit doc freshness invalidation: ' + name)
                    self.assertIn('RERUN', result.stdout)
                self.edit_and_restore(name, stale)
                self.assertIn('REUSE', self.lc('reuse', 'audit-doc'))
        self.assertFalse((self.root / 'knowledge').exists())


class AuditDocFailureTests(AuditDocFixture):  # R5
    def test_four_static_failures_fail_actual_command(self):
        variants = [(name, term) for name in AUDIT_DOC_DOCS for term in AUDIT_DOC_TOKENS]
        self.assertEqual(len(variants), 4)
        for name, term in variants:
            with self.subTest(name=name, term=term):
                path = self.root / name
                original = path.read_bytes()
                token = term.encode()
                self.assertIn(token, original)
                changed = original.replace(token, b'removed')
                self.assertNotIn(token, changed)
                path.write_bytes(changed)
                try:
                    self.assertNotEqual(original, changed)
                    self.assertEqual(path.read_bytes(), changed)
                    self.suggestion()
                    self.execution(failure=repr(term) + ' not found in')
                finally:
                    path.write_bytes(original)


class AuditDocAdopterEndToEndTests(AuditDocFixture):  # R6
    def test_explicit_adoption_freshness_identity_and_receipt(self):
        (self.root / '.agentic.json').unlink()
        self.lc('tier', 'L1', '--reason', 'static audit doc adopter fixture')
        result = self.process([sys.executable, '.ai/scripts/okf.py', 'init'])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.write('knowledge/project/sync-ignore', '*\n')
        value = self.suggestion()
        prefix = ('---\ntype: Capability\ntitle: Audit documentation\nnamespace: AUDITDOC\nstatus: draft\n---\n'
                  '# Audit documentation\n\n## Requirements\n\n- AUDITDOC-R1: The static check MUST pass.\n'
                  '  - Verify: `' + ' '.join(AUDIT_DOC_COMMAND) + '`\n')
        original = prefix + value['inputs_line'] + '\n'
        capability = self.write('knowledge/capabilities/audit-doc.md', original)
        self.commit()

        def status():
            result = self.process([sys.executable, '.ai/scripts/lifecycle.py', 'assure', '--json'])
            data = json.loads(result.stdout)
            state = next(r['status'] for r in data['requirements'] if r['id'] == 'AUDITDOC-R1')
            self.assertEqual(result.returncode, 0 if state == 'VERIFIED' else 1, result.stdout + result.stderr)
            return state

        self.assertEqual(status(), 'UNVERIFIED')
        before = self.preflight()
        self.lc('assure', '--run', 'AUDITDOC-R1')
        self.assert_inputs_unchanged(before)
        self.assertEqual(status(), 'VERIFIED')
        for name in ('.ai/scripts/tests/unrelated.py', 'unrelated.md'):
            self.edit_and_restore(name, lambda: self.assertEqual(status(), 'VERIFIED'))
            self.assertEqual(status(), 'VERIFIED')
        for name in [*AUDIT_DOC_DOCS, *AUDIT_DOC_TESTS,
                     '.ai/scripts/review_guard.py', '.ai/scripts/new_audit.py']:
            with self.subTest(name=name):
                self.edit_and_restore(name, lambda: self.assertEqual(status(), 'STALE'))
                self.assertEqual(status(), 'VERIFIED')
        reordered = [*value['inputs'][:-2], value['inputs'][-1], value['inputs'][-2]]
        capability.write_text(prefix + '  - Inputs: ' + ' '.join('`' + p + '`' for p in reordered) + '\n')
        self.assertEqual(status(), 'UNVERIFIED')
        capability.write_text(original.replace(AUDIT_DOC_COMMAND[2] + '`', AUDIT_DOC_COMMAND[2] + ' -v`'))
        self.assertEqual(status(), 'UNVERIFIED')
        capability.write_text(original)
        self.assertEqual(status(), 'VERIFIED')
        entries = [e for p in (self.root / 'knowledge/history/lifecycle').glob('*.json')
                   for e in json.loads(p.read_text()).get('ledger', []) if e['label'] == 'req:AUDITDOC-R1']
        self.assertEqual((entries[-1]['argv'], entries[-1]['inputs'], entries[-1]['exit']),
                         (AUDIT_DOC_COMMAND, AUDIT_DOC_INPUTS + [EXCLUDE], 0))
        self.write('knowledge/history/lifecycle/extra-receipt.json', '{}\n')
        self.assertEqual(status(), 'VERIFIED')


class AuditDocControlTests(AuditDocFixture):  # R6
    def test_confirmed_broken_variants_fail_intended_criteria(self):
        method = 'test_each_input_and_addition_invalidates'
        variants = [(p, AuditDocFrameworkEndToEndTests, method,
                     'missing audit doc freshness invalidation: ' + p) for p in AUDIT_DOC_DOCS]
        variants += [('loose', AuditDocProfileTests, 'test_exact_registration_and_prior_profiles', '0 != 2'),
                     ('empty', AuditDocFrameworkEndToEndTests, method, 'audit doc execution count must be one')]
        self.assertEqual(len(variants), 4)
        for variant, cls, test, criterion in variants:
            with self.subTest(variant=variant):
                case = cls(test)
                setup = case.setUp

                def mutated_setup():
                    setup()
                    path = case.root / '.ai/scripts/assurance_inputs.py'
                    original = path.read_text()
                    if variant in AUDIT_DOC_DOCS:
                        catalog = copy.deepcopy(case.module().PROFILES)
                        profile = next(p for p in catalog if p['id'] == 'python-audit-doc-contract')
                        profile['inputs'].remove(variant)
                        del profile['rationale'][variant]
                        replacement = (original.split('PROFILES = ', 1)[0] + 'PROFILES = ' + repr(catalog)
                                       + '\nLIMITATIONS =' + original.split('\nLIMITATIONS =', 1)[1])
                    elif variant == 'loose':
                        old = "p['argv'] == list(argv)"
                        case.assertEqual(original.count(old), 1)
                        replacement = original.replace(old, "p['argv'] == list(argv)[:len(p['argv'])]")
                    else:
                        path = case.root / AUDIT_DOC_TESTS[0]
                        original = path.read_text()
                        replacement = 'import sys\nimport unittest\nunittest.main(argv=[sys.argv[0]])\n'
                    path.write_text(replacement)
                    case.assertNotEqual(original, replacement, 'mutation was not applied')
                    case.assertEqual(path.read_text(), replacement, 'mutation bytes differ')
                    if variant in AUDIT_DOC_DOCS:
                        value = case.suggestion()
                        case.assertNotIn(variant, value['inputs'])
                        case.assertNotIn(variant, value['rationale'])
                    if variant == 'empty':
                        result = case.process(AUDIT_DOC_COMMAND)
                        case.assertRegex(result.stdout + result.stderr, r'Ran 0 tests? in ')

                case.setUp = mutated_setup
                result = unittest.TestResult()
                case.run(result)
                self.assertEqual(result.testsRun, 1)
                self.assertFalse(result.errors, result.errors)
                self.assertTrue(result.failures, 'broken audit doc variant survived: ' + variant)
                self.assertIn(criterion, '\n'.join(detail for _, detail in result.failures))


# Analysis/convergence documentation: specification-5h.md R1-R6. Independent of PROFILES.
ANALYSIS_CONVERGENCE_DOC_COMMAND = ['python3', '.ai/scripts/tests/test_lifecycle_conformance.py',
                                    'Tiers.test_analyze_and_converge_are_documented']
ANALYSIS_CONVERGENCE_DOC_TESTS = [ANALYSIS_CONVERGENCE_DOC_COMMAND[1], '.ai/scripts/tests/disk_tmp.py']
ANALYSIS_CONVERGENCE_DOC_DOCS = ['.ai/lifecycle.md', '.ai/docs/lifecycle.md', '.ai/validation-policy.md']
ANALYSIS_CONVERGENCE_DOC_INPUTS = ['.ai/scripts/**', '!.ai/scripts/tests/**',
                                  *ANALYSIS_CONVERGENCE_DOC_TESTS, *ANALYSIS_CONVERGENCE_DOC_DOCS]
ANALYSIS_CONVERGENCE_DOC_IMPORTS = ['.ai/scripts/' + name + '.py' for name in
                                   ('scratch', 'lifecycle', 'review_guard', 'ledger', 'brownfield',
                                    'okf', 'learning', 'scan', 'project_context', 'assurance')]
ANALYSIS_CONVERGENCE_DOC_TOKENS = ('lifecycle.py analyze', 'lifecycle.py converge')
ANALYSIS_CONVERGENCE_DOC_PHRASE = 'cites a passing converge run of an identical command on the current tree'


class AnalysisConvergenceDocFixture(Fixture):
    def setUp(self):
        super().setUp()
        # Compatibility copies do not define the selected method's read oracle.
        for name in dict.fromkeys([*ANALYSIS_CONVERGENCE_DOC_TESTS, *ANALYSIS_CONVERGENCE_DOC_DOCS,
                                   *VALIDATION_POLICY_DOCS, *INSTALLER_DOC_TEXT, *REPORT_DOCS,
                                   *WIRING_JSON, *ARCH_TESTS[:-1]]):
            destination = self.root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(SCRIPTS.parent.parent / name, destination)
        self.commit()

    def export(self, argv=None, **kwargs):
        return super().export(argv=ANALYSIS_CONVERGENCE_DOC_COMMAND if argv is None else argv, **kwargs)

    def selected_bytes(self):
        return {name: (self.root / name).read_bytes()
                for name in ledger.input_paths(self.root, ANALYSIS_CONVERGENCE_DOC_INPUTS)}

    def assert_inputs_unchanged(self, before):
        self.assertEqual(self.selected_bytes(), before, 'analysis/convergence doc execution changed inputs')

    def execution(self, failure=None):
        before = self.selected_bytes()
        result = self.process(ANALYSIS_CONVERGENCE_DOC_COMMAND)
        output = result.stdout + result.stderr
        counts = re.findall(r'Ran (\d+) tests? in ', output)
        self.assertEqual(len(counts), 1, 'analysis/convergence doc execution count missing or ambiguous: ' + output)
        self.assertEqual(int(counts[0]), 1, 'analysis/convergence doc execution count must be one: ' + output)
        if failure is None:
            self.assertEqual(result.returncode, 0, output)
            self.assertRegex(output, r'\nOK\s*$')
        else:
            self.assertNotEqual(result.returncode, 0, output)
            self.assertIn('AssertionError', output)
            self.assertIn(ANALYSIS_CONVERGENCE_DOC_COMMAND[2].split('.')[1], output)
            self.assertIn(failure, output)
            self.assertNotIn('ERROR:', output)
        self.assert_inputs_unchanged(before)
        return result

    def preflight(self):
        before = self.selected_bytes()
        self.execution()
        return before

    def edit_and_restore(self, name, check):
        path = self.root / name
        original = path.read_bytes() if path.exists() else None
        changed = (original or b'') + b'\n '
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(changed)
        try:
            self.assertNotEqual(original, changed)
            self.assertEqual(path.read_bytes(), changed)
            if name in ANALYSIS_CONVERGENCE_DOC_DOCS:
                self.execution()
            check()
        finally:
            if original is None:
                path.unlink()
            else:
                path.write_bytes(original)

    def assert_prior_profiles(self):
        result = subprocess.run(
            ['git', 'show', '8cb4d804a620e0761c2bab45846e7cd62c98ddd4:.ai/scripts/assurance_inputs.py'],
            cwd=SCRIPTS.parent.parent, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        import ast
        baseline = next(ast.literal_eval(n.value) for n in ast.parse(result.stdout).body
                        if isinstance(n, ast.Assign)
                        and any(isinstance(t, ast.Name) and t.id == 'PROFILES' for t in n.targets))
        identities = ('python-runner-test', 'python-architecture-compatibility', 'python-harness-wiring',
                      'python-reviewer-report-contract', 'python-installer-doc-contract',
                      'python-validation-policy-contract', 'python-audit-doc-contract')
        self.assertEqual(tuple(p['id'] for p in baseline), identities)
        actual = self.module().PROFILES
        for expected in baseline:
            self.assertEqual(next(p for p in actual if p['id'] == expected['id']), expected)
            value = self.suggestion(argv=expected['argv'])
            self.assertEqual((value['profile_id'], value['argv'], value['inputs'], value['rationale']),
                             (expected['id'], expected['argv'], expected['inputs'], expected['rationale']))


class AnalysisConvergenceDocProfileTests(AnalysisConvergenceDocFixture):  # R1
    def test_exact_registration_and_prior_profiles(self):
        value = self.suggestion()
        self.assertEqual(value['profile_id'], 'python-analysis-convergence-doc-contract')
        self.assertEqual(value['argv'], ANALYSIS_CONVERGENCE_DOC_COMMAND)
        self.assert_prior_profiles()
        for argv in (ANALYSIS_CONVERGENCE_DOC_COMMAND[:2], ANALYSIS_CONVERGENCE_DOC_COMMAND[:2] + ['Tiers'],
                     ANALYSIS_CONVERGENCE_DOC_COMMAND[:2] + ['Tiers.test_tiers_match'],
                     ANALYSIS_CONVERGENCE_DOC_COMMAND + ['-v'],
                     [sys.executable, *ANALYSIS_CONVERGENCE_DOC_COMMAND[1:]],
                     ['python3', './' + ANALYSIS_CONVERGENCE_DOC_COMMAND[1], ANALYSIS_CONVERGENCE_DOC_COMMAND[2]],
                     ['python3', '-m', 'unittest', 'discover', '-s', '.ai/scripts/tests',
                      '-p', 'test_lifecycle_conformance.py']):
            self.assertIn('exact command', self.refused(argv=argv)['reason'])
        self.refused(cwd=self.root / '.ai')
        prior = AuditDocProfileTests('test_exact_registration_and_prior_profiles')
        result = unittest.TestResult()
        prior.run(result)
        self.assertEqual(result.testsRun, 1)
        self.assertTrue(result.wasSuccessful(), repr(result.errors + result.failures))


class AnalysisConvergenceDocExportTests(AnalysisConvergenceDocFixture):  # R3
    def test_readonly_formats_supplements_and_no_semantic_parsing(self):
        marker = self.root / 'executed'
        for name in ANALYSIS_CONVERGENCE_DOC_TESTS:
            self.write(name, f'from pathlib import Path\nPath({str(marker)!r}).touch()\nraise RuntimeError("executed")\n')
        for name in ANALYSIS_CONVERGENCE_DOC_DOCS:
            self.write(name, 'nonconforming static document')
        for name in ('space file.txt', 'second.txt'):
            self.write(name, 'supplement')
        before = snapshot(self.root)
        extra = ('space file.txt', 'second.txt')
        value = self.suggestion(extra=extra)
        text = self.export(extra=extra, json_output=False)
        self.assertEqual(text.returncode, 0, text.stderr)
        self.assertEqual(value['inputs'], ANALYSIS_CONVERGENCE_DOC_INPUTS + list(extra))
        self.assertEqual(value['lifecycle_inputs_argv'], ['--inputs', *value['inputs']])
        for item in (value['profile_id'], value['inputs_line'], json.dumps(ANALYSIS_CONVERGENCE_DOC_COMMAND),
                     json.dumps(value['lifecycle_inputs_argv']), *value['rationale'].values(), *value['limitations']):
            self.assertIn(item, text.stdout)
        raw = ('- ANALYSISDOC-R1: The check MUST pass.\n  - Verify: `'
               + ' '.join(ANALYSIS_CONVERGENCE_DOC_COMMAND) + '`\n' + value['inputs_line'] + '\n')
        parsed = assurance.parse('ANALYSISDOC-R1', 'capabilities/analysis-doc.md', raw, root=self.root)
        self.assertIsNone(parsed.invalid)
        self.assertEqual(list(parsed.globs), value['inputs'])
        self.assertTrue(value['review_required'])
        self.assertEqual(snapshot(self.root), before)
        self.assertFalse(marker.exists())

    def test_required_literals_and_unsafe_boundaries_refuse(self):
        for name in [*ANALYSIS_CONVERGENCE_DOC_TESTS, *ANALYSIS_CONVERGENCE_DOC_DOCS]:
            path = self.root / name
            original = path.read_bytes()
            path.unlink()
            try:
                self.refused()
            finally:
                path.write_bytes(original)
        name = ANALYSIS_CONVERGENCE_DOC_DOCS[1]
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
        try:
            self.refused()
        finally:
            path.unlink()
            path.write_bytes(original)
        for extra in ('!README.md', '../x', '/etc/passwd', '', 'x`bad', '--other-option'):
            self.refused(extra=(extra,))


# Shared setup/called bodies independently reviewed for the exact 5h method.
ANALYSIS_CONVERGENCE_DOC_SETUP_PINS = {
    '.ai/scripts/tests/test_lifecycle_conformance.py': '50977be9e0fc2636e75b83eba96f267339efd91e89f3d035690d0a0e24e8a02b',
    '.ai/scripts/tests/disk_tmp.py': 'fff9eed82f770bce05c477c507ad3c00dae4a16c216521b004646837c0bdd02f',
    '.ai/scripts/scratch.py': '523cbb977066b41423329249d132d2dc27a2f963db15b71489c2579fdb093060',
    '.ai/scripts/lifecycle.py': '048f391c166ffb58b8ba1d769ca287adc78d5c155a28bebba043e0d93a30e1ca',
    '.ai/scripts/review_guard.py': '2d806b1c16cb028a8b2197aec8881b0a4db1a962125f5a5d50a8599b01c45d69',
    '.ai/scripts/ledger.py': 'fc2423e775969cdc28173f970d7c676e6ad254e8f5e120abb89a5c1244b80cab',
}


class AnalysisConvergenceDocDependencyTests(AnalysisConvergenceDocFixture):  # R2
    def test_order_scope_and_independent_oracle(self):
        value = self.suggestion()
        actual_setup = {p: report_setup_digest(self.root / p) for p in ANALYSIS_CONVERGENCE_DOC_SETUP_PINS}
        self.assertEqual(actual_setup, ANALYSIS_CONVERGENCE_DOC_SETUP_PINS,
                         'review analysis/convergence doc dependency boundary: ' + repr(actual_setup))
        self.assertEqual(value['inputs'], ANALYSIS_CONVERGENCE_DOC_INPUTS)
        self.assertEqual(set(value['rationale']), set(ANALYSIS_CONVERGENCE_DOC_INPUTS))
        for name, terms in {
            '.ai/scripts/**': ('conservative', 'import', 'lazy'),
            '!.ai/scripts/tests/**': ('exclude',),
            ANALYSIS_CONVERGENCE_DOC_TESTS[0]: ('method', 'static'),
            ANALYSIS_CONVERGENCE_DOC_TESTS[1]: ('helper',),
            **{p: ('direct',) for p in ANALYSIS_CONVERGENCE_DOC_DOCS},
        }.items():
            for term in terms:
                self.assertIn(term, value['rationale'][name].lower())
        included = ['.ai/scripts/future_analysis.py', '.ai/scripts/assets/analysis.txt']
        compatibility = [*VALIDATION_POLICY_DOCS, *INSTALLER_DOC_TEXT, *REPORT_DOCS,
                         *WIRING_JSON, *ARCH_TESTS[:-1]]
        excluded = ['.ai/scripts/tests/unrelated.py', 'unrelated.md',
                    *[p for p in compatibility if p not in ANALYSIS_CONVERGENCE_DOC_DOCS]]
        for name in included + excluded[:2]:
            self.write(name, '# independent inventory fixture\n')
        selected = set(ledger.input_paths(self.root, value['inputs']))
        self.assertTrue(set([*ANALYSIS_CONVERGENCE_DOC_TESTS, *ANALYSIS_CONVERGENCE_DOC_DOCS,
                             *ANALYSIS_CONVERGENCE_DOC_IMPORTS, *included]).issubset(selected))
        self.assertFalse(set(excluded) & selected)
        import ast
        source = (self.root / ANALYSIS_CONVERGENCE_DOC_TESTS[0]).read_text()
        cls = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef) and n.name == 'Tiers')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                      and n.name == ANALYSIS_CONVERGENCE_DOC_COMMAND[2].split('.')[1])
        reviewed = '\n'.join(source.splitlines()[method.lineno - 1:method.end_lineno])
        self.assertEqual(hashlib.sha256(reviewed.encode()).hexdigest(),
                         'a372825d7faccafb93e10a5195829130e7db867fa932b767c2ed42e4c5512610',
                         'review analysis/convergence doc selected method boundary')
        self.assertEqual(len(method.body), 2)
        loop, separate = method.body
        self.assertIsInstance(loop, ast.For)
        self.assertIsInstance(loop.iter, ast.Tuple)
        loop_reads = ast.literal_eval(loop.iter)
        self.assertEqual(list(loop_reads), ANALYSIS_CONVERGENCE_DOC_DOCS)
        self.assertIsInstance(loop.target, ast.Name)
        loop_calls = [n for n in ast.walk(loop) if isinstance(n, ast.Call)
                      and isinstance(n.func, ast.Name) and n.func.id == 'text']
        self.assertEqual(len(loop_calls), 2)
        for call in loop_calls:
            self.assertEqual(len(call.args), 1)
            self.assertFalse(call.keywords)
            self.assertIsInstance(call.args[0], ast.Name)
            self.assertEqual(call.args[0].id, loop.target.id)
        literal_calls = [n for n in ast.walk(separate) if isinstance(n, ast.Call)
                         and isinstance(n.func, ast.Name) and n.func.id == 'text']
        self.assertEqual(len(literal_calls), 1)
        self.assertEqual(len(literal_calls[0].args), 1)
        self.assertFalse(literal_calls[0].keywords)
        literal_reads = [ast.literal_eval(literal_calls[0].args[0])]
        self.assertEqual(literal_reads, ['.ai/validation-policy.md'])
        self.assertEqual(list(dict.fromkeys([*loop_reads, *literal_reads])), ANALYSIS_CONVERGENCE_DOC_DOCS)
        all_calls = [n for n in ast.walk(method) if isinstance(n, ast.Call)
                     and isinstance(n.func, ast.Name) and n.func.id == 'text']
        self.assertEqual(len(all_calls), len(loop_calls) + len(literal_calls))

    def test_reachable_added_dependencies_require_review(self):
        variants = [(p, ()) for p in ANALYSIS_CONVERGENCE_DOC_SETUP_PINS]
        variants += [(ANALYSIS_CONVERGENCE_DOC_TESTS[0], ('Tiers', ANALYSIS_CONVERGENCE_DOC_COMMAND[2].split('.')[1])),
                     (ANALYSIS_CONVERGENCE_DOC_TESTS[0], ('text',)),
                     ('.ai/scripts/scratch.py', ('require_disk',)),
                     ('.ai/scripts/lifecycle.py', ('lazy',)),
                     ('.ai/scripts/review_guard.py', ('protected',)),
                     ('.ai/scripts/review_guard.py', ('protected', 'decorate')),
                     (ANALYSIS_CONVERGENCE_DOC_TESTS[0], ('import-helper',))]
        self.assertEqual(len(variants), 13)
        for name, body in variants:
            with self.subTest(name=name, body=body):
                case = AnalysisConvergenceDocDependencyTests('test_order_scope_and_independent_oracle')
                setup = case.setUp

                def mutated_setup():
                    setup()
                    import ast
                    path = case.root / name
                    source = path.read_text()
                    tree = ast.parse(source)
                    addition = '__import__("pathlib").Path("unrelated.md").read_text()\n'
                    if body == ('import-helper',):
                        helper = '.ai/scripts/tests/unreviewed_analysis_helper.py'
                        case.write(helper, addition)
                        case.assertNotIn(helper, ledger.input_paths(case.root, ANALYSIS_CONVERGENCE_DOC_INPUTS))
                        addition = 'import unreviewed_analysis_helper\n'
                    if body and body != ('import-helper',):
                        node = tree
                        for part in body:
                            node = next(n for n in node.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))
                                        and n.name == part)
                        first = node.body[0]
                        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                                and isinstance(first.value.value, str):
                            after = first.end_lineno
                        else:
                            after = min([first.lineno, *[n.lineno for n in
                                         getattr(first, 'decorator_list', [])]]) - 1
                        addition = ' ' * first.col_offset + addition
                    else:
                        after = max(n.end_lineno for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom)))
                    lines = source.splitlines(keepends=True)
                    changed = ''.join(lines[:after]) + addition + ''.join(lines[after:])
                    path.write_text(changed)
                    case.assertNotEqual(source, changed)
                    case.assertEqual(path.read_text(), changed)
                    case.assertNotIn('unrelated.md', ledger.input_paths(case.root, ANALYSIS_CONVERGENCE_DOC_INPUTS))
                    missing = case.process(ANALYSIS_CONVERGENCE_DOC_COMMAND)
                    case.assertNotEqual(missing.returncode, 0)
                    case.assertIn('FileNotFoundError', missing.stdout + missing.stderr)
                    case.assertIn('unrelated.md', missing.stdout + missing.stderr)
                    case.write('unrelated.md', 'new excluded dependency')
                    case.execution()

                case.setUp = mutated_setup
                result = unittest.TestResult()
                case.run(result)
                self.assertEqual(result.testsRun, 1)
                self.assertFalse(result.errors, result.errors)
                self.assertEqual(len(result.failures), 1, 'unreviewed dependency survived: ' + repr((name, body)))
                self.assertIn('review analysis/convergence doc dependency boundary', result.failures[0][1])


class AnalysisConvergenceDocCompatibilityTests(AnalysisConvergenceDocFixture):  # R4
    def test_advisory_guide_and_existing_contracts(self):
        self.assert_prior_profiles()
        self.assertIsNone(ledger.default_inputs(ANALYSIS_CONVERGENCE_DOC_COMMAND))
        self.assertEqual(ledger.default_inputs(COMMAND), ('python-tests', ['**']))
        for argv in (['python3', '-m', 'unittest', 'discover', '-s', '.ai/scripts/tests'],
                     *[['python3', '.ai/scripts/run_tests.py', '-j', str(n)] for n in (1, 8, 32)]):
            self.refused(argv=argv)
        value = self.suggestion()
        self.assertNotIn(EXCLUDE, value['inputs'])
        self.assertEqual(value['schema_version'], 1)
        self.assertTrue(value['review_required'])
        self.assertIn('runtime', ' '.join(value['limitations']).lower())
        guide = (self.root / ARCH_GUIDE).read_text()
        for phrase in ('python-analysis-convergence-doc-contract', ' '.join(ANALYSIS_CONVERGENCE_DOC_COMMAND),
                       'static', 'conservative', 'explicit', 'manual', 'substring',
                       'separate literal', 'seven', 'section placement', 'evidence matching',
                       *ANALYSIS_CONVERGENCE_DOC_DOCS):
            self.assertIn(phrase, guide)


class AnalysisConvergenceDocFrameworkEndToEndTests(AnalysisConvergenceDocFixture):  # R5
    def record(self):
        value = self.suggestion()
        before = self.preflight()
        self.lc('tier', 'L1', '--reason', 'static analysis/convergence doc framework fixture')
        self.lc('run', 'analysis-doc', *value['lifecycle_inputs_argv'], '--', *ANALYSIS_CONVERGENCE_DOC_COMMAND)
        self.assert_inputs_unchanged(before)
        import lifecycle
        entry = lifecycle.load(self.root)['ledger'][-1]
        self.assertEqual((entry['argv'], entry['inputs'], entry['exit']),
                         (ANALYSIS_CONVERGENCE_DOC_COMMAND, value['inputs'], 0))
        self.assertIn('REUSE', self.lc('reuse', 'analysis-doc'))

    def test_each_input_and_addition_invalidates(self):
        self.record()
        for name in ('.ai/scripts/tests/unrelated.py', 'unrelated.md'):
            self.edit_and_restore(name, lambda: self.assertIn('REUSE', self.lc('reuse', 'analysis-doc')))
            self.assertIn('REUSE', self.lc('reuse', 'analysis-doc'))
        for name in [*ANALYSIS_CONVERGENCE_DOC_DOCS, *ANALYSIS_CONVERGENCE_DOC_TESTS,
                     '.ai/scripts/review_guard.py', '.ai/scripts/new_analysis.py']:
            with self.subTest(name=name):
                def stale():
                    result = self.process([sys.executable, '.ai/scripts/lifecycle.py', 'reuse', 'analysis-doc'])
                    self.assertEqual(result.returncode, 1, 'missing analysis/convergence doc freshness invalidation: ' + name)
                    self.assertIn('RERUN', result.stdout)
                self.edit_and_restore(name, stale)
                self.assertIn('REUSE', self.lc('reuse', 'analysis-doc'))
        self.assertFalse((self.root / 'knowledge').exists())


class AnalysisConvergenceDocFailureTests(AnalysisConvergenceDocFixture):  # R5
    def test_seven_static_failures_fail_actual_command(self):
        variants = [(name, term) for name in ANALYSIS_CONVERGENCE_DOC_DOCS
                    for term in ANALYSIS_CONVERGENCE_DOC_TOKENS]
        variants.append(('.ai/validation-policy.md', ANALYSIS_CONVERGENCE_DOC_PHRASE))
        self.assertEqual(len(variants), 7)
        for name, term in variants:
            with self.subTest(name=name, term=term):
                path = self.root / name
                original = path.read_bytes()
                token = term.encode()
                self.assertIn(token, original)
                changed = original.replace(token, b'removed')
                self.assertNotIn(token, changed)
                path.write_bytes(changed)
                try:
                    self.assertNotEqual(original, changed)
                    self.assertEqual(path.read_bytes(), changed)
                    self.suggestion()
                    self.execution(failure=repr(term) + ' not found in')
                finally:
                    path.write_bytes(original)


class AnalysisConvergenceDocAdopterEndToEndTests(AnalysisConvergenceDocFixture):  # R6
    def test_explicit_adoption_freshness_identity_and_receipt(self):
        (self.root / '.agentic.json').unlink()
        self.lc('tier', 'L1', '--reason', 'static analysis/convergence doc adopter fixture')
        result = self.process([sys.executable, '.ai/scripts/okf.py', 'init'])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.write('knowledge/project/sync-ignore', '*\n')
        value = self.suggestion()
        prefix = ('---\ntype: Capability\ntitle: Analysis documentation\nnamespace: ANALYSISDOC\nstatus: draft\n---\n'
                  '# Analysis documentation\n\n## Requirements\n\n- ANALYSISDOC-R1: The static check MUST pass.\n'
                  '  - Verify: `' + ' '.join(ANALYSIS_CONVERGENCE_DOC_COMMAND) + '`\n')
        original = prefix + value['inputs_line'] + '\n'
        capability = self.write('knowledge/capabilities/analysis-doc.md', original)
        self.commit()

        def status():
            result = self.process([sys.executable, '.ai/scripts/lifecycle.py', 'assure', '--json'])
            data = json.loads(result.stdout)
            state = next(r['status'] for r in data['requirements'] if r['id'] == 'ANALYSISDOC-R1')
            self.assertEqual(result.returncode, 0 if state == 'VERIFIED' else 1, result.stdout + result.stderr)
            return state

        self.assertEqual(status(), 'UNVERIFIED')
        before = self.preflight()
        self.lc('assure', '--run', 'ANALYSISDOC-R1')
        self.assert_inputs_unchanged(before)
        self.assertEqual(status(), 'VERIFIED')
        for name in ('.ai/scripts/tests/unrelated.py', 'unrelated.md'):
            self.edit_and_restore(name, lambda: self.assertEqual(status(), 'VERIFIED'))
            self.assertEqual(status(), 'VERIFIED')
        for name in [*ANALYSIS_CONVERGENCE_DOC_DOCS, *ANALYSIS_CONVERGENCE_DOC_TESTS,
                     '.ai/scripts/review_guard.py', '.ai/scripts/new_analysis.py']:
            with self.subTest(name=name):
                self.edit_and_restore(name, lambda: self.assertEqual(status(), 'STALE'))
                self.assertEqual(status(), 'VERIFIED')
        reordered = [*value['inputs'][:-2], value['inputs'][-1], value['inputs'][-2]]
        capability.write_text(prefix + '  - Inputs: ' + ' '.join('`' + p + '`' for p in reordered) + '\n')
        self.assertEqual(status(), 'UNVERIFIED')
        capability.write_text(original.replace(ANALYSIS_CONVERGENCE_DOC_COMMAND[2] + '`',
                                               ANALYSIS_CONVERGENCE_DOC_COMMAND[2] + ' -v`'))
        self.assertEqual(status(), 'UNVERIFIED')
        capability.write_text(original)
        self.assertEqual(status(), 'VERIFIED')
        entries = [e for p in (self.root / 'knowledge/history/lifecycle').glob('*.json')
                   for e in json.loads(p.read_text()).get('ledger', []) if e['label'] == 'req:ANALYSISDOC-R1']
        self.assertEqual((entries[-1]['argv'], entries[-1]['inputs'], entries[-1]['exit']),
                         (ANALYSIS_CONVERGENCE_DOC_COMMAND, ANALYSIS_CONVERGENCE_DOC_INPUTS + [EXCLUDE], 0))
        self.write('knowledge/history/lifecycle/extra-receipt.json', '{}\n')
        self.assertEqual(status(), 'VERIFIED')


class AnalysisConvergenceDocControlTests(AnalysisConvergenceDocFixture):  # R6
    def test_confirmed_broken_variants_fail_intended_criteria(self):
        method = 'test_each_input_and_addition_invalidates'
        variants = [(p, AnalysisConvergenceDocFrameworkEndToEndTests, method,
                     'missing analysis/convergence doc freshness invalidation: ' + p)
                    for p in ANALYSIS_CONVERGENCE_DOC_DOCS]
        variants += [('loose', AnalysisConvergenceDocProfileTests, 'test_exact_registration_and_prior_profiles', '0 != 2'),
                     ('empty', AnalysisConvergenceDocFrameworkEndToEndTests, method,
                      'analysis/convergence doc execution count must be one')]
        self.assertEqual(len(variants), 5)
        for variant, cls, test, criterion in variants:
            with self.subTest(variant=variant):
                case = cls(test)
                setup = case.setUp

                def mutated_setup():
                    setup()
                    path = case.root / '.ai/scripts/assurance_inputs.py'
                    original = path.read_text()
                    if variant in ANALYSIS_CONVERGENCE_DOC_DOCS:
                        catalog = copy.deepcopy(case.module().PROFILES)
                        profile = next(p for p in catalog if p['id'] == 'python-analysis-convergence-doc-contract')
                        profile['inputs'].remove(variant)
                        del profile['rationale'][variant]
                        replacement = (original.split('PROFILES = ', 1)[0] + 'PROFILES = ' + repr(catalog)
                                       + '\nLIMITATIONS =' + original.split('\nLIMITATIONS =', 1)[1])
                    elif variant == 'loose':
                        old = "p['argv'] == list(argv)"
                        case.assertEqual(original.count(old), 1)
                        replacement = original.replace(old, "p['argv'] == list(argv)[:len(p['argv'])]")
                    else:
                        path = case.root / ANALYSIS_CONVERGENCE_DOC_TESTS[0]
                        original = path.read_text()
                        replacement = 'import sys\nimport unittest\nunittest.main(argv=[sys.argv[0]])\n'
                    path.write_text(replacement)
                    case.assertNotEqual(original, replacement, 'mutation was not applied')
                    case.assertEqual(path.read_text(), replacement, 'mutation bytes differ')
                    if variant in ANALYSIS_CONVERGENCE_DOC_DOCS:
                        value = case.suggestion()
                        case.assertNotIn(variant, value['inputs'])
                        case.assertNotIn(variant, value['rationale'])
                    if variant == 'empty':
                        result = case.process(ANALYSIS_CONVERGENCE_DOC_COMMAND)
                        case.assertRegex(result.stdout + result.stderr, r'Ran 0 tests? in ')

                case.setUp = mutated_setup
                result = unittest.TestResult()
                case.run(result)
                self.assertEqual(result.testsRun, 1)
                self.assertFalse(result.errors, result.errors)
                self.assertEqual(len(result.failures), 1, 'broken variant survived: ' + variant)
                self.assertIn(criterion, result.failures[0][1])



# Stage documentation/runtime names: specification-5i.md R1-R6. Independent of PROFILES.
STAGE_DOC_COMMAND = ['python3', '.ai/scripts/tests/test_lifecycle_conformance.py',
                     'Tiers.test_every_stage_the_script_gates_is_described_in_the_lifecycle']
STAGE_DOC_TESTS = [STAGE_DOC_COMMAND[1], '.ai/scripts/tests/disk_tmp.py']
STAGE_DOC_DOCS = ['.ai/lifecycle.md']
STAGE_DOC_INPUTS = ['.ai/scripts/**', '!.ai/scripts/tests/**',
                    *STAGE_DOC_TESTS, *STAGE_DOC_DOCS]
STAGE_DOC_IMPORTS = ['.ai/scripts/' + name + '.py' for name in
                     ('scratch', 'lifecycle', 'review_guard', 'ledger', 'brownfield',
                      'okf', 'learning', 'scan', 'project_context', 'assurance')]
STAGE_DOC_HEADINGS = ('Stage 0: Intent', 'Stage 1: Plan', 'Stage 3: Review',
                      'Stage 4: Verify and sync', 'Stage 5: Ship')
STAGE_DOC_NAMES = {'intent', 'plan', 'review', 'verify', 'ship'}


class StageDocFixture(Fixture):
    def setUp(self):
        super().setUp()
        # Compatibility copies do not define the selected method's read oracle.
        for name in dict.fromkeys([*STAGE_DOC_TESTS, *STAGE_DOC_DOCS,
                                   '.ai/docs/lifecycle.md', *VALIDATION_POLICY_DOCS, *INSTALLER_DOC_TEXT, *REPORT_DOCS,
                                   *WIRING_JSON, *ARCH_TESTS[:-1]]):
            destination = self.root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(SCRIPTS.parent.parent / name, destination)
        self.commit()

    def export(self, argv=None, **kwargs):
        return super().export(argv=STAGE_DOC_COMMAND if argv is None else argv, **kwargs)

    def selected_bytes(self):
        return {name: (self.root / name).read_bytes()
                for name in ledger.input_paths(self.root, STAGE_DOC_INPUTS)}

    def assert_inputs_unchanged(self, before):
        self.assertEqual(self.selected_bytes(), before, 'stage doc execution changed inputs')

    def execution(self, failure=None):
        before = self.selected_bytes()
        result = self.process(STAGE_DOC_COMMAND)
        output = result.stdout + result.stderr
        counts = re.findall(r'Ran (\d+) tests? in ', output)
        self.assertEqual(len(counts), 1, 'stage doc execution count missing or ambiguous: ' + output)
        self.assertEqual(int(counts[0]), 1, 'stage doc execution count must be one: ' + output)
        if failure is None:
            self.assertEqual(result.returncode, 0, output)
            self.assertRegex(output, r'\nOK\s*$')
        else:
            self.assertNotEqual(result.returncode, 0, output)
            self.assertIn('AssertionError', output)
            self.assertIn(STAGE_DOC_COMMAND[2].split('.')[1], output)
            self.assertIn(failure, output)
            self.assertNotIn('ERROR:', output)
        self.assert_inputs_unchanged(before)
        return result

    def preflight(self):
        before = self.selected_bytes()
        self.execution()
        return before

    def edit_and_restore(self, name, check):
        path = self.root / name
        original = path.read_bytes() if path.exists() else None
        changed = (original or b'') + b'\n '
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(changed)
        try:
            self.assertNotEqual(original, changed)
            self.assertEqual(path.read_bytes(), changed)
            if name in STAGE_DOC_DOCS:
                self.execution()
            check()
        finally:
            if original is None:
                path.unlink()
            else:
                path.write_bytes(original)

    def assert_prior_profiles(self):
        result = subprocess.run(
            ['git', 'show', '0efa2240b6109f6e69fe7a5dacaa3f9be16482c2:.ai/scripts/assurance_inputs.py'],
            cwd=SCRIPTS.parent.parent, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        import ast
        baseline = next(ast.literal_eval(n.value) for n in ast.parse(result.stdout).body
                        if isinstance(n, ast.Assign)
                        and any(isinstance(t, ast.Name) and t.id == 'PROFILES' for t in n.targets))
        identities = ('python-runner-test', 'python-architecture-compatibility', 'python-harness-wiring',
                      'python-reviewer-report-contract', 'python-installer-doc-contract',
                      'python-validation-policy-contract', 'python-audit-doc-contract',
                      'python-analysis-convergence-doc-contract')
        self.assertEqual(tuple(p['id'] for p in baseline), identities)
        actual = self.module().PROFILES
        for expected in baseline:
            self.assertEqual(next(p for p in actual if p['id'] == expected['id']), expected)
            value = self.suggestion(argv=expected['argv'])
            self.assertEqual((value['profile_id'], value['argv'], value['inputs'], value['rationale']),
                             (expected['id'], expected['argv'], expected['inputs'], expected['rationale']))


class StageDocProfileTests(StageDocFixture):  # R1
    def test_exact_registration_and_prior_profiles(self):
        value = self.suggestion()
        self.assertEqual(value['profile_id'], 'python-stage-doc-contract')
        self.assertEqual(value['argv'], STAGE_DOC_COMMAND)
        self.assert_prior_profiles()
        for argv in (STAGE_DOC_COMMAND[:2], STAGE_DOC_COMMAND[:2] + ['Tiers'],
                     STAGE_DOC_COMMAND[:2] + ['Tiers.test_tiers_match'],
                     STAGE_DOC_COMMAND + ['-v'],
                     [sys.executable, *STAGE_DOC_COMMAND[1:]],
                     ['python3', './' + STAGE_DOC_COMMAND[1], STAGE_DOC_COMMAND[2]],
                     ['python3', '-m', 'unittest', 'discover', '-s', '.ai/scripts/tests',
                      '-p', 'test_lifecycle_conformance.py']):
            self.assertIn('exact command', self.refused(argv=argv)['reason'])
        self.refused(cwd=self.root / '.ai')


class StageDocExportTests(StageDocFixture):  # R3
    def test_readonly_formats_supplements_and_no_semantic_parsing(self):
        marker = self.root / 'executed'
        for name in STAGE_DOC_TESTS:
            self.write(name, f'from pathlib import Path\nPath({str(marker)!r}).touch()\nraise RuntimeError("executed")\n')
        for name in STAGE_DOC_DOCS:
            self.write(name, 'nonconforming static document')
        for name in ('space file.txt', 'second.txt'):
            self.write(name, 'supplement')
        before = snapshot(self.root)
        extra = ('space file.txt', 'second.txt')
        value = self.suggestion(extra=extra)
        text = self.export(extra=extra, json_output=False)
        self.assertEqual(text.returncode, 0, text.stderr)
        self.assertEqual(value['inputs'], STAGE_DOC_INPUTS + list(extra))
        self.assertEqual(value['lifecycle_inputs_argv'], ['--inputs', *value['inputs']])
        for item in (value['profile_id'], value['inputs_line'], json.dumps(STAGE_DOC_COMMAND),
                     json.dumps(value['lifecycle_inputs_argv']), *value['rationale'].values(), *value['limitations']):
            self.assertIn(item, text.stdout)
        raw = ('- STAGEDOC-R1: The check MUST pass.\n  - Verify: `'
               + ' '.join(STAGE_DOC_COMMAND) + '`\n' + value['inputs_line'] + '\n')
        parsed = assurance.parse('STAGEDOC-R1', 'capabilities/stage-doc.md', raw, root=self.root)
        self.assertIsNone(parsed.invalid)
        self.assertEqual(list(parsed.globs), value['inputs'])
        self.assertTrue(value['review_required'])
        self.assertEqual(snapshot(self.root), before)
        self.assertFalse(marker.exists())

    def test_required_literals_and_unsafe_boundaries_refuse(self):
        for name in [*STAGE_DOC_TESTS, *STAGE_DOC_DOCS]:
            path = self.root / name
            original = path.read_bytes()
            path.unlink()
            try:
                self.refused()
            finally:
                path.write_bytes(original)
        name = STAGE_DOC_DOCS[0]
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
        try:
            self.refused()
        finally:
            path.unlink()
            path.write_bytes(original)
        for extra in ('!README.md', '../x', '/etc/passwd', '', 'x`bad', '--other-option'):
            self.refused(extra=(extra,))


# Shared setup/called bodies independently reviewed for the exact 5i method.
STAGE_DOC_SETUP_PINS = {
    '.ai/scripts/tests/test_lifecycle_conformance.py': '50977be9e0fc2636e75b83eba96f267339efd91e89f3d035690d0a0e24e8a02b',
    '.ai/scripts/tests/disk_tmp.py': 'fff9eed82f770bce05c477c507ad3c00dae4a16c216521b004646837c0bdd02f',
    '.ai/scripts/scratch.py': '523cbb977066b41423329249d132d2dc27a2f963db15b71489c2579fdb093060',
    '.ai/scripts/lifecycle.py': '048f391c166ffb58b8ba1d769ca287adc78d5c155a28bebba043e0d93a30e1ca',
    '.ai/scripts/review_guard.py': '2d806b1c16cb028a8b2197aec8881b0a4db1a962125f5a5d50a8599b01c45d69',
    '.ai/scripts/ledger.py': 'fc2423e775969cdc28173f970d7c676e6ad254e8f5e120abb89a5c1244b80cab',
}


class StageDocDependencyTests(StageDocFixture):  # R2
    def test_order_scope_and_independent_oracle(self):
        value = self.suggestion()
        actual_setup = {p: report_setup_digest(self.root / p) for p in STAGE_DOC_SETUP_PINS}
        self.assertEqual(actual_setup, STAGE_DOC_SETUP_PINS,
                         'review stage doc dependency boundary: ' + repr(actual_setup))
        self.assertEqual(value['inputs'], STAGE_DOC_INPUTS)
        self.assertEqual(set(value['rationale']), set(STAGE_DOC_INPUTS))
        for name, terms in {
            '.ai/scripts/**': ('conservative', 'import', 'lazy'),
            '!.ai/scripts/tests/**': ('exclude',),
            STAGE_DOC_TESTS[0]: ('method', 'static'),
            STAGE_DOC_TESTS[1]: ('helper',),
            **{p: ('direct',) for p in STAGE_DOC_DOCS},
        }.items():
            for term in terms:
                self.assertIn(term, value['rationale'][name].lower())
        included = ['.ai/scripts/future_stage.py', '.ai/scripts/assets/stage.txt']
        compatibility = ['.ai/docs/lifecycle.md', *VALIDATION_POLICY_DOCS, *INSTALLER_DOC_TEXT, *REPORT_DOCS,
                         *WIRING_JSON, *ARCH_TESTS[:-1]]
        excluded = ['.ai/scripts/tests/unrelated.py', 'unrelated.md',
                    *[p for p in compatibility if p not in STAGE_DOC_DOCS]]
        for name in included + excluded[:2]:
            self.write(name, '# independent inventory fixture\n')
        selected = set(ledger.input_paths(self.root, value['inputs']))
        self.assertTrue(set([*STAGE_DOC_TESTS, *STAGE_DOC_DOCS,
                             *STAGE_DOC_IMPORTS, *included]).issubset(selected))
        self.assertFalse(set(excluded) & selected)
        import ast
        source = (self.root / STAGE_DOC_TESTS[0]).read_text()
        cls = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef) and n.name == 'Tiers')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                      and n.name == STAGE_DOC_COMMAND[2].split('.')[1])
        reviewed = '\n'.join(source.splitlines()[method.lineno - 1:method.end_lineno])
        self.assertEqual(hashlib.sha256(reviewed.encode()).hexdigest(),
                         'ebb7f78a76621ee6964916ab7b8e58a139429c1fe30acf4b9ecaabac8ce7b8a3',
                         'review stage doc selected method boundary')
        self.assertEqual(len(method.body), 3)
        document, loop, runtime = method.body
        self.assertIsInstance(document, ast.Assign)
        self.assertEqual(len(document.targets), 1)
        self.assertIsInstance(document.targets[0], ast.Name)
        doc_variable = document.targets[0].id
        self.assertIsInstance(document.value, ast.Call)
        self.assertEqual(ast.dump(document.value.func), ast.dump(ast.Name(id='text', ctx=ast.Load())))
        self.assertEqual(len(document.value.args), 1)
        self.assertFalse(document.value.keywords)
        self.assertEqual([ast.literal_eval(document.value.args[0])], STAGE_DOC_DOCS)
        self.assertIsInstance(loop, ast.For)
        self.assertIsInstance(loop.iter, ast.Tuple)
        self.assertEqual(ast.literal_eval(loop.iter), STAGE_DOC_HEADINGS)
        self.assertIsInstance(loop.target, ast.Name)
        self.assertFalse(loop.orelse)
        self.assertEqual(len(loop.body), 1)
        expected_heading = ast.parse("self.assertIn(f'## {" + loop.target.id + "}\\n', " + doc_variable + ")").body[0]
        self.assertEqual(ast.dump(loop.body[0]), ast.dump(expected_heading))
        expected_runtime = ast.parse(
            "self.assertEqual(set(lifecycle.STAGES), {'intent', 'plan', 'review', 'verify', 'ship'})").body[0]
        self.assertEqual(ast.dump(runtime), ast.dump(expected_runtime))
        self.assertEqual(ast.literal_eval(runtime.value.args[1]), STAGE_DOC_NAMES)
        all_reads = [n for n in ast.walk(method) if isinstance(n, ast.Call)
                     and isinstance(n.func, ast.Name) and n.func.id == 'text']
        self.assertEqual(len(all_reads), 1)

    def test_reachable_added_dependencies_require_review(self):
        variants = [(p, ()) for p in STAGE_DOC_SETUP_PINS]
        variants += [(STAGE_DOC_TESTS[0], ('Tiers', STAGE_DOC_COMMAND[2].split('.')[1])),
                     (STAGE_DOC_TESTS[0], ('text',)),
                     ('.ai/scripts/scratch.py', ('require_disk',)),
                     ('.ai/scripts/lifecycle.py', ('lazy',)),
                     ('.ai/scripts/review_guard.py', ('protected',)),
                     ('.ai/scripts/review_guard.py', ('protected', 'decorate')),
                     (STAGE_DOC_TESTS[0], ('import-helper',))]
        self.assertEqual(len(variants), 13)
        for name, body in variants:
            with self.subTest(name=name, body=body):
                case = StageDocDependencyTests('test_order_scope_and_independent_oracle')
                setup = case.setUp

                def mutated_setup():
                    setup()
                    import ast
                    path = case.root / name
                    source = path.read_text()
                    tree = ast.parse(source)
                    addition = '__import__("pathlib").Path("unrelated.md").read_text()\n'
                    if body == ('import-helper',):
                        helper = '.ai/scripts/tests/unreviewed_stage_helper.py'
                        case.write(helper, addition)
                        case.assertNotIn(helper, ledger.input_paths(case.root, STAGE_DOC_INPUTS))
                        addition = 'import unreviewed_stage_helper\n'
                    if body and body != ('import-helper',):
                        node = tree
                        for part in body:
                            node = next(n for n in node.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))
                                        and n.name == part)
                        first = node.body[0]
                        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                                and isinstance(first.value.value, str):
                            after = first.end_lineno
                        else:
                            after = min([first.lineno, *[n.lineno for n in
                                         getattr(first, 'decorator_list', [])]]) - 1
                        addition = ' ' * first.col_offset + addition
                    else:
                        after = max(n.end_lineno for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom)))
                    lines = source.splitlines(keepends=True)
                    changed = ''.join(lines[:after]) + addition + ''.join(lines[after:])
                    path.write_text(changed)
                    case.assertNotEqual(source, changed)
                    case.assertEqual(path.read_text(), changed)
                    case.assertNotIn('unrelated.md', ledger.input_paths(case.root, STAGE_DOC_INPUTS))
                    missing = case.process(STAGE_DOC_COMMAND)
                    case.assertNotEqual(missing.returncode, 0)
                    case.assertIn('FileNotFoundError', missing.stdout + missing.stderr)
                    case.assertIn('unrelated.md', missing.stdout + missing.stderr)
                    case.write('unrelated.md', 'new excluded dependency')
                    case.execution()

                case.setUp = mutated_setup
                result = unittest.TestResult()
                case.run(result)
                self.assertEqual(result.testsRun, 1)
                self.assertFalse(result.errors, result.errors)
                self.assertEqual(len(result.failures), 1, 'unreviewed dependency survived: ' + repr((name, body)))
                self.assertIn('review stage doc dependency boundary', result.failures[0][1])


class StageDocCompatibilityTests(StageDocFixture):  # R4
    def test_advisory_guide_and_existing_contracts(self):
        self.assert_prior_profiles()
        self.assertIsNone(ledger.default_inputs(STAGE_DOC_COMMAND))
        self.assertEqual(ledger.default_inputs(COMMAND), ('python-tests', ['**']))
        for argv in (['python3', '-m', 'unittest', 'discover', '-s', '.ai/scripts/tests'],
                     *[['python3', '.ai/scripts/run_tests.py', '-j', str(n)] for n in (1, 8, 32)]):
            self.refused(argv=argv)
        value = self.suggestion()
        self.assertNotIn(EXCLUDE, value['inputs'])
        self.assertEqual(value['schema_version'], 1)
        self.assertTrue(value['review_required'])
        self.assertIn('runtime', ' '.join(value['limitations']).lower())
        guide = (self.root / ARCH_GUIDE).read_text()
        for phrase in ('python-stage-doc-contract', ' '.join(STAGE_DOC_COMMAND),
                       'static', 'conservative', 'explicit', 'manual', 'substring',
                       'five heading', 'runtime', 'set equality', 'Stage 2', 'tuple type',
                       'section bodies', 'duplicates', 'enforcement', 'eight prior profiles',
                       *STAGE_DOC_DOCS):
            self.assertIn(phrase, guide)


class StageDocFrameworkEndToEndTests(StageDocFixture):  # R5
    def record(self):
        value = self.suggestion()
        before = self.preflight()
        self.lc('tier', 'L1', '--reason', 'static stage doc framework fixture')
        self.lc('run', 'stage-doc', *value['lifecycle_inputs_argv'], '--', *STAGE_DOC_COMMAND)
        self.assert_inputs_unchanged(before)
        import lifecycle
        entry = lifecycle.load(self.root)['ledger'][-1]
        self.assertEqual((entry['argv'], entry['inputs'], entry['exit']),
                         (STAGE_DOC_COMMAND, value['inputs'], 0))
        self.assertIn('REUSE', self.lc('reuse', 'stage-doc'))

    def test_each_input_and_addition_invalidates(self):
        self.record()
        for name in ('.ai/scripts/tests/unrelated.py', 'unrelated.md'):
            self.edit_and_restore(name, lambda: self.assertIn('REUSE', self.lc('reuse', 'stage-doc')))
            self.assertIn('REUSE', self.lc('reuse', 'stage-doc'))
        for name in [*STAGE_DOC_DOCS, *STAGE_DOC_TESTS,
                     '.ai/scripts/review_guard.py', '.ai/scripts/new_stage.py']:
            with self.subTest(name=name):
                def stale():
                    result = self.process([sys.executable, '.ai/scripts/lifecycle.py', 'reuse', 'stage-doc'])
                    self.assertEqual(result.returncode, 1, 'missing stage doc freshness invalidation: ' + name)
                    self.assertIn('RERUN', result.stdout)
                self.edit_and_restore(name, stale)
                self.assertIn('REUSE', self.lc('reuse', 'stage-doc'))
        self.assertFalse((self.root / 'knowledge').exists())


class StageDocFailureTests(StageDocFixture):  # R5
    def test_six_assertion_failures_fail_actual_command(self):
        variants = [('heading', heading) for heading in STAGE_DOC_HEADINGS]
        variants.append(('runtime', 'STAGES'))
        self.assertEqual(len(variants), 6)
        for kind, term in variants:
            with self.subTest(kind=kind, term=term):
                name = STAGE_DOC_DOCS[0] if kind == 'heading' else '.ai/scripts/lifecycle.py'
                path = self.root / name
                original = path.read_bytes()
                if kind == 'heading':
                    token = ('## ' + term + '\n').encode()
                    self.assertIn(token, original)
                    changed = original.replace(token, b'removed heading\n')
                    self.assertNotIn(token, changed)
                    criterion = repr('## ' + term + '\n') + ' not found in'
                else:
                    import ast
                    source = original.decode()
                    assignment = next(n for n in ast.parse(source).body if isinstance(n, ast.Assign)
                                      and any(isinstance(t, ast.Name) and t.id == 'STAGES' for t in n.targets))
                    self.assertEqual(set(ast.literal_eval(assignment.value)), STAGE_DOC_NAMES)
                    lines = source.splitlines(keepends=True)
                    changed = (''.join(lines[:assignment.lineno - 1])
                               + "STAGES = ('intent', 'plan', 'review', 'verify', 'unexpected-stage')\n"
                               + ''.join(lines[assignment.end_lineno:])).encode()
                    criterion = "Items in the first set but not the second:"
                path.write_bytes(changed)
                try:
                    self.assertNotEqual(original, changed)
                    self.assertEqual(path.read_bytes(), changed)
                    self.suggestion()
                    result = self.execution(failure=criterion)
                    if kind == 'runtime':
                        self.assertIn('unexpected-stage', result.stdout + result.stderr)
                        self.assertIn("'ship'", result.stdout + result.stderr)
                        self.assertIn('set(lifecycle.STAGES)', result.stdout + result.stderr)
                finally:
                    path.write_bytes(original)


class StageDocAdopterEndToEndTests(StageDocFixture):  # R6
    def test_explicit_adoption_freshness_identity_and_receipt(self):
        (self.root / '.agentic.json').unlink()
        self.lc('tier', 'L1', '--reason', 'static stage doc adopter fixture')
        result = self.process([sys.executable, '.ai/scripts/okf.py', 'init'])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.write('knowledge/project/sync-ignore', '*\n')
        value = self.suggestion()
        prefix = ('---\ntype: Capability\ntitle: Stage documentation\nnamespace: STAGEDOC\nstatus: draft\n---\n'
                  '# Stage documentation\n\n## Requirements\n\n- STAGEDOC-R1: The static check MUST pass.\n'
                  '  - Verify: `' + ' '.join(STAGE_DOC_COMMAND) + '`\n')
        original = prefix + value['inputs_line'] + '\n'
        capability = self.write('knowledge/capabilities/stage-doc.md', original)
        self.commit()

        def status():
            result = self.process([sys.executable, '.ai/scripts/lifecycle.py', 'assure', '--json'])
            data = json.loads(result.stdout)
            state = next(r['status'] for r in data['requirements'] if r['id'] == 'STAGEDOC-R1')
            self.assertEqual(result.returncode, 0 if state == 'VERIFIED' else 1, result.stdout + result.stderr)
            return state

        self.assertEqual(status(), 'UNVERIFIED')
        before = self.preflight()
        self.lc('assure', '--run', 'STAGEDOC-R1')
        self.assert_inputs_unchanged(before)
        self.assertEqual(status(), 'VERIFIED')
        for name in ('.ai/scripts/tests/unrelated.py', 'unrelated.md'):
            self.edit_and_restore(name, lambda: self.assertEqual(status(), 'VERIFIED'))
            self.assertEqual(status(), 'VERIFIED')
        for name in [*STAGE_DOC_DOCS, *STAGE_DOC_TESTS,
                     '.ai/scripts/review_guard.py', '.ai/scripts/new_stage.py']:
            with self.subTest(name=name):
                self.edit_and_restore(name, lambda: self.assertEqual(status(), 'STALE'))
                self.assertEqual(status(), 'VERIFIED')
        reordered = [*value['inputs'][:-2], value['inputs'][-1], value['inputs'][-2]]
        capability.write_text(prefix + '  - Inputs: ' + ' '.join('`' + p + '`' for p in reordered) + '\n')
        self.assertEqual(status(), 'UNVERIFIED')
        capability.write_text(original.replace(STAGE_DOC_COMMAND[2] + '`',
                                               STAGE_DOC_COMMAND[2] + ' -v`'))
        self.assertEqual(status(), 'UNVERIFIED')
        capability.write_text(original)
        self.assertEqual(status(), 'VERIFIED')
        entries = [e for p in (self.root / 'knowledge/history/lifecycle').glob('*.json')
                   for e in json.loads(p.read_text()).get('ledger', []) if e['label'] == 'req:STAGEDOC-R1']
        self.assertEqual((entries[-1]['argv'], entries[-1]['inputs'], entries[-1]['exit']),
                         (STAGE_DOC_COMMAND, STAGE_DOC_INPUTS + [EXCLUDE], 0))
        self.write('knowledge/history/lifecycle/extra-receipt.json', '{}\n')
        self.assertEqual(status(), 'VERIFIED')


class StageDocControlTests(StageDocFixture):  # R6
    def test_confirmed_broken_variants_fail_intended_criteria(self):
        method = 'test_each_input_and_addition_invalidates'
        variants = [(p, StageDocFrameworkEndToEndTests, method,
                     'missing stage doc freshness invalidation: ' + p)
                    for p in STAGE_DOC_DOCS]
        variants += [('loose', StageDocProfileTests, 'test_exact_registration_and_prior_profiles', '0 != 2'),
                     ('empty', StageDocFrameworkEndToEndTests, method,
                      'stage doc execution count must be one')]
        self.assertEqual(len(variants), 3)
        for variant, cls, test, criterion in variants:
            with self.subTest(variant=variant):
                case = cls(test)
                setup = case.setUp

                def mutated_setup():
                    setup()
                    path = case.root / '.ai/scripts/assurance_inputs.py'
                    original = path.read_text()
                    if variant in STAGE_DOC_DOCS:
                        catalog = copy.deepcopy(case.module().PROFILES)
                        profile = next(p for p in catalog if p['id'] == 'python-stage-doc-contract')
                        profile['inputs'].remove(variant)
                        del profile['rationale'][variant]
                        replacement = (original.split('PROFILES = ', 1)[0] + 'PROFILES = ' + repr(catalog)
                                       + '\nLIMITATIONS =' + original.split('\nLIMITATIONS =', 1)[1])
                    elif variant == 'loose':
                        old = "p['argv'] == list(argv)"
                        case.assertEqual(original.count(old), 1)
                        replacement = original.replace(old, "p['argv'] == list(argv)[:len(p['argv'])]")
                    else:
                        path = case.root / STAGE_DOC_TESTS[0]
                        original = path.read_text()
                        replacement = 'import sys\nimport unittest\nunittest.main(argv=[sys.argv[0]])\n'
                    path.write_text(replacement)
                    case.assertNotEqual(original, replacement, 'mutation was not applied')
                    case.assertEqual(path.read_text(), replacement, 'mutation bytes differ')
                    if variant in STAGE_DOC_DOCS:
                        value = case.suggestion()
                        case.assertNotIn(variant, value['inputs'])
                        case.assertNotIn(variant, value['rationale'])
                    if variant == 'empty':
                        result = case.process(STAGE_DOC_COMMAND)
                        case.assertRegex(result.stdout + result.stderr, r'Ran 0 tests? in ')

                case.setUp = mutated_setup
                result = unittest.TestResult()
                case.run(result)
                self.assertEqual(result.testsRun, 1)
                self.assertFalse(result.errors, result.errors)
                self.assertEqual(len(result.failures), 1, 'broken variant survived: ' + variant)
                self.assertIn(criterion, result.failures[0][1])


TIER_DOC_COMMAND = ['python3', '.ai/scripts/tests/test_lifecycle_conformance.py',
                     'Tiers.test_tier_definitions_agree_across_agents_lifecycle_and_script']
TIER_DOC_TESTS = [TIER_DOC_COMMAND[1], '.ai/scripts/tests/disk_tmp.py']
TIER_DOC_DOCS = ['AGENTS.md', '.ai/lifecycle.md']
TIER_DOC_INPUTS = ['.ai/scripts/**', '!.ai/scripts/tests/**',
                    *TIER_DOC_TESTS, *TIER_DOC_DOCS]
TIER_DOC_IMPORTS = ['.ai/scripts/' + name + '.py' for name in
                     ('scratch', 'lifecycle', 'review_guard', 'ledger', 'brownfield',
                      'okf', 'learning', 'scan', 'project_context', 'assurance')]
TIER_DOC_BASELINE = ('L0', 'L1', 'L2', 'L3')


class TierDocFixture(Fixture):
    def runtime_baseline(self):
        before = self.selected_bytes()
        program = (
            'import json, runpy, sys\n'
            'sys.path.insert(0, ".ai/scripts/tests")\n'
            'namespace = runpy.run_path(".ai/scripts/tests/test_lifecycle_conformance.py")\n'
            'module = namespace["lifecycle"]\n'
            'print(json.dumps([list(module.TIERS), list(module.REQUIRED)]))\n')
        result = self.process(['python3', '-c', program])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        observed_tiers, observed_required = json.loads(result.stdout)
        import ast
        tree = ast.parse((self.root / '.ai/scripts/lifecycle.py').read_text())
        definitions = {n.targets[0].id: ast.literal_eval(n.value)
                       for n in tree.body if isinstance(n, ast.Assign)
                       and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name)
                       and n.targets[0].id in ('TIERS', 'REQUIRED')}
        self.assertEqual(tuple(observed_tiers), TIER_DOC_BASELINE,
                         'runtime baseline differs: stop for human scope/count review')
        self.assertEqual(observed_tiers, list(definitions['TIERS']))
        self.assertEqual(observed_required, list(definitions['REQUIRED']))
        self.assertEqual(set(observed_required), set(observed_tiers))
        self.assert_inputs_unchanged(before)
        return observed_tiers

    def setUp(self):
        super().setUp()
        # Compatibility copies do not define the selected method's read oracle.
        for name in dict.fromkeys([*TIER_DOC_TESTS, *TIER_DOC_DOCS,
                                   '.ai/docs/lifecycle.md', *VALIDATION_POLICY_DOCS, *INSTALLER_DOC_TEXT, *REPORT_DOCS,
                                   *WIRING_JSON, *ARCH_TESTS[:-1]]):
            destination = self.root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(SCRIPTS.parent.parent / name, destination)
        self.commit()

    def export(self, argv=None, **kwargs):
        return super().export(argv=TIER_DOC_COMMAND if argv is None else argv, **kwargs)

    def selected_bytes(self):
        return {name: (self.root / name).read_bytes()
                for name in ledger.input_paths(self.root, TIER_DOC_INPUTS)}

    def assert_inputs_unchanged(self, before):
        self.assertEqual(self.selected_bytes(), before, 'tier doc execution changed inputs')

    def execution(self, failure=None):
        before = self.selected_bytes()
        result = self.process(TIER_DOC_COMMAND)
        output = result.stdout + result.stderr
        counts = re.findall(r'Ran (\d+) tests? in ', output)
        self.assertEqual(len(counts), 1, 'tier doc execution count missing or ambiguous: ' + output)
        self.assertEqual(int(counts[0]), 1, 'tier doc execution count must be one: ' + output)
        if failure is None:
            self.assertEqual(result.returncode, 0, output)
            self.assertRegex(output, r'\nOK\s*$')
        else:
            self.assertNotEqual(result.returncode, 0, output)
            self.assertIn('AssertionError', output)
            self.assertIn(TIER_DOC_COMMAND[2].split('.')[1], output)
            self.assertIn(failure, output)
            self.assertNotIn('ERROR:', output)
        self.assert_inputs_unchanged(before)
        return result

    def preflight(self):
        before = self.selected_bytes()
        self.execution()
        return before

    def edit_and_restore(self, name, check):
        path = self.root / name
        original = path.read_bytes() if path.exists() else None
        changed = (original or b'') + b'\n '
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(changed)
        try:
            self.assertNotEqual(original, changed)
            self.assertEqual(path.read_bytes(), changed)
            if name in TIER_DOC_DOCS:
                self.execution()
            check()
        finally:
            if original is None:
                path.unlink()
            else:
                path.write_bytes(original)

    def assert_prior_profiles(self):
        result = subprocess.run(
            ['git', 'show', 'f2c0b6db99e797b99781034a7f8b4b44b17f5f00:.ai/scripts/assurance_inputs.py'],
            cwd=SCRIPTS.parent.parent, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        import ast
        baseline = next(ast.literal_eval(n.value) for n in ast.parse(result.stdout).body
                        if isinstance(n, ast.Assign)
                        and any(isinstance(t, ast.Name) and t.id == 'PROFILES' for t in n.targets))
        identities = ('python-runner-test', 'python-architecture-compatibility', 'python-harness-wiring',
                      'python-reviewer-report-contract', 'python-installer-doc-contract',
                      'python-validation-policy-contract', 'python-audit-doc-contract',
                      'python-analysis-convergence-doc-contract', 'python-stage-doc-contract')
        self.assertEqual(tuple(p['id'] for p in baseline), identities)
        actual = self.module().PROFILES
        for expected in baseline:
            self.assertEqual(next(p for p in actual if p['id'] == expected['id']), expected)
            value = self.suggestion(argv=expected['argv'])
            self.assertEqual((value['profile_id'], value['argv'], value['inputs'], value['rationale']),
                             (expected['id'], expected['argv'], expected['inputs'], expected['rationale']))


class TierDocProfileTests(TierDocFixture):  # R1
    def test_exact_registration_and_prior_profiles(self):
        value = self.suggestion()
        self.assertEqual(value['profile_id'], 'python-tier-doc-contract')
        self.assertEqual(value['argv'], TIER_DOC_COMMAND)
        self.assert_prior_profiles()
        for argv in (TIER_DOC_COMMAND[:2], TIER_DOC_COMMAND[:2] + ['Tiers'],
                     TIER_DOC_COMMAND[:2] + ['Tiers.test_tiers_match'],
                     TIER_DOC_COMMAND + ['-v'],
                     [sys.executable, *TIER_DOC_COMMAND[1:]],
                     ['python3', './' + TIER_DOC_COMMAND[1], TIER_DOC_COMMAND[2]],
                     ['python3', '-m', 'unittest', 'discover', '-s', '.ai/scripts/tests',
                      '-p', 'test_lifecycle_conformance.py']):
            self.assertIn('exact command', self.refused(argv=argv)['reason'])
        self.refused(cwd=self.root / '.ai')


class TierDocExportTests(TierDocFixture):  # R3
    def test_readonly_formats_supplements_and_no_semantic_parsing(self):
        marker = self.root / 'executed'
        for name in TIER_DOC_TESTS:
            self.write(name, f'from pathlib import Path\nPath({str(marker)!r}).touch()\nraise RuntimeError("executed")\n')
        for name in TIER_DOC_DOCS:
            self.write(name, 'nonconforming static document')
        for name in ('space file.txt', 'second.txt'):
            self.write(name, 'supplement')
        before = snapshot(self.root)
        extra = ('space file.txt', 'second.txt')
        value = self.suggestion(extra=extra)
        text = self.export(extra=extra, json_output=False)
        self.assertEqual(text.returncode, 0, text.stderr)
        self.assertEqual(value['inputs'], TIER_DOC_INPUTS + list(extra))
        self.assertEqual(value['lifecycle_inputs_argv'], ['--inputs', *value['inputs']])
        for item in (value['profile_id'], value['inputs_line'], json.dumps(TIER_DOC_COMMAND),
                     json.dumps(value['lifecycle_inputs_argv']), *value['rationale'].values(), *value['limitations']):
            self.assertIn(item, text.stdout)
        raw = ('- TIERDOC-R1: The check MUST pass.\n  - Verify: `'
               + ' '.join(TIER_DOC_COMMAND) + '`\n' + value['inputs_line'] + '\n')
        parsed = assurance.parse('TIERDOC-R1', 'capabilities/tier-doc.md', raw, root=self.root)
        self.assertIsNone(parsed.invalid)
        self.assertEqual(list(parsed.globs), value['inputs'])
        self.assertTrue(value['review_required'])
        self.assertEqual(snapshot(self.root), before)
        self.assertFalse(marker.exists())

    def test_required_literals_and_unsafe_boundaries_refuse(self):
        for name in [*TIER_DOC_TESTS, *TIER_DOC_DOCS]:
            path = self.root / name
            original = path.read_bytes()
            path.unlink()
            try:
                self.refused()
            finally:
                path.write_bytes(original)
        self.assertEqual(self.suggestion()['inputs'], TIER_DOC_INPUTS)
        name = TIER_DOC_DOCS[0]
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
        try:
            self.refused()
        finally:
            path.unlink()
            path.write_bytes(original)
        for extra in ('!README.md', '../x', '/etc/passwd', '', 'x`bad', '--other-option'):
            self.refused(extra=(extra,))



# Shared setup/called bodies independently reviewed for the exact 5j method.
TIER_DOC_SETUP_PINS = {
    '.ai/scripts/tests/test_lifecycle_conformance.py': '50977be9e0fc2636e75b83eba96f267339efd91e89f3d035690d0a0e24e8a02b',
    '.ai/scripts/tests/disk_tmp.py': 'fff9eed82f770bce05c477c507ad3c00dae4a16c216521b004646837c0bdd02f',
    '.ai/scripts/scratch.py': '523cbb977066b41423329249d132d2dc27a2f963db15b71489c2579fdb093060',
    '.ai/scripts/lifecycle.py': '048f391c166ffb58b8ba1d769ca287adc78d5c155a28bebba043e0d93a30e1ca',
    '.ai/scripts/review_guard.py': '2d806b1c16cb028a8b2197aec8881b0a4db1a962125f5a5d50a8599b01c45d69',
    '.ai/scripts/ledger.py': 'fc2423e775969cdc28173f970d7c676e6ad254e8f5e120abb89a5c1244b80cab',
}


class TierDocDependencyTests(TierDocFixture):  # R2
    def test_order_scope_and_independent_oracle(self):
        value = self.suggestion()
        actual_setup = {p: report_setup_digest(self.root / p) for p in TIER_DOC_SETUP_PINS}
        self.assertEqual(actual_setup, TIER_DOC_SETUP_PINS,
                         'review tier doc dependency boundary: ' + repr(actual_setup))
        self.assertEqual(value['inputs'], TIER_DOC_INPUTS)
        self.assertEqual(set(value['rationale']), set(TIER_DOC_INPUTS))
        for name, terms in {
            '.ai/scripts/**': ('conservative', 'import', 'lazy'),
            '!.ai/scripts/tests/**': ('exclude',),
            TIER_DOC_TESTS[0]: ('method', 'static'),
            TIER_DOC_TESTS[1]: ('helper',),
            **{p: ('direct',) for p in TIER_DOC_DOCS},
        }.items():
            for term in terms:
                self.assertIn(term, value['rationale'][name].lower())
        included = ['.ai/scripts/future_tier.py', '.ai/scripts/assets/tier.txt']
        compatibility = ['.ai/docs/lifecycle.md', *VALIDATION_POLICY_DOCS, *INSTALLER_DOC_TEXT, *REPORT_DOCS,
                         *WIRING_JSON, *ARCH_TESTS[:-1]]
        excluded = ['.ai/scripts/tests/unrelated.py', 'unrelated.md',
                    *[p for p in compatibility if p not in TIER_DOC_DOCS]]
        for name in included + excluded[:2]:
            self.write(name, '# independent inventory fixture\n')
        selected = set(ledger.input_paths(self.root, value['inputs']))
        self.assertTrue(set([*TIER_DOC_TESTS, *TIER_DOC_DOCS,
                             *TIER_DOC_IMPORTS, *included]).issubset(selected))
        self.assertFalse(set(excluded) & selected)
        import ast
        source = (self.root / TIER_DOC_TESTS[0]).read_text()
        cls = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef) and n.name == 'Tiers')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                      and n.name == TIER_DOC_COMMAND[2].split('.')[1])
        reviewed = '\n'.join(source.splitlines()[method.lineno - 1:method.end_lineno])
        expected_method = (
            '    def test_tier_definitions_agree_across_agents_lifecycle_and_script(self) -> None:\n'
            '        for tier in lifecycle.TIERS:\n'
            '            self.assertIn(f"**{tier}**", text("AGENTS.md"))\n'
            '            self.assertRegex(text(".ai/lifecycle.md"), rf"\\| {tier} ")\n'
            '        self.assertEqual(set(lifecycle.REQUIRED), set(lifecycle.TIERS))')
        self.assertEqual(hashlib.sha256(reviewed.encode()).hexdigest(),
                         hashlib.sha256(expected_method.encode()).hexdigest(),
                         'review tier doc selected method boundary')
        self.assertEqual(len(method.body), 2)
        loop, runtime = method.body
        self.assertIsInstance(loop, ast.For)
        self.assertEqual(ast.dump(loop.iter), ast.dump(ast.parse('lifecycle.TIERS', mode='eval').body))
        self.assertIsInstance(loop.target, ast.Name)
        self.assertFalse(loop.orelse)
        self.assertEqual(len(loop.body), 2)
        variable = loop.target.id
        expected_bold = ast.parse(
            'self.assertIn(f"**{' + variable + '}**", text("AGENTS.md"))').body[0]
        expected_regex = ast.parse(
            'self.assertRegex(text(".ai/lifecycle.md"), rf"\\| {' + variable + '} ")').body[0]
        self.assertEqual(ast.dump(loop.body[0]), ast.dump(expected_bold))
        self.assertEqual(ast.dump(loop.body[1]), ast.dump(expected_regex))
        expected_runtime = ast.parse(
            'self.assertEqual(set(lifecycle.REQUIRED), set(lifecycle.TIERS))').body[0]
        self.assertEqual(ast.dump(runtime), ast.dump(expected_runtime))
        all_reads = [n for n in ast.walk(method) if isinstance(n, ast.Call)
                     and isinstance(n.func, ast.Name) and n.func.id == 'text']
        self.assertEqual([ast.literal_eval(n.args[0]) for n in all_reads], TIER_DOC_DOCS)

    def test_reachable_added_dependencies_require_review(self):
        variants = [(p, ()) for p in TIER_DOC_SETUP_PINS]
        variants += [(TIER_DOC_TESTS[0], ('Tiers', TIER_DOC_COMMAND[2].split('.')[1])),
                     (TIER_DOC_TESTS[0], ('text',)),
                     ('.ai/scripts/scratch.py', ('require_disk',)),
                     ('.ai/scripts/lifecycle.py', ('lazy',)),
                     ('.ai/scripts/review_guard.py', ('protected',)),
                     ('.ai/scripts/review_guard.py', ('protected', 'decorate')),
                     (TIER_DOC_TESTS[0], ('import-helper',))]
        for name, body in variants:
            with self.subTest(name=name, body=body):
                case = TierDocDependencyTests('test_order_scope_and_independent_oracle')
                setup = case.setUp

                def mutated_setup():
                    setup()
                    import ast
                    path = case.root / name
                    source = path.read_text()
                    tree = ast.parse(source)
                    addition = '__import__("pathlib").Path("unrelated.md").read_text()\n'
                    if body == ('import-helper',):
                        helper = '.ai/scripts/tests/unreviewed_tier_helper.py'
                        case.write(helper, addition)
                        case.assertNotIn(helper, ledger.input_paths(case.root, TIER_DOC_INPUTS))
                        addition = 'import unreviewed_tier_helper\n'
                    if body and body != ('import-helper',):
                        node = tree
                        for part in body:
                            node = next(n for n in node.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))
                                        and n.name == part)
                        first = node.body[0]
                        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                                and isinstance(first.value.value, str):
                            after = first.end_lineno
                        else:
                            after = min([first.lineno, *[n.lineno for n in
                                         getattr(first, 'decorator_list', [])]]) - 1
                        addition = ' ' * first.col_offset + addition
                    else:
                        after = max(n.end_lineno for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom)))
                    lines = source.splitlines(keepends=True)
                    changed = ''.join(lines[:after]) + addition + ''.join(lines[after:])
                    path.write_text(changed)
                    case.assertNotEqual(source, changed)
                    case.assertEqual(path.read_text(), changed)
                    case.assertNotIn('unrelated.md', ledger.input_paths(case.root, TIER_DOC_INPUTS))
                    missing = case.process(TIER_DOC_COMMAND)
                    case.assertNotEqual(missing.returncode, 0)
                    case.assertIn('FileNotFoundError', missing.stdout + missing.stderr)
                    case.assertIn('unrelated.md', missing.stdout + missing.stderr)
                    case.write('unrelated.md', 'new excluded dependency')
                    case.execution()

                case.setUp = mutated_setup
                result = unittest.TestResult()
                case.run(result)
                self.assertEqual(result.testsRun, 1)
                self.assertFalse(result.errors, result.errors)
                self.assertEqual(len(result.failures), 1, 'unreviewed dependency survived: ' + repr((name, body)))
                self.assertIn('review tier doc dependency boundary', result.failures[0][1])


class TierDocCompatibilityTests(TierDocFixture):  # R4
    def test_advisory_guide_and_existing_contracts(self):
        self.assert_prior_profiles()
        self.assertIsNone(ledger.default_inputs(TIER_DOC_COMMAND))
        self.assertEqual(ledger.default_inputs(COMMAND), ('python-tests', ['**']))
        for argv in (['python3', '-m', 'unittest', 'discover', '-s', '.ai/scripts/tests'],
                     *[['python3', '.ai/scripts/run_tests.py', '-j', str(n)] for n in (1, 8, 32)]):
            self.refused(argv=argv)
        value = self.suggestion()
        self.assertNotIn(EXCLUDE, value['inputs'])
        self.assertEqual(value['schema_version'], 1)
        self.assertTrue(value['review_required'])
        self.assertIn('runtime', ' '.join(value['limitations']).lower())
        guide = (self.root / ARCH_GUIDE).read_text()
        for phrase in ('python-tier-doc-contract', ' '.join(TIER_DOC_COMMAND),
                       'static', 'conservative', 'explicit', 'manual', 'substring',
                       'observed runtime tier', 'runtime', 'set equality', 'nonempty', 'tuple type',
                       'section bodies', 'duplicates', 'enforcement', 'nine prior profiles',
                       'REQUIRED values', 'unescaped', 'vacuous', 'mapping type',
                       *TIER_DOC_DOCS):
            self.assertIn(phrase, guide)


class TierDocFrameworkEndToEndTests(TierDocFixture):  # R5
    def record(self):
        value = self.suggestion()
        before = self.preflight()
        self.runtime_baseline()
        self.lc('tier', 'L1', '--reason', 'static tier doc framework fixture')
        self.lc('run', 'tier-doc', *value['lifecycle_inputs_argv'], '--', *TIER_DOC_COMMAND)
        self.assert_inputs_unchanged(before)
        import lifecycle
        entry = lifecycle.load(self.root)['ledger'][-1]
        self.assertEqual((entry['argv'], entry['inputs'], entry['exit']),
                         (TIER_DOC_COMMAND, value['inputs'], 0))
        self.assertIn('REUSE', self.lc('reuse', 'tier-doc'))

    def test_each_input_and_addition_invalidates(self):
        self.record()
        for name in ('.ai/scripts/tests/unrelated.py', 'unrelated.md'):
            self.edit_and_restore(name, lambda: self.assertIn('REUSE', self.lc('reuse', 'tier-doc')))
            self.assertIn('REUSE', self.lc('reuse', 'tier-doc'))
        for name in [*TIER_DOC_DOCS, *TIER_DOC_TESTS,
                     '.ai/scripts/review_guard.py', '.ai/scripts/new_tier.py']:
            with self.subTest(name=name):
                def stale():
                    result = self.process([sys.executable, '.ai/scripts/lifecycle.py', 'reuse', 'tier-doc'])
                    self.assertEqual(result.returncode, 1, 'missing tier doc freshness invalidation: ' + name)
                    self.assertIn('RERUN', result.stdout)
                self.edit_and_restore(name, stale)
                self.assertIn('REUSE', self.lc('reuse', 'tier-doc'))
        self.assertFalse((self.root / 'knowledge').exists())


class TierDocFailureTests(TierDocFixture):  # R5
    def test_nine_assertion_failures_fail_actual_command(self):
        tiers = self.runtime_baseline()
        variants = [('bold', tier) for tier in tiers] + [('regex', tier) for tier in tiers]
        variants.append(('runtime', 'REQUIRED'))
        self.assertEqual(len(variants), 9)
        for kind, term in variants:
            with self.subTest(kind=kind, term=term):
                name = {'bold': TIER_DOC_DOCS[0], 'regex': TIER_DOC_DOCS[1],
                        'runtime': '.ai/scripts/lifecycle.py'}[kind]
                path = self.root / name
                original = path.read_bytes()
                if kind == 'bold':
                    token = ('**' + term + '**').encode()
                    self.assertIn(token, original)
                    changed = original.replace(token, b'removed bold tier')
                    self.assertNotIn(token, changed)
                    criterion = repr(token.decode()) + ' not found in'
                elif kind == 'regex':
                    pattern = r'\| ' + term + ' '
                    self.assertRegex(original.decode(), pattern)
                    changed = re.sub(pattern, 'removed tier ', original.decode()).encode()
                    self.assertNotRegex(changed.decode(), pattern)
                    criterion = 'Regex didn'
                else:
                    import ast
                    source = original.decode()
                    assignment = next(n for n in ast.parse(source).body if isinstance(n, ast.Assign)
                                      and any(isinstance(t, ast.Name) and t.id == 'REQUIRED' for t in n.targets))
                    mapping = ast.literal_eval(assignment.value)
                    self.assertEqual(set(mapping), set(tiers))
                    mapping['unexpected-tier'] = ()
                    lines = source.splitlines(keepends=True)
                    changed = (''.join(lines[:assignment.lineno - 1])
                               + 'REQUIRED = ' + repr(mapping) + '\n'
                               + ''.join(lines[assignment.end_lineno:])).encode()
                    criterion = 'Items in the first set but not the second:'
                path.write_bytes(changed)
                try:
                    self.assertNotEqual(original, changed)
                    self.assertEqual(path.read_bytes(), changed)
                    self.suggestion()
                    result = self.execution(failure=criterion)
                    output = result.stdout + result.stderr
                    if kind == 'runtime':
                        self.assertIn('unexpected-tier', output)
                        self.assertIn('set(lifecycle.REQUIRED), set(lifecycle.TIERS)', output)
                    elif kind == 'regex':
                        self.assertIn(repr(r'\| ' + term + ' '), output)
                finally:
                    path.write_bytes(original)


class TierDocAdopterEndToEndTests(TierDocFixture):  # R6
    def test_explicit_adoption_freshness_identity_and_receipt(self):
        (self.root / '.agentic.json').unlink()
        self.lc('tier', 'L1', '--reason', 'static tier doc adopter fixture')
        result = self.process([sys.executable, '.ai/scripts/okf.py', 'init'])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.write('knowledge/project/sync-ignore', '*\n')
        value = self.suggestion()
        prefix = ('---\ntype: Capability\ntitle: Tier documentation\nnamespace: TIERDOC\nstatus: draft\n---\n'
                  '# Tier documentation\n\n## Requirements\n\n- TIERDOC-R1: The static check MUST pass.\n'
                  '  - Verify: `' + ' '.join(TIER_DOC_COMMAND) + '`\n')
        original = prefix + value['inputs_line'] + '\n'
        capability = self.write('knowledge/capabilities/tier-doc.md', original)
        self.commit()

        def status():
            result = self.process([sys.executable, '.ai/scripts/lifecycle.py', 'assure', '--json'])
            data = json.loads(result.stdout)
            state = next(r['status'] for r in data['requirements'] if r['id'] == 'TIERDOC-R1')
            self.assertEqual(result.returncode, 0 if state == 'VERIFIED' else 1, result.stdout + result.stderr)
            return state

        self.assertEqual(status(), 'UNVERIFIED')
        before = self.preflight()
        self.lc('assure', '--run', 'TIERDOC-R1')
        self.assert_inputs_unchanged(before)
        self.assertEqual(status(), 'VERIFIED')
        for name in ('.ai/scripts/tests/unrelated.py', 'unrelated.md'):
            self.edit_and_restore(name, lambda: self.assertEqual(status(), 'VERIFIED'))
            self.assertEqual(status(), 'VERIFIED')
        for name in [*TIER_DOC_DOCS, *TIER_DOC_TESTS,
                     '.ai/scripts/review_guard.py', '.ai/scripts/new_tier.py']:
            with self.subTest(name=name):
                self.edit_and_restore(name, lambda: self.assertEqual(status(), 'STALE'))
                self.assertEqual(status(), 'VERIFIED')
        reordered = [*value['inputs'][:-2], value['inputs'][-1], value['inputs'][-2]]
        capability.write_text(prefix + '  - Inputs: ' + ' '.join('`' + p + '`' for p in reordered) + '\n')
        self.assertEqual(status(), 'UNVERIFIED')
        capability.write_text(original.replace(TIER_DOC_COMMAND[2] + '`',
                                               TIER_DOC_COMMAND[2] + ' -v`'))
        self.assertEqual(status(), 'UNVERIFIED')
        capability.write_text(original)
        self.assertEqual(status(), 'VERIFIED')
        entries = [e for p in (self.root / 'knowledge/history/lifecycle').glob('*.json')
                   for e in json.loads(p.read_text()).get('ledger', []) if e['label'] == 'req:TIERDOC-R1']
        self.assertEqual((entries[-1]['argv'], entries[-1]['inputs'], entries[-1]['exit']),
                         (TIER_DOC_COMMAND, TIER_DOC_INPUTS + [EXCLUDE], 0))
        self.write('knowledge/history/lifecycle/extra-receipt.json', '{}\n')
        self.assertEqual(status(), 'VERIFIED')


class TierDocControlTests(TierDocFixture):  # R6
    def test_confirmed_broken_variants_fail_intended_criteria(self):
        method = 'test_each_input_and_addition_invalidates'
        variants = [(p, TierDocFrameworkEndToEndTests, method,
                     'missing tier doc freshness invalidation: ' + p)
                    for p in TIER_DOC_DOCS]
        variants += [('loose', TierDocProfileTests, 'test_exact_registration_and_prior_profiles', '0 != 2'),
                     ('empty', TierDocFrameworkEndToEndTests, method,
                      'tier doc execution count must be one')]
        self.assertEqual(len(variants), 4)
        for variant, cls, test, criterion in variants:
            with self.subTest(variant=variant):
                case = cls(test)
                setup = case.setUp

                def mutated_setup():
                    setup()
                    path = case.root / '.ai/scripts/assurance_inputs.py'
                    original = path.read_text()
                    if variant in TIER_DOC_DOCS:
                        catalog = copy.deepcopy(case.module().PROFILES)
                        profile = next(p for p in catalog if p['id'] == 'python-tier-doc-contract')
                        profile['inputs'].remove(variant)
                        del profile['rationale'][variant]
                        replacement = (original.split('PROFILES = ', 1)[0] + 'PROFILES = ' + repr(catalog)
                                       + '\nLIMITATIONS =' + original.split('\nLIMITATIONS =', 1)[1])
                    elif variant == 'loose':
                        old = "p['argv'] == list(argv)"
                        case.assertEqual(original.count(old), 1)
                        replacement = original.replace(old, "p['argv'] == list(argv)[:len(p['argv'])]")
                    else:
                        path = case.root / TIER_DOC_TESTS[0]
                        original = path.read_text()
                        replacement = 'import sys\nimport unittest\nunittest.main(argv=[sys.argv[0]])\n'
                    path.write_text(replacement)
                    case.assertNotEqual(original, replacement, 'mutation was not applied')
                    case.assertEqual(path.read_text(), replacement, 'mutation bytes differ')
                    if variant in TIER_DOC_DOCS:
                        value = case.suggestion()
                        case.assertNotIn(variant, value['inputs'])
                        case.assertNotIn(variant, value['rationale'])
                    if variant == 'empty':
                        result = case.process(TIER_DOC_COMMAND)
                        case.assertRegex(result.stdout + result.stderr, r'Ran 0 tests? in ')

                case.setUp = mutated_setup
                result = unittest.TestResult()
                case.run(result)
                self.assertEqual(result.testsRun, 1)
                self.assertFalse(result.errors, result.errors)
                self.assertEqual(len(result.failures), 1, 'broken variant survived: ' + variant)
                self.assertIn(criterion, result.failures[0][1])

ASSURANCE_DOC_COMMAND = ['python3', '.ai/scripts/tests/test_lifecycle_conformance.py',
                         'Assurance.test_assurance_documented']
ASSURANCE_DOC_TESTS = [ASSURANCE_DOC_COMMAND[1], '.ai/scripts/tests/disk_tmp.py']
ASSURANCE_DOC_DOCS = ['.ai/lifecycle.md']
ASSURANCE_DOC_INPUTS = ['.ai/scripts/**', '!.ai/scripts/tests/**',
                        *ASSURANCE_DOC_TESTS, *ASSURANCE_DOC_DOCS]


class AssuranceDocFixture(Fixture):
    def setUp(self):
        super().setUp()
        # Previous-profile export fixtures retain their own documents/helpers.
        for name in dict.fromkeys([*ASSURANCE_DOC_TESTS, *ASSURANCE_DOC_DOCS,
                                   '.ai/docs/lifecycle.md', *VALIDATION_POLICY_DOCS,
                                   *INSTALLER_DOC_TEXT, *REPORT_DOCS, *WIRING_JSON, *ARCH_TESTS[:-1]]):
            destination = self.root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(SCRIPTS.parent.parent / name, destination)
        self.commit()

    def export(self, argv=None, **kwargs):
        return super().export(argv=ASSURANCE_DOC_COMMAND if argv is None else argv, **kwargs)

    def selected_bytes(self):
        return {name: (self.root / name).read_bytes()
                for name in ledger.input_paths(self.root, ASSURANCE_DOC_INPUTS)}

    def assert_inputs_unchanged(self, before):
        self.assertEqual(self.selected_bytes(), before, 'assurance doc execution changed inputs')

    def execution(self, failure=None):
        before = self.selected_bytes()
        result = self.process(ASSURANCE_DOC_COMMAND)
        output = result.stdout + result.stderr
        counts = re.findall(r'Ran (\d+) tests? in ', output)
        self.assertEqual(len(counts), 1, 'assurance doc execution count missing or ambiguous: ' + output)
        self.assertEqual(int(counts[0]), 1, 'assurance doc execution count must be one: ' + output)
        if failure is None:
            self.assertEqual(result.returncode, 0, output)
            self.assertRegex(output, r'\nOK\s*$')
        else:
            self.assertNotEqual(result.returncode, 0, output)
            self.assertIn('AssertionError', output)
            self.assertIn(ASSURANCE_DOC_COMMAND[2].split('.')[1], output)
            self.assertIn(failure, output)
            self.assertNotIn('ERROR:', output)
        self.assert_inputs_unchanged(before)
        return result

    def preflight(self):
        before = self.selected_bytes()
        self.execution()
        return before

    def edit_and_restore(self, name, check):
        path = self.root / name
        original = path.read_bytes() if path.exists() else None
        changed = (original or b'') + b'\n '
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(changed)
        try:
            self.assertNotEqual(original, changed)
            self.assertEqual(path.read_bytes(), changed)
            if name in ASSURANCE_DOC_DOCS:
                self.execution()
            check()
        finally:
            if original is None:
                path.unlink()
                self.assertFalse(path.exists())
            else:
                path.write_bytes(original)
                self.assertEqual(path.read_bytes(), original)

    def assert_prior_profiles(self):
        result = subprocess.run(
            ['git', 'show', '22c65521b281fce485ec5d10e45359cded53ec3f:.ai/scripts/assurance_inputs.py'],
            cwd=SCRIPTS.parent.parent, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        import ast
        baseline = next(ast.literal_eval(n.value) for n in ast.parse(result.stdout).body
                        if isinstance(n, ast.Assign)
                        and any(isinstance(t, ast.Name) and t.id == 'PROFILES' for t in n.targets))
        identities = ('python-runner-test', 'python-architecture-compatibility', 'python-harness-wiring',
                      'python-reviewer-report-contract', 'python-installer-doc-contract',
                      'python-validation-policy-contract', 'python-audit-doc-contract',
                      'python-analysis-convergence-doc-contract', 'python-stage-doc-contract',
                      'python-tier-doc-contract')
        self.assertEqual(tuple(p['id'] for p in baseline), identities)
        actual = self.module().PROFILES
        self.assertEqual(len(actual), 13)
        for expected in baseline:
            self.assertEqual(next(p for p in actual if p['id'] == expected['id']), expected)
            value = self.suggestion(argv=expected['argv'])
            self.assertEqual((value['profile_id'], value['argv'], value['inputs'], value['rationale']),
                             (expected['id'], expected['argv'], expected['inputs'], expected['rationale']))


class AssuranceDocProfileTests(AssuranceDocFixture):  # R1
    def test_exact_registration_and_prior_profiles(self):
        value = self.suggestion()
        self.assertEqual(value['profile_id'], 'python-assurance-doc-contract')
        self.assertEqual(value['argv'], ASSURANCE_DOC_COMMAND)
        self.assert_prior_profiles()
        for argv in (ASSURANCE_DOC_COMMAND[:2], ASSURANCE_DOC_COMMAND[:2] + ['Assurance'],
                     ASSURANCE_DOC_COMMAND[:2] + ['Assurance.test_other'],
                     ASSURANCE_DOC_COMMAND + ['-v'], [sys.executable, *ASSURANCE_DOC_COMMAND[1:]],
                     ['python3', './' + ASSURANCE_DOC_COMMAND[1], ASSURANCE_DOC_COMMAND[2]],
                     ['python3', '-m', 'unittest', 'discover', '-s', '.ai/scripts/tests',
                      '-p', 'test_lifecycle_conformance.py']):
            self.assertIn('exact command', self.refused(argv=argv)['reason'])
        self.refused(cwd=self.root / '.ai')


class AssuranceDocExportTests(AssuranceDocFixture):  # R3
    def test_readonly_formats_supplements_and_no_semantic_parsing(self):
        marker = self.root / 'executed'
        for name in ASSURANCE_DOC_TESTS:
            self.write(name, f'from pathlib import Path\nPath({str(marker)!r}).touch()\nraise RuntimeError("executed")\n')
        self.write(ASSURANCE_DOC_DOCS[0], 'nonconforming static document')
        for name in ('space file.txt', 'second.txt'):
            self.write(name, 'supplement')
        before = snapshot(self.root)
        extra = ('space file.txt', 'second.txt')
        value = self.suggestion(extra=extra)
        text = self.export(extra=extra, json_output=False)
        self.assertEqual(text.returncode, 0, text.stderr)
        self.assertEqual(value['inputs'], ASSURANCE_DOC_INPUTS + list(extra))
        self.assertEqual(value['lifecycle_inputs_argv'], ['--inputs', *value['inputs']])
        for item in (value['profile_id'], value['inputs_line'], json.dumps(ASSURANCE_DOC_COMMAND),
                     json.dumps(value['lifecycle_inputs_argv']), *value['rationale'].values(), *value['limitations']):
            self.assertIn(item, text.stdout)
        raw = ('- ASSURANCEDOC-R1: The check MUST pass.\n  - Verify: `'
               + ' '.join(ASSURANCE_DOC_COMMAND) + '`\n' + value['inputs_line'] + '\n')
        parsed = assurance.parse('ASSURANCEDOC-R1', 'capabilities/assurance-doc.md', raw, root=self.root)
        self.assertIsNone(parsed.invalid)
        self.assertEqual(list(parsed.globs), value['inputs'])
        self.assertTrue(value['review_required'])
        self.assertEqual(snapshot(self.root), before)
        self.assertFalse(marker.exists())

    def test_required_literals_and_unsafe_boundaries_refuse(self):
        for name in [*ASSURANCE_DOC_TESTS, *ASSURANCE_DOC_DOCS]:
            path = self.root / name
            original = path.read_bytes()
            path.unlink()
            try:
                self.refused()
            finally:
                path.write_bytes(original)
        self.assertEqual(self.suggestion()['inputs'], ASSURANCE_DOC_INPUTS)
        name = ASSURANCE_DOC_DOCS[0]
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
        try:
            self.refused()
        finally:
            path.unlink()
            path.write_bytes(original)
        for extra in ('!README.md', '../x', '/etc/passwd', '', 'x`bad', '--other-option'):
            self.refused(extra=(extra,))


# Independent selected-source contract; neither tuple is derived from PROFILES.
ASSURANCE_DOC_TERMS = (
    '- Verify:', '- Inputs:', 'VERIFIED', 'STALE', 'FAILED', 'UNVERIFIED',
    'INVALID', 'MANUAL', 'UNDECLARED', 'lifecycle.py assure', '--run', '--changed', '--strict',
    'covers only that command on those inputs', 'whole tree', 'squash',
    'runtime executable changed', 'does not combine with',
    'python3 .ai/scripts/assurance_demo.py', 'python3 .ai/scripts/assurance_measure.py')
ASSURANCE_DOC_JUDGMENT_TERMS = (
    'judgment (attested, not verified):', '## Validation Reviewed', 'Accept-risk:',
    'risk_acceptance', 'not bound to', '`note:`', 'unauthenticated')
ASSURANCE_DOC_SECTION = r'(?s)## Assurance status\n(.*?)(?=\n## )'
ASSURANCE_DOC_ROW = r'(?m)^\| Assurance \| `assure'
# Reviewed eager setup and called bodies for this selection, not reached producer bodies.
ASSURANCE_DOC_SETUP_PINS = {
    '.ai/scripts/tests/test_lifecycle_conformance.py': '50977be9e0fc2636e75b83eba96f267339efd91e89f3d035690d0a0e24e8a02b',
    '.ai/scripts/tests/disk_tmp.py': 'fff9eed82f770bce05c477c507ad3c00dae4a16c216521b004646837c0bdd02f',
    '.ai/scripts/scratch.py': '523cbb977066b41423329249d132d2dc27a2f963db15b71489c2579fdb093060',
    '.ai/scripts/lifecycle.py': '048f391c166ffb58b8ba1d769ca287adc78d5c155a28bebba043e0d93a30e1ca',
    '.ai/scripts/review_guard.py': '2d806b1c16cb028a8b2197aec8881b0a4db1a962125f5a5d50a8599b01c45d69',
    '.ai/scripts/ledger.py': 'fc2423e775969cdc28173f970d7c676e6ad254e8f5e120abb89a5c1244b80cab',
}


class AssuranceDocDependencyTests(AssuranceDocFixture):  # R2
    def test_order_scope_and_independent_oracle(self):
        value = self.suggestion()
        actual = {p: report_setup_digest(self.root / p) for p in ASSURANCE_DOC_SETUP_PINS}
        self.assertEqual(actual, ASSURANCE_DOC_SETUP_PINS,
                         'review assurance doc dependency boundary: ' + repr(actual))
        self.assertEqual(value['inputs'], ASSURANCE_DOC_INPUTS)
        self.assertEqual(set(value['rationale']), set(ASSURANCE_DOC_INPUTS))
        for name, terms in {
            '.ai/scripts/**': ('conservative', 'import', 'lazy'),
            '!.ai/scripts/tests/**': ('exclude',),
            ASSURANCE_DOC_TESTS[0]: ('method', 'static'),
            ASSURANCE_DOC_TESTS[1]: ('helper',),
            ASSURANCE_DOC_DOCS[0]: ('sole', 'direct', 'twice'),
        }.items():
            for term in terms:
                self.assertIn(term, value['rationale'][name].lower())
        included = ['.ai/scripts/future_assurance.py', '.ai/scripts/assets/assurance.txt']
        compatibility = ['.ai/docs/lifecycle.md', *VALIDATION_POLICY_DOCS, *INSTALLER_DOC_TEXT,
                         *REPORT_DOCS, *WIRING_JSON, *ARCH_TESTS[:-1]]
        excluded = ['.ai/scripts/tests/unrelated.py', 'unrelated.md',
                    *[p for p in compatibility if p not in ASSURANCE_DOC_DOCS]]
        for name in included + excluded[:2]:
            self.write(name, '# independent inventory fixture\n')
        selected = set(ledger.input_paths(self.root, value['inputs']))
        imports = ['.ai/scripts/' + n + '.py' for n in
                   ('scratch', 'lifecycle', 'review_guard', 'ledger', 'brownfield',
                    'okf', 'learning', 'scan', 'project_context', 'assurance')]
        self.assertTrue(set([*ASSURANCE_DOC_TESTS, *ASSURANCE_DOC_DOCS, *imports, *included]).issubset(selected))
        self.assertFalse(set(excluded) & selected)
        import ast
        tree = ast.parse((self.root / ASSURANCE_DOC_TESTS[0]).read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Assurance')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                      and n.name == 'test_assurance_documented')
        self.assertEqual(len(method.body), 6)
        section, matched, body, terms, judgment, row = method.body
        expected = [
            'section = re.search(' + repr(ASSURANCE_DOC_SECTION) + ', text(".ai/lifecycle.md"))',
            'self.assertIsNotNone(section, ".ai/lifecycle.md needs an \'## Assurance status\' section")',
            'body = section.group(1)',
            'for term in ' + repr(ASSURANCE_DOC_TERMS) + ':\n    self.assertIn(term, body, term)',
            'for term in ' + repr(ASSURANCE_DOC_JUDGMENT_TERMS) + ':\n    self.assertIn(term, body, term)',
            'self.assertRegex(text(".ai/lifecycle.md"), ' + repr(ASSURANCE_DOC_ROW) + ', "Recording table row")',
        ]
        for node, source in zip((section, matched, body, terms, judgment, row), expected):
            self.assertEqual(ast.dump(node), ast.dump(ast.parse(source).body[0]),
                             'review assurance doc selected method boundary')
        self.assertEqual(ast.literal_eval(terms.iter), ASSURANCE_DOC_TERMS)
        self.assertEqual(ast.literal_eval(judgment.iter), ASSURANCE_DOC_JUDGMENT_TERMS)
        self.assertEqual((len(terms.iter.elts), len(judgment.iter.elts)), (20, 7))
        reads = [n for n in ast.walk(method) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Name) and n.func.id == 'text']
        self.assertEqual([ast.literal_eval(n.args[0]) for n in reads], ASSURANCE_DOC_DOCS * 2)
        self.assertTrue(re.compile(ASSURANCE_DOC_SECTION).flags & re.S)
        self.assertTrue(re.compile(ASSURANCE_DOC_ROW).flags & re.M)

    def test_reachable_added_dependencies_require_review(self):
        variants = [(p, ()) for p in ASSURANCE_DOC_SETUP_PINS]
        variants += [(ASSURANCE_DOC_TESTS[0], ('Assurance', 'test_assurance_documented')),
                     (ASSURANCE_DOC_TESTS[0], ('text',)),
                     ('.ai/scripts/scratch.py', ('require_disk',)),
                     ('.ai/scripts/lifecycle.py', ('lazy',)),
                     ('.ai/scripts/review_guard.py', ('protected',)),
                     ('.ai/scripts/review_guard.py', ('protected', 'decorate')),
                     (ASSURANCE_DOC_TESTS[0], ('import-helper',))]
        for name, body in variants:
            with self.subTest(name=name, body=body):
                case = AssuranceDocDependencyTests('test_order_scope_and_independent_oracle')
                setup = case.setUp

                def mutated_setup():
                    setup()
                    import ast
                    path = case.root / name
                    source = path.read_text()
                    tree = ast.parse(source)
                    addition = '__import__("pathlib").Path("unrelated.md").read_text()\n'
                    if body == ('import-helper',):
                        helper = '.ai/scripts/tests/unreviewed_assurance_helper.py'
                        case.write(helper, addition)
                        case.assertNotIn(helper, ledger.input_paths(case.root, ASSURANCE_DOC_INPUTS))
                        addition = 'import unreviewed_assurance_helper\n'
                    if body and body != ('import-helper',):
                        node = tree
                        for part in body:
                            node = next(n for n in node.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))
                                        and n.name == part)
                        first = node.body[0]
                        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                                and isinstance(first.value.value, str):
                            after = first.end_lineno
                        else:
                            after = min([first.lineno, *[n.lineno for n in
                                         getattr(first, 'decorator_list', [])]]) - 1
                        addition = ' ' * first.col_offset + addition
                    else:
                        after = max(n.end_lineno for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom)))
                    lines = source.splitlines(keepends=True)
                    changed = ''.join(lines[:after]) + addition + ''.join(lines[after:])
                    path.write_text(changed)
                    case.assertNotEqual(source, changed)
                    case.assertEqual(path.read_text(), changed)
                    case.assertFalse((case.root / 'unrelated.md').exists())
                    case.assertNotIn('unrelated.md', ledger.input_paths(case.root, ASSURANCE_DOC_INPUTS))
                    missing = case.process(ASSURANCE_DOC_COMMAND)
                    case.assertNotEqual(missing.returncode, 0)
                    case.assertIn('FileNotFoundError', missing.stdout + missing.stderr)
                    case.assertIn('unrelated.md', missing.stdout + missing.stderr)
                    case.write('unrelated.md', 'new excluded dependency')
                    case.execution()

                case.setUp = mutated_setup
                result = unittest.TestResult()
                case.run(result)
                self.assertEqual(result.testsRun, 1)
                self.assertFalse(result.errors, result.errors)
                self.assertEqual(len(result.failures), 1, 'unreviewed dependency survived: ' + repr((name, body)))
                self.assertIn('review assurance doc dependency boundary', result.failures[0][1])


class AssuranceDocCompatibilityTests(AssuranceDocFixture):  # R4
    def test_advisory_guide_and_existing_contracts(self):
        self.assert_prior_profiles()
        self.assertIsNone(ledger.default_inputs(ASSURANCE_DOC_COMMAND))
        self.assertEqual(ledger.default_inputs(COMMAND), ('python-tests', ['**']))
        for argv in (['python3', '-m', 'unittest', 'discover', '-s', '.ai/scripts/tests'],
                     *[['python3', '.ai/scripts/run_tests.py', '-j', str(n)] for n in (1, 8, 32)]):
            self.refused(argv=argv)
        value = self.suggestion()
        self.assertNotIn(EXCLUDE, value['inputs'])
        self.assertEqual(value['schema_version'], 1)
        self.assertTrue(value['review_required'])
        self.assertIn('runtime', ' '.join(value['limitations']).lower())
        guide = (self.root / ARCH_GUIDE).read_text()
        for phrase in ('python-assurance-doc-contract', ' '.join(ASSURANCE_DOC_COMMAND),
                       'two literal reads', '20', 'seven', '29 assertions', 'one test',
                       'DOTALL', 'MULTILINE', 'unanchored', 'first matching capture',
                       'case-sensitive', 'row-prefix', 'no end anchor', 'semantics',
                       'conservative', 'explicit', 'manual', 'ten prior profiles',
                       *ASSURANCE_DOC_INPUTS):
            self.assertIn(phrase, guide)
        baseline = subprocess.run(['git', 'show',
            '22c65521b281fce485ec5d10e45359cded53ec3f:.ai/lifecycle.md'],
            cwd=SCRIPTS.parent.parent, capture_output=True, text=True, timeout=10)
        self.assertEqual(baseline.returncode, 0, baseline.stderr)
        for paragraph in baseline.stdout.split('\n\n'):
            self.assertIn(paragraph, guide, 'previous guide paragraph changed')


class AssuranceDocFrameworkEndToEndTests(AssuranceDocFixture):  # R5
    def record(self):
        value = self.suggestion()
        before = self.preflight()
        self.lc('tier', 'L1', '--reason', 'static assurance doc framework fixture')
        self.lc('run', 'assurance-doc', *value['lifecycle_inputs_argv'], '--', *ASSURANCE_DOC_COMMAND)
        self.assert_inputs_unchanged(before)
        import lifecycle
        entry = lifecycle.load(self.root)['ledger'][-1]
        self.assertEqual((entry['argv'], entry['inputs'], entry['exit']),
                         (ASSURANCE_DOC_COMMAND, value['inputs'], 0))
        self.assertIn('REUSE', self.lc('reuse', 'assurance-doc'))

    def test_each_input_and_addition_invalidates(self):
        self.record()
        for name in ('.ai/scripts/tests/unrelated.py', 'unrelated.md'):
            self.edit_and_restore(name, lambda: self.assertIn('REUSE', self.lc('reuse', 'assurance-doc')))
            self.assertIn('REUSE', self.lc('reuse', 'assurance-doc'))
        for name in [*ASSURANCE_DOC_DOCS, *ASSURANCE_DOC_TESTS,
                     '.ai/scripts/review_guard.py', '.ai/scripts/new_assurance.py']:
            with self.subTest(name=name):
                def stale():
                    result = self.process([sys.executable, '.ai/scripts/lifecycle.py', 'reuse', 'assurance-doc'])
                    self.assertEqual(result.returncode, 1, 'missing assurance doc freshness invalidation: ' + name)
                    self.assertIn('RERUN', result.stdout)
                self.edit_and_restore(name, stale)
                self.assertIn('REUSE', self.lc('reuse', 'assurance-doc'))
        self.assertFalse((self.root / 'knowledge').exists())


class AssuranceDocFailureTests(AssuranceDocFixture):  # R5
    def test_twenty_nine_assertion_failures_fail_actual_command(self):
        path = self.root / ASSURANCE_DOC_DOCS[0]
        original = path.read_bytes()
        document = original.decode()
        capture = re.search(ASSURANCE_DOC_SECTION, document)
        self.assertIsNotNone(capture)
        tokens = (*ASSURANCE_DOC_TERMS, *ASSURANCE_DOC_JUDGMENT_TERMS)
        self.assertEqual((len(ASSURANCE_DOC_TERMS), len(ASSURANCE_DOC_JUDGMENT_TERMS)), (20, 7))
        self.assertEqual(len(set(tokens)), 27)
        self.execution()
        variants = [('section', None), *[('token', t) for t in tokens], ('row', None)]
        self.assertEqual(len(variants), 29)
        for kind, term in variants:
            with self.subTest(kind=kind, term=term):
                if kind == 'section':
                    self.assertIn('## Assurance status\n', document)
                    changed = document.replace('## Assurance status\n', '## Removed assurance section\n')
                    self.assertIsNone(re.search(ASSURANCE_DOC_SECTION, changed))
                    criterion = "needs an '## Assurance status' section"
                    assertion = 'self.assertIsNotNone(section,'
                elif kind == 'token':
                    body = capture.group(1)
                    self.assertIn(term, body)
                    changed_body = body.replace(term, '[removed]')
                    self.assertNotIn(term, changed_body)
                    for earlier in tokens[:tokens.index(term)]:
                        self.assertIn(earlier, changed_body)
                    changed = document[:capture.start(1)] + changed_body + document[capture.end(1):]
                    after = re.search(ASSURANCE_DOC_SECTION, changed)
                    self.assertIsNotNone(after)
                    self.assertEqual(after.start(1), capture.start(1))
                    self.assertEqual(after.group(1), changed_body)
                    self.assertEqual(changed[after.end(1):], document[capture.end(1):])
                    criterion = 'AssertionError: ' + repr(term) + ' not found in'
                    assertion = 'self.assertIn(term, body, term)'
                else:
                    self.assertRegex(document, ASSURANCE_DOC_ROW)
                    changed = re.sub(ASSURANCE_DOC_ROW, '| Removed recording | `assure', document)
                    self.assertNotRegex(changed, ASSURANCE_DOC_ROW)
                    self.assertEqual(re.search(ASSURANCE_DOC_SECTION, changed).group(1), capture.group(1))
                    criterion = 'Recording table row'
                    assertion = 'self.assertRegex(text('
                path.write_bytes(changed.encode())
                try:
                    self.assertNotEqual(original, path.read_bytes())
                    self.assertEqual(path.read_bytes(), changed.encode())
                    self.suggestion()
                    result = self.execution(failure=criterion)
                    self.assertIn(assertion, result.stdout + result.stderr)
                finally:
                    path.write_bytes(original)
                    self.assertEqual(path.read_bytes(), original)


class AssuranceDocAdopterEndToEndTests(AssuranceDocFixture):  # R6
    def test_explicit_adoption_freshness_identity_and_receipt(self):
        (self.root / '.agentic.json').unlink()
        self.lc('tier', 'L1', '--reason', 'static assurance doc adopter fixture')
        result = self.process([sys.executable, '.ai/scripts/okf.py', 'init'])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.write('knowledge/project/sync-ignore', '*\n')
        value = self.suggestion()
        prefix = ('---\ntype: Capability\ntitle: Assurance documentation\nnamespace: ASSURANCEDOC\nstatus: draft\n---\n'
                  '# Assurance documentation\n\n## Requirements\n\n- ASSURANCEDOC-R1: The static check MUST pass.\n'
                  '  - Verify: `' + ' '.join(ASSURANCE_DOC_COMMAND) + '`\n')
        original = prefix + value['inputs_line'] + '\n'
        capability = self.write('knowledge/capabilities/assurance-doc.md', original)
        self.commit()

        def status():
            result = self.process([sys.executable, '.ai/scripts/lifecycle.py', 'assure', '--json'])
            data = json.loads(result.stdout)
            state = next(r['status'] for r in data['requirements'] if r['id'] == 'ASSURANCEDOC-R1')
            self.assertEqual(result.returncode, 0 if state == 'VERIFIED' else 1, result.stdout + result.stderr)
            return state

        self.assertEqual(status(), 'UNVERIFIED')
        before = self.preflight()
        self.lc('assure', '--run', 'ASSURANCEDOC-R1')
        self.assert_inputs_unchanged(before)
        self.assertEqual(status(), 'VERIFIED')
        for name in ('.ai/scripts/tests/unrelated.py', 'unrelated.md'):
            self.edit_and_restore(name, lambda: self.assertEqual(status(), 'VERIFIED'))
            self.assertEqual(status(), 'VERIFIED')
        for name in [*ASSURANCE_DOC_DOCS, *ASSURANCE_DOC_TESTS,
                     '.ai/scripts/review_guard.py', '.ai/scripts/new_assurance.py']:
            with self.subTest(name=name):
                self.edit_and_restore(name, lambda: self.assertEqual(status(), 'STALE'))
                self.assertEqual(status(), 'VERIFIED')
        reordered = [*value['inputs'][:-2], value['inputs'][-1], value['inputs'][-2]]
        capability.write_text(prefix + '  - Inputs: ' + ' '.join('`' + p + '`' for p in reordered) + '\n')
        self.assertEqual(status(), 'UNVERIFIED')
        capability.write_text(original.replace(ASSURANCE_DOC_COMMAND[2] + '`',
                                               ASSURANCE_DOC_COMMAND[2] + ' -v`'))
        self.assertEqual(status(), 'UNVERIFIED')
        capability.write_text(original)
        self.assertEqual(status(), 'VERIFIED')
        entries = [e for p in (self.root / 'knowledge/history/lifecycle').glob('*.json')
                   for e in json.loads(p.read_text()).get('ledger', []) if e['label'] == 'req:ASSURANCEDOC-R1']
        self.assertEqual((entries[-1]['argv'], entries[-1]['inputs'], entries[-1]['exit']),
                         (ASSURANCE_DOC_COMMAND, ASSURANCE_DOC_INPUTS + [EXCLUDE], 0))
        self.write('knowledge/history/lifecycle/extra-receipt.json', '{}\n')
        self.assertEqual(status(), 'VERIFIED')


class AssuranceDocControlTests(AssuranceDocFixture):  # R6
    def test_confirmed_broken_variants_fail_intended_criteria(self):
        method = 'test_each_input_and_addition_invalidates'
        variants = [(ASSURANCE_DOC_DOCS[0], AssuranceDocFrameworkEndToEndTests, method,
                     'missing assurance doc freshness invalidation: ' + ASSURANCE_DOC_DOCS[0]),
                    ('loose', AssuranceDocProfileTests, 'test_exact_registration_and_prior_profiles', '0 != 2'),
                    ('empty', AssuranceDocFrameworkEndToEndTests, method,
                     'assurance doc execution count must be one')]
        self.assertEqual(len(variants), 3)
        for variant, cls, test, criterion in variants:
            with self.subTest(variant=variant):
                case = cls(test)
                setup = case.setUp

                def mutated_setup():
                    setup()
                    path = case.root / '.ai/scripts/assurance_inputs.py'
                    original = path.read_text()
                    if variant in ASSURANCE_DOC_DOCS:
                        catalog = copy.deepcopy(case.module().PROFILES)
                        profile = next(p for p in catalog if p['id'] == 'python-assurance-doc-contract')
                        profile['inputs'].remove(variant)
                        del profile['rationale'][variant]
                        replacement = (original.split('PROFILES = ', 1)[0] + 'PROFILES = ' + repr(catalog)
                                       + '\nLIMITATIONS =' + original.split('\nLIMITATIONS =', 1)[1])
                    elif variant == 'loose':
                        old = "p['argv'] == list(argv)"
                        case.assertEqual(original.count(old), 1)
                        replacement = original.replace(old, "p['argv'] == list(argv)[:len(p['argv'])]")
                    else:
                        path = case.root / ASSURANCE_DOC_TESTS[0]
                        original = path.read_text()
                        replacement = 'import sys\nimport unittest\nunittest.main(argv=[sys.argv[0]])\n'
                    path.write_text(replacement)
                    case.assertNotEqual(original, replacement, 'mutation was not applied')
                    case.assertEqual(path.read_text(), replacement, 'mutation bytes differ')
                    if variant in ASSURANCE_DOC_DOCS:
                        value = case.suggestion()
                        case.assertNotIn(variant, value['inputs'])
                        case.assertNotIn(variant, value['rationale'])
                    if variant == 'empty':
                        result = case.process(ASSURANCE_DOC_COMMAND)
                        case.assertRegex(result.stdout + result.stderr, r'Ran 0 tests? in ')

                case.setUp = mutated_setup
                result = unittest.TestResult()
                case.run(result)
                self.assertEqual(result.testsRun, 1)
                self.assertFalse(result.errors, result.errors)
                self.assertEqual(len(result.failures), 1, 'broken variant survived: ' + variant)
                self.assertIn(criterion, result.failures[0][1])


AGENTS_BUDGET_COMMAND = ['python3', '.ai/scripts/tests/test_lifecycle_conformance.py',
                         'AgentsBudget.test_agents_md_stays_below_its_cold_start_budget']
AGENTS_BUDGET_TESTS = [AGENTS_BUDGET_COMMAND[1], '.ai/scripts/tests/disk_tmp.py']
AGENTS_BUDGET_INPUTS = ['.ai/scripts/**', '!.ai/scripts/tests/**', *AGENTS_BUDGET_TESTS, 'AGENTS.md']
AGENTS_BUDGET_HEAD = 'cf158b53b9c164b22a3172792ab3c86980106e0e'


class AgentsBudgetFixture(Fixture):
    def setUp(self):
        super().setUp()
        # Compatibility exports retain their own documents; only AGENTS is a direct read here.
        for name in dict.fromkeys([*AGENTS_BUDGET_TESTS, 'AGENTS.md', '.ai/lifecycle.md',
                                   '.ai/docs/lifecycle.md', *VALIDATION_POLICY_DOCS,
                                   *INSTALLER_DOC_TEXT, *REPORT_DOCS, *WIRING_JSON, *ARCH_TESTS[:-1]]):
            destination = self.root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(SCRIPTS.parent.parent / name, destination)
        self.commit()

    def export(self, argv=None, **kwargs):
        return super().export(argv=AGENTS_BUDGET_COMMAND if argv is None else argv, **kwargs)

    def selected_bytes(self):
        return {name: (self.root / name).read_bytes()
                for name in ledger.input_paths(self.root, AGENTS_BUDGET_INPUTS)}

    def assert_inputs_unchanged(self, before):
        self.assertEqual(self.selected_bytes(), before, 'agents budget execution changed inputs')

    def execution(self, failure=None):
        before = self.selected_bytes()
        result = self.process(AGENTS_BUDGET_COMMAND)
        output = result.stdout + result.stderr
        counts = re.findall(r'Ran (\d+) tests? in ', output)
        self.assertEqual(len(counts), 1, 'agents budget execution count missing or ambiguous: ' + output)
        self.assertEqual(int(counts[0]), 1, 'agents budget execution count must be one: ' + output)
        if failure is None:
            self.assertEqual(result.returncode, 0, output)
            self.assertRegex(output, r'\nOK\s*$')
        else:
            self.assertNotEqual(result.returncode, 0, output)
            self.assertIn('AssertionError: ' + failure, output)
            self.assertIn(AGENTS_BUDGET_COMMAND[2].split('.')[1], output)
            self.assertIn('self.assertLess(len(text("AGENTS.md").encode()), 30_000)', output)
            self.assertNotIn('ERROR:', output)
            self.assertRegex(output, r'FAILED \(failures=1\)')
        self.assert_inputs_unchanged(before)
        return result

    def preflight(self):
        before = self.selected_bytes()
        self.execution()
        return before

    def edit_and_restore(self, name, check):
        path = self.root / name
        original = path.read_bytes() if path.exists() else None
        changed = (original or b'') + b'\n '
        if name == 'AGENTS.md':
            # Observe margin independently before making the small preserving edit.
            length = len(original.decode('utf-8').replace('\r\n', '\n').replace('\r', '\n').encode('utf-8'))
            self.assertLess(length + 2, 30000, 'freshness edit has insufficient budget margin')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(changed)
        try:
            self.assertNotEqual(original, changed)
            self.assertEqual(path.read_bytes(), changed)
            if name == 'AGENTS.md':
                self.execution()
            check()
        finally:
            if original is None:
                path.unlink()
                self.assertFalse(path.exists())
            else:
                path.write_bytes(original)
                self.assertEqual(path.read_bytes(), original)

    def assert_prior_profiles(self):
        result = subprocess.run(['git', 'show', AGENTS_BUDGET_HEAD + ':.ai/scripts/assurance_inputs.py'],
                                cwd=SCRIPTS.parent.parent, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        import ast
        baseline = next(ast.literal_eval(n.value) for n in ast.parse(result.stdout).body
                        if isinstance(n, ast.Assign)
                        and any(isinstance(t, ast.Name) and t.id == 'PROFILES' for t in n.targets))
        identities = ('python-runner-test', 'python-architecture-compatibility', 'python-harness-wiring',
                      'python-reviewer-report-contract', 'python-installer-doc-contract',
                      'python-validation-policy-contract', 'python-audit-doc-contract',
                      'python-analysis-convergence-doc-contract', 'python-stage-doc-contract',
                      'python-tier-doc-contract', 'python-assurance-doc-contract')
        self.assertEqual(tuple(p['id'] for p in baseline), identities)
        actual = self.module().PROFILES
        self.assertEqual(len(actual), 13)
        for expected in baseline:
            self.assertEqual(next(p for p in actual if p['id'] == expected['id']), expected)
            value = self.suggestion(argv=expected['argv'])
            self.assertEqual((value['profile_id'], value['argv'], value['inputs'], value['rationale']),
                             (expected['id'], expected['argv'], expected['inputs'], expected['rationale']))


class AgentsBudgetProfileTests(AgentsBudgetFixture):  # R1
    def test_exact_registration_and_prior_profiles(self):
        value = self.suggestion()
        self.assertEqual(value['profile_id'], 'python-agents-budget-contract')
        self.assertEqual(value['argv'], AGENTS_BUDGET_COMMAND)
        self.assert_prior_profiles()
        for argv in (AGENTS_BUDGET_COMMAND[:2], AGENTS_BUDGET_COMMAND[:2] + ['AgentsBudget'],
                     AGENTS_BUDGET_COMMAND[:2] + ['AgentsBudget.test_every_heading_survives'],
                     AGENTS_BUDGET_COMMAND + ['-v'], [sys.executable, *AGENTS_BUDGET_COMMAND[1:]],
                     ['python3', './' + AGENTS_BUDGET_COMMAND[1], AGENTS_BUDGET_COMMAND[2]],
                     ['python3', '-m', 'unittest', 'discover', '-s', '.ai/scripts/tests',
                      '-p', 'test_lifecycle_conformance.py']):
            self.assertIn('exact command', self.refused(argv=argv)['reason'])
        self.refused(cwd=self.root / '.ai')


class AgentsBudgetExportTests(AgentsBudgetFixture):  # R3
    def test_readonly_formats_supplements_and_no_execution(self):
        marker = self.root / 'executed'
        for name in AGENTS_BUDGET_TESTS:
            self.write(name, f'from pathlib import Path\nPath({str(marker)!r}).touch()\nraise RuntimeError("executed")\n')
        (self.root / 'AGENTS.md').write_bytes(b'a' * 30000)
        for name in ('space file.txt', 'second.txt'):
            self.write(name, 'supplement')
        before = snapshot(self.root)
        value = self.suggestion(extra=('space file.txt', 'second.txt'))
        text = self.export(extra=('space file.txt', 'second.txt'), json_output=False)
        self.assertEqual(text.returncode, 0, text.stderr)
        self.assertEqual(value['inputs'], AGENTS_BUDGET_INPUTS + ['space file.txt', 'second.txt'])
        self.assertEqual(value['lifecycle_inputs_argv'], ['--inputs', *value['inputs']])
        for item in (value['profile_id'], value['inputs_line'], json.dumps(AGENTS_BUDGET_COMMAND),
                     json.dumps(value['lifecycle_inputs_argv']), *value['rationale'].values(), *value['limitations']):
            self.assertIn(item, text.stdout)
        raw = ('- AGENTSBUDGET-R1: The check MUST pass.\n  - Verify: `'
               + ' '.join(AGENTS_BUDGET_COMMAND) + '`\n' + value['inputs_line'] + '\n')
        parsed = assurance.parse('AGENTSBUDGET-R1', 'capabilities/agents-budget.md', raw, root=self.root)
        self.assertIsNone(parsed.invalid)
        self.assertEqual(list(parsed.globs), value['inputs'])
        self.assertTrue(value['review_required'])
        self.assertEqual(snapshot(self.root), before)
        self.assertFalse(marker.exists())

    def test_required_literals_and_unsafe_boundaries_refuse(self):
        for name in [*AGENTS_BUDGET_TESTS, 'AGENTS.md']:
            path = self.root / name
            original = path.read_bytes()
            path.unlink()
            try:
                self.refused()
            finally:
                path.write_bytes(original)
        self.assertEqual(self.suggestion()['inputs'], AGENTS_BUDGET_INPUTS)
        self.git('rm', '--cached', 'AGENTS.md')
        self.write('.gitignore', 'AGENTS.md\n')
        self.refused()
        self.git('add', '-f', 'AGENTS.md')
        path = self.root / 'AGENTS.md'
        original = path.read_bytes()
        outside = Path(self.temp.name) / 'outside.md'
        outside.write_bytes(original)
        path.unlink()
        path.symlink_to(outside)
        try:
            self.refused()
        finally:
            path.unlink()
            path.write_bytes(original)
        for extra in ('!README.md', '../x', '/etc/passwd', '', 'x`bad', '--other-option'):
            self.refused(extra=(extra,))


AGENTS_BUDGET_SETUP_PINS = {
    '.ai/scripts/tests/test_lifecycle_conformance.py': '50977be9e0fc2636e75b83eba96f267339efd91e89f3d035690d0a0e24e8a02b',
    '.ai/scripts/tests/disk_tmp.py': 'fff9eed82f770bce05c477c507ad3c00dae4a16c216521b004646837c0bdd02f',
    '.ai/scripts/scratch.py': '523cbb977066b41423329249d132d2dc27a2f963db15b71489c2579fdb093060',
    '.ai/scripts/lifecycle.py': '048f391c166ffb58b8ba1d769ca287adc78d5c155a28bebba043e0d93a30e1ca',
    '.ai/scripts/review_guard.py': '2d806b1c16cb028a8b2197aec8881b0a4db1a962125f5a5d50a8599b01c45d69',
    '.ai/scripts/ledger.py': 'fc2423e775969cdc28173f970d7c676e6ad254e8f5e120abb89a5c1244b80cab',
}


class AgentsBudgetDependencyTests(AgentsBudgetFixture):  # R2
    def test_order_scope_and_independent_oracle(self):
        value = self.suggestion()
        actual = {p: report_setup_digest(self.root / p) for p in AGENTS_BUDGET_SETUP_PINS}
        self.assertEqual(actual, AGENTS_BUDGET_SETUP_PINS,
                         'review agents budget dependency boundary: ' + repr(actual))
        self.assertEqual(value['inputs'], AGENTS_BUDGET_INPUTS)
        self.assertEqual(set(value['rationale']), set(AGENTS_BUDGET_INPUTS))
        for name, terms in {
            '.ai/scripts/**': ('conservative', 'import', 'lazy'),
            '!.ai/scripts/tests/**': ('exclude',),
            AGENTS_BUDGET_TESTS[0]: ('method', 'strict', 'one test'),
            AGENTS_BUDGET_TESTS[1]: ('helper',),
            'AGENTS.md': ('sole', 'direct', 'once', 'decoding', 'newline', 'utf-8', 'strict'),
        }.items():
            for term in terms:
                self.assertIn(term, value['rationale'][name].lower())
        included = ['.ai/scripts/future_budget.py', '.ai/scripts/assets/budget.txt']
        compatibility = ['.ai/lifecycle.md', '.ai/docs/lifecycle.md', *VALIDATION_POLICY_DOCS,
                         *INSTALLER_DOC_TEXT, *REPORT_DOCS, *WIRING_JSON, *ARCH_TESTS[:-1]]
        excluded = ['.ai/scripts/tests/unrelated.py', 'unrelated.md',
                    *[p for p in compatibility if p != 'AGENTS.md']]
        for name in included + excluded[:2]:
            self.write(name, '# independent inventory fixture\n')
        selected = set(ledger.input_paths(self.root, value['inputs']))
        imports = ['.ai/scripts/' + n + '.py' for n in
                   ('scratch', 'lifecycle', 'review_guard', 'ledger', 'brownfield',
                    'okf', 'learning', 'scan', 'project_context', 'assurance')]
        self.assertTrue(set([*AGENTS_BUDGET_TESTS, 'AGENTS.md', *imports, *included]).issubset(selected))
        self.assertFalse(set(excluded) & selected)
        import ast
        tree = ast.parse((self.root / AGENTS_BUDGET_TESTS[0]).read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'AgentsBudget')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                      and n.name == 'test_agents_md_stays_below_its_cold_start_budget')
        expected = ast.parse('self.assertLess(len(text("AGENTS.md").encode()), 30000)').body
        self.assertEqual([ast.dump(n) for n in method.body], [ast.dump(n) for n in expected],
                         'review agents budget selected method boundary')
        reads = [n for n in ast.walk(method) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Name) and n.func.id == 'text']
        self.assertEqual(len(reads), 1)
        self.assertEqual([ast.literal_eval(n.args[0]) for n in reads], ['AGENTS.md'])
        self.assertEqual(reads[0].keywords, [])

    def test_reachable_added_dependencies_require_review(self):
        # Enumerated for this selection; uncalled baseline/flat/producer bodies are pins only.
        variants = [(p, ()) for p in AGENTS_BUDGET_SETUP_PINS]
        variants += [(AGENTS_BUDGET_TESTS[0], ('AgentsBudget',)),
                     (AGENTS_BUDGET_TESTS[0], ('AgentsBudget', 'test_agents_md_stays_below_its_cold_start_budget')),
                     (AGENTS_BUDGET_TESTS[0], ('text',)),
                     ('.ai/scripts/scratch.py', ('require_disk',)),
                     ('.ai/scripts/lifecycle.py', ('lazy',)),
                     ('.ai/scripts/review_guard.py', ('protected',)),
                     ('.ai/scripts/review_guard.py', ('protected', 'decorate')),
                     (AGENTS_BUDGET_TESTS[0], ('import-helper',))]
        for name, body in variants:
            with self.subTest(name=name, body=body):
                case = AgentsBudgetDependencyTests('test_order_scope_and_independent_oracle')
                setup = case.setUp

                def mutated_setup():
                    setup()
                    import ast
                    path = case.root / name
                    original = path.read_bytes()
                    source = original.decode('utf-8')
                    tree = ast.parse(source)
                    addition = '__import__("pathlib").Path("unrelated.md").read_text()\n'
                    if body == ('import-helper',):
                        helper = '.ai/scripts/tests/unreviewed_budget_helper.py'
                        case.write(helper, addition)
                        case.assertEqual((case.root / helper).read_bytes(), addition.encode('utf-8'))
                        case.assertNotIn(helper, ledger.input_paths(case.root, AGENTS_BUDGET_INPUTS))
                        addition = 'import unreviewed_budget_helper\n'
                    if body and body != ('import-helper',):
                        node = tree
                        for part in body:
                            node = next(n for n in node.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))
                                        and n.name == part)
                        first = node.body[0]
                        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                                and isinstance(first.value.value, str):
                            after = first.end_lineno
                        else:
                            after = min([first.lineno, *[n.lineno for n in
                                         getattr(first, 'decorator_list', [])]]) - 1
                        addition = ' ' * first.col_offset + addition
                    else:
                        after = max(n.end_lineno for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom)))
                    lines = source.splitlines(keepends=True)
                    changed = (''.join(lines[:after]) + addition + ''.join(lines[after:])).encode('utf-8')
                    path.write_bytes(changed)
                    case.assertNotEqual(original, changed)
                    case.assertEqual(path.read_bytes(), changed)
                    case.assertFalse((case.root / 'unrelated.md').exists())
                    case.assertNotIn('unrelated.md', ledger.input_paths(case.root, AGENTS_BUDGET_INPUTS))
                    missing = case.process(AGENTS_BUDGET_COMMAND)
                    case.assertNotEqual(missing.returncode, 0)
                    case.assertIn('FileNotFoundError', missing.stdout + missing.stderr)
                    case.assertIn('unrelated.md', missing.stdout + missing.stderr)
                    case.write('unrelated.md', 'new excluded dependency')
                    case.execution()

                case.setUp = mutated_setup
                result = unittest.TestResult()
                case.run(result)
                self.assertEqual(result.testsRun, 1)
                self.assertFalse(result.errors, result.errors)
                self.assertEqual(len(result.failures), 1, 'unreviewed dependency survived: ' + repr((name, body)))
                self.assertIn('review agents budget dependency boundary', result.failures[0][1])


class AgentsBudgetCompatibilityTests(AgentsBudgetFixture):  # R4
    def test_advisory_guide_and_existing_contracts(self):
        self.assert_prior_profiles()
        self.assertIsNone(ledger.default_inputs(AGENTS_BUDGET_COMMAND))
        self.assertEqual(ledger.default_inputs(COMMAND), ('python-tests', ['**']))
        for argv in (['python3', '-m', 'unittest', 'discover', '-s', '.ai/scripts/tests'],
                     *[['python3', '.ai/scripts/run_tests.py', '-j', str(n)] for n in (1, 8, 32)]):
            self.refused(argv=argv)
        value = self.suggestion()
        self.assertNotIn(EXCLUDE, value['inputs'])
        self.assertEqual(value['schema_version'], 1)
        self.assertTrue(value['review_required'])
        self.assertIn('runtime', ' '.join(value['limitations']).lower())
        guide = (self.root / ARCH_GUIDE).read_text()
        for phrase in ('python-agents-budget-contract', ' '.join(AGENTS_BUDGET_COMMAND),
                       'one literal read', 'one strict assertion', 'one test', '30000',
                       'default decoding', 'universal-newline', 'UTF-8 re-encoding',
                       'raw-file size', 'characters', 'tokens', 'latency', 'semantics',
                       'historical', 'normative', 'conservative', 'explicit', 'manual',
                       'eleven prior profiles', *AGENTS_BUDGET_INPUTS):
            self.assertIn(phrase, guide)
        baseline = subprocess.run(['git', 'show', AGENTS_BUDGET_HEAD + ':.ai/lifecycle.md'],
                                  cwd=SCRIPTS.parent.parent, capture_output=True, text=True, timeout=10)
        self.assertEqual(baseline.returncode, 0, baseline.stderr)
        for paragraph in baseline.stdout.split('\n\n'):
            self.assertIn(paragraph, guide, 'previous guide paragraph changed')


class AgentsBudgetFrameworkEndToEndTests(AgentsBudgetFixture):  # R5
    def record(self):
        value = self.suggestion()
        before = self.preflight()
        self.lc('tier', 'L1', '--reason', 'encoded text budget framework fixture')
        self.lc('run', 'agents-budget', *value['lifecycle_inputs_argv'], '--', *AGENTS_BUDGET_COMMAND)
        self.assert_inputs_unchanged(before)
        import lifecycle
        entry = lifecycle.load(self.root)['ledger'][-1]
        self.assertEqual((entry['argv'], entry['inputs'], entry['exit']),
                         (AGENTS_BUDGET_COMMAND, value['inputs'], 0))
        self.assertIn('REUSE', self.lc('reuse', 'agents-budget'))

    def test_each_input_and_addition_invalidates(self):
        self.record()
        for name in ('.ai/scripts/tests/unrelated.py', 'unrelated.md'):
            self.edit_and_restore(name, lambda: self.assertIn('REUSE', self.lc('reuse', 'agents-budget')))
            self.assertIn('REUSE', self.lc('reuse', 'agents-budget'))
        for name in ['AGENTS.md', *AGENTS_BUDGET_TESTS,
                     '.ai/scripts/review_guard.py', '.ai/scripts/new_budget.py']:
            with self.subTest(name=name):
                def stale():
                    result = self.process([sys.executable, '.ai/scripts/lifecycle.py', 'reuse', 'agents-budget'])
                    self.assertEqual(result.returncode, 1, 'missing agents budget freshness invalidation: ' + name)
                    self.assertIn('RERUN', result.stdout)
                self.edit_and_restore(name, stale)
                self.assertIn('REUSE', self.lc('reuse', 'agents-budget'))
        self.assertFalse((self.root / 'knowledge').exists())


class AgentsBudgetFailureTests(AgentsBudgetFixture):  # R5
    def test_five_encoding_and_boundary_cases(self):
        # Probe the actual default open decoder in the selected child's launch environment.
        marker = self.root / 'decoder-probe.txt'
        marker.write_bytes(b'\xc3\xa9\r\n')
        probe = ('import codecs,json\n'
                 'with open("decoder-probe.txt") as f:\n'
                 ' print(json.dumps([codecs.lookup(f.encoding).name, f.read()]))\n')
        result = self.process(['python3', '-c', probe])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout), ['utf-8', '\u00e9\n'],
                         'fixture requires confirmed UTF-8 default decoding; scope review required')
        marker.unlink()
        self.execution()
        # Independent construction: expected lengths never come from the selected text helper.
        cases = [('below', b'a' * 29998 + b'\n', 'a' * 29998 + '\n', 29999, None),
                 ('equal', b'a' * 29999 + b'\n', 'a' * 29999 + '\n', 30000, '30000 not less than 30000'),
                 ('above', b'a' * 30000 + b'\n', 'a' * 30000 + '\n', 30001, '30001 not less than 30000'),
                 ('multibyte', b'\xc3\xa9' * 15000, '\u00e9' * 15000, 30000, '30000 not less than 30000'),
                 ('crlf', b'a\r\n' * 10000, 'a\n' * 10000, 20000, None)]
        self.assertEqual((len(cases), sum(c[4] is None for c in cases)), (5, 2))
        path = self.root / 'AGENTS.md'
        original = path.read_bytes()
        for label, raw, normalized, encoded_length, failure in cases:
            with self.subTest(case=label):
                self.assertEqual(raw.decode('utf-8').replace('\r\n', '\n').replace('\r', '\n'), normalized)
                self.assertEqual(len(normalized.encode('utf-8')), encoded_length)
                if label == 'multibyte':
                    self.assertEqual((len(normalized), len(raw)), (15000, 30000))
                if label == 'crlf':
                    self.assertEqual((len(raw), len(normalized)), (30000, 20000))
                path.write_bytes(raw)
                try:
                    self.assertNotEqual(original, raw)
                    self.assertEqual(path.read_bytes(), raw)
                    self.assertEqual(self.suggestion()['inputs'], AGENTS_BUDGET_INPUTS)
                    self.execution(failure=failure)
                finally:
                    path.write_bytes(original)
                    self.assertEqual(path.read_bytes(), original)


class AgentsBudgetAdopterEndToEndTests(AgentsBudgetFixture):  # R6
    def test_explicit_adoption_freshness_identity_and_receipt(self):
        (self.root / '.agentic.json').unlink()
        self.lc('tier', 'L1', '--reason', 'encoded text budget adopter fixture')
        result = self.process([sys.executable, '.ai/scripts/okf.py', 'init'])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.write('knowledge/project/sync-ignore', '*\n')
        value = self.suggestion()
        prefix = ('---\ntype: Capability\ntitle: AGENTS budget\nnamespace: AGENTSBUDGET\nstatus: draft\n---\n'
                  '# AGENTS budget\n\n## Requirements\n\n- AGENTSBUDGET-R1: The budget check MUST pass.\n'
                  '  - Verify: `' + ' '.join(AGENTS_BUDGET_COMMAND) + '`\n')
        original = prefix + value['inputs_line'] + '\n'
        capability = self.write('knowledge/capabilities/agents-budget.md', original)
        self.commit()

        def status():
            result = self.process([sys.executable, '.ai/scripts/lifecycle.py', 'assure', '--json'])
            data = json.loads(result.stdout)
            state = next(r['status'] for r in data['requirements'] if r['id'] == 'AGENTSBUDGET-R1')
            self.assertEqual(result.returncode, 0 if state == 'VERIFIED' else 1, result.stdout + result.stderr)
            return state

        self.assertEqual(status(), 'UNVERIFIED')
        before = self.preflight()
        self.lc('assure', '--run', 'AGENTSBUDGET-R1')
        self.assert_inputs_unchanged(before)
        self.assertEqual(status(), 'VERIFIED')
        for name in ('.ai/scripts/tests/unrelated.py', 'unrelated.md'):
            self.edit_and_restore(name, lambda: self.assertEqual(status(), 'VERIFIED'))
            self.assertEqual(status(), 'VERIFIED')
        for name in ['AGENTS.md', *AGENTS_BUDGET_TESTS,
                     '.ai/scripts/review_guard.py', '.ai/scripts/new_budget.py']:
            with self.subTest(name=name):
                self.edit_and_restore(name, lambda: self.assertEqual(status(), 'STALE'))
                self.assertEqual(status(), 'VERIFIED')
        reordered = [*value['inputs'][:-2], value['inputs'][-1], value['inputs'][-2]]
        capability.write_text(prefix + '  - Inputs: ' + ' '.join('`' + p + '`' for p in reordered) + '\n')
        self.assertEqual(status(), 'UNVERIFIED')
        capability.write_text(original.replace(AGENTS_BUDGET_COMMAND[2] + '`',
                                               AGENTS_BUDGET_COMMAND[2] + ' -v`'))
        self.assertEqual(status(), 'UNVERIFIED')
        capability.write_text(original)
        self.assertEqual(status(), 'VERIFIED')
        entries = [e for p in (self.root / 'knowledge/history/lifecycle').glob('*.json')
                   for e in json.loads(p.read_text()).get('ledger', []) if e['label'] == 'req:AGENTSBUDGET-R1']
        self.assertEqual((entries[-1]['argv'], entries[-1]['inputs'], entries[-1]['exit']),
                         (AGENTS_BUDGET_COMMAND, AGENTS_BUDGET_INPUTS + [EXCLUDE], 0))
        self.write('knowledge/history/lifecycle/extra-receipt.json', '{}\n')
        self.assertEqual(status(), 'VERIFIED')


class AgentsBudgetControlTests(AgentsBudgetFixture):  # R6
    def test_confirmed_broken_variants_fail_intended_criteria(self):
        method = 'test_each_input_and_addition_invalidates'
        variants = [('AGENTS.md', AgentsBudgetFrameworkEndToEndTests, method,
                     'missing agents budget freshness invalidation: AGENTS.md'),
                    ('loose', AgentsBudgetProfileTests, 'test_exact_registration_and_prior_profiles', '0 != 2'),
                    ('empty', AgentsBudgetFrameworkEndToEndTests, method,
                     'agents budget execution count must be one')]
        self.assertEqual(len(variants), 3)
        for variant, cls, test, criterion in variants:
            with self.subTest(variant=variant):
                case = cls(test)
                setup = case.setUp

                def mutated_setup():
                    setup()
                    path = case.root / '.ai/scripts/assurance_inputs.py'
                    original = path.read_bytes()
                    source = original.decode('utf-8')
                    if variant == 'AGENTS.md':
                        catalog = copy.deepcopy(case.module().PROFILES)
                        profile = next(p for p in catalog if p['id'] == 'python-agents-budget-contract')
                        profile['inputs'].remove(variant)
                        del profile['rationale'][variant]
                        replacement = (source.split('PROFILES = ', 1)[0] + 'PROFILES = ' + repr(catalog)
                                       + '\nLIMITATIONS =' + source.split('\nLIMITATIONS =', 1)[1])
                    elif variant == 'loose':
                        old = "p['argv'] == list(argv)"
                        case.assertEqual(source.count(old), 1)
                        replacement = source.replace(old, "p['argv'] == list(argv)[:len(p['argv'])]")
                    else:
                        path = case.root / AGENTS_BUDGET_TESTS[0]
                        original = path.read_bytes()
                        replacement = 'import sys\nimport unittest\nunittest.main(argv=[sys.argv[0]])\n'
                    changed = replacement.encode('utf-8')
                    path.write_bytes(changed)
                    case.assertNotEqual(original, changed, 'mutation was not applied')
                    case.assertEqual(path.read_bytes(), changed, 'mutation bytes differ')
                    if variant == 'AGENTS.md':
                        value = case.suggestion()
                        case.assertNotIn(variant, value['inputs'])
                        case.assertNotIn(variant, value['rationale'])
                    if variant == 'empty':
                        result = case.process(AGENTS_BUDGET_COMMAND)
                        case.assertRegex(result.stdout + result.stderr, r'Ran 0 tests? in ')

                case.setUp = mutated_setup
                result = unittest.TestResult()
                case.run(result)
                self.assertEqual(result.testsRun, 1)
                self.assertFalse(result.errors, result.errors)
                self.assertEqual(len(result.failures), 1, 'broken variant survived: ' + variant)
                self.assertIn(criterion, result.failures[0][1])


# Semantic lens: specification-5m.md R1-R6. Independent reviewed declarations.
SEMANTIC_LENS_COMMAND = ['python3', '.ai/scripts/tests/test_lifecycle_conformance.py',
                         'RolesAndSkills.test_semantic_lens_in_analyst_reviewer_and_skills']
SEMANTIC_LENS_TESTS = [SEMANTIC_LENS_COMMAND[1], '.ai/scripts/tests/disk_tmp.py']
SEMANTIC_LENS_DOCS = ['.ai/agents/analyst.md', '.ai/agents/reviewer.md',
                      '.claude/skills/spec/SKILL.md', '.claude/skills/review/SKILL.md']
SEMANTIC_LENS_INPUTS = ['.ai/scripts/**', '!.ai/scripts/tests/**',
                        *SEMANTIC_LENS_TESTS, *SEMANTIC_LENS_DOCS]
SEMANTIC_LENS_HEAD = 'e702aa9a2be85992d0590d14d691e74adcfcec3d'


class SemanticLensFixture(AgentsBudgetFixture):
    def setUp(self):
        # Reuse predecessor compatibility data, not its assertion or read oracle.
        super().setUp()
        for name in SEMANTIC_LENS_DOCS:
            destination = self.root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(SCRIPTS.parent.parent / name, destination)
        self.commit()

    def export(self, argv=None, **kwargs):
        return Fixture.export(self, argv=SEMANTIC_LENS_COMMAND if argv is None else argv, **kwargs)

    def selected_bytes(self):
        return {name: (self.root / name).read_bytes()
                for name in ledger.input_paths(self.root, SEMANTIC_LENS_INPUTS)}

    def assert_inputs_unchanged(self, before):
        self.assertEqual(self.selected_bytes(), before, 'semantic lens execution changed inputs')

    def execution(self):
        before = self.selected_bytes()
        result = self.process(SEMANTIC_LENS_COMMAND)
        output = result.stdout + result.stderr
        counts = re.findall(r'Ran (\d+) tests? in ', output)
        self.assertEqual(len(counts), 1, 'semantic lens execution count missing or ambiguous: ' + output)
        self.assertEqual(int(counts[0]), 1, 'semantic lens execution count must be one: ' + output)
        self.assertEqual(result.returncode, 0, output)
        self.assertRegex(output, r'\nOK\s*$')
        self.assert_inputs_unchanged(before)
        return result

    def edit_and_restore(self, name, check):
        path = self.root / name
        original = path.read_bytes() if path.exists() else None
        changed = (original or b'') + b'\n '
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(changed)
        try:
            self.assertNotEqual(original, changed)
            self.assertEqual(path.read_bytes(), changed)
            if name in SEMANTIC_LENS_DOCS:
                self.execution()
            check()
        finally:
            if original is None:
                path.unlink()
                self.assertFalse(path.exists())
            else:
                path.write_bytes(original)
                self.assertEqual(path.read_bytes(), original)

    def assert_prior_profiles(self):
        result = subprocess.run(['git', 'show', SEMANTIC_LENS_HEAD + ':.ai/scripts/assurance_inputs.py'],
                                cwd=SCRIPTS.parent.parent, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        import ast
        baseline = next(ast.literal_eval(n.value) for n in ast.parse(result.stdout).body
                        if isinstance(n, ast.Assign)
                        and any(isinstance(t, ast.Name) and t.id == 'PROFILES' for t in n.targets))
        identities = ('python-runner-test', 'python-architecture-compatibility', 'python-harness-wiring',
                      'python-reviewer-report-contract', 'python-installer-doc-contract',
                      'python-validation-policy-contract', 'python-audit-doc-contract',
                      'python-analysis-convergence-doc-contract', 'python-stage-doc-contract',
                      'python-tier-doc-contract', 'python-assurance-doc-contract',
                      'python-agents-budget-contract')
        self.assertEqual(tuple(p['id'] for p in baseline), identities)
        actual = self.module().PROFILES
        self.assertEqual(len(actual), 13)
        for expected in baseline:
            self.assertEqual(next(p for p in actual if p['id'] == expected['id']), expected)
            value = self.suggestion(argv=expected['argv'])
            self.assertEqual((value['profile_id'], value['argv'], value['inputs'], value['rationale']),
                             (expected['id'], expected['argv'], expected['inputs'], expected['rationale']))


class SemanticLensProfileTests(SemanticLensFixture):  # R1
    def test_exact_registration_and_prior_profiles(self):
        value = self.suggestion()
        self.assertEqual(value['profile_id'], 'python-semantic-lens-doc-contract')
        self.assertEqual(value['argv'], SEMANTIC_LENS_COMMAND)
        self.assert_prior_profiles()
        for argv in (SEMANTIC_LENS_COMMAND[:2], SEMANTIC_LENS_COMMAND[:2] + ['RolesAndSkills'],
                     SEMANTIC_LENS_COMMAND[:2] + ['RolesAndSkills.test_skills_have_name_matching_directory_and_a_description'],
                     SEMANTIC_LENS_COMMAND + ['-v'], [sys.executable, *SEMANTIC_LENS_COMMAND[1:]],
                     ['python3', './' + SEMANTIC_LENS_COMMAND[1], SEMANTIC_LENS_COMMAND[2]],
                     ['python3', '-m', 'unittest', 'discover', '-s', '.ai/scripts/tests',
                      '-p', 'test_lifecycle_conformance.py']):
            self.assertIn('exact command', self.refused(argv=argv)['reason'])
        self.refused(cwd=self.root / '.ai')


class SemanticLensExportTests(SemanticLensFixture):  # R3
    def test_readonly_formats_supplements_and_no_execution(self):
        marker = self.root / 'executed'
        for name in SEMANTIC_LENS_TESTS:
            self.write(name, f'from pathlib import Path\nPath({str(marker)!r}).touch()\nraise RuntimeError("executed")\n')
        for name in SEMANTIC_LENS_DOCS:
            self.write(name, 'assertion-failing existing document\n')
        for name in ('space file.txt', 'second.txt'):
            self.write(name, 'supplement')
        before = snapshot(self.root)
        value = self.suggestion(extra=('space file.txt', 'second.txt'))
        text = self.export(extra=('space file.txt', 'second.txt'), json_output=False)
        self.assertEqual(text.returncode, 0, text.stderr)
        self.assertEqual(value['inputs'], SEMANTIC_LENS_INPUTS + ['space file.txt', 'second.txt'])
        self.assertEqual(value['lifecycle_inputs_argv'], ['--inputs', *value['inputs']])
        for item in (value['profile_id'], value['inputs_line'], json.dumps(SEMANTIC_LENS_COMMAND),
                     json.dumps(value['lifecycle_inputs_argv']), *value['rationale'].values(), *value['limitations']):
            self.assertIn(item, text.stdout)
        raw = ('- SEMANTICLENS-R1: The check MUST pass.\n  - Verify: `'
               + ' '.join(SEMANTIC_LENS_COMMAND) + '`\n' + value['inputs_line'] + '\n')
        parsed = assurance.parse('SEMANTICLENS-R1', 'capabilities/semantic-lens.md', raw, root=self.root)
        self.assertIsNone(parsed.invalid)
        self.assertEqual(list(parsed.globs), value['inputs'])
        self.assertTrue(value['review_required'])
        self.assertEqual(snapshot(self.root), before)
        self.assertFalse(marker.exists())

    def test_required_literals_and_unsafe_boundaries_refuse(self):
        for name in [*SEMANTIC_LENS_TESTS, *SEMANTIC_LENS_DOCS]:
            path = self.root / name
            original = path.read_bytes()
            path.unlink()
            try:
                self.refused()
            finally:
                path.write_bytes(original)
        self.assertEqual(self.suggestion()['inputs'], SEMANTIC_LENS_INPUTS)
        name = SEMANTIC_LENS_DOCS[0]
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
        try:
            self.refused()
        finally:
            path.unlink()
            path.write_bytes(original)
        for extra in ('!README.md', '../x', '/etc/passwd', '', 'x`bad', '--other-option'):
            self.refused(extra=(extra,))


SEMANTIC_LENS_SETUP_PINS = {
    '.ai/scripts/tests/test_lifecycle_conformance.py': '50977be9e0fc2636e75b83eba96f267339efd91e89f3d035690d0a0e24e8a02b',
    '.ai/scripts/tests/disk_tmp.py': 'fff9eed82f770bce05c477c507ad3c00dae4a16c216521b004646837c0bdd02f',
    '.ai/scripts/scratch.py': '523cbb977066b41423329249d132d2dc27a2f963db15b71489c2579fdb093060',
    '.ai/scripts/lifecycle.py': '048f391c166ffb58b8ba1d769ca287adc78d5c155a28bebba043e0d93a30e1ca',
    '.ai/scripts/review_guard.py': '2d806b1c16cb028a8b2197aec8881b0a4db1a962125f5a5d50a8599b01c45d69',
    '.ai/scripts/ledger.py': 'fc2423e775969cdc28173f970d7c676e6ad254e8f5e120abb89a5c1244b80cab',
}


class SemanticLensDependencyTests(SemanticLensFixture):  # R2
    def test_order_scope_and_independent_oracle(self):
        value = self.suggestion()
        actual = {p: report_setup_digest(self.root / p) for p in SEMANTIC_LENS_SETUP_PINS}
        self.assertEqual(actual, SEMANTIC_LENS_SETUP_PINS,
                         'review semantic lens dependency boundary: ' + repr(actual))
        self.assertEqual(value['inputs'], SEMANTIC_LENS_INPUTS)
        self.assertEqual(set(value['rationale']), set(SEMANTIC_LENS_INPUTS))
        for name, terms in {
            '.ai/scripts/**': ('conservative', 'import', 'lazy'),
            '!.ai/scripts/tests/**': ('exclude',),
            SEMANTIC_LENS_TESTS[0]: ('method', 'fourteen', 'one test'),
            SEMANTIC_LENS_TESTS[1]: ('helper',),
            SEMANTIC_LENS_DOCS[0]: ('direct', 'whole-document', 'once', 'analyze'),
            SEMANTIC_LENS_DOCS[1]: ('direct', 'once', 'split', 'capture'),
            SEMANTIC_LENS_DOCS[2]: ('direct', 'whole-document', 'once', 'analyze'),
            SEMANTIC_LENS_DOCS[3]: ('direct', 'whole-document', 'once', 'converge'),
        }.items():
            for term in terms:
                self.assertIn(term, value['rationale'][name].lower())
        included = ['.ai/scripts/future_semantic.py', '.ai/scripts/assets/semantic.txt']
        compatibility = ['AGENTS.md', '.ai/lifecycle.md', '.ai/docs/lifecycle.md',
                         *VALIDATION_POLICY_DOCS, *INSTALLER_DOC_TEXT, *REPORT_DOCS,
                         *WIRING_JSON, *ARCH_TESTS[:-1]]
        excluded = ['.ai/scripts/tests/unrelated.py', 'unrelated.md',
                    *[p for p in compatibility if p not in SEMANTIC_LENS_DOCS]]
        for name in included + excluded[:2]:
            self.write(name, '# independent inventory fixture\n')
        selected = set(ledger.input_paths(self.root, value['inputs']))
        self.assertTrue(set([*SEMANTIC_LENS_TESTS, *SEMANTIC_LENS_DOCS,
                             *REPORT_IMPORTS, *included]).issubset(selected))
        self.assertFalse(set(excluded) & selected)
        import ast
        tree = ast.parse((self.root / SEMANTIC_LENS_TESTS[0]).read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'RolesAndSkills')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                      and n.name == 'test_semantic_lens_in_analyst_reviewer_and_skills')
        # Literal expected bindings, split/index semantics and assertions, not catalog-derived.
        expected = ast.parse('''analyst, reviewer = text(".ai/agents/analyst.md"), text(".ai/agents/reviewer.md")
for term in ("missing scenarios", "error paths", "contradictions", "terminology drift"):
    self.assertIn(term, analyst, term)
    self.assertIn(term, reviewer, term)
self.assertIn("lifecycle.py analyze", analyst)
self.assertIn("lifecycle.py analyze", text(".claude/skills/spec/SKILL.md"))
passes = reviewer.split("## Passes", 1)[1].split("\\n## ", 1)[0]
for path, body in ((".ai/agents/reviewer.md#Passes", passes), (".claude/skills/review/SKILL.md", text(".claude/skills/review/SKILL.md"))):
    self.assertIn("lifecycle.py converge", body, path)
    self.assertIn("## Validation Reviewed", body, path)
''').body
        self.assertEqual(len(method.body), 6)
        self.assertEqual([ast.dump(n) for n in method.body], [ast.dump(n) for n in expected],
                         'review semantic lens selected method boundary')
        reads = [n for n in ast.walk(method) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Name) and n.func.id == 'text']
        self.assertEqual(len(reads), 4)
        self.assertCountEqual([ast.literal_eval(n.args[0]) for n in reads], SEMANTIC_LENS_DOCS)
        for call in reads:
            self.assertEqual((len(call.args), call.keywords), (1, []))

    def test_reachable_added_dependencies_require_review(self):
        # Fresh proof for this selector; uncalled baseline/flat/producer bodies are pins only.
        variants = [(p, ()) for p in SEMANTIC_LENS_SETUP_PINS]
        variants += [(SEMANTIC_LENS_TESTS[0], ('RolesAndSkills',)),
                     (SEMANTIC_LENS_TESTS[0], ('RolesAndSkills', 'test_semantic_lens_in_analyst_reviewer_and_skills')),
                     (SEMANTIC_LENS_TESTS[0], ('text',)),
                     ('.ai/scripts/scratch.py', ('require_disk',)),
                     ('.ai/scripts/lifecycle.py', ('lazy',)),
                     ('.ai/scripts/review_guard.py', ('protected',)),
                     ('.ai/scripts/review_guard.py', ('protected', 'decorate')),
                     (SEMANTIC_LENS_TESTS[0], ('import-helper',))]
        self.assertEqual(len(variants), 14)
        for name, body in variants:
            with self.subTest(name=name, body=body):
                case = SemanticLensDependencyTests('test_order_scope_and_independent_oracle')
                setup = case.setUp

                def mutated_setup():
                    setup()
                    import ast
                    path = case.root / name
                    original = path.read_bytes()
                    def restore():
                        path.write_bytes(original)
                        case.assertEqual(path.read_bytes(), original, 'semantic lens restoration mismatch')
                    case.addCleanup(restore)
                    source = original.decode('utf-8')
                    tree = ast.parse(source)
                    addition = '__import__("pathlib").Path("unrelated.md").read_text()\n'
                    if body == ('import-helper',):
                        helper = '.ai/scripts/tests/unreviewed_semantic_helper.py'
                        case.write(helper, addition)
                        case.assertEqual((case.root / helper).read_bytes(), addition.encode('utf-8'))
                        case.assertNotIn(helper, ledger.input_paths(case.root, SEMANTIC_LENS_INPUTS))
                        addition = 'import unreviewed_semantic_helper\n'
                    if body and body != ('import-helper',):
                        node = tree
                        for part in body:
                            node = next(n for n in node.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))
                                        and n.name == part)
                        first = node.body[0]
                        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                                and isinstance(first.value.value, str):
                            after = first.end_lineno
                        else:
                            after = min([first.lineno, *[n.lineno for n in
                                         getattr(first, 'decorator_list', [])]]) - 1
                        addition = ' ' * first.col_offset + addition
                    else:
                        after = max(n.end_lineno for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom)))
                    lines = source.splitlines(keepends=True)
                    changed = (''.join(lines[:after]) + addition + ''.join(lines[after:])).encode('utf-8')
                    path.write_bytes(changed)
                    case.assertNotEqual(original, changed)
                    case.assertEqual(path.read_bytes(), changed)
                    case.assertFalse((case.root / 'unrelated.md').exists())
                    case.assertNotIn('unrelated.md', ledger.input_paths(case.root, SEMANTIC_LENS_INPUTS))
                    missing = case.process(SEMANTIC_LENS_COMMAND)
                    case.assertNotEqual(missing.returncode, 0)
                    case.assertIn('FileNotFoundError', missing.stdout + missing.stderr)
                    case.assertIn('unrelated.md', missing.stdout + missing.stderr)
                    case.write('unrelated.md', 'new excluded dependency')
                    case.execution()

                case.setUp = mutated_setup
                result = unittest.TestResult()
                case.run(result)
                self.assertEqual(result.testsRun, 1)
                self.assertFalse(result.errors, result.errors)
                self.assertEqual(len(result.failures), 1, 'unreviewed dependency survived: ' + repr((name, body)))
                self.assertIn('review semantic lens dependency boundary', result.failures[0][1])


class SemanticLensCompatibilityTests(SemanticLensFixture):  # R4
    def test_advisory_guide_and_existing_contracts(self):
        self.assert_prior_profiles()
        self.assertIsNone(ledger.default_inputs(SEMANTIC_LENS_COMMAND))
        self.assertEqual(ledger.default_inputs(COMMAND), ('python-tests', ['**']))
        for argv in (['python3', '-m', 'unittest', 'discover', '-s', '.ai/scripts/tests'],
                     *[['python3', '.ai/scripts/run_tests.py', '-j', str(n)] for n in (1, 8, 32)]):
            self.refused(argv=argv)
        value = self.suggestion()
        self.assertNotIn(EXCLUDE, value['inputs'])
        self.assertEqual(value['schema_version'], 1)
        self.assertTrue(value['review_required'])
        self.assertIn('runtime', ' '.join(value['limitations']).lower())
        guide = (self.root / ARCH_GUIDE).read_text()
        for phrase in ('python-semantic-lens-doc-contract', ' '.join(SEMANTIC_LENS_COMMAND),
                       'four literal reads', 'fourteen case-sensitive', 'one test',
                       'first literal', 'IndexError', 'inline', 'semantic-lens effectiveness',
                       'conservative', 'explicit', 'manual', 'twelve prior profiles',
                       *SEMANTIC_LENS_INPUTS):
            self.assertIn(phrase, guide)
        baseline = subprocess.run(['git', 'show', SEMANTIC_LENS_HEAD + ':.ai/lifecycle.md'],
                                  cwd=SCRIPTS.parent.parent, capture_output=True, text=True, timeout=10)
        self.assertEqual(baseline.returncode, 0, baseline.stderr)
        for paragraph in baseline.stdout.split('\n\n'):
            self.assertIn(paragraph, guide, 'previous guide paragraph changed')


class SemanticLensFrameworkEndToEndTests(SemanticLensFixture):  # R5
    def record(self):
        value = self.suggestion()
        before = self.preflight()
        self.lc('tier', 'L1', '--reason', 'semantic lens framework fixture')
        self.lc('run', 'semantic-lens', *value['lifecycle_inputs_argv'], '--', *SEMANTIC_LENS_COMMAND)
        self.assert_inputs_unchanged(before)
        import lifecycle
        entry = lifecycle.load(self.root)['ledger'][-1]
        self.assertEqual((entry['argv'], entry['inputs'], entry['exit']),
                         (SEMANTIC_LENS_COMMAND, value['inputs'], 0))
        self.assertIn('REUSE', self.lc('reuse', 'semantic-lens'))

    def test_each_input_and_addition_invalidates(self):
        self.record()
        for name in ('.ai/scripts/tests/unrelated.py', 'unrelated.md'):
            self.edit_and_restore(name, lambda: self.assertIn('REUSE', self.lc('reuse', 'semantic-lens')))
            self.assertIn('REUSE', self.lc('reuse', 'semantic-lens'))
        for name in [*SEMANTIC_LENS_DOCS, *SEMANTIC_LENS_TESTS,
                     '.ai/scripts/review_guard.py', '.ai/scripts/new_semantic.py']:
            with self.subTest(name=name):
                def stale():
                    result = self.process([sys.executable, '.ai/scripts/lifecycle.py', 'reuse', 'semantic-lens'])
                    self.assertEqual(result.returncode, 1, 'missing semantic lens freshness invalidation: ' + name)
                    self.assertIn('RERUN', result.stdout)
                self.edit_and_restore(name, stale)
                self.assertIn('REUSE', self.lc('reuse', 'semantic-lens'))
        self.assertFalse((self.root / 'knowledge').exists())


class SemanticLensFailureTests(SemanticLensFixture):  # R5
    def test_fourteen_intended_assertion_failures(self):
        terms = ('missing scenarios', 'error paths', 'contradictions', 'terminology drift')
        analyst, reviewer, spec_skill, review_skill = SEMANTIC_LENS_DOCS
        # Ordered exactly as the selected method executes, with literal expected source sites.
        cases = [(name, 'whole', term, 'self.assertIn(term, ' + binding + ', term)', term)
                 for term in terms for name, binding in ((analyst, 'analyst'), (reviewer, 'reviewer'))]
        cases += [(analyst, 'whole', 'lifecycle.py analyze',
                   'self.assertIn("lifecycle.py analyze", analyst)', None),
                  (spec_skill, 'whole', 'lifecycle.py analyze',
                   'self.assertIn("lifecycle.py analyze", text(".claude/skills/spec/SKILL.md"))', None)]
        cases += [(name, scope, token, 'self.assertIn("' + token + '", body, path)', diagnostic)
                  for name, scope, diagnostic in ((reviewer, 'passes', reviewer + '#Passes'),
                                                   (review_skill, 'whole', review_skill))
                  for token in ('lifecycle.py converge', '## Validation Reviewed')]
        self.assertEqual(len(cases), 14)
        originals = {name: (self.root / name).read_bytes() for name in SEMANTIC_LENS_DOCS}

        def bounds(body, scope):
            if scope == 'whole':
                return 0, len(body)
            # Independent index-based capture, not the selected chained split.
            start = body.index('## Passes') + len('## Passes')
            end = body.find('\n## ', start)
            return start, len(body) if end == -1 else end

        def predicates(documents):
            return [token in documents[name][slice(*bounds(documents[name], scope))]
                    for name, scope, token, _, _ in cases]

        documents = {name: raw.decode('utf-8') for name, raw in originals.items()}
        self.assertEqual(predicates(documents), [True] * 14)
        self.execution()
        for index, (name, scope, token, source, diagnostic) in enumerate(cases):
            with self.subTest(index=index, document=name, scope=scope, token=token):
                path = self.root / name
                body = documents[name]
                start, end = bounds(body, scope)
                capture = body[start:end]
                self.assertGreater(capture.count(token), 0)
                changed_body = body[:start] + capture.replace(token, 'REMOVED_SEMANTIC_TOKEN') + body[end:]
                changed = changed_body.encode('utf-8')
                path.write_bytes(changed)
                try:
                    self.assertNotEqual(originals[name], changed)
                    self.assertEqual(path.read_bytes(), changed)
                    if scope == 'passes':
                        self.assertEqual(changed_body[:start], body[:start])
                        self.assertEqual(changed_body[bounds(changed_body, scope)[1]:], body[end:])
                    altered = {**documents, name: changed_body}
                    expected = [True] * 14
                    expected[index] = False
                    self.assertEqual(predicates(altered), expected, 'mutation changed another predicate')
                    self.assertEqual(self.suggestion()['inputs'], SEMANTIC_LENS_INPUTS)
                    before = self.selected_bytes()
                    result = self.process(SEMANTIC_LENS_COMMAND)
                    output = result.stdout + result.stderr
                    self.assertEqual(re.findall(r'Ran (\d+) tests? in ', output), ['1'], output)
                    self.assertNotEqual(result.returncode, 0, output)
                    self.assertRegex(output, r'FAILED \(failures=1\)')
                    self.assertEqual(len(re.findall(r'^FAIL:', output, re.M)), 1, output)
                    self.assertFalse(re.search(r'^ERROR:', output, re.M), output)
                    self.assertIn('AssertionError: ' + repr(token) + ' not found', output)
                    self.assertIn(source, output)
                    self.assertIn(SEMANTIC_LENS_COMMAND[2].split('.')[1], output)
                    if diagnostic is not None:
                        self.assertIn(' : ' + diagnostic, output)
                    self.assert_inputs_unchanged(before)
                finally:
                    path.write_bytes(originals[name])
                    self.assertEqual(path.read_bytes(), originals[name])
        self.assertEqual({name: (self.root / name).read_bytes() for name in SEMANTIC_LENS_DOCS}, originals)


class SemanticLensAdopterEndToEndTests(SemanticLensFixture):  # R6
    def test_explicit_adoption_freshness_identity_and_receipt(self):
        (self.root / '.agentic.json').unlink()
        self.lc('tier', 'L1', '--reason', 'semantic lens adopter fixture')
        result = self.process([sys.executable, '.ai/scripts/okf.py', 'init'])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.write('knowledge/project/sync-ignore', '*\n')
        value = self.suggestion()
        prefix = ('---\ntype: Capability\ntitle: Semantic lens\nnamespace: SEMANTICLENS\nstatus: draft\n---\n'
                  '# Semantic lens\n\n## Requirements\n\n- SEMANTICLENS-R1: The documentation check MUST pass.\n'
                  '  - Verify: `' + ' '.join(SEMANTIC_LENS_COMMAND) + '`\n')
        original = prefix + value['inputs_line'] + '\n'
        capability = self.write('knowledge/capabilities/semantic-lens.md', original)
        self.commit()

        def status():
            result = self.process([sys.executable, '.ai/scripts/lifecycle.py', 'assure', '--json'])
            data = json.loads(result.stdout)
            state = next(r['status'] for r in data['requirements'] if r['id'] == 'SEMANTICLENS-R1')
            self.assertEqual(result.returncode, 0 if state == 'VERIFIED' else 1, result.stdout + result.stderr)
            return state

        self.assertEqual(status(), 'UNVERIFIED')
        before = self.preflight()
        self.lc('assure', '--run', 'SEMANTICLENS-R1')
        self.assert_inputs_unchanged(before)
        self.assertEqual(status(), 'VERIFIED')
        for name in ('.ai/scripts/tests/unrelated.py', 'unrelated.md'):
            self.edit_and_restore(name, lambda: self.assertEqual(status(), 'VERIFIED'))
            self.assertEqual(status(), 'VERIFIED')
        for name in [*SEMANTIC_LENS_DOCS, *SEMANTIC_LENS_TESTS,
                     '.ai/scripts/review_guard.py', '.ai/scripts/new_semantic.py']:
            with self.subTest(name=name):
                self.edit_and_restore(name, lambda: self.assertEqual(status(), 'STALE'))
                self.assertEqual(status(), 'VERIFIED')
        reordered = [*value['inputs'][:-2], value['inputs'][-1], value['inputs'][-2]]
        capability.write_text(prefix + '  - Inputs: ' + ' '.join('`' + p + '`' for p in reordered) + '\n')
        self.assertEqual(status(), 'UNVERIFIED')
        capability.write_text(original.replace(SEMANTIC_LENS_COMMAND[2] + '`',
                                               SEMANTIC_LENS_COMMAND[2] + ' -v`'))
        self.assertEqual(status(), 'UNVERIFIED')
        capability.write_text(original)
        self.assertEqual(status(), 'VERIFIED')
        entries = [e for p in (self.root / 'knowledge/history/lifecycle').glob('*.json')
                   for e in json.loads(p.read_text()).get('ledger', []) if e['label'] == 'req:SEMANTICLENS-R1']
        self.assertEqual((entries[-1]['argv'], entries[-1]['inputs'], entries[-1]['exit']),
                         (SEMANTIC_LENS_COMMAND, SEMANTIC_LENS_INPUTS + [EXCLUDE], 0))
        self.write('knowledge/history/lifecycle/extra-receipt.json', '{}\n')
        self.assertEqual(status(), 'VERIFIED')


class SemanticLensControlTests(SemanticLensFixture):  # R6
    def test_confirmed_broken_variants_fail_intended_criteria(self):
        method = 'test_each_input_and_addition_invalidates'
        variants = [(name, SemanticLensFrameworkEndToEndTests, method,
                     'missing semantic lens freshness invalidation: ' + name) for name in SEMANTIC_LENS_DOCS]
        variants += [('loose', SemanticLensProfileTests, 'test_exact_registration_and_prior_profiles', '0 != 2'),
                     ('empty', SemanticLensFrameworkEndToEndTests, method,
                      'semantic lens execution count must be one')]
        self.assertEqual(len(variants), 6)
        for variant, cls, test, criterion in variants:
            with self.subTest(variant=variant):
                case = cls(test)
                setup = case.setUp

                def mutated_setup():
                    setup()
                    path = case.root / '.ai/scripts/assurance_inputs.py'
                    original = path.read_bytes()
                    source = original.decode('utf-8')
                    if variant in SEMANTIC_LENS_DOCS:
                        catalog = copy.deepcopy(case.module().PROFILES)
                        profile = next(p for p in catalog if p['id'] == 'python-semantic-lens-doc-contract')
                        profile['inputs'].remove(variant)
                        del profile['rationale'][variant]
                        replacement = (source.split('PROFILES = ', 1)[0] + 'PROFILES = ' + repr(catalog)
                                       + '\nLIMITATIONS =' + source.split('\nLIMITATIONS =', 1)[1])
                    elif variant == 'loose':
                        old = "p['argv'] == list(argv)"
                        case.assertEqual(source.count(old), 1)
                        replacement = source.replace(old, "p['argv'] == list(argv)[:len(p['argv'])]")
                    else:
                        path = case.root / SEMANTIC_LENS_TESTS[0]
                        original = path.read_bytes()
                        replacement = 'import sys\nimport unittest\nunittest.main(argv=[sys.argv[0]])\n'
                    def restore():
                        path.write_bytes(original)
                        case.assertEqual(path.read_bytes(), original, 'semantic lens restoration mismatch')
                    case.addCleanup(restore)
                    changed = replacement.encode('utf-8')
                    path.write_bytes(changed)
                    case.assertNotEqual(original, changed, 'mutation was not applied')
                    case.assertEqual(path.read_bytes(), changed, 'mutation bytes differ')
                    if variant in SEMANTIC_LENS_DOCS:
                        value = case.suggestion()
                        case.assertNotIn(variant, value['inputs'])
                        case.assertNotIn(variant, value['rationale'])
                    if variant == 'empty':
                        result = case.process(SEMANTIC_LENS_COMMAND)
                        case.assertEqual(re.findall(r'Ran (\d+) tests? in ', result.stdout + result.stderr), ['0'])

                case.setUp = mutated_setup
                result = unittest.TestResult()
                case.run(result)
                self.assertEqual(result.testsRun, 1)
                self.assertFalse(result.errors, result.errors)
                self.assertEqual(len(result.failures), 1, 'broken variant survived: ' + variant)
                self.assertIn(criterion, result.failures[0][1])


if __name__ == '__main__':
    unittest.main()
