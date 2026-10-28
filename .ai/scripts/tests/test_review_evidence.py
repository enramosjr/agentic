"""review_evidence.py mirrors the review semantics of lifecycle.py without importing it (increment 4, R1-R3)."""
import inspect
from pathlib import Path
import re
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import disk_tmp  # noqa: F401,E402
import lifecycle  # noqa: E402
import review_evidence  # noqa: E402

FRONT = '---\ntype: Review\nstamp: one\n---\n'
CORPUS = {
    'plain.md': '# Review\n\n## Verdict\n\nApproved\n\n## Validation Reviewed\n\n- CALC-R2 ok\n',
    'frontmatter.md': FRONT + '\n# Review\n\n## Verdict\n\nApproved\n\n## Validation Reviewed\n\n- CALC-R2 ok\n',
    'frontmatter-edit.md': FRONT.replace('one', 'two') + '\n# Review\n\n## Verdict\n\nApproved\n\n## Validation Reviewed\n\n- CALC-R2 ok\n',
    'crlf.md': '# Review\r\n\r\n## Verdict\r\n\r\nApproved\r\n\r\n## Validation Reviewed\r\n\r\n- CALC-R2 ok\r\n',
    'casing.md': '# Review\n\n## verdict\n\napproved with notes\n\n## VALIDATION REVIEWED\n\n- CALC-R2 ok\n',
    'verdicts.md': '# Review\n\n## Verdicts\n\nChanges requested\n\n## Verdict\n\nApproved\n',
    'blank-lines.md': '# Review\n\n## Verdict\n\n\n\n   Approved   \n',
    'no-verdict.md': '# Review\n\n## Validation Reviewed\n\n- CALC-R2 ok\n',
    'empty-verdict.md': '# Review\n\n## Verdict\n',
    'heading-prefix.md': '# Review\n\n## Validation Reviewed (manual)\n\n- CALC-R2 ok\n',
    'trailing-space.md': '# Review\n\n## Verdict   \n\nApproved\n\n',
    'notes.txt': 'not markdown\n## Verdict\nApproved\n',
}
CITATIONS = (
    ('- CALC-R2 ok', True), ('- CALC-R2-x', False), ('- xCALC-R2', False), ('- CALC-R20', False),
    ('- CALC-R2.', True), ('- CALC-R2, then more', True), ('- (CALC-R2)', True), ('- CALC-R2@0123456789ab', True),
    ('- CALC-R2@zz', True), ('- calc-r2', False), ('- NOCALC-R2', False), ('- CALC-R2_', False), ('- CALC-R2', True),
)


class ParityChecks(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.dir = Path(temp.name)

    def written(self, name, text):
        path = self.dir / name
        path.write_bytes(text.encode())
        return path

    def test_hash_verdict_and_section_match_lifecycle(self):
        for name, text in CORPUS.items():
            path = self.written(name, text)
            self.assertEqual(review_evidence.ref_hash(path), lifecycle.ref_hash(path), name)
            self.assertEqual(review_evidence.load_review(path)[0], lifecycle.ref_hash(path), name)
            self.assertEqual(review_evidence.read_verdict(path), lifecycle.read_verdict(path), name)
            self.assertEqual(review_evidence.verdict(path.read_text()), lifecycle.read_verdict(path), name)
            expected = lifecycle.find_section(lifecycle.sections(text), 'validation reviewed')
            self.assertEqual(review_evidence.reviewed_section(path.read_text()), '\n'.join(expected or []), name)

    def test_frontmatter_only_edit_keeps_the_hash(self):
        one = self.written('one.md', CORPUS['frontmatter.md'])
        two = self.written('two.md', CORPUS['frontmatter-edit.md'])
        self.assertEqual(review_evidence.ref_hash(one), review_evidence.ref_hash(two))

    def test_body_edit_changes_the_hash(self):
        one = self.written('one.md', CORPUS['plain.md'])
        two = self.written('two.md', CORPUS['plain.md'] + 'More.\n')
        self.assertNotEqual(review_evidence.ref_hash(one), review_evidence.ref_hash(two))

    def test_approved_matches_the_stage_rule(self):
        for name, text in CORPUS.items():
            path = self.written(name, text)
            self.assertEqual(review_evidence.approved(path.read_text()),
                             lifecycle.read_verdict(path).lower().startswith('approved'), name)

    def test_citations_follow_the_converge_boundary_rule(self):
        for line, cited in CITATIONS:
            text = f'## Validation Reviewed\n\n{line}\n'
            regex = re.search(r'(?<![\w-])CALC\-R2(?![\w-])', '\n'.join(lifecycle.find_section(lifecycle.sections(text), 'validation reviewed') or []))
            self.assertEqual(bool(review_evidence.citations(review_evidence.reviewed_section(text), 'CALC-R2')), bool(regex), line)
            self.assertEqual(bool(regex), cited, line)

    def test_pin_classification(self):
        found = review_evidence.citations(
            'CALC-R2 and CALC-R2@0123456789AB. and CALC-R2@zz and CALC-R2@0123456789a and CALC-R2@0123456789abcdef0', 'CALC-R2')
        self.assertEqual(found, [('plain', ''), ('pin', '0123456789AB'), ('malformed', '@zz'),
                                 ('malformed', '@0123456789a'), ('pin', '0123456789abcdef0')])

    def test_converge_still_uses_the_mirrored_regex(self):
        source = inspect.getsource(lifecycle.converge_problem)
        self.assertIn('rf"(?<![\\w-]){re.escape(rid)}(?![\\w-])"', source)
        self.assertIn('"validation reviewed"', source)
        self.assertEqual(review_evidence.BOUNDARY, r'(?<![\w-]){}(?![\w-])')


class ImportGraphChecks(unittest.TestCase):
    def test_no_import_cycle(self):
        for name in ('assurance.py', 'review_evidence.py'):
            text = (SCRIPTS / name).read_text()
            self.assertIsNone(re.search(r'^\s*(import lifecycle|from lifecycle import)', text, re.M), name)


if __name__ == '__main__':
    unittest.main()
