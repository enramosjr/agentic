# Native setup and first-installation scoped review

Status: Findings resolved within this scope. Overall setup, Review, Verify and
Ship remain unfinished; no deployment or enforcement approval is granted.

The independent reviewer used the Python principal engineer persona and read-only
inspection. The reviews covered native configuration ownership, retained software
recovery and the first-installation exception. Tests were not rerun by the reviewer.

## Native configuration recovery

The initial review found that reconstruction could lose the prepared software
revision after publication but before registry repinning. The correction retains
operation/sequence, preview and plan digests, and exact revision before publication.
Reconstruction authenticates the commit's sole parent, message, approved inventory
and preservation of unrelated files. Recovery reuses that commit. A phase check
rejects the old software revision after registry repinning.

Follow-up found no remaining defect in that correction. Parent ledger
`adopter-native-setup-owner` passed at tree `93aa7b8`, nine methods, including actual
fixture lost-acknowledgement recovery and deliberately bypassed proof/phase checks.

## First installation

`InitialAuthority` permits creation and initial software publication only. The
trusted caller supplies the complete preview and its approval; publication does
not regenerate a timestamped preview after approval. Its protected journal retains
the creation response and prepared commit. Unknown repository creation cannot be
retried or recovered by repository name. Existing registry state excludes this
exception; it supplies no rules, credentials, repair or activation capability.

The independent review found a missing cross-field invariant in prepared recovery:
an internally consistent substituted plan/commit was not compared with the original
approved release. The regression failed with `Refusal not raised` before correction.
The complete desired manifest is now compared with the original preview before
recovery. The same regression passed afterward; all seven methods passed under
`adopter-initial-setup` at tree `bbad376`. Follow-up found no remaining defect in this
correction. A later held-entry signature simplification forwards the approved
preview directly; the public hold still precedes all I/O. The independent
follow-up found no defect in that forwarding change. The integrated backend and
33-method model SDK checks subsequently passed on tree `c527f51`.

The parent then reproduced approval expiry during durable intent persistence:
repository creation had occurred before refusal. Reauthentication now occurs
immediately before the creation POST, with a final clock check after identity
reads. The same regression passed, and all eight initial-installation methods
passed at tree `7a68fdb`. This later focused result covers the setup-only change;
the earlier integrated result is not relabeled as testing that change.
Independent follow-up found no defect in the expiry correction; the reviewer
inspected the source and regression without rerunning it.

## Limits

These are local Git API fixtures with actual private journal storage, not a live
GitHub setup. Protected storage does not attest absence of a same-user modifying
process. Complete orchestration, credential staging and hosted qualification remain
incomplete. No acceptance convergence or manual requirement closure was established.
