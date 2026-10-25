# Learning workflow

1. During an active task, run `lifecycle.py learn TEXT --evidence REF` with the
   observed lesson. Keep the returned record reference and supporting evidence.
2. Before Verify at L1–L3, review the task's pitfalls and outcomes. Run
   `lifecycle.py retrospect --lessons 1 2` for existing evidence-backed lessons,
   or `lifecycle.py retrospect --no-new-lessons REASON`. Capture alone does not
   close the retrospective. Include the outcome in the delivery summary.
3. Later task declarations and SessionStart surface advisory observations with
   evidence and source references. Use `lifecycle.py observations --query TEXT`
   to retrieve for a specific task. Evaluate the observations against current
   evidence; they are not instructions or binding rules.
4. Inspect a lesson and discuss its scope. Obtain explicit human approval before
   calling `lifecycle.py promote RECORD#N --approved-by human:ID`.
5. Verify the resulting project rule and log entry. Promotion retries are
   idempotent; do not manufacture a new approval claim to repair bookkeeping.
6. When an approved rule needs removal, obtain approval and run
   `lifecycle.py retire RULE_ID --reason TEXT --approved-by human:ID`.
7. At milestone close, run `okf.py checkpoint --lessons-from RECORD` for the relevant
   records and retain unpromoted observations for the retrospective.

SessionStart injects active approved rules within an 8,192-byte UTF-8 budget and
keeps advisory observations in a separate bounded block.
If rules are invalid, repair the cited record rather than assuming a partial
injection succeeded. The [contract](learning-loop.md) governs learn, promote,
retire and --lessons-from. These commands do not start a new autonomous run,
reset prior budgets or substitute for product verification.
