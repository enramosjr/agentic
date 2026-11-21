"""Real review/preparation/broker validators over fake GitHub, never hosted proof."""
import backend_test_support
import copy
import json
import unittest
from unittest.mock import patch

import service
from trusted_ci_github import independent_approval
from trusted_ci_policy import Refusal
from test_authority_producer_composition import Composition
from test_authority_broker_evidence import execute, fixture


def preparation():
    f = Composition()
    f.clock[0] = 1090
    f.binding['fence'].update(pending=None, sequence=0)
    f.acquisitions = []
    def acquire(head, configuration, operation):
        f.acquisitions.append(copy.deepcopy(operation))
        f.binding['fence']['pending'] = operation
        f.binding['fence']['sequence'] += 1
        return copy.deepcopy(f.binding)
    f.registry.acquire_operation = acquire
    pages = f.api.pages
    f.api.pages = lambda path, collection=None: (f.api.artifacts if path.endswith('/actions/artifacts') else
        [a for a in f.api.artifacts if a['workflow_run']['id'] == 99] if path.endswith('/runs/99/artifacts') else pages(path, collection))
    return f


def prepare(f, request=None):
    environment = f.job('prepare', 'prepare', 851)
    environment['AGENTIC_ADMIN_PRIVATE_KEY'] = 'SYNTHETIC-admin'
    with patch.object(service, 'context', side_effect=lambda *a:(f.api, f.registry, copy.deepcopy(f.binding), f.identities)), \
         patch.object(service, 'Registry', return_value=f.registry):
        return service._prepare(environment, request or dict(pr=f.snapshot['pr']), clock=lambda:f.clock[0],
            app_factory=lambda app, pem:f.roots['admin'], token_factory=f.token_api)


class HumanReviewContracts(unittest.TestCase):
    def test_preparation_refuses_missing_stale_dismissed_coding_bot_and_author_reviews_before_fencing(self):
        for defect in ('missing', 'stale', 'dismissed', 'coding', 'bot', 'author', 'changes', 'duplicate'):
            f = preparation()
            review = f.source.reviews[0]
            if defect == 'missing': f.source.reviews = []
            if defect == 'stale': review['commit_id'] = '0' * 40
            if defect == 'dismissed': review['state'] = 'DISMISSED'
            if defect == 'coding': review['user']['id'] = 18
            if defect == 'bot': review['user']['type'] = 'Bot'
            if defect == 'author': f.source.prs[0]['user']['id'] = 17
            if defect == 'changes': f.source.reviews.append(dict(review, id=401, state='CHANGES_REQUESTED'))
            if defect == 'duplicate': f.source.reviews.append(copy.deepcopy(review))
            before = f.source.current_base
            with self.subTest(defect=defect), self.assertRaisesRegex(Refusal, 'review|approval|human|change request'):
                prepare(f)
            self.assertEqual(f.acquisitions, [])
            self.assertIsNone(f.binding['fence']['pending'])
            self.assertEqual(f.source.current_base, before)
            self.assertEqual(f.source.merges, [])
            for root in f.roots.values(): self.assertEqual(set(root.visible), set(root.revoked))

    def test_review_withdrawn_during_token_acquisition_cannot_acquire_fence(self):
        f = preparation()
        post = f.roots['admin'].post
        def withdraw(path, body):
            result = post(path, body)
            if body.get('permissions') == dict(contents='write', actions='read'):
                f.source.reviews[0]['state'] = 'DISMISSED'
            return result
        f.roots['admin'].post = withdraw
        with self.assertRaisesRegex(Refusal, 'approval|review'):
            prepare(f)
        self.assertEqual(f.acquisitions, [])
        self.assertIsNone(f.binding['fence']['pending'])
        self.assertEqual(set(f.roots['admin'].visible), set(f.roots['admin'].revoked))

    def test_human_review_can_resume_preparation_once_and_is_not_a_merge_authorization(self):
        f = preparation()
        reviews = copy.deepcopy(f.source.reviews)
        f.source.reviews = []
        with self.assertRaises(Refusal): prepare(f)
        f.source.reviews = reviews  # Simulate only the external human boundary.
        result = prepare(f)
        self.assertEqual(result['snapshot'], f.snapshot)
        self.assertEqual(result['task'], f.locators['task'])
        self.assertEqual(result['qualification'], f.locators['qualification'])
        with self.assertRaisesRegex(Refusal, 'settled'): prepare(f)
        self.assertEqual(len(f.acquisitions), 1)
        self.assertEqual(f.source.merges, [])
        self.assertNotIn('SYNTHETIC-', json.dumps(result))
        f.source.reviews[0]['state'] = 'DISMISSED'
        with self.assertRaisesRegex(Refusal, 'approval'):
            independent_approval(f.source, f.binding['deployment']['policy'], f.source.prs[0], human=True)

    def test_setup_consent_cannot_be_supplied_as_candidate_review(self):
        f = preparation()
        with self.assertRaises(Refusal):
            prepare(f, dict(pr=f.snapshot['pr'], approval='a' * 64))
        self.assertEqual(f.acquisitions, [])

    def test_interrupted_review_read_can_resume_without_a_fence_or_duplicate_dispatch(self):
        f = preparation()
        pages = f.source.pages
        def interrupted(path, collection=None):
            if path.endswith('/reviews'): raise OSError('synthetic unavailable review API')
            return pages(path, collection)
        f.source.pages = interrupted
        with self.assertRaises(OSError): prepare(f)
        self.assertEqual(f.acquisitions, [])
        self.assertIsNone(f.binding['fence']['pending'])
        f.source.pages = pages
        prepare(f)
        with self.assertRaises(Refusal): prepare(f)
        self.assertEqual(len(f.acquisitions), 1)
        self.assertEqual(f.source.merges, [])
        for root in f.roots.values(): self.assertEqual(set(root.visible), set(root.revoked))

    def test_final_broker_requires_human_identity_and_rejects_ambiguous_review_inventory(self):
        for defect in ('bot', 'missing-type', 'duplicate'):
            f = fixture()
            if defect == 'bot': f[1].reviews[0]['user']['type'] = 'Bot'
            if defect == 'missing-type': f[1].reviews[0]['user'].pop('type')
            if defect == 'duplicate': f[1].reviews.append(copy.deepcopy(f[1].reviews[0]))
            before = f[1].current_base
            with self.subTest(defect=defect), self.assertRaisesRegex(Refusal, 'human|review'):
                execute(f)
            self.assertEqual(f[1].merges, [])
            self.assertEqual(f[1].current_base, before)


if __name__ == '__main__': unittest.main()
