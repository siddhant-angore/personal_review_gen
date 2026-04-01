"""Data models for year-end review."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from functools import cached_property

_JIRA_KEY_RE = re.compile(r"[A-Z][A-Z0-9]+-\d+")

JIRA_CATEGORY_MAP: dict[str, str] = {
    "FKX": "Bug Fixes",
    "FUNDS": "Funds & Remittance",
    "PT": "Cards & Transactions",
    "WASABI": "Core feature team I",
    "SESAME": "Core feature team II",
}

JIRA_DONE_STATUSES = frozenset({"Done", "Closed"})


@dataclass
class PullRequest:
    number: int
    title: str
    url: str
    created_at: date
    merged_at: date
    additions: int
    deletions: int
    repo: str = ""  # "owner/repo"

    @cached_property
    def jira_keys(self) -> list[str]:
        """Extract JIRA ticket keys from the PR title."""
        return _JIRA_KEY_RE.findall(self.title)

    @cached_property
    def category(self) -> str:
        """Categorize PR based on JIRA project prefix."""
        keys = self.jira_keys
        if not keys:
            return "Other"
        prefix = keys[0].split("-")[0]
        return JIRA_CATEGORY_MAP.get(prefix, "Other")

    @classmethod
    def from_gh_json(cls, data: dict, repo: str = "") -> PullRequest:
        return cls(
            number=data["number"],
            title=data["title"],
            url=data["url"],
            created_at=datetime.fromisoformat(
                data["createdAt"].replace("Z", "+00:00")
            ).date(),
            merged_at=datetime.fromisoformat(
                data["mergedAt"].replace("Z", "+00:00")
            ).date(),
            additions=data["additions"],
            deletions=data["deletions"],
            repo=repo,
        )


@dataclass
class JiraTicket:
    key: str
    summary: str
    issue_type: str
    status: str
    priority: str

    @property
    def project(self) -> str:
        return self.key.split("-")[0]

    def url_for(self, jira_base_url: str) -> str:
        return f"{jira_base_url}/browse/{self.key}"


@dataclass
class GitStats:
    total_commits: int = 0
    total_additions: int = 0
    total_deletions: int = 0
    monthly_commits: dict[str, int] = field(default_factory=dict)
    monthly_additions: dict[str, int] = field(default_factory=dict)
    monthly_deletions: dict[str, int] = field(default_factory=dict)
    package_file_changes: dict[str, int] = field(default_factory=dict)


@dataclass
class RepoStats:
    """Per-repo summary for the breakdown table."""

    repo: str
    prs_merged: int = 0
    prs_reviewed: int = 0
    commits: int = 0
    additions: int = 0
    deletions: int = 0


@dataclass
class ReviewData:
    prs_authored: list[PullRequest] = field(default_factory=list)
    prs_reviewed_count: int = 0
    jira_tickets: list[JiraTicket] = field(default_factory=list)
    git_stats: GitStats = field(default_factory=GitStats)
    per_repo_stats: list[RepoStats] = field(default_factory=list)


@dataclass
class UserConfig:
    github_username: str
    github_repos: list[str]  # ["owner/repo1", "owner/repo2"]
    jira_username: str
    jira_base_url: str
    start_date: date
    end_date: date
    output_dir: str = "./review_output"
    jira_exclude_projects: list[str] = field(default_factory=list)
