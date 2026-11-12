import os
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any

from .analyzer import RepoReport

def sanitize_filename(name: str) -> str:
    """Make repo name safe for filenames across OSes."""
    return re.sub(r'[\\/*?:"<>|]', '_', name)

def make_progress_bar(percentage: float, width: int = 15) -> str:
    """Generate visual markdown progress bar e.g. [██████░░░░░░]"""
    filled = int(round((percentage / 100.0) * width))
    empty = width - filled
    return f"`{'█' * filled}{'░' * empty}`"

class MarkdownGenerator:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.repos_dir = self.output_dir / "repos"

    def generate_all(self, user_profile: Dict[str, Any], reports: List[RepoReport]):
        """Generate individual repo markdown files and the master index."""
        self.repos_dir.mkdir(parents=True, exist_ok=True)

        # Generate individual files
        for report in reports:
            self.generate_repo_page(report)

        # Generate master index
        self.generate_index_page(user_profile, reports)

    def generate_repo_page(self, repo: RepoReport) -> Path:
        filename = f"{sanitize_filename(repo.name)}.md"
        filepath = self.repos_dir / filename

        langs_list = list(repo.language_breakdown.keys())
        topics_str = ", ".join(f'"{t}"' for t in repo.topics)
        topics_yaml = f"[{topics_str}]" if repo.topics else "[]"
        langs_str = ", ".join(f'"{l}"' for l in langs_list)
        langs_yaml = f"[{langs_str}]" if langs_list else "[]"
        fws_str = ", ".join(f'"{f}"' for f in repo.all_frameworks)
        fws_yaml = f"[{fws_str}]" if repo.all_frameworks else "[]"

        content = []
        # 1. YAML Frontmatter for LLM indexing & RAG metadata
        content.append("---")
        content.append(f'title: "{repo.name}"')
        content.append(f'full_name: "{repo.full_name}"')
        content.append(f'owner: "{repo.owner}"')
        content.append(f'primary_language: "{repo.primary_language}"')
        content.append(f"languages: {langs_yaml}")
        content.append(f"frameworks: {fws_yaml}")
        content.append(f'scale: "{repo.scale_label}"')
        content.append(f"code_bytes: {repo.code_bytes}")
        content.append(f"disk_size_kb: {repo.size_kb}")
        content.append(f'asset_note: "{repo.asset_breakdown_note}"')
        content.append(f"commits: {repo.commit_count}")
        content.append(f"contributors: {repo.contributors_count}")
        content.append(f"stars: {repo.stars_count}")
        content.append(f"forks: {repo.forks_count}")
        content.append(f"open_issues: {repo.open_issues_count}")
        content.append(f'status: "{repo.activity_status}"')
        content.append(f'collaboration: "{repo.collaboration_style}"')
        content.append(f'created_at: "{repo.created_at or ""}"')
        content.append(f'last_pushed_at: "{repo.pushed_at or ""}"')
        content.append(f'development_length: "{repo.development_length}"')
        content.append(f'license: "{repo.license_name}"')
        content.append(f'visibility: "{repo.visibility}"')
        content.append(f"topics: {topics_yaml}")
        content.append(f'html_url: "{repo.html_url}"')
        content.append(f'classification: "{repo.repo_classification}"')
        content.append(f'is_stub_or_empty: {str(repo.is_stub_or_empty).lower()}')
        content.append(f'stub_reason: "{repo.stub_reason or "None"}"')
        content.append(f"lines_added: {repo.lines_added}")
        content.append(f"lines_deleted: {repo.lines_deleted}")
        content.append(f"net_lines: {repo.net_lines}")
        content.append(f"total_churn: {repo.total_churn}")
        content.append(f"avg_churn_per_commit: {repo.avg_churn_per_commit}")
        content.append(f'change_intensity: "{repo.change_intensity}"')
        content.append("wiki_type: repository-spec")
        content.append("---\n")

        # 2. Navigation & Header
        content.append("[← Back to Master Repository Index](../INDEX.md)\n")
        content.append(f"# {repo.name}\n")
        
        # Badges row
        badges = [
            f"**Type:** `{repo.repo_classification}`",
            f"**Visibility:** `{repo.visibility}`",
            f"**Status:** `{repo.activity_status}`",
            f"**Language:** `{repo.primary_language}`",
            f"**Commits:** `{repo.commit_count}`",
            f"**Churn:** `+{repo.lines_added:,} / -{repo.lines_deleted:,}`",
            f"**License:** `{repo.license_name}`"
        ]
        content.append(" | ".join(badges) + "\n")
        content.append(f"> {repo.description}\n")
        if repo.is_stub_or_empty:
            content.append(f"> **Classification Notice:** Identified as `{repo.repo_classification}` ({repo.stub_reason})\n")
        if repo.homepage:
            content.append(f"- **Live Demo / Homepage:** [{repo.homepage}]({repo.homepage})")
        content.append(f"- **GitHub Repository:** [{repo.html_url}]({repo.html_url})\n")

        # 3. LLM Quick Context (Dense AI-digestible summary)
        content.append("## 1. LLM Context Summary")
        content.append(repo.llm_summary + "\n")

        # 4. Specifications & Codebase Metrics Table
        content.append("## 2. Key Specifications & Metrics\n")
        content.append("| Metric | Value | Detail |")
        content.append("| :--- | :--- | :--- |")
        content.append(f"| **Repository Classification** | `{repo.repo_classification}` | {repo.stub_reason or 'Full substantive project'} |")
        content.append(f"| **Source Code Scale** | `{repo.scale_label}` | {repo.asset_breakdown_note} |")
        content.append(f"| **Total Disk Size** | `{repo.size_kb:,} KB` | Includes code, assets, images, and history |")
        content.append(f"| **Primary Language** | `{repo.primary_language}` | Dominant language by byte volume |")
        content.append(f"| **Total Commits** | `{repo.commit_count}` commits | On default branch `{repo.default_branch}` |")
        content.append(f"| **Lifetime Code Churn** | `+{repo.lines_added:,} / -{repo.lines_deleted:,}` lines | All-time cumulative line additions and deletions |")
        content.append(f"| **Change Pattern** | `{repo.change_intensity}` | Avg ~{repo.avg_churn_per_commit} lines/commit |")
        content.append(f"| **Development Lifespan** | `{repo.development_length}` | From inception to latest push |")
        content.append(f"| **Created Date** | `{repo.created_at[:10] if repo.created_at else 'Unknown'}` | Initial repo creation |")
        content.append(f"| **Last Pushed Date** | `{repo.pushed_at[:10] if repo.pushed_at else 'Unknown'}` | {repo.days_since_last_push} days ago |")
        content.append(f"| **Default Branch** | `{repo.default_branch}` | Total active branches: {repo.branch_count} |")
        content.append(f"| **Releases / Tags** | `{repo.releases_count}` releases | {'Latest: ' + repo.latest_release.tag_name if repo.latest_release else 'None'} |")
        content.append(f"| **Community Engagement** | `{repo.stars_count}` stars / `{repo.forks_count}` forks | Watchers: {repo.watchers_count}, Open Issues: {repo.open_issues_count} |")
        content.append(f"| **Collaboration Model** | `{repo.collaboration_style}` | {repo.contributors_count} contributor(s) |")
        content.append("")

        # 5. Technology Stack & Frameworks
        content.append("## 3. Technology Stack & Frameworks\n")
        if repo.frameworks_by_category:
            content.append("| Category | Detected Technologies & Frameworks |")
            content.append("| :--- | :--- |")
            for cat, tools in repo.frameworks_by_category.items():
                tools_badges = " ".join([f"`{t}`" for t in tools])
                content.append(f"| **{cat}** | {tools_badges} |")
            content.append("")
        else:
            content.append("*No major recognized frameworks detected in top-level manifests.*\n")

        # Language Byte Breakdown
        if repo.language_breakdown:
            content.append("### Language Distribution\n")
            content.append("| Language | Percentage | Volume | Distribution |")
            content.append("| :--- | :--- | :--- | :--- |")
            for lang, data in repo.language_breakdown.items():
                pct = data["percentage"]
                b_count = data["bytes"]
                bar = make_progress_bar(pct)
                content.append(f"| **{lang}** | `{pct}%` | {b_count:,} bytes | {bar} |")
            content.append("")

        # 6. Collaboration & Contributors
        content.append("## 4. Collaboration & Contributors\n")
        content.append(f"- **Collaboration Pattern:** {repo.collaboration_style}")
        content.append(f"- **Lead Contributor Share:** {repo.top_contributor_share}%\n")
        if repo.contributors:
            content.append("| Contributor | Commits | Share | Profile |")
            content.append("| :--- | :--- | :--- | :--- |")
            for c in repo.contributors[:10]:
                content.append(f"| **[@{c.login}]({c.html_url})** | {c.contributions} | `{c.percentage}%` | [{c.login}]({c.html_url}) |")
            if len(repo.contributors) > 10:
                content.append(f"| *... and {len(repo.contributors) - 10} more contributors* | | | |")
            content.append("")

        # 7. Releases & Branches
        content.append("## 5. Releases & Repository Structure\n")
        if repo.releases:
            content.append("### Releases History")
            for rel in repo.releases:
                pub = rel.published_at[:10] if rel.published_at else "Unknown date"
                content.append(f"- **[{rel.tag_name}]({rel.html_url})** - *{rel.name}* (Published: {pub})")
            content.append("")

        if repo.root_files:
            content.append("### Top-Level Files & Structure")
            files_preview = ", ".join([f"`{f}`" for f in repo.root_files[:25]])
            content.append(f"Root files ({len(repo.root_files)} detected): {files_preview}\n")

        # 8. README Excerpt
        content.append("## 6. README Summary & Excerpt\n")
        content.append(repo.readme_excerpt + "\n")

        # 9. LLM Prompt Suggestions
        content.append("## 7. LLM Query & Reasoning Guide")
        content.append("When querying an LLM about this repository:")
        content.append(f"- **Architecture Queries:** Refer to detected frameworks ({', '.join(repo.all_frameworks) if repo.all_frameworks else 'standard ' + repo.primary_language}).")
        content.append(f"- **Maintenance Queries:** The repository is currently **{repo.activity_status}** with development spanning {repo.development_length}.")
        content.append(f"- **Scope Queries:** Classified as **{repo.scale_label}** with {repo.commit_count} commits.")
        content.append("\n---\n*Generated by GitHub Wiki Inspector.* [Return to Index](../INDEX.md)")

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(content) + "\n")

        return filepath

    def generate_index_page(self, user_profile: Dict[str, Any], reports: List[RepoReport]) -> Path:
        filepath = self.output_dir / "INDEX.md"

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        user_login = user_profile.get("login") or (reports[0].owner if reports else "User")
        user_name = user_profile.get("name") or user_login
        user_bio = user_profile.get("bio") or "No bio available."
        user_html = user_profile.get("html_url") or f"https://github.com/{user_login}"

        total_repos = len(reports)
        total_commits = sum(r.commit_count for r in reports)
        total_stars = sum(r.stars_count for r in reports)
        total_forks = sum(r.forks_count for r in reports)
        total_lines_added = sum(r.lines_added for r in reports)
        total_lines_deleted = sum(r.lines_deleted for r in reports)
        total_net_lines = total_lines_added - total_lines_deleted
        substantive_repos = [r for r in reports if not r.is_stub_or_empty]
        stub_repos = [r for r in reports if r.is_stub_or_empty]
        public_repos = [r for r in reports if r.visibility.lower() == "public"]
        private_repos = [r for r in reports if r.visibility.lower() == "private"]
        
        # Language aggregates
        lang_counter: Dict[str, int] = {}
        for r in reports:
            if r.primary_language and r.primary_language != "Unknown":
                lang_counter[r.primary_language] = lang_counter.get(r.primary_language, 0) + 1
        sorted_langs = sorted(lang_counter.items(), key=lambda x: x[1], reverse=True)

        content = []
        # Frontmatter
        content.append("---")
        content.append(f'title: "GitHub Portfolio & Repository Wiki Index"')
        content.append(f'owner: "{user_login}"')
        content.append(f"total_repositories: {total_repos}")
        content.append(f"public_repositories: {len(public_repos)}")
        content.append(f"private_repositories: {len(private_repos)}")
        content.append(f"substantive_projects: {len(substantive_repos)}")
        content.append(f"stub_repositories: {len(stub_repos)}")
        content.append(f"total_commits: {total_commits}")
        content.append(f"total_lines_added: {total_lines_added}")
        content.append(f"total_lines_deleted: {total_lines_deleted}")
        content.append(f"net_lines: {total_net_lines}")
        content.append(f"total_stars: {total_stars}")
        content.append(f"total_forks: {total_forks}")
        content.append(f'generated_at: "{now_str}"')
        content.append("wiki_type: master-index")
        content.append("---\n")

        # Header
        content.append(f"# GitHub Repository Wiki: [@{user_login}]({user_html})\n")
        content.append(f"> **Developer Profile:** {user_name} — *{user_bio}*\n")
        content.append(f"*Generated on {now_str}*\n")

        # Portfolio Dashboard
        content.append("## Portfolio Summary\n")
        content.append("| Metric | Count | Description |")
        content.append("| :--- | :--- | :--- |")
        content.append(f"| **Total Repositories** | `{total_repos}` | Public and private repositories analyzed |")
        content.append(f"| **Visibility Distribution** | `{len(public_repos)} public` / `{len(private_repos)} private` | Access permissions |")
        content.append(f"| **Project Breakdown** | `{len(substantive_repos)} substantive` / `{len(stub_repos)} minimal stubs` | Active projects vs trivial stubs |")
        content.append(f"| **Total Commits Analyzed** | `{total_commits:,}` | Cumulative commit activity |")
        content.append(f"| **Total Code Churn** | `+{total_lines_added:,} / -{total_lines_deleted:,}` lines | Net: {total_net_lines:,} lines modified |")
        content.append(f"| **Total Stars Earned** | `{total_stars:,}` | Stars across repositories |")
        content.append(f"| **Total Forks** | `{total_forks:,}` | Forks across repositories |")
        primary_lang_str = ", ".join([f"**{l}** ({c})" for l, c in sorted_langs[:5]]) if sorted_langs else "None"
        content.append(f"| **Top Languages** | {primary_lang_str} | Primary languages across portfolio |")
        content.append("")

        # Master Catalog Tables Grouped by Public / Private Status
        content.append("## Repository Catalog by Visibility\n")

        def render_repo_table(repo_subset: List[RepoReport]) -> List[str]:
            lines = [
                "| Repository | Classification | Language | Frameworks | Code Scale | Commits | Lifetime Churn (+ / -) | Status |",
                "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
            ]
            for r in sorted(repo_subset, key=lambda x: x.days_since_last_push):
                safe_name = sanitize_filename(r.name)
                repo_link = f"[{r.name}](repos/{safe_name}.md)"
                fw_str = ", ".join(r.all_frameworks[:2]) + (f" *+{len(r.all_frameworks)-2}*" if len(r.all_frameworks) > 2 else "")
                fw_str = fw_str if fw_str else "—"
                churn_display = f"+{r.lines_added:,} / -{r.lines_deleted:,}" if r.total_churn > 0 else "0 lines"
                scale_short = r.scale_label.split(" (")[0]
                lines.append(
                    f"| **{repo_link}** | `{r.repo_classification}` | `{r.primary_language}` | {fw_str} | {scale_short} | {r.commit_count:,} | `{churn_display}` | `{r.activity_status}` |"
                )
            return lines

        content.append(f"### Public Repositories ({len(public_repos)})\n")
        if public_repos:
            content.extend(render_repo_table(public_repos))
        else:
            content.append("*No public repositories found.*")
        content.append("")

        content.append(f"### Private Repositories ({len(private_repos)})\n")
        if private_repos:
            content.extend(render_repo_table(private_repos))
        else:
            content.append("*No private repositories found or analyzed.*")
        content.append("")

        # Separate Section for Substantive Projects
        if substantive_repos:
            content.append(f"## Substantive Codebases ({len(substantive_repos)} projects)\n")
            content.append("Repositories containing complete application code, modules, or services:\n")
            for r in substantive_repos:
                safe_name = sanitize_filename(r.name)
                fw_tag = f" — *{', '.join(r.all_frameworks)}*" if r.all_frameworks else ""
                churn_display = f"Churn: +{r.lines_added:,} / -{r.lines_deleted:,}"
                content.append(f"- **[{r.name}](repos/{safe_name}.md)** (`{r.primary_language}`): {r.description}{fw_tag} ({churn_display}, {r.commit_count} commits)")
            content.append("")

        # Separate Section for Minimal / Stub Repositories
        if stub_repos:
            content.append(f"## Minimal & Stub Repositories ({len(stub_repos)} stubs / 1-file repos)\n")
            content.append("Repositories identified as initial placeholders, single-file tests, or only containing a README:\n")
            for r in stub_repos:
                safe_name = sanitize_filename(r.name)
                content.append(f"- **[{r.name}](repos/{safe_name}.md)** — *{r.stub_reason}* (`{r.activity_status}`, {r.commit_count} commits)")
            content.append("")

        # Grouping by Primary Language
        content.append("## Repositories by Primary Technology\n")
        by_language: Dict[str, List[RepoReport]] = {}
        for r in reports:
            by_language.setdefault(r.primary_language, []).append(r)

        for lang, lang_repos in sorted(by_language.items(), key=lambda x: len(x[1]), reverse=True):
            content.append(f"### {lang} ({len(lang_repos)} repositories)\n")
            for r in lang_repos:
                safe_name = sanitize_filename(r.name)
                fw_tag = f" — *{', '.join(r.all_frameworks)}*" if r.all_frameworks else ""
                content.append(f"- **[{r.name}](repos/{safe_name}.md)**: {r.description}{fw_tag} (`{r.activity_status}`, {r.commit_count} commits)")
            content.append("")

        # Grouping by Activity Status
        content.append("## Repositories by Activity and Maintenance Status\n")
        by_status: Dict[str, List[RepoReport]] = {}
        for r in reports:
            by_status.setdefault(r.activity_status, []).append(r)

        for status, status_repos in by_status.items():
            content.append(f"### {status} ({len(status_repos)})\n")
            for r in status_repos:
                safe_name = sanitize_filename(r.name)
                content.append(f"- **[{r.name}](repos/{safe_name}.md)** (`{r.primary_language}`) - Lifespan: {r.development_length}, {r.commit_count} commits")
            content.append("")

        # LLM Wiki Navigation & Query Guide
        content.append("## LLM Wiki Ingestion Instructions\n")
        content.append("This directory structure is formatted as a self-contained LLM knowledge base / wiki:")
        content.append("1. **Index (`INDEX.md`):** Use this file to get an overarching map of repositories, tech stacks, and activity statuses.")
        content.append("2. **Detailed Dossiers (`repos/<repo_name>.md`):** Inspect specific files when answering questions about repository architecture, dependencies, frameworks, commit history, or contributor roles.")
        content.append("3. **YAML Frontmatter:** Every markdown document contains structured YAML frontmatter for machine parsing, vector database ingestion, or tool calling.")
        content.append("\n---\n*Generated by GitHub Wiki Inspector.*")

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(content) + "\n")

        return filepath
