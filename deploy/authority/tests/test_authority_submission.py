"""Source-only submission contracts; no model, GitHub or hosted admission proof."""
import backend_test_support
import copy
import unittest
import io
import tarfile

from test_authority_protocol import deployment
from test_authority_repository import GitHost
from trusted_ci_github import HostRefusal
from trusted_ci_policy import Refusal, digest
import submission


class SubmissionHost(GitHost):
    def __init__(self):
        super().__init__()
        self.refs, self.prs = {}, []
        self.fail_after = None
    def get(self, path):
        if path == '/repos/owner/project':
            return {'id': 123, 'default_branch': 'main'}
        if path == '/users/agentic-coding%5Bbot%5D':
            return {'id': 18, 'type': 'Bot'}
        if '/git/ref/heads/' in path:
            branch = path.split('/git/ref/heads/')[1].replace('%2F', '/')
            if branch not in self.refs:
                raise HostRefusal(404)
            return {'object': {'sha': self.refs[branch]}}
        if '/pulls/' in path:
            return copy.deepcopy(next(pr for pr in self.prs if str(pr['number']) == path.rsplit('/', 1)[1]))
        if '/git/trees/' in path:
            result = super().get(path)
            result['sha'] = path.rsplit('/', 1)[1].split('?')[0]
            return result
        return super().get(path)
    def pages(self, path, collection=None):
        if path == '/installation/repositories':
            return [{'id': 123}]
        if '/pulls?' in path:
            return copy.deepcopy(self.prs)
        raise AssertionError(path)
    def post(self, path, data):
        self.writes.append((path, copy.deepcopy(data)))
        if path.endswith('/git/trees'):
            values = {r['path']: (r['mode'], r['sha']) for r in data['tree']}
            key = digest(values)[:40]
            self.trees[key] = values
            result = {'sha': key}
        elif path.endswith('/git/refs'):
            branch = data['ref'].removeprefix('refs/heads/')
            if branch in self.refs:
                raise HostRefusal(422)
            self.refs[branch] = data['sha']
            result = {'object': {'sha': data['sha']}}
        elif path.endswith('/pulls'):
            head = self.refs[data['head']]
            result = dict(number=len(self.prs) + 1, state='open', merged=False, draft=False,
                body=data['body'], user={'id': 18, 'type': 'Bot'},
                base={'ref': data['base'], 'repo': {'id': 123}},
                head={'ref': data['head'], 'sha': head, 'repo': {'id': 123}})
            self.prs.append(result)
        else:
            self.writes.pop()
            result = super().post(path, data)
            if path.endswith('/git/commits'):
                self.commits[result['sha']].update(author=data['author'], committer=data['committer'])
        if self.fail_after and path.endswith(self.fail_after):
            self.fail_after = None
            raise OSError('synthetic lost submission acknowledgement')
        return copy.deepcopy(result)


def fixture():
    d = deployment()
    d.update(state='active', qualification='a' * 64)
    d['resources'].update(coding_bot_id='18', coding_slug='agentic-coding')
    request = dict(schema_version=2, task_id='1' * 32, configuration_revision='b' * 40,
        deployment_digest=digest(d), base='a' * 40, issued=1000, run_id=99, attempt=1)
    files = {'src/main.py': {'content': b'print("review me")\n', 'executable': False},
             'run.sh': {'content': b'#!/bin/sh\nexit 0\n', 'executable': True}}
    return d, request, files


class SubmissionContracts(unittest.TestCase):
    def test_source_capture_is_exact_and_refuses_corrupt_blobs_or_target_movement(self):
        d, request, _ = fixture()
        for defect in (None, 'blob', 'target'):
            host = SubmissionHost()
            host.refs['main'] = request['base']
            key = host.blob(b'\x00\xffsource bytes')
            host.trees['b' * 40]['payload.bin'] = ('100755', key)
            original = host.get
            fetched = []
            def get(route):
                value = original(route)
                if '/git/blobs/' in route:
                    if defect == 'blob': value['content'] = 'dGFtcGVyZWQ='
                    if defect == 'target': host.refs['main'] = 'c' * 40
                return value
            host.get = get
            def fetch(route, **kwargs):
                self.assertEqual(kwargs, dict(limit=submission.MAX_BYTES * 2))
                fetched.append(route)
                return get(route)
            host.fetch = fetch
            if defect is None:
                exported = submission.read_export(submission.capture_source(host, d, request['base']))
                self.assertEqual(exported['payload.bin'], dict(content=b'\x00\xffsource bytes', executable=True))
                self.assertEqual(exported['README.md']['content'], b'adopter data')
            else:
                with self.subTest(defect=defect), self.assertRaises(Refusal):
                    submission.capture_source(host, d, request['base'])
            self.assertEqual(host.writes, [])
            self.assertTrue(fetched, 'large source blobs used the default one-MiB API ceiling')

    def test_stopped_worker_tar_exports_only_regular_source_bytes_and_modes(self):
        d, request, files = fixture()
        output = io.BytesIO()
        with tarfile.open(fileobj=output, mode='w') as archive:
            for path, item in dict(files, **{'.git/config': {'content': b'hostile git config', 'executable': False}}).items():
                member = tarfile.TarInfo('./' + path)
                member.size, member.mode = len(item['content']), 0o755 if item['executable'] else 0o644
                archive.addfile(member, io.BytesIO(item['content']))
        exported = submission.read_export(output.getvalue())
        self.assertEqual(exported, files)
        result = submission.submit(SubmissionHost(), d, request, exported, 1001)
        self.assertEqual(result['pr'], 1)
        for kind in (tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.CHRTYPE):
            output = io.BytesIO()
            with tarfile.open(fileobj=output, mode='w') as archive:
                member = tarfile.TarInfo('src/escape')
                member.type, member.linkname = kind, '/host/secrets'
                archive.addfile(member)
            with self.subTest(kind=kind), self.assertRaises(Refusal):
                submission.read_export(output.getvalue())

    def test_exact_export_becomes_one_fixed_target_pr_with_correct_modes_and_deletions(self):
        d, request, files = fixture()
        host = SubmissionHost()
        result = submission.submit(host, d, request, files, 1001)
        self.assertEqual(result['pr'], 1)
        self.assertEqual(host.prs[0]['base']['ref'], 'main')
        head = host.commits[result['head']]
        self.assertEqual([p['sha'] for p in head['parents']], [request['base']])
        tree = host.trees[head['tree']['sha']]
        self.assertEqual(set(tree), set(files))
        self.assertEqual(tree['run.sh'][0], '100755')
        self.assertEqual(host.blobs[tree['src/main.py'][1]], files['src/main.py']['content'])
        self.assertNotIn('README.md', tree)
        self.assertFalse(result['admission_established'])
        writes = list(host.writes)
        self.assertEqual(submission.submit(host, d, request, files, 1001), result)
        self.assertEqual(host.writes, writes)

    def test_lost_commit_branch_and_pr_acknowledgements_recover_exact_result(self):
        for point in ('/git/commits', '/git/refs', '/pulls'):
            d, request, files = fixture()
            host = SubmissionHost()
            host.fail_after = point
            with self.subTest(point=point), self.assertRaises(OSError):
                submission.submit(host, d, request, files, 1001)
            result = submission.submit(host, d, request, files, 1001)
            self.assertEqual(result['pr'], 1)
            self.assertEqual(len(host.refs), 1)
            self.assertEqual(len(host.prs), 1)

    def test_unsafe_exports_and_bindings_are_rejected_before_writes(self):
        d, request, files = fixture()
        for path in ('../escape', '.git/config', 'src/.GIT/hooks/x', 'AUX.txt', 'a\\b', '/absolute', 'a:stream',
                     'a*', 'a?', 'a|b', 'a<b', 'a\x7fb'):
            host = SubmissionHost()
            bad = dict(files, **{path: {'content': b'unsafe', 'executable': False}})
            with self.subTest(path=path), self.assertRaises(Refusal):
                submission.submit(host, d, request, bad, 1001)
            self.assertEqual(host.writes, [])
        for bad in [dict(files, **{'SRC/main.py': files['src/main.py']}),
                    dict(files, **{'src': files['run.sh']})]:
            host = SubmissionHost()
            with self.assertRaises(Refusal):
                submission.submit(host, d, request, bad, 1001)
            self.assertEqual(host.writes, [])
        altered = dict(request, deployment_digest='f' * 64)
        host = SubmissionHost()
        with self.assertRaises(Refusal):
            submission.submit(host, d, altered, files, 1001)
        self.assertEqual(host.writes, [])

    def test_foreign_branch_changed_head_or_wrong_pr_author_never_reuses_submission(self):
        for defect in ('head', 'author', 'tree'):
            d, request, files = fixture()
            host = SubmissionHost()
            first = submission.submit(host, d, request, files, 1001)
            if defect == 'head':
                host.refs[first['branch']] = 'a' * 40
            elif defect == 'author':
                host.prs[0]['user']['id'] = 999
            else:
                host.commits[first['head']]['tree']['sha'] = 'b' * 40
            writes = list(host.writes)
            with self.subTest(defect=defect), self.assertRaises(Refusal):
                submission.submit(host, d, request, files, 1001)
            self.assertEqual(host.writes, writes)


if __name__ == '__main__':
    unittest.main()
