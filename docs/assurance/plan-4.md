# Plan: Attested evidence in the assurance report (increment 4)

Spec: specification-4.md (0.1.0-draft, approved, R1-R9). Tier L2, kind feature. Branch `claude/assurance-increment-4` at `055b62f` (main, includes increments 1 and 6).
Persona: Python (advisory). Untracked working file: the repository holds no documents and `docs/` is gitignored. Framework source has no `knowledge/`.

## Findings that shape the design

- `assurance.py`: `parse()` ignores unknown bullets (only `Verify:` and `Inputs:` are scanned via `^\s+[-*] Kind:(.*)$` plus the `SCENARIO` regex). `evaluate()` builds results through `result()` with exactly the keys `id, capability, status, basis, evidence, reason`. `render()` and `document()` are pure. `exit_code(results, strict, broken)` looks only at statuses and `broken`.
- `lifecycle.py cmd_assure`: `broken = bool(diagnostics)` comes from `requirements()` only, before `evidence()` diagnostics are appended, so evidence diagnostics never fail the run. `evidence()` skips the committed file whose stem equals the active task id, then adds the state under `f'{active}.json'`; attestation reading mirrors that.
- `ref_hash`: for `.md`, `sha256(body(read_text()).strip())` with frontmatter stripped; otherwise `sha256(read_bytes())`. `read_verdict` returns the first non-blank line after `^##\s+Verdict\b` (case-insensitive). `cmd_stage review` checks `.lower().startswith("approved")` at L2/L3 only; at L1 it records `ref` and `sha256` without checking the verdict. `sections` lowercases `##` headings; `find_section` matches by `startswith`. The `converge_problem` citation regex is `(?<![\w-]){re.escape(rid)}(?![\w-])` over the `validation reviewed` section.
- `brownfield.sha(text)` is `sha256(text.encode('utf-8'))`; `Block.raw` is the exact text from the `- ID:` line through the last non-blank line and keeps every indented sub-bullet. Any edit inside the block, including adding `Accept-risk:`, changes the digest; edits outside do not.
- `ledger.audit(entries)` returns `[]` for a missing ledger and flags non-list ledgers, non-object entries, output keys and unknown keys.
- `tests/test_assurance.py` `Case` copies `SCRIPTS.glob('*.py')` into a temp git repo (a new module is picked up automatically), runs `okf.py init` (records land in `knowledge/history/lifecycle`). `ReportFormatTests` asserts exact item and `evidence` key sets, so new keys must be conditional. `.ai/lifecycle.md` has `## Assurance status`, checked by `test_lifecycle_conformance.Assurance`.

## Design decisions

**D-a. Review helpers without an import cycle.** New stdlib-only module `.ai/scripts/review_evidence.py` (imports `hashlib`, `re`, `pathlib`) holding copies of `body`, `sections`, `find_section`, `ref_hash`, `read_verdict`, `verdict_of` and the citation scanner. `lifecycle.py` is not refactored; `assurance.py` imports `review_evidence`, not `lifecycle`. A parity test (`test_review_evidence.py`, `ParityChecks`) compares both implementations over a corpus (frontmatter or not, a frontmatter-only edit, CRLF, `## verdict` casing, `## Verdicts`, blank lines after the heading, a missing verdict, a non-`.md` ref), checks a citation table (`CALC-R2`, `CALC-R2-x`, `xCALC-R2`, `CALC-R20`, `CALC-R2.`, `CALC-R2@<hex>`) against the converge regex, and asserts `inspect.getsource(lifecycle.converge_problem)` contains the exact regex literal. `ImportGraphChecks` asserts `assurance.py` and `review_evidence.py` contain no `import lifecycle`.

**D-b. `Accept-risk:` grammar.** `RISK = re.compile(r'^\s+[-*] Accept-risk:(.*)$')` added to `parse()`'s kind tuple, so "line after a scenario" and "duplicate" handling applies unchanged. Validation runs after the scan loop and before the `'Verify' not in found` branch, so a malformed line makes an undeclared block INVALID too. Value grammar: (1) a first token `YYYY-MM-DD` accepted by `datetime.date.fromisoformat`, else `Accept-risk: date must be a valid YYYY-MM-DD`; (2) `\s+by\s+((?:human|decision):\S+)`, else `Accept-risk: needs 'by human:<id>' or 'by decision:<ADR>'`; (3) `\s+[-–—]\s+(\S.*)$` as the reason, else `Accept-risk: needs a reason after ' - '`. Also INVALID: `duplicate Accept-risk: line`, `Accept-risk: line after a scenario`. `Obligation` gains defaulted fields `risk: tuple = ()` (`(until, by, reason)`, set only on a valid parse) and `block_sha256: str = ''` (set in `requirements()` from `brownfield.sha(block.raw)`).

**D-c. Notes.** `assurance.attest(...)` returns `(attested_by_id, notes)`. Notes are not appended to `diagnostics`, and `cmd_assure` computes `broken` before notes exist, so exit codes cannot change. JSON: a top-level `notes` key (sorted, unique) only when non-empty; text: `note: <text>` lines after `diagnostic:` lines. A note arises only for a MANUAL requirement that a readable review report currently cites, because only then is an attempt observable: `attestation: <ID>: <record>: not honored (<reason>)` with reasons `record failed ledger audit: <first problem>`, `review <ref> changed since it was recorded`, `verdict is not Approved: <first 80 chars>`, `requirement changed since attestation (current block sha256 starts <12hex>)`, `malformed pin <text>`. Once an id has an honored attestation, its notes are suppressed. A candidate review stage needs a dict with str `ref`, `sha256`, `at`; the ref must be relative and resolve inside `root`, else it is skipped silently (traversal guard). Pin rules: per boundary occurrence, a following `@` then `[0-9A-Fa-f]{12,}(?![\w-])` is a pin, anything else after `@` is malformed (not honored, with a note). Precedence in one report: matching pin (`pinned: true`), then an unpinned occurrence (`pinned: false`), then a mismatch (note). A match is `block_sha256.startswith(pin.lower())`.

**D-d. Rendering and conditional keys (R9).** `evaluate()` and `result()` are untouched. New `assurance.annotate(root, records_dir, state, obligations, results, today=None) -> list[str]` mutates only the items it extends, so inputs absent means byte-identical output. `attested` (only for a MANUAL requirement with an honored attestation): `basis: "attested"`, `judgment: true`, `record`, `review`, `review_sha256`, `at`, `intent_approved_by` (str or null), `pinned`, `reason` (see D2). `risk_acceptance` (only STALE, FAILED or UNVERIFIED with a valid `risk`): `{basis: "declared", until, by, reason, state}`, `state` `active` if `until >= today (UTC)` else `expired`. Text lines under the requirement line, indented 4 spaces: `judgment (attested, not verified): approved review <ref> (sha256 <12hex>) at <at>; recorded in <record>; intent approved_by <claim|none recorded> (claim); <reason>` and `risk acceptance (declared, not verified): <active until|expired on> <until>, claimed by <by> - <reason>; status still <STATUS>`. `render(results, diagnostics, notes=())` and `document(results, diagnostics, base=None, notes=())` add `notes` only when non-empty; `schema_version` stays 1; top-level `basis` is never `attested`. Golden test: normalised text, `--json`, `--strict` and `--changed --base HEAD` output of a fixture captured BEFORE any change (Step 1), embedded in `CompatibilityTests`, passing before and after.

**D-e. Fixtures.** `Case.reviewed(text, name, cited, approved_by=None)` helper in `test_assurance_attested.py` (reusing `from test_assurance import Case, CAP, RECORDS, SCOPED`): write the report to `reviews/<name>.md` (names without the requirement id or TODO-like words, since `scan_problem` runs), then `task(new=True)`, `stage intent --note`, `stage plan --note`, `stage review --ref reviews/<name>.md --note`. At L1 a "Changes requested" report is recordable. Committed-record source: `commit('x')` then `task(new=True)`; active-state source: do not switch task. Clock: stage `at` has 1-second resolution, so `retime(record, at, approved_by=None)` rewrites `stages.review.at` and `stages.intent.approved_by` in the record JSON (neither is covered by the ledger or `ref_hash`). Risk expiry uses `2000-01-01` (expired) and `2999-12-31` (active); the boundary day is tested by calling `assurance.annotate(..., today=date(...))` directly. STALE: edit `src/calc.py`; FAILED: break `src/calc.py` and `assure --run`; UNVERIFIED: no evidence.

**D-f. Pin source.** `block_sha256` is the full 64-hex digest; a 12+ hex pin is a case-insensitive prefix match. A pin copied from the fixture block matches; adding an `Accept-risk:` line to that block gives the mismatch note and no `attested`; edits outside the block leave the pin valid.

## Steps (test-first; each ends with a failing-closed check)

0. **Lifecycle setup.** Intent is recorded (approved by `human:enramosjr`). Record `stage plan --ref docs/assurance/plan-4.md`. Check: `git status` shows no tracked changes; `git diff --stat -- .ai/scripts` is empty (baseline for the golden).
1. **Golden capture, then red tests** in new `.ai/scripts/tests/test_assurance_attested.py`. (1a) With scripts unmodified, build the golden fixture with a throwaway driver in the scratchpad: VERIFIED, STALE, FAILED, UNVERIFIED, MANUAL, UNDECLARED, INVALID requirements, an Approved review citing only a non-MANUAL id, and a record with no citations; paste the normalised outputs (normalise `head=[0-9a-f]{7}` and `at=...Z`) into `CompatibilityTests`. (1b) Write the nine classes named in the spec's Acceptance filters, docstrings citing R ids: `SourceTests` (R1), `FailClosedTests` (R2: edited report, deleted report, "Changes requested", uncited id, audit-failing record, `../` and absolute refs, unreadable record, note suppression), `PinTests` (R3), `LabelTests` (R4: exact key set, basis, judgment, `intent_approved_by`, text prefix, id not repeated), `NoUpgradeTests` (R5), `RiskSyntaxTests` (R6), `RiskSemanticsTests` (R7), `ExitCodeTests` (R8), `CompatibilityTests` (R9, plus `schema_version == 1`, no files written, `okf.py validate` exit 0 with attestation and `Accept-risk:` present). Check: `lifecycle.py redgreen red -- python3 -m unittest discover -s .ai/scripts/tests -p test_assurance_attested.py` fails (only the golden tests may pass); `test_assurance.py` passes as a baseline.
2. **`review_evidence.py` plus parity tests** (R1, R2, R3). Red first: `lifecycle.py run parity-red -- python3 -m unittest discover -s .ai/scripts/tests -p test_review_evidence.py` fails with an import error. Implement `body`, `sections`, `find_section`, `ref_hash`, `verdict_of`/`read_verdict`, `load_review(path) -> (digest, text)` and `citations(text, rid)`. Check: the same command passes.
3. **Parser** (R6, R7). Edit `assurance.py`: `RISK`, grammar, `Obligation.risk` and `block_sha256`. Check: `-k RiskSyntaxTests` green; `test_assurance.py` stays green.
4. **Attest** (R1, R2, R3, R5). `attest(root, records_dir, state, manual_obligations)` iterates sources like `evidence()`, audits with `ledger.audit(record.get('ledger'))`, skips non-dict and unreadable records silently, applies D-c, and chooses the newest by `(at, record name)`; only declared, valid MANUAL obligations are passed in. Check: `-k SourceTests`, `-k FailClosedTests`, `-k PinTests`, `-k NoUpgradeTests` green.
5. **Annotate and render** (R4, R7, R8, R9). `annotate(...)` handles MANUAL attestation, risk acceptance and notes; `render` and `document` get conditional `notes`. Check: `-k LabelTests`, `-k RiskSemanticsTests`, `-k CompatibilityTests` green.
6. **Wire `cmd_assure`** (R8, R9), the only edit to `lifecycle.py`: hold `state = load(root)` and `records_dir` in variables and pass both to `assurance.evidence`; after the `reasons` loop call `notes = assurance.annotate(root, records_dir, state, obligations, results)` (`obligations` is already the `--changed` filter); pass `notes` to `document` and `render`; leave `exit_code(..., broken)` and `assure --run` untouched. Check: `-k ExitCodeTests` green, including `--changed` filtering.
7. **Documentation** (supporting, no R id; see D3). Extend `.ai/lifecycle.md` `## Assurance status` with a short paragraph (citation and `@hex` pin, `Accept-risk:`, the `judgment (attested, not verified)` label, notes) and add the terms to `test_lifecycle_conformance.Assurance`. Check: that test passes. Dropped if D3 is answered "no".
8. **Mutation proof** (AGENTS.md §8.6). A throwaway scratchpad `mutate.py` copies `.ai/scripts` to a scratch dir, applies one replacement, runs the named class there, touches nothing in the tree; confirm each mutation is applied before trusting a pass. Each must make its class fail; the unmutated tree must pass:

   | Class | Broken variant |
   |---|---|
   | SourceTests | `max` becomes `min`; skip the active-state source |
   | FailClosedTests | skip the hash compare; skip the verdict check; skip `ledger.audit`; skip the inside-root guard |
   | PinTests | always honor on mismatch; compare against a different digest; always `pinned: False` |
   | LabelTests | `basis` becomes `"declared"`; drop `judgment`; change the text prefix; print the id |
   | NoUpgradeTests | attach to all statuses; set status to `VERIFIED` when attested |
   | RiskSyntaxTests | skip the duplicate check; accept an empty reason; skip `fromisoformat` |
   | RiskSemanticsTests | `>=` becomes `>`; always `active`; also attach to MANUAL |
   | ExitCodeTests | append notes to `diagnostics` before `broken`; treat expired as exit 1 |
   | CompatibilityTests | always emit `notes: []`; add an `attested: null` key; change `schema_version` |
   | ParityChecks | change `\w-` to `\w`; drop `.strip()` in the digest |

9. **Validate and verify.** Close the retrospective (`lifecycle.py learn` / `retrospect`), independent review with the `reviewer` subagent (save its report untracked, e.g. `docs/assurance/review-4.md`), `stage review --ref`, `lifecycle.py converge docs/assurance/specification-4.md`, the full suite through `lifecycle.py run`, then `stage verify`.

## Requirement map

| Req | Steps | Check that fails closed |
|---|---|---|
| R1 | 2, 4 | `-k SourceTests`; `ParityChecks` |
| R2 | 2, 4 | `-k FailClosedTests` |
| R3 | 2, 3, 4 | `-k PinTests`; block digest checked in Step 3 |
| R4 | 5 | `-k LabelTests` |
| R5 | 4, 5 | `-k NoUpgradeTests` |
| R6 | 3 | `-k RiskSyntaxTests` |
| R7 | 3, 5 | `-k RiskSemanticsTests` |
| R8 | 6 | `-k ExitCodeTests` |
| R9 | 1, 5, 6 | `test_assurance.py` unmodified; `-k CompatibilityTests` (golden from Step 1) |

## Validation commands

Run each through `lifecycle.py run LABEL -- CMD`, with `lifecycle.py reuse` before repeating.

- Focused loop: `python3 -m unittest discover -s .ai/scripts/tests -p test_review_evidence.py`; `... -p test_assurance_attested.py -k <Class>` for each of the nine classes; `... -p test_assurance.py`.
- Once, when edits are complete: `... -p test_lifecycle_conformance.py`; `python3 .ai/scripts/run_tests.py`; `python3 .ai/scripts/assurance_demo.py` (the unchanged demo still passes).
- Then `lifecycle.py stage verify`. `lifecycle_eval.py run` on a real agent is not required: no tier or stage rule changes.

## Risks

- Parity drift from duplicated helpers: mitigated by the corpus parity test and the `getsource` assertion.
- Pin discoverability: the 12-hex prefix is shown in the unpinned `reason` and the mismatch note; no new CLI (non-goal).
- Adding `Accept-risk:` invalidates a block's pinned attestations: intended (spec Assumptions); documented in Step 7.
- L1 fixtures edit `approved_by` in JSON: the code reads only `stages.intent.approved_by`, so the helper is faithful.
- Midnight flake: avoided by injecting `today` for the boundary day and using far dates for CLI tests.
- A failing-audit record that an Approved report cites: `evidence()` already prints an `... ignored` diagnostic that does not fail the run; the new note adds a second line, which is acceptable.

## Decisions (settled 2026-10-27: user chose the recommended default for D1, D2 and D3; spec wording amended accordingly)

- **D1 (R2 acceptance vs R9).** The spec's R2 says a deleted report gives "only a note". A deleted report leaves no observable citation, and any note would break R9's byte-identical output for repositories whose old records reference gitignored paths (this repository's own case). Default: no note for a deleted report; the test asserts no `attested` and output identical to baseline. Notes appear only where a citation is observable. Amends R2's wording.
- **D2 (R3 vs R4 key set).** R3 requires a reason for unpinned citations, but R4 lists eight keys. Default: a ninth key `reason`, always present on `attested`, with the exact key set asserted in `LabelTests`. Amends R4 to list it.
- **D3 (documentation).** Step 7 edits the existing committed `.ai/lifecycle.md` and its conformance test, as increments 1 and 6 did. The spec's Constraints say "no committed documents", which could be read to cover it. Default: keep Step 7, because `.ai/lifecycle.md` is existing shipped framework documentation, not a new document. Skip it if the user disagrees.
