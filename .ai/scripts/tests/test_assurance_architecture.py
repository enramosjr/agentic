"""Governed architecture constraints: specification-3.md R1-R7."""
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from test_assurance import Case, CAP, SCOPED, EXCLUDE, SCRIPTS
from test_assurance_gate import GateCase, DeltaCase
import assurance
import lifecycle

ADR = 'knowledge/project/decisions/layers.md'
LINK = '[Layer boundary](../project/decisions/layers.md#boundary)'
LINE = '  - Governed-by: ' + LINK + '\n'
DECISION = '---\ntype: Decision\ntitle: Layers\nstatus: draft\n---\n# Layers\n## Boundary\nCore avoids adapters.\n'


class GovernedCase(Case):
    def setUp(self):
        super().setUp()
        self.write(ADR, DECISION)

    def governed(self, block=SCOPED, line=LINE):
        block = block.splitlines(keepends=True)
        self.capability(block[0] + line + ''.join(block[1:]))

    def assert_governance(self, item, reference=LINK, document=ADR):
        expected = {'basis': 'declared', 'reference': reference}
        if document is not None:
            expected['document'] = document
        self.assertEqual(item['governed_by'], expected)


class DeclarationTests(GovernedCase):  # R1
    def test_optional_declaration_in_an_ordinary_capability(self):
        self.governed()
        item = self.status('CALC-R1')
        self.assertEqual(item['status'], 'UNVERIFIED')
        self.assert_governance(item)
        self.capability(SCOPED)
        self.assertNotIn('governed_by', self.status('CALC-R1'))

    def test_context_is_explicit_not_the_callers_working_directory(self):
        raw = SCOPED.replace('  - Verify:', LINE + '  - Verify:')
        normal = assurance.parse('CALC-R1', CAP, raw, root=self.root)
        delta = assurance.parse('CALC-R1', '/capabilities/calc.md', raw, root=self.root)
        self.assertIsNone(normal.invalid)
        self.assertEqual(normal.governed_by, delta.governed_by)
        missing = assurance.parse('CALC-R1', CAP, raw)
        self.assertIn('context', missing.invalid)
        self.assertIsNone(assurance.parse('CALC-R1', CAP, SCOPED).invalid)


class ReferenceTests(GovernedCase):  # R2
    def test_existing_okf_link_forms_and_exact_one_link(self):
        for reference in (
            '[Decision](<../project/decisions/layers.md>)',
            '[Decision](../project/decisions/layers.md "Layers")',
            "[Decision](../project/decisions/layers.md 'Layers')",
            '[Decision](<../project/decisions/layers.md#boundary> "Layers")',
            '[Decision](../project/decisions/layers.md (Layers))',
            r'[Layer\] boundary](../project/decisions/layers.md)',
        ):
            with self.subTest(reference=reference):
                self.governed(line='  - Governed-by: ' + reference + '\n')
                item = self.status('CALC-R1')
                self.assertEqual(item['status'], 'UNVERIFIED')
                self.assert_governance(item, reference)
        for reference in (
            '[Decision](<../project/decisions/layers.md)',
            '[Decision](../project/decisions/layers.md "Layers)',
            LINK + ' ' + LINK,
        ):
            with self.subTest(reference=reference):
                self.governed(line='  - Governed-by: ' + reference + '\n')
                self.assertEqual(self.status('CALC-R1')['status'], 'INVALID')

    def test_both_path_conventions_decoding_and_fragment_preservation(self):
        self.write('knowledge/project/decisions/space name.md', DECISION)
        for target, document in (
            ('../project/decisions/layers.md', ADR),
            ('/project/decisions/layers.md', ADR),
            ('../project/decisions/layers.md#missing-anchor', ADR),
            ('../project/decisions/space%20name.md', 'knowledge/project/decisions/space name.md'),
            ('../project/decisions/layers.md?view=1#boundary', ADR),
        ):
            with self.subTest(target=target):
                reference = '[Decision](' + target + ')'
                self.governed(line='  - Governed-by: ' + reference + '\n')
                self.assert_governance(self.status('CALC-R1'), reference, document)

    def test_invalid_references_are_diagnosed_and_not_executed(self):
        self.write('knowledge/project/decisions/check.py', 'raise RuntimeError("must not execute")\n')
        values = ('', 'ADR-1', '[x]()', '[](../project/decisions/layers.md)',
                  '[x](https://example.com/adr.md)', '[x](file:///etc/passwd)',
                  '[x](//example.com/adr.md)', '[x](../project/decisions/missing.md)',
                  '[x](../project/decisions)', '[x](../../outside.md)',
                  '[x](../project/decisions/check.py)',
                  LINK + ' ' + LINK, LINK + ' trailing text')
        for value in values:
            with self.subTest(value=value):
                self.governed(line='  - Governed-by: ' + value + '\n')
                item = self.status('CALC-R1')
                self.assertEqual(item['status'], 'INVALID', value)
                self.assertIn('Governed-by:', item['reason'])
                self.assertIn('must', item['reason'].lower())
                self.assert_governance(item, value, None)
                report = self.lc('assure', code=1)
                self.assertIn('CALC-R1', report.stdout)

    def test_duplicates_late_lines_and_escaping_symlink(self):
        outside = self.write('outside.md', '# outside\n')
        (self.root / 'knowledge/project/decisions/escape.md').symlink_to(outside)
        for line in (LINE + LINE,
                     '  - Governed-by: [escape](../project/decisions/escape.md)\n'):
            with self.subTest(line=line):
                self.governed(line=line)
                self.assertEqual(self.status('CALC-R1')['status'], 'INVALID')
        self.capability(SCOPED + LINE)
        self.assertIn('scenario', self.status('CALC-R1')['reason'])


class ReportTests(GovernedCase):  # R3, R5
    def test_governance_on_every_status_preserves_existing_fields(self):
        self.task()
        for status in assurance.STATUSES:
            with self.subTest(status=status):
                self.write('src/calc.py', 'ok\n')
                block = SCOPED
                if status == 'MANUAL':
                    block = '- CALC-R1: Layers MUST be reviewed.\n  - Verify: manual - judgment\n'
                elif status == 'UNDECLARED':
                    block = '- CALC-R1: Layers MUST be respected.\n'
                elif status == 'INVALID':
                    block = SCOPED.replace('`python3 check.py`', 'not a command')
                elif status == 'UNVERIFIED':
                    block = SCOPED.replace('python3 check.py', 'python3 check.py fresh')
                self.governed(block)
                if status in ('VERIFIED', 'STALE', 'FAILED'):
                    if status == 'FAILED':
                        self.write('src/calc.py', 'broken\n')
                    self.lc('assure', '--run', code=1 if status == 'FAILED' else 0)
                    if status == 'STALE':
                        self.write('src/calc.py', 'ok, modified\n')
                before_entries = self.req_entries()
                data, code = self.report()
                item = data['requirements'][0]
                self.assertEqual(item['status'], status)
                self.assert_governance(item)
                text = self.lc('assure', code=code).stdout
                self.assertIn('governance (declared, not verified): ' + LINK, text)
                self.assertEqual(self.req_entries(), before_entries)
                self.capability(block)
                plain, plain_code = self.report()
                del item['governed_by']
                self.assertEqual(data, plain)
                self.assertEqual(code, plain_code)

    def test_readers_do_not_run_obligations_or_manufacture_approval(self):
        self.write('check.py', 'from pathlib import Path\nPath("marker").touch()\n')
        self.governed()
        data, code = self.report()
        self.assertEqual((data['schema_version'], code), (1, 1))
        self.assertNotIn('approved_by', data['requirements'][0]['governed_by'])
        self.lc('assure', code=1)
        self.assertFalse((self.root / 'marker').exists())


class FreshnessTests(GovernedCase):  # R4, R5
    def test_adr_is_an_input_only_when_explicitly_declared(self):
        self.task()
        for include in (False, True):
            with self.subTest(include=include):
                block = SCOPED.replace('`src/**`', '`src/**` `' + ADR + '`') if include else SCOPED
                self.governed(block)
                self.lc('assure', '--run')
                entry = self.req_entries()[-1]
                expected = ['check.py', 'src/**'] + ([ADR] if include else []) + [EXCLUDE]
                self.assertEqual(entry['inputs'], expected)
                self.assertEqual(entry['argv'], ['python3', 'check.py'])
                self.write(ADR, (self.root / ADR).read_text() + '\nChanged decision.\n')
                self.assertEqual(self.status('CALC-R1')['status'], 'STALE' if include else 'VERIFIED')

    def test_whole_tree_retains_existing_markdown_exemption(self):
        self.governed(SCOPED.replace('  - Inputs: `check.py` `src/**`\n', ''))
        self.task()
        self.lc('assure', '--run')
        self.write(ADR, DECISION + '\nChanged.\n')
        self.assertEqual(self.req_entries()[-1]['inputs'], [])
        self.assertEqual(self.status('CALC-R1')['status'], 'VERIFIED')


class ConstraintFlowTests(GovernedCase):  # R5
    def test_real_forbidden_dependency_sequence(self):
        import assurance_architecture_demo as demo
        out, err = io.StringIO(), io.StringIO()
        code = demo.run(base=Path(self.temp.name), out=out, err=err)
        self.assertEqual(code, 0, err.getvalue())
        self.assertEqual(re.findall(r'^STEP \d/5 ([A-Z]+)', out.getvalue(), re.M),
                         ['UNVERIFIED', 'VERIFIED', 'STALE', 'FAILED', 'VERIFIED'])

    def test_disabled_checker_cannot_pass_the_demo(self):
        import assurance_architecture_demo as demo
        seen = []
        def disable(repo):
            checker = repo / 'check.py'
            checker.write_text('raise SystemExit(0)\n')
            self.assertEqual(checker.read_text(), 'raise SystemExit(0)\n')
            seen.append(repo)
        out, err = io.StringIO(), io.StringIO()
        self.assertEqual(demo.run(base=Path(self.temp.name), prepare=disable, out=out, err=err), 1)
        self.assertTrue(seen)
        self.assertIn('exited 0', err.getvalue())
        self.assertFalse(seen[0].exists())

    def test_manual_and_undeclared_remain_nonexecuting(self):
        self.governed('- CALC-R1: Layers MUST be reviewed.\n  - Verify: manual - judgment\n')
        self.assertEqual(self.report()[1], 0)
        self.assertEqual(self.status('CALC-R1')['status'], 'MANUAL')
        self.governed('- CALC-R1: Layers MUST be respected.\n')
        self.assertEqual(self.report()[1], 0)
        self.assertEqual(self.status('CALC-R1')['status'], 'UNDECLARED')
        self.assertEqual(self.report('--strict')[1], 1)


class IntegrationTests(DeltaCase):  # R2, R4, R6
    def setUp(self):
        super().setUp()
        self.write(ADR, DECISION)

    def governed_delta(self, kind='modified', line=LINE):
        spec = self.delta(kind)
        path = self.root / spec
        text = path.read_text().replace('  - Verify:', line + '  - Verify:')
        path.write_text(text)
        return spec

    def test_add_and_modify_preserve_reference_and_execute_once(self):
        for kind in ('added', 'modified'):
            with self.subTest(kind=kind):
                spec = self.governed_delta(kind)
                self.start()
                before = (self.root / 'runs.md').read_text() if (self.root / 'runs.md').exists() else ''
                self.prepare(spec=spec)
                rid = 'CALC-R2' if kind == 'added' else 'CALC-R1'
                [entry] = [e for e in self.req_entries() if e['label'] == 'req:' + rid]
                self.assertEqual(entry['argv'], ['python3', 'count.py'])
                self.assertEqual(entry['inputs'], ['count.py', 'src/**', EXCLUDE])
                self.assertEqual((self.root / 'runs.md').read_text(), before + 'x')
                item = self.status(rid)
                self.assertEqual(item['status'], 'VERIFIED')
                self.assertEqual(item['governed_by']['document'], ADR)
                self.assertIn(LINE, (self.root / CAP).read_text())
                if kind == 'added':
                    self.lc('assure', '--run', 'CALC-R1')
                self.verify()

    def test_invalid_delta_publishes_no_requirement_evidence(self):
        # Valid Markdown link exists, but violates Governed-by's single-link grammar.
        spec = self.governed_delta(line=LINE.rstrip() + ' trailing text\n')
        self.approve_delta(spec)
        self.lc('converge', spec)
        self.assertEqual(self.req_entries(), [])
        self.lc('merge', spec)
        self.write('docs/review.md', '## Verdict\nApproved\n')
        self.lc('stage', 'review', '--ref', 'docs/review.md')
        self.lc('retrospect', '--no-new-lessons', 'fixture')
        self.assert_blocked('INVALID')

    def test_existing_gate_statuses_repair_and_nonblocking_outcomes(self):
        governed = SCOPED.replace('  - Verify:', LINE + '  - Verify:')
        self.capability(governed)
        self.start()
        self.prepare()
        self.assert_blocked('UNVERIFIED')
        self.lc('assure', '--run')
        self.write('src/calc.py', 'ok, changed\n')
        self.lc('converge', 'docs/task.md')
        self.assert_blocked('STALE')
        self.write('src/calc.py', 'broken\n')
        self.lc('assure', '--run', code=1)
        self.lc('converge', 'docs/task.md')
        self.assert_blocked('FAILED')
        self.capability(governed.replace(LINK, LINK + ' trailing text'))
        self.assert_blocked('INVALID')
        self.capability(governed)
        self.write('src/calc.py', 'ok\n')
        self.lc('assure', '--run')
        self.lc('converge', 'docs/task.md')
        self.verify()
        self.start()
        self.capability('- CALC-R1: Boundary MUST be reviewed.\n' + LINE +
                        '  - Verify: manual - judgment\n' +
                        '- CALC-R2: Other boundary MUST be respected.\n' + LINE)
        self.prepare()
        self.verify()


class CompatibilityTests(GovernedCase):  # R7
    def test_published_demo_and_invoking_checkout_immutability(self):
        import assurance_architecture_demo as demo
        watched = [p for p in SCRIPTS.glob('*.py')]
        watched.append(SCRIPTS.parent / 'lifecycle.md')
        before = {p: p.read_bytes() for p in watched}
        result = subprocess.run([sys.executable, str(SCRIPTS / 'assurance_architecture_demo.py')],
                                cwd=self.root, env=self.env, capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(re.findall(r'^STEP \d/5 ([A-Z]+)', result.stdout, re.M),
                         ['UNVERIFIED', 'VERIFIED', 'STALE', 'FAILED', 'VERIFIED'])
        self.assertEqual(before, {p: p.read_bytes() for p in watched})
        guide = (SCRIPTS.parent / 'lifecycle.md').read_text()
        self.assertIn('python3 .ai/scripts/assurance_architecture_demo.py', guide)
        self.assertIn(demo.DECLARATION, guide)
        self.assertIn(demo.CHECK.rstrip(), guide)
        for text in ('Governed-by:', 'provenance', 'MANUAL', 'UNDECLARED', 'fragment', 'Inputs:'):
            self.assertIn(text, guide)

    def test_ungoverned_public_shape_stays_unchanged(self):
        self.capability(SCOPED)
        data, code = self.report()
        self.assertEqual((data['schema_version'], code), (1, 1))
        self.assertEqual(set(data['requirements'][0]),
                         {'id', 'capability', 'status', 'basis', 'evidence', 'reason'})
        self.assertNotIn('governance', self.lc('assure', code=1).stdout)


if __name__ == '__main__':
    unittest.main()
