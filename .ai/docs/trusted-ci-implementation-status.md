# Trusted CI implementation status

Status: Local disk-backed qualification passed; unfinished implementation on
`codex/trusted-ci`, being checkpointed solely for the user-requested frozen-candidate
gate. Not ready to ship. External enforcement
has not been activated. User spec and plan approvals
are recorded in the branch's lifecycle state; their approved bodies remain pinned.

## Source prepared

- Strict policy, snapshot and evidence validation, including approved policy epochs.
- Restricted Docker/Podman execution with runtime checks before candidate execution,
  no issuer credentials, and independently provisioned disk-backed work storage.
- Host-side critical assertions and authority-controlled adopter extension support.
- Exact merge-bound GitHub artifact provenance and separate App publication.
- Read-only deployment inspection, independent access attestation checks and hosted
  qualification probes with explicit obligation-specific denial evidence.
- Separate authority workflow, installer distribution and provisioning notice,
  adopter guide and governance documentation updates.

## Executed evidence

Commands use the installed Python executable on Windows in place of `python3`.
See the lifecycle ledger in Git scratch for exact executable, inputs and outcomes.

### Current disk-backed qualification — 2026-11-07

The user explicitly approved the documented privileged infrastructure setup in
the dedicated Podman WSL2 backend. A fixed trusted image created a 256 MiB ext4
filesystem with UID/GID 65534 ownership, attached as the recorded task-owned
`/dev/loop0`, and mounted through the engine-managed work volume.

- `lifecycle.py run trusted-ci-disk-isolation -- python -m unittest discover -s .ai/scripts/tests -p test_trusted_ci_isolation.py`
  → PASS under strict acceptance, with the real OCI case executed, not skipped.
- `lifecycle.py run trusted-ci-disk-controller-final -- python -m unittest discover -s .ai/scripts/tests -p test_trusted_ci_acceptance.py`
  → PASS under strict acceptance. The full real controller/lifecycle/assurance/
  installer flow passed, and a deliberately broken candidate with unconditional
  success, empty candidate tests and forged local approval was rejected by the
  trusted lifecycle assertion.
- `lifecycle.py run trusted-ci-disk-combined -- python -m unittest -v test_trusted_ci_isolation test_trusted_ci_acceptance`
  → PASS, nine tests with no skips, on tree `a287560`. Tests now clean only their
  admitted fixture data through an unprivileged trusted-image helper after the
  candidate container has stopped, so the modules execute sequentially without
  privileged resets between them.
- Final `lifecycle.py run trusted-ci-disk-owned-cleanup -- python -m unittest -v test_trusted_ci_isolation test_trusted_ci_acceptance`
  → PASS, **eleven tests with no skips**, on tree `7a1d717`. Independent review
  identified a fixture-cleanup reservation race; the helper now reacquires the
  exact deterministic container name before deleting its own data. The collision
  and failed-admission guards have recorded RED/GREEN and portable regressions,
  and the corrected helper also passed this real sequential-container run.
- Independent cleanup check found only `lost+found` in the work filesystem. Both
  task-owned volume mappings were then removed; the recorded loop device was
  verified against its backing file, detached, and confirmed detached. Final
  filtered volume and candidate-container inventories were both `[]`.

R2/R3's earlier local environment blockers are resolved. Hosted R9 qualification
and the full frozen-candidate gate remain outstanding. These results do not replace
the earlier failed convergence record with a claimed new convergence PASS.

### Earlier diagnostics and portable evidence

- `lifecycle.py run trusted-ci-portable -- python -m unittest discover -s .ai/scripts/tests -p test_trusted_ci_*.py`
  → PASS, with real controller/isolation cases explicitly skipped without the
  required volume. This establishes portable checks, actual localhost HTTP publisher
  integration and actual installer/local-feedback paths, not deployed enforcement.
- `python -m unittest discover -s .ai/scripts/tests -p test_trusted_ci_qualification.py`
  → PASS, six tests, including the complete controlled-host ten-case driver and
  rejection of generic refusals. Controlled responses are not hosted evidence.
- A deliberately broken `check_negative` implementation made its criterion-proof
  regression fail as expected; the negative test is sensitive to missing enforcement.
- `python -m unittest discover -s .ai/scripts/tests -p test_trusted_ci_isolation.py`
  → PASS for portable checks, with one real OCI case skipped. The Docker read-only
  source-handling regression was observed RED, then GREEN after its fix.
- `lifecycle.py converge .ai/docs/trusted-ci-spec.md` with
  `AGENTIC_TRUSTED_ACCEPTANCE=1` → **7 PASS, 3 FAIL**. R2/R3 lack the required
  disk-backed executor prerequisites; R9 lacks the independent hosted credentials
  and configuration. No strict skipped pass or convergence success is claimed.
- `lifecycle.py run trusted-ci-installer-regression -- python -m unittest discover -s .ai/scripts/tests -p test_install.py`
  → FAIL/timeout at 600 seconds. Its installed governance-size failure was isolated
  to `InstructionsTests.test_installed_governance_including_markers_stays_below_budget`,
  reproduced RED, and repaired with a shorter existing-introduction link.
- `lifecycle.py run trusted-ci-installed-budget -- python -m unittest discover -s .ai/scripts/tests -p test_install.py -k test_installed_governance_including_markers_stays_below_budget`
  → PASS after that repair. The serial suite's final incomplete class was separately
  run with `lifecycle.py run trusted-ci-windows-hook-upgrade -- python -m unittest test_install.WindowsHookUpgradeTests`
  → PASS. These focused results do not rewrite the broader timeout as a suite PASS.
- Source `AgentsBudget.test_agents_md_stays_below_its_cold_start_budget` → PASS.
- Spec/plan/test requirement trace → PASS for all ten requirement IDs.
- Lifecycle audit → PASS. Review and Verify stages remain open.
- `okf.py affected` reports no bundle; framework-source exemption applies. Existing
  framework docs were updated and no `knowledge/` bundle was created.

An early Podman container isolation check passed before the work area was corrected
from tmpfs. The full controller then correctly failed on lifecycle's disk-backed
scratch requirement. That earlier smoke result does not qualify the current
disk-backed implementation; the current qualification above supplies that evidence.

## Independent review

The original [review](trusted-ci-review.md) and
[follow-up](trusted-ci-review-followup.md) requested changes. The final narrow
[supplement](trusted-ci-review-supplement.md) found no remaining issue in the
examined correction, while explicitly withholding completion/deployment approval.
Reported matrix poisoning, workflow API shape, unrelated-denial, predecessor-binding
and vacuous-test defects were corrected. A frozen-candidate gate and current passing
convergence remain required after infrastructure is available.

The [local follow-up review](trusted-ci-local-review.md) found no remaining issue
in the cleanup ownership correction. Its review preceded the final eleven-test
result above; R9/full-gate evidence still prevents overall approval.

## External prerequisites

1. Future authority executors still need independently provisioned disk-backed
   work storage. The local blocker was resolved through the user's explicit
   [storage authorization](trusted-ci-storage-proposal.md), and its task-owned
   resources were cleaned afterward. The executor itself performs no privileged
   storage setup.
2. An independent administrator must provision the authority repository, approved
   image/policy, App, private credentials, restricted coding identity, effective host
   rules and disposable hosted qualification fixtures. Credentials must remain
   outside the coding environment; the current administrator-capable session does
   not establish that separation.
3. Run hosted positive/denial qualification and the reviewed frozen candidate's
   full required gate. Local disk-backed controller/isolation acceptance has passed.

The retrospective recorded the observed tmpfs/disk-backed integration lesson with
its failing command evidence. No lesson was promoted to a project rule. A `wip:`
checkpoint and branch-only push may be used for the explicitly requested full CI
gate. No PR, default-branch merge or remote-rule mutation is authorized by that gate.
