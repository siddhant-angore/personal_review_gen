# Fetch Review Stats

CLI tool that generates developer contribution reports by aggregating data from GitHub and JIRA. Supports multiple repositories in a single run. Produces a consolidated markdown report and CSV exports covering PRs, code reviews, JIRA tickets, and commit statistics.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [GitHub CLI](https://cli.github.com/) (`gh`) - authenticated via `gh auth login`
- [Atlassian CLI](https://bobswift.atlassian.net/wiki/spaces/ACLI/overview) (`acli`) - optional, for JIRA integration
- Python 3.11+

## Setup

```bash
git clone <repo-url> && cd personal_review_gen
uv sync
```

## Configuration

On first run, a config file is auto-created with placeholder values:

```bash
uv run fetch-review-stats
# Creates your_stats_review_config.toml — fill in your details and re-run
```

Or copy the sample config manually:

```bash
cp fetch_review_stats/config.toml your_stats_review_config.toml
```

Edit `your_stats_review_config.toml`:

```toml
[github]
username = "your-github-username"
repos    = ["owner/repo1", "owner/repo2"]    # all repos to include

[jira]
username         = "you@company.com"
base_url         = "https://your-org.atlassian.net"
exclude_projects = ["TEST"]

[period]
start = "2025-04-01"
end   = "2026-03-31"

[output]
dir = "./review_output"
```

## Usage

```bash
# Full report (CSV + markdown) across all configured repos
uv run fetch-review-stats

# Use a custom config file
uv run fetch-review-stats -c path/to/config.toml

# CSV export only
uv run fetch-review-stats --csv-only

# Markdown only (assumes CSVs already exist)
uv run fetch-review-stats --markdown-only

# Skip JIRA data
uv run fetch-review-stats --skip-jira

# Skip per-PR file change analysis (faster)
uv run fetch-review-stats --skip-file-changes
```

## Output

Reports are written to the configured output directory (default: `./review_output/`):

| File | Contents |
|------|----------|
| `review_*.md` | Full markdown report with per-repo breakdown, stats, and categorized contributions |
| `prs_*.csv` | Pull request details with repo, title, additions, deletions, merge date |
| `jira_tickets_*.csv` | JIRA ticket information (type, status, priority) |
| `git_stats_*.csv` | Monthly commit and line change statistics |
| `summary_*.csv` | Per-repo breakdown and totals |

## How It Works

1. Fetches merged PRs and review counts from GitHub API for each configured repo
2. Fetches commit counts per repo via GitHub commits API
3. Optionally fetches per-PR file changes for package-level analysis
4. Fetches JIRA tickets (single query, not per-repo)
5. Deduplicates PRs (by URL) and JIRA tickets (by key) across repos
6. Generates consolidated CSV exports and markdown report

No local repository clones are needed - all data is fetched via the GitHub and JIRA APIs.

## Project Structure

```
fetch_review_stats/
  cli.py           # CLI entry point and orchestration
  config.py        # TOML configuration loading with auto-create
  models.py        # Data models (PullRequest, JiraTicket, GitStats, etc.)
  github_client.py # GitHub API: PRs, reviews, commits, file changes
  jira_client.py   # JIRA interactions via acli CLI
  markdown_gen.py  # Markdown report generation
  csv_export.py    # CSV file exporting
  config.toml      # Sample configuration template
```
