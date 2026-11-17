# Step 70: verify and report

Runs the test writer's suite against the build and turns the results into the reports a programme needs: what passes, traced back to the criteria, decisions and rules; how well the build's own tests cover the code; where the build deviates from the rules; and what is still open.

| Part | Who | Writes |
|---|---|---|
| 70a | script [`verify.py`](./verify.py): runs nothing, reads the behave JSON results of the suite and the inventory, decisions and rules | `{RUN}/report/verification.json`, `verification.md`: results per criterion, decision and rule; the traceability matrix |
| 70b | fresh agent, brief below | `{RUN}/report/REPORT.md`: the final report |

Before 70a, run the suite yourself against the running build (the commands are in the suite's README) with JSON output to `{RUN}/tests/work/reports/`. Optional checks where the tools are installed: mutation testing on the build's own tests (for Java: PIT), a dependency and container scan (for example Trivy), a static scan (for example Semgrep with an OWASP rule set). Keep their outputs in `{RUN}/report/`.

## 70b: brief for a fresh agent

---

You write the **final report** of a build run of a spec-driven software factory, for the programme's spec owners and architects. Read `{RUN}/RUN.json`, `{RUN}/report/` (the verification of 70a and any scan outputs), `{RUN}/tests/work/COVERAGE.md` and its reports, and from the build: `{RUN}/build/work/TRACEABILITY.md`, `DEVIATIONS.md`, `BUILD-LOG.md` and its coverage report. Read no code beyond what you need to explain a failure.

Write `{RUN}/report/REPORT.md`:

1. **In short:** what was built, how it scored, what it means.
2. **Results:** scenarios passed and failed, per feature and per tag kind; criteria covered and passing; decisions covered and passing.
3. **Failures:** each failing scenario with its cause: the build differs from a decision (a build bug), the suite misreads a decision (a test bug), or the decision is ambiguous (a spec gap: name the question for the owner).
4. **Traceability:** the share of live criteria with a passing scenario, with a scenario at all, and with code according to the build's traceability; the criteria with nothing.
5. **Quality of the build:** own test coverage, mutation score if measured, deviations from the rules (with the rule ids), scan results.
6. **New spec gaps:** from the build log and the failures, the questions for the owners that steps 20 to 30 did not raise.
7. **Compared with earlier runs,** if `RUN.json` or the project names one.

Cite scenario names, criterion ids, decision ids and rule ids. Do not judge the people who wrote the specs. Plain English, short sentences, no em-dashes or en-dashes. Report back in under 200 words.

---
