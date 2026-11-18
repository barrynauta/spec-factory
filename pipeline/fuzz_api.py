#!/usr/bin/env python3
"""Step 70 (fuzz): property-based API fuzzing of a running build against its OpenAPI.

Schemathesis generates requests from the OpenAPI file (valid, invalid, edge cases) and checks every
response: no server errors, status codes, media types, headers and bodies as the contract says,
invalid input rejected, valid input accepted, undeclared methods answered with 405. The hand-written
suite tests what the decisions say with chosen examples; fuzzing tests what nobody thought of.

The decisions may extend the contract on purpose (stricter limits, unknown fields rejected, ...).
Those failures are expected. The component lists them in <component>/fuzz-known.yaml, each with the
decision that explains it; every other failure is a finding. A known entry matches on the operation
(or "*"), the check code (for example ST202) and, optionally, a text in the server's answer.

Configuration, in the component's build.yaml:

  fuzz:
    openapi: specs/api/<file>.yaml   # relative to the run's tests/input/
    user: <user with full rights>    # token by password grant, TOKEN_URL and TOKEN_CLIENT from tests.environment
    password: <password>
    max_examples: 30                 # per operation
    seed: 1
    max_time: 300                    # seconds for the whole run

Needs schemathesis 4.x: on PATH, or SCHEMATHESIS=/path/to/schemathesis.

Run: ./factory fuzz_api <component> <run-folder>
Writes <run>/report/fuzz/ (JUnit), <run>/report/fuzz.json and <run>/report/fuzz-summary.md.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from project import component_dir  # noqa: E402


def token(url, client, user, password):
    data = urllib.parse.urlencode({"grant_type": "password", "client_id": client, "username": user,
                                   "password": password, "scope": "openid"}).encode()
    with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=20) as r:
        return json.load(r)["access_token"]


def failures(junit):
    """One record per failed check: operation, check code and title, status, the server's detail."""
    out = []
    for tc in ET.parse(junit).getroot().iter("testcase"):
        for f in list(tc.findall("failure")) + list(tc.findall("error")):
            txt = (f.text or "") + "\n" + (f.get("message") or "")
            for blk in re.split(r"\n(?=\d+\. Test Case ID)", txt):
                for m in re.finditer(r"- (ST\d+) ([^\n]+)", blk):
                    st = re.search(r"\[(\d{3})\]", blk)
                    det = re.findall(r'"detail":"([^"]{0,200})', blk)
                    out.append({"operation": tc.get("name"), "check": m.group(1), "title": m.group(2).strip(),
                                "status": st.group(1) if st else "",
                                "detail": re.split(r"\s*//|\n", det[-1] if det else blk[m.end():m.end() + 200].strip())[0].strip()})
    return out


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    comp = component_dir(sys.argv[1])
    run = Path(sys.argv[2]).expanduser()
    prof = yaml.safe_load((comp / "build.yaml").read_text(encoding="utf-8"))
    fz, env = prof.get("fuzz") or sys.exit("no fuzz section in build.yaml"), prof["tests"]["environment"]
    exe = os.environ.get("SCHEMATHESIS") or shutil.which("schemathesis") or sys.exit("schemathesis not found (PATH or SCHEMATHESIS)")
    spec = run / "tests/input" / fz["openapi"]
    out = run / "report/fuzz"
    out.mkdir(parents=True, exist_ok=True)
    tok = token(env["TOKEN_URL"], env["TOKEN_CLIENT"], fz["user"], fz["password"])
    cmd = [exe, "run", str(spec), "-u", env["API_URL"], "-H", f"Authorization: Bearer {tok}", "--checks", "all",
           "-n", str(fz.get("max_examples", 30)), "--seed", str(fz.get("seed", 1)), "--max-time", str(fz.get("max_time", 300)),
           "--report", "junit", "--report-junit-path", "junit.xml", "--report-dir", str(out), "--warnings", "off", "--no-color"]
    res = subprocess.run(cmd, cwd=out, capture_output=True, text=True)
    (out / "console.txt").write_text(res.stdout[-200000:] + res.stderr[-20000:], encoding="utf-8")
    junit = out / "junit.xml"
    if not junit.exists():
        sys.exit(f"no JUnit report; see {out / 'console.txt'}")
    ops = sum(1 for _ in ET.parse(junit).getroot().iter("testcase"))
    known_file = comp / "fuzz-known.yaml"
    known = (yaml.safe_load(known_file.read_text(encoding="utf-8")) or {}).get("known", []) if known_file.exists() else []

    def explain(f):
        for k in known:
            if k.get("operation", "*") in ("*", f["operation"]) and k["check"] == f["check"] and \
               k.get("detail_contains", "") in f["detail"]:
                return k
        return None

    rows = []
    for f in failures(junit):
        k = explain(f)
        rows.append(f | ({"verdict": "explained", "decision": k["decision"], "reason": k.get("reason", "")} if k
                         else {"verdict": "finding"}))
    found = [r for r in rows if r["verdict"] == "finding"]
    server = [r for r in rows if r["check"] == "ST200" or r["title"].lower().startswith("server error")]
    summary = {"operations": ops, "failed_checks": len(rows), "explained": len(rows) - len(found), "findings": len(found),
               "server_errors": len(server), "by_check": dict(Counter(r["check"] for r in rows)),
               "schemathesis_exit": res.returncode}
    (run / "report/fuzz.json").write_text(json.dumps({"summary": summary, "failures": rows}, indent=1, ensure_ascii=False) + "\n",
                                          encoding="utf-8")
    md = ["# API fuzzing (step 70)", "",
          f"Schemathesis against `{env['API_URL']}`, contract `{fz['openapi']}`, {fz.get('max_examples', 30)} examples per operation, "
          f"seed {fz.get('seed', 1)}. Known failures from `fuzz-known.yaml` are explained by a decision; the rest are findings.", "",
          f"Operations: {ops}. Failed checks: {len(rows)}. Explained by a decision: {summary['explained']}. "
          f"Findings: {len(found)}. Server errors: {len(server)}.", "",
          "## Findings", "", "| Operation | Check | Status | Server answer |", "|---|---|---|---|"]
    md += [f"| {r['operation']} | {r['check']} {r['title']} | {r['status']} | {r['detail'][:150].replace('|', '/')} |" for r in found] or ["| none | | | |"]
    md += ["", "## Explained by a decision", "", "| Operation | Check | Decision | Reason |", "|---|---|---|---|"]
    md += [f"| {r['operation']} | {r['check']} {r['title']} | {r['decision']} | {r['reason']} |" for r in rows if r["verdict"] == "explained"]
    (run / "report/fuzz-summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
