#!/usr/bin/env python3
"""Step 10 (CDMs): find CDM files in the repositories, independent of the register.

Walks every project in the GitLab group of project.yaml (gitlab_url, gitlab_group; without a
token, so public projects only; paths in gitlab_skip are skipped) and looks on the default
branch, on develop, and on every branch with "cdm" or "data-model" in its name, in the paths of
project.yaml cdm_paths:

  cdm_paths:
    - {path: documents/architecture/cdm, all: true}   # every file there is a CDM
    - {path: openapi}                                 # only names with cdm, ConceptualDataModel or data-model

Writes cdm/scan.json: per file the project, branch, commit and path, and whether the
register lists that project. Compare with SOURCES.json to see what the register misses.

Run: python3 pipeline/scan_cdms.py  (takes a while: about 3 calls per project, with waits on 429)
"""
import json
import re
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_specs import get, proj  # noqa: E402

from project import ROOT as FACTORY, component_dir, engine_ref  # noqa: E402
from project import CDM_PATHS, GITLAB_GROUP as GROUP, GITLAB_SKIP, GITLAB_URL  # noqa: E402
PATTERN = re.compile(r"(?i)(cdm|conceptualdatamodel|data-model|datamodel)")


def projects():
    out, page = [], 1
    g = urllib.parse.quote(GROUP, safe="")
    while True:
        items = get(f"{GITLAB_URL}/api/v4/groups/{g}/projects?include_subgroups=true&archived=false"
                    f"&per_page=100&page={page}&simple=true")
        out += items
        if len(items) < 100:
            return out
        page += 1


def tree(project, ref, path):
    q = urllib.parse.urlencode({"ref": ref, "path": path, "per_page": 100, "recursive": "true"})
    return get(f"{proj(project)}/repository/tree?{q}", missing_ok=True) or []


def main():
    reg = json.loads((FACTORY / "cdm/SOURCES.json").read_text(encoding="utf-8"))
    in_register = {r.get("project") or re.search(re.escape(GITLAB_URL.split("//")[-1]) + r"/(.+?)/-/", r["link"]).group(1) for r in reg["cdms"]}
    found, scanned = [], 0
    for p in projects():
        path = p["path_with_namespace"]
        if any(path.startswith(x) for x in GITLAB_SKIP) or p.get("empty_repo"):
            continue
        scanned += 1
        try:
            branches = [b["name"] for b in get(f"{proj(path)}/repository/branches?per_page=100", missing_ok=True) or []]
        except Exception as e:  # noqa: BLE001
            print(f"skip {path}: {e}", file=sys.stderr)
            continue
        refs = [b for b in dict.fromkeys([p.get("default_branch"), "develop"] +
                                          [b for b in branches if re.search(r"(?i)cdm|data-?model", b)]) if b in branches]
        for ref in refs:
            for cp in CDM_PATHS:
                base, every = cp["path"], cp.get("all", False)
                for item in tree(path, ref, base):
                    if item["type"] == "blob" and (every or PATTERN.search(item["name"])):
                        found.append({"project": path, "branch": ref, "path": item["path"],
                                      "in_register": path in in_register})
        if scanned % 25 == 0:
            print(f"{scanned} projects scanned, {len(found)} files", file=sys.stderr)
    # One row per project and file name; list the branches it is on.
    merged = {}
    for f in found:
        k = (f["project"], f["path"])
        merged.setdefault(k, {**f, "branches": []})["branches"].append(f["branch"])
    rows = sorted(merged.values(), key=lambda r: (r["project"], r["path"]))
    for r in rows:
        r.pop("branch")
    out = {"scanned_projects": scanned, "files": rows,
           "projects_with_cdm": len({r["project"] for r in rows}),
           "projects_with_cdm_not_in_register": sorted({r["project"] for r in rows if not r["in_register"]})}
    (FACTORY / "cdm/scan.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "files"}, indent=1))


if __name__ == "__main__":
    main()
