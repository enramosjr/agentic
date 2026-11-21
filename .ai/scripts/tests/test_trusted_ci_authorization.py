"""R4 R5 R6: authenticated host identity, fresh refs and independent approval."""
import base64
import copy
import json
import unittest
import io
import zipfile
import hashlib
from trusted_ci_fixtures import policy, snapshot, report
import trusted_ci_github as g
from trusted_ci_policy import Refusal, digest


class Host:
    def __init__(self):
        self.calls = []
        self.p = policy()
        self.s = snapshot()
        self.pr = dict(number=7, state='open', draft=False, user={'id': 18},
                       head={'sha': self.s['head']}, base={'sha': self.s['base'], 'ref': 'main'})
        self.review = dict(id=1, user={'id': 17}, state='APPROVED',
                           commit_id=self.s['head'], submitted_at='2026-11-07T00:00:00Z')

    def get(self, path):
        self.calls.append(('GET', path))
        if '/pulls/7/reviews' in path:
            return [self.review]
        if path.endswith('/pulls/7'):
            return self.pr
        if '/git/ref/pull/7/merge' in path:
            return {'object': {'sha': self.s['merge']}}
        if '/git/commits/' in path:
            return {'sha': self.s['merge'], 'parents': [{'sha': self.s['base']}, {'sha': self.s['head']}]}
        if '/contents/' in path:
            marker = dict(epoch=self.p['epoch'], policy_digest=digest(self.p))
            return dict(encoding='base64', content=base64.b64encode(json.dumps(marker).encode()).decode())
        if '/branches/' in path:
            return dict(commit={'sha': self.s['base']})
        if path == '/repos/owner/project':
            return dict(id=123, default_branch='main')
        if path == '/repos/owner/authority':
            return dict(id=456)
        if '/installation' in path:
            return dict(app_id=42, permissions={'checks': 'write', 'contents': 'read', 'pull_requests': 'read'})
        raise AssertionError(path)

    def pages(self, path):
        return self.get(path)

    def post(self, path, data):
        self.calls.append(('POST', path, data))
        return dict(id=321, **data)


class AuthorizationTests(unittest.TestCase):
    def test_exact_merge_binding_and_independent_review(self):
        h = Host()
        self.assertEqual(g.current_snapshot(h, policy(), 7, 99, 1), snapshot())
        g.independent_approval(h, policy(), h.pr)
        for state, user, commit in [('DISMISSED', 17, '4' * 40), ('APPROVED', 18, '4' * 40),
                                     ('APPROVED', 17, '0' * 40)]:
            h.review.update(state=state, user={'id': user}, commit_id=commit)
            with self.assertRaises(Refusal):
                g.independent_approval(h, policy(), h.pr)

    def test_latest_request_changes_cannot_be_overruled(self):
        h = Host()
        approved = h.review
        denied = dict(approved, id=2, state='CHANGES_REQUESTED', submitted_at='2026-11-07T01:00:00Z')
        h.pages = lambda path: [denied, approved]
        with self.assertRaises(Refusal):
            g.independent_approval(h, policy(), h.pr)

    def test_stale_base_or_wrong_merge_parents_refuses(self):
        h = Host()
        h.pr['base']['sha'] = '0' * 40
        with self.assertRaises(Refusal):
            g.current_snapshot(h, policy(), 7, 99, 1)

    def test_real_http_publisher_binds_artifact_execution_and_merge(self):
        from trusted_ci_http import FixtureServer
        h = Host()
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, 'w') as z:
            z.writestr('report.json', json.dumps(report()))
        raw = archive.getvalue()
        original = h.get
        def get(path):
            if path.endswith('/actions/runs/99'):
                return dict(repository={'id': 456}, head_sha='1' * 40,
                            path=policy()['workflow'] + '@main', head_branch='main',
                            workflow_id=22, run_attempt=1, event='schedule')
            if path.endswith('/actions/workflows/22'):
                return dict(id=22, path=policy()['workflow'])
            if path.endswith('/attempts/1/jobs'):
                return dict(total_count=1, jobs=[dict(name='verify (7)', conclusion='success')])
            if path.endswith('/artifacts'):
                return dict(total_count=1, artifacts=[dict(id=77, name='report-7-1', expired=False,
                            workflow_run=dict(id=99, head_sha='1' * 40),
                            digest='sha256:' + hashlib.sha256(raw).hexdigest())])
            if path.endswith('/artifacts/77/zip'):
                return raw
            return original(path)
        h.get = get
        def post(path, data):
            h.calls.append(('POST', path, data))
            return dict(id=321, app={'id': 42}, **data)
        h.post = post
        with FixtureServer(h) as transport:
            api = g.GitHub('fixture-read-token', opener=transport)
            g.publish(api, api, policy(), 7, 99, 1)
        posts = [c for c in h.calls if c[0] == 'POST']
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0][2]['head_sha'], snapshot()['merge'])
        self.assertNotEqual(posts[0][2]['head_sha'], snapshot()['head'])
        self.assertEqual(posts[0][2]['external_id'], digest(report()))
