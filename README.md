# YouTrip Review

CLI tool that generates developer contribution reports by aggregating data from GitHub, JIRA, and local git history. Produces markdown reports and CSV exports covering PRs, code reviews, JIRA tickets, and commit statistics.

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

Copy the sample config and fill in your details:

```bash
cp youtrip_review/config.toml youtrip_review_config.toml
```

Edit `youtrip_review_config.toml`:

```toml
[github]
username = "your-github-username"
repo     = "owner/repo"

[git]
author_name = "Your Name"          # partial match for git log --author
repo_path   = "/path/to/local/repo"

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
# Full report (CSV + markdown)
uv run youtrip-review

# Use a custom config file
uv run youtrip-review -c path/to/config.toml

# CSV export only
uv run youtrip-review --csv-only

# Markdown only (assumes CSVs already exist)
uv run youtrip-review --markdown-only

# Skip JIRA data
uv run youtrip-review --skip-jira

# Skip local git stats
uv run youtrip-review --skip-git-stats
```

## Output

Reports are written to the configured output directory (default: `./review_output/`):

| File | Contents |
|------|----------|
| `review_*.md` | Full markdown report with stats, charts, and categorized contributions |
| `prs_*.csv` | Pull request details (title, additions, deletions, merge date) |
| `jira_tickets_*.csv` | JIRA ticket information (type, status, priority) |
| `git_stats_*.csv` | Monthly git commit and line change statistics |
| `summary_*.csv` | Executive summary metrics |

## Project Structure

```
youtrip_review/
  cli.py           # CLI entry point and orchestration
  config.py        # TOML configuration loading
  models.py        # Data models (PullRequest, JiraTicket, GitStats, etc.)
  github_client.py # GitHub API interactions via gh CLI
  jira_client.py   # JIRA interactions via acli CLI
  git_client.py    # Local git repository statistics
  markdown_gen.py  # Markdown report generation
  csv_export.py    # CSV file exporting
  config.toml      # Sample configuration template
```
