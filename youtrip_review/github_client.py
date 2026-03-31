"""Fetch PR and review data from GitHub using the `gh` CLI."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import date

from .models import PullRequest, UserConfig


def _run_gh(args: list[str], timeout: int = 60) -> str:
    """Run a gh CLI command and return stdout."""
    cmd = ["gh"] + args
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(f"gh command failed: {' '.join(cmd)}\n{result.stderr}")
    return result.stdout.strip()


def check_gh_auth() -> bool:
    try:
        _run_gh(["auth", "status"])
        return True
    except (RuntimeError, FileNotFoundError):
        return False


def fetch_merged_prs(config: UserConfig, *, progress: bool = True) -> list[PullRequest]:
    """Fetch all merged PRs authored by the user in the date range.

    Uses GitHub search API with pagination to get all results.
    """
    if progress:
        print("  Fetching merged PRs from GitHub...", end="", flush=True)

    prs: list[PullRequest] = []
    page = 1
    per_page = 100

    while True:
        query = (
            f"repo:{config.github_repo}"
            f"+type:pr"
            f"+author:{config.github_username}"
            f"+is:merged"
            f"+created:{config.start_date.isoformat()}..{config.end_date.isoformat()}"
        )
        result = _run_gh(
            [
                "api",
                f"search/issues?q={query}&per_page={per_page}&page={page}",
                "--jq",
                ".items[].number",
            ],
            timeout=30,
        )

        if not result:
            break

        pr_numbers = [int(n) for n in result.strip().splitlines() if n.strip()]
        if not pr_numbers:
            break

        # Fetch full details for each PR in this batch
        for num in pr_numbers:
            detail_json = _run_gh(
                [
                    "pr",
                    "view",
                    str(num),
                    "--repo",
                    config.github_repo,
                    "--json",
                    "number,title,url,createdAt,mergedAt,additions,deletions",
                ],
                timeout=15,
            )
            data = json.loads(detail_json)
            prs.append(PullRequest.from_gh_json(data))
            if progress:
                print(".", end="", flush=True)

        if len(pr_numbers) < per_page:
            break
        page += 1

    if progress:
        print(f" {len(prs)} PRs found.")

    # Sort by merged date
    prs.sort(key=lambda p: p.merged_at)
    return prs


def fetch_review_count(config: UserConfig, *, progress: bool = True) -> int:
    """Count PRs reviewed by the user in the date range."""
    if progress:
        print("  Counting PRs reviewed...", end="", flush=True)

    query = (
        f"repo:{config.github_repo}"
        f"+type:pr"
        f"+reviewed-by:{config.github_username}"
        f"+is:merged"
        f"+created:{config.start_date.isoformat()}..{config.end_date.isoformat()}"
    )
    result = _run_gh(
        ["api", f"search/issues?q={query}&per_page=1", "--jq", ".total_count"],
        timeout=15,
    )
    count = int(result) if result else 0
    if progress:
        print(f" {count} reviews.")
    return count
