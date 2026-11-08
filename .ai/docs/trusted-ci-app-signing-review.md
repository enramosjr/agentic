# In-memory App signing scoped review

Status: No findings in this correction. Complete bootstrap integration and hosted
qualification remain unfinished; no overall feature or deployment approval.

The independent read-only reviewer applied the Python principal engineer persona
to secret containment, cryptographic validation and dependency boundaries.

Signing uses bounded RSA keys in memory, fixed RS256 claims and sanitized parse
failures. No PEM file or signer subprocess remains. Lazy cryptography imports
preserve the installed stdlib-client boundary. The backend dependency file is in
the bootstrap inventory, documented for Python 3.11+, and installed before optional
signing tests in CI.

Two tests verify generated PKCS1/PKCS8 signatures and reject EC, weak RSA and
malformed keys. They forbid temporary signer files and the old signer child.
The original tests failed before implementation and passed afterward.
`adopter-app-signing` passed at tree `5948d1f` with real cryptography/PyJWT and
synthetic keys. No real App credentials or API calls were used. The reviewer
inspected the tests without rerunning them. `adopter-auth-ci-contract` also passed
at that tree; the expanded remote matrix has not run.

Complete bootstrap wiring, credential staging and hosted qualification remain
unverified. No convergence or manual requirement closure was established.
