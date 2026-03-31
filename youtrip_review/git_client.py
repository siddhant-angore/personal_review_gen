"""Fetch git statistics from the local repository."""

from __future__ import annotations

import subprocess
from collections import defaultdict
from datetime import date

from .models import GitStats, UserConfig


def _run_git(args: list[str], cwd: str | None = None, timeout: int = 30) -> str:
    cmd = ["git"] + args
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
    if result.returncode != 0:
        raise RuntimeError(f"git command failed: {' '.join(cmd)}\n{result.stderr}")
    return result.stdout.strip()


def fetch_git_stats(config: UserConfig, *, progress: bool = True) -> GitStats:
    """Gather commit counts, LOC, and package-level breakdown from git log."""
    if progress:
        print("  Collecting git statistics...", end="", flush=True)

    stats = GitStats()
    author = config.git_author_name
    since = config.start_date.isoformat()
    until = config.end_date.isoformat()
    cwd = config.git_repo_path

    # Total non-merge commits
    result = _run_git(
        ["log", f"--author={author}", f"--since={since}", f"--until={until}",
         "--oneline", "--no-merges"], cwd=cwd
    )
    stats.total_commits = len(result.splitlines()) if result else 0

    # Monthly breakdown
    start = config.start_date
    end = config.end_date
    current_year = start.year
    current_month = start.month

    while date(current_year, current_month, 1) <= end:
        month_str = f"{current_year}-{current_month:02d}"
        month_since = f"{current_year}-{current_month:02d}-01"
        # Last day of month
        if current_month == 12:
            next_year, next_month = current_year + 1, 1
        else:
            next_year, next_month = current_year, current_month + 1
        month_until = f"{next_year}-{next_month:02d}-01"

        # Commit count
        result = _run_git(
            ["log", f"--author={author}", f"--since={month_since}", f"--until={month_until}",
             "--oneline", "--no-merges"], cwd=cwd
        )
        commit_count = len(result.splitlines()) if result else 0
        stats.monthly_commits[month_str] = commit_count

        # LOC
        result = _run_git(
            ["log", f"--author={author}", f"--since={month_since}", f"--until={month_until}",
             "--shortstat", "--no-merges", "--format="], cwd=cwd
        )
        ins, dels = 0, 0
        for line in result.splitlines():
            parts = line.strip().split(",")
            for part in parts:
                part = part.strip()
                if "insertion" in part:
                    ins += int(part.split()[0])
                elif "deletion" in part:
                    dels += int(part.split()[0])
        stats.monthly_additions[month_str] = ins
        stats.monthly_deletions[month_str] = dels
        stats.total_additions += ins
        stats.total_deletions += dels

        if progress:
            print(".", end="", flush=True)

        # Advance month
        current_month += 1
        if current_month > 12:
            current_month = 1
            current_year += 1

    # Package-level file change counts
    result = _run_git(
        ["log", f"--author={author}", f"--since={since}", f"--until={until}",
         "--no-merges", "--numstat", "--format="], cwd=cwd
    )
    pkg_counts: dict[str, int] = defaultdict(int)
    for line in result.splitlines():
        parts = line.split("\t")
        if len(parts) >= 3:
            filepath = parts[2]
            # Group by top two path segments (e.g. packages/card)
            segments = filepath.split("/")
            if len(segments) >= 2:
                group = f"{segments[0]}/{segments[1]}"
            else:
                group = segments[0]
            pkg_counts[group] += 1
    stats.package_file_changes = dict(sorted(pkg_counts.items(), key=lambda x: -x[1]))

    if progress:
        print(f" done. ({stats.total_commits} commits)")

    return stats
