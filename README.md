> **Notice:** This repository is fully AI-generated.

# GitHub Account & Repository Inspector for LLM Wikis

A Python tool designed to scrape, analyze, and catalog your GitHub account and repositories into a structured LLM Wiki markdown knowledge base.

It analyzes your repositories from multiple angles (frameworks, code scale, timeline, commits, collaborators, community health) and generates:
1. One detailed Markdown dossier (`.md`) for each repository in `reports/repos/<repo-name>.md` with structured YAML frontmatter, metric tables, and LLM context summaries.
2. One Master Index file (`INDEX.md`) with interactive catalog tables, tech stack groupings, activity statuses, and LLM ingestion guides.

---

## Quick Start

### 1. Zero External Dependencies
This tool uses Python's standard library (`urllib`, `json`, `base64`, `re`, `datetime`). You can run it immediately with Python 3.8+ without installing external packages.

### 2. Configure Credentials (`.env`)
Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Open `.env` and fill in your GitHub details:

```ini
GITHUB_TOKEN=ghp_yourPersonalAccessTokenHere
GITHUB_USERNAME=your_username_here
OUTPUT_DIR=./reports
INCLUDE_FORKS=true
REPO_VISIBILITY=all
```

---

## Running the Tool

### Basic Run
Run directly with your `.env` settings:

```bash
python3 main.py
```

### CLI Overrides & Options
```bash
# Specify username or GitHub URL directly
python3 main.py -u https://github.com/torvalds

# Pass token directly via CLI
python3 main.py -u your_username -t ghp_yourTokenHere

# Output to a custom wiki folder
python3 main.py -o ./my_github_wiki

# Inspect only a single repository
python3 main.py --repo my-special-project

# Filter out forked repositories
python3 main.py --no-forks

# Filter repository visibility (all / public / private)
python3 main.py --visibility public
```

---

## What Perspectives Are Analyzed?

| Perspective | Details Extracted |
| :--- | :--- |
| **Repository Identity** | Name, description, topics/tags, homepage/demo URL, license (SPDX), visibility (Public/Private), default branch. |
| **Codebase Scale** | Repository size (KB/MB) and scale categorization (*Micro < 1MB*, *Small 1-10MB*, *Medium 10-50MB*, *Large 50-200MB*, *Enterprise > 200MB*). |
| **Language Distribution** | Byte-level volume breakdown, exact percentage calculation, and visual progress distribution bars. |
| **Frameworks & Tech Stack** | Scans manifest files (`package.json`, `requirements.txt`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `Dockerfile`, etc.) to detect frameworks across Web, AI/ML, Databases/ORMs, DevOps, and CI/CD. |
| **Development Timeline** | First commit date, latest commit date, development lifespan (e.g. `2 years, 3 months` or `18 days`), and days since last commit. |
| **Activity & Velocity Status** | Categorized into `Active Development` (< 60d), `Maintained` (< 180d), `Dormant / Stale` (< 365d), `Inactive / Legacy` (> 1y), or `Archived`. |
| **Commit Volume** | Total commit count calculated efficiently via O(1) header pagination. |
| **Collaboration Pattern** | Single developer vs. Collaborative team, list of contributors, commit share percentage of lead contributor, contributor profile links. |
| **Releases & Branches** | Active branches count, release tag history, latest release details and published dates. |
| **Community Health** | Stars count, forks, watchers, open issue count. |
| **Documentation & Summary** | Top-level file directory preview and extracted README overview. |
| **LLM Context Synthesis** | High semantic-density paragraph generated for AI agents to grasp the purpose, architecture, and state. |

---

## Generated LLM Wiki Structure

```
reports/
├── INDEX.md               # Master Wiki Catalog & Portfolio Dashboard
└── repos/                 # Individual repository dossiers
    ├── repo-alpha.md
    ├── repo-beta.md
    └── ...
```

---

## Running Tests

```bash
python3 tests/test_inspector.py
```
