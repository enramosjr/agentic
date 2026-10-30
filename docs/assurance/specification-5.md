# Spec: assurance increment 5 — Python validation input profiles

Approved by human:enramosjr in chat, 2026-10-28 America/Chicago. L2; Python principal engineer; analyst role.
The user approved the revised defaults and specification and requested an implementation plan for approval before coding. The Python framework scope supersedes the earlier language-adopter proposal. This approval authorizes planning, not implementation.

## Problem and outcome

This framework validates Python scripts using unittest, a parallel unittest runner, and focused test invocations. Existing automatic Python input inference conservatively selects the entire repository inventory for unittest and the parallel runner; other commands can use explicit lifecycle inputs. There is no framework knowledge bundle or living framework capability to modify.

Increment 5 would make inspected input scopes reusable for focused framework checks. The proposed adapter exports a maintained command profile as explicit lifecycle input arguments and, for optional use in adopter capabilities, an existing-syntax Inputs line. It does not select tests or prove dependency completeness. Savings would be demonstrated only for a defined local scenario, without claiming measured project-wide speedup.

Python import closure alone is insufficient: tests launch scripts by path, copy script inventories, and read Markdown/configuration. Profiles therefore declare file dependencies and their source-based rationale, with author review remaining necessary.

## Users and scenarios

A framework maintainer requests a suggestion for the focused command `python3 -m unittest discover -s .ai/scripts/tests -p test_run_tests.py`. This is a proposed focused form of the documented discovery command, not a claim that this exact invocation has already passed. Its first candidate profile covers these four inspected repository files:

- `.ai/scripts/tests/test_run_tests.py`: selected test module.
- `.ai/scripts/tests/disk_tmp.py`: imported fixture temporary-directory helper.
- `.ai/scripts/scratch.py`: helper dependency.
- `.ai/scripts/run_tests.py`: subprocess script exercised by the test.

The test creates its child test suite in temporary storage; the runner discovers that generated suite. Its direct script file has no unittest main entry point, so `python3 .ai/scripts/tests/test_run_tests.py` MUST NOT be represented as an equivalent executing check.

The framework's full commands remain broad: `python3 .ai/scripts/run_tests.py -j 8` and `python3 -m unittest discover -s .ai/scripts/tests`. Changing the runner worker count changes concurrency, not coverage. The adapter declines to export a narrow scope for either full-suite family.

More complex checks are not silently reduced to imports. Assurance test fixtures copy all framework scripts, and architecture compatibility tests read `.ai/lifecycle.md`; lifecycle conformance reads roles, skills, hooks and documentation. Additional focused profiles require inspection of those dependencies before inclusion; they are not part of this initial pilot.

## Requirements

- R1: A standalone opt-in exporter MUST accept explicit command argv without executing or importing the command, test modules or their dependencies. Proposed interface: `python3 .ai/scripts/assurance_inputs.py [--json] [--extra-input GLOB]... -- COMMAND...`. Reading a suggestion MUST NOT edit sources/capabilities/profiles, create lifecycle evidence, run validation, alter statuses or grant trust.
- R2: The exporter MUST match only explicitly declared argv forms in maintained framework Python profiles. Each profile MUST declare an identifier, command argv, ordered repository-relative input globs and dependency rationale. Rationale MUST distinguish source imports/helpers, subprocess scripts, copied-file inventories and non-code repository reads where applicable. Profile matching MUST NOT silently normalize different test selections, options, interpreter argv or working directories into the same command. Profiles MUST be treated as declared scope, not approval credentials or proof of complete reads.
- R3: The initial supported focused profile MUST cover the discovery command and four repository files listed in Users and scenarios, from the repository root. Its scope MUST include all four even though the runner is not imported by the test. Newly introduced or changed repository dependencies MUST require profile review alongside the check change. Profile generation MUST NOT substitute a general AST-only dependency inference or claim that profile completeness is mechanically established.
- R4: Unknown command forms, broad full-suite commands, malformed/duplicate/ambiguous profiles, unsafe or unrepresentable globs, missing required literal files, paths escaping the repository and unsupported input boundaries MUST yield nonzero, a reason and no usable scope/declaration. Positive supplemental globs MUST be validated and appended after profile globs; negative supplements, absolute paths, parent traversal, empty and declaration-unrepresentable values MUST be rejected. Unresolved repository reads or known mutable application data outside the supported file inventory MUST NOT be silently classified as unrelated.
- R5: Successful text output MUST expose the profile ID, exact supplied argv, ordered globs, dependency rationale and review limitations, one copyable existing-syntax Inputs line, and explicit argv tokens for lifecycle `--inputs`. JSON MUST expose the same data as structured values, including the lifecycle-input token array. Both formats MUST NOT claim VERIFIED, automatic approval or complete read discovery. Failure output MUST provide a reason without a usable declaration or input-token array. Success MUST exit zero; refusal MUST exit nonzero. Output MUST preserve ordered-glob semantics and avoid executable shell-string construction.
- R6: The exporter MUST preserve automatic lifecycle inference, assurance matching/status/report schemas, receipt exclusions, gates and required validation coverage. It MUST NOT change the parallel runner, select fewer tests, reinterpret worker count as scope, narrow full-suite commands or automatically apply profiles. Refusal MUST recommend retaining the current scope. Explicit `**` MUST NOT be described as equivalent to omitted Inputs. An applied change of assurance command or ordered input declaration MUST require matching evidence under existing semantics; old evidence MUST NOT be migrated by this tool.
- R7: End-to-end validation MUST drive the public exporter and execute the actual focused runner-test command through existing lifecycle `run --inputs` and `reuse` in an isolated framework fixture. With a handwritten repository-read oracle, it MUST assert a passing real check, reuse after an unrelated repository source edit, and rerun required after changes to each of the four declared files. In a separate ordinary adopter fixture, explicit adoption of exported Inputs MUST yield VERIFIED after a passing obligation run, STALE after a declared input edit, retained freshness after a known unrelated edit and UNVERIFIED after an unmatched declaration change. The framework checkout MUST NOT acquire a knowledge bundle. Absent tests, unusable export or missing end states MUST fail validation.

## Acceptance

These are proposed NEW tests in `.ai/scripts/tests/test_assurance_inputs.py`, not existing tests or PASS claims. Direct invocation must fail if the file or named class is missing; an empty test run is not evidence. Implementation validation, including the real focused command below, awaits a human-approved spec and plan.

- R1: `python3 .ai/scripts/tests/test_assurance_inputs.py ReadOnlyTests` asserts sentinel commands/import side effects never execute and source, profile, capability and lifecycle evidence files remain unchanged. It uses non-executing file inspection to obtain a suggestion.
- R2: `python3 .ai/scripts/tests/test_assurance_inputs.py ProfileTests` validates profile identity, exact argv/root matching, unique definitions and explicit dependency rationale. Different selection, extra options and an unregistered interpreter form cannot reuse the pilot profile.
- R3: `python3 .ai/scripts/tests/test_assurance_inputs.py DependencyCoverageTests` asserts the four pilot dependencies against a handwritten source-derived oracle, specifically including the non-imported subprocess runner. Confirmed variants deleting the runner or helper from the profile must fail. It demonstrates that the nonexecuting direct-script form is refused.
- R4: `python3 .ai/scripts/tests/test_assurance_inputs.py RefusalTests` covers each refused boundary and invalid supplemental glob, full-runner concurrency variants, unrestricted discovery, positive supplement ordering and preserved diagnostics. An unsupported command never yields copyable narrowing output.
- R5: `python3 .ai/scripts/tests/test_assurance_inputs.py OutputTests` checks text/JSON identity, exact lifecycle token arrays and preservation of values containing spaces without shell execution, parses the Inputs line through the existing assurance parser, and asserts limitations plus absent failure candidates.
- R6: `python3 .ai/scripts/tests/test_assurance_inputs.py CompatibilityTests` asserts unchanged existing Python default inference, broad-suite meaning, assurance report/status/evidence/gate behavior and receipt exclusions. A synthetic profiled non-code read ensures the exporter preserves declared Markdown/configuration inputs rather than filtering by `.py`.
- R7: `python3 .ai/scripts/tests/test_assurance_inputs.py EndToEndTests` drives both required flows and asserts the real focused check executes at least one test. It checks changed/unrelated file outcomes against the independent oracle and no invoking-checkout modifications. Confirmed controls dropping a relevant dependency or using empty test discovery must break the acceptance test.

## Constraints

Python 3.9+ and standard library only; reuse the repository's unittest conventions and existing lifecycle/assurance input semantics. No new external tools, packages or network access. The initial catalog is limited to the single inspected pilot command, not mappings for every framework test. The plan may choose a small declarative storage format; it must implement the approved profile contract without adding arbitrary executable profile code.

Profiles describe repository-file inputs. They do not fingerprint arbitrary ignored files, external mutable data, OS mount information, environment variables, temporary storage or every subprocess runtime dependency. In particular scratch.py consults runtime mount/temp configuration; the adapter must report that boundary and cannot establish portability across runtime changes or strengthen the existing evidence model. Known unresolved application-data reads are grounds to decline narrowing; ambient platform/runtime assumptions remain explicitly outside this file-scope claim.

Profile changes and changes introducing new reads require normal code/input-completeness review. A profile is not self-authenticating or automatically refreshed. Output includes author-facing limitations; no new human-approval schema or trust grant is introduced. A profile's own definition is an additional input when an executing check actually reads it; this exporter does not implicitly change supplied target commands to consume profiles at runtime.

Framework mode remains without knowledge/. R-number IDs specify a framework feature, not a delta against a nonexistent capability. Working artifacts remain ignored under docs/assurance and uncommitted. Historical native/model evidence and consumed allocations remain unchanged: no new native/model evaluation, fixture trust grant, rescoring or historical record modification. No source edit, commit, push, PR, merge or new worktree is authorized for this task. Human spec approval and an approved plan are required before implementation.

## Non-goals

Language-adopter package adapters; automatic AST/import-graph completeness; runtime file-read tracing; a general Python command analyzer; all-test profile catalog; test selection from diffs; replacing or reducing the full gate; automatic Inputs edits or lifecycle inference changes; new evidence authority, gate or profile approval system; project-wide timing/benefit claims; changing old evidence or rerunning completed campaigns.

## Assumptions

The user has settled the language/context choice: this framework's Python code and validation commands, and approved D1–D5 below. Inspecting real test code identifies candidate repository reads, not runtime verification. The first pilot deliberately has a short, inspectable dependency list; later profiles must justify their own boundaries. Reuse in a controlled fixture establishes only its declared inputs and oracle, not arbitrary real-world dependency completeness.

## Open questions

None. The user approved the revised defaults and specification. The spec is ready for planning; implementation awaits approval of the resulting plan.

## Approved decisions

1. D1 — Maintained command profiles with explicit input globs and dependency rationale. Profiles require maintenance when reads change; import closure alone is insufficient.
2. D2 — One focused runner-test discovery pilot with its four inspected files. The full parallel runner and unrestricted discovery remain broad; additional mappings are separate reviewed changes.
3. D3 — Standalone exact-command exporter with text/JSON, lifecycle input argv, optional Inputs declaration and positive supplements. The primary caller is the framework maintainer; no framework capability bundle is needed.
4. D4 — Refuse unprofiled/unsupported boundaries with a reason and no usable candidate; preserve current scope and report runtime/ignored/external-read limitations.
5. D5 — Explicit adoption with existing evidence matching and gates, profile review when dependencies change, and fixture proof of lifecycle reuse and assurance freshness. This is a reusable declaration mechanism, not automatic dependency discovery or measured whole-project savings.

## Investigation evidence

See [investigation-5.md](investigation-5.md) for source-backed Python findings and command distinctions. Authoritative delivered increment 3 state remains in the leading updates of [handoff-3.md](handoff-3.md) and [implementation-3.md](implementation-3.md). The old roadmap supplied the input-adapter objective; the user's Python/framework instruction supersedes its proposed language order. Earlier unapproved increment 5 decisions are withdrawn.
