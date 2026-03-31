"""Load configuration from config.toml."""

from __future__ import annotations

import shutil
import sys
import tomllib
from datetime import date
from pathlib import Path

from .models import UserConfig
from .ui import bold, error, purple, success, warn

# config.toml lives next to this file inside the package
_PACKAGE_DIR = Path(__file__).parent
_BUNDLED_CONFIG = _PACKAGE_DIR / "config.toml"
# User's working-directory copy (created on first run)
_LOCAL_CONFIG = Path("your_stats_review_config.toml")


def _ensure_config_exists() -> Path:
    """Return the path to the config file, copying the template if needed."""
    if _LOCAL_CONFIG.exists():
        return _LOCAL_CONFIG
    shutil.copy(_BUNDLED_CONFIG, _LOCAL_CONFIG)
    print(f"\n{success('Created')} {purple(str(_LOCAL_CONFIG))}")
    print(f"  Fill in your details and re-run: {bold('uv run fetch-review-stats')}\n")
    sys.exit(0)


def load_config(config_path: str | None = None) -> UserConfig:
    """Parse the TOML config file and return a UserConfig."""
    path = Path(config_path) if config_path else _ensure_config_exists()

    if not path.exists():
        print(error(f"Config file not found: {purple(str(path))}"))
        sys.exit(1)

    with path.open("rb") as f:
        raw = tomllib.load(f)

    gh = raw.get("github", {})
    jira = raw.get("jira", {})
    period = raw.get("period", {})
    output = raw.get("output", {})

    # Support both new (repos list) and old (repo string) formats
    repos = gh.get("repos", [])
    if not repos and gh.get("repo"):
        repos = [gh["repo"]]
        print(warn(f"Config uses deprecated 'github.repo'. Update to 'github.repos = [\"{gh['repo']}\"]'"))

    # Validate required fields
    missing = []
    if not gh.get("username"):
        missing.append("github.username")
    if not repos:
        missing.append("github.repos")
    if not period.get("start"):
        missing.append("period.start")
    if not period.get("end"):
        missing.append("period.end")

    if missing:
        print(error(f"Missing required config fields: {', '.join(missing)}"))
        print(f"  Edit {purple(str(path))} and fill them in.")
        sys.exit(1)

    output_dir = str(Path(output.get("dir", "./review_output")).resolve())

    return UserConfig(
        github_username=gh["username"],
        github_repos=repos,
        jira_username=jira.get("username", ""),
        jira_base_url=jira.get("base_url", "").rstrip("/"),
        jira_exclude_projects=jira.get("exclude_projects", ["TEST"]),
        start_date=date.fromisoformat(period["start"]),
        end_date=date.fromisoformat(period["end"]),
        output_dir=output_dir,
    )
