"""Held candidate-free broker sequencing, with bounded warm-producer waits.

This build cannot start a public session. Internal fixture execution composes the
real collector/receipt/dispatch interfaces without granting hosted qualification.
No administrative API, registry writer, candidate command or root key is loaded.
"""
import secrets
import time

import authority_release
import broker_evidence
from broker_refusal import same
import control_rendezvous
from merge_receipts import ActionsReceipts, not_submitted
import merge_window
from trusted_ci_policy import positive, require

PURPOSES = ('admin', 'reader', 'issuer', 'coding', 'merge')


class Session:
    def __init__(self, registry, source, authority, identities, job_id, locators, merger, uploader,
                 clock=None, sleeper=None):
        self.registry, self.source, self.authority = registry, source, authority
        self.identities, self.job_id, self.locators = identities, job_id, locators
        self.merger, self.uploader = merger, uploader
        self.clock = clock or (lambda: int(time.time()))
        self.sleeper = sleeper or time.sleep

    def run(self):
        authority_release.authorize('broker-merge')  # Before registry/network access.
        return self._run()

    def _guard(self):
        current = self.registry.binding()
        same(current, self.binding, 'operation changed while awaiting final producers')
        self.receipts.current_job()

    def _wait(self, deadline, warm):
        p, op = self.binding['deployment']['policy'], self.binding['fence']['pending']
        names = ['controls (' + str(op['pr']) + ')', *['final proof (' + purpose + ')' for purpose in PURPOSES]]
        root = '/repos/' + p['authority_repository']
        while self.clock() < deadline:
            self._guard()
            jobs = self.authority.pages(root + '/actions/runs/' + str(op['run_id']) +
                '/attempts/' + str(op['attempt']) + '/jobs', 'jobs')
            selected = {}
            for name in names:
                matches = [j for j in jobs if j['name'] == name]
                require(len(matches) <= 1, 'ambiguous final producer job')
                if not matches:
                    continue
                job = matches[0]
                require(positive(job['id']) and job['run_id'] == op['run_id'] and job['head_sha'] == p['workflow_sha'],
                        'final producer belongs to another execution')
                require(job['status'] in ('queued', 'waiting', 'pending', 'in_progress', 'completed'),
                        'unsupported final producer state')
                require(job['status'] != 'completed' or not warm and job['conclusion'] == 'success',
                        'final producer ended before readiness or did not succeed')
                if job['status'] == ('in_progress' if warm else 'completed'):
                    selected[name] = job
            if len(selected) == len(names):
                self._guard()
                return selected
            self.sleeper(min(2, max(0, deadline - self.clock())))
        require(False, 'final producer rendezvous timed out; operation remains pending')

    def _locators(self, jobs):
        p, op = self.binding['deployment']['policy'], self.binding['fence']['pending']
        artifacts = self.authority.pages('/repos/' + p['authority_repository'] + '/actions/runs/' +
                                         str(op['run_id']) + '/artifacts', 'artifacts')
        def locate(prefix, job_name):
            matches = [a for a in artifacts if a['name'] == prefix + '-' + str(op['attempt'])]
            require(len(matches) == 1 and positive(matches[0]['id']), 'missing or ambiguous final producer artifact')
            return dict(run_id=op['run_id'], attempt=op['attempt'], job_id=jobs[job_name]['id'], artifact_id=matches[0]['id'])
        controls = locate('controls-' + str(op['pr']), 'controls (' + str(op['pr']) + ')')
        proofs = {purpose: locate('final-proof-' + purpose, 'final proof (' + purpose + ')') for purpose in PURPOSES}
        return controls, proofs

    def _run(self):
        """Internal source tests only until the public release hold is lifted."""
        self.binding = self.registry.binding()
        op = self.binding['fence']['pending']
        require(op is not None and op['kind'] == 'merge', 'pending broker operation required')
        self.receipts = ActionsReceipts(self.authority, self.registry.binding, self.job_id, self.clock, uploader=self.uploader)
        try:
            gate = self._collect(op)
        except Exception:
            # This closed path has never entered dispatch. An immutable positive
            # artifact may permit later terminal admin recovery, never a retry.
            document = not_submitted(self.binding, self.job_id, self.clock())
            stored = self.receipts.append('not-submitted', document)
            require(self.receipts.authenticate(stored) == document, 'no-dispatch evidence readback differs')
            raise
        # Crossing this boundary is permanently uncertain, including failures
        # before dispatch itself reaches HTTP. Never emit not-submitted here.
        try:
            return merge_window.dispatch(gate, self.registry.binding, self.receipts, self.merger, self.clock)
        except Exception:
            return {'state': 'unknown', 'fence_pending': True, 'operation_id': op['operation_id'],
                    'sequence': self.binding['fence']['sequence']}

    def _collect(self, op):
        # Both administrative and purpose jobs must already be running. Their
        # queue time cannot consume a readback window that has not begun.
        self._wait(min(self.clock() + 120, op['execution_deadline'] - 60,
                       self.binding['deployment']['expires'] - 60), warm=True)
        locators = self.locators() if callable(self.locators) else self.locators
        prepared = broker_evidence.preload(self.registry, self.source, self.authority, self.identities,
                                           self.job_id, locators, self.clock)
        self._guard()
        request = control_rendezvous.ready(self.binding, self.job_id, secrets.token_hex(16), self.clock())
        self.receipts.append('control-ready', request)
        jobs = self._wait(request['expires'] - 60, warm=False)
        controls, final_proofs = self._locators(jobs)
        return broker_evidence.finish(self.registry, self.source, self.authority, self.identities,
                                      prepared, request, controls, final_proofs, self.clock)
