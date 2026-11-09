"""Held qualification-parent admission and frozen source capture, never activation.

The trusted native caller supplies the completed Provision and independently
configured disposable Registry. Closed own-App proofs and model delivery are
authenticated here, not replaced by setup consent or caller JSON. This admits
only the candidate-free qualification parent; production task/broker validators
retain their active-state requirements. No case outcome is produced here.
"""
import copy
from pathlib import Path

import app_proofs
import authority_release
import model_vault
import private_setup
import provenance
import reconcile
import submission
import setup
from codex_harness import profile
from registry import Registry
from trial_setup import Provision
from trusted_ci_policy import digest, object_fields, positive, require


class Admission:
    def __init__(self, provision, registry, authority, source, root, clock, store_factory=private_setup.Store):
        self.provision, self.registry, self.authority, self.source = provision, registry, authority, source
        self.root, self.clock, self.store = Path(root), clock, store_factory
        self.journal = self.document = self.intent = None
        self.environment = self.binding = self.pair = self.provision_document = self.started = None

    def _binding(self):
        require(isinstance(self.provision, Provision) and isinstance(self.registry, Registry),
                'native provision and independent trial registry required')
        pair = self.provision.completed()
        b = self.registry.binding()
        d, p = b['deployment'], b['deployment']['policy']
        origin = self.provision.session._check()['deployment']
        require(d['state'] == 'qualification' and d['qualification'] is None and
                b['fence']['pending'] is None and 0 < self.clock() < d['expires'],
                'settled unqualified trial configuration required')
        require(p['repository'] == pair['fixture_repository'] and p['repository_id'] == pair['fixture_repository_id'] and
                p['authority_repository'] == pair['authority_repository'] and
                p['authority_repository_id'] == pair['authority_repository_id'] and
                p['workflow_sha'] == pair['software_revision'] and
                d['adapter'] == origin['adapter'] and d['account'] == origin['account'] and
                self.registry.coordinates['registry_branch'] == 'agentic-registry', 'trial configuration substituted approved resources')
        identities = app_proofs.load_identities(d)
        require(identities == pair['identities'], 'trial own-App identities differ from provisioning')
        resources, original = profile(d), profile(origin)
        for key in ('model_auth', 'model_id', 'codex_sha', 'codex_version', 'coding_image', 'bundle_sha'):
            require(resources.get(key) is not None and resources.get(key) == original.get(key),
                    'trial model or runtime differs from approved origin')
        require(resources.get('model_session') != original.get('model_session'),
                'trial requires a distinct model authorization session')
        # Qualification targets differ; critical coverage and runtime policy do not.
        for key in ('target', 'workflow', 'image', 'checks', 'reviewers', 'limits'):
            require(p[key] == origin['policy'][key], 'trial critical policy differs from approved origin')
        return pair, b, identities

    def _observe(self, environment, task, model, proofs, delivery_key):
        forbidden = set(setup.CREDENTIAL_NAMES) - {'AGENTIC_MODEL_DELIVERY_KEY'} | {
            'GH_TOKEN', 'OPENAI_API_KEY', 'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY',
            'AWS_SESSION_TOKEN', 'AZURE_CLIENT_SECRET', 'ARM_CLIENT_SECRET'}
        require(not any(environment.get(key) for key in forbidden),
                'trial admission inherited another purpose credential')
        pair, binding, identities = self._binding()
        d, now = binding['deployment'], self.clock()
        self.started = now
        object_fields(task, model_vault.TASK_FIELDS, 'qualification model task')
        object_fields(proofs, app_proofs.PERMISSIONS, 'five trial own-App producers')
        require(task['purpose'] == 'qualification' and positive(task['deadline']) and
                now < task['deadline'], 'distinct qualification-purpose execution required')
        job = provenance.admit_job(self.authority, d, environment, 'hosted qualification', now)
        require(task['run_id'] == int(environment['GITHUB_RUN_ID']) and
                task['attempt'] == int(environment['GITHUB_RUN_ATTEMPT']), 'qualification task belongs to another execution')
        lease = model_vault.read_delivery(self.authority, binding, task, model, delivery_key, now)
        app_digests, expires = {}, [task['deadline'], lease['expires'], d['expires'],
            self.provision.preview['expires'], self.provision.session._check()['fence']['pending']['execution_deadline']]
        for purpose, locator in proofs.items():
            proof = provenance.authenticated_document(self.authority, d, locator, 'proof', purpose, now)
            require(proof['run_id'] == task['run_id'] and proof['attempt'] == task['attempt'],
                    'trial own-App proof belongs to another execution')
            value = app_proofs.validate(proof['document'], d, identities, purpose, binding['branch_head'], now)
            require(proof['job_started'] <= value['observed'] <= proof['artifact_created'] <= proof['job_completed'],
                    'trial own-App observation outside closed job')
            app_digests[purpose] = digest(value)
            expires.append(value['expires'])
        class Deployment:
            def read(self): return copy.deepcopy(d)
        controls = reconcile.Reconciler(self.source, Deployment(), self.clock).readback()
        # Closed artifact IDs and content digests are immutable. Live readbacks
        # bracket their authentication without downloading them again per blob.
        self.binding, self.pair = copy.deepcopy(binding), copy.deepcopy(pair)
        self.provision_document = copy.deepcopy(self.provision.document)
        return dict(schema_version=1, kind='qualification-execution-admission', origin=pair['origin'],
            provision_digest=digest(pair), configuration_revision=binding['configuration_revision'],
            deployment_digest=binding['deployment_digest'], branch_head=binding['branch_head'],
            task=copy.deepcopy(task), model=copy.deepcopy(model), proofs=copy.deepcopy(proofs),
            model_lease_digest=digest(lease), app_proof_digests=app_digests, controls_digest=controls,
            execution=dict(run_id=task['run_id'], attempt=task['attempt'], job_id=job['id']),
            source_base=pair['fixture_revision'], expires=min(expires),
            execution_admitted=True, hosted_qualified=False, enforcement_active=False)

    def run(self, environment, task, model, proofs, delivery_key, approve):
        authority_release.authorize('protected-run')
        self.intent = self.document = self.journal = None
        observed = self._observe(environment, task, model, proofs, delivery_key)
        self.intent, self.environment = copy.deepcopy(observed), dict(environment)
        self._live()
        self.journal = self.store(self.root / 'execution')
        self.document = self.journal.read()
        if self.document is None:
            approval = approve(copy.deepcopy(observed))
            require(approval == digest(observed), 'exact trial execution consent required; setup consent is insufficient')
            self._live()
            self.document = self.journal.write(None, dict(admission=observed, approval=approval))
        state = self.document['value']
        object_fields(state, ('admission', 'approval'), 'retained trial admission')
        require(state['admission'] == observed and state['approval'] == digest(observed),
                'resume only the original exact trial execution')
        self._guard()
        return copy.deepcopy(self.intent)

    def _clock(self):
        require(self.intent is not None and type(self.clock()) is int and
                self.started <= self.clock() < self.intent['expires'], 'trial execution admission expired')

    def _live(self):
        self._clock()
        i = self.intent
        require(self.provision.journal.read() == self.provision_document and
                self.provision._origin(self.pair['fixture_repository'], self.pair['authority_repository']) == i['origin'],
                'trial provisioning or origin fence changed')
        require(self.registry.binding() == self.binding, 'trial execution configuration changed')
        p = self.binding['deployment']['policy']
        repo = self.source.get('/repos/' + p['repository'])
        require(repo.get('id') == p['repository_id'] and repo.get('private') is True and
                repo.get('owner', {}).get('id') == self.pair['identities']['owner_id'] and
                repo.get('default_branch') == p['target'] and
                submission.existing_ref(self.source, '/repos/' + p['repository'], p['target']) == i['source_base'],
                'trial frozen source identity or ref changed')
        # The registry authenticates the authority's identity and software ref.
        # A completed job cannot continue using an earlier live-parent admission.
        job = provenance.admit_job(self.authority, self.binding['deployment'], self.environment,
                                   'hosted qualification', self.clock())
        require(job['id'] == i['execution']['job_id'], 'qualification parent changed')
        controller = self
        class Deployment:
            def read(self): return copy.deepcopy(controller.binding['deployment'])
        require(reconcile.Reconciler(self.source, Deployment(), self.clock).readback() == i['controls_digest'],
                'trial effective controls changed')
        require(self.provision._origin(self.pair['fixture_repository'], self.pair['authority_repository']) == i['origin'] and
                self.registry.binding() == self.binding, 'trial configuration moved during live readback')
        self._clock()  # Includes time consumed by every live API read above.

    def _guard(self):
        require(self.document is not None and self.journal.read() == self.document and
                self.document['value'] == dict(admission=self.intent, approval=digest(self.intent)),
                'retained exact trial consent required')
        self._live()
        require(self.journal.read() == self.document and self.provision.journal.read() == self.provision_document,
                'trial consent journal changed during live readback')
        self._clock()

    def capture_source(self):
        """First admitted operation: bounded exact bytes, without checkout/execution."""
        authority_release.authorize('protected-run')
        self._guard()
        # Immutable Git blobs are checked by capture_source. No bytes escape
        # until the final live guard accepts; no candidate or mutation is run.
        raw = submission.capture_source(self.source, self.binding['deployment'], self.intent['source_base'], self._clock)
        self._guard()
        return raw
