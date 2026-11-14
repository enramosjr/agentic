# Credential-free cloud infrastructure rendering

Local rendering is available. The adopter-owned
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

## Validation

`python3 .ai/scripts/tests/test_authority_render.py` checks both provider CLIs,
payload integrity, overwrite refusal and invalid-input rejection locally.
Template validation uses AWS cfn-lint and Azure Bicep. These checks do not prove
effective IAM/RBAC, hosted execution or complete qualification. Those require
separately authorized trusted setup and adopter-owned test accounts. Local hooks
continue to provide feedback; they do not replace the independent authority.
