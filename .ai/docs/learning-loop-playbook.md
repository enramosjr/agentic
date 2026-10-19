# Learning workflow

1. During an active task, run `lifecycle.py learn TEXT` with the observed lesson.
   Keep the returned record reference and supporting evidence. Capture is optional.
2. Inspect the lesson and discuss its scope. Obtain explicit human approval before
   calling `lifecycle.py promote RECORD#N --approved-by human:ID`.
3. Verify the resulting project rule and log entry. Promotion retries are
   idempotent; do not manufacture a new approval claim to repair bookkeeping.
4. When an approved rule needs removal, obtain approval and run
   `lifecycle.py retire RULE_ID --reason TEXT --approved-by human:ID`.
5. At milestone close, run `okf.py checkpoint --lessons-from RECORD` for the relevant
   records and retain unpromoted observations for the retrospective.

SessionStart injects only active approved rules, within an 8,192-byte UTF-8 budget.
If rules are invalid, repair the cited record rather than assuming a partial
injection succeeded. The [contract](learning-loop.md) governs learn, promote,
retire and --lessons-from. These commands do not start a new autonomous run,
reset prior budgets or substitute for product verification.
