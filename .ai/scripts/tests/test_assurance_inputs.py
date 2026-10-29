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


if __name__ == '__main__':
    unittest.main()
