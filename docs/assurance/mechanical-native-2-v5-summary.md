# V5 native campaign result

The explicitly approved pair executed once: **Claude PASS, Codex ERROR**. Charged time was **131.58858792600222 agent-seconds**, with zero final reservations. The campaign finished within the approved 600 agent-second and 660-second limits. No retry occurred. Full evidence: [mechanical-native-2-v5-report.json](mechanical-native-2-v5-report.json).

Claude completed the scenario and mechanically bound native review through Verify on source a9e58f56be695f860d87a470fdf18b038e698c18a5982703bab939b088e7f409. Exactly one native reviewer started and completed; it remained read-only. Captured, saved and receipt report hashes match. Strict outcome and qualification checks passed.

Codex stopped before enabling mechanical review. The guard rejected ordinary branch creation in the fixture's separate-Git-directory layout because reverse metadata discovery could not establish checkout ownership. No Codex reviewer, convergence or Verify ran. Its ERROR is preserved, with parent events and raw stream. This run does not qualify Codex native review.

The source correction now uses a sanitized physical ownership witness and retains foreign metadata and index/object/common checks. It passed independent review, 63 focused tests, 33 confirmed semantic mutation controls, 802 framework tests and all eight requirement checks. See [final8 local validation](mechanical-validation-2-final8-report.md). Claude's earlier PASS remains explicitly scoped to its original source; the exact source comparison is retained separately.

Overall feature completion is pending Codex native qualification. A fresh Codex-only proposal is prepared separately; the v5 no-retry clause requires another explicit allocation before that attempt can run. Implementation remains uncommitted. No Verify, Ship, push, PR or merge is claimed.
