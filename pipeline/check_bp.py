#!/usr/bin/env python3
"""Step 22a: coverage between the business process and the rest of the specs.

For each process step and requirement of the component (step 12 inventory) it lists the
acceptance criteria linked to it (step 12b links), and through those criteria the API
operations. It flags:

  BP-01  a process step or requirement no criterion covers
  BP-02  a process step or requirement covered by criteria, none of which reaches an operation
  BP-03  a story none of whose criteria is linked to the process
  BP-04  a link to a process id that is not in the inventory

Links written with section ids ("BP02C#BP02C.01 Create a new schema", "BP02B#2B.1 - ...")
are mapped to the inventory ids (BP02C.01, BP2B.1) first.

Writes <component>/validation/bp-checks.json and bp-checks.md.

Run: ./factory check_bp <component>
"""
import json
import re
import sys
from collections import defaultdict

from project import component_dir, engine_ref  # noqa: E402


def norm_bp(x, ids):
    """Map a process reference to an inventory id, or return it unchanged."""
    if x in ids:
        return x
    tail = x.split("#", 1)[1] if "#" in x else x
    m = re.match(r"(BP\d+[A-Z]?\.\d+)", tail)
    if m and m.group(1) in ids:
        return m.group(1)
    m = re.match(r"(\d+[A-Z]?(?:\.\d+)+)", tail)
    if m and f"BP{m.group(1)}" in ids:
        return f"BP{m.group(1)}"
    return x


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    name = sys.argv[1]
    comp = component_dir(name)
    inv = json.loads((comp / "inventory/inventory.json").read_text(encoding="utf-8"))
    links = json.loads((comp / "inventory/links.json").read_text(encoding="utf-8")) if (comp / "inventory/links.json").exists() else []
    reqs = inv["bp_requirements"]
    ids = {r["id"] for r in reqs}
    ac_ids = {a["id"] for s in inv["stories"] for a in s["acs"] if not a["struck"]}
    op_ids = {o["id"] for a in inv["apis"] for o in a["operations"]}
    ac_story = {a["id"]: s["key"] for s in inv["stories"] for a in s["acs"]}

    ac_to_bp, ac_to_op, unknown = defaultdict(set), defaultdict(set), set()
    for l in links:
        a, b = l["from"], l["to"]
        for x, y in ((a, b), (b, a)):
            if x in ac_ids:
                if y.startswith("BP"):
                    n = norm_bp(y, ids)
                    if n in ids:
                        ac_to_bp[x].add(n)
                    else:
                        unknown.add(y)
                elif y in op_ids:
                    ac_to_op[x].add(y)
    bp_acs = defaultdict(set)
    for ac, bps in ac_to_bp.items():
        for bp in bps:
            bp_acs[bp].add(ac)

    # A detailed requirement (BP2B.1.1) inherits the criteria of its parent (BP2B.1), and the other way round
    # a parent counts as covered when one of its children is.
    def parent(i):
        return i.rsplit(".", 1)[0] if i.count(".") >= 2 else None
    inherited = defaultdict(set)
    for i in ids:
        p = parent(i)
        if p in bp_acs:
            inherited[i] |= bp_acs[p]
        if i in bp_acs and p in ids:
            inherited[p] |= bp_acs[i]
    rows, findings = [], []

    def f(target, check, detail):
        findings.append({"id": f"BA-{len(findings) + 1:03d}", "target": target, "check": check, "detail": detail})

    # Report gaps at the level the links use most (step, requirement or detailed requirement); other levels are info.
    kind_of = {r["id"]: r.get("kind", "detailed") for r in reqs}
    linked_kinds = defaultdict(int)
    for bp in bp_acs:
        linked_kinds[kind_of[bp]] += 1
    primary = max(linked_kinds, key=linked_kinds.get) if linked_kinds else None
    for r in reqs:
        direct = bp_acs.get(r["id"], set())
        acs = sorted(direct | inherited.get(r["id"], set()))
        ops = sorted({o for a in acs for o in ac_to_op.get(a, [])})
        rows.append({"id": r["id"], "kind": r.get("kind", "detailed"), "process": r["process"], "title": r["title"],
                     "criteria": acs, "stories": sorted({ac_story[a] for a in acs}), "operations": ops})
        rows[-1]["via"] = "direct" if direct else ("inherited" if acs else "")
        if r.get("kind", "detailed") != primary:
            continue
        if not acs:
            f(r["id"], "BP-01", f"no acceptance criterion covers this {r.get('kind', 'requirement')}: {r['title']}")
        elif not ops:
            f(r["id"], "BP-02", f"{len(acs)} criteria cover it, but none is linked to an API operation: {r['title']}")
    linked_stories = {ac_story[a] for a in ac_to_bp}
    for s in inv["stories"]:
        if [a for a in s["acs"] if not a["struck"]] and s["key"] not in linked_stories:
            f(s["key"], "BP-03", f"no criterion of this story is linked to the business process: {s['title'][:90]}")
    for u in sorted(unknown):
        f(u, "BP-04", "link to a process id that is not in the inventory")

    kinds = defaultdict(lambda: [0, 0])
    for r in rows:
        kinds[r["kind"]][0] += 1
        kinds[r["kind"]][1] += bool(r["criteria"])
    summary = {"component": name, "process_items": len(rows), "level_of_the_links": primary,
               "covered_by_kind": {k: f"{v[1]} of {v[0]}" for k, v in kinds.items()},
               "findings": len(findings),
               "by_check": {c: sum(1 for x in findings if x["check"] == c) for c in ("BP-01", "BP-02", "BP-03", "BP-04")}}
    out = comp / "validation"
    (out / "bp-checks.json").write_text(json.dumps({"summary": summary, "items": rows, "findings": findings}, indent=1,
                                                   ensure_ascii=False) + "\n", encoding="utf-8")
    md = [f"# Business process checks (step 22a): {name}", "",
          "Generated by " + engine_ref("check_bp.py") + " from the step 12 inventory and the step 12b links. "
          "Coverage only: which process steps and requirements the criteria cover, and whether those criteria reach an "
          "API operation. Step 22b judges the process itself. A detailed requirement inherits the criteria of its parent "
          f"and the other way round; gaps are reported at the level the links use ({primary}), other levels are listed below.", "",
          "| Kind | Covered by a criterion |", "|---|---|"]
    md += [f"| {k} | {v} |" for k, v in summary["covered_by_kind"].items()]
    md += ["", "| Check | What | Findings |", "|---|---|---|",
           f"| BP-01 | step or requirement with no criterion | {summary['by_check']['BP-01']} |",
           f"| BP-02 | covered, but no criterion reaches an operation | {summary['by_check']['BP-02']} |",
           f"| BP-03 | story with no link to the process | {summary['by_check']['BP-03']} |",
           f"| BP-04 | link to an unknown process id | {summary['by_check']['BP-04']} |", "",
           "## Process items", "", "| Id | Kind | Title | Criteria | Operations |", "|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| `{r['id']}` | {r['kind']} | {r['title'][:70]} | {len(r['criteria'])} | {len(r['operations'])} |")
    md += ["", "## Findings", "", "| Id | Target | Check | Detail |", "|---|---|---|---|"]
    md += [f"| {x['id']} | `{x['target']}` | {x['check']} | {x['detail'].replace('|', '/')} |" for x in findings]
    (out / "bp-checks.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
