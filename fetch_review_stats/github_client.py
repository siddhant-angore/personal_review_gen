"""Fetch PR, review, and commit data from GitHub using the `gh` CLI."""

from __future__ import annotations

import json
import subprocess
from collections import defaultdict
from datetime import date, timedelta

from .models import GitStats, PullRequest, RepoStats, ReviewData, UserConfig
from .ui import Spinner, header, status, status_error


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


# ── PR fetching ──────────────────────────────────────────────────────


def fetch_merged_prs(
    username: str, repo: str, start: date, end: date,
) -> list[PullRequest]:
    """Fetch all merged PRs authored by the user in the date range."""
    prs: list[PullRequest] = []
    page = 1
    per_page = 100

    while True:
        query = (
            f"repo:{repo}"
            f"+type:pr"
            f"+author:{username}"
            f"+is:merged"
            f"+created:{start.isoformat()}..{end.isoformat()}"
        )
        result = _run_gh(
            ["api", f"search/issues?q={query}&per_page={per_page}&page={page}",
             "--jq", ".items[].number"],
            timeout=30,
        )

        if not result:
            break

        pr_numbers = [int(n) for n in result.strip().splitlines() if n.strip()]
        if not pr_numbers:
            break

        for num in pr_numbers:
            detail_json = _run_gh(
                ["pr", "view", str(num), "--repo", repo,
                 "--json", "number,title,url,createdAt,mergedAt,additions,deletions"],
                timeout=15,
            )
            data = json.loads(detail_json)
            prs.append(PullRequest.from_gh_json(data, repo=repo))

        if len(pr_numbers) < per_page:
            break
        page += 1

    return prs


def fetch_review_count(
    username: str, repo: str, start: date, end: date,
) -> int:
    """Count PRs reviewed by the user in the date range."""
    query = (
        f"repo:{repo}"
        f"+type:pr"
        f"+reviewed-by:{username}"
        f"+is:merged"
        f"+created:{start.isoformat()}..{end.isoformat()}"
    )
    result = _run_gh(
        ["api", f"search/issues?q={query}&per_page=1", "--jq", ".total_count"],
        timeout=15,
    )
    return int(result) if result else 0


# ── Commit stats from GitHub API ─────────────────────────────────────


def fetch_commit_stats(
    username: str, repo: str, start: date, end: date,
) -> dict[str, int]:
    """Fetch commit dates and return monthly commit counts.

    Returns: {"2025-04": 5, "2025-05": 12, ...}
    """
    # GitHub API --until is exclusive, add 1 day to include end date
    until_date = (end + timedelta(days=1)).isoformat()
    url = (
        f"repos/{repo}/commits"
        f"?author={username}"
        f"&since={start.isoformat()}T00:00:00Z"
        f"&until={until_date}T00:00:00Z"
        f"&per_page=100"
    )
    result = _run_gh(
        ["api", url, "--paginate", "--jq", ".[].commit.author.date"],
        timeout=120,
    )

    monthly: dict[str, int] = defaultdict(int)
    if result:
        for line in result.splitlines():
            if line.strip():
                month = line.strip()[:7]
                monthly[month] += 1

    return dict(monthly)


# ── PR file changes (package-level) ──────────────────────────────────


def fetch_pr_file_changes(
    repo: str, pr_numbers: list[int],
) -> dict[str, int]:
    """Fetch changed files for each PR and group by top-level package.

    Returns: {"packages/card": 15, "lib/core": 8, ...}
    """
    pkg_counts: dict[str, int] = defaultdict(int)

    for num in pr_numbers:
        try:
            result = _run_gh(
                ["api", f"repos/{repo}/pulls/{num}/files",
                 "--paginate", "--jq", ".[].filename"],
                timeout=15,
            )
        except RuntimeError:
            continue

        if result:
            for fpath in result.splitlines():
                fpath = fpath.strip()
                if not fpath:
                    continue
                segments = fpath.split("/")
                if len(segments) >= 2:
                    group = f"{segments[0]}/{segments[1]}"
                else:
                    group = segments[0]
                pkg_counts[group] += 1

    return dict(sorted(pkg_counts.items(), key=lambda x: -x[1]))


# ── Deduplication helpers ────────────────────────────────────────────


def deduplicate_prs(all_prs: list[PullRequest]) -> list[PullRequest]:
    """Deduplicate PRs by URL, preserving order."""
    seen: set[str] = set()
    unique: list[PullRequest] = []
    for pr in all_prs:
        if pr.url not in seen:
            seen.add(pr.url)
            unique.append(pr)
    return unique


# ── Monthly stats from PR data ───────────────────────────────────────


def _compute_monthly_pr_stats(
    prs: list[PullRequest],
) -> tuple[dict[str, int], dict[str, int]]:
    """Compute monthly additions/deletions from PR merge dates."""
    monthly_add: dict[str, int] = defaultdict(int)
    monthly_del: dict[str, int] = defaultdict(int)
    for pr in prs:
        month = pr.merged_at.strftime("%Y-%m")
        monthly_add[month] += pr.additions
        monthly_del[month] += pr.deletions
    return dict(monthly_add), dict(monthly_del)


# ── Multi-repo orchestrator ──────────────────────────────────────────


def fetch_all_repos(
    config: UserConfig, *, skip_file_changes: bool = False,
) -> ReviewData:
    """Fetch data from all configured repos and return consolidated ReviewData."""
    all_prs: list[PullRequest] = []
    per_repo: list[RepoStats] = []
    total_reviewed = 0
    all_monthly_commits: dict[str, int] = defaultdict(int)
    all_pkg_changes: dict[str, int] = defaultdict(int)

    username = config.github_username
    start = config.start_date
    end = config.end_date

    for repo in config.github_repos:
        print(header(repo))

        # PRs
        try:
            with Spinner("Fetching PRs..."):
                repo_prs = fetch_merged_prs(username, repo, start, end)
            print(status("PRs authored", len(repo_prs)))
        except Exception as e:
            print(status_error("PRs authored", str(e)))
            repo_prs = []

        # Reviews
        try:
            with Spinner("Fetching reviews..."):
                reviewed = fetch_review_count(username, repo, start, end)
            print(status("PRs reviewed", reviewed))
        except Exception as e:
            print(status_error("PRs reviewed", str(e)))
            reviewed = 0

        # Commits
        try:
            with Spinner("Fetching commits..."):
                monthly_commits = fetch_commit_stats(username, repo, start, end)
            print(status("Commits", sum(monthly_commits.values())))
        except Exception as e:
            print(status_error("Commits", str(e)))
            monthly_commits = {}

        # File changes (optional)
        pkg_changes: dict[str, int] = {}
        if not skip_file_changes and repo_prs:
            try:
                with Spinner("Fetching file changes..."):
                    pkg_changes = fetch_pr_file_changes(
                        repo, [pr.number for pr in repo_prs],
                    )
                print(status("File changes", "done"))
            except Exception as e:
                print(status_error("File changes", str(e)))

        # Accumulate
        all_prs.extend(repo_prs)
        total_reviewed += reviewed

        for month, count in monthly_commits.items():
            all_monthly_commits[month] += count

        for pkg, count in pkg_changes.items():
            all_pkg_changes[pkg] += count

        repo_additions = sum(pr.additions for pr in repo_prs)
        repo_deletions = sum(pr.deletions for pr in repo_prs)

        per_repo.append(RepoStats(
            repo=repo,
            prs_merged=len(repo_prs),
            prs_reviewed=reviewed,
            commits=sum(monthly_commits.values()),
            additions=repo_additions,
            deletions=repo_deletions,
        ))

    # Deduplicate
    prs = deduplicate_prs(all_prs)
    prs.sort(key=lambda p: p.merged_at)

    # Build consolidated GitStats
    monthly_add, monthly_del = _compute_monthly_pr_stats(prs)

    stats = GitStats(
        total_commits=sum(all_monthly_commits.values()),
        total_additions=sum(pr.additions for pr in prs),
        total_deletions=sum(pr.deletions for pr in prs),
        monthly_commits=dict(all_monthly_commits),
        monthly_additions=monthly_add,
        monthly_deletions=monthly_del,
        package_file_changes=dict(sorted(all_pkg_changes.items(), key=lambda x: -x[1])),
    )

    return ReviewData(
        prs_authored=prs,
        prs_reviewed_count=total_reviewed,
        git_stats=stats,
        per_repo_stats=per_repo,
    )
