"""CLI entry point for fetch-review-stats."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import load_config
from .csv_export import export_all
from .github_client import check_gh_auth, fetch_all_repos
from .jira_client import check_acli_auth, fetch_tickets
from .markdown_gen import write_markdown
from .models import ReviewData

BANNER = r"""
  ┌──────────────────────────────────────┐
  │   Your company stats review          │
  │   Generate your contribution report  │
  │   from GitHub & JIRA                 │
  └──────────────────────────────────────┘
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="fetch-review-stats",
        description="Generate a contribution review document from GitHub and JIRA data.",
    )
    parser.add_argument(
        "-c",
        "--config",
        default=None,
        help="Path to config TOML file (default: ./your_stats_review_config.toml)",
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
        "--skip-file-changes",
        action="store_true",
        help="Skip fetching per-PR file changes (faster, skips package breakdown)",
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
        issues.append(
            "Atlassian CLI (acli) not authenticated. Run: acli jira auth login"
        )

    if issues:
        for issue in issues:
            print(f"    ! {issue}")
        print()

    # --- Ensure output dir ---
    Path(config.output_dir).mkdir(parents=True, exist_ok=True)

    print(f"  User:       @{config.github_username}")
    print(f"  Repos:      {', '.join(config.github_repos)}")
    print(f"  Period:     {config.start_date} to {config.end_date}")
    print(f"  Output:     {config.output_dir}")

    # --- Fetch GitHub data (all repos) ---
    data = fetch_all_repos(config, skip_file_changes=args.skip_file_changes)

    # --- Fetch JIRA data ---
    if not args.skip_jira and config.jira_username:
        try:
            data.jira_tickets = fetch_tickets(config)
        except Exception as e:
            print(f"\n  Error fetching JIRA tickets: {e}")
            data.jira_tickets = []
    elif args.skip_jira:
        print("\n  Skipping JIRA (--skip-jira)")
    else:
        print("\n  Skipping JIRA (no jira.username in config)")

    # --- Export ---
    print()

    if not args.markdown_only:
        print("  Exporting CSV files...")
        csv_paths = export_all(
            data.prs_authored,
            data.jira_tickets,
            data.git_stats,
            data.prs_reviewed_count,
            data.per_repo_stats,
            config,
        )
        for p in csv_paths:
            print(f"    -> {p}")

    if not args.csv_only:
        print("\n  Generating markdown report...")
        md_path = write_markdown(data, config)
        print(f"    -> {md_path}")

    # --- Summary ---
    print(f"""
  ┌─ Summary ──────────────────────────────
  │ Repositories:   {len(config.github_repos)}
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
