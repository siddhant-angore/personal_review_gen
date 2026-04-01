"""Export fetched data to CSV files."""

from __future__ import annotations

import csv
from pathlib import Path

from .models import JIRA_BUG_CATEGORY, JIRA_DONE_STATUSES, GitStats, JiraTicket, PullRequest, RepoStats, UserConfig


def _prefix(config: UserConfig) -> str:
    """Date-range prefix for output filenames."""
    return f"{config.github_username}_{config.start_date.isoformat()}_to_{config.end_date.isoformat()}"


def export_prs(prs: list[PullRequest], config: UserConfig) -> Path:
    path = Path(config.output_dir) / f"prs_{_prefix(config)}.csv"
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Repo", "Number", "Title", "URL", "Created", "Merged",
            "Additions", "Deletions", "Net", "Category", "JIRA Keys",
        ])
        for pr in prs:
            writer.writerow([
                pr.repo,
                pr.number,
                pr.title,
                pr.url,
                pr.created_at.isoformat(),
                pr.merged_at.isoformat(),
                pr.additions,
                pr.deletions,
                pr.additions - pr.deletions,
                pr.category,
                ";".join(pr.jira_keys),
            ])
    return path


def export_jira_tickets(tickets: list[JiraTicket], config: UserConfig) -> Path:
    path = Path(config.output_dir) / f"jira_tickets_{_prefix(config)}.csv"
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Key", "URL", "Type", "Priority", "Status", "Project", "Summary"])
        for t in tickets:
            writer.writerow([
                t.key,
                t.url_for(config.jira_base_url),
                t.issue_type,
                t.priority,
                t.status,
                t.project,
                t.summary,
            ])
    return path


def export_git_stats(stats: GitStats, config: UserConfig) -> Path:
    path = Path(config.output_dir) / f"git_stats_{_prefix(config)}.csv"
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Month", "Commits", "Additions", "Deletions", "Net"])
        for month in sorted(stats.monthly_commits.keys()):
            commits = stats.monthly_commits.get(month, 0)
            ins = stats.monthly_additions.get(month, 0)
            dels = stats.monthly_deletions.get(month, 0)
            writer.writerow([month, commits, ins, dels, ins - dels])
    return path


def export_summary(
    prs: list[PullRequest],
    tickets: list[JiraTicket],
    stats: GitStats,
    review_count: int,
    per_repo_stats: list[RepoStats],
    config: UserConfig,
) -> Path:
    path = Path(config.output_dir) / f"summary_{_prefix(config)}.csv"
    done_count = sum(1 for t in tickets if t.status in JIRA_DONE_STATUSES)
    bug_prs = sum(1 for pr in prs if pr.category == JIRA_BUG_CATEGORY)
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Repo", "GitHub Username", "Period Start", "Period End",
            "PRs Merged", "PRs Reviewed", "Lines Added", "Lines Deleted", "Net Lines",
            "Commits", "JIRA Tickets", "JIRA Completed", "Bug Fixes PRs", "Packages Touched",
        ])
        # Per-repo rows
        for rs in per_repo_stats:
            writer.writerow([
                rs.repo, config.github_username,
                config.start_date.isoformat(), config.end_date.isoformat(),
                rs.prs_merged, rs.prs_reviewed,
                rs.additions, rs.deletions, rs.additions - rs.deletions,
                rs.commits, "", "", "", "",
            ])
        # Totals row
        writer.writerow([
            "TOTAL", config.github_username,
            config.start_date.isoformat(), config.end_date.isoformat(),
            len(prs), review_count,
            stats.total_additions, stats.total_deletions,
            stats.total_additions - stats.total_deletions,
            stats.total_commits, len(tickets), done_count,
            bug_prs, len(stats.package_file_changes),
        ])
    return path


def export_all(
    prs: list[PullRequest],
    tickets: list[JiraTicket],
    stats: GitStats,
    review_count: int,
    per_repo_stats: list[RepoStats],
    config: UserConfig,
) -> list[Path]:
    """Export all data to CSV files."""
    Path(config.output_dir).mkdir(parents=True, exist_ok=True)
    return [
        export_prs(prs, config),
        export_jira_tickets(tickets, config),
        export_git_stats(stats, config),
        export_summary(prs, tickets, stats, review_count, per_repo_stats, config),
    ]
