# Adopter-owned authority: registration preflight

This is an unfinished implementation candidate, not a production installer or
qualified enforcement service. The current build deliberately blocks both
`bootstrap_stage.py preview` and `apply` before authentication or side effects.
The user authorized continued source implementation and local tests while holding
privileged setup and live qualification. No trusted setup context is available.
The maintainer does not provide a hosted service or fund adopter infrastructure.

## Trust boundary

Run this stage only from a frozen bundle reviewed by the human administrator,
on a device or OS account inaccessible to coding agents. Another terminal in the
same agent-accessible account does not establish separation. Do not provide a
human GitHub token, browser profile or returned App private key to a coding agent.
The existing unrestricted coding session remains unverified.

The bundle is a candidate, not a signed release. The original
`authority-bootstrap-preflight.zip` predates the operational holds and is obsolete;
do not execute it. Newly exported held bundles include `authority_release.py`.
A future published installer must select and verify the approved release
automatically; this maintainer preflight does not establish that installed path.

## Resources and consent

The preflight creates one NEW private authority repository, one separate private
coding-fixture repository and five private Apps
owned by the selected user or organization. Administration, read-only verification,
issuance, coding and merging have different App identities. Private keys go directly into
the private authority's encrypted secrets. They are not printed or written into
workspace configuration. Metadata records which steps were reached.

The administrator approves normal GitHub registration and installation screens.
Install administration and reader Apps on the authority repository, and issuer,
coding and merge Apps on the separate coding fixture. Coding and merge Apps must
never have authority access; the preflight explicitly attempts that scope and rejects an
overbroad installation. Select only the named repository for each purpose.
No target branch rule or AWS/Azure resource is changed, and no enforcement is
activated. GitHub storage usage belongs to the selected account and its plan.

This early stage does not yet implement interrupted-run recovery, upgrade or
teardown. An interrupted operation must remain unverified; keep its resources for
trusted recovery rather than rerunning against or adopting an existing repository.
These missing lifecycle operations block completion of the overall feature.

## Future trusted preflight

The separate trusted backend requires Python 3.11+, the pinned optional dependencies
in `deploy/authority/requirements-auth.txt`, GitHub CLI authenticated as the human
administrator and a browser. App signing now stays in memory; it does not create
PEM files or invoke an OpenSSL child. The installed project client remains stdlib
Python 3.9+. No AWS or Azure account is needed for this preflight.

The future flow previews account ownership, repositories, App permissions and
cost ownership, then requires approval of the exact preview digest. Its CLI is
held in this build; there is no environment-variable override. Do not attempt
registration from the modifying environment.

Registration will use browser consent screens without copying credentials. It
uses a temporary loopback listener, single-use state and no webhook service.
After installation, the helper checks scope and verifies that non-administrative
Apps cannot mint an administrative token. A missing capability or rejected
callback fails the preflight; it must not be called a completed setup.

When live qualification is separately authorized, return only the non-secret JSON
result or failure category. Never return tokens,
private keys, callback URLs/codes, browser data or credential files to the coding
environment. A successful registration result still says `state: setup` and
`enforcement_qualified: false`.

## Remaining qualification

Real GitHub consent is pending. Local HTTP tests use a simulated GitHub exchange;
they verify callback handling, not GitHub's registration support. The dedicated
Podman WSL2 disk/OCI probe passed, but GitHub-hosted execution remains unqualified.
The user has no AWS/Azure test accounts, so both cloud paths remain unqualified.
The complete adopted spec, installed launcher, protection/recovery flow and final
frozen-candidate gate are not complete.
