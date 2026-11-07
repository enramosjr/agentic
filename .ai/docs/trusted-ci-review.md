# Review Report

## Verdict

Changes requested — this diagnostic review found remaining qualification-evidence defects. It does not approve completion or deployment.

## Scope

Reviewed the unfinished `codex/trusted-ci` working tree: policy, controller, sandbox, GitHub adapter, deployment inspector, qualification driver, authority workflow, new tests, installer output and trusted-CI documentation.

Previously reported matrix poisoning, documented workflow-path compatibility, organization-only qualification marking and deployed isolation checks were corrected during review. Their final integrated validation remains pending.

## Persona Applied

Python principal engineer. Relevant considerations were strict boundary validation, effective runtime restrictions, resource ownership, and tests that establish the claimed failure reason.

## Findings

1. **High — unrelated HTTP errors can qualify as governance denials.**

   `.ai/scripts/trusted_ci_qualification.py:121–138` accepts HTTP 409/422 and an unchanged target as a successful negative probe. A changed PR head can produce a SHA-mismatch refusal; malformed or otherwise invalid requests can produce validation errors. These do not prove the intended protection rejected the exact candidate. Recheck the complete snapshot immediately before mutation and validate a bounded, explicit policy-denial category. Stale fixtures, authentication failures and generic validation errors must remain unqualified.

2. **High — freshness fixtures are not bound to their claimed predecessor.**

   `.ai/scripts/trusted_ci_qualification.py:114–120` does not bind `prior_head`/`prior_base` to `prior_merge`’s actual parents. Moreover, `policy-transition` currently checks only that the base changed, duplicating `new-base` without establishing a policy transition. An unrelated historical App success plus invented predecessor fields can satisfy these checks. Read the predecessor commit and markers; verify its real parents, the unchanged counterpart for head/base probes, and an actual approved epoch/digest change for the policy probe.

3. **Medium — the incomplete-inventory test fails for the wrong reason.**

   `.ai/scripts/tests/test_trusted_ci_qualification.py:41–49` supplies identity 18 as both coding and merger actors. The merger-identity check rejects it before the empty case inventory is inspected. Use separately permitted identities and assert the inventory diagnostic. The complete qualification-driver flow also needs a controlled-host integration test rather than only helper and early-refusal tests.

## Validation Reviewed

- Ran structured source, test and documentation inspection, including completeness and trust-boundary tracing.
- Ran a read-only provenance probe using GitHub’s documented `workflow.yml@main` response shape after its correction: **PASS**, with exact SHA and workflow identity retained.
- Ran `okf.py affected`: reported no `knowledge/` bundle. The framework exemption applies; no bundle should be initialized.
- Inspected the installer diff: the only existing-code change was its external-provisioning notice.
- Found no TODO/FIXME/stub markers in the new production modules.
- Parent-reported portable, installer and HTTP checks were reviewed as reported evidence, not independently rerun.
- No current passing `lifecycle.py converge` evidence exists. Real disk-backed execution and hosted qualification remain outstanding. No MANUAL acceptance dispositions were supplied.

## Residual Risks

- The current disk-backed executor has not completed its real controller/isolation acceptance path.
- Independent authority/App provisioning and actual hosted positive/denial tests remain unperformed.
- The rejected privileged storage provisioning was removed; this review did not execute privileged setup or mutate remote state.
- The implementation changed during review. Fixes require focused re-review and a frozen-candidate gate before any completion claim.
