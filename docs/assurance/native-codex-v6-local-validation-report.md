# Codex v6 local preparation

Current product tree: `5d42a15c9fb995ce09703be0121c5b31e6dd387e93d8733b8cc7dd34f0189516`. No tracked source changes or native/app-server/model calls were made for this preparation.

Fresh proposal: `operator-2-mechanical-codex-v6/`, one Codex control-delta cell, installed Codex 0.162.1 / gpt-6.1-sol / medium, 300 aggregate agent-seconds and a 330-second campaign envelope. Runner verifies current/frozen source bytes/modes, binary/operator/command pins, first-party subscription authentication, exclusive no-retry marker and selected single-cell scope. It supplies `codex/named-greeting` before native SessionStart/task state, preserving HEAD/tree/staged index/commit count/cleanliness. Existing workspace-write/never and invocation-local exact-handler trust checks remain unchanged. Permission expansion is not proposed.

Local evidence, all exit 0:

* `lifecycle.py run assurance-2-codex-v6-local-prebranch -- python3 docs/assurance/validate-native-prebranch-2-v6.py`: sealed 8 tests PASS. Full output: `native-codex-v6-local-full.log`. Artifact: `native-codex-v6-local-artifact.json`, SHA-256 `42ca3012fd86b44fee14d30715455a13e396cbd2e22e6914d0ff54c4ef847300`.
* `lifecycle.py run assurance-2-codex-v6-local-mutations -- python3 docs/assurance/mutate-native-prebranch-2-v6.py`: 3/3 byte-confirmed sealed variants killed by assertion failures (omitted prebranch, accepted observed session, accepted wrong adapter); no setup/import failures counted. Report: `native-codex-v6-local-mutations.json`.
* `lifecycle.py run assurance-2-codex-v6-policy-regressions -- python3 docs/assurance/validate-native-policy-2-codex-v6.py`: existing 10 policy tests PASS on changed current generic launcher/preparer/default runner. Covers exact trust, guard/auth, retention/SIGKILL, pin drift, aggregate budget shrinking and selected scope. Full output/artifact: `native-codex-v6-policy-full.log`, `native-codex-v6-policy-artifact.json`.
* `lifecycle.py run assurance-2-codex-v6-setup-regressions -- python3 docs/assurance/validate-native-setup-2-codex-v6.py`: existing 2 setup tests PASS unchanged. They explicitly use archived v3 fixture bytes and the current generic preparer; their source closure is sealed, and the archived Gitfile still refers to its original metadata for disk scratch. This scope is distinct from the fresh v6 actual setup below. Full output/artifact: `native-codex-v6-setup-full.log`, `native-codex-v6-setup-artifact.json`.
* `python3 docs/assurance/prepare-native-2-mechanical-codex-v6.py`: complete selected delta/live check closure and actual current v6 real Git/Python fixture setup PASS, clean frozen provenance and exact source/collector byte/mode equality. `operator-2-mechanical-codex-v6/setup-preflight.json` records zero agent/model processes.
* `python3 docs/assurance/report-native-preparation-2-codex-v6.py`: source/frozen/operator/binary pin audit PASS. `native-codex-v6-preparation-report.json` records no started marker/result and no trust/native inference proof claim.

Final frozen pins: runner `6b3cacdd3c30b0c0e7de70654d8caac685d851c1b3d2ded69ca6caf217cb4b21`; launcher `27dbdbf20df2f2481f2bb8feeb5f7c1a6572c3615e85f5282bf26360d5425c21`; planned commands `d08253a43291084aa5395252d926d1d352511d5b86e41202aa5f46286a912544`; preparation `77087458aedec9bcab4f963756151388ebd66fb7f1135480d9bcf78f3063188e`. Each mode is 0644.

Future guarded command (NOT executed; requires fresh human allocation/trust approval):

```sh
python3 .ai/scripts/lifecycle.py run assurance-2-real-agent --timeout 340 -- python3 docs/assurance/run-native-2-mechanical-codex-v6.py --authorized-allocation-and-scoped-trust
```

Claude's v5 PASS and all prior errors remain unchanged. No product full gate was repeated, and no current Codex behavioral PASS, native trust/callback/reviewer proof, Verify or delivery claim is made.
