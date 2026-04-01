"""Generate the year-end review markdown document."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date as _date
from pathlib import Path

from .models import JIRA_CATEGORY_MAP, JIRA_DONE_STATUSES, JiraTicket, PullRequest, ReviewData, UserConfig


def _fmt(n: int) -> str:
    """Format number with commas."""
    return f"{n:,}"


def _pr_link(pr: PullRequest) -> str:
    return f"[#{pr.number}]({pr.url})"


def _jira_link(ticket: JiraTicket, base_url: str) -> str:
    return f"[{ticket.key}]({ticket.url_for(base_url)})"


def _jira_key_link(key: str, base_url: str) -> str:
    return f"[{key}]({base_url}/browse/{key})"


def generate_markdown(data: ReviewData, config: UserConfig) -> str:
    """Generate the full review markdown."""
    prs = data.prs_authored
    tickets = data.jira_tickets
    stats = data.git_stats
    review_count = data.prs_reviewed_count
    base_url = config.jira_base_url

    lines: list[str] = []

    def w(text: str = "") -> None:
        lines.append(text)

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
    w(f"**Repositories:** {len(config.github_repos)}")
    w()
    for repo in config.github_repos:
        w(f"- [{repo}](https://github.com/{repo})")
    w()
    w("---")
    w()

    # --- Per-Repo Breakdown ---
    if data.per_repo_stats:
        w("## Per-Repo Breakdown")
        w()
        w("| Repository | PRs Merged | PRs Reviewed | Commits | Lines Added | Lines Deleted | Net |")
        w("|---|---|---|---|---|---|---|")
        for rs in data.per_repo_stats:
            net = rs.additions - rs.deletions
            sign = "+" if net >= 0 else ""
            w(f"| {rs.repo} | {rs.prs_merged} | {rs.prs_reviewed} | {rs.commits} | {_fmt(rs.additions)} | {_fmt(rs.deletions)} | {sign}{_fmt(net)} |")
        w()
        w("---")
        w()

    # --- Key Stats ---
    done_count = sum(1 for t in tickets if t.status in JIRA_DONE_STATUSES)
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
    if stats.total_commits:
        w(f"| **Commits** | {_fmt(stats.total_commits)} |")
    w(f"| **JIRA Tickets** | {_fmt(len(tickets))} |")
    w(f"| **JIRA Completed (Done/Closed)** | {_fmt(done_count)} |")
    w(f"| **Bug Fix PRs** | {len(bug_prs)} |")
    if stats.package_file_changes:
        w(f"| **Packages Touched** | {len(stats.package_file_changes)} |")
    review_ratio = round(review_count / len(prs), 2) if review_count > 0 and prs else None
    if review_ratio:
        w(f"| **Review-to-Author Ratio** | {review_ratio}:1 |")
    w()
    w("---")
    w()

    # --- Monthly Activity ---
    if stats.monthly_commits or stats.monthly_additions:
        all_months = sorted(set(stats.monthly_commits.keys()) | set(stats.monthly_additions.keys()))
        w("## Monthly Activity Breakdown")
        w()
        w("| Month | Commits | Lines Added | Lines Deleted | Net |")
        w("|---|---|---|---|---|")
        for month in all_months:
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

    category_order = list(dict.fromkeys(JIRA_CATEGORY_MAP.values())) + ["Other"]
    for cat_name in category_order:
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
    if stats.package_file_changes:
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
    if tickets:
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

        completion = round(done_count / len(tickets) * 100, 1)
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
            _jira_key_link(k, base_url) for k in pr.jira_keys
        ) if base_url else ", ".join(pr.jira_keys)
        w(f"| {i} | {_pr_link(pr)} | {pr.title} | {jira_links} | {pr.merged_at} | {_fmt(pr.additions)} | {_fmt(pr.deletions)} |")
    w()
    w("---")
    w()

    # --- All JIRA Tickets ---
    if tickets:
        w("## All JIRA Tickets")
        w()

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
                ticket_link = _jira_link(t, base_url) if base_url else t.key
                w(f"| {ticket_link} | {t.issue_type} | {t.priority} | {t.status} | {pr_links} | {t.summary} |")
            w()

        w("---")
        w()

    # --- Code Reviews ---
    w("## Code Review Contributions")
    w()
    w(f"- **{_fmt(review_count)} PRs reviewed** across the period")
    if review_ratio:
        w(f"- Review-to-author ratio: **{review_ratio}:1**")
    w()
    w("---")
    w()
    w(f"*Generated by fetch-review-stats on {_date.today().isoformat()}*")
    w()

    return "\n".join(lines)


def write_markdown(data: ReviewData, config: UserConfig) -> Path:
    """Generate and write the markdown file."""
    content = generate_markdown(data, config)
    filename = f"review-{config.start_date.isoformat()}-to-{config.end_date.isoformat()}.md"
    path = Path(config.output_dir) / filename
    path.write_text(content)
    return path
