#!/usr/bin/env python3
"""Steps 40 to 60: prepare the isolated workspaces of a build run.

A run gets two workspaces outside the project, so the test writer and the code writer
cannot see each other's work, nor earlier runs or the upstream code:

  <runs>/<project>-<component>-<run>/tests/   for the test writers (steps 40 and 60)
  <runs>/<project>-<component>-<run>/build/   for the code writer (step 50)

Each gets an input/ folder with the same frozen material: the component's specs, the
decisions and the final glossary of step 30, the stable ids of step 12, the rules that
apply to building (engine and project rules whose steps include 40, 50 or 60), and the
component's build profile (build.yaml). The test workspace also gets the inventory with
the acceptance criteria ids, so every scenario can name the criterion it checks.

The gate of step 30 must pass first.

Run: ./factory prepare_run <component> <run-name> [--runs ~/src/spec-factory-runs]
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

from project import CFG, ENGINE, ROOT, component_dir, engine_commit, load_rules  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("component")
    ap.add_argument("run")
    ap.add_argument("--runs", default="~/src/spec-factory-runs")
    a = ap.parse_args()
    comp = component_dir(a.component)
    gate = subprocess.run([sys.executable, str(ENGINE / "pipeline/check_gate.py"), a.component], capture_output=True, text=True)
    if gate.returncode != 0:
        sys.exit(f"the gate of step 30 does not pass for {a.component}:\n{gate.stdout}")
    if not (comp / "build.yaml").exists():
        sys.exit(f"no build profile: {comp / 'build.yaml'}")
    base = Path(a.runs).expanduser() / f"{CFG.get('name', 'project').lower().replace(' ', '-')}-{a.component}-{a.run}"
    if base.exists():
        sys.exit(f"{base} exists: a run is never reused")
    rules = [r for r in load_rules().values() if set(r.get("steps", [])) & {40, 50, 60}]
    for part in ("tests", "build"):
        inp = base / part / "input"
        shutil.copytree(comp / "specs", inp / "specs", ignore=shutil.ignore_patterns("_private"))
        (inp / "decisions").mkdir(parents=True)
        for f in ("decisions.json", "decisions.md", "glossary.md"):
            shutil.copy(comp / "decisions" / f, inp / "decisions" / f)
        shutil.copy(comp / "build.yaml", inp / "build.yaml")
        cat = CFG.get("reuse_catalogue")
        if part == "build" and cat and (ROOT / cat).exists():
            shutil.copy(ROOT / cat, inp / "reuse-catalogue.yaml")  # REUSE-05: what the project already offers
        # The CDM files the component's sources name (D87 traces the logical model to them; DATA rules judge it).
        cdm = (yaml.safe_load((comp / "sources.yaml").read_text(encoding="utf-8")) or {}).get("cdm") or {}
        for v in cdm.values():
            for name in ([v] if isinstance(v, str) else v):
                if (ROOT / "cdm" / name).exists():
                    (inp / "cdm").mkdir(exist_ok=True)
                    shutil.copy(ROOT / "cdm" / name, inp / "cdm" / name)
        (inp / "rules.json").write_text(json.dumps(rules, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        if part == "tests":
            inv = json.loads((comp / "inventory/inventory.json").read_text(encoding="utf-8"))
            slim = {"stories": [{"key": s["key"], "title": s["title"],
                                 "acs": [{"id": x["id"], "heading": x["heading"], "struck": x["struck"]} for x in s["acs"]]}
                                for s in inv["stories"]],
                    "operations": [o["id"] for api in inv["apis"] for o in api["operations"]]}
            (inp / "ids.json").write_text(json.dumps(slim, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        (base / part / "work").mkdir()
    manifest = {"project": CFG.get("name"), "component": a.component, "run": a.run, "engine": engine_commit(),
                "project_root": str(ROOT), "rules": len(rules),
                "build_profile": yaml.safe_load((comp / "build.yaml").read_text(encoding="utf-8"))}
    (base / "RUN.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    print(f"{base}\n  tests/input  for steps 40 and 60\n  build/input  for step 50\n  {len(rules)} rules apply to building")


if __name__ == "__main__":
    main()
