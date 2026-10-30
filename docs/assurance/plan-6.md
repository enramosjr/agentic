# Plan: Assurance STALE demo (increment 6)

Spec: specification-6.md v0.2.0 (approved, R1-R7). Tier L2, kind feature. Base `4031aab`.
Persona: Python (advisory): subprocess `shell=False` with timeouts, `try/finally` cleanup, Python 3.9 compatibility, stdlib only. Framework source has no `knowledge/`; nothing is added under `docs/`; this plan is an untracked working file.

## Design decisions

1. **Module `.ai/scripts/assurance_demo.py`**, importable and runnable. Imports only the stdlib and sibling `scratch` (`require_disk`). It never imports `lifecycle`, `assurance` or `ledger`, so the real CLI is the only source of statuses (R3).
2. **Own builder, no shared test code.** `build(repo, prepare=None)` (about 25 lines mirroring `tests/test_assurance.py` `Case.setUp`): copy `SCRIPTS.glob('*.py')` into `repo/.ai/scripts`, `git init -q`, `okf.py init`, `knowledge/project/sync-ignore` = `*\n`, files `check.py`, `src/calc.py`, `notes.txt`, capability `knowledge/capabilities/demo.md` (frontmatter `namespace: DEMO`, `DEMO-R1` with `- Verify: \`python3 check.py\`` and `- Inputs: \`check.py\` \`src/**\``), `okf.py reindex`, commit with `git -c user.name=Demo -c user.email=demo@example.invalid`, then `lifecycle.py tier L1 --reason "assurance demo" --new`. `test_assurance.py` is untouched.
3. **Disk-backed temp base.** `_base()` uses `tempfile.gettempdir()` if `scratch.require_disk` accepts it, else `$XDG_CACHE_HOME or ~/.cache` + `/okf-tests`; if that fails too, exit 1 with the message. `run(base=...)` overrides.
4. **Guaranteed removal.** `run()` does `tempfile.mkdtemp(prefix='assurance-demo-', dir=base)`, and the whole body sits in `try/finally: shutil.rmtree(..., ignore_errors=True)` with a stderr warning if the directory survives. `main()` installs a SIGTERM handler raising `SystemExit(143)`. No `--keep`.
5. **Session.** `session.lifecycle(*args)` runs `[sys.executable, repo/.ai/scripts/lifecycle.py, *args]`, `cwd=repo`, `capture_output`, `timeout=120`, `shell=False`, env = `os.environ` + `PYTHONDONTWRITEBYTECODE=1` minus `_AGENTIC_LIFECYCLE_RUN_ROOTS`, `OKF_AUTONOMOUS`, `LIFECYCLE_GUARD` and every `GIT_*`; it records each call. Setup (`git`, `okf.py`, the tier declaration) is not a demonstrated step. `BuildTests` asserts every demonstrated step command is `lifecycle.py` and setup executables are limited to `git` and `okf.py`.
6. **Observation (R3).** `observe(extra_args)` runs `lifecycle.py assure --json ...`, parses stdout, reads `requirements`. Step 5 requires `DEMO-R1` in the `--changed` result. Any exit other than the documented 1 (STALE/UNVERIFIED), a JSON error, or a missing `DEMO-R1` is a `DemoFailure`. A step prints only after its observed status equals its expectation; on mismatch stderr gets `assurance_demo: step N (<title>): expected X, observed Y`, stdout nothing for that step, return 1, cleanup. Step 4 also requires `src/calc.py` in the reason. The printed status word is always `item['status']`.
7. **Six steps (R2).**

   | # | Action | Commands shown | Expect |
   |---|---|---|---|
   | 1 | none | `assure --json` | UNVERIFIED |
   | 2 | `assure --run`, then observe | `assure --run`, `assure --json` | VERIFIED |
   | 3 | write `notes.txt` (outside the inputs) | `assure --json` | VERIFIED |
   | 4 | append a comment to `src/calc.py`, keeping it starting with `ok` | `assure --json` | STALE, reason names `src/calc.py` |
   | 5 | none | `assure --changed --base HEAD --json` | `DEMO-R1` listed; its observed status (STALE) is the step status |
   | 6 | `assure --run`, then observe | `assure --run`, `assure --json` | VERIFIED |

   Edits stay uncommitted. Output per step, all from observation: `STEP 4/6 STALE - input edited`, then `  $ python3 .ai/scripts/lifecycle.py assure --json`, then `  DEMO-R1: STALE - <reason>`. After step 6 the demo prints exactly one closing line, `VERIFIED covers only the declared command on its declared inputs.` (R5), and only on success.
8. **Fail-closed hook (R3).** `run(prepare=None, out=None, err=None, transcript=None, calls=None, base=None)` calls `prepare(repo)` after the scripts are copied and before the commit. Tests append to the copied `assurance.py` a wrapper forcing `evaluate` to return VERIFIED (variant A: always; variant B: only STALE becomes VERIFIED so step 4 fails and step 1 passes). A third case has `prepare` raise `RuntimeError` and asserts propagation and an empty base.
9. **Isolation (R4).** Snapshot before/after: `git status --porcelain=v2 -z`, `git rev-parse HEAD`, bytes of `knowledge/history/lifecycle/*` if present (none in the framework), and the bytes or absence of the invoking repo's lifecycle state file (path via `lifecycle.py`'s helpers). No-network check: AST-parse `assurance_demo.py` for imports in `{socket, ssl, http, urllib, ftplib, smtplib, xmlrpc, requests, telnetlib}`, plus a child `python3 -c` that imports the demo, runs `main([])`, and prints the intersection of `sys.modules` roots with that set (dropping only `socket` if `scratch` pulls it transitively).
10. **Docs (R7).** `.ai/lifecycle.md` Assurance status gains one closing sentence: ``Run `python3 .ai/scripts/assurance_demo.py` to watch a requirement go VERIFIED, STALE, VERIFIED in a throwaway repository.`` No link, no new file. Conformance test: extend class `Assurance` in `test_lifecycle_conformance.py` to assert the command appears in the section.

## Steps

Run checks via `lifecycle.py run LABEL -- CMD`; run `lifecycle.py reuse` before any repeat.

1. **Tests first** (R1-R6). Create `.ai/scripts/tests/test_assurance_demo.py` (header like `test_assurance.py`: `SCRIPTS`/`sys.path`, `import disk_tmp` first, then `assurance_demo`) with classes `BuildTests` (R1; also removal after a forced failure and after `prepare` raises), `SequenceTests` (R2; one shared run in `setUpClass`), `FailClosedTests` (R3; the three cases of decision 8), `IsolationTests` (R4), `LimitSentenceTests` (R5), `EndToEndTests` (R6; subprocess with a test-owned `TMPDIR`; asserts return code 0, six ordered steps, final VERIFIED, last line is the limit sentence, directory empty). Record red: `lifecycle.py redgreen red -- python3 -m unittest discover -s .ai/scripts/tests -p test_assurance_demo.py`. Check: it fails with `ModuleNotFoundError: assurance_demo`.
2. **Demo core** (R1, R3, R4). Create `.ai/scripts/assurance_demo.py`: `_base`, `build`, env, `Session`, `DemoFailure`, `run` with `try/finally`, SIGTERM handler. Check: `-k BuildTests`, `-k FailClosedTests`.
3. **Sequence and output** (R2, R5). Six steps, observation/expectation, output format, closing sentence, `main(argv) -> int` with `argparse` (`--help` only). Check: `-k SequenceTests`, `-k LimitSentenceTests`, `-k IsolationTests`, `-k EndToEndTests`; run `python3 .ai/scripts/assurance_demo.py` once by hand and check `git status` is unchanged.
4. **Doc sentence** (R7). Extend the `Assurance` conformance test first (red), then add the sentence to `.ai/lifecycle.md`. Check: `test_lifecycle_conformance.py` passes.
5. **Existing suite** (R7). `python3 .ai/scripts/run_tests.py` through `lifecycle.py run`, once on the frozen tree. Check: PASS, `test_assurance.py` unchanged.
6. **Mutation proofs** (§8.6). Show each new class fails against a broken variant, restore, then `redgreen green`:

   | Class | Broken variant |
   |---|---|
   | `BuildTests` | remove the `finally` rmtree |
   | `SequenceTests` | swap steps 3 and 4 |
   | `FailClosedTests` | print the expected status without comparing |
   | `IsolationTests` | write a cwd-relative file in the demo |
   | `LimitSentenceTests` | print the sentence on failure too |
   | `EndToEndTests` | skip cleanup |
   | `Assurance` (conformance) | remove the new sentence |

7. **Verify and review.** `lifecycle.py converge docs/assurance/specification-6.md`; independent review (`reviewer`) with a report saved untracked; `lifecycle.py retrospect`; `lifecycle.py stage review --ref`, then `stage verify`. Do not rerun unchanged checks.

## Validation commands

- Focused: `python3 -m unittest discover -s .ai/scripts/tests -p test_assurance_demo.py` (and `-k` per class).
- Slice E2E once: `python3 .ai/scripts/assurance_demo.py`, then `git status` is clean.
- Conformance: `python3 -m unittest discover -s .ai/scripts/tests -p test_lifecycle_conformance.py`.
- Full: `python3 .ai/scripts/run_tests.py`, once per frozen candidate.

## Requirement map

| Requirement | Steps | Check |
|---|---|---|
| R1 | 1, 2, 6 | `BuildTests` |
| R2 | 1, 3, 6 | `SequenceTests` |
| R3 | 1, 2, 3, 6 | `FailClosedTests` |
| R4 | 1, 2, 3, 6 | `IsolationTests` |
| R5 | 1, 3, 6 | `LimitSentenceTests` |
| R6 | 1, 3, 6 | `EndToEndTests` |
| R7 | 4, 5, 6 | conformance `Assurance`, `run_tests.py` |

## Risks and notes

- A network-named module pulled in transitively by `scratch` weakens only the runtime import check; the AST check stays.
- The demo runs about ten lifecycle subprocesses (a few seconds); classes share one run through `setUpClass`.

## Open decisions

None.
