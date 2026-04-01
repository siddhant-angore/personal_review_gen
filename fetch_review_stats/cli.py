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
from .ui import (
    PURPLE, GREEN, RED, RESET, BOLD, DIM,
    Spinner, bold, config_line, dim, error, filepath,
    purple, status, success, summary_line, warn,
)


def _banner() -> str:
    b = f"{PURPLE}│{RESET}"
    return f"""
  {PURPLE}┌──────────────────────────────────────┐{RESET}
  {b}   {BOLD}Fetch Review Stats{RESET}                 {b}
  {b}   {DIM}Generate your contribution report{RESET}   {b}
  {b}   {DIM}from GitHub & JIRA{RESET}                  {b}
  {PURPLE}└──────────────────────────────────────┘{RESET}
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

    try:
        return _run(args)
    except KeyboardInterrupt:
        print(f"\n\n{error('Interrupted.')}")
        return 130


def _run(args: argparse.Namespace) -> int:
    print(_banner())

    # --- Load config ---
    config = load_config(args.config)

    # --- Prerequisites ---
    print(dim("  Checking prerequisites..."))
    gh_ok = check_gh_auth()
    if gh_ok:
        print(success("GitHub CLI authenticated"))
    else:
        print(error("GitHub CLI (gh) not authenticated. Run: gh auth login"))

    if not args.skip_jira and config.jira_username:
        if check_acli_auth():
            print(success("Atlassian CLI authenticated"))
        else:
            print(warn("Atlassian CLI (acli) not authenticated. Run: acli jira auth login"))

    # --- Ensure output dir ---
    Path(config.output_dir).mkdir(parents=True, exist_ok=True)

    # --- Config echo ---
    print()
    print(config_line("User", f"@{config.github_username}"))
    print(config_line("Repos", ", ".join(config.github_repos)))
    print(config_line("Period", f"{config.start_date} {purple('→')} {config.end_date}"))
    print(config_line("Output", config.output_dir))

    # --- Fetch GitHub data (all repos) ---
    data = fetch_all_repos(config, skip_file_changes=args.skip_file_changes)

    # --- Fetch JIRA data ---
    if not args.skip_jira and config.jira_username:
        try:
            with Spinner("Fetching JIRA tickets..."):
                data.jira_tickets = fetch_tickets(config)
        except Exception as e:
            print(error(f"JIRA tickets: {e}"))
            data.jira_tickets = []
    elif args.skip_jira:
        print(f"\n{dim('  Skipping JIRA (--skip-jira)')}")
    else:
        print(f"\n{dim('  Skipping JIRA (no jira.username in config)')}")

    # --- Export ---
    print()

    if not args.markdown_only:
        print(dim("  Exporting CSV files..."))
        csv_paths = export_all(
            data.prs_authored,
            data.jira_tickets,
            data.git_stats,
            data.prs_reviewed_count,
            data.per_repo_stats,
            config,
        )
        for p in csv_paths:
            print(filepath(Path(p).name))

    if not args.csv_only:
        print(dim("\n  Generating markdown report..."))
        md_path = write_markdown(data, config)
        print(filepath(Path(md_path).name))

    # --- Summary ---
    total_add = data.git_stats.total_additions
    total_del = data.git_stats.total_deletions

    print(f"""
  {PURPLE}┌─ {BOLD}Summary{RESET} {PURPLE}──────────────────────────────{RESET}""")
    print(summary_line("Repositories", len(config.github_repos)))
    print(summary_line("PRs Merged", len(data.prs_authored)))
    print(summary_line("PRs Reviewed", data.prs_reviewed_count))
    print(summary_line("JIRA Tickets", len(data.jira_tickets)))
    print(summary_line("Commits", data.git_stats.total_commits))
    print(summary_line("Lines Added", total_add, GREEN))
    print(summary_line("Lines Deleted", total_del, RED))
    print(f"  {PURPLE}└────────────────────────────────────────{RESET}")

    print(f"\n{success('Done!')} Output in: {purple(config.output_dir)}\n")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n\n{error('Interrupted.')}")
        sys.exit(130)
