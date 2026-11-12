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

def categorize_scale(code_bytes: int, disk_size_kb: int) -> tuple[str, str]:
    """
    Categorize repository scale based on actual source code bytes,
    ignoring images, media, and binary assets.
    """
    code_kb = round(code_bytes / 1024.0, 1)

    if code_kb < 100:
        scale_label = f"Micro (< 100 KB code, {code_kb} KB)"
    elif code_kb < 1000:
        scale_label = f"Small ({code_kb} KB code)"
    elif code_kb < 10000:
        scale_label = f"Medium ({code_kb / 1024:.1f} MB code)"
    elif code_kb < 50000:
        scale_label = f"Large ({code_kb / 1024:.1f} MB code)"
    else:
        scale_label = f"Enterprise ({code_kb / 1024:.1f} MB code)"

    # Detect when images/binaries inflate total disk size
    disk_mb = disk_size_kb / 1024.0
    code_mb = code_kb / 1024.0
    if disk_mb > 3.0 and code_mb < (disk_mb * 0.3):
        asset_note = f"Asset-heavy: Total disk is {disk_mb:.1f} MB (images/media/binaries); pure source code is {code_kb} KB."
    elif disk_size_kb > 0 and code_bytes == 0:
        asset_note = f"Asset-only: Disk is {disk_size_kb} KB, with no recognized source code files."
    else:
        asset_note = f"Source code: {code_kb} KB (Disk: {disk_size_kb} KB)."

    return scale_label, asset_note

def parse_notebook_content(raw_json: str) -> Dict[str, Any]:
    """
    Parse a Jupyter Notebook (.ipynb) JSON structure.
    Extracts pure executable code lines, markdown documentation lines,
    pure code character bytes, and ignores bloated base64 plot outputs.
    """
    import json
    try:
        nb = json.loads(raw_json)
    except Exception:
        return {"code_lines": 0, "md_lines": 0, "code_bytes": 0, "code_text": ""}

    code_lines = 0
    md_lines = 0
    code_chunks = []

    for cell in nb.get("cells", []):
        ctype = cell.get("cell_type")
        source = cell.get("source", [])
        lines = source if isinstance(source, list) else source.splitlines()
        clean_lines = [l.strip() for l in lines if l.strip()]

        if ctype == "code":
            code_lines += len(clean_lines)
            code_chunks.append("".join(lines))
        elif ctype == "markdown":
            md_lines += len(clean_lines)

    code_text = "\n".join(code_chunks)
    code_bytes = len(code_text.encode("utf-8"))
    return {
        "code_lines": code_lines,
        "md_lines": md_lines,
        "code_bytes": code_bytes,
        "code_text": code_text
    }

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
    code_bytes: int
    scale_label: str
    asset_breakdown_note: str
    
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

    # Classification & Stub Detection
    is_stub_or_empty: bool = False
    repo_classification: str = "Substantive Project"
    stub_reason: Optional[str] = None

    # Code Churn & Change Volume
    lines_added: int = 0
    lines_deleted: int = 0
    net_lines: int = 0
    total_churn: int = 0
    avg_churn_per_commit: float = 0.0
    change_intensity: str = "Unknown"

    # Jupyter Notebook Specifics
    notebook_count: int = 0
    notebook_code_lines: int = 0
    notebook_markdown_lines: int = 0

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

        # Languages & pure source code volume (excludes images and binaries)
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

        # Codebase scale based on pure code bytes (ignores images/media)
        size_kb = raw_repo.get("size", 0)
        scale_label, asset_note = categorize_scale(total_lang_bytes, size_kb)

        # Root files inspection for frameworks
        root_files = self.client.get_root_files(owner, name)
        frameworks_by_cat = self.detector.detect(owner, name, root_files)

        # Detect and parse Jupyter Notebooks (.ipynb)
        notebook_files = [f for f in root_files if f.lower().endswith(".ipynb")]
        if not notebook_files and (primary_language == "Jupyter Notebook" or "Jupyter Notebook" in raw_langs):
            tree_files = self.client.get_tree_files(owner, name, default_branch)
            notebook_files = [f for f in tree_files if f.lower().endswith(".ipynb")]

        total_nb_code_lines = 0
        total_nb_md_lines = 0
        total_nb_code_bytes = 0
        nb_code_snippets = []

        # Parse notebooks (up to 10 files to balance depth & API quota)
        for nb_path in notebook_files[:10]:
            nb_content = self.client.get_file_content(owner, name, nb_path)
            if nb_content:
                parsed_nb = parse_notebook_content(nb_content)
                total_nb_code_lines += parsed_nb["code_lines"]
                total_nb_md_lines += parsed_nb["md_lines"]
                total_nb_code_bytes += parsed_nb["code_bytes"]
                if parsed_nb["code_text"]:
                    nb_code_snippets.append(parsed_nb["code_text"])

        # Detect frameworks directly from Jupyter notebook code cells
        if nb_code_snippets:
            joined_nb_code = "\n".join(nb_code_snippets).lower()
            self.detector._match_patterns(joined_nb_code, frameworks_by_cat)

        all_frameworks = []
        for cat_list in frameworks_by_cat.values():
            all_frameworks.extend(cat_list)
        all_frameworks = sorted(list(set(all_frameworks)))

        # Adjust pure code scale if Jupyter notebooks are present
        if total_nb_code_bytes > 0:
            if "Jupyter Notebook" in raw_langs:
                # Replace raw JSON byte size of .ipynb with the actual code character bytes
                pure_lang_bytes = (total_lang_bytes - raw_langs.get("Jupyter Notebook", 0)) + total_nb_code_bytes
            else:
                pure_lang_bytes = total_lang_bytes + total_nb_code_bytes
            scale_label, asset_note = categorize_scale(pure_lang_bytes, size_kb)

        # Fix for newly created repos where GitHub API temporarily returns size: 0
        if size_kb == 0 and (total_lang_bytes > 0 or total_nb_code_bytes > 0):
            size_kb = max(1, (total_lang_bytes + total_nb_code_bytes) // 1024)
            scale_label, asset_note = categorize_scale(total_lang_bytes + total_nb_code_bytes, size_kb)

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

        # Code Churn & Volume of Changes (how much change happens)
        code_freq = self.client.get_code_frequency(owner, name)
        lines_added = sum(w[1] for w in code_freq if len(w) >= 3 and w[1] > 0)
        lines_deleted = sum(abs(w[2]) for w in code_freq if len(w) >= 3)

        # Fallback 1: Incorporate Jupyter notebook code cells if diffs missed them
        if total_nb_code_lines > 0:
            lines_added = max(lines_added, total_nb_code_lines)

        # Fallback 2: If stats cache was unavailable, sample recent commits directly
        if lines_added == 0 and commit_count > 0:
            sample_add, sample_del = self.client.get_commit_churn_sample(owner, name, limit=min(12, commit_count))
            lines_added = sample_add
            lines_deleted = sample_del

        # Fallback 3: If still 0 but repository contains source code bytes, estimate baseline lines
        if lines_added == 0 and total_lang_bytes > 0 and commit_count > 0:
            lines_added = max(20, total_lang_bytes // 35)

        net_lines = lines_added - lines_deleted
        total_churn = lines_added + lines_deleted
        avg_churn_per_commit = round(total_churn / commit_count, 1) if commit_count > 0 else 0.0

        if total_churn == 0:
            change_intensity = "No tracked line changes"
        elif total_churn < 50:
            change_intensity = "Trivial churn (< 50 lines modified)"
        elif lines_added > 0 and (lines_deleted / lines_added) > 0.40:
            change_intensity = "High refactoring (heavy rewriting/deletions)"
        elif lines_added > 0 and (lines_deleted / lines_added) < 0.15:
            change_intensity = "Additive growth (mostly new code additions)"
        else:
            change_intensity = "Iterative evolution (balanced edits)"

        # Stub & Empty Repository Detection
        lower_root_files = [f.lower() for f in root_files]
        is_stub_or_empty = False
        repo_classification = "Substantive Project"
        stub_reason = None

        if commit_count == 0 and len(root_files) == 0:
            is_stub_or_empty = True
            repo_classification = "Empty Repository"
            stub_reason = "Repository has 0 commits and contains no files."
        elif len(root_files) == 1:
            only_file = root_files[0]
            if "readme" in only_file.lower():
                is_stub_or_empty = True
                repo_classification = "Minimal / Stub (Only README)"
                stub_reason = f"Single file in repository: '{only_file}'."
            elif not all_frameworks and total_churn < 50:
                is_stub_or_empty = True
                repo_classification = "Minimal / Stub (Single File)"
                stub_reason = f"Only one file present: '{only_file}'."
        elif len(root_files) <= 2 and all("readme" in f or "license" in f or f.startswith(".") for f in lower_root_files) and total_churn < 50:
            is_stub_or_empty = True
            repo_classification = "Minimal / Stub (Skeleton only)"
            stub_reason = f"Only meta/config files present ({', '.join(root_files)})."
        elif commit_count <= 2 and len(root_files) <= 3 and not all_frameworks and total_churn < 50:
            is_stub_or_empty = True
            repo_classification = "Minimal / Stub (Starter test)"
            stub_reason = f"Very low commit volume ({commit_count} commits, {total_churn} LOC churn) and minimal files."

        # If Jupyter notebooks have substantial code cells, it is a genuine substantive project
        if total_nb_code_lines > 15:
            is_stub_or_empty = False
            repo_classification = "Substantive Project"
            stub_reason = None

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
            stars=stars_count,
            classification=repo_classification,
            churn_str=f"+{lines_added:,} / -{lines_deleted:,} LOC" if total_churn > 0 else "0 LOC churn"
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
            code_bytes=total_lang_bytes,
            scale_label=scale_label,
            asset_breakdown_note=asset_note,
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
            llm_summary=llm_summary,
            is_stub_or_empty=is_stub_or_empty,
            repo_classification=repo_classification,
            stub_reason=stub_reason,
            lines_added=lines_added,
            lines_deleted=lines_deleted,
            net_lines=net_lines,
            total_churn=total_churn,
            avg_churn_per_commit=avg_churn_per_commit,
            change_intensity=change_intensity
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
                              topics: List[str], stars: int,
                              classification: str = "Substantive Project",
                              churn_str: str = "") -> str:
        fw_str = f" utilizing {', '.join(frameworks)}" if frameworks else ""
        topics_str = f" Tagged with: {', '.join(topics)}." if topics else ""
        stars_str = f" It has garnered {stars} stars." if stars > 0 else ""
        class_str = f" Classified as [{classification}]." if classification != "Substantive Project" else ""
        churn_info = f" Code churn: {churn_str}." if churn_str else ""
        return (
            f"**`{name}`** is a {scale_label.lower()} repository primarily written in **{primary_language}**{fw_str}. "
            f"Purpose: {description} "
            f"Development span: **{dev_length}** across **{commits} commits**.{churn_info} "
            f"Current status: **{activity_status}** ({collab}).{class_str}{topics_str}{stars_str}"
        )
