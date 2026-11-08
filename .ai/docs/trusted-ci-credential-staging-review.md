# Review Report

## Verdict

The scoped freshness finding is resolved. Complete onboarding, workflow integration
and hosted qualification remain unfinished; no overall approval is granted.

## Scope

Independent read-only review of `CredentialStaging`, pinned credential consumers,
credential-proof admission, and native-session/artifact/SDK fixtures.

## Persona Applied

Python principal engineer. Applied authorization freshness, preservation of existing
secrets, secret containment, and authenticated consumer evidence.

## Findings

The review found that CLI identity readback could consume the remaining operation
window after its initial authorization check. A regression advanced the clock during
that read; one synthetic secret write occurred before refusal. The guard now
reauthenticates after CLI/journal readback and checks deployment expiry before the
write. The same regression passed afterward.

A separate inventory regression caught case-insensitive name collisions. Inventory
comparison now canonicalizes names, preserving existing secrets for explicit repair.
This follows GitHub's [secret-name rules](https://docs.github.com/en/actions/reference/security/secrets).

Follow-up found no remaining defect in these corrections. Consumer acceptance binds
the closed role, exact run/attempt/job/artifact, current configuration operation,
intent/nonce, and a domain-separated HMAC made with the actually loaded value.

## Validation Reviewed

Parent ledger `adopter-credential-staging` passed on tree `0c2c5a2`: ten SDK methods
with actual private journals, generated RSA signatures, encrypted model records and
synthetic Git/Actions/CLI endpoints. The expiry and inventory corrections have
actual RED/GREEN evidence. Consumer tests cover value mismatch, nonce substitution,
and recovery of an uncertain write without rewriting it.

The reviewer inspected source/tests without rerunning them. `okf.py affected` reports
no OKF bundle, consistent with framework mode. No convergence or manual acceptance
closure was established.

## Residual Risks

Artifact-to-job attribution relies on the pinned workflow's closed producer roles.
Cached progress does not replace fresh activation evidence, and GitHub secret writes
do not provide a CAS guarantee against out-of-band administrators. Full registration,
workflow composition and hosted qualification remain unfinished. Public holds remain
intact; no real secret, cloud or provider mutation was performed by these fixtures.
