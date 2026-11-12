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
        content.append(f"size_kb: {repo.size_kb}")
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
        content.append("wiki_type: repository-spec")
        content.append("---\n")

        # 2. Navigation & Header
        content.append("[← Back to Master Repository Index](../INDEX.md)\n")
        content.append(f"# {repo.name}\n")
        
        # Badges row
        badges = [
            f"**Visibility:** `{repo.visibility}`",
            f"**Status:** `{repo.activity_status}`",
            f"**Language:** `{repo.primary_language}`",
            f"**Commits:** `{repo.commit_count}`",
            f"**Stars:** `{repo.stars_count}`",
            f"**License:** `{repo.license_name}`"
        ]
        content.append(" | ".join(badges) + "\n")
        content.append(f"> {repo.description}\n")
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
        content.append(f"| **Codebase Scale** | `{repo.scale_label}` | Disk size: {repo.size_kb:,} KB |")
        content.append(f"| **Primary Language** | `{repo.primary_language}` | Dominant language by byte volume |")
        content.append(f"| **Total Commits** | `{repo.commit_count}` commits | On default branch `{repo.default_branch}` |")
        content.append(f"| **Development Lifespan** | `{repo.development_length}` | From inception to latest push |")
        content.append(f"| **Created Date** | `{repo.created_at[:10] if repo.created_at else 'Unknown'}` | Initial repo creation |")
        content.append(f"| **Last Pushed Date** | `{repo.pushed_at[:10] if repo.pushed_at else 'Unknown'}` | {repo.days_since_last_push} days ago |")
        content.append(f"| **Default Branch** | `{repo.default_branch}` | Total active branches: {repo.branch_count} |")
        content.append(f"| **Releases / Tags** | `{repo.releases_count}` releases | {'Latest: ' + repo.latest_release.tag_name if repo.latest_release else 'None'} |")
        content.append(f"| **Community Engagement** | `{repo.stars_count}` ★ / `{repo.forks_count}` ⑂ | Watchers: {repo.watchers_count}, Open Issues: {repo.open_issues_count} |")
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
        content.append(f"total_commits: {total_commits}")
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
        content.append(f"| **Total Commits Analyzed** | `{total_commits:,}` | Cumulative commit activity |")
        content.append(f"| **Total Stars Earned** | `{total_stars:,}` | Stars across repositories |")
        content.append(f"| **Total Forks** | `{total_forks:,}` | Forks across repositories |")
        primary_lang_str = ", ".join([f"**{l}** ({c})" for l, c in sorted_langs[:5]]) if sorted_langs else "None"
        content.append(f"| **Top Languages** | {primary_lang_str} | Primary languages across portfolio |")
        content.append("")

        # Master Catalog Table
        content.append("## Repository Catalog\n")
        content.append("Links to individual repository specifications.\n")
        content.append("| Repository | Primary Language | Detected Frameworks | Scale | Commits | Stars | Last Active | Status |")
        content.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")

        for r in sorted(reports, key=lambda x: x.days_since_last_push):
            safe_name = sanitize_filename(r.name)
            repo_link = f"[{r.name}](repos/{safe_name}.md)"
            fw_str = ", ".join(r.all_frameworks[:3]) + (f" *+{len(r.all_frameworks)-3}*" if len(r.all_frameworks) > 3 else "")
            fw_str = fw_str if fw_str else "—"
            scale_short = r.scale_label.split(" (")[0]
            last_pushed = r.pushed_at[:10] if r.pushed_at else "—"
            content.append(
                f"| **{repo_link}** | `{r.primary_language}` | {fw_str} | {scale_short} | {r.commit_count:,} | {r.stars_count} | {last_pushed} | `{r.activity_status}` |"
            )
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
