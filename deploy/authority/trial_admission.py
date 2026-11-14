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
        self._hosted = None

    @classmethod
    def hosted(cls, registry, origin_reader, authority, source, root, clock, environment, hint, prompt,
               model, proofs, delivery_key, store_factory=private_setup.Store):
        """Admit authenticated native consent; caller JSON never grants a waiver."""
        authority_release.authorize('protected-run')
        from trial_handoff import Hosted
        context = Hosted(registry, origin_reader, authority, environment, hint, prompt, clock)
        c = cls(None, registry, authority, source, root, clock, store_factory)
        c._hosted = context
        c.run(context.environment, context.task, model, proofs, delivery_key, context.approve)
        return c

    def _binding(self):
        require((self._hosted is not None or isinstance(self.provision, Provision)) and isinstance(self.registry, Registry),
                'native provision and independent trial registry required')
        if self._hosted is not None:
            self._hosted.guard()
            pair = copy.deepcopy(self._hosted.record['pair'])
            origin = self._hosted.origin_binding['deployment']
        else:
            pair = self.provision.completed()
            origin = self.provision.session._check()['deployment']
        b = self.registry.binding()
        d, p = b['deployment'], b['deployment']['policy']
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
        origin_binding = self._hosted.origin_binding if self._hosted is not None else self.provision.session._check()
        app_digests, expires = {}, [task['deadline'], lease['expires'], d['expires'],
            self._hosted.record['expires'] if self._hosted is not None else self.provision.preview['expires'],
            origin_binding['fence']['pending']['execution_deadline']]
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
        self.provision_document = copy.deepcopy(self.provision.document) if self.provision is not None else None
        self.origin_binding = copy.deepcopy(origin_binding)
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
        if self._hosted is not None: approve = self._hosted.approve
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
        self._original_guard()
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
        self._original_guard()
        require(self.registry.binding() == self.binding, 'trial configuration moved during live readback')
        self._clock()  # Includes time consumed by every live API read above.

    def _guard(self):
        require(self.document is not None and self.journal.read() == self.document and
                self.document['value'] == dict(admission=self.intent, approval=digest(self.intent)),
                'retained exact trial consent required')
        self._live()
        require(self.journal.read() == self.document and (self.provision is None or
                self.provision.journal.read() == self.provision_document),
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

    def _worker_configuration(self):
        """Live configuration pointers to immutable documents authenticated by run()."""
        self._clock()
        expected = dict(admission=self.intent, approval=digest(self.intent))
        if self._hosted is not None:
            require(self.journal.read() == self.document and self.document['value'] == expected,
                    'retained hosted trial consent changed')
            branches = self._hosted.worker_configuration()
            require(self.journal.read() == self.document, 'hosted consent changed during readback')
            self._clock()
            return branches
        def journals():
            require(self.journal.read() == self.document and self.document['value'] == expected and
                    self.provision.journal.read() == self.provision_document,
                    'retained trial consent or provisioning changed')
        journals()
        session = self.provision.session
        require(session.expected == (self.origin_binding['configuration_revision'], self.origin_binding['deployment_digest'],
                                     self.origin_binding['branch_head']) and
                session.operation_id == self.intent['origin']['operation_id'] and
                session.sequence == self.intent['origin']['sequence'], 'original trial session changed')
        session._owned(self.origin_binding)  # Local ownership/scope/deadline checks; no immutable blob download.
        original_branch = session.registry.unchanged(self.origin_binding)
        trial_branch = self.registry.unchanged(self.binding)
        journals()
        self._clock()
        return original_branch, trial_branch

    def _worker_guard(self):
        """Full job/controls checks bracket work; source/config pointers guard effects."""
        original_branch, trial_branch = self._worker_configuration()
        original = self._hosted.original if self._hosted is not None else self.provision.session.registry
        p = self.binding['deployment']['policy']
        repo = self.source.get('/repos/' + p['repository'])
        require(repo.get('id') == p['repository_id'] and repo.get('private') is True and
                repo.get('owner', {}).get('id') == self.pair['identities']['owner_id'] and
                repo.get('default_branch') == p['target'] and
                submission.existing_ref(self.source, '/repos/' + p['repository'], p['target']) == self.intent['source_base'],
                'trial frozen source identity or ref changed')
        for registry, binding, branch in ((original, self.origin_binding, original_branch),
                                          (self.registry, self.binding, trial_branch)):
            require(registry.ref(registry.coordinates['registry_branch']) == binding['branch_head'] and
                    registry.ref(branch) == binding['software_revision'], 'trial pointers moved during source readback')
        require(self.journal.read() == self.document and (self.provision is None or
                self.provision.journal.read() == self.provision_document), 'trial journals moved during source readback')
        if self._hosted is not None:
            require(original.ref('agentic-trial-' + self._hosted.record['task_id']) == self._hosted.record['execution']['publication_revision'] and
                    original.ref('agentic-trial-' + self._hosted.record['task_id'] + '-execution') == self._hosted.revision,
                    'native execution binding moved during source observation')
            self._hosted.local_guard()
        self._clock()

    def _original_guard(self):
        if self._hosted is not None:
            self._hosted.guard()
        else:
            require(self.provision.journal.read() == self.provision_document and
                    self.provision._origin(self.pair['fixture_repository'], self.pair['authority_repository']) == self.intent['origin'],
                    'trial provisioning or origin fence changed')


class ControlAdmission:
    """Separate hosted observation purpose; cannot admit a coding Worker."""
    def __init__(self, registry, origin_reader, authority, root, clock, environment, hint, prompt, model, proofs,
                 store_factory=private_setup.Store):
        from trial_handoff import Hosted
        self._hosted = Hosted(registry, origin_reader, authority, environment, hint, prompt, clock)
        context = self._hosted
        require(context.environment['GITHUB_JOB'] == 'trial_task_controls', 'independent trial controls purpose required')
        self.registry, self.authority, self.root, self.clock, self.store = registry, authority, Path(root), clock, store_factory
        self.binding, self.environment, self.started = copy.deepcopy(context.record['trial']), context.environment, clock()
        d, task = self.binding['deployment'], context.task
        object_fields(proofs, app_proofs.PERMISSIONS, 'five closed trial own-App producers')
        identities, deadlines = app_proofs.load_identities(d), [task['deadline']]
        for purpose, location in proofs.items():
            proof = provenance.authenticated_document(authority, d, location, 'proof', purpose, clock())
            require(proof['run_id'] == task['run_id'] and proof['attempt'] == task['attempt'], 'trial control proof execution differs')
            value = app_proofs.validate(proof['document'], d, identities, purpose, self.binding['branch_head'], clock())
            require(proof['job_started'] <= value['observed'] <= proof['artifact_created'] <= proof['job_completed'],
                    'trial control App proof lies outside producer interval')
            deadlines.append(value['expires'])
        proof = provenance.authenticated_document(authority, d, model, 'model-lease', task['task_id'], clock())
        object_fields(proof['document'], ('ciphertext', 'model_execution_qualified'), 'closed encrypted trial model delivery')
        require(proof['run_id'] == task['run_id'] and proof['attempt'] == task['attempt'] and
                proof['document']['model_execution_qualified'] is False and isinstance(proof['document']['ciphertext'], str) and
                0 < len(proof['document']['ciphertext']) <= model_vault.MAX_CIPHER and proof['document']['ciphertext'].isascii(),
                'trial control model delivery differs')
        parent = provenance.execution_job(authority, d, task['run_id'], task['attempt'], 'hosted qualification')
        require(parent['id'] != context.job['id'], 'separate qualification parent and trial controls required')
        self.intent = dict(task=task, source_base=context.record['pair']['fixture_revision'],
            configuration_revision=self.binding['configuration_revision'], deployment_digest=self.binding['deployment_digest'],
            execution=dict(run_id=task['run_id'], attempt=task['attempt'], job_id=parent['id']), expires=min(deadlines))
        self.journal = self.store(self.root / 'control-admission')
        self.document = self.journal.read()
        expected = dict(intent=self.intent, consent_digest=digest(context.record))
        context.guard()
        if self.document is None: self.document = self.journal.write(None, expected)
        require(self.document['value'] == expected, 'retained separate control admission differs')
        self._guard()

    def _clock(self):
        require(self.started <= self.clock() < self.intent['expires'], 'trial control admission expired')

    def _worker_configuration(self):
        self._clock()
        require(self.journal.read() == self.document, 'retained trial control consent changed')
        result = self._hosted.worker_configuration()
        require(self.journal.read() == self.document, 'trial control consent changed during live readback')
        self._clock()
        return result

    def _guard(self):
        self._worker_configuration()
        job = provenance.execution_job(self.authority, self.binding['deployment'], self.intent['task']['run_id'],
            self.intent['task']['attempt'], 'trial task controls (' + self.intent['task']['task_id'] + ')')
        require(job['id'] == self._hosted.job['id'], 'independent trial control producer changed')
        self._worker_configuration()
