"""Held admin terminal recovery. Consumes proof; never dispatches or retries.

The recovery pin is independently supplied by trusted release configuration,
not inferred from today's default branch or the candidate. Admin credential
staging belongs to the separately pinned workflow, which remains unqualified.
"""
import copy
import re
import time

import authority_release
from merge_receipts import ActionsReceipts
from merge_window import recover_merged
from trusted_ci_github import authority_run
from trusted_ci_policy import digest, object_fields, positive, require, sha


class Finalizer:
    def __init__(self, registry, authority, source, recovery_pin, environment, clock=None):
        self.registry, self.authority, self.source = registry, authority, source
        self.pin, self.environment = copy.deepcopy(recovery_pin), dict(environment)
        self.clock = clock or (lambda: int(time.time()))

    def finalize(self, operation_id, sequence, broker_job_id):
        authority_release.authorize('broker-merge')
        return self._finalize(operation_id, sequence, broker_job_id)

    def _admit(self):
        p, env = self.pin, self.environment
        object_fields(p, ('authority_repository', 'authority_repository_id', 'workflow', 'workflow_sha'), 'trusted recovery pin')
        require(isinstance(p['authority_repository'], str) and
                re.fullmatch('[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', p['authority_repository']) and
                all(v not in ('.', '..') for v in p['authority_repository'].split('/')) and
                positive(p['authority_repository_id']) and sha(p['workflow_sha']) and
                isinstance(p['workflow'], str) and re.fullmatch(r'\.github/workflows/[A-Za-z0-9_-]+\.ya?ml', p['workflow']),
                'independent recovery runtime pin required')
        require(env.get('GITHUB_REPOSITORY_ID') == str(p['authority_repository_id']) and
                env.get('GITHUB_SHA') == p['workflow_sha'] and env.get('GITHUB_JOB') == 'finalize',
                'not the trusted recovery environment')
        values = [env.get(k) for k in ('GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT')]
        require(all(isinstance(v, str) and re.fullmatch('[1-9][0-9]{0,19}', v) for v in values),
                'exact recovery execution required')
        run_id, attempt = map(int, values)
        run = authority_run(self.authority, p, run_id, attempt)
        require(run['id'] == run_id, 'recovery run identity differs')
        jobs = self.authority.pages('/repos/' + p['authority_repository'] + '/actions/runs/' + str(run_id) +
                                    '/attempts/' + str(attempt) + '/jobs', 'jobs')
        matches = [j for j in jobs if j['name'] == 'finalize']
        require(len(matches) == 1, 'missing or ambiguous recovery job')
        job = matches[0]
        require(positive(job['id']) and job['run_id'] == run_id and job['head_sha'] == p['workflow_sha'] and
                job['status'] == 'in_progress' and job['conclusion'] is None, 'recovery job provenance differs')
        return dict(run_id=run_id, attempt=attempt, job_id=job['id'], workflow_sha=p['workflow_sha'])

    def _finalize(self, operation_id, sequence, broker_job_id):
        require(isinstance(operation_id, str) and re.fullmatch('[0-9a-f]{32}', operation_id) and
                positive(sequence) and positive(broker_job_id), 'exact terminal operation required')
        recovery = self._admit()  # Before reading the administrative registry.
        before = self.registry.binding(check_software=False)
        d, fence = before['deployment'], before['fence']
        p, op = d['policy'], fence['pending']
        require(p['authority_repository'] == self.pin['authority_repository'] and
                p['authority_repository_id'] == self.pin['authority_repository_id'] and
                op is not None and op['kind'] == 'merge' and op['operation_id'] == operation_id and
                fence['sequence'] == sequence and op['configuration_revision'] == before['configuration_revision'] and
                op['deployment_digest'] == before['deployment_digest'], 'pending recovery configuration differs')
        read = lambda: self.registry.binding(check_software=False)
        receipts = ActionsReceipts(self.authority, read, broker_job_id, self.clock, recovery=True)
        producer = receipts.terminal_job()
        locators = {kind: receipts.find_for_recovery(kind) for kind in ('not-submitted', 'dispatch', 'outcome')}
        positive_no_dispatch = locators['not-submitted'] is not None
        require(not positive_no_dispatch or not (locators['dispatch'] or locators['outcome']),
                'contradictory broker terminal evidence; preserve the fence')
        facts = None
        if positive_no_dispatch:
            receipts.authenticate(locators['not-submitted'])
            kind = 'not-submitted'
        else:
            require(locators['dispatch'] is not None, 'no positive terminal evidence; preserve the fence')
            dispatch = receipts.authenticate(locators['dispatch'])
            if locators['outcome'] is not None:
                outcome = receipts.authenticate(locators['outcome'])
                require(outcome['gate_digest'] == dispatch['gate_digest'],
                        'outcome contradicts its dispatch authorization; preserve the fence')
            root = '/repos/' + p['repository']
            pr = self.source.get(root + '/pulls/' + str(op['pr']))
            require(sha(pr.get('merge_commit_sha')), 'exact merged commit unavailable; preserve the fence')
            commit = self.source.get(root + '/git/commits/' + pr['merge_commit_sha'])
            facts = recover_merged(dispatch['gate'], pr, commit)
            facts.update(pr_digest=digest(pr), commit_digest=digest(commit))
            kind = 'merged'
        envelope = dict(schema_version=2, kind='broker-terminal-recovery', operation_digest=digest(op),
            configuration_revision=before['configuration_revision'], deployment_digest=before['deployment_digest'],
            producer=dict(id=producer['id'], run_id=producer['run_id'], head_sha=producer['head_sha'],
                          conclusion=producer['conclusion'], completed_at=producer['completed_at']),
            recovery=recovery, artifacts=locators, facts=facts)
        terminal = dict(operation_id=operation_id, sequence=sequence, kind=kind, receipt_digest=digest(envelope))
        require(read() == before, 'registry changed during terminal recovery')
        # The storage helper checks exact nonforce pointer/parent/tree readback,
        # including lost acknowledgements. No source mutation exists in this class.
        return self.registry.finalize_operation(before['branch_head'], terminal)
