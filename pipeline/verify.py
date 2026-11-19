#!/usr/bin/env python3
"""Step 70a: trace the test results of a build run back to the specification.

Reads the behave JSON results in <run>/tests/work/reports/*.json (or the files given with
--results), the component's inventory and decisions, and the rules. Every scenario carries
tags naming what it checks: @AC_<story>_<ACn>, @Dnn / @Enn and rule ids. The script counts,
per acceptance criterion, decision and rule, the scenarios and how many passed, and writes
the traceability matrix.

Writes <run>/report/verification.json and verification.md.

Run: ./factory verify <component> <run-folder> [--results file.json ...]
"""
import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from project import component_dir, engine_ref, load_rules  # noqa: E402


def scenarios(paths):
    out = []
    for p in paths:
        src = [p]
        data = json.loads(Path(p).read_text(encoding="utf-8"))
        # Only behave JSON (a list of features); skip other reports in the folder, such as axe results.
        if not isinstance(data, list) or not all(isinstance(f, dict) and f.get("keyword") == "Feature" for f in data):
            print(f"skipped {p}: not behave JSON", file=sys.stderr)
            continue
        for feat in data:
            ftags = [t.lstrip("@") for t in feat.get("tags", [])]
            for el in feat.get("elements", []):
                if el.get("type") == "background":
                    continue
                tags = ftags + [t.lstrip("@") for t in el.get("tags", [])]
                steps = el.get("steps", [])
                statuses = [s.get("result", {}).get("status", "skipped") for s in steps]
                status = el.get("status") or ("failed" if "failed" in statuses or "error" in statuses
                                              else "passed" if statuses and all(x == "passed" for x in statuses)
                                              else "skipped")
                out.append({"feature": feat.get("name", ""), "name": el.get("name", ""), "tags": tags,
                            "status": status, "file": el.get("location", feat.get("location", "")), "_src": src})
    # Several result files (for example API, store-down and UI runs) each list the other scenarios as skipped.
    # Keep one record per scenario: a failed or passed result wins over skipped; the last real result wins.
    # Key by feature file without the line number, name and occurrence: a suite step may edit a feature file
    # between two runs, which shifts lines, so file:line would count one scenario twice (run 6 of the first project).
    merged, seen = {}, {}
    for s in out:
        base = (s["file"].rsplit(":", 1)[0], s["name"])
        n = seen.get((id(s["_src"]),) + base, 0)
        seen[(id(s["_src"]),) + base] = n + 1
        key = base + (n,)
        if key not in merged or s["status"] != "skipped":
            merged[key] = s
    return [{k: v for k, v in s.items() if k != "_src"} for s in merged.values()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("component")
    ap.add_argument("run")
    ap.add_argument("--results", nargs="*")
    a = ap.parse_args()
    comp = component_dir(a.component)
    run = Path(a.run).expanduser()
    results = a.results or sorted((run / "tests/work/reports").glob("*.json"))
    sc = scenarios(results)
    inv = json.loads((comp / "inventory/inventory.json").read_text(encoding="utf-8"))
    decisions = json.loads((comp / "decisions/decisions.json").read_text(encoding="utf-8"))
    rules = load_rules()
    live = [a_["id"] for s in inv["stories"] for a_ in s["acs"] if not a_["struck"]]

    by = {"ac": defaultdict(list), "decision": defaultdict(list), "rule": defaultdict(list)}
    for s in sc:
        for t in s["tags"]:
            m = re.match(r"AC_(.+)_(AC[\d.]+)$", t)
            if m:
                by["ac"][f"{m.group(1)}/{m.group(2)}"].append(s)
            elif re.match(r"^[DEQ]\d+$", t):
                by["decision"][t].append(s)
            elif t in rules:
                by["rule"][t].append(s)

    def stat(lst):
        return {"scenarios": len(lst), "passed": sum(x["status"] == "passed" for x in lst),
                "failed": sum(x["status"] == "failed" for x in lst)}

    ac_rows = {i: stat(by["ac"].get(i, [])) for i in live}
    dec_rows = {d["id"]: stat(by["decision"].get(d["id"], [])) for d in decisions}
    rule_rows = {r: stat(lst) for r, lst in sorted(by["rule"].items())}
    unknown_ac = sorted(set(by["ac"]) - set(live))
    tot = stat(sc)
    summary = {
        "component": a.component, "run": run.name, "result_files": [str(p) for p in results],
        "scenarios": tot["scenarios"], "passed": tot["passed"], "failed": tot["failed"],
        "skipped": tot["scenarios"] - tot["passed"] - tot["failed"],
        "criteria_live": len(live),
        "criteria_with_a_scenario": sum(1 for v in ac_rows.values() if v["scenarios"]),
        "criteria_all_passing": sum(1 for v in ac_rows.values() if v["scenarios"] and v["passed"] == v["scenarios"]),
        "decisions": len(decisions),
        "decisions_with_a_scenario": sum(1 for v in dec_rows.values() if v["scenarios"]),
        "decisions_all_passing": sum(1 for v in dec_rows.values() if v["scenarios"] and v["passed"] == v["scenarios"]),
        "rules_tested": len(rule_rows),
        "tags_naming_unknown_criteria": unknown_ac,
    }
    out = run / "report"
    out.mkdir(exist_ok=True)
    (out / "verification.json").write_text(json.dumps({"summary": summary, "criteria": ac_rows, "decisions": dec_rows,
                                                       "rules": rule_rows,
                                                       "failed": [s for s in sc if s["status"] == "failed"]},
                                                      indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    pct = lambda n, d: f"{n} of {d} ({round(100 * n / d) if d else 0}%)"  # noqa: E731
    md = [f"# Verification (step 70a): {a.component}, {run.name}", "",
          "Generated by " + engine_ref("verify.py") + " from the suite's results and the step 12 and 30 ids.", "",
          "| Measure | Result |", "|---|---|",
          f"| Scenarios passed | {pct(tot['passed'], tot['scenarios'])}; failed {tot['failed']}, skipped {summary['skipped']} |",
          f"| Live criteria with a scenario | {pct(summary['criteria_with_a_scenario'], len(live))} |",
          f"| Live criteria with all scenarios passing | {pct(summary['criteria_all_passing'], len(live))} |",
          f"| Decisions with a scenario | {pct(summary['decisions_with_a_scenario'], len(decisions))} |",
          f"| Decisions with all scenarios passing | {pct(summary['decisions_all_passing'], len(decisions))} |",
          f"| Rules tested | {len(rule_rows)} |", ""]
    if unknown_ac:
        md += ["Tags naming criteria that are not live: " + ", ".join(unknown_ac), ""]
    md += ["## Failed scenarios", "", "| Feature | Scenario | Tags |", "|---|---|---|"]
    md += [f"| {s['feature']} | {s['name']} | {' '.join(s['tags'])} |" for s in sc if s["status"] == "failed"] or ["| none | | |"]
    md += ["", "## Traceability: criteria", "", "| Criterion | Scenarios | Passed | Failed |", "|---|---|---|---|"]
    md += [f"| `{i}` | {v['scenarios']} | {v['passed']} | {v['failed']} |" for i, v in ac_rows.items()]
    md += ["", "## Traceability: decisions", "", "| Decision | Scenarios | Passed | Failed |", "|---|---|---|---|"]
    md += [f"| {i} | {v['scenarios']} | {v['passed']} | {v['failed']} |" for i, v in dec_rows.items()]
    md += ["", "## Rules tested", "", "| Rule | Scenarios | Passed | Failed |", "|---|---|---|---|"]
    md += [f"| {i} | {v['scenarios']} | {v['passed']} | {v['failed']} |" for i, v in rule_rows.items()]
    (out / "verification.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
