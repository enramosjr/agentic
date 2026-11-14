"""R4: complete exact evidence, never candidate PASS text."""
import copy
import unittest
from trusted_ci_fixtures import policy, report, snapshot
import trusted_ci_policy as t


class ProvenanceTests(unittest.TestCase):
    def test_exact_report_and_no_candidate_selected_checks(self):
        p, r = policy(), report()
        t.validate_report(r, p, snapshot())
        for status in ['failed', 'skipped', 'neutral', 'cancelled', 'timed_out', 'PASS']:
            bad = copy.deepcopy(r)
            bad['outcomes'][0]['status'] = status
            with self.subTest(status=status), self.assertRaises(t.Refusal):
                t.validate_report(bad, p, snapshot())
        for outcomes in [[], r['outcomes'][:-1], r['outcomes'] + [r['outcomes'][0]]]:
            with self.assertRaises(t.Refusal):
                t.validate_report(dict(r, outcomes=outcomes), p, snapshot())

    def test_wrong_authority_and_unknown_fields(self):
        for key in snapshot():
            bad = report()
            bad['snapshot'][key] = 'substitution'
            with self.subTest(key=key), self.assertRaises(t.Refusal):
                t.validate_report(bad, policy(), snapshot())
        with self.assertRaises(t.Refusal):
            t.validate_report(dict(report(), approved=True), policy(), snapshot())
