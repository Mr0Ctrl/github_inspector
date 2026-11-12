import math
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

from .framework_detector import FrameworkDetector

def parse_iso(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str:
        return None
    try:
        # Format: 2023-08-01T12:00:00Z
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except Exception:
        return None

def format_duration(start_dt: datetime, end_dt: datetime) -> str:
    """Format duration between two datetimes in human readable form."""
    diff = end_dt - start_dt
    days = max(0, diff.days)
    if days == 0:
        return "1 day (initial release)"
    if days < 30:
        return f"{days} days"
    months = days // 30
    rem_days = days % 30
    if months < 12:
        return f"{months} month{'s' if months > 1 else ''}" + (f", {rem_days} days" if rem_days > 5 else "")
    years = months // 12
    rem_months = months % 12
    res = f"{years} year{'s' if years > 1 else ''}"
    if rem_months > 0:
        res += f", {rem_months} month{'s' if rem_months > 1 else ''}"
    return res

def categorize_scale(size_kb: int) -> str:
    if size_kb < 1000:
        return f"Micro (< 1 MB, {size_kb} KB)"
    elif size_kb < 10000:
        return f"Small ({size_kb / 1024:.1f} MB)"
    elif size_kb < 50000:
        return f"Medium ({size_kb / 1024:.1f} MB)"
    elif size_kb < 200000:
        return f"Large ({size_kb / 1024:.1f} MB)"
    else:
        return f"Enterprise ({size_kb / 1024:.1f} MB)"

@dataclass
class ContributorInfo:
    login: str
    contributions: int
    html_url: str
    percentage: float = 0.0

@dataclass
class ReleaseInfo:
    tag_name: str
    name: str
    published_at: Optional[str]
    html_url: str

@dataclass
class RepoReport:
    name: str
    full_name: str
    owner: str
    html_url: str
    description: str
    visibility: str
    is_fork: bool
    is_archived: bool
    default_branch: str
    license_name: str
    homepage: str
    topics: List[str]
    
    # Scale & Size
    size_kb: int
    scale_label: str
    
    # Languages
    primary_language: str
    language_breakdown: Dict[str, Dict[str, Any]]  # lang -> {bytes, percentage}
    
    # Frameworks
    frameworks_by_category: Dict[str, List[str]]
    all_frameworks: List[str]
    
    # Timeline & Velocity
    created_at: Optional[str]
    pushed_at: Optional[str]
    updated_at: Optional[str]
    first_commit_date: Optional[str]
    latest_commit_date: Optional[str]
    development_length: str
    days_since_last_push: int
    activity_status: str
    
    # Commits & Branches
    commit_count: int
    branches: List[str]
    branch_count: int
    
    # Releases
    releases: List[ReleaseInfo]
    releases_count: int
    latest_release: Optional[ReleaseInfo]
    
    # Contributors & Community
    contributors: List[ContributorInfo]
    contributors_count: int
    top_contributor_share: float
    collaboration_style: str
    stars_count: int
    forks_count: int
    watchers_count: int
    open_issues_count: int
    
    # Structure & Docs
    root_files: List[str]
    readme_excerpt: str
    llm_summary: str

class RepoAnalyzer:
    def __init__(self, client):
        self.client = client
        self.detector = FrameworkDetector(client)

    def analyze(self, raw_repo: Dict[str, Any]) -> RepoReport:
        owner = raw_repo.get("owner", {}).get("login", "")
        name = raw_repo.get("name", "")
        full_name = raw_repo.get("full_name", f"{owner}/{name}")
        html_url = raw_repo.get("html_url", "")
        description = raw_repo.get("description") or "No description provided."
        visibility = "Private" if raw_repo.get("private") else "Public"
        is_fork = bool(raw_repo.get("fork"))
        is_archived = bool(raw_repo.get("archived"))
        default_branch = raw_repo.get("default_branch", "main")
        license_info = raw_repo.get("license")
        license_name = license_info.get("name") if license_info else "None specified"
        homepage = raw_repo.get("homepage") or ""
        topics = raw_repo.get("topics") or []

        # Codebase scale
        size_kb = raw_repo.get("size", 0)
        scale_label = categorize_scale(size_kb)

        # Languages
        raw_langs = self.client.get_languages(owner, name)
        total_lang_bytes = sum(raw_langs.values())
        lang_breakdown: Dict[str, Dict[str, Any]] = {}
        for l_name, l_bytes in sorted(raw_langs.items(), key=lambda x: x[1], reverse=True):
            pct = (l_bytes / total_lang_bytes * 100) if total_lang_bytes > 0 else 0
            lang_breakdown[l_name] = {
                "bytes": l_bytes,
                "percentage": round(pct, 1)
            }
        primary_language = raw_repo.get("language") or (list(lang_breakdown.keys())[0] if lang_breakdown else "Unknown")

        # Root files inspection for frameworks
        root_files = self.client.get_root_files(owner, name)
        frameworks_by_cat = self.detector.detect(owner, name, root_files)
        all_frameworks = []
        for cat_list in frameworks_by_cat.values():
            all_frameworks.extend(cat_list)
        all_frameworks = sorted(list(set(all_frameworks)))

        # Commit stats
        commit_count, latest_commit, first_commit = self.client.get_commit_stats(owner, name)
        
        latest_commit_date = None
        if latest_commit and "commit" in latest_commit:
            latest_commit_date = latest_commit["commit"].get("committer", {}).get("date")

        first_commit_date = None
        if first_commit and "commit" in first_commit:
            first_commit_date = first_commit["commit"].get("committer", {}).get("date")

        # Dates & Lifespan
        created_at_str = raw_repo.get("created_at")
        pushed_at_str = raw_repo.get("pushed_at") or latest_commit_date
        updated_at_str = raw_repo.get("updated_at")

        dt_created = parse_iso(created_at_str)
        dt_pushed = parse_iso(pushed_at_str) or parse_iso(latest_commit_date)
        dt_first = parse_iso(first_commit_date) or dt_created

        # Development length
        dev_start = dt_first or dt_created
        dev_end = dt_pushed or datetime.now(timezone.utc)
        development_length = format_duration(dev_start, dev_end) if dev_start and dev_end else "Unknown"

        # Days since last push & Activity status
        now_utc = datetime.now(timezone.utc)
        days_since_push = (now_utc - dt_pushed).days if dt_pushed else 9999
        if is_archived:
            activity_status = "Archived"
        elif days_since_push < 60:
            activity_status = "Active Development"
        elif days_since_push < 180:
            activity_status = "Maintained"
        elif days_since_push < 365:
            activity_status = "Dormant / Stale"
        else:
            activity_status = "Inactive / Legacy"

        # Branches
        branches = self.client.get_branches(owner, name)
        branch_count = len(branches)

        # Releases
        raw_releases = self.client.get_releases(owner, name)
        releases = []
        for r in raw_releases:
            releases.append(ReleaseInfo(
                tag_name=r.get("tag_name", ""),
                name=r.get("name") or r.get("tag_name", ""),
                published_at=r.get("published_at"),
                html_url=r.get("html_url", "")
            ))
        latest_release = releases[0] if releases else None
        releases_count = len(releases)

        # Contributors
        raw_contribs = self.client.get_contributors(owner, name)
        contributors: List[ContributorInfo] = []
        total_contrib_commits = sum(c.get("contributions", 0) for c in raw_contribs)
        for c in raw_contribs:
            c_commits = c.get("contributions", 0)
            pct = (c_commits / total_contrib_commits * 100) if total_contrib_commits > 0 else 0
            contributors.append(ContributorInfo(
                login=c.get("login", "unknown"),
                contributions=c_commits,
                html_url=c.get("html_url", ""),
                percentage=round(pct, 1)
            ))
        contributors_count = len(contributors)
        top_contributor_share = contributors[0].percentage if contributors else 100.0

        if contributors_count <= 1:
            collaboration_style = "Solo Project"
        elif top_contributor_share > 85.0:
            collaboration_style = "Solo Lead with Minor Contributors"
        else:
            collaboration_style = f"Collaborative Team ({contributors_count} contributors)"

        # Community metrics
        stars_count = raw_repo.get("stargazers_count", 0)
        forks_count = raw_repo.get("forks_count", 0)
        watchers_count = raw_repo.get("watchers_count", 0)
        open_issues_count = raw_repo.get("open_issues_count", 0)

        # Readme
        readme_raw = self.client.get_readme(owner, name) or ""
        readme_excerpt = self._extract_readme_summary(readme_raw)

        # Synthesize dense LLM Wiki summary
        llm_summary = self._generate_llm_summary(
            name=name,
            description=description,
            primary_language=primary_language,
            frameworks=all_frameworks,
            scale_label=scale_label,
            commits=commit_count,
            dev_length=development_length,
            activity_status=activity_status,
            collab=collaboration_style,
            topics=topics,
            stars=stars_count
        )

        return RepoReport(
            name=name,
            full_name=full_name,
            owner=owner,
            html_url=html_url,
            description=description,
            visibility=visibility,
            is_fork=is_fork,
            is_archived=is_archived,
            default_branch=default_branch,
            license_name=license_name,
            homepage=homepage,
            topics=topics,
            size_kb=size_kb,
            scale_label=scale_label,
            primary_language=primary_language,
            language_breakdown=lang_breakdown,
            frameworks_by_category=frameworks_by_cat,
            all_frameworks=all_frameworks,
            created_at=created_at_str,
            pushed_at=pushed_at_str,
            updated_at=updated_at_str,
            first_commit_date=first_commit_date,
            latest_commit_date=latest_commit_date,
            development_length=development_length,
            days_since_last_push=days_since_push,
            activity_status=activity_status,
            commit_count=commit_count,
            branches=branches,
            branch_count=branch_count,
            releases=releases,
            releases_count=releases_count,
            latest_release=latest_release,
            contributors=contributors,
            contributors_count=contributors_count,
            top_contributor_share=top_contributor_share,
            collaboration_style=collaboration_style,
            stars_count=stars_count,
            forks_count=forks_count,
            watchers_count=watchers_count,
            open_issues_count=open_issues_count,
            root_files=root_files,
            readme_excerpt=readme_excerpt,
            llm_summary=llm_summary
        )

    def _extract_readme_summary(self, readme_text: str) -> str:
        if not readme_text:
            return "No README file found in repository."
        # Strip badges, markdown headers, and empty lines to get readable text
        import re
        lines = []
        for line in readme_text.splitlines():
            line = line.strip()
            if not line:
                continue
            # Skip badge links e.g. [![...](...)]
            if re.match(r'^\[?!\[.*?\]\(.*?\)\]?', line):
                continue
            # Strip markdown title marks #
            if line.startswith("#"):
                clean = line.lstrip("#").strip()
                if clean:
                    lines.append(f"**{clean}**")
                continue
            lines.append(line)
            if len(" ".join(lines)) > 600:
                break
        excerpt = "\n\n".join(lines[:4])
        return excerpt if excerpt else "README contains only media/badges."

    def _generate_llm_summary(self, name: str, description: str, primary_language: str,
                              frameworks: List[str], scale_label: str, commits: int,
                              dev_length: str, activity_status: str, collab: str,
                              topics: List[str], stars: int) -> str:
        fw_str = f" utilizing {', '.join(frameworks)}" if frameworks else ""
        topics_str = f" Tagged with: {', '.join(topics)}." if topics else ""
        stars_str = f" It has garnered {stars} stars." if stars > 0 else ""
        return (
            f"**`{name}`** is a {scale_label.lower()} repository primarily written in **{primary_language}**{fw_str}. "
            f"Purpose: {description} "
            f"Development span: **{dev_length}** across **{commits} commits**. "
            f"Current status: **{activity_status}** ({collab}).{topics_str}{stars_str}"
        )
