"""Generate the year-end review markdown document."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from .models import GitStats, JiraTicket, PullRequest, UserConfig


def _fmt(n: int) -> str:
    """Format number with commas."""
    return f"{n:,}"


def _pr_link(pr: PullRequest) -> str:
    return f"[#{pr.number}]({pr.url})"


def _jira_link(ticket: JiraTicket, base_url: str) -> str:
    return f"[{ticket.key}]({ticket.url_for(base_url)})"


def _jira_key_link(key: str, base_url: str) -> str:
    return f"[{key}]({base_url}/browse/{key})"


def generate_markdown(
    prs: list[PullRequest],
    tickets: list[JiraTicket],
    stats: GitStats,
    review_count: int,
    config: UserConfig,
) -> str:
    """Generate the full year-end review markdown."""
    lines: list[str] = []

    def w(text: str = "") -> None:
        lines.append(text)

    # Build lookup: jira_key -> ticket
    ticket_map: dict[str, JiraTicket] = {t.key: t for t in tickets}

    # Build lookup: jira_key -> list of PRs
    key_to_prs: dict[str, list[PullRequest]] = defaultdict(list)
    for pr in prs:
        for key in pr.jira_keys:
            key_to_prs[key].append(pr)

    # --- Header ---
    period = f"{config.start_date.strftime('%B %Y')} - {config.end_date.strftime('%B %Y')}"
    w(f"# Contribution Review: {period}")
    w()
    w(f"**Author:** @{config.github_username}")
    w(f"**Period:** {config.start_date.isoformat()} to {config.end_date.isoformat()}")
    w(f"**Repository:** [{config.github_repo}](https://github.com/{config.github_repo})")
    w()
    w("---")
    w()

    # --- Key Stats ---
    done_count = sum(1 for t in tickets if t.status in ("Done", "Closed"))
    bug_prs = [pr for pr in prs if pr.category == "Bug Fix"]
    total_add = sum(pr.additions for pr in prs)
    total_del = sum(pr.deletions for pr in prs)

    w("## Key Stats at a Glance")
    w()
    w("| Metric | Value |")
    w("|---|---|")
    w(f"| **PRs Merged** | {_fmt(len(prs))} |")
    w(f"| **PRs Reviewed** | {_fmt(review_count)} |")
    w(f"| **Lines Added** | {_fmt(total_add)} |")
    w(f"| **Lines Deleted** | {_fmt(total_del)} |")
    w(f"| **Net Lines of Code** | +{_fmt(total_add - total_del)} |")
    w(f"| **JIRA Tickets** | {_fmt(len(tickets))} |")
    w(f"| **JIRA Completed (Done/Closed)** | {_fmt(done_count)} |")
    w(f"| **Bug Fix PRs** | {len(bug_prs)} |")
    w(f"| **Packages Touched** | {len(stats.package_file_changes)} |")
    if review_count > 0 and len(prs) > 0:
        ratio = round(review_count / len(prs), 2)
        w(f"| **Review-to-Author Ratio** | {ratio}:1 |")
    w()
    w("---")
    w()

    # --- Monthly Activity ---
    w("## Monthly Activity Breakdown")
    w()
    w("| Month | Commits | Lines Added | Lines Deleted | Net |")
    w("|---|---|---|---|---|")
    for month in sorted(stats.monthly_commits.keys()):
        commits = stats.monthly_commits.get(month, 0)
        ins = stats.monthly_additions.get(month, 0)
        dels = stats.monthly_deletions.get(month, 0)
        net = ins - dels
        sign = "+" if net >= 0 else ""
        w(f"| {month} | {commits} | {_fmt(ins)} | {_fmt(dels)} | {sign}{_fmt(net)} |")
    w()
    w("---")
    w()

    # --- Work by Category ---
    w("## Work by Category")
    w()

    categories = defaultdict(list)
    for pr in prs:
        categories[pr.category].append(pr)

    for cat_name in ["Bug Fix", "Product & Features", "Funds & Remittance",
                      "Code Quality", "Platform & Infrastructure", "Other"]:
        cat_prs = categories.get(cat_name, [])
        if not cat_prs:
            continue
        w(f"### {cat_name} ({len(cat_prs)} PRs)")
        w()
        w("| PR | Title | Merged | +Lines | -Lines |")
        w("|---|---|---|---|---|")
        for pr in cat_prs:
            w(f"| {_pr_link(pr)} | {pr.title} | {pr.merged_at} | {_fmt(pr.additions)} | {_fmt(pr.deletions)} |")
        w()

    w("---")
    w()

    # --- Package Ownership ---
    w("## Package Ownership & Impact")
    w()
    w("| Package | Files Changed |")
    w("|---|---|")
    for pkg, count in list(stats.package_file_changes.items())[:20]:
        w(f"| `{pkg}` | {count} |")
    w()
    w("---")
    w()

    # --- JIRA Overview ---
    w("## JIRA Tickets Overview")
    w()

    # By type
    type_counts = Counter(t.issue_type for t in tickets)
    w("### By Type")
    w()
    w("| Type | Count |")
    w("|---|---|")
    for t, c in type_counts.most_common():
        w(f"| {t} | {c} |")
    w()

    # By status
    status_counts = Counter(t.status for t in tickets)
    w("### By Status")
    w()
    w("| Status | Count |")
    w("|---|---|")
    for s, c in status_counts.most_common():
        w(f"| {s} | {c} |")
    w()

    # By project
    project_counts = Counter(t.project for t in tickets)
    w("### By Project")
    w()
    w("| Project | Count |")
    w("|---|---|")
    for p, c in project_counts.most_common():
        w(f"| {p} | {c} |")
    w()

    # By priority
    priority_counts = Counter(t.priority for t in tickets)
    w("### By Priority")
    w()
    w("| Priority | Count |")
    w("|---|---|")
    for p, c in sorted(priority_counts.items()):
        w(f"| {p} | {c} |")
    w()

    completion = round(done_count / len(tickets) * 100, 1) if tickets else 0
    w(f"> **Completion Rate:** {done_count} completed out of {len(tickets)} assigned = **{completion}%**")
    w()
    w("---")
    w()

    # --- All Merged PRs ---
    w("## All Merged PRs (Chronological)")
    w()
    w("| # | PR | Title | JIRA | Merged | +Lines | -Lines |")
    w("|---|---|---|---|---|---|---|")
    for i, pr in enumerate(prs, 1):
        jira_links = ", ".join(
            _jira_key_link(k, config.jira_base_url) for k in pr.jira_keys
        )
        w(f"| {i} | {_pr_link(pr)} | {pr.title} | {jira_links} | {pr.merged_at} | {_fmt(pr.additions)} | {_fmt(pr.deletions)} |")
    w()
    w("---")
    w()

    # --- All JIRA Tickets ---
    w("## All JIRA Tickets")
    w()

    # Group by project
    tickets_by_project: dict[str, list[JiraTicket]] = defaultdict(list)
    for t in tickets:
        tickets_by_project[t.project].append(t)

    for proj in sorted(tickets_by_project.keys()):
        proj_tickets = tickets_by_project[proj]
        w(f"### {proj} ({len(proj_tickets)} tickets)")
        w()
        w("| Ticket | Type | Priority | Status | Linked PRs | Summary |")
        w("|---|---|---|---|---|---|")
        for t in proj_tickets:
            linked = key_to_prs.get(t.key, [])
            pr_links = ", ".join(_pr_link(p) for p in linked) if linked else "-"
            w(f"| {_jira_link(t, config.jira_base_url)} | {t.issue_type} | {t.priority} | {t.status} | {pr_links} | {t.summary} |")
        w()

    w("---")
    w()

    # --- Code Reviews ---
    w("## Code Review Contributions")
    w()
    w(f"- **{_fmt(review_count)} PRs reviewed** across the period")
    if review_count > 0 and len(prs) > 0:
        w(f"- Review-to-author ratio: **{round(review_count / len(prs), 2)}:1**")
    w()
    w("---")
    w()
    from datetime import date as _date
    w(f"*Generated by youtrip-review on {_date.today().isoformat()}*")
    w()

    return "\n".join(lines)


def write_markdown(
    prs: list[PullRequest],
    tickets: list[JiraTicket],
    stats: GitStats,
    review_count: int,
    config: UserConfig,
) -> Path:
    """Generate and write the markdown file."""
    content = generate_markdown(prs, tickets, stats, review_count, config)
    filename = f"review-{config.start_date.isoformat()}-to-{config.end_date.isoformat()}.md"
    path = Path(config.output_dir) / filename
    path.write_text(content)
    return path
