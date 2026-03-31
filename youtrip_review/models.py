"""Data models for year-end review."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class PullRequest:
    number: int
    title: str
    url: str
    created_at: date
    merged_at: date
    additions: int
    deletions: int

    @property
    def jira_keys(self) -> list[str]:
        """Extract JIRA ticket keys from the PR title."""
        import re

        return re.findall(r"[A-Z][A-Z0-9]+-\d+", self.title)

    @property
    def category(self) -> str:
        """Categorize PR based on JIRA project prefix."""
        keys = self.jira_keys
        if not keys:
            return "Other"
        prefix = keys[0].split("-")[0]
        categories = {
            "FKX": "Bug Fix",
            "FUNDS": "Funds & Remittance",
            "PT": "Product & Features",
            "WASABI": "Code Quality",
            "SESAME": "Platform & Infrastructure",
        }
        return categories.get(prefix, "Other")

    @classmethod
    def from_gh_json(cls, data: dict) -> PullRequest:
        return cls(
            number=data["number"],
            title=data["title"],
            url=data["url"],
            created_at=datetime.fromisoformat(data["createdAt"].replace("Z", "+00:00")).date(),
            merged_at=datetime.fromisoformat(data["mergedAt"].replace("Z", "+00:00")).date(),
            additions=data["additions"],
            deletions=data["deletions"],
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

    @property
    def url(self) -> str:
        # Will be set from config
        return ""

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
class ReviewData:
    prs_authored: list[PullRequest] = field(default_factory=list)
    prs_reviewed_count: int = 0
    jira_tickets: list[JiraTicket] = field(default_factory=list)
    git_stats: GitStats = field(default_factory=GitStats)


@dataclass
class UserConfig:
    github_username: str
    github_repo: str  # "owner/repo"
    jira_username: str  # email for ACLI
    jira_base_url: str  # e.g. "https://yourorg.atlassian.net"
    git_author_name: str  # for git log --author
    start_date: date
    end_date: date
    output_dir: str = "."
    git_repo_path: str = "."  # local repo path for git log
    jira_exclude_projects: list[str] = field(default_factory=list)
