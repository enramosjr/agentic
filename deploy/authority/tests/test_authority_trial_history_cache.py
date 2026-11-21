"""A guard may skip re-deriving verified immutable terminals, never rereading what can change."""
import backend_test_support
import copy
import unittest
from contextlib import ExitStack
from unittest.mock import DEFAULT, MagicMock, patch

from trusted_ci_policy import Refusal
from registry import trial_reference
import test_authority_trial_history_walk as walk
import trial_case
import trial_host_case

STALE = ('bad_acceptance_terminal', 'replaced_checks_terminal', 'forged_records_terminal', 'spoofed_source_terminal',
         'new_head_terminal', 'new_base_terminal', 'policy_transition_terminal')
SOURCES = ('_bad_source', '_replaced_source', '_forged_source', '_spoof_source', '_new_head_source', '_new_base_source',
           '_policy_transition_source')
NAME = 'trial-case-terminal-' + 'a'*32 + '-1'


class Authority:
    """Authority artifact inventory; the readback is the real one."""
    def __init__(self):
        self.artifacts = [dict(id=5, name=NAME, expired=False, digest='sha256:'+'a'*64,
                               workflow_run=dict(id=7, repository_id=2, head_repository_id=2, head_sha='w'*40))]
        self.listings = 0

    def get(self, path): raise AssertionError(path)
    def fetch(self, path, **kwargs): raise AssertionError(path)

    def pages(self, path, collection=None):
        self.listings += 1
        return copy.deepcopy(self.artifacts)


class HistoryCache(unittest.TestCase):
    fixture = walk.HistoryWalkContracts.fixture

    record_expires = certificate_expires = trial_expires = terminal_expires = 1000

    def setUp(self):
        self.original, self.record, self.history, self.documents, self.refs, self.visits = self.fixture()
        self.authority = Authority()
        self.clock = [100]
        document = dict(before=dict(deployment=dict(expires=self.terminal_expires, policy=dict(authority_repository='o/authority',
                        authority_repository_id=2, workflow_sha='w'*40))))
        reference = dict(run_id=7, role='trial-case-terminal', key='a'*32, attempt=1, artifact_id=5,
                         artifact_digest='sha256:'+'a'*64, job_id=9)
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        enter = self.stack.enter_context
        enter(patch.object(__import__('trial_mutation'), 'authenticate', return_value=(dict(preview=dict(baseline={})), None)))
        enter(patch.object(__import__('trial_mutation'), 'validate', return_value={}))
        enter(patch.object(__import__('provenance'), 'authenticated_document', return_value=dict(document=document)))
        # The host-side recovery envelope read is modeled elsewhere; the artifact readback below is the real one.
        enter(patch.object(trial_host_case, '_host_terminal'))
        self.readers = {n: enter(patch.object(trial_host_case, n, return_value=dict(_references=[reference]))) for n in STALE}
        self.sources = {n: enter(patch.object(trial_host_case, n)) for n in SOURCES}
        self.source = object(); self.verified = {}

    def guard(self, verified=True, clock=None):
        trial_case.history_guard(self.original, self.record, self.history, clock or (lambda: self.clock[0]), self.authority,
                                 self.source, self.verified if verified else None)

    def derivations(self):
        return sum(r.call_count for r in self.readers.values())

    def test_second_guard_skips_derivation_but_rereads_every_dependency(self):
        self.guard()
        self.assertEqual(self.derivations(), len(STALE))
        first_visits, first_listings = len(self.visits), self.authority.listings
        self.assertEqual(len(self.verified), len(STALE))
        for source in self.sources.values(): source.reset_mock()
        self.guard()
        self.assertEqual(self.derivations(), len(STALE), 'verified immutable terminals are not re-derived')
        self.assertEqual(len(self.visits)-first_visits, first_visits, 'every case blob is reread')
        self.assertEqual(self.authority.listings-first_listings, first_listings, 'every retained artifact is relisted')
        self.assertTrue(all(source.call_count == 1 for source in self.sources.values()), 'live source facts are reread')

    def test_no_table_means_full_derivation_every_guard(self):
        self.guard(verified=False); self.guard(verified=False)
        self.assertEqual(self.derivations(), 2*len(STALE))

    def test_replaced_artifact_with_same_id_and_other_digest_fails_a_later_guard(self):
        self.guard()
        self.authority.artifacts[0]['digest'] = 'sha256:'+'b'*64
        with self.assertRaisesRegex(Refusal, 'revoked or replaced'): self.guard()
        self.assertEqual(self.derivations(), len(STALE), 'the later guard failed on the live recheck, not a derivation')

    def test_deleted_artifact_fails_a_later_guard(self):
        self.guard()
        self.authority.artifacts[:] = []
        with self.assertRaisesRegex(Refusal, 'missing or ambiguous'): self.guard()

    def test_expired_artifact_fails_a_later_guard(self):
        self.guard()
        self.authority.artifacts[0]['expired'] = True
        with self.assertRaisesRegex(Refusal, 'revoked or replaced'): self.guard()

    def test_moved_pointer_fails_a_later_guard(self):
        self.guard()
        prior = self.documents[f'{6:040x}']
        self.refs[trial_reference(prior)] = 'f'*40
        with self.assertRaisesRegex(Refusal, 'reference moved'): self.guard()

    def test_each_expiry_bound_is_rechecked_on_every_guard(self):
        for bound in ('record', 'certificate', 'trial', 'terminal'):
            with self.subTest(bound=bound):
                self.stack.close()
                setattr(self, bound + '_expires', 500)
                try: self.setUp()
                finally: setattr(self, bound + '_expires', 1000)
                self.guard()
                self.guard(clock=lambda: 499)
                with self.assertRaisesRegex(Refusal, 'expired'): self.guard(clock=lambda: 500)
                self.assertEqual(self.derivations(), len(STALE), 'the later guards were served from the table')

    def test_changed_case_blob_is_not_served_from_the_table(self):
        self.guard()
        before = self.derivations()
        self.documents[f'{10:040x}']['note'] = 'changed after verification'
        self.refs[trial_reference(self.documents[f'{10:040x}'])] = f'{10:040x}'
        self.guard()
        self.assertGreater(self.derivations(), before, 'a different blob is a different key and is derived again')


if __name__ == '__main__': unittest.main()
