"""V2 discovery must not depend on a candidate-editable policy marker."""
import unittest
from test_authority_protocol import deployment
import authority_github as a
from trusted_ci_fixtures import snapshot
from trusted_ci_policy import Refusal


class Host:
    def __init__(self):
        self.parents = ['5' * 40, '4' * 40]
        self.paths = []

    def get(self, path):
        self.paths.append(path)
        values = {
            '/repos/owner/project': {'id': 123},
            '/repos/owner/authority': {'id': 456},
            '/repos/owner/project/pulls/7': {'state': 'open', 'draft': False,
                'head': {'sha': '4' * 40}, 'base': {'sha': '5' * 40, 'ref': 'main'}},
            '/repos/owner/project/branches/main': {'commit': {'sha': '5' * 40}},
            '/repos/owner/project/git/ref/pull/7/merge': {'object': {'sha': '6' * 40}},
            '/repos/owner/project/git/commits/' + '6' * 40: {'parents': [{'sha': x} for x in self.parents]},
        }
        return values[path]


class Discovery(unittest.TestCase):
    def test_remote_policy_removes_marker_bootstrap_cycle(self):
        host = Host()
        self.assertEqual(a.current_snapshot(host, deployment(), 7, 99, 1), snapshot())
        self.assertFalse(any('contents' in path for path in host.paths))

    def test_wrong_synthetic_merge_parents_are_rejected(self):
        host = Host()
        host.parents.reverse()
        with self.assertRaises(Refusal):
            a.current_snapshot(host, deployment(), 7, 99, 1)

    def test_cross_repository_read_requests_are_rejected(self):
        class Reader:
            def get(self, path):
                return path
        split = a.Readers(Reader(), Reader(), deployment())
        self.assertEqual(split.get('/repos/owner/authority/actions/runs/99'),
                         '/repos/owner/authority/actions/runs/99')
        for path in ('/repos/owner/other', '/repos/owner/project/../other', '/repos/owner/project-evil'):
            with self.assertRaises(Refusal):
                split.get(path)

    def test_control_identity_reads_are_single_login_gets_only(self):
        class Reader:
            def get(self,path): return path
        split=a.Readers(Reader(),Reader(),deployment())
        for path in ('/users/maintainer','/users/agentic-coding%5Bbot%5D'):
            self.assertEqual(split.get(path),path)
        for path in ('/users/maintainer/repos','/users/../repos/owner/other','/users/maintainer?x=y',
                     'https://api.github.com/users/maintainer','/users/maintainer%2Frepos'):
            with self.assertRaises(Refusal): split.get(path)


if __name__ == '__main__':
    unittest.main()
