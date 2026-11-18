"""Where the project is, and its settings.

The engine (this repository) holds the steps; a project folder holds the data of one
programme: project.yaml, guidelines/, cdm/ and components/<name>/. The scripts find the
project through the environment variable SPEC_FACTORY_PROJECT (set by the project's
`factory` wrapper), or the current directory.

Everything programme-specific (issue key prefix, Jira and GitLab addresses, API
conventions) comes from project.yaml, never from the scripts.
"""
import os
import re
import subprocess
from pathlib import Path

import yaml

ENGINE = Path(__file__).resolve().parent.parent
ROOT = Path(os.environ.get("SPEC_FACTORY_PROJECT", os.getcwd())).resolve()
_cfg_file = ROOT / "project.yaml"
CFG = yaml.safe_load(_cfg_file.read_text(encoding="utf-8")) if _cfg_file.exists() else {}

# Issue key prefix of the stories (project.yaml story_key, for example PROJ for PROJ-123).
# Without it, any Jira-style key (upper-case letters and digits, a hyphen, a number) is accepted.
STORY_KEY = CFG.get("story_key")
KEY_PREFIX_RE = re.escape(STORY_KEY) if STORY_KEY else r"[A-Z][A-Z0-9]+"
KEY_RE = rf"\b{KEY_PREFIX_RE}-\d+\b"
STORY_GLOB = f"{STORY_KEY}-*.md" if STORY_KEY else "*-*.md"
JIRA_URL = os.environ.get("JIRA_URL", CFG.get("jira_url", "")).rstrip("/")
GITLAB_URL = os.environ.get("GITLAB_URL", CFG.get("gitlab_url", "https://gitlab.com")).rstrip("/")
GITLAB_GROUP = CFG.get("gitlab_group", "")
GITLAB_SKIP = CFG.get("gitlab_skip", [])
# Where step 10 looks for CDM files in each repository (project.yaml cdm_paths). A path whose files
# are all CDMs is listed with all: true; otherwise only file names that look like a CDM count.
CDM_PATHS = CFG.get("cdm_paths", [])
API = CFG.get("api_conventions", {})


def component_dir(name):
    """components/<name>; a name that is a path (for example '.') is taken as is."""
    p = ROOT / "components" / name
    return p if p.is_dir() else (ROOT / name).resolve()


def engine_commit():
    try:
        return subprocess.run(["git", "-C", str(ENGINE), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def engine_ref(script):
    """How a generated file names the script that made it: path in the engine plus its commit."""
    return f"`spec-factory/pipeline/{script}` (engine {engine_commit()})"


def load_rules():
    """The engine rules (guidelines/rules.json in the engine) plus the project's own rules
    (guidelines/rules.json in the project, from step 11). A project rule with the same id wins."""
    import json
    rules = {}
    for origin, f in (("engine", ENGINE / "guidelines/rules.json"), ("project", ROOT / "guidelines/rules.json")):
        if f.exists():
            for r in json.loads(f.read_text(encoding="utf-8")):
                r["origin"] = origin
                rules[r["id"]] = r
    return rules
