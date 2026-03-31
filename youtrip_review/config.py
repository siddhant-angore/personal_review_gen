"""Load configuration from config.toml."""

from __future__ import annotations

import shutil
import sys
import tomllib
from datetime import date
from pathlib import Path

from .models import UserConfig

# config.toml lives next to this file inside the package
_PACKAGE_DIR = Path(__file__).parent
_BUNDLED_CONFIG = _PACKAGE_DIR / "config.toml"
# User's working-directory copy (created on first run)
_LOCAL_CONFIG = Path("youtrip_review_config.toml")


def _ensure_config_exists() -> Path:
    """Return the path to the config file, copying the template if needed."""
    if _LOCAL_CONFIG.exists():
        return _LOCAL_CONFIG
    shutil.copy(_BUNDLED_CONFIG, _LOCAL_CONFIG)
    print(f"\n  Created {_LOCAL_CONFIG}")
    print("  Fill in your details and re-run:  uv run youtrip-review\n")
    sys.exit(0)


def load_config(config_path: str | None = None) -> UserConfig:
    """Parse the TOML config file and return a UserConfig."""
    path = Path(config_path) if config_path else _ensure_config_exists()

    if not path.exists():
        print(f"  Config file not found: {path}")
        sys.exit(1)

    with path.open("rb") as f:
        raw = tomllib.load(f)

    gh = raw.get("github", {})
    git = raw.get("git", {})
    jira = raw.get("jira", {})
    period = raw.get("period", {})
    output = raw.get("output", {})

    # Validate required fields
    missing = []
    if not gh.get("username"):
        missing.append("github.username")
    if not gh.get("repo"):
        missing.append("github.repo")
    if not period.get("start"):
        missing.append("period.start")
    if not period.get("end"):
        missing.append("period.end")

    if missing:
        print(f"  Missing required config fields: {', '.join(missing)}")
        print(f"  Edit {path} and fill them in.")
        sys.exit(1)

    output_dir = str(Path(output.get("dir", ".")).resolve())
    repo_path_raw = git.get("repo_path", "")
    git_repo_path = str(Path(repo_path_raw).expanduser().resolve()) if repo_path_raw else "."

    return UserConfig(
        github_username=gh["username"],
        github_repo=gh["repo"],
        git_author_name=git.get("author_name", gh["username"]),
        jira_username=jira.get("username", ""),
        jira_base_url=jira.get("base_url", "").rstrip("/"),
        jira_exclude_projects=jira.get("exclude_projects", ["TEST"]),
        start_date=date.fromisoformat(period["start"]),
        end_date=date.fromisoformat(period["end"]),
        output_dir=output_dir,
        git_repo_path=git_repo_path,
    )
