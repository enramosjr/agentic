# Review Report

## Verdict

Changes requested — most reported defects are corrected, but the original denial-evidence finding remains partially unresolved. This follow-up does not approve completion or deployment.

## Scope

Focused re-review of the previously reported fixes: qualification denial classification, snapshot freshness, predecessor bindings, policy-transition evidence, negative execution reports, fixture mutation identities, inventory test, matrix publication and effective isolation checks.

## Persona Applied

Python principal engineer. The review focused on boundary validation and whether negative tests establish the claimed failure reason.

## Findings

1. **High — generic merge refusal still permits qualification for an unrelated gate.**

   `.ai/scripts/trusted_ci_github.py:35–37` accepts HTTP 405 with “Pull Request is not mergeable” as `merge_policy`. The probe establishes conflict-free inputs, passing status checks and one independent review, but does not establish every other applicable gate. For example, `.ai/scripts/trusted_ci_deployment.py` accepts review counts greater than one and requires resolved threads; `.ai/scripts/trusted_ci_qualification.py:96–111` neither establishes the required approval count nor verifies resolved threads. A negative fixture blocked by those conditions can therefore qualify a missing-check denial without proving that the intended check blocked it.

   Require a denial specific to the intended obligation, or establish every other effective gate before accepting a generic refusal. Unsupported or uninspectable gate conditions must leave the probe unqualified.

The other originally reported fixes are satisfactory by focused source inspection:

- Exact snapshot rereads now reject moved fixtures before and after negative updates.
- Actual predecessor parents and unchanged counterpart revisions are checked.
- The policy-transition case requires a changed epoch and policy digest.
- Negative cases require trusted failed-obligation evidence and reviewed mutation bytes.
- Distinct fixture identities and the corrected inventory diagnostic remove the earlier vacuous test.
- Per-PR publication survives another PR’s matrix failure.
- Effective isolation checks precede candidate execution.

## Validation Reviewed

- `lifecycle.py reuse` for the qualification test command: **RERUN**, no matching ledger entry.
- `python -m unittest discover -s .ai/scripts/tests -p test_trusted_ci_qualification.py`: **PASS**, six tests.
- Inspected the corrected controller, sandbox, GitHub adapter, qualification flow and fixtures.
- No remote mutations or privileged infrastructure operations were performed.
- No passing `lifecycle.py converge` evidence exists. R3’s current disk-backed execution and R9’s hosted enforcement qualification remain outstanding; no completion approval is given.
- No MANUAL acceptance dispositions were supplied.

## Residual Risks

The current disk-backed executor and hosted authority have not completed their required live acceptance paths. Controlled-host tests establish application wiring, not actual GitHub enforcement.
