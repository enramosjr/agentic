# Review Report

## Verdict

Approved narrowly for the inspected corrections. Overall onboarding, worker
integration and live provider qualification remain unfinished and unapproved.

## Scope

Independent read-only review of AWS immutable stack identity and operation-specific
completion, Azure request-bound group recovery/readiness, and their direct fixtures
in `deploy/authority/cloud.py` and `deploy/authority/cloud_setup.py`.

## Persona Applied

Python principal engineer: boundary validation, partial-effect recovery and bounded
observation. No live operations or tests were run by the reviewer.

## Findings

The initial review requested three corrections:

- Updates must target the approved AWS stack ARN. Recovery must retain that ARN
  and the new request token, separately from an explicitly approved no-op.
- Completion must come from a successful root-stack event for that token/stack,
  followed by consistent terminal readback. An old COMPLETE status plus a matching
  IN_PROGRESS event cannot establish completion.
- Azure group creation and deployment submission need separate durable phases.
  A lost group-create acknowledgement must recover only a request-tagged group,
  then submit the uniquely named deployment once.

These corrections were inspected without remaining findings. A subsequent
readiness regression caught `group-ready` being persisted during Creating. The
source now keeps `group-started`, polls with guards/deadline until Succeeded, and
rechecks the same closed proof before submission. The reviewer inspected that
delta without further findings.

AWS's [UpdateStack contract](https://docs.aws.amazon.com/AWSCloudFormation/latest/APIReference/API_UpdateStack.html)
supports unique stack IDs; its [StackEvent contract](https://docs.aws.amazon.com/AWSCloudFormation/latest/APIReference/API_StackEvent.html)
defines the operation request token.

## Validation Reviewed

The parent recorded the three cloud boundary failures RED, then the 10-method
module GREEN over synthetic provider endpoints and real protected journals. The
additional group-readiness regression reproduced RED; its GREEN was pending when
this scoped report was issued. Current integrated checks remain required.

`okf.py affected` reports no bundle, consistent with framework mode. No
`knowledge/` initialization, convergence closure or MANUAL acceptance was made.

## Residual Risks

Deployment readback is explicitly `provisioned-unqualified`. It does not prove
effective IAM/RBAC, credential isolation, runtime isolation or supported live
adapter behavior. Privileged setup and live qualification remain blocked, and
enforcement remains inactive.
