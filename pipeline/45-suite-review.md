# Step 45: suite review

A second reader checks the test writer's suite against the specs and the decisions before the suite judges a build. A wrong scenario costs twice: a correct build fails on it, or a wrong build passes it. In runs 4 and 5 of the first project, 4 of the 11 failures were test bugs: scenarios that expected more than the decisions say. This step catches those before the build is judged.

It runs after step 40 and needs no build, so it runs while the code writer (step 50) works. Like the test writer, the reviewer never sees the build.

| Part | Who | Writes |
|---|---|---|
| 45a | fresh agent, brief below | the review as text; the orchestrator saves it as `{RUN}/tests/review/SUITE-REVIEW.md` |
| 45b | the test writer of step 40 (resumed) or a fresh agent with the step 40 brief | fixes in `{RUN}/tests/work/`; its answer per finding as text, which the orchestrator appends to `SUITE-REVIEW.md` |

**The gate:** every blocker of 45a is fixed or rejected with a reason before step 70 runs the suite. A rejected blocker stays visible: step 70b names it when its scenario fails.

## 45a: brief for a fresh agent

---

You review the **black-box test suite** of a spec-driven software factory, before it is used to judge a build. A test writer wrote it from the specs and the decisions. You check that every scenario tests what the specs and decisions say: no more, no less, and in a way that gives the same result on every run.

### Input (read-only)

- `{RUN}/tests/input/`: the decisions (`decisions/decisions.md`, `decisions.json`, `glossary.md`), the specs, `ids.json`, `rules.json`, `build.yaml`.
- `{RUN}/tests/work/`: the suite (features, step definitions, fixtures, `README.md`, `COVERAGE.md`, the load test if any).
- Never read `{RUN}/build/`, any other run or the project folder. Do not run the suite against anything; a dry run (for behave: `behave --dry-run`) is fine. Do not change any file.

### What to look for

For each scenario, against the decisions it is tagged with (and the criteria and rules):

1. **Over-assertion:** the scenario checks something no decision or criterion fixes (a text, an order, a field, a disabled button, a status code the decisions leave open). A correct build may fail it.
2. **Under-assertion:** the scenario misses what the decision fixes (it checks the status but not the body the decision gives, or "nothing stored" is not proven). A wrong build may pass it.
3. **Misreading:** the scenario contradicts its decision, or follows a spec text where a decision overrides it.
4. **Proof that cannot work:** a check that depends on something the decisions leave open, for example "nothing stored" proven with a GET on a name that may be rejected for its format.
5. **Fragile:** depends on timing within the stated precision, on the order of other scenarios, on data another scenario creates, on an empty store, or on the local machine.
6. **Traceability:** a criterion, decision or rule tag that does not match what the scenario checks; a missing tag.
7. **Gaps:** a decision, criterion or quality target that should have a scenario and has none, where `COVERAGE.md` gives no good reason.

Severity: **blocker** (a build that follows the decisions fails the scenario, or a build that breaks a decision passes it; an over-assertion that a correct build can fail is a blocker), **major** (likely to give a wrong result on some builds, or misses a point a decision fixes), **minor** (tags, wording, clarity, small gaps).

### Output

Do not write any file. Return markdown, starting with `# Suite review`:

1. **In short:** scenarios reviewed, findings per severity and per kind.
2. **Findings:** a table: id (`SR-01`, `SR-02`, ...), severity, kind, scenario (feature file and line, scenario name), decision or criterion, what is wrong, what the scenario should check instead.
3. **Questions for the decisions:** points where the decisions themselves are unclear, so the scenario cannot be right either way (these go to the run report as owner questions).

Then a line `=== SUMMARY ===` and a summary for the orchestrator in under 150 words. Judge the suite, not its writer. Plain English, short sentences, no em-dashes or en-dashes.

---

## 45b: brief for the test writer

---

A reviewer checked your suite against the decisions. The review is in `{RUN}/tests/review/SUITE-REVIEW.md`. For every blocker and major finding, either fix the scenario (keep its tags and meaning, change only what the finding is about) or reject the finding with a reason that cites the decision. Minor findings: fix them where it is cheap. Rerun the dry run.

The same isolation rules as in step 40 apply. Do not write a report file. Return your answer as text: one line per finding (`SR-nn: fixed`, or `SR-nn: rejected, because ...`), then the dry-run result.

---
