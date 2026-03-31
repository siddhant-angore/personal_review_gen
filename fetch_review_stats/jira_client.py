"""Fetch JIRA ticket data using the ACLI (Atlassian CLI)."""

from __future__ import annotations

import csv
import io
import subprocess

from .models import JiraTicket, UserConfig
from .ui import status


def _run_acli(args: list[str], timeout: int = 120) -> str:
    """Run an acli command and return stdout."""
    cmd = ["acli"] + args
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(f"acli command failed: {' '.join(cmd)}\n{result.stderr}")
    return result.stdout.strip()


def check_acli_auth() -> bool:
    try:
        result = subprocess.run(
            ["acli", "jira", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def fetch_tickets(config: UserConfig) -> list[JiraTicket]:
    """Fetch all JIRA tickets assigned to the user in the date range."""
    # Build exclude clause
    exclude_clause = ""
    if config.jira_exclude_projects:
        projects = ", ".join(config.jira_exclude_projects)
        exclude_clause = f" AND project NOT IN ({projects})"

    jql = (
        f"assignee = '{config.jira_username}'"
        f" AND updated >= '{config.start_date.isoformat()}'"
        f" AND updated <= '{config.end_date.isoformat()}'"
        f"{exclude_clause}"
        f" ORDER BY key ASC"
    )

    csv_output = _run_acli(
        [
            "jira",
            "workitem",
            "search",
            "--jql",
            jql,
            "--fields",
            "key,summary,issuetype,status,priority",
            "--csv",
            "--paginate",
        ],
        timeout=120,
    )

    tickets: list[JiraTicket] = []
    reader = csv.DictReader(io.StringIO(csv_output))
    for row in reader:
        tickets.append(
            JiraTicket(
                key=row.get("Key", ""),
                summary=row.get("Summary", ""),
                issue_type=row.get("Type", ""),
                status=row.get("Status", ""),
                priority=row.get("Priority", ""),
            )
        )

    print(status("JIRA tickets", len(tickets), "found"))
    return tickets
