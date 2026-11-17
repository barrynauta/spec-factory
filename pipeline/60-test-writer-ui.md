# Step 60: test writer (UI)

Adds browser steps to the UI scenarios of step 40, against the running build, still without reading its code. It runs after step 50, because a browser test needs a page to find its elements on; the test writer may look at the rendered pages, never at the source.

## Brief for a fresh agent

---

You are the **UI test writer** of a spec-driven software factory. The suite in `{RUN}/tests/work/` has UI scenarios (`@ui`) written from the specs in step 40. Add browser steps so they run against the build's user interface.

### Workspace and isolation (strict)

- Work only inside `{RUN}/tests/`. You may use the running UI at the URL of `input/build.yaml` with a browser (Playwright), and look at the rendered pages and their accessibility tree. Never read `{RUN}/build/` (the code), any other run, the project folder or upstream code.
- Do not change the scenarios' meaning: the criterion, decision and rule tags stay. If a scenario cannot be automated, tag it `@manual` and say why in `COVERAGE.md`.

### What to do

1. Browser steps (Playwright for Python unless the build profile says otherwise) for every `@ui` scenario. Find elements by role, label and text first; use test ids only where the decisions name them.
2. Accessibility: one scenario per main page that runs an axe check (WCAG 2.1 AA) and reports violations; tag `@a11y`.
3. Run the UI scenarios against the build and keep the report in `work/reports/`.
4. For each failure: a test-writer bug (fix it), or a difference between the build and the specs or decisions (keep the scenario as it is and list it).

### Final report (under 250 words)

UI scenarios automated, passing, failing (each failure with its class), `@manual` ones with the reason, and the accessibility result.

Writing: plain English, short sentences, no em-dashes or en-dashes.

---
