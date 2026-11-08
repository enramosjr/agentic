# Local task-controls checkpoint — 2026-11-08

Status: Bounded local integration on `codex/trusted-ci`, uncommitted. The approved
adopter-owned L2 feature remains unfinished. This note supersedes the missing
`task_controls` status in the historical handoff; it does not change approved
acceptance or authorize release. Python persona governed the backend; JavaScript
considerations applied only to fixed launcher/uploader boundaries.

## Implemented local path

`coding_parent.py` finishes worker, relay and disk cleanup before uploading a
single `task-ready` artifact. Its retained nonce and exact upload acknowledgement
bind the prepared request, export manifest, configuration, deployment, source base,
task, run, attempt and task job. Readiness is not admission or a task result.

`task_controls.py` authenticates that exact in-progress producer through a separate
live-readiness transport. Ordinary closed-artifact readers reject readiness. The
separate candidate-free `service.py` controls role observes complete source rules,
bypass details, actors and indirect automation. Its source-only admin token is
revoked before response upload. Missing bypass visibility explicitly refuses;
coding receives no administrative credentials. Unsupported automation still blocks
without modifying Actions, hooks or required checks.

The task accepts only a successful closed administrative producer bound to its
retained readiness artifact. Every source mutation checks its original observation
start, at most thirty seconds old. Observation, rendezvous and retained mutation
budgets also use monotonic time. Rereading does not renew authorization. Slow
submission can stop after creating some objects; it must not claim admission.

The fixed action maps `task-controls` only to job `task_controls`, passes only its
administrative key, avoids the coding job's sudo path, and bounds the wait. Runtime
packaging includes the dependency; isolated extracted-runtime imports exercise the
real task path. All public execution roles remain held.

`authority_setup.py` refuses every unimplemented remote operation independently of
the release hold, before deployment reads or local inspection. Framework CI now
invokes `deploy/authority/test_task_service.py` after installing optional auth
dependencies. No workflow, provider or GitHub operation was executed here.

## Verification

Commands below use `C:/Users/enram/AppData/Local/Python/bin/python.exe` as `PY`.
Optional-crypto execution uses the existing isolated `authority-auth-env` Python
identified in the handoff. Local fixtures use synthetic credentials and endpoints.

- `PY -m unittest discover -s deploy/authority/tests -p test_authority_task_controls.py`
  → recorded RED for missing module, then GREEN. Additional exact-artifact,
  freshness and monotonic-budget cases passed.
- `PY -m unittest discover -s deploy/authority/tests -p test_authority_controls.py`
  → recorded RED for omitted bypass detail causing an unclassified exception,
  then GREEN with explicit refusal. Omitted visibility never established authority.
- `PY -m unittest discover -s .ai/scripts/tests -p test_authority_client.py`
  → recorded RED for ten false-success fallthrough cases after mocked hold release,
  then GREEN; clean installed-client checks passed as part of that command.
- `PY -m unittest discover -s deploy/authority/tests -p test_authority_runtime_bundle.py`
  → recorded RED for missing dependency in the extracted artifact, then GREEN.
- `node deploy/authority/artifact_upload/test_action.mjs` → PASS, ledger
  `adopter-task-controls-launcher`, tree `3bf124e`; lifecycle reuse confirmed current.
- `node deploy/authority/artifact_upload/test_upload.mjs` → PASS, ledger
  `adopter-task-controls-upload`, tree `3bf124e`.
- Optional Python `deploy/authority/test_task_service.py` → PASS, ledger
  `adopter-task-controls-crypto-final`, final tree `9281b9e`.
- `PY -m unittest discover -s deploy/authority/tests` → PASS, ledger
  `adopter-task-controls-packaged`, final tree `9281b9e`. The single `--inputs`
  covers `deploy/**`, `.ai/scripts/authority_*.py`, `.ai/scripts/trusted_ci_*.py`
  and `.github/workflows/framework-parity.yml`. Earlier aggregates at `3bf124e`
  and `995869e` are historical; this result includes the package correction.

The inherited framework suite `PY .ai/scripts/run_tests.py -j 4` timed out.
Supervisor exit marker was 1, lifecycle recorded exit `None`, and the buffered
suite log stayed empty. No surviving test workers or duplicate gate were found.
Its repeated `--inputs` also retained only `.github/**`; it is not formal current
candidate evidence. The full framework suite has no aggregate PASS.

The independent [scoped review](trusted-ci-task-controls-review.md) covers this
local integration only. Its report preceded the final aggregate result above.
No full-spec convergence or lifecycle Verify is claimed.
Framework mode uses existing docs and Git scratch receipts; no `knowledge/` was
created. `okf.py affected` reported the absent bundle consistently with that mode.

## Finite remaining delivery groups

1. Connect the complete authority producer graph: preparation, model authorization,
   coding/admin rendezvous, independent verification, publication, broker and
   administrative recovery/finalization. The current v2 template still contains
   seven credential consumers only.
2. Complete the native onboarding/operator coordinator and installed remote-client
   routing, including approved automation migration that preserves required checks.
3. Complete scoped qualification trial admission, real case producers and explicit
   independent human-review handling; local fixtures do not substitute for them.
4. Complete status, drift, repair, upgrade and teardown coordination, including
   cloud-resource promotion and preservation of unrelated resources/protections.
5. Freeze the integrated candidate, complete convergence, full framework verification
   and independent feature review. Live GitHub/OCI/model/AWS/Azure qualification
   requires unavailable trusted contexts/accounts and remains held.

No privileged setup, real credential staging, cloud resources, GitHub mutations,
publication, activation, enforcement, merges, commit, push or PR creation occurred.
Unrelated posix-hook-python files and its worktree were preserved. Retrospective:
this continuation applied existing separation, freshness and packaging rules;
no new rule or lesson promotion is proposed. Lifecycle refused a replacement
retrospective as conflicting with the previously recorded closure; that existing
closure was preserved. The unfinished full feature was not marked Verified.
