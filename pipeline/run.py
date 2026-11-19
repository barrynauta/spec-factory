#!/usr/bin/env python3
"""Run steps 40 to 70 of one build run with one command: the orchestrator.

  ./factory run <component> <run>                 every step, in order
  ./factory run <component> <run> --from fuzz     resume from a step (earlier steps must be done)
  ./factory run <component> <run> --only scans    one step (or a comma-separated list)
  ./factory run <component> <run> --dry-run       print the plan and the commands, change nothing

Steps (agents run headless through the Claude Code CLI, `claude -p`):

  prepare      prepare_run.py: the two isolated workspaces (gate of step 30 must pass)
  write        agents 40 (test writer) and 50 (code writer), in parallel
  review       agent 45a (suite review, saved as tests/review/SUITE-REVIEW.md), then 45b (the test writer
               of step 40, resumed, fixes or rejects each finding; its answer is appended)
  stack        build/work/stack.sh up (the build's own start command, idempotent)
  suite        tests/work/run.sh api
  ui           agent 60 (UI test writer), then tests/work/run.sh ui
  store_down   build/work/stack.sh store-down-up, tests/work/run.sh store-down, stack.sh store-down-down
  scans        Trivy on the build folder and on every image that stack.sh images lists
  fuzz         fuzz_api.py (Schemathesis against the OpenAPI, fuzz section of build.yaml)
  load         tests/work/run.sh load, when the suite has a load test
  verify       verify.py (70a)
  design       agent 70c (independent design review), saved as report/design-review.md
  report       agent 70b (final report), saved as report/REPORT.md
  export       copy the run into <component>/runs/<run>: no .env, keys, virtualenvs, node_modules or
               build output; home paths replaced by ~; stops if a secret scanner (gitleaks) finds anything

State: RUN.json gets a "steps" entry per step (status, start, end, seconds) and, for agents, the model,
cost in USD, turns and session id. Agent transcripts' final answers are kept in <run>/logs/.

Agent settings in project.yaml (all optional):

  agents:
    command: claude                   # the Claude Code CLI
    model: ""                         # empty: the CLI default; or a model name per step under models:
    models: {write_code: "", write_tests: ""}
    permission_mode: acceptEdits      # the agents need to write files and run commands (build, docker)
    allowed_tools: [Bash, Read, Edit, Write, Glob, Grep]
    max_budget_usd: 0                 # per agent call; 0 = no limit
    deny_paths: []                    # extra paths no agent may read, for example upstream source code

Isolation: each agent gets deny rules for the other workspace, the other runs, the project folder and
the deny_paths. The rules cover the file tools; a shell command could still read a denied path, so the
briefs' isolation rules stay the main line, and the deny rules are a second one.
"""
import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from project import CFG, ENGINE, ROOT, component_dir  # noqa: E402

PIPE = ENGINE / "pipeline"
STEPS = ["prepare", "write", "review", "stack", "suite", "ui", "store_down", "scans", "fuzz", "load",
         "verify", "design", "report", "export"]
HEADLESS = ("You run headless as one step of an automated pipeline. Nobody can answer questions: decide, "
            "note your assumptions where the brief asks for them, and finish the task. ")


def now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def brief(md_file, heading):
    """The brief text under a heading: between the first two lines that are exactly '---'."""
    text = (PIPE / md_file).read_text(encoding="utf-8")
    i = text.index(heading)
    parts = text[i:].split("\n---\n")
    return parts[1].strip() + "\n"


class Run:
    def __init__(self, comp_name, run_name, dry):
        self.comp_name, self.comp, self.dry = comp_name, component_dir(comp_name), dry
        self.prof = yaml.safe_load((self.comp / "build.yaml").read_text(encoding="utf-8"))
        runs_root = Path(CFG.get("runs", "~/src/spec-factory-runs")).expanduser()
        self.runs_root = runs_root
        self.dir = runs_root / f"{CFG.get('name', 'project').lower().replace(' ', '-')}-{comp_name}-{run_name}"
        self.name = run_name
        self.ag = CFG.get("agents") or {}
        self.logs = self.dir / "logs"

    # ---------- state ----------
    def state(self):
        p = self.dir / "RUN.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

    def mark(self, step, **kw):
        if self.dry or not self.dir.exists():
            return
        st = self.state()
        st.setdefault("steps", {}).setdefault(step, {}).update(kw)
        (self.dir / "RUN.json").write_text(json.dumps(st, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    def done(self, step):
        return (self.state().get("steps") or {}).get(step, {}).get("status") == "done"

    # ---------- helpers ----------
    def sh(self, cmd, cwd=None, env=None, check=True, timeout=None):
        print(f"  $ {' '.join(map(str, cmd)) if isinstance(cmd, list) else cmd}" + (f"   (in {cwd})" if cwd else ""))
        if self.dry:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        r = subprocess.run(cmd, cwd=cwd, env={**os.environ, **(env or {})}, capture_output=True, text=True, timeout=timeout)
        if check and r.returncode != 0:
            raise RuntimeError(f"command failed ({r.returncode}): {cmd}\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
        return r

    def deny_rules(self, own, project_ok=False):
        """Read and write deny rules: everything of the run except the agent's own part, other runs, project."""
        paths = [p for p in (self.dir / "tests", self.dir / "build", self.dir / "report") if p not in own]
        if self.runs_root.exists():
            paths += [p for p in self.runs_root.iterdir() if p.is_dir() and p != self.dir and not p.name.startswith("_")]
        paths += ([] if project_ok else [ROOT]) + [Path(x).expanduser() for x in self.ag.get("deny_paths", [])]
        rules = []
        for p in paths:
            for tool in ("Read", "Edit", "Write", "Glob", "Grep"):
                rules.append(f"{tool}(/{p}/**)")
        return rules

    def agent(self, step, label, prompt, own, resume=None, model_key=None, project_ok=False):
        """One headless agent call. own: the folders it may use. Returns (text, record)."""
        model = (self.ag.get("models") or {}).get(model_key or label) or self.ag.get("model") or ""
        # disableAllHooks: the user's own hooks (session logs, start-up context) must not run inside a factory agent.
        settings = {"disableAllHooks": True, "permissions": {"deny": self.deny_rules(own, project_ok)}}
        cmd = [self.ag.get("command", "claude"), "-p", HEADLESS + prompt, "--output-format", "json",
               "--permission-mode", self.ag.get("permission_mode", "acceptEdits"),
               "--allowedTools", *self.ag.get("allowed_tools", ["Bash", "Read", "Edit", "Write", "Glob", "Grep"]),
               "--settings", json.dumps(settings)]
        for d in own:
            cmd += ["--add-dir", str(d)]
        if model:
            cmd += ["--model", model]
        if self.ag.get("max_budget_usd"):
            cmd += ["--max-budget-usd", str(self.ag["max_budget_usd"])]
        if resume:
            cmd += ["--resume", resume]
        print(f"  agent {label} in {own[0]}" + (f" (resumes {resume})" if resume else "") + (f", model {model}" if model else ""))
        if self.dry:
            return "", {}
        self.logs.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        r = subprocess.run(cmd, cwd=own[0], capture_output=True, text=True)
        try:
            out = json.loads(r.stdout)
        except json.JSONDecodeError:
            raise RuntimeError(f"agent {label}: no JSON answer (exit {r.returncode})\n{r.stderr[-2000:]}")
        text = out.get("result", "")
        (self.logs / f"{label}.md").write_text(text, encoding="utf-8")
        rec = {"model": model or "default", "cost_usd": out.get("total_cost_usd"), "turns": out.get("num_turns"),
               "seconds": round(time.time() - t0), "session_id": out.get("session_id"), "is_error": out.get("is_error")}
        if out.get("is_error") or r.returncode != 0:
            raise RuntimeError(f"agent {label} ended with an error: {text[-1500:]}")
        return text, rec

    @staticmethod
    def before_summary(text, title):
        """The document part of an agent answer: from its title line up to '=== SUMMARY ==='."""
        body = text[text.index(title):] if title in text else text
        return body.split("=== SUMMARY ===")[0].rstrip() + "\n"

    def fill(self, text):
        return text.replace("{RUN}", str(self.dir))

    # ---------- steps ----------
    def s_prepare(self):
        self.sh([sys.executable, PIPE / "prepare_run.py", self.comp_name, self.name, "--runs", str(self.runs_root)])

    def s_write(self):
        """Steps 40 and 50 in parallel."""
        jobs = {"write_tests": (brief("40-test-writer.md", "## Brief for a fresh agent"), [self.dir / "tests"]),
                "write_code": (brief("50-code-writer.md", "## Brief for a fresh agent"), [self.dir / "build"])}
        if self.dry:
            for k, (b, own) in jobs.items():
                self.agent("write", k, self.fill(b), own)
            return
        import concurrent.futures as cf
        prev = (self.state().get("steps") or {}).get("write", {})
        for k in [k for k in jobs if (prev.get(k) or {}).get("is_error") is False]:
            print(f"  agent {k} finished in an earlier attempt: skipped")
            jobs.pop(k)
        for k, (b, own) in list(jobs.items()):
            if any((own[0] / "work").iterdir()):
                jobs[k] = (b + "\nNote: `work/` already holds a partial result of an earlier attempt of this step that was "
                               "interrupted. Check what is there, keep what is sound, and finish the task.\n", own)
        with cf.ThreadPoolExecutor(2) as ex:
            fut = {k: ex.submit(self.agent, "write", k, self.fill(b), own) for k, (b, own) in jobs.items()}
            for k, f in fut.items():
                _, rec = f.result()
                self.mark("write", **{k: rec})

    def s_review(self):
        rev_dir = self.dir / "tests/review"
        if not self.dry:
            rev_dir.mkdir(parents=True, exist_ok=True)
        text, rec = self.agent("review", "review_45a", self.fill(brief("45-suite-review.md", "## 45a: brief")), [self.dir / "tests"])
        if not self.dry:
            (rev_dir / "SUITE-REVIEW.md").write_text(self.before_summary(text, "# Suite review"), encoding="utf-8")
            self.mark("review", review_45a=rec)
        session = ((self.state().get("steps") or {}).get("write", {}).get("write_tests") or {}).get("session_id")
        ans, rec = self.agent("review", "fix_45b", self.fill(brief("45-suite-review.md", "## 45b: brief")),
                              [self.dir / "tests"], resume=session, model_key="write_tests")
        if not self.dry:
            with open(rev_dir / "SUITE-REVIEW.md", "a", encoding="utf-8") as f:
                f.write("\n## Answers of the test writer (45b)\n\n" + ans.strip() + "\n")
            self.mark("review", fix_45b=rec)

    def s_stack(self):
        self.sh(["bash", "stack.sh", "up"], cwd=self.dir / "build/work", timeout=1800)

    def suite(self, mode, extra_env=None):
        self.sh(["bash", "run.sh", mode], cwd=self.dir / "tests/work", env=extra_env, check=False, timeout=3600)

    def s_suite(self):
        self.suite("api")

    def s_ui(self):
        self.agent("ui", "ui_60", self.fill(brief("60-test-writer-ui.md", "## Brief for a fresh agent")), [self.dir / "tests"],
                   model_key="write_tests")
        self.suite("ui")

    def s_store_down(self):
        w = self.dir / "build/work"
        self.sh(["bash", "stack.sh", "store-down-up"], cwd=w, timeout=600)
        try:
            self.suite("store-down")
        finally:
            self.sh(["bash", "stack.sh", "store-down-down"], cwd=w, check=False)

    def s_scans(self):
        rep = self.dir / "report"
        trivy = shutil.which("trivy")
        if not trivy:
            if not self.dry:
                rep.mkdir(exist_ok=True)
                (rep / "scan-summary.md").write_text("# Scan summary\n\nTrivy is not installed; no scan was run.\n", encoding="utf-8")
            return
        if not self.dry:
            rep.mkdir(exist_ok=True)
        self.sh([trivy, "fs", "--quiet", "--scanners", "vuln", "--severity", "HIGH,CRITICAL", "--format", "json",
                 "-o", rep / "trivy-deps.json", self.dir / "build/work"])
        imgs = self.sh(["bash", "stack.sh", "images"], cwd=self.dir / "build/work").stdout.split()
        rows = []
        for img in imgs:
            safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", img.split("@")[0])[:60]
            self.sh([trivy, "image", "--quiet", "--severity", "HIGH,CRITICAL", "--format", "json", "-o", rep / f"trivy-{safe}.json", img])
        if self.dry:
            return
        for f in sorted(rep.glob("trivy-*.json")):
            c = {"CRITICAL": 0, "HIGH": 0}
            for res in json.loads(f.read_text()).get("Results") or []:
                for v in res.get("Vulnerabilities") or []:
                    c[v["Severity"]] = c.get(v["Severity"], 0) + 1
            rows.append(f"| {f.stem[6:]} | {c['CRITICAL']} | {c['HIGH']} |")
        md = ["# Scan summary (step 70, orchestrator)", "", f"Trivy, HIGH and CRITICAL only, {now()}, independent of the build's own scan.", "",
              "| Target | CRITICAL | HIGH |", "|---|---|---|"] + rows
        (rep / "scan-summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    def s_fuzz(self):
        if not self.prof.get("fuzz"):
            print("  no fuzz section in build.yaml: skipped")
            return
        self.sh([sys.executable, PIPE / "fuzz_api.py", self.comp_name, str(self.dir)], timeout=1800)

    def s_load(self):
        if not (self.dir / "tests/work/load").exists() and not self.dry:
            print("  the suite has no load test: skipped")
            return
        self.suite("load")
        src = self.dir / "tests/work/reports/load.json"
        if src.exists():
            shutil.copy(src, self.dir / "report/load.json")

    def s_verify(self):
        self.sh([sys.executable, PIPE / "verify.py", self.comp_name, str(self.dir)])

    def s_design(self):
        text, rec = self.agent("design", "design_70c", self.fill(brief("70-verify.md", "## 70c: brief")), [self.dir / "build"])
        if not self.dry:
            (self.dir / "report/design-review.md").write_text(self.before_summary(text, "# Design review"), encoding="utf-8")
            self.mark("design", design_70c=rec)

    def s_report(self):
        own = [self.dir / "report", self.dir / "tests", self.dir / "build"]
        # 70b may read the project folder: it compares with earlier runs kept there.
        text, rec = self.agent("report", "report_70b", self.fill(brief("70-verify.md", "## 70b: brief")), own, project_ok=True)
        if not self.dry:
            m = re.search(r"^# .*$", text, re.M)
            (self.dir / "report/REPORT.md").write_text(self.before_summary(text, m.group(0) if m else ""), encoding="utf-8")
            self.mark("report", report_70b=rec)

    def s_export(self):
        dest = self.comp / "runs" / self.name
        if dest.exists() and not self.dry:
            raise RuntimeError(f"{dest} exists: an export is never overwritten")
        skip = shutil.ignore_patterns(".venv", ".venv-*", "venv", "node_modules", "target", "dist", "__pycache__", ".pytest_cache", ".hypothesis",
                                      ".env", ".env.*", "*.pem", "*.key", "*.p12", "*.jks", ".ui-state")
        print(f"  copy to {dest}")
        if self.dry:
            return
        for src, name in ((self.dir / "tests/work", "tests"), (self.dir / "tests/review", "tests-review"),
                          (self.dir / "build/work", "build"), (self.dir / "report", "report")):
            if src.exists():
                shutil.copytree(src, dest / name, ignore=skip)
        shutil.copy(self.dir / "RUN.json", dest / "RUN.json")
        home = str(Path.home())
        for f in dest.rglob("*"):
            if f.is_file() and f.stat().st_size < 20_000_000:
                try:
                    t = f.read_text(encoding="utf-8")
                except (UnicodeDecodeError, OSError):
                    continue
                if home in t:
                    f.write_text(t.replace(home, "~"), encoding="utf-8")
        leaks = [str(f) for f in dest.rglob("*") if f.name.startswith(".env") or f.suffix in (".pem", ".key")]
        gl = shutil.which("gitleaks")
        if gl:
            r = subprocess.run([gl, "dir", str(dest), "--no-banner", "--redact", "--exit-code", "3"], capture_output=True, text=True)
            if r.returncode == 3:
                leaks.append("gitleaks: " + r.stdout[-1500:])
        if leaks:
            raise RuntimeError("export stopped, possible secrets:\n" + "\n".join(leaks))
        files = sum(1 for f in dest.rglob("*") if f.is_file())
        print(f"  {files} files exported" + ("" if gl else " (gitleaks not installed: only file names were checked)"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("component")
    ap.add_argument("run")
    ap.add_argument("--from", dest="start", choices=STEPS)
    ap.add_argument("--only")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    r = Run(a.component, a.run, a.dry_run)
    steps = a.only.split(",") if a.only else STEPS[STEPS.index(a.start):] if a.start else STEPS
    bad = [s for s in steps if s not in STEPS]
    if bad:
        sys.exit(f"unknown steps: {bad}; steps are {STEPS}")
    if a.start and not a.dry_run:
        missing = [s for s in STEPS[:STEPS.index(a.start)] if not r.done(s)]
        if missing:
            sys.exit(f"--from {a.start}: these earlier steps are not done: {missing}")
    print(f"run {r.dir}{' (dry run)' if a.dry_run else ''}")
    for s in steps:
        if s == "prepare" and r.dir.exists() and not a.dry_run:
            print("prepare: workspace exists, skipped")
            continue
        print(f"{s}:")
        t0 = time.time()
        r.mark(s, status="running", start=now())
        try:
            getattr(r, f"s_{s}")()
        except Exception as e:  # noqa: BLE001
            r.mark(s, status="failed", end=now(), error=str(e)[:2000])
            sys.exit(f"step {s} failed: {e}\nResume with: ./factory run {a.component} {a.run} --from {s}")
        if s == "prepare":
            r.mark(s, start=datetime.datetime.fromtimestamp(t0).isoformat(timespec="seconds"))
        r.mark(s, status="done", end=now(), seconds=round(time.time() - t0))
    if not a.dry_run:
        st = r.state().get("steps", {})
        cost = sum((v.get("cost_usd") or 0) for s in st.values() for v in s.values() if isinstance(v, dict))
        print(f"finished; agent cost about {cost:.2f} USD; state in {r.dir / 'RUN.json'}")


if __name__ == "__main__":
    main()
