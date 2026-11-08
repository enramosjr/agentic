# Credential-free cloud infrastructure rendering

Status: Local rendering is implemented and scoped-reviewed. The adopter-owned
authority feature and hosted AWS/Azure execution remain unfinished and unqualified.

AGENTIC maintains the templates and adapter code. Adopters select their own AWS
account or Azure subscription and own their resource usage. No AGENTIC-operated
hosting service or shared infrastructure subsidy is involved.

## Available operation

`deploy/authority/render_cloud.py` generates an AWS CloudFormation or Azure ARM
template, an ownership/cost preview and a checksum manifest in a NEW directory.
It uses Python 3.9+ and the standard library. It needs no account login, provider
CLI, metadata service, administrator credential, GitHub token or model service.
Rendering does not deploy resources or establish enforcement.

Run from the optional deployment source package, which is separate from the
recursively installed `.ai/` tooling. These examples use synthetic identifiers;
their output is for inspection, not deployment:

```text
python3 deploy/authority/render_cloud.py --adapter aws --account 123456789012 --region us-east-2 --authority example/authority --output aws-render
python3 deploy/authority/render_cloud.py --adapter azure --account 11111111-2222-3333-4444-555555555555 --region eastus --authority example/authority --output azure-render
```

The optional `--deployment` sets the managed resource prefix; otherwise it is
derived from the account, region and authority selection. `--branch` defaults to
`main`. Federation is limited to that authority repository and branch. The tool
rejects invalid inputs before creating output and refuses to overwrite an existing
directory. It writes the manifest after the payloads and records their SHA-256
checksums. Checksums establish integrity, not authenticity or provider acceptance.

Successful output always states `unqualified` and `enforcement_qualified: false`.
It is not a version-2 deployment or execution receipt and cannot authorize a merge.

## Preview interpretation

The preview names the cost owner, billable resource types and proposed job limits.
The limits describe the intended executor configuration; rendering does not
establish them. There is no hard billing cap. The Azure template includes persistent
NAT/public-IP resources, which can incur costs while idle if deployed. Future
verification jobs also consume compute, disks, storage and network resources.

Trusted provisioning must authenticate the selected account, preview actual
changes, collect consent, provision and read back resources, and complete live
qualification before the adapter is advertised as enforced. The current partial
provider primitives and offline checks do not complete that flow. No manual key
copying or hand-assembled cloud configuration is an accepted onboarding fallback.

## Executed checks

- Real subprocess CLI tests for both providers, payload integrity, overwrite
  refusal and invalid-input rejection: `python3 .ai/scripts/tests/test_authority_render.py`
  → PASS, 3 tests. These are local rendering checks, not hosted acceptance groups.
- [AWS cfn-lint](https://github.com/aws-cloudformation/cfn-lint), pinned at 1.60.0:
  ledger `adopter-aws-template-lint` → PASS after fixing W3011. Shared OIDC
  retention now covers both deletion and replacement. The focused regression
  recorded RED followed by GREEN.
- [Azure Bicep](https://github.com/Azure/bicep/releases/tag/v0.49.2), version 0.49.2:
  ARM decompilation and Bicep compilation → PASS, ledger labels
  `adopter-azure-template-decompile` and `adopter-azure-template-build`.
- The Bicep binary's SHA-256 matched the official release asset metadata before
  execution: `acfff0453c9bcf442aa97103acbcd845ef366634e6ea2a2ba5734514409ce9c3`.

Exact executable paths, arguments and source snapshots are recorded in Git scratch.
The Windows validator environment lacked a required binary dependency; validation
used an isolated Python 3.14 environment in the dedicated Podman WSL2 backend.
This changed no backend OS packages and used no cloud credentials.

## Current blockers

The user has no trusted setup context and no AWS/Azure test accounts available.
Privileged GitHub setup, hosted execution, effective IAM/RBAC checks and complete
qualification cannot be performed here. The remaining implementation and final
feature gate are not complete. Local hooks continue to provide feedback; they do
not replace the independent authority.
