# Step 70: verify and report

Runs the test writer's suite against the build and turns the results into the reports a programme needs: what passes, traced back to the criteria, decisions and rules; how well the build's own tests cover the code; where the build deviates from the rules; and what is still open.

| Part | Who | Writes |
|---|---|---|
| 70a | script [`verify.py`](./verify.py): runs nothing, reads the behave JSON results of the suite and the inventory, decisions and rules | `{RUN}/report/verification.json`, `verification.md`: results per criterion, decision and rule; the traceability matrix |
| 70c | fresh agent, brief below | an independent design review of the build against the review rules, as text; the orchestrator saves it as `{RUN}/report/design-review.md` |
| 70b | fresh agent, brief below | the final report as text; the orchestrator saves it as `{RUN}/report/REPORT.md` |

The orchestrator (the session that runs the factory) does the following before 70a, itself, not through an agent:

1. Check the gate of step 45: no blocker of `{RUN}/tests/review/SUITE-REVIEW.md` is left without a fix or a reason.
2. Run the suite against the running build (the commands are in the suite's README) with JSON output to `{RUN}/tests/work/reports/`.
3. Run the dependency and image scan, whatever step 50 reported, so the report rests on a scan the build did not run itself. With Trivy: `trivy fs --scanners vuln --severity HIGH,CRITICAL --format json -o {RUN}/report/trivy-deps.json {RUN}/build/work`, and per image of the stack `trivy image --severity HIGH,CRITICAL --format json -o {RUN}/report/trivy-<image>.json <image>`. Add a short `{RUN}/report/scan-summary.md` with HIGH and CRITICAL counts per target. If the tool is missing, write that in the summary.
4. Fuzz the API: `./factory fuzz_api <component> {RUN}` (Schemathesis from the OpenAPI, settings in the `fuzz` section of `build.yaml`). Failures that a decision explains are listed with their decision in `<component>/fuzz-known.yaml`; the rest are findings. Output: `{RUN}/report/fuzz-summary.md`, `fuzz.json` and `fuzz/`. A new entry in `fuzz-known.yaml` needs a decision id; a failure without one is a finding, not a reason to add it. For a new component the file starts empty: after the first fuzz run, the orchestrator goes through the failures, matches each one against the contract changes decision of step 30, adds the matches with their decision id, and leaves every other failure as a finding. Then it runs the fuzzing again.
5. Run the load test of the suite (`{RUN}/tests/work/load/`, see its README) against the running build, when the suite has one. Keep `reports/load.json` and copy it to `{RUN}/report/load.json`. Run it after the functional suites, never at the same time.
6. Optional, where the tools are installed: mutation testing on the build's own tests (for Java: PIT), a static scan (for example Semgrep with an OWASP rule set). Outputs in `{RUN}/report/`.

Then 70c, then 70b. After 70c, the orchestrator saves the agent's answer, up to the line `=== SUMMARY ===`, as `{RUN}/report/design-review.md`. After 70b, the orchestrator saves the agent's answer, up to the line `=== SUMMARY ===`, as `{RUN}/report/REPORT.md`. Subagents may not be able to write files (some harnesses block it), so 70b returns the report as text.

## 70c: brief for a fresh agent

---

You do an **independent design review** of a build of a spec-driven software factory. The code writer judged its own work against the rules (`DEVIATIONS.md`, `REUSE.md`, `QUALITY.md`); you check that judgement from the code. Most rules can only be checked by reading, so your review is what makes them real checks.

### Input (read-only)

- `{RUN}/build/input/rules.json`: the rules. Review every rule whose `check` is `review` and whose `steps` contain 70. Group them by prefix.
- `{RUN}/build/input/decisions/` and, when present, `{RUN}/build/input/reuse-catalogue.yaml`.
- `{RUN}/build/work/`: the code, configuration, Dockerfiles, compose file and docs.
- Read `DEVIATIONS.md`, `REUSE.md` and `QUALITY.md` of the build only **after** you have formed your own verdict on a rule, then compare.
- Do not read `{RUN}/tests/`, `{RUN}/report/` or any other run. Do not change any file. Do not start or stop anything.

### What to check

For each rule: `met`, `partly`, `not met` or `not applicable`, with evidence (file and line, or the config key) in one or two lines. Pay special attention to:

- **Reuse (`REUSE-`)**: own implementations of security, parsing or infrastructure; capabilities the reuse catalogue offers that were built anyway; whether `REUSE.md` is true and complete.
- **Patterns**: a named pattern where a recurring problem appears, and no pattern where there is no such problem (over-engineering is a finding too).
- **Quality (`NFR-`)**: unbounded queries, lists, caches or pools; missing container limits; health and graceful shutdown; logs, metrics and traces; whether `QUALITY.md` is true.
- **Architecture and security** (`MACH-`, `MSV-`, `OWT-`, `OWA-`, the project's `ARCH-`, `CODE-`, `SEC-`): what can be seen in the code.

Then list where you disagree with the code writer: a rule it reports as met that you find not met, and the other way round.

### Output

Do not write any file. Return markdown, starting with `# Design review`:

1. **In short:** rules reviewed, verdicts per level (MUST, SHOULD) and per prefix, the five most important findings.
2. **Verdicts:** one table per prefix: rule id, level, verdict, evidence.
3. **Disagreements with the build's own documents.**
4. **Findings for the next run:** what the briefs, decisions or rules should change so the next build does better.

Then a line `=== SUMMARY ===` and a summary for the orchestrator in under 150 words. Plain English, short sentences, no em-dashes or en-dashes. Judge the code, not the people.

---

## 70b: brief for a fresh agent

---

You write the **final report** of a build run of a spec-driven software factory, for the programme's spec owners and architects. Read `{RUN}/RUN.json`, `{RUN}/report/` (the verification of 70a, `scan-summary.md` and the other scan outputs, `load.json` when present, `fuzz-summary.md`, and `design-review.md` of 70c), `{RUN}/tests/work/COVERAGE.md` and its reports, `{RUN}/tests/review/SUITE-REVIEW.md` (the suite review of step 45 and the test writer's answers), and from the build: `{RUN}/build/work/TRACEABILITY.md`, `DEVIATIONS.md`, `REUSE.md`, `QUALITY.md`, `BUILD-LOG.md` and its coverage report. Read no code beyond what you need to explain a failure.

Do not write any file. Return the full report as markdown in your answer, starting with a `# ` title line; the orchestrator saves it as `{RUN}/report/REPORT.md`. The report has these sections:

1. **In short:** what was built, how it scored, what it means.
2. **Results:** scenarios passed and failed, per feature and per tag kind; criteria covered and passing; decisions covered and passing.
3. **Failures:** each failing scenario with its cause; then each fuzz finding (`fuzz-summary.md`) with its cause: a build bug, a contract problem in the OpenAPI, or a decision the fuzz list misses (say when step 45 flagged the scenario and the test writer kept it): the build differs from a decision (a build bug), the suite misreads a decision (a test bug), or the decision is ambiguous (a spec gap: name the question for the owner).
4. **Traceability:** the share of live criteria with a passing scenario, with a scenario at all, and with code according to the build's traceability; the criteria with nothing.
5. **Quality of the build:** a table of the quality targets (`Q` decisions) with target, measured value (from `load.json` and the other reports) and verdict, or why not measured (`NFR-13`); reuse (`REUSE.md` and the 70c verdicts on `REUSE-`); the main 70c findings and disagreements; own test coverage, mutation score if measured, deviations from the rules (with the rule ids), scan results: HIGH and CRITICAL counts per target from `scan-summary.md`, set against what the build's `SECURITY-SCAN.md` says it fixed or accepted.
6. **New spec gaps:** from the build log and the failures, the questions for the owners that steps 20 to 30 did not raise. Number them; they go back into step 30 as findings `R-nnn` (see the brief of step 30).
7. **Compared with earlier runs,** if `RUN.json` or the project names one.

Cite scenario names, criterion ids, decision ids and rule ids. Do not judge the people who wrote the specs. Plain English, short sentences, no em-dashes or en-dashes. After the report, add a line `=== SUMMARY ===` and a summary for the orchestrator in under 200 words.

---
