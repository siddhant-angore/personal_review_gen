"""CLI entry point for YouTrip Review."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import load_config
from .csv_export import export_all
from .git_client import fetch_git_stats
from .github_client import check_gh_auth, fetch_merged_prs, fetch_review_count
from .jira_client import check_acli_auth, fetch_tickets
from .markdown_gen import write_markdown
from .models import ReviewData

BANNER = r"""
  ┌──────────────────────────────────────┐
  │   YouTrip Review                     │
  │   Generate your contribution report  │
  │   from GitHub, JIRA & git data.      │
  └──────────────────────────────────────┘
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="youtrip-review",
        description="Generate a contribution review document from GitHub and JIRA data.",
    )
    parser.add_argument(
        "-c", "--config",
        default=None,
        help="Path to config TOML file (default: ./youtrip_review_config.toml)",
    )
    parser.add_argument(
        "--csv-only",
        action="store_true",
        help="Only export CSV data, skip markdown generation",
    )
    parser.add_argument(
        "--markdown-only",
        action="store_true",
        help="Only generate markdown (assumes CSVs already exist)",
    )
    parser.add_argument(
        "--skip-jira",
        action="store_true",
        help="Skip JIRA data fetching (useful if ACLI is not configured)",
    )
    parser.add_argument(
        "--skip-git-stats",
        action="store_true",
        help="Skip local git log stats (useful when not in a git repo)",
    )
    args = parser.parse_args(argv)

    print(BANNER)

    # --- Load config ---
    config = load_config(args.config)

    # --- Prerequisites ---
    print("  Checking prerequisites...")
    issues = []
    if not check_gh_auth():
        issues.append("GitHub CLI (gh) not authenticated. Run: gh auth login")
    if not args.skip_jira and config.jira_username and not check_acli_auth():
        issues.append("Atlassian CLI (acli) not authenticated. Run: acli jira auth login")

    if issues:
        for issue in issues:
            print(f"    ! {issue}")
        print()

    # --- Ensure output dir ---
    Path(config.output_dir).mkdir(parents=True, exist_ok=True)

    print(f"  User:       @{config.github_username}")
    print(f"  Repo:       {config.github_repo}")
    print(f"  Period:     {config.start_date} to {config.end_date}")
    print(f"  Output:     {config.output_dir}")
    print()

    # --- Fetch Data ---
    data = ReviewData()

    try:
        data.prs_authored = fetch_merged_prs(config)
    except Exception as e:
        print(f"\n  Error fetching PRs: {e}")
        data.prs_authored = []

    try:
        data.prs_reviewed_count = fetch_review_count(config)
    except Exception as e:
        print(f"\n  Error fetching review count: {e}")
        data.prs_reviewed_count = 0

    if not args.skip_jira and config.jira_username:
        try:
            data.jira_tickets = fetch_tickets(config)
        except Exception as e:
            print(f"\n  Error fetching JIRA tickets: {e}")
            data.jira_tickets = []
    elif args.skip_jira:
        print("  Skipping JIRA (--skip-jira)")
    else:
        print("  Skipping JIRA (no jira.username in config)")

    if not args.skip_git_stats:
        try:
            data.git_stats = fetch_git_stats(config)
        except Exception as e:
            print(f"\n  Error fetching git stats: {e}")
    else:
        print("  Skipping git stats (--skip-git-stats)")

    # --- Export ---
    print()

    if not args.markdown_only:
        print("  Exporting CSV files...")
        csv_paths = export_all(
            data.prs_authored,
            data.jira_tickets,
            data.git_stats,
            data.prs_reviewed_count,
            config,
        )
        for p in csv_paths:
            print(f"    -> {p}")

    if not args.csv_only:
        print("\n  Generating markdown report...")
        md_path = write_markdown(
            data.prs_authored,
            data.jira_tickets,
            data.git_stats,
            data.prs_reviewed_count,
            config,
        )
        print(f"    -> {md_path}")

    # --- Summary ---
    print(f"""
  ┌─ Summary ──────────────────────────────
  │ PRs Merged:     {len(data.prs_authored)}
  │ PRs Reviewed:   {data.prs_reviewed_count}
  │ JIRA Tickets:   {len(data.jira_tickets)}
  │ Git Commits:    {data.git_stats.total_commits}
  │ Lines Added:    {data.git_stats.total_additions:,}
  │ Lines Deleted:  {data.git_stats.total_deletions:,}
  └────────────────────────────────────────

  Done! Output in: {config.output_dir}
""")

    return 0


if __name__ == "__main__":
    sys.exit(main())
