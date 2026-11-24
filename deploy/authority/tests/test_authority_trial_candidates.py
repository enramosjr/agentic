"""Native closed worker -> actual distinct candidate PRs, never qualification."""
import backend_test_support
import copy
import unittest

import authority_release
import test_authority_trial_service as service_fixture
from trusted_ci_policy import Refusal, digest


@unittest.skipIf(service_fixture.hosted.workflow.staging.handoff.preparation.jwt is None, 'optional cryptography required')
class Candidates(unittest.TestCase):
    fixture = service_fixture.TrialService.fixture
    prepared = service_fixture.TrialService.prepared
    connected = service_fixture.TrialService.connected
    configured = service_fixture.TrialService.configured
    exercise = service_fixture.TrialService.exercise

    def prepare(self, native, source, origin, apps, tokens, admin, artifacts):
        import trial_candidates
        # The native administrator reads the same actual controls used by the
        # separate trial-controls producer. GitHub/OCI remain fixture transports.
        api = native.provision.api
        if not getattr(api, 'candidate_trees', False):
            original, pages, directories = api.get, api.pages, {}
            def get(route):
                if route in directories: return copy.deepcopy(directories[route])
                if route.startswith('/users/') and '%5Bbot%5D' in route: return source.get(route)
                if route.endswith('/actions/permissions'): return admin.get(route)
                value = original(route)
                if '/repos/owner/trial/git/trees/' in route and '?' not in route:
                    entries, nested = [], {}
                    for entry in value['tree']:
                        if '/' in entry['path']:
                            folder, path = entry['path'].split('/',1)
                            nested.setdefault(folder, []).append(dict(entry, path=path))
                        else: entries.append(entry)
                    for folder, children in nested.items():
                        tree = digest(children)[:40]
                        directories['/repos/owner/trial/git/trees/' + tree] = dict(sha=tree, truncated=False, tree=children)
                        entries.append(dict(path=folder, mode='040000', type='tree', sha=tree))
                    value = dict(value, tree=entries)
                return value
            api.get, api.candidate_trees = get, True
            api.pages = lambda route, collection=None: admin.pages(route, collection) if (
                '/collaborators?' in route or route.endswith('/hooks')) else pages(route, collection)
        return trial_candidates.Prepare(native, apps(native.registry.read()['apps']['coding'],
            native.registry.api.secrets['AGENTIC_CODING_PRIVATE_KEY']), tokens,
            lambda token: origin.reader)

    def test_closed_native_worker_prepares_distinct_exact_candidates_and_resumes_without_writes(self):
        def check(*args):
            import trial_candidates
            native, source, origin, apps, tokens, admin, artifacts = args
            controller = self.prepare(*args)
            before, production = native.registry.binding(), origin.binding()
            result = controller._run('prompt', source)
            self.assertEqual([v['name'] for v in result['candidates']], list(trial_candidates.CASES))
            submitted = [v['submitted'] for v in result['candidates']]
            self.assertEqual(len({v['pr'] for v in submitted}), 16)
            self.assertEqual(len({v['head'] for v in submitted}), 16)
            self.assertEqual(len(source.prs), 17)
            for value in submitted:
                self.assertEqual(value['tree'], result['worker']['submitted']['tree'])
                self.assertEqual(source.commits[value['head']]['parents'], [{'sha':source.refs['main']}])
            writes = copy.deepcopy(source.writes)
            self.assertEqual(self.prepare(*args)._run('prompt', source), result)
            self.assertEqual(source.writes, writes)
            self.assertEqual(native.registry.binding(), before)
            self.assertEqual(origin.binding(), production)
            self.assertEqual(before['deployment']['state'], 'qualification')
            self.assertIsNone(before['deployment']['qualification'])
            self.assertFalse(result['hosted_qualified'])
            self.assertFalse(result['enforcement_active'])
            self.assertFalse(result['cases_executed'])
            for secret in native.registry.api.secrets.values(): self.assertNotIn(secret, str(result))
        self.exercise(continuation=check)

    def test_lost_pr_ack_recovers_read_only_and_missing_pr_never_replays(self):
        for lost in ('/pulls', '/git/refs'):
            def check(*args):
                native, source, *_ = args
                controller = self.prepare(*args)
                source.fail_after = lost
                with self.assertRaises(OSError): controller._run('prompt', source)
                writes = copy.deepcopy(source.writes)
                self.assertEqual(native.provision.store(native.provision.root / 'trial-candidates').read()['value']['pending'], 0)
                if lost == '/pulls':
                    result = self.prepare(*args)._run('prompt', source)
                    self.assertEqual(len(result['candidates']),16)
                    self.assertEqual(len([v for v in source.writes if v[0].endswith('/pulls')]),17)
                else:
                    with self.assertRaisesRegex(Refusal, 'read-only recovery'):
                        self.prepare(*args)._run('prompt', source)
                    self.assertEqual(source.writes,writes)
            with self.subTest(lost=lost): self.exercise(continuation=check)

    def test_closed_receipt_and_live_bindings_are_required_before_any_candidate_write(self):
        for fault in ('artifact', 'open-worker', 'origin', 'prompt', 'target', 'root'):
            def check(*args):
                native, source, origin, _, _, _, artifacts = args
                controller = self.prepare(*args)
                writes = copy.deepcopy(source.writes)
                target = source.refs['main']
                if fault == 'artifact': artifacts[-1][0]['digest'] = 'sha256:' + '0' * 64
                if fault == 'open-worker':
                    pages = native.registry.api.pages
                    def opened(route, collection=None):
                        values = pages(route, collection)
                        if collection == 'jobs':
                            for job in values:
                                if job['name'] == 'hosted qualification': job.update(status='in_progress',conclusion=None)
                        return values
                    native.registry.api.pages = opened
                if fault == 'origin': origin.api.refs['main'] = '9' * 40
                if fault == 'target': source.refs['main'] = '9' * 40
                if fault == 'root':
                    controller.coding = args[3](native.registry.read()['apps']['merge'],
                        native.registry.api.secrets['AGENTIC_MERGE_PRIVATE_KEY'])
                with self.assertRaises(Refusal):
                    controller._run('different' if fault == 'prompt' else 'prompt', source)
                self.assertEqual(source.writes,writes)
                if fault == 'target': source.refs['main'] = target
            with self.subTest(fault=fault): self.exercise(continuation=check)

    def test_original_control_budget_and_scope_guard_fence_every_mutation(self):
        for fault in ('elapsed', 'backward', 'origin'):
            def check(*args):
                native, source, origin, *_ = args
                controller = self.prepare(*args)
                post, effects = source.post, []
                def mutate(route, body):
                    value = post(route, body)
                    effects.append(route)
                    if len(effects) == 1:
                        if fault == 'origin': origin.api.refs['main'] = '9' * 40
                    return value
                # Move the clock after the first actual write. The original
                # observation may not be renewed between objects.
                clock = native.provision.clock
                moved = [False]
                def now(): return clock() + (31 if fault == 'elapsed' else -1) if moved[0] else clock()
                native.provision.clock = now
                def write(route, body):
                    value = mutate(route, body)
                    moved[0] = True
                    return value
                source.post = write
                with self.assertRaises(Refusal): controller._run('prompt', source)
                self.assertEqual(len(effects),1)
                self.assertEqual(len(source.prs),1)
                with self.assertRaises(Refusal): self.prepare(*args)._run('prompt', source)
                self.assertEqual(len(effects),1)
            with self.subTest(fault=fault): self.exercise(continuation=check)

    def test_retained_request_substitution_cannot_change_prepared_case_identity(self):
        def check(*args):
            native, source, *_ = args
            controller = self.prepare(*args)
            source.fail_after = '/pulls'
            with self.assertRaises(OSError): controller._run('prompt', source)
            journal = native.provision.store(native.provision.root / 'trial-candidates')
            retained = journal.read()
            state = copy.deepcopy(retained['value'])
            # Even a different deterministic submission must not replace the
            # request retained before the original uncertain source effect.
            state['requests'][1]['task_id'] = 'f' * 32
            journal.write(retained,state)
            writes = copy.deepcopy(source.writes)
            with self.assertRaises(Refusal): self.prepare(*args)._run('prompt', source)
            self.assertEqual(source.writes,writes)
        self.exercise(continuation=check)

    def test_case_submission_fits_original_controls_window_at_100ms_per_request(self):
        def check(*args):
            from unittest.mock import patch
            import trial_candidates
            native, source, origin, *_ = args
            controller = self.prepare(*args)
            elapsed, depth, active = [native.provision.clock() * 10], [0], [False]
            native.provision.clock = lambda: elapsed[0] // 10
            for transport in (source, origin.api, native.registry.api, controller.coding):
                for method in ('get', 'pages', 'fetch', 'post'):
                    if not hasattr(transport, method): continue
                    original = getattr(transport, method)
                    def delayed(*a, _original=original, **kw):
                        if depth[0] or not active[0]: return _original(*a, **kw)
                        depth[0] += 1
                        elapsed[0] += 1
                        try: return _original(*a, **kw)
                        finally: depth[0] -= 1
                    setattr(transport, method, delayed)
            observe = trial_candidates.observe
            def measured(*a):
                facts = observe(*a)
                active[0] = True
                return facts
            with patch.object(trial_candidates, 'observe', side_effect=measured):
                result = controller._run('prompt', source)
            self.assertEqual(len(result['candidates']),16)
        self.exercise(continuation=check)


class Holds(unittest.TestCase):
    def test_hold_precedes_native_or_transport_access(self):
        import trial_candidates
        with self.assertRaises(authority_release.Held):
            trial_candidates.Prepare(None, None).run('prompt')
