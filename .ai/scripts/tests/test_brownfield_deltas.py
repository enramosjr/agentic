"""Gap 3 R1–R12: public CLI contracts for brownfield deltas."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import contextlib
import io

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import disk_tmp  # noqa: F401
import lifecycle

OLD = '- EXPORT-R1: The exporter MUST write UTF-8.\n  - Scenario utf8: Write café.\n'
DROP = '- EXPORT-R2: The exporter MUST emit legacy headers.\n'
KEEP = '- EXPORT-R9: The exporter MUST preserve dates.\n'


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


class DeltaCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.scripts = self.root / '.ai/scripts'
        self.scripts.mkdir(parents=True)
        for source in SCRIPTS.glob('*.py'):
            shutil.copy2(source, self.scripts / source.name)
        self.git('init', '-q')
        self.cli('okf.py', 'init')
        (self.root / 'knowledge/project/sync-ignore').write_text('*.md\n')
        self.cap =self.root / 'knowledge/capabilities/export.md'
        self.cap.write_text('---\ntype: Capability\ntitle: Export\nnamespace: EXPORT\n'
                            'status: draft\n---\n\n# Export\n\nKeep this prose.\n\n'
                            '## Requirements\n\n' + OLD + '\n' + DROP + '\n' + KEEP +
                            '\n## Notes\n\nKeep these notes.\n')
        self.spec = self.root / 'knowledge/specifications/change.md'
        self.spec.write_text(self.delta())
        self.cli('okf.py', 'reindex')
        self.git('add', '-A')
        self.git('commit', '-qm', 'fixture')

    def git(self, *args):
        return subprocess.run(['git', '-c', 'user.name=Test', '-c', 'user.email=t@t', *args],
                              cwd=self.root, capture_output=True, text=True, check=True).stdout

    def cli(self, script, *args, code=0):
        result = subprocess.run([sys.executable, str(self.scripts / script), *args], cwd=self.root,
                                env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
                                capture_output=True, text=True, timeout=60)
        if code is not None:
            self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return result

    def lc(self, *args, **kwargs):
        return self.cli('lifecycle.py', *args, **kwargs)

    def delta(self, added='- EXPORT-R3: The exporter MUST escape delimiters.',
              modified='- EXPORT-R1: The exporter MUST write UTF-16.',
              removed='- EXPORT-R2: The exporter MUST stop emitting legacy headers. Reason: retired.',
              command='python3 -c "raise SystemExit(0)"'):
        return ('---\ntype: Specification\nstatus: draft\ntarget: /capabilities/export.md\n---\n'
                '# Change\n\n## Target baseline\n\nTarget: /capabilities/export.md\n'
                f'- EXPORT-R3: absent\n- EXPORT-R1: sha256:{digest(OLD)}\n'
                f'- EXPORT-R2: sha256:{digest(DROP)}\n\n'
                f'## Added requirements\n\n{added}\n\n## Modified requirements\n\n{modified}\n\n'
                f'## Removed requirements\n\n{removed}\n\n## Acceptance\n\n'
                + ''.join(f'- {rid}: `{command}` passes.\n' for rid in ('EXPORT-R3', 'EXPORT-R1', 'EXPORT-R2'))
                + '\n## Constraints\n\nNone.\n\n## Non-goals\n\nOther formats.\n\n'
                '## Assumptions\n\nNone.\n\n## Open questions\n\nNone.\n')

    def analyze(self, code=0):
        return self.lc('analyze', str(self.spec), code=code)

    def snapshot(self):
        return {str(p.relative_to(self.root)): (p.read_bytes(), p.stat().st_mtime_ns)
                for p in self.root.rglob('*') if p.is_file() and not p.is_symlink()}

    def approve(self):
        self.lc('tier', 'L2', '--new', '--reason', 'fixture', '--kind', 'feature')
        self.lc('stage', 'intent', '--ref', str(self.spec.relative_to(self.root)), '--approved-by', 'human:test')

    def record(self):
        return next((self.root / 'knowledge/history/lifecycle').glob('*.json'))


class CompatibilityTests(DeltaCase):  # R1
    def test_valid_delta_and_legacy_spec(self):
        self.analyze()
        self.spec.write_text('# Legacy\n\n## Requirements\n- R1: The tool MUST print a greeting.\n'
                             '## Acceptance\n- R1: `python3 -V` passes.\n## Non-goals\nNone.\n'
                             '## Open questions\nNone.\n')
        self.analyze()

    def test_prose_target_refuses_without_rewriting(self):
        self.cap.write_text('---\ntype: Capability\n---\n# Prose only\n')
        before = self.snapshot()
        self.assertIn('structured', self.analyze(1).stdout)
        self.assertEqual(before, self.snapshot())


class LivingIdTests(DeltaCase):  # R2
    def test_namespace_duplicate_and_foreign_ids(self):
        for text in (self.cap.read_text().replace('namespace: EXPORT', 'namespace: bad'),
                     self.cap.read_text().replace('EXPORT-R9', 'OTHER-R9'),
                     self.cap.read_text().replace('EXPORT-R9', 'EXPORT-R1')):
            with self.subTest(text=text):
                self.cap.write_text(text)
                self.analyze(1)

    def test_duplicate_namespace(self):
        (self.cap.parent / 'other.md').write_bytes(self.cap.read_bytes())
        self.assertIn('namespace', self.analyze(1).stdout)

    def test_retired_id_from_retained_delta_is_reserved(self):
        retired = self.spec.with_name('retired.md')
        retired.write_text('---\ntype: Specification\nstatus: stable\ntarget: /capabilities/export.md\n---\n'
                           '## Removed requirements\n- EXPORT-R3: The exporter MUST retire this. Reason: obsolete.\n')
        self.assertIn('retired ID', self.analyze(1).stdout)


class DeltaAnalysisTests(DeltaCase):  # R3
    def test_removal_requires_must_even_with_should_or_reason_modal(self):
        for text in ('SHOULD stop emitting legacy headers. Reason: retired.',
                     'SHOULD stop emitting legacy headers. Reason: clients MUST migrate.'):
            self.spec.write_text(self.delta(removed='- EXPORT-R2: The exporter ' + text))
            self.assertIn('High', self.analyze(1).stdout)

    def test_rejection_severities(self):
        original = self.spec.read_text()
        cases = [('EXPORT-R3: The exporter', 'EXPORT-R9: The exporter', 'Critical'),
                 ('Reason: retired.', 'Reason:', 'High'),
                 ('EXPORT-R2: The exporter MUST stop', 'EXPORT-R8: The exporter MUST stop', 'Critical'),
                 ('## Modified requirements', '## Added requirements', 'Critical')]
        for old, new, severity in cases:
            with self.subTest(old=old):
                self.spec.write_text(original.replace(old, new))
                self.assertIn(severity, self.analyze(1).stdout)

    def test_missing_target_and_orphan_acceptance(self):
        self.spec.write_text(self.delta().replace('target: /capabilities/export.md\n', ''))
        self.analyze(1)
        self.spec.write_text(self.delta().replace('- EXPORT-R3: `', '- EXPORT-R8: `'))
        self.assertIn('Critical', self.analyze(1).stdout)


class BaselineTests(DeltaCase):  # R4
    def test_stale_block_refuses_but_unrelated_changes_pass(self):
        self.cap.write_text(self.cap.read_text().replace('preserve dates', 'preserve time zones'))
        self.analyze()
        self.cap.write_text(self.cap.read_text().replace('Write café.', 'Write ASCII.'))
        before = self.snapshot()
        self.assertIn('EXPORT-R1', self.analyze(1).stdout)
        self.assertEqual(before, self.snapshot())

    def test_redirect_and_traversal_refused(self):
        for target in ('/capabilities/other.md', '/capabilities/../export.md', '/project/x.md',
                       '/capabilities/./export.md', '/capabilities//export.md'):
            self.spec.write_text(self.delta().replace('target: /capabilities/export.md', 'target: ' + target))
            self.analyze(1)

    def test_alias_with_matching_approved_mirror_is_refused(self):
        for alias in ('/capabilities/./export.md', '/capabilities//export.md'):
            self.spec.write_text(self.delta().replace('/capabilities/export.md', alias))
            self.assertIn('canonical', self.analyze(1).stdout)

    def test_capability_directory_cannot_escape_bundle(self):
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        shutil.copy2(self.cap, Path(outside.name) / self.cap.name)
        shutil.rmtree(self.cap.parent)
        self.cap.parent.symlink_to(outside.name, target_is_directory=True)
        self.assertIn('target', self.analyze(1).stdout)

    def test_conflict_diagnostic_names_every_operated_conflict(self):
        self.cap.write_text(self.cap.read_text().replace('UTF-8', 'ASCII').replace('legacy headers', 'old headers'))
        output = self.analyze(1).stdout
        self.assertIn('EXPORT-R1', output)
        self.assertIn('EXPORT-R2', output)


class MergeCliTests(DeltaCase):  # R5
    def test_invalid_log_destination_refused_before_receipt_or_target_write(self):
        self.approve()
        log = self.root / 'knowledge/log.md'
        log.unlink()
        log.mkdir()
        before = self.snapshot()
        self.lc('merge', str(self.spec), code=1)
        self.assertEqual(before, self.snapshot())

    def test_preview_then_approved_apply_and_noop(self):
        before = self.snapshot()
        preview = self.lc('merge', str(self.spec), '--dry-run').stdout
        self.assertIn('+', preview)
        self.assertIn('UTF-16', preview)
        self.assertEqual(before, self.snapshot())
        self.lc('merge', str(self.spec), code=1)
        self.approve()
        self.lc('merge', str(self.spec))
        text = self.cap.read_text()
        self.assertIn('UTF-16.\n  - Scenario utf8: Write café.', text)
        self.assertNotIn('EXPORT-R2', text)
        self.assertIn(KEEP, text)
        self.assertLess(text.index('EXPORT-R9'), text.index('EXPORT-R3'))
        self.assertIn('Keep this prose.', text)
        self.assertTrue(text.endswith('## Notes\n\nKeep these notes.\n'))
        after = self.snapshot()
        self.assertIn('up to date', self.lc('merge', str(self.spec)).stdout)
        self.assertEqual(after, self.snapshot())
        self.assertIn('up to date', self.lc('merge', str(self.spec), '--dry-run').stdout)

    def test_apply_edited_spec_refused(self):
        self.approve()
        self.spec.write_text(self.spec.read_text().replace('UTF-16', 'UTF-32'))
        before = self.snapshot()
        self.lc('merge', str(self.spec), code=1)
        self.assertEqual(before, self.snapshot())

    def test_crlf_unrelated_bytes_preserved(self):
        original = self.cap.read_bytes().replace(b'\n', b'\r\n')
        self.cap.write_bytes(original)
        self.spec.write_text(self.delta().replace(digest(OLD), digest(OLD.replace('\n', '\r\n')))
                             .replace(digest(DROP), digest(DROP.replace('\n', '\r\n'))))
        self.approve()
        self.lc('merge', str(self.spec))
        after = self.cap.read_bytes()
        self.assertIn(KEEP.replace('\n', '\r\n').encode(), after)
        self.assertTrue(after.endswith(b'## Notes\r\n\r\nKeep these notes.\r\n'))
        self.assertIn('  - Scenario utf8: Write café.\r\n'.encode(), after)


class ScenarioTests(DeltaCase):  # R6
    def test_continuation_only_scenario_is_preserved_and_requires_directive(self):
        multiline = '- EXPORT-R1: The exporter MUST write UTF-8.\n  - Scenario multiline:\n    Write café.\n'
        self.cap.write_text(self.cap.read_text().replace(OLD, multiline))
        self.spec.write_text(self.delta().replace(digest(OLD), digest(multiline)))
        self.approve()
        self.lc('merge', str(self.spec))
        self.assertIn('  - Scenario multiline:\n    Write café.\n', self.cap.read_text())

    def test_explicit_replacement_and_clear(self):
        for scenarios in ('  - Scenario new: Write ASCII.\n', ''):
            with self.subTest(scenarios=scenarios):
                self.spec.write_text(self.delta(modified='- EXPORT-R1: The exporter MUST write UTF-16.\n'
                                                        '  Scenarios: replace\n' + scenarios))
                preview = self.lc('merge', str(self.spec), '--dry-run').stdout
                self.assertIn('-  - Scenario utf8:', preview)
                self.assertNotIn('+  Scenarios: replace', preview)

    def test_reject_implicit_and_duplicate_scenarios(self):
        for suffix in ('\n  - Scenario new: changed', '\n  - Scenario new:\n    changed',
                       '\n  Scenarios: replace\n  - Scenario same: one\n  - Scenario same: two'):
            self.spec.write_text(self.delta(modified='- EXPORT-R1: The exporter MUST write UTF-16.' + suffix))
            self.analyze(1)

    def test_merge_never_executes_acceptance(self):
        self.spec.write_text(self.delta(command='python3 -c "open(\'SENTINEL\', \'w\').write(\'bad\')"'))
        self.approve()
        self.lc('merge', str(self.spec))
        self.assertFalse((self.root / 'SENTINEL').exists())


class ReceiptRecoveryTests(DeltaCase):  # R7
    def journal_boundary(self, phase):
        self.approve()
        write = lifecycle.write_atomic
        hit = []

        def interrupted(path, data):
            merge = data.get('merge', {})
            is_record = path == self.record()
            state = merge.get('state')
            selected = ((phase == 'before_pending' and is_record and state == 'pending')
                        or (phase == 'after_pending' and is_record and state == 'pending')
                        or (phase == 'pending_scratch' and not is_record and state == 'pending')
                        or (phase == 'before_completed' and is_record and state == 'completed')
                        or (phase == 'after_completed' and is_record and state == 'completed'))
            if selected and not hit:
                hit.append(phase)
                if phase.startswith('after_'):
                    write(path, data)
                raise OSError('injected journal boundary ' + phase)
            return write(path, data)

        oldcwd = Path.cwd()
        os.chdir(self.root)
        try:
            with mock.patch.object(lifecycle, 'write_atomic', side_effect=interrupted), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(lifecycle.main(['merge', str(self.spec)]), 1)
        finally:
            os.chdir(oldcwd)
        self.assertEqual(hit, [phase])
        self.lc('merge', str(self.spec))  # Actual new CLI process, no injection.
        receipt = json.loads(self.record().read_text())['merge']
        self.assertEqual(receipt['state'], 'completed')
        self.assertEqual((self.root / 'knowledge/log.md').read_text().count(receipt['log_id']), 1)
        self.assertNotIn('EXPORT-R2', self.cap.read_text())
        self.assertIn('UTF-16', self.cap.read_text())
        self.cli('okf.py', 'records')

    def test_before_pending_publication(self):
        self.journal_boundary('before_pending')

    def test_after_pending_publication_before_scratch(self):
        self.journal_boundary('after_pending')

    def test_pending_scratch_failure(self):
        self.journal_boundary('pending_scratch')

    def test_before_completed_publication(self):
        self.journal_boundary('before_completed')

    def test_completed_publication_before_scratch(self):
        self.journal_boundary('after_completed')

    def interrupted(self, helper):
        self.approve()
        oldcwd = Path.cwd()
        os.chdir(self.root)
        try:
            with mock.patch(helper, side_effect=OSError('injected I/O failure')), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(lifecycle.main(['merge', str(self.spec)]), 1)
        finally:
            os.chdir(oldcwd)
        self.assertEqual(json.loads(self.record().read_text())['merge']['state'], 'pending')

    def test_resume_after_target_and_log_interruptions(self):
        self.interrupted('okf.append_log')
        self.assertIn('UTF-16', self.cap.read_text())
        # A stale scratch copy must not overwrite the durable journal.
        statefile = next((self.root / '.git/okf-scratch').glob('lifecycle-*.json'))
        state = json.loads(statefile.read_text())
        state.pop('merge', None)
        statefile.write_text(json.dumps(state))
        self.lc('merge', str(self.spec))
        receipt = json.loads(self.record().read_text())['merge']
        self.assertEqual(receipt['state'], 'completed')
        self.assertEqual((self.root / 'knowledge/log.md').read_text().count(receipt['log_id']), 1)
        self.cli('okf.py', 'records')

    def test_resume_after_log_write_does_not_duplicate(self):
        self.interrupted('okf.reindex')
        self.lc('merge', str(self.spec))
        receipt = json.loads(self.record().read_text())['merge']
        self.assertEqual((self.root / 'knowledge/log.md').read_text().count(receipt['log_id']), 1)

    def test_third_state_refused(self):
        self.interrupted('okf.append_log')
        self.cap.write_text(self.cap.read_text().replace('UTF-16', 'UTF-64'))
        before = self.snapshot()
        self.lc('merge', str(self.spec), code=1)
        self.assertEqual(before, self.snapshot())


class LifecycleIntegrationTests(DeltaCase):  # R9
    def test_trace_queue_audit_and_converge(self):
        self.approve()
        specbytes = self.spec.read_bytes()
        self.assertIn('EXPORT-R2', self.lc('queue-from-spec', str(self.spec)).stdout)
        plan = self.root / 'plan.md'
        plan.write_text('EXPORT-R3 EXPORT-R1 EXPORT-R2')
        tests = self.root / 'tests.py'
        tests.write_text('EXPORT-R30 EXPORT-R10 EXPORT-R20')
        self.lc('trace', str(self.spec), '--plan', str(plan), '--tests', str(tests), code=1)
        tests.write_text('EXPORT-R3 EXPORT-R1 EXPORT-R2')
        self.lc('trace', str(self.spec), '--plan', str(plan), '--tests', str(tests))
        self.lc('audit')
        self.assertIn('3 PASS', self.lc('converge', str(self.spec)).stdout)
        self.lc('merge', str(self.spec))
        self.analyze()
        self.assertIn('3 PASS', self.lc('converge', str(self.spec)).stdout)
        self.lc('audit')
        self.assertEqual(specbytes, self.spec.read_bytes())
        self.assertEqual(set(json.loads(self.record().read_text())['stages']), {'intent'})


class VerifyE2ETests(DeltaCase):  # R8
    def test_pending_and_missing_receipts_refuse_verify(self):
        self.prepare_review()
        original = json.loads(self.record().read_text())
        for mode in ('pending', 'missing'):
            record = json.loads(json.dumps(original))
            if mode == 'pending':
                record['merge']['state'] = 'pending'
            else:
                del record['merge']
            self.record().write_text(json.dumps(record))
            result = self.lc('stage', 'verify', '--note', mode + ' receipt', code=1)
            self.assertIn('merge', result.stderr)

    def prepare_review(self, manual=False):
        if manual:
            self.spec.write_text(self.spec.read_text().replace('- EXPORT-R1: `python3 -c "raise SystemExit(0)"` passes.',
                                                              '- EXPORT-R1: Check the output by inspection.'))
        self.approve()
        (self.root / 'plan.md').write_text('EXPORT-R3 EXPORT-R1 EXPORT-R2')
        (self.root / 'review.md').write_text('# Review\n\n## Verdict\nApproved\n\n## Validation Reviewed\nOTHER-EXPORT-R1\n')
        self.lc('stage', 'plan', '--ref', 'plan.md')
        self.lc('stage', 'review', '--ref', 'review.md')
        self.lc('merge', str(self.spec))
        self.lc('converge', str(self.spec))
        self.lc('retrospect', '--no-new-lessons', 'The receipt fixture adds no new project lessons.')

    def test_receipt_cannot_restore_removed_requirement(self):
        self.prepare_review()
        record = json.loads(self.record().read_text())
        removed = next(op for op in record['merge']['operations'] if op['id'] == 'EXPORT-R2')
        removed['after'], removed['replacement'] = digest(DROP), DROP
        self.record().write_text(json.dumps(record))
        self.cap.write_text(self.cap.read_text().replace('## Notes', DROP + '\n## Notes'))
        self.lc('stage', 'verify', '--note', 'tampered removal receipt', code=1)

    def test_receipt_prose_must_match_approved_delta(self):
        self.prepare_review()
        record = json.loads(self.record().read_text())
        modified = next(op for op in record['merge']['operations'] if op['id'] == 'EXPORT-R1')
        modified['replacement'] = modified['replacement'].replace('UTF-16', 'UTF-64')
        modified['after'] = digest(modified['replacement'])
        self.record().write_text(json.dumps(record))
        self.cap.write_text(self.cap.read_text().replace('UTF-16', 'UTF-64'))
        self.lc('stage', 'verify', '--note', 'tampered prose receipt', code=1)

    def test_manual_citation_requires_complete_id(self):
        self.prepare_review(manual=True)
        self.lc('stage', 'verify', '--note', 'foreign citation', code=1)

    def test_complete_flow_and_postimage_mutations(self):
        self.approve()
        (self.root / 'plan.md').write_text('EXPORT-R3 EXPORT-R1 EXPORT-R2')
        (self.root / 'review.md').write_text('# Review\n\n## Verdict\nApproved\n')
        self.lc('stage', 'plan', '--ref', 'plan.md')
        self.lc('stage', 'review', '--ref', 'review.md')
        self.lc('converge', str(self.spec))
        self.lc('retrospect', '--no-new-lessons', 'The receipt fixture adds no new project lessons.')
        self.assertIn('merge', self.lc('stage', 'verify', '--note', 'fixture checks', code=1).stderr)
        self.lc('merge', str(self.spec))
        self.lc('converge', str(self.spec))
        self.lc('stage', 'verify', '--note', 'fixture acceptance passed')
        original = self.cap.read_text()
        self.cap.write_text(original.replace('Keep this prose.', 'Different unrelated prose.'))
        self.lc('stage', 'verify', '--note', 'unrelated prose permitted')
        self.cap.write_text(original.replace('UTF-16', 'UTF-32'))
        self.lc('stage', 'verify', '--note', 'tampered', code=1)
        self.cap.write_text(original.replace('resource:', 'lost_resource:'))
        self.lc('stage', 'verify', '--note', 'missing source', code=1)


class ConflictTests(DeltaCase):  # R10
    def test_disjoint_delta_still_applies_after_first_merge(self):
        self.approve()
        self.lc('merge', str(self.spec))
        second = self.spec.with_name('disjoint.md')
        text = self.delta(added='- EXPORT-R4: The exporter MUST escape quotes.',
                          modified='- EXPORT-R9: The exporter MUST preserve time zones.', removed='None.')
        text = text.replace('- EXPORT-R3: absent', '- EXPORT-R4: absent')
        text = text.replace('- EXPORT-R1: sha256:' + digest(OLD), '- EXPORT-R9: sha256:' + digest(KEEP))
        text = text.replace('- EXPORT-R2: sha256:' + digest(DROP) + '\n', '')
        text = text.replace('- EXPORT-R3: `', '- EXPORT-R4: `').replace('- EXPORT-R1: `', '- EXPORT-R9: `')
        text = '\n'.join(line for line in text.split('\n') if not line.startswith('- EXPORT-R2: `'))
        second.write_text(text)
        self.lc('tier', 'L2', '--new', '--reason', 'second task', '--kind', 'feature')
        self.lc('stage', 'intent', '--ref', str(second.relative_to(self.root)), '--approved-by', 'human:test')
        self.lc('merge', str(second))
        self.assertIn('UTF-16', self.cap.read_text())
        self.assertIn('preserve time zones', self.cap.read_text())
        self.assertIn('EXPORT-R4', self.cap.read_text())

    def test_malformed_advisory_draft_does_not_block(self):
        other = self.spec.with_name('broken.md')
        other.write_text(self.delta() + '\n## Added requirements\n- malformed\n')
        self.lc('merge', str(self.spec), '--dry-run')

    def test_draft_warning_and_conflicting_second_delta(self):
        other = self.spec.with_name('other.md')
        other.write_bytes(self.spec.read_bytes())
        result = self.lc('merge', str(self.spec), '--dry-run')
        self.assertIn('local draft overlap', result.stderr)
        self.assertIn('unobserved branches', result.stderr)
        self.approve()
        self.lc('merge', str(self.spec))
        before = self.snapshot()
        self.lc('merge', str(other), '--dry-run', code=1)
        self.assertEqual(before, self.snapshot())


class DocumentationTests(unittest.TestCase):  # R12
    def test_installed_skill_content_and_preservation(self):
        from test_install import InstallerCase
        case = InstallerCase()
        case.setUp()
        self.addCleanup(case.doCleanups)
        case.write('AGENTS.md', '# Our instructions\n')
        case.commit()
        case.run_install()
        skill = (case.target / '.claude/skills/onboard/SKILL.md').read_text()
        self.assertIn('okf.py onboard', skill)
        self.assertIn('approval', skill)
        self.assertIn('sources', skill)
        self.assertTrue((case.target / '.ai/scripts/brownfield.py').is_file())
        self.assertTrue((case.target / 'AGENTS.md').read_text().startswith('# Our instructions\n'))
        self.assertFalse((case.target / 'knowledge/specifications/brownfield-onboarding-and-deltas.md').exists())
        result = subprocess.run([sys.executable, '.ai/scripts/okf.py', 'records'], cwd=case.target,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_workflow_and_hold_documented(self):
        root = SCRIPTS.parents[1]
        for path in ('.ai/lifecycle.md', '.ai/agents/analyst.md', '.claude/skills/spec/SKILL.md'):
            self.assertIn('Target baseline', (root / path).read_text())
        roadmap = root / '.ai/README.md'
        self.assertIn('baseline remains on hold', roadmap.read_text())


if __name__ == '__main__':
    unittest.main()
