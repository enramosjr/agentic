"""Attested evidence and risk acceptance in the assurance report, increment 4 (docs/assurance/specification-4.md R1-R9)."""
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import brownfield  # noqa: E402
from test_assurance import CAP, RECORDS, SCOPED, Case  # noqa: E402

MANUAL_REQ = '- CALC-R2: The calculator MUST look right.\n  - Verify: manual - needs a UX review\n  - Scenario look: it looks right.\n'
REPORT = '# Review\n\n## Verdict\n\n{verdict}\n\n## Validation Reviewed\n\n{cited}\n'


def normalise(text):
    """Strip the values that differ per run: short heads, timestamps and task-id record names."""
    text = re.sub(r'head=[0-9a-f]{7}', 'head=HEAD', text)
    text = re.sub(r'at=\d{4}-\d\d-\d\dT[\d:]+(?:\.[0-9]{1,6})?Z', 'at=NOW', text)
    text = re.sub(r'"at": "[^"]+"', '"at": "NOW"', text)
    text = re.sub(r'"head": "[0-9a-f]{40}"', '"head": "HEAD"', text)
    return re.sub(r'[\w.-]+\.json', 'RECORD.json', text)


class AttestedCase(Case):
    def reviewed(self, name='r1', cited='- CALC-R2 looked right.', verdict='Approved', committed=False):
        """Record a lifecycle task whose review stage references a report; returns the report path."""
        report = self.write(f'reviews/{name}.md', REPORT.format(verdict=verdict, cited=cited))
        self.task(new=True)
        self.lc('stage', 'intent', '--note', 'goal: judge calc; check: review; assumptions: none')
        self.lc('stage', 'plan', '--note', 'one step')
        self.lc('stage', 'review', '--ref', f'reviews/{name}.md', '--note', 'self review of the diff')
        if committed:
            self.commit(f'record {name}')
        return report

    def record_path(self, index=-1):
        return sorted((self.root / RECORDS).glob('*.json'))[index]

    def retime(self, path, at, approved_by=None):
        data = json.loads(path.read_text())
        data['stages']['review']['at'] = at
        if approved_by is not None:
            data['stages']['intent']['approved_by'] = approved_by
        path.write_text(json.dumps(data, indent=2))

    def manual_capability(self, scoped=False):
        self.capability((SCOPED if scoped else '') + MANUAL_REQ)
        self.commit('manual capability')

    def record_for(self, ref):
        for path in sorted((self.root / RECORDS).glob('*.json')):
            if json.loads(path.read_text()).get('stages', {}).get('review', {}).get('ref') == ref:
                return path
        raise AssertionError(f'no record references {ref}')

    def block_sha(self, rid='CALC-R2'):
        text = brownfield.read(self.root / CAP)
        _, spans = brownfield.document(text)
        return brownfield.sha(brownfield.blocks(text, spans['requirements'])[rid].raw)


def review_digest(path):
    """sha256 of a frontmatter-free report, as the review stage records it."""
    return hashlib.sha256(path.read_text().strip().encode()).hexdigest()


GOLDEN_REQUIREMENTS = (
    SCOPED
    + '- CALC-R2: The calculator MUST look right.\n  - Verify: manual - needs a UX review\n  - Scenario look: it looks right.\n'
    + '- CALC-R3: Stale MUST be shown.\n  - Verify: `python3 check.py`\n  - Inputs: `stale.txt`\n'
    + '- CALC-R4: Failure MUST be shown.\n  - Verify: `python3 failcheck.py`\n  - Inputs: `failcheck.py`\n'
    + '- CALC-R5: Never run MUST be unverified.\n  - Verify: `python3 check.py --unrun`\n  - Inputs: `src/**`\n'
    + '- CALC-R6: Undeclared MUST be shown.\n  - Scenario nothing: nothing declared.\n'
    + '- CALC-R7: Prose verify MUST be invalid.\n  - Verify: run the tests\n')


# Captured with the unmodified increment 1 scripts (before any increment 4 change); R9 byte-identity baseline.
GOLDEN = {'changed': (1,
             '{\n'
             '  "changed_base": "HEAD~1",\n'
             '  "diagnostics": [],\n'
             '  "requirements": [\n'
             '    {\n'
             '      "basis": "declared",\n'
             '      "capability": "knowledge/capabilities/calc.md",\n'
             '      "evidence": null,\n'
             '      "id": "CALC-R2",\n'
             '      "reason": "no Inputs: declared, so the whole tree counts; MANUAL: human judgment: needs '
             'a UX review",\n'
             '      "status": "MANUAL"\n'
             '    },\n'
             '    {\n'
             '      "basis": "mechanical",\n'
             '      "capability": "knowledge/capabilities/calc.md",\n'
             '      "evidence": {\n'
             '        "at": "NOW",\n'
             '        "exit": 0,\n'
             '        "head": "HEAD",\n'
             '        "record": "RECORD.json"\n'
             '      },\n'
             '      "id": "CALC-R3",\n'
             '      "reason": "inputs changed: stale.txt; STALE: req:CALC-R3 inputs changed: stale.txt; run '
             '`python3 .ai/scripts/lifecycle.py assure --run CALC-R3`",\n'
             '      "status": "STALE"\n'
             '    },\n'
             '    {\n'
             '      "basis": "none",\n'
             '      "capability": "knowledge/capabilities/calc.md",\n'
             '      "evidence": null,\n'
             '      "id": "CALC-R7",\n'
             '      "reason": "obligation is invalid, so its scope is unknown; INVALID: Verify: needs one '
             'backticked command, or manual and a reason",\n'
             '      "status": "INVALID"\n'
             '    }\n'
             '  ],\n'
             '  "schema_version": 1,\n'
             '  "summary": {\n'
             '    "FAILED": 0,\n'
             '    "INVALID": 1,\n'
             '    "MANUAL": 1,\n'
             '    "STALE": 1,\n'
             '    "UNDECLARED": 0,\n'
             '    "UNVERIFIED": 0,\n'
             '    "VERIFIED": 0\n'
             '  }\n'
             '}\n'),
 'json': (1,
          '{\n'
          '  "diagnostics": [],\n'
          '  "requirements": [\n'
          '    {\n'
          '      "basis": "mechanical",\n'
          '      "capability": "knowledge/capabilities/calc.md",\n'
          '      "evidence": {\n'
          '        "at": "NOW",\n'
          '        "exit": 0,\n'
          '        "head": "HEAD",\n'
          '        "record": "RECORD.json"\n'
          '      },\n'
          '      "id": "CALC-R1",\n'
          '      "reason": "passed on unchanged inputs; covers only this command on these inputs",\n'
          '      "status": "VERIFIED"\n'
          '    },\n'
          '    {\n'
          '      "basis": "declared",\n'
          '      "capability": "knowledge/capabilities/calc.md",\n'
          '      "evidence": null,\n'
          '      "id": "CALC-R2",\n'
          '      "reason": "human judgment: needs a UX review",\n'
          '      "status": "MANUAL"\n'
          '    },\n'
          '    {\n'
          '      "basis": "mechanical",\n'
          '      "capability": "knowledge/capabilities/calc.md",\n'
          '      "evidence": {\n'
          '        "at": "NOW",\n'
          '        "exit": 0,\n'
          '        "head": "HEAD",\n'
          '        "record": "RECORD.json"\n'
          '      },\n'
          '      "id": "CALC-R3",\n'
          '      "reason": "req:CALC-R3 inputs changed: stale.txt; run `python3 .ai/scripts/lifecycle.py '
          'assure --run CALC-R3`",\n'
          '      "status": "STALE"\n'
          '    },\n'
          '    {\n'
          '      "basis": "mechanical",\n'
          '      "capability": "knowledge/capabilities/calc.md",\n'
          '      "evidence": {\n'
          '        "at": "NOW",\n'
          '        "exit": 1,\n'
          '        "head": "HEAD",\n'
          '        "record": "RECORD.json"\n'
          '      },\n'
          '      "id": "CALC-R4",\n'
          '      "reason": "newest run exited 1",\n'
          '      "status": "FAILED"\n'
          '    },\n'
          '    {\n'
          '      "basis": "none",\n'
          '      "capability": "knowledge/capabilities/calc.md",\n'
          '      "evidence": null,\n'
          '      "id": "CALC-R5",\n'
          '      "reason": "no evidence; run `python3 .ai/scripts/lifecycle.py assure --run CALC-R5`",\n'
          '      "status": "UNVERIFIED"\n'
          '    },\n'
          '    {\n'
          '      "basis": "none",\n'
          '      "capability": "knowledge/capabilities/calc.md",\n'
          '      "evidence": null,\n'
          '      "id": "CALC-R6",\n'
          '      "reason": "no Verify: line",\n'
          '      "status": "UNDECLARED"\n'
          '    },\n'
          '    {\n'
          '      "basis": "none",\n'
          '      "capability": "knowledge/capabilities/calc.md",\n'
          '      "evidence": null,\n'
          '      "id": "CALC-R7",\n'
          '      "reason": "Verify: needs one backticked command, or manual and a reason",\n'
          '      "status": "INVALID"\n'
          '    }\n'
          '  ],\n'
          '  "schema_version": 1,\n'
          '  "summary": {\n'
          '    "FAILED": 1,\n'
          '    "INVALID": 1,\n'
          '    "MANUAL": 1,\n'
          '    "STALE": 1,\n'
          '    "UNDECLARED": 1,\n'
          '    "UNVERIFIED": 1,\n'
          '    "VERIFIED": 1\n'
          '  }\n'
          '}\n'),
 'strict': (1,
            'VERIFIED   CALC-R1 knowledge/capabilities/calc.md head=HEAD at=NOW - passed on unchanged '
            'inputs; covers only this command on these inputs\n'
            'MANUAL     CALC-R2 knowledge/capabilities/calc.md - human judgment: needs a UX review\n'
            'STALE      CALC-R3 knowledge/capabilities/calc.md head=HEAD at=NOW - req:CALC-R3 inputs '
            'changed: stale.txt; run `python3 .ai/scripts/lifecycle.py assure --run CALC-R3`\n'
            'FAILED     CALC-R4 knowledge/capabilities/calc.md head=HEAD at=NOW - newest run exited 1\n'
            'UNVERIFIED CALC-R5 knowledge/capabilities/calc.md - no evidence; run `python3 '
            '.ai/scripts/lifecycle.py assure --run CALC-R5`\n'
            'UNDECLARED CALC-R6 knowledge/capabilities/calc.md - no Verify: line\n'
            'INVALID    CALC-R7 knowledge/capabilities/calc.md - Verify: needs one backticked command, or '
            'manual and a reason\n'
            'assure: 1 VERIFIED, 1 STALE, 1 FAILED, 1 UNVERIFIED, 1 INVALID, 1 MANUAL, 1 UNDECLARED\n'),
 'text': (1,
          'VERIFIED   CALC-R1 knowledge/capabilities/calc.md head=HEAD at=NOW - passed on unchanged inputs; '
          'covers only this command on these inputs\n'
          'MANUAL     CALC-R2 knowledge/capabilities/calc.md - human judgment: needs a UX review\n'
          'STALE      CALC-R3 knowledge/capabilities/calc.md head=HEAD at=NOW - req:CALC-R3 inputs changed: '
          'stale.txt; run `python3 .ai/scripts/lifecycle.py assure --run CALC-R3`\n'
          'FAILED     CALC-R4 knowledge/capabilities/calc.md head=HEAD at=NOW - newest run exited 1\n'
          'UNVERIFIED CALC-R5 knowledge/capabilities/calc.md - no evidence; run `python3 '
          '.ai/scripts/lifecycle.py assure --run CALC-R5`\n'
          'UNDECLARED CALC-R6 knowledge/capabilities/calc.md - no Verify: line\n'
          'INVALID    CALC-R7 knowledge/capabilities/calc.md - Verify: needs one backticked command, or '
          'manual and a reason\n'
          'assure: 1 VERIFIED, 1 STALE, 1 FAILED, 1 UNVERIFIED, 1 INVALID, 1 MANUAL, 1 UNDECLARED\n')}


class GoldenCase(AttestedCase):
    """Every status, plus an Approved review citing only a non-MANUAL id: the R9 baseline fixture."""

    def build_golden(self):
        self.write('stale.txt', 'one\n')
        self.write('failcheck.py', 'import sys\nsys.exit(1)\n')
        self.capability(GOLDEN_REQUIREMENTS)
        self.commit('golden capability')
        self.task()
        self.lc('assure', '--run', 'CALC-R1', 'CALC-R3')
        self.lc('assure', '--run', 'CALC-R4', code=1)
        self.write('stale.txt', 'two\n')
        self.reviewed(name='golden', cited='- CALC-R1 reran green.')
        self.commit('golden state')

    def golden(self):
        out = {}
        for key, args in (('text', ()), ('strict', ('--strict',)), ('json', ('--json',)),
                          ('changed', ('--json', '--changed', '--base', 'HEAD~1'))):
            result = self.lc('assure', *args, code=None)
            out[key] = (result.returncode, normalise(result.stdout))
        return out


class SourceTests(AttestedCase):  # R1
    def setUp(self):
        super().setUp()
        self.manual_capability()

    def test_active_state_attestation(self):
        self.reviewed()
        item = self.status('CALC-R2')
        att = item['attested']
        self.assertEqual((item['status'], att['review'], att['basis'], att['judgment']), ('MANUAL', 'reviews/r1.md', 'attested', True))
        self.assertEqual(att['review_sha256'], review_digest(self.root / 'reviews/r1.md'))
        self.assertTrue(re.match(r'\d{4}-\d\d-\d\dT[\d:]+Z$', att['at']))
        self.assertTrue(att['record'].endswith('.json'))

    def test_committed_record_attestation(self):
        self.reviewed(committed=True)
        self.task(new=True)
        att = self.status('CALC-R2')['attested']
        self.assertEqual(att['review'], 'reviews/r1.md')
        self.assertEqual(att['record'], self.record_for('reviews/r1.md').name)

    def test_newest_review_wins_by_stage_time_not_record_name(self):
        self.reviewed(name='a', committed=True)
        self.reviewed(name='b', committed=True)
        first, second = self.record_for('reviews/a.md'), self.record_for('reviews/b.md')
        self.retime(first, '2026-03-01T00:00:00Z')
        self.retime(second, '2026-02-01T00:00:00Z')
        self.task(new=True)
        self.assertEqual(self.status('CALC-R2')['attested']['review'], 'reviews/a.md')
        self.retime(first, '2026-01-01T00:00:00Z')
        self.assertEqual(self.status('CALC-R2')['attested']['review'], 'reviews/b.md')

    def test_no_citation_no_attestation(self):
        data, _ = self.report()
        self.assertNotIn('attested', data['requirements'][0])


class FailClosedTests(AttestedCase):  # R2
    def setUp(self):
        super().setUp()
        self.manual_capability()
        self.before = self.outputs()  # exit 0: a manual-only capability, so any change in code would show

    def outputs(self):
        return [(r.returncode, r.stdout) for r in (self.lc('assure', code=None), self.lc('assure', '--json', code=None))]

    def not_honored(self, reason):
        data, code = self.report()
        item = data['requirements'][0]
        self.assertNotIn('attested', item)
        self.assertEqual(code, 0)
        [note] = data['notes']
        self.assertTrue(note.startswith('attestation: CALC-R2: '), note)
        self.assertIn('not honored', note)
        self.assertIn(reason, note)
        text = self.lc('assure').stdout
        self.assertIn('note: ' + note, text.splitlines())
        self.assertNotIn('judgment (attested', text)

    def test_edited_report(self):
        report = self.reviewed()
        report.write_text(report.read_text() + '\nA late edit.\n')
        self.not_honored('changed since it was recorded')

    def test_changes_requested_verdict(self):
        self.reviewed(verdict='Changes requested: fix it')
        self.not_honored('verdict is not Approved')

    def test_ledger_audit_failing_record(self):
        self.reviewed(committed=True)
        path = self.record_for('reviews/r1.md')
        data = json.loads(path.read_text())
        data['ledger'] = [{'label': 'x', 'output': 'SECRET'}]
        path.write_text(json.dumps(data))
        self.task(new=True)
        self.not_honored('failed ledger audit')

    def test_uncited_id_gives_nothing(self):
        self.reviewed(cited='- CALC-R9 was looked at.')
        data, code = self.report()
        self.assertEqual((code, 'attested' in data['requirements'][0], 'notes' in data), (0, False, False))
        self.assertEqual(self.outputs(), self.before)

    def test_longer_id_is_not_a_citation(self):
        self.reviewed(cited='- CALC-R20 and xCALC-R2 and CALC-R2-extra.')
        self.assertEqual(self.outputs(), self.before)

    def test_deleted_report_is_silent(self):
        report = self.reviewed()
        self.assertIn('attested', self.status('CALC-R2'))
        report.unlink()
        self.assertEqual(self.outputs(), self.before)

    def test_refs_outside_the_repository_are_skipped(self):
        outside = self.root.parent / 'outside.md'
        outside.write_text(REPORT.format(verdict='Approved', cited='- CALC-R2'))
        self.reviewed(committed=True)
        self.task(new=True)
        path = self.record_for('reviews/r1.md')
        (self.root / 'reviews/link.md').symlink_to(outside)
        for ref in ('../outside.md', str(outside), 'reviews/link.md'):
            data = json.loads(path.read_text())
            data['stages']['review'].update(ref=ref, sha256=review_digest(outside))
            path.write_text(json.dumps(data))
            self.assertEqual(self.outputs(), self.before, ref)

    def test_unreadable_record_contributes_nothing(self):
        self.write(f'{RECORDS}/bad.json', '{not json')
        data, code = self.report()
        self.assertEqual((code, 'attested' in data['requirements'][0], 'notes' in data), (0, False, False))
        self.assertIn('bad.json', ' '.join(data['diagnostics']))  # the existing diagnostic, not a note

    def test_honored_attestation_suppresses_notes_for_the_same_id(self):
        self.reviewed(name='bad', verdict='Changes requested', committed=True)
        self.reviewed(name='good', committed=True)
        self.retime(self.record_for('reviews/bad.md'), '2026-03-01T00:00:00Z')
        self.retime(self.record_for('reviews/good.md'), '2026-02-01T00:00:00Z')
        self.task(new=True)
        data, _ = self.report()
        self.assertEqual(data['requirements'][0]['attested']['review'], 'reviews/good.md')
        self.assertNotIn('notes', data)


class PinTests(AttestedCase):  # R3
    def setUp(self):
        super().setUp()
        self.manual_capability(scoped=True)

    def test_matching_pin_is_honored_and_bound(self):
        self.reviewed(cited=f'- CALC-R2@{self.block_sha()[:12]} looked right.')
        att = self.status('CALC-R2')['attested']
        self.assertEqual((att['pinned'], att['reason']), (True, None))

    def test_pin_is_case_insensitive_and_may_be_longer(self):
        self.reviewed(cited=f'- CALC-R2@{self.block_sha()[:20].upper()} looked right.')
        self.assertTrue(self.status('CALC-R2')['attested']['pinned'])

    def test_edit_inside_block_invalidates_pin(self):
        self.reviewed(cited=f'- CALC-R2@{self.block_sha()[:12]} looked right.')
        self.capability(SCOPED + MANUAL_REQ.replace('MUST look right', 'MUST look very right'))
        data, code = self.report()
        self.assertNotIn('attested', data['requirements'][1])
        self.assertIn('requirement changed since attestation', ' '.join(data['notes']))
        self.assertEqual(code, 1)  # the scoped CALC-R1 is UNVERIFIED; the note changes nothing

    def test_edit_outside_block_keeps_pin(self):
        self.reviewed(cited=f'- CALC-R2@{self.block_sha()[:12]} looked right.')
        self.capability(SCOPED + MANUAL_REQ)
        path = self.root / CAP
        path.write_text(path.read_text().replace('Prose.', 'Different prose.'))
        self.assertTrue(self.status('CALC-R2')['attested']['pinned'])

    def test_unpinned_is_honored_but_labeled(self):
        self.reviewed()
        att = self.status('CALC-R2')['attested']
        self.assertFalse(att['pinned'])
        self.assertIn('not bound to requirement text', att['reason'])
        self.assertIn(self.block_sha()[:12], att['reason'])

    def test_malformed_pin_is_not_honored(self):
        self.reviewed(cited='- CALC-R2@xyz looked right.')
        data, _ = self.report()
        self.assertNotIn('attested', data['requirements'][1])
        self.assertIn('malformed pin', ' '.join(data['notes']))

    def test_short_pin_is_malformed(self):
        self.reviewed(cited=f'- CALC-R2@{self.block_sha()[:11]} looked right.')
        data, _ = self.report()
        self.assertNotIn('attested', data['requirements'][1])
        self.assertIn('malformed pin', ' '.join(data['notes']))

    def test_matching_pin_wins_over_other_mentions(self):
        self.reviewed(cited=f'- CALC-R2@{"0" * 12} stale.\n- CALC-R2 plain.\n- CALC-R2@{self.block_sha()[:12]} ok.')
        self.assertTrue(self.status('CALC-R2')['attested']['pinned'])

    def test_adding_accept_risk_changes_the_digest(self):
        pin = self.block_sha()[:12]
        self.reviewed(cited=f'- CALC-R2@{pin} looked right.')
        self.capability(SCOPED + MANUAL_REQ.replace('  - Scenario look', '  - Accept-risk: 2999-12-31 by human:x - fine\n  - Scenario look'))
        self.assertNotEqual(self.block_sha()[:12], pin)
        data, _ = self.report()
        self.assertNotIn('attested', data['requirements'][1])
        self.assertIn('requirement changed since attestation', ' '.join(data['notes']))


class LabelTests(AttestedCase):  # R4
    KEYS = {'basis', 'judgment', 'record', 'review', 'review_sha256', 'at', 'intent_approved_by', 'pinned', 'reason'}

    def setUp(self):
        super().setUp()
        self.manual_capability()

    def test_exact_key_set_and_judgment_labels(self):
        self.reviewed(committed=True)
        self.task(new=True)
        item = self.status('CALC-R2')
        self.assertEqual(set(item['attested']), self.KEYS)
        self.assertEqual((item['attested']['basis'], item['attested']['judgment']), ('attested', True))
        self.assertEqual((item['status'], item['basis']), ('MANUAL', 'declared'))

    def test_intent_approved_by_is_null_or_the_recorded_claim(self):
        self.reviewed(committed=True)
        self.task(new=True)
        self.assertIsNone(self.status('CALC-R2')['attested']['intent_approved_by'])
        self.retime(self.record_for('reviews/r1.md'), '2026-02-01T00:00:00Z', approved_by='human:enramosjr')
        self.assertEqual(self.status('CALC-R2')['attested']['intent_approved_by'], 'human:enramosjr')

    def test_text_line_is_indented_labeled_and_omits_the_id(self):
        self.reviewed()
        lines = self.lc('assure').stdout.splitlines()
        index = next(i for i, line in enumerate(lines) if line.startswith('MANUAL'))
        line = lines[index + 1]
        self.assertTrue(line.startswith('    judgment (attested, not verified): '), line)
        self.assertNotIn('CALC-R2', line)
        self.assertIn('reviews/r1.md', line)
        self.assertIn('(claim)', line)
        self.assertEqual(lines[-1].split(': ', 1)[0], 'assure')


class NoUpgradeTests(GoldenCase):  # R5
    def test_citing_every_non_manual_requirement_changes_nothing(self):
        self.build_golden()
        self.reviewed(name='all', cited='\n'.join(f'- CALC-R{n} looked right.' for n in (1, 3, 4, 5, 6, 7)))
        self.assertEqual(self.golden(), GOLDEN)
        data, _ = self.report()
        self.assertFalse(any('attested' in item for item in data['requirements']))

    def test_manual_stays_manual_and_basis_declared(self):
        self.build_golden()
        self.reviewed(name='manual', cited='- CALC-R2 looked right.')
        data, _ = self.report()
        item = next(r for r in data['requirements'] if r['id'] == 'CALC-R2')
        self.assertEqual((item['status'], item['basis'], item['evidence']), ('MANUAL', 'declared', None))
        self.assertEqual(item['attested']['basis'], 'attested')
        self.assertEqual(data['summary'], json.loads(GOLDEN['json'][1])['summary'])
        self.assertFalse(any(r['status'] == 'VERIFIED' and r['id'] == 'CALC-R2' for r in data['requirements']))
        self.assertEqual(self.report('--strict')[1], 1)


def risk_capability(*lines, verify=True):
    body = '- CALC-R1: The calculator MUST add.\n'
    if verify:
        body += '  - Verify: `python3 check.py`\n  - Inputs: `check.py` `src/**`\n'
    body += ''.join(f'  - {line}\n' for line in lines)
    return body + '  - Scenario add: 1 + 1 is 2.\n'


class RiskSyntaxTests(AttestedCase):  # R6
    def invalid(self, *lines, verify=True, reason=''):
        self.capability(risk_capability(*lines, verify=verify))
        item = self.status('CALC-R1')
        self.assertEqual(item['status'], 'INVALID', lines)
        self.assertIn(reason, item['reason'])
        self.assertEqual(self.report()[1], 1)

    def test_valid_forms_stay_valid(self):
        for line in ('Accept-risk: 2999-12-31 by human:enramosjr - known gap, tracked',
                     'Accept-risk: 2999-12-31 by decision:ADR-7 - accepted in the ADR',
                     'Accept-risk: 2000-01-01 by human:x - a reason - with a dash'):
            self.capability(risk_capability(line))
            self.assertNotEqual(self.status('CALC-R1')['status'], 'INVALID', line)

    def test_malformed_forms_are_invalid_with_a_reason(self):
        self.invalid('Accept-risk: 2999-13-45 by human:x - r', reason='date must be a valid YYYY-MM-DD')
        self.invalid('Accept-risk: tomorrow by human:x - r', reason='date must be a valid YYYY-MM-DD')
        self.invalid('Accept-risk: 2999-12-31 - r', reason="needs 'by human:<id>' or 'by decision:<ADR>'")
        self.invalid('Accept-risk: 2999-12-31 by someone - r', reason="needs 'by human:<id>' or 'by decision:<ADR>'")
        self.invalid('Accept-risk: 2999-12-31 by human:x', reason="needs a reason after ' - '")
        self.invalid('Accept-risk: 2999-12-31 by human:x - ', reason="needs a reason after ' - '")
        self.invalid('Accept-risk: 2999-12-31 by human:x - a', 'Accept-risk: 2999-12-31 by human:x - b', reason='duplicate Accept-risk: line')

    def test_line_after_a_scenario_is_invalid(self):
        self.capability('- CALC-R1: The calculator MUST add.\n  - Verify: `python3 check.py`\n'
                        '  - Scenario add: 1 + 1 is 2.\n  - Accept-risk: 2999-12-31 by human:x - r\n')
        item = self.status('CALC-R1')
        self.assertEqual(item['status'], 'INVALID')
        self.assertIn('Accept-risk: line after a scenario', item['reason'])

    def test_malformed_line_invalidates_an_undeclared_block_too(self):
        self.invalid('Accept-risk: nonsense', verify=False, reason='date must be a valid YYYY-MM-DD')

    def test_valid_line_without_verify_stays_undeclared(self):
        self.capability(risk_capability('Accept-risk: 2999-12-31 by human:x - r', verify=False))
        self.assertEqual(self.status('CALC-R1')['status'], 'UNDECLARED')


class RiskSemanticsTests(AttestedCase):  # R7
    LINE = 'Accept-risk: {until} by human:enramosjr - tracked in the backlog'

    def stale(self, until):
        self.capability(risk_capability(self.LINE.format(until=until)))
        self.task()
        self.lc('assure', '--run')
        self.write('src/calc.py', f'ok, edited for {until}\n')

    def test_future_date_is_active_and_status_unchanged(self):
        self.stale('2999-12-31')
        item = self.status('CALC-R1')
        self.assertEqual(item['status'], 'STALE')
        self.assertEqual(item['risk_acceptance'], {'basis': 'declared', 'until': '2999-12-31', 'by': 'human:enramosjr',
                                                   'reason': 'tracked in the backlog', 'state': 'active'})

    def test_past_date_is_expired_and_status_unchanged(self):
        self.stale('2000-01-01')
        item = self.status('CALC-R1')
        self.assertEqual((item['status'], item['risk_acceptance']['state']), ('STALE', 'expired'))
        self.assertEqual(self.report()[1], 1)

    def test_text_line_is_labeled_a_claim_and_keeps_the_status(self):
        self.stale('2999-12-31')
        lines = self.lc('assure', code=None).stdout.splitlines()
        line = lines[next(i for i, ln in enumerate(lines) if ln.startswith('STALE')) + 1]
        self.assertEqual(line, '    risk acceptance (declared, not verified): active until 2999-12-31, claimed by '
                               'human:enramosjr - tracked in the backlog; status still STALE')
        self.stale('2000-01-01')
        self.assertIn('    risk acceptance (declared, not verified): expired on 2000-01-01, claimed by',
                      self.lc('assure', code=None).stdout)

    def test_failed_and_unverified_also_show_it(self):
        self.capability(risk_capability(self.LINE.format(until='2999-12-31')))
        self.assertEqual(self.status('CALC-R1')['status'], 'UNVERIFIED')
        self.assertEqual(self.status('CALC-R1')['risk_acceptance']['state'], 'active')
        self.write('src/calc.py', 'broken\n')
        self.task()
        self.lc('assure', '--run', code=1)
        item = self.status('CALC-R1')
        self.assertEqual((item['status'], item['risk_acceptance']['until']), ('FAILED', '2999-12-31'))

    def test_ignored_on_verified_and_manual(self):
        self.capability(risk_capability(self.LINE.format(until='2999-12-31'))
                        + '- CALC-R2: Looks MUST be right.\n  - Verify: manual - review\n  - Accept-risk: 2999-12-31 by human:x - r\n')
        self.task()
        self.lc('assure', '--run')
        data, _ = self.report()
        statuses = {r['id']: r['status'] for r in data['requirements']}
        self.assertEqual(statuses, {'CALC-R1': 'VERIFIED', 'CALC-R2': 'MANUAL'})
        self.assertFalse(any('risk_acceptance' in r for r in data['requirements']))

    def test_boundary_day_is_active_the_day_after_expired(self):
        import assurance
        self.capability(risk_capability(self.LINE.format(until='2999-12-31')))
        obligations, _ = assurance.requirements(self.root)
        for today, state in ((date(2999, 12, 30), 'active'), (date(2999, 12, 31), 'active'), (date(3000, 1, 1), 'expired')):
            results = [assurance.result(o, 'STALE', 'x') for o in obligations]
            assurance.annotate(self.root, self.root / RECORDS, None, obligations, results, today=today)
            self.assertEqual(results[0]['risk_acceptance']['state'], state, today)


class ExitCodeTests(AttestedCase):  # R8
    def codes(self, *flags):
        return [self.lc('assure', *flags, code=None).returncode, self.report(*flags)[1]]

    def test_attestation_and_notes_never_change_exit_or_summary(self):
        self.manual_capability()
        before = {flag: (self.codes(*flag), self.report(*flag)[0]['summary']) for flag in ((), ('--strict',))}
        self.reviewed(cited=f'- CALC-R2@{"0" * 12} stale pin.')  # a note, no attestation
        self.assertIn('notes', self.report()[0])
        for step in ('note', 'attested'):
            if step == 'attested':
                self.reviewed(name='good')
                self.assertIn('attested', self.report()[0]['requirements'][0])
            for flag in ((), ('--strict',)):
                self.assertEqual((self.codes(*flag), self.report(*flag)[0]['summary']), before[flag], (step, flag))
        self.assertEqual(before[()][0], [0, 0])

    def test_risk_acceptance_never_changes_exit_or_summary(self):
        self.capability(risk_capability())
        plain = (self.codes(), self.report()[0]['summary'])
        for until in ('2999-12-31', '2000-01-01'):
            self.capability(risk_capability(f'Accept-risk: {until} by human:x - r'))
            self.assertEqual((self.codes(), self.report()[0]['summary']), plain, until)
        self.assertEqual(plain[0], [1, 1])

    def test_changed_lists_attestation_and_notes_only_for_listed_requirements(self):
        self.capability(MANUAL_REQ + '- CALC-R3: Docs MUST read well.\n  - Verify: manual - docs review\n  - Inputs: `docs/**`\n'
                        '  - Scenario read: it reads well.\n')
        self.commit('two manual requirements')
        self.reviewed(cited=f'- CALC-R2 ok.\n- CALC-R3 ok.\n- CALC-R3@{"0" * 12} stale pin.')
        data, code = self.report('--changed', '--base', 'HEAD')
        self.assertEqual([r['id'] for r in data['requirements']], ['CALC-R2'])
        self.assertIn('attested', data['requirements'][0])
        self.assertNotIn('notes', data)
        self.assertEqual(code, 0)
        self.write('docs/page.md', 'changed\n')
        data, _ = self.report('--changed', '--base', 'HEAD')
        self.assertEqual([r['id'] for r in data['requirements']], ['CALC-R2', 'CALC-R3'])
        self.assertIn('attested', data['requirements'][1])  # the unpinned mention is honored


class CompatibilityTests(GoldenCase):  # R9
    def snapshot(self):
        return {str(path): path.read_bytes() for path in self.root.rglob('*')
                if path.is_file() and '.git' not in path.relative_to(self.root).parts[:1]}

    def test_input_free_output_is_byte_identical_to_increment_1(self):
        self.build_golden()
        self.assertEqual(self.golden(), GOLDEN)

    def test_schema_version_and_no_conditional_keys_without_input(self):
        self.build_golden()
        data, _ = self.report()
        self.assertEqual(data['schema_version'], 1)
        self.assertEqual(set(data), {'schema_version', 'requirements', 'diagnostics', 'summary'})
        for item in data['requirements']:
            self.assertEqual(set(item), {'id', 'capability', 'status', 'basis', 'evidence', 'reason'})

    def test_report_is_read_only_with_attestation_present(self):
        self.build_golden()
        self.reviewed(name='manual', cited='- CALC-R2 looked right.')
        self.assertIn('attested', self.status('CALC-R2'))
        before = self.snapshot()
        self.lc('assure', code=None)
        self.lc('assure', '--json', code=None)
        self.assertEqual(self.snapshot(), before)

    def test_okf_validate_stays_clean_with_attestation_and_accept_risk(self):
        self.capability(risk_capability('Accept-risk: 2999-12-31 by human:x - known gap') + MANUAL_REQ)
        self.commit('risk')
        self.reviewed()
        self.assertIn('attested', self.status('CALC-R2'))
        self.cli('okf.py', 'validate')
