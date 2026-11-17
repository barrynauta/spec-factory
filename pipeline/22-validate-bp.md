# Step 22: validate the business process

Checks the business process of a component against the rest of the specs: does every process step and requirement have acceptance criteria and an API behind it, does every story belong somewhere in the process, and does the process hold together as a flow between the parties (order, hand-overs, what happens when a step fails). Steps 20 and 21 looked at single criteria and operations; this step looks at the flow.

| Part | Who | Reads | Writes |
|---|---|---|---|
| 22a | script [`check_bp.py`](./check_bp.py) | `inventory/inventory.json`, `inventory/links.json` | `validation/bp-checks.json`, `bp-checks.md` |
| 22b | fresh agent, brief below | the process files, the inventory, the findings of 20b, 21b and 23b, the decisions of step 30, the engine rules | `validation/bp-findings.json`, `bp-review.md` |

22a is coverage only: BP-01 (a step or requirement no criterion covers), BP-02 (covered, but no criterion reaches an operation), BP-03 (a story with no link to the process), BP-04 (a link to an unknown process id). A detailed requirement inherits the criteria of its parent; gaps are reported at the level the links use.

The gate of step 30 reads `bp-findings.json`; its blockers need a decision (a step 30 addendum when step 22 runs after step 30).

## 22b: brief for a fresh agent

---

You validate the **business process** of one component for a spec-driven software factory experiment. A script has checked the coverage between the process and the criteria. You judge the process as a flow: the order of the steps, who does what, how the parties hand over, and what happens when a step fails. You do not decide; you state what is open, with evidence, and the question for the process owner.

### Input (read-only)

- `{PROJECT}/components/{COMPONENT}/specs/functional/`: the business process files (and `specs/README.md`).
- `{PROJECT}/components/{COMPONENT}/inventory/`: `inventory.json` (process steps and requirements with ids), `links.json`, `inventory-review.md`.
- `{PROJECT}/components/{COMPONENT}/validation/`: `bp-checks.json` and `.md` (22a), `ac-findings.json` (20b), `api-findings.json` (21b), `domain-findings.json` and `glossary.md` (23b). Do not repeat their findings; refer to them by id.
- `{PROJECT}/components/{COMPONENT}/decisions/decisions.json` and `glossary.md` (step 30): the state machines and flows already decided.
- `{ENGINE}/guidelines/rules.json`: `MSV-03` (events for state changes), `MSV-06` (dependencies down), `MSV-08` (sagas and compensation), `OWT-A06` (abuse cases), `OWT-A10` (exceptional conditions), `OWA-API6` (sensitive business flows).
- This brief, in `{ENGINE}/pipeline/22-validate-bp.md`.

Read nothing else: no spec digest, no tests, no builds, no other components, no web.

### What to do

1. **Triage 22a.** For each BP-01 and BP-02: is the step out of scope for this component (another component or an external party does it), covered under another name, or a real gap? For each BP-03: which process step should the story belong to, or is it outside the process (technical, cross-cutting)? Only real gaps become findings.
2. **Order and states.** Walk the process step by step. Does its order match the state machine and transitions of the decisions? Name each step where the process and the decided states disagree (a step the states skip, a state no step reaches).
3. **Parties and hand-overs.** For each step: which party acts, and is that the role the stories and the API give? Where the flow passes from one party (or component) to another, is it said how (an API call, an event, a callback) and what the receiver sees?
4. **Failure paths.** For each step that can fail (a check, a signature, a dependency): is the outcome defined, and is the earlier work undone or kept (MSV-08, OWT-A10)? A flow across parties with no defined failure outcome is a finding.
5. **Abuse.** For flows that create obligations or cost for another party: is there a limit or a check (OWA-API6, OWT-A06)?

### Severity

- **blocker:** the order, the party or the hand-over of a main-path step is open or contradicts the decided states, so two builders would build different flows.
- **major:** a failure path or a hand-over detail is open on a main path; a real coverage gap; a story whose place in the process is unclear.
- **minor:** naming, numbering, a process text that lags behind the stories.

### What to write

`{PROJECT}/components/{COMPONENT}/validation/bp-findings.json`: findings in the format of step 20b, ids `B-001` and up, `rule` (an engine rule id, or `BP-01` to `BP-04`, or `FLOW` for order and hand-over points) instead of `check`, `from_22a` (the BA- ids it confirms) and `see` (related F-, P-, D- and decision ids).

`{PROJECT}/components/{COMPONENT}/validation/bp-review.md`: summary (totals per severity, the 5 findings with most impact), blockers with their questions, the flow table (step, party, input, output, hand-over, failure outcome, state before and after, findings), the 22a triage in numbers.

### Rules

Evidence first: cite process ids, story and criterion ids, operation ids and decision ids. Positive tone, roles not names. Plain English, short sentences, no em-dashes or en-dashes.

### Final report (under 250 words)

Totals per severity, blockers, the 22a triage in numbers, and the 3 most important gaps in the flow.

---
