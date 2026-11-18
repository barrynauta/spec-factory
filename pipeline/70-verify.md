# Step 70: verify and report

Runs the test writer's suite against the build and turns the results into the reports a programme needs: what passes, traced back to the criteria, decisions and rules; how well the build's own tests cover the code; where the build deviates from the rules; and what is still open.

| Part | Who | Writes |
|---|---|---|
| 70a | script [`verify.py`](./verify.py): runs nothing, reads the behave JSON results of the suite and the inventory, decisions and rules | `{RUN}/report/verification.json`, `verification.md`: results per criterion, decision and rule; the traceability matrix |
| 70b | fresh agent, brief below | the final report as text; the orchestrator saves it as `{RUN}/report/REPORT.md` |

The orchestrator (the session that runs the factory) does the following before 70a, itself, not through an agent:

1. Run the suite against the running build (the commands are in the suite's README) with JSON output to `{RUN}/tests/work/reports/`.
2. Run the dependency and image scan, whatever step 50 reported, so the report rests on a scan the build did not run itself. With Trivy: `trivy fs --scanners vuln --severity HIGH,CRITICAL --format json -o {RUN}/report/trivy-deps.json {RUN}/build/work`, and per image of the stack `trivy image --severity HIGH,CRITICAL --format json -o {RUN}/report/trivy-<image>.json <image>`. Add a short `{RUN}/report/scan-summary.md` with HIGH and CRITICAL counts per target. If the tool is missing, write that in the summary.
3. Optional, where the tools are installed: mutation testing on the build's own tests (for Java: PIT), a static scan (for example Semgrep with an OWASP rule set). Outputs in `{RUN}/report/`.

After 70b, the orchestrator saves the agent's answer, up to the line `=== SUMMARY ===`, as `{RUN}/report/REPORT.md`. Subagents may not be able to write files (some harnesses block it), so 70b returns the report as text.

## 70b: brief for a fresh agent

---

You write the **final report** of a build run of a spec-driven software factory, for the programme's spec owners and architects. Read `{RUN}/RUN.json`, `{RUN}/report/` (the verification of 70a, `scan-summary.md` and the other scan outputs), `{RUN}/tests/work/COVERAGE.md` and its reports, and from the build: `{RUN}/build/work/TRACEABILITY.md`, `DEVIATIONS.md`, `BUILD-LOG.md` and its coverage report. Read no code beyond what you need to explain a failure.

Do not write any file. Return the full report as markdown in your answer, starting with a `# ` title line; the orchestrator saves it as `{RUN}/report/REPORT.md`. The report has these sections:

1. **In short:** what was built, how it scored, what it means.
2. **Results:** scenarios passed and failed, per feature and per tag kind; criteria covered and passing; decisions covered and passing.
3. **Failures:** each failing scenario with its cause: the build differs from a decision (a build bug), the suite misreads a decision (a test bug), or the decision is ambiguous (a spec gap: name the question for the owner).
4. **Traceability:** the share of live criteria with a passing scenario, with a scenario at all, and with code according to the build's traceability; the criteria with nothing.
5. **Quality of the build:** own test coverage, mutation score if measured, deviations from the rules (with the rule ids), scan results: HIGH and CRITICAL counts per target from `scan-summary.md`, set against what the build's `SECURITY-SCAN.md` says it fixed or accepted.
6. **New spec gaps:** from the build log and the failures, the questions for the owners that steps 20 to 30 did not raise. Number them; they go back into step 30 as findings `R-nnn` (see the brief of step 30).
7. **Compared with earlier runs,** if `RUN.json` or the project names one.

Cite scenario names, criterion ids, decision ids and rule ids. Do not judge the people who wrote the specs. Plain English, short sentences, no em-dashes or en-dashes. After the report, add a line `=== SUMMARY ===` and a summary for the orchestrator in under 200 words.

---
