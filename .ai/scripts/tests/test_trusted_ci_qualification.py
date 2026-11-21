"""R9: the driver needs real explicit denials and a changed positive ref."""
import unittest
import base64
import hashlib
import io
import json
import zipfile
from urllib.parse import urlparse, parse_qs, unquote
from trusted_ci_fixtures import policy, report, snapshot
from trusted_ci_policy import Refusal
from trusted_ci_github import HostRefusal, denial_category
import trusted_ci_qualification as q


class Host:
    def __init__(self):
        self.base = '5' * 40
        self.writes = []
        self.refuse = True

    def get(self, path):
        if path == '/repos/owner/project':
            return dict(id=123)
        if path == '/repos/owner/authority':
            return dict(id=456)
        if path.endswith('/git/ref/heads/main'):
            return dict(object=dict(sha=self.base))
        raise AssertionError(path)


class QualificationTests(unittest.TestCase):
    def test_validation_or_revision_race_is_not_a_policy_denial(self):
        self.assertEqual(denial_category(409, b'{"message":"Head branch was modified"}'), 'unknown')
        self.assertEqual(denial_category(422, b'{"message":"Validation Failed"}'), 'unknown')
        self.assertEqual(denial_category(403, b'{"message":"Resource not accessible by integration"}'), 'unknown')
        self.assertEqual(denial_category(405, b'{"message":"Pull Request is not mergeable"}'), 'unknown')
        self.assertEqual(denial_category(422, b'{"message":"Repository rule violations found"}'), 'unknown')
        self.assertEqual(denial_category(405, json.dumps({'message': 'Required status check "AGENTIC trusted acceptance" is expected.'}).encode()), 'required_check')
    def test_negative_proof_needs_actual_failed_criterion_and_exact_snapshot(self):
        p, r, s = policy(), report(), snapshot()
        with self.assertRaises(Refusal):
            q.check_negative(r, p, s, p['checks'][0])
        r['outcomes'][0]['status'] = 'failure'
        q.check_negative(r, p, s, p['checks'][0])
        for status in ['skipped', 'not_run', 'unavailable']:
            r['outcomes'][0]['status'] = status
            with self.assertRaises(Refusal):
                q.check_negative(r, p, s, p['checks'][0])
        r['outcomes'][0]['status'] = 'failure'
        r['snapshot']['head'] = '0' * 40
        with self.assertRaises(Refusal):
            q.check_negative(r, p, s, p['checks'][0])

    def test_incomplete_fixture_inventory_cannot_produce_receipt(self):
        h = Host()
        class Actor:
            def __init__(self, actor):
                self.actor = actor
            def get(self, path):
                return {'id': self.actor}
        with self.assertRaisesRegex(Refusal, 'complete ordered case inventory'):
            q.probe(h, Actor(18), Actor(17), policy(),
                    dict(schema_version=1, qualification_repository_id=123, cases=[]), 'controls')
        self.assertEqual(h.writes, [])

    def test_wrong_target_refuses_before_any_host_mutation(self):
        with self.assertRaises(Refusal):
            q.probe(Host(), None, None, policy(),
                    dict(schema_version=1, qualification_repository_id=456, cases=[]), 'controls')

    def test_complete_driver_checks_negative_execution_and_final_host_refs(self):
        host = PreparedHost()
        result = q.probe(host, Actor(host, 18), Actor(host, 17), policy(), host.manifest, 'controls')
        self.assertEqual([c['name'] for c in result['cases']], list(q.CASES))
        self.assertEqual(len(host.writes), 10)
        self.assertTrue(all(c['before'] == c['after'] for c in result['cases'][:-1]))
        self.assertNotEqual(result['cases'][-1]['before'], result['cases'][-1]['after'])

    def test_generic_http_refusal_does_not_produce_qualification(self):
        host = PreparedHost()
        host.denial = 'unknown'
        with self.assertRaisesRegex(Refusal, 'explicitly deny'):
            q.probe(host, Actor(host, 18), Actor(host, 17), policy(), host.manifest, 'controls')


class Actor:
    def __init__(self, host, actor):
        self.host, self.actor = host, actor

    def get(self, path):
        assert path == '/user'
        return dict(id=self.actor)

    def fetch(self, path, method, data):
        self.host.writes.append((self.actor, path, method, data))
        if method == 'PATCH':
            raise HostRefusal(422, 'protected_update')
        case = self.host.cases[int(path.split('/pulls/')[1].split('/')[0])]
        if case['name'] != 'positive':
            category = 'required_review' if case['name'] == 'missing-approval' else self.host.denial
            raise HostRefusal(405, category, self.host.p['check_name'])
        self.host.base = self.host.merge(case['pr'])
        return dict(merged=True)


class PreparedHost:
    """Deterministic host contract fixture, explicitly not hosted enforcement evidence."""
    def __init__(self):
        self.p, self.base, self.writes, self.denial = policy(), '5' * 40, [], 'required_check'
        self.cases, self.archives = {}, {}
        for n, name in enumerate(q.CASES, 1):
            paths = ['.ai/scripts/lifecycle.py']
            if name == 'replaced-checks':
                paths.append('.ai/scripts/tests/test_lifecycle.py')
            if name == 'forged-records':
                paths.append('knowledge/history/lifecycle/forged.json')
            raw = ('mutated-' + name).encode()
            case = dict(name=name, pr=n, head=self.head(n), prior_merge=self.prior(n),
                        prior_head=('9' * 40 if name == 'new-head' else self.head(n)),
                        prior_base=('5' * 40 if name == 'new-head' else '8' * 40),
                        negative_run_id=1000 + n, negative_attempt=1,
                        expected_failure=self.p['checks'][0],
                        mutations=[dict(path=path, sha256=hashlib.sha256(raw).hexdigest()) for path in paths])
            self.cases[n] = case
            s = snapshot()
            s.update(pr=n, head=self.head(n), merge=self.merge(n), run_id=1000+n)
            r = dict(schema_version=1, snapshot=s,
                     outcomes=[dict(id=c, status='failure' if i == 0 else 'not_run')
                               for i, c in enumerate(self.p['checks'])])
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, 'w') as z:
                z.writestr('report.json', json.dumps(r))
            self.archives[n] = buffer.getvalue()
        self.manifest = dict(schema_version=1, qualification_repository_id=123, cases=list(self.cases.values()))

    @staticmethod
    def head(n):
        return format(n + 100, '040x')

    @staticmethod
    def merge(n):
        return format(n + 200, '040x')

    @staticmethod
    def prior(n):
        return format(n + 300, '040x')

    def get(self, path):
        parsed = urlparse(path)
        route, query = parsed.path, parse_qs(parsed.query)
        if route == '/repos/owner/project':
            return dict(id=123)
        if route == '/repos/owner/authority':
            return dict(id=456)
        if '/branches/main' in route:
            return dict(commit={'sha': self.base})
        if '/git/ref/heads/main' in route:
            return dict(object={'sha': self.base})
        if '/pulls/' in route:
            n = int(route.split('/pulls/')[1].split('/')[0])
            return dict(number=n, state='open', draft=False, mergeable=True, user={'id': 18},
                        head={'sha': self.head(n)}, base={'sha': self.base, 'ref': 'main'})
        if '/git/ref/pull/' in route:
            return dict(object={'sha': self.merge(int(route.split('/pull/')[1].split('/')[0]))})
        if '/git/commits/' in route:
            value = route.rsplit('/', 1)[1]
            n = int(value, 16)
            if n >= 300:
                c = self.cases[n - 300]
                return dict(parents=[dict(sha=c['prior_base']), dict(sha=c['prior_head'])])
            return dict(parents=[dict(sha=self.base), dict(sha=self.head(n-200))])
        if '/contents/' in route:
            name = unquote(route.split('/contents/')[1])
            ref = query['ref'][0]
            if name == '.agentic-trusted-ci.json':
                marker = dict(epoch=self.p['epoch'], policy_digest=q.digest(self.p))
                if ref == '8' * 40:
                    marker = dict(epoch='v0', policy_digest='0' * 64)
                raw = json.dumps(marker).encode()
            elif ref == self.base:
                raw = b'baseline'
            else:
                n = int(ref, 16)-100
                raw = ('mutated-' + self.cases[n]['name']).encode()
            return dict(encoding='base64', content=base64.b64encode(raw).decode())
        if '/actions/runs/' in route:
            return dict(repository={'id': 456}, head_sha='1' * 40, workflow_id=22,
                        path=self.p['workflow'] + '@main', head_branch='main', run_attempt=1, event='workflow_dispatch')
        if '/actions/workflows/' in route:
            return dict(id=22, path=self.p['workflow'])
        raise AssertionError(path)

    def pages(self, path, collection=None):
        if '/reviews' in path:
            n = int(path.split('/pulls/')[1].split('/')[0])
            return [] if self.cases[n]['name'] == 'missing-approval' else [dict(
                id=100+n, user={'id': 17}, state='APPROVED', commit_id=self.head(n))]
        if '/check-runs' in path:
            value = int(path.split('/commits/')[1].split('/')[0], 16)
            prior = value >= 300
            n = value-300 if prior else value-200
            case = self.cases[n]
            if prior or case['name'] in ('positive', 'direct-push', 'missing-approval', 'spoofed-source'):
                return [dict(name=self.p['check_name'], app={'id': 99 if case['name'] == 'spoofed-source' else 42},
                             status='completed', conclusion='success')]
            return []
        if '/rules/branches/' in path:
            return []
        if '/attempts/1/jobs' in path:
            n = int(path.split('/runs/')[1].split('/')[0])-1000
            return [dict(name='verify ('+str(n)+')', conclusion='failure')]
        if path.endswith('/artifacts'):
            run_id = int(path.split('/runs/')[1].split('/')[0])
            n = run_id-1000
            raw = self.archives[n]
            return [dict(id=n, name='report-'+str(n)+'-1', expired=False,
                         workflow_run=dict(id=run_id, head_sha='1'*40),
                         digest='sha256:'+hashlib.sha256(raw).hexdigest())]
        raise AssertionError(path)

    def fetch(self, path, **kwargs):
        return self.archives[int(path.split('/artifacts/')[1].split('/')[0])]
