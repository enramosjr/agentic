"""Ordered host-probe producers over local transports; never hosted evidence."""
import backend_test_support
import base64
import copy
import hashlib
import io
import json
import tarfile
import unittest
import zipfile
from unittest.mock import patch
from urllib.parse import parse_qs, unquote, urlsplit

import qualification_cases
import checks
import controls
import service
import trusted_ci_controller
import test_authority_protocol
from registry import DOCUMENT, OPERATION, Registry
from test_authority_registry import RegistryHost, coordinates
from trusted_ci_github import HostRefusal
from trusted_ci_policy import Refusal, digest
from test_authority_producer_composition import Composition


class ConnectedHost:
    """Existing ACTIVE regression fixtures, never an initial-trial state bridge.

    Real service verification/publication, App proof issuance, cleanup and closed
    artifacts are composed here. GitHub/OCI responses are local fixture boundaries.
    """
    def __init__(self):
        self.fixtures, self.commits, self.by_merge = {}, {}, {}
        self.records, self.raw, self.jobs, self.artifacts, self.attempts = [], {}, [], [], []
        self.base, self.denial, self.move_after, self.ack = '5' * 40, None, False, False
        self.wrong_obligation = False
        self.clock = [1095]
        self.registry_host = RegistryHost()
        for index, name in enumerate(qualification_cases.HOST_CASES, 1):
            f = self.fixture(index, name)
            d, s = f.binding['deployment'], f.snapshot
            case = dict(name=name, snapshot=copy.deepcopy(s), evidence=None, coordinates=None,
                        expected_failure=None, mutations=[], prior=None)
            if name in qualification_cases.NEGATIVE:
                # The real controller observes a candidate that allows an operation
                # which the first approved obligation explicitly expects to deny.
                self.negative(f, case)
            elif name in qualification_cases.ACCEPTANCE:
                self.acceptance(f, case)
            elif name in qualification_cases.STALE:
                old = self.fixture(index, name, prior=True)
                previous = dict(snapshot=copy.deepcopy(old.snapshot))
                self.acceptance(old, previous)
                case['prior'] = dict(deployment=copy.deepcopy(old.binding['deployment']), snapshot=copy.deepcopy(old.snapshot),
                                     evidence=previous['evidence'], coordinates=previous['coordinates'],
                                     registry_revision=old.binding['branch_head'])
                self.commits[old.snapshot['merge']] = old.source.get('/repos/owner/project/git/commits/' + old.snapshot['merge'])
                self.by_merge[old.snapshot['merge']] = copy.deepcopy(old.source.checks)
                self.retain(old, case['prior']['evidence'], index)
                f.source.checks = []
            if name == 'missing-approval': f.source.reviews = []
            if name == 'spoofed-source':
                f.source.checks = [dict(id=700, name=d['policy']['check_name'], head_sha=s['merge'],
                                        app=dict(id=999), status='completed', conclusion='success')]
            self.fixtures[index] = f
            self.records.append(case)
            if case['evidence']: self.retain(f, case['evidence'], index)
        self.active = self.fixtures[1]
        self.registry = Registry(self.registry_host, coordinates())
        self.binding = self.registry.binding()
        self.d = self.binding['deployment']
        self.manifest = dict(repository_id=123, configuration_revision=self.binding['configuration_revision'],
                             deployment_digest=self.binding['deployment_digest'], cases=self.records)

    def retain(self, f, location, index):
        old_id, new_id = location['artifact_id'], index * 10000 + location['artifact_id']
        artifact = copy.deepcopy(next(a for a in f.api.artifacts if a['id'] == old_id))
        artifact['id'] = new_id
        self.artifacts.append(artifact); self.raw[new_id] = f.api.raw[old_id]
        location['artifact_id'] = new_id
        self.jobs.extend(j for j in f.api.jobs if j['id'] == location['job_id'])

    def fixture(self, index, name, prior=False):
        original = test_authority_protocol.policy
        def policy():
            p = original()
            if prior and name == 'policy-transition': p['epoch'] = 'old-context'
            return p
        with patch.object(test_authority_protocol, 'policy', side_effect=policy): f = Composition()
        d, s = f.binding['deployment'], f.snapshot
        old_commit = f.source.commits[s['head']]
        files = {'.ai/scripts/lifecycle.py': ('# local fixture ' + name + '\nimport sys\nsys.exit(0)\n').encode()}
        if name == 'replaced-checks': files['.ai/scripts/tests/test_lifecycle.py'] = b'# replaced candidate test\n'
        if name == 'forged-records': files['knowledge/history/lifecycle/forged.json'] = b'{"approved_by":"human:forged","status":"PASS"}'
        entries = copy.deepcopy(f.source.trees[old_commit['tree']['sha']])
        entries.update({path:('100644', f.source.blob(raw)) for path, raw in files.items()})
        tree = f.source.post('/repos/owner/project/git/trees', dict(tree=[dict(path=p, mode=m, sha=key)
            for p,(m,key) in entries.items()]))['sha']
        head = f.source.post('/repos/owner/project/git/commits', dict(
            message='distinct fixture ' + name + ('-old-head' if prior and name == 'new-head' else ''),
            tree=tree, parents=[v['sha'] for v in old_commit['parents']],
            author=old_commit['author'], committer=old_commit['committer']))['sha']
        base = 'e' * 40 if prior and name != 'new-head' else '5' * 40
        s.update(pr=index, head=head, base=base, merge=format((20000 if prior else 10000) + index, '040x'))
        revision = self.registry_host.blob(json.dumps(d, sort_keys=True).encode())
        f.binding['configuration_revision'] = revision
        f.request['configuration_revision'] = revision
        f.binding['fence']['pending'].update(pr=index, head=head, base=base, merge=s['merge'], configuration_revision=revision)
        f.source.merge_head, f.source.current_base, f.facts['base'] = head, base, base
        f.source.merge_tree = tree
        f.source.commits[base] = copy.deepcopy(old_commit)
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode='w') as archive:
            for path, (mode, blob) in entries.items():
                raw = f.source.blobs[blob]
                member = tarfile.TarInfo('candidate/' + path)
                member.size = len(raw)
                archive.addfile(member, io.BytesIO(raw))
        f.tar, f.mutations = stream.getvalue(), files
        pr = f.source.prs[0]
        pr.update(number=index, mergeable=True)
        pr['head']['sha'], pr['base']['sha'] = head, base
        f.source.refs[pr['head']['ref']] = head
        f.source.reviews[0]['commit_id'] = head
        task_id = f.locators['task']['locator']['artifact_id']
        task = f.api.documents[task_id]
        task['configuration_revision'] = revision
        task['submitted'].update(pr=index, head=head, tree=tree, configuration_revision=revision)
        f.api.replace(task_id, task, 'task.json')
        host = self.registry_host
        document_tree = {DOCUMENT:('100644', revision),
                         OPERATION:('100644', host.blob(json.dumps(f.binding['fence'], sort_keys=True).encode()))}
        registry_tree = digest(document_tree)[:40]
        host.trees[registry_tree] = document_tree
        commit = host.post('/repos/owner/authority/git/commits', dict(message='local registry fixture',
            tree=registry_tree, parents=[host.ref]))['sha']
        host.refs.update(main=d['policy']['workflow_sha'], **{'agentic-registry':commit})
        f.registry = Registry(host, coordinates())
        f.binding = f.registry.binding()
        get = f.source.get
        def source_get(path):
            if '/contents/' in path:
                parsed = urlsplit(path)
                ref = parse_qs(parsed.query)['ref'][0]
                name = unquote(parsed.path.split('/contents/')[1])
                entries = f.source.trees[f.source.commits[ref]['tree']['sha']]
                if name not in entries: raise HostRefusal(404)
                return dict(encoding='base64', content=base64.b64encode(f.source.blobs[entries[name][1]]).decode())
            if '/git/ref/pull/' in path: return dict(object=dict(sha=s['merge']))
            if path.endswith('/git/commits/' + s['merge']):
                return dict(sha=s['merge'], tree=dict(sha=f.source.merge_tree),
                            parents=[dict(sha=s['base']), dict(sha=s['head'])])
            return get(path)
        f.source.get = source_get
        return f

    def negative(self, f, case):
        name = case['name']
        case['mutations'] = [dict(path=p, sha256=hashlib.sha256(raw).hexdigest()) for p,raw in f.mutations.items()]
        case['expected_failure'] = f.binding['deployment']['policy']['checks'][0]
        f.source.checks = []
        f.api.artifacts[:] = [a for a in f.api.artifacts if not a['name'].startswith('evidence-')]
        env = f.job('verify (' + str(f.snapshot['pr']) + ')', 'verify', 510)
        class Disk:
            name = 'local-fixture'
            def __init__(self, *a, **kw): pass
            def __enter__(self): f.events.append('disk-open'); return self
            def __exit__(self, *a): f.events.append('disk-clean')
        class Box:
            def __init__(self, candidate, *a, **kw):
                self.script = (candidate / '.ai/scripts/lifecycle.py').read_bytes()
            def __enter__(self): return self
            def __exit__(self, *a): f.events.append('box-clean')
            def run(self, argv, **kw):
                # Local OCI response: this exact candidate permits the guarded
                # operation, so the real pinned controller records its failure.
                if '.ai/scripts/lifecycle.py' in argv and 'gate' in argv:
                    return (0, '') if b'sys.exit(0)' in self.script else (1, 'intent')
                return 0, ''
        result = service._verify_actions(f.source, f.binding['deployment'], f.snapshot, 510, lambda:None,
            lambda:f.clock[0], disk_factory=Disk, box_factory=Box, image_loader=lambda *a:None)
        document = dict(schema_version=2, kind='actions', registry_revision=f.binding['configuration_revision'], result=result)
        artifact = f.upload('evidence-' + str(f.snapshot['pr']) + '-1', json.dumps(document).encode())
        f.api.jobs[-1].update(status='completed', conclusion='success', completed_at='1970-01-01T00:18:00Z')
        case['evidence'] = dict(run_id=99, attempt=1, job_id=510, artifact_id=artifact)

    def acceptance(self, f, case):
        f.run('verify', verifier=f.verify)
        f.clock[0] = 1090
        for purpose in ('admin', 'reader', 'issuer', 'coding', 'merge'): f.run('proof', purpose)
        with patch.object(controls, 'observe', return_value=f.facts): f.run('publication-controls')
        f.source.checks.clear()
        f.run('publish')
        case['evidence'] = service._locator(f.api, f.binding['deployment'], 99, 1, 'evidence', f.snapshot['pr'])
        proof = next(a for a in f.api.artifacts if a['id'] == case['evidence']['artifact_id'])
        with zipfile.ZipFile(io.BytesIO(f.api.raw[proof['id']])) as archive:
            evidence = json.loads(archive.read('evidence.json'))
        task = f.api.documents[f.locators['task']['locator']['artifact_id']]
        case['coordinates'] = dict(configuration_revision=f.binding['configuration_revision'], operation=copy.deepcopy(f.binding['fence']['pending']),
            sequence=1, issuer_installation_id=f.identities['apps']['issuer']['installation_id'],
            evidence_job_id=case['evidence']['job_id'], evidence_digest=digest(evidence), task_digest=digest(task))

    def get(self, path):
        parsed = urlsplit(path)
        if path == '/repos/owner/authority': return self.active.api.get(path)
        if '/pulls/' in parsed.path:
            self.active = self.fixtures[int(parsed.path.rsplit('/', 1)[1])]
        if '/contents/' in parsed.path:
            ref = parse_qs(parsed.query)['ref'][0]
            fixture = next(f for f in self.fixtures.values() if f.snapshot['head'] == ref) if ref != self.base else self.active
            return fixture.source.get(path)
        if '/git/commits/' in path and path.rsplit('/', 1)[1] in self.commits: return self.commits[path.rsplit('/', 1)[1]]
        if '/git/ref/heads/main' in path: return dict(object=dict(sha=self.base))
        if '/actions/' in path: return self.active.api.get(path)
        return self.active.source.get(path)

    def pages(self, path, collection=None):
        if '/actions/' in path:
            return self.jobs if path.endswith('/jobs') else self.artifacts
        if '/commits/' in path:
            merge = path.split('/commits/')[1].split('/')[0]
            if merge in self.by_merge: return self.by_merge[merge]
        if '/rules/branches/' in path:
            return [dict(type='required_status_checks', parameters=dict(required_status_checks=[dict(
                context=self.d['policy']['check_name'], integration_id=self.d['policy']['app_id'])]))]
        return self.active.source.pages(path, collection)

    def fetch(self, path, **kwargs): return self.raw[int(path.split('/artifacts/')[1].split('/')[0])]

    def runner(self):
        host = self
        fixture = self.fixtures[1]
        class Actor:
            def __init__(self, actor, kind): self.actor, self.kind = actor, kind
            def get(self, path): return dict(id=self.actor, type=self.kind)
            def fetch(self, path, method, data):
                host.attempts.append(dict(actor=self.actor, path=path, method=method, data=data))
                name = host.records[host.active.snapshot['pr'] - 1]['name']
                if host.move_after: host.base = 'a' * 40
                if host.ack: raise OSError('lost acknowledgement')
                category = ('protected_update' if method == 'PATCH' else
                            'required_review' if name == 'missing-approval' else 'required_check')
                raise HostRefusal(422 if method == 'PATCH' else 405, host.denial or category,
                                  ('unrelated-check' if host.wrong_obligation else host.d['policy']['check_name'])
                                  if category == 'required_check' else None)
        def tokens(token):
            probe = fixture.token_api(token)
            actor = Actor(18 if token.startswith('coding:') else 19, 'Bot')
            class Scoped:
                def get(self, path):
                    if path == '/user': raise AssertionError('installation token has no user endpoint')
                    return probe.get(path)
                def pages(self, path, collection=None): return probe.pages(path, collection)
                def fetch(self, path, method='GET', data=None, **kwargs):
                    if path == '/installation/token': return probe.fetch(path, method=method, **kwargs)
                    return actor.fetch(path, method, data)
            return Scoped()
        return qualification_cases.HostCases(self.registry, self, self, self.active.identities,
            fixture.roots['coding'], fixture.roots['merge'], Actor(17, 'User'), lambda:self.clock[0], tokens)


class QualificationCaseContracts(unittest.TestCase):
    def test_public_hold_precedes_all_network_and_native_access(self):
        class Unavailable:
            def __getattr__(self, name): raise AssertionError('unexpected access ' + name)
        boundary = Unavailable()
        with self.assertRaisesRegex(Refusal, 'qualify-live blocked'):
            qualification_cases.HostCases(boundary, boundary, boundary, {}, boundary, boundary, boundary, boundary).run({})

    def test_order_and_duplicate_identity_refuse_before_any_attempt(self):
        for defect in ('order', 'pr', 'head', 'configuration'):
            f = ConnectedHost()
            if defect == 'order': f.records.reverse()
            if defect in ('pr', 'head'): f.records[1]['snapshot'][defect] = f.records[0]['snapshot'][defect]
            if defect == 'configuration': f.manifest['deployment_digest'] = '0' * 64
            with self.subTest(defect=defect), self.assertRaises(Refusal): f.runner()._run(f.manifest)
            self.assertEqual(f.attempts, [])

    def test_generic_errors_wrong_obligation_and_uncertain_outcome_are_not_denials_or_replayed(self):
        for defect in ('generic', 'obligation', 'ack', 'move'):
            f = ConnectedHost()
            if defect == 'generic': f.denial = 'unknown'
            if defect == 'ack': f.ack = True
            if defect == 'move': f.move_after = True
            if defect == 'obligation': f.wrong_obligation = True
            runner = f.runner()
            with self.subTest(defect=defect), self.assertRaises((Refusal, OSError)): runner._run(f.manifest)
            self.assertEqual(len(f.attempts), 1)
            with self.assertRaisesRegex(Refusal, 'never replay'): runner._run(f.manifest)

    def replace(self, f, case, edit):
        location = case['evidence']
        identity = location['artifact_id']
        with zipfile.ZipFile(io.BytesIO(f.raw[identity])) as archive:
            document = json.loads(archive.read('evidence.json'))
        edit(document)
        raw = io.BytesIO()
        with zipfile.ZipFile(raw, 'w') as archive: archive.writestr('evidence.json', json.dumps(document))
        f.raw[identity] = raw.getvalue()
        next(a for a in f.artifacts if a['id'] == identity)['digest'] = 'sha256:' + hashlib.sha256(raw.getvalue()).hexdigest()

    def test_failed_obligation_mutation_archive_and_cleanup_are_actual_prerequisites(self):
        for defect in ('skipped', 'success', 'mutations', 'digest', 'job', 'cleanup', 'execution'):
            f = ConnectedHost()
            if defect in ('skipped', 'success'):
                self.replace(f, f.records[0], lambda d:d['result']['report']['outcomes'][0].update(status='not_run' if defect == 'skipped' else 'success'))
            if defect == 'mutations': f.records[0]['mutations'][0]['sha256'] = '0' * 64
            if defect == 'digest': f.raw[f.records[0]['evidence']['artifact_id']] = b'corrupt'
            if defect == 'job': next(j for j in f.jobs if j['name'] == 'verify (1)').update(status='in_progress', conclusion=None)
            if defect == 'cleanup': self.replace(f, f.records[0], lambda d:d['result'].update(cleanup_complete=False))
            if defect == 'execution': self.replace(f, f.records[0], lambda d:d['result']['report']['execution'].update(job_id=999))
            with self.subTest(defect=defect), self.assertRaises(Refusal): f.runner()._run(f.manifest)
            self.assertEqual(f.attempts, [])

    def test_acceptance_prior_success_and_other_obligations_cannot_be_fabricated(self):
        for defect in ('issuer', 'prior', 'parents', 'policy', 'extra-check', 'approval'):
            f = ConnectedHost()
            if defect == 'issuer': f.fixtures[5].source.checks[0]['app']['id'] = 999
            if defect == 'prior': f.by_merge[f.records[6]['prior']['snapshot']['merge']] = []
            if defect == 'parents': f.commits[f.records[6]['prior']['snapshot']['merge']]['parents'].reverse()
            if defect == 'policy': f.records[8]['prior']['deployment']['policy']['epoch'] = f.d['policy']['epoch']
            if defect == 'approval': f.fixtures[1].source.reviews[0]['user']['type'] = 'Bot'
            if defect == 'extra-check':
                pages = f.pages
                def with_extra(path, collection=None):
                    rows = pages(path, collection)
                    if '/rules/branches/' in path:
                        rows[0]['parameters']['required_status_checks'].append(dict(context='unrelated', integration_id=101))
                    return rows
                f.pages = with_extra
            with self.subTest(defect=defect), self.assertRaises(Refusal): f.runner()._run(f.manifest)
            self.assertLess(len(f.attempts), len(qualification_cases.HOST_CASES))

    def test_connected_prefix_produces_exact_intended_denials_and_bound_observations(self):
        f = ConnectedHost()
        result = f.runner()._run(f.manifest)
        self.assertEqual([c['name'] for c in result['cases']], list(qualification_cases.HOST_CASES))
        self.assertEqual(len(f.attempts), len(qualification_cases.HOST_CASES))
        self.assertFalse(result['hosted_qualified'])
        for record, evidence, request in zip(result['cases'], result['observations'], f.attempts):
            self.assertEqual(record['evidence_digest'], digest(evidence))
            self.assertEqual(record['before'], record['after'])
            self.assertEqual(record['actor_id'], request['actor'])
            self.assertEqual(evidence['request'], {k:v for k,v in request.items() if k != 'actor'})
            self.assertIsNone(record['merge_commit'])
            self.assertEqual(record['merge_parents'], [])
            self.assertEqual(evidence['synthetic_commit']['tree']['sha'], record['tree'])
            self.assertEqual([v['sha'] for v in evidence['synthetic_commit']['parents']], [record['base'], record['head']])
        for name in qualification_cases.NEGATIVE:
            fixture = f.fixtures[list(qualification_cases.HOST_CASES).index(name) + 1]
            self.assertLess(fixture.events.index('box-clean'), fixture.events.index('disk-clean'))
            self.assertLess(fixture.events.index('disk-clean'), next(i for i,v in enumerate(fixture.events) if v.startswith('upload:evidence')))
        roots = f.fixtures[1].roots
        for purpose in ('coding', 'merge'):
            self.assertEqual(set(roots[purpose].visible), set(roots[purpose].revoked))

    def test_credential_failure_cannot_masquerade_as_the_host_request_denial(self):
        f = ConnectedHost()
        root = f.fixtures[1].roots['merge']
        def unavailable(path): raise HostRefusal(405, 'required_check', f.d['policy']['check_name'])
        root.get = unavailable
        with self.assertRaises(HostRefusal): f.runner()._run(f.manifest)
        self.assertEqual(f.attempts, [])

    def test_commit_readback_must_name_the_exact_synthetic_revision(self):
        f = ConnectedHost()
        get = f.get
        def substituted(path):
            value = get(path)
            if path.endswith('/git/commits/' + f.records[0]['snapshot']['merge']):
                value['sha'] = '0' * 40
            return value
        f.get = substituted
        with self.assertRaises(Refusal): f.runner()._run(f.manifest)
        self.assertEqual(f.attempts, [])

    def test_host_prefix_excludes_broker_positive_and_preserves_approved_order(self):
        self.assertEqual(qualification_cases.HOST_CASES, (
            'bad-acceptance', 'replaced-checks', 'forged-records', 'spoofed-source',
            'missing-approval', 'direct-push', 'new-head', 'new-base',
            'policy-transition', 'human-update', 'coding-update'))

    def test_remaining_cases_recheck_prerequisites_after_durable_intent(self):
        for name in ('new-base', 'policy-transition', 'human-update'):
            for fault in ('approval', 'issuer', 'other-obligation'):
                with self.subTest(name=name, fault=fault):
                    f = ConnectedHost()
                    case = next(c for c in f.records if c['name'] == name)
                    runner = f.runner()
                    runner.binding, runner.d = f.binding, f.d
                    retained = []
                    def retain(request):
                        retained.append(copy.deepcopy(request))
                        if fault == 'approval':
                            f.active.source.reviews.clear()
                        elif fault == 'issuer':
                            merge = (case['prior']['snapshot']['merge'] if case['prior'] else case['snapshot']['merge'])
                            entries = f.by_merge[merge] if case['prior'] else f.active.source.checks
                            self.assertTrue(entries)
                            entries.clear()
                        else:
                            pages = f.pages
                            def extra(path, collection=None):
                                rows = pages(path, collection)
                                if '/rules/branches/' in path:
                                    rows[0]['parameters']['required_status_checks'].append(
                                        dict(context='another', integration_id=101))
                                return rows
                            f.pages = extra
                    with self.assertRaises(Refusal):
                        runner._probe(case, dict(merge=19, human=17), dict(id=17, type='User'), before_send=retain)
                    self.assertEqual(len(retained), 1)
                    self.assertEqual(f.attempts, [])

    def test_human_identity_is_reauthenticated_after_durable_intent(self):
        for changed in (dict(id=17, type='Bot'), dict(id=18, type='User'), dict(id=17.0, type='User')):
            with self.subTest(changed=changed):
                f = ConnectedHost()
                case = next(c for c in f.records if c['name'] == 'human-update')
                runner = f.runner()
                runner.binding, runner.d = f.binding, f.d
                def retain(request): runner.human.get = lambda path: changed
                with self.assertRaises(Refusal):
                    runner._probe(case, dict(human=17), dict(id=17, type='User'), before_send=retain)
                self.assertEqual(f.attempts, [])

    def test_full_prefix_requires_strict_human_identity_before_any_attempt(self):
        f = ConnectedHost()
        runner = f.runner()
        runner.human.get = lambda path: dict(id=17.0, type='User')
        with self.assertRaisesRegex(Refusal, 'host probe actor identity differs'):
            runner._run(f.manifest)
        self.assertEqual(f.attempts, [])

    def test_human_identity_read_cannot_outlive_admission(self):
        from trusted_ci_policy import require
        f = ConnectedHost()
        case = next(c for c in f.records if c['name'] == 'human-update')
        runner = f.runner()
        runner.binding, runner.d = f.binding, f.d
        moved = []
        runner.admission_guard = lambda: require(not moved, 'admission moved')
        def retain(request):
            def identity(path):
                moved.append(True)
                return dict(id=17, type='User')
            runner.human.get = identity
        with self.assertRaisesRegex(Refusal, 'admission moved'):
            runner._probe(case, dict(human=17), dict(id=17, type='User'), before_send=retain)
        self.assertEqual(f.attempts, [])

    def test_human_update_counts_only_protected_403_or_422(self):
        for status in (401, 403, 404, 405, 422, 500):
            with self.subTest(status=status):
                f = ConnectedHost()
                case = next(c for c in f.records if c['name'] == 'human-update')
                runner = f.runner()
                runner.binding, runner.d = f.binding, f.d
                def deny(path, method, data):
                    f.attempts.append(dict(path=path, method=method, data=data))
                    raise HostRefusal(status, 'protected_update')
                runner.human.fetch = deny
                if status in (403, 422):
                    record, _ = runner._probe(case, dict(human=17), dict(id=17, type='User'))
                    self.assertEqual(record['http_status'], status)
                else:
                    with self.assertRaises(Refusal):
                        runner._probe(case, dict(human=17), dict(id=17, type='User'))
                self.assertEqual(len(f.attempts), 1)


if __name__ == '__main__':
    unittest.main()
