import json
import base64
import time
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

class GitHubAPIError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[Dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data

class GitHubClient:
    BASE_URL = "https://api.github.com"

    def __init__(self, token: Optional[str] = None):
        self.token = token
        self.last_rate_limit_remaining: Optional[int] = None
        self.last_rate_limit_reset: Optional[int] = None

    def _build_request(self, url: str, headers: Optional[Dict[str, str]] = None) -> urllib.request.Request:
        req = urllib.request.Request(url)
        req.add_header("Accept", "application/vnd.github.v3+json")
        req.add_header("User-Agent", "GitHub-Wiki-Inspector/1.0")
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        if headers:
            for k, v in headers.items():
                req.add_header(k, v)
        return req

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None, return_headers: bool = False) -> Any:
        """Execute a GET request against the GitHub API."""
        if endpoint.startswith("http"):
            url = endpoint
        else:
            url = f"{self.BASE_URL}{endpoint if endpoint.startswith('/') else '/' + endpoint}"

        if params:
            query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
            url = f"{url}?{query}" if "?" not in url else f"{url}&{query}"

        req = self._build_request(url)

        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                status = response.status
                headers = dict(response.headers)
                
                # Track rate limit
                if "x-ratelimit-remaining" in headers:
                    try:
                        self.last_rate_limit_remaining = int(headers["x-ratelimit-remaining"])
                        self.last_rate_limit_reset = int(headers.get("x-ratelimit-reset", 0))
                    except (ValueError, TypeError):
                        pass

                body = response.read().decode("utf-8", errors="replace")
                data = json.loads(body) if body else None

                if return_headers:
                    return data, headers
                return data

        except urllib.error.HTTPError as e:
            headers = dict(e.headers)
            body = e.read().decode("utf-8", errors="replace")
            try:
                err_data = json.loads(body)
                msg = err_data.get("message", str(e))
            except Exception:
                err_data = None
                msg = body or str(e)

            # Check for rate limit exceeded
            if e.code == 403 and "rate limit" in msg.lower():
                reset_time = headers.get("x-ratelimit-reset")
                if reset_time:
                    try:
                        dt = datetime.fromtimestamp(int(reset_time)).strftime('%H:%M:%S')
                        msg = f"GitHub API Rate Limit exceeded! Resets at {dt}."
                    except Exception:
                        pass
            raise GitHubAPIError(f"HTTP {e.code}: {msg}", status_code=e.code, response_data=err_data)
        except urllib.error.URLError as e:
            raise GitHubAPIError(f"Network error connecting to GitHub: {e.reason}")

    def get_rate_limit(self) -> Dict[str, Any]:
        """Fetch current rate limit status."""
        try:
            return self.get("/rate_limit")
        except Exception:
            return {}

    def get_user_profile(self, username: Optional[str] = None) -> Dict[str, Any]:
        """Get profile for authenticated user or specified username."""
        if username:
            return self.get(f"/users/{username}")
        # If token is provided and username is empty, fetch authenticated user
        return self.get("/user")

    def get_user_repos(self, username: Optional[str] = None, visibility: str = "all", include_forks: bool = True) -> List[Dict[str, Any]]:
        """
        List repositories for user.
        If username is authenticated user or omitted, uses /user/repos to support private repos.
        """
        repos = []
        page = 1
        per_page = 100

        # Determine authenticated user login if needed
        is_authenticated_user = False
        if self.token:
            try:
                auth_user = self.get("/user")
                if not username or (auth_user and auth_user.get("login", "").lower() == username.lower()):
                    is_authenticated_user = True
                    username = auth_user.get("login")
            except Exception:
                pass

        endpoint = "/user/repos" if is_authenticated_user else f"/users/{username}/repos"

        while True:
            params = {
                "per_page": per_page,
                "page": page,
                "sort": "updated",
                "direction": "desc"
            }
            if is_authenticated_user:
                if visibility in ("all", "public", "private"):
                    params["visibility"] = visibility
                params["affiliation"] = "owner"
            else:
                params["type"] = "all" if visibility == "all" else "owner"

            try:
                batch, headers = self.get(endpoint, params=params, return_headers=True)
            except GitHubAPIError as e:
                # If /user/repos failed or unauthorized, fallback to /users/{username}/repos
                if is_authenticated_user and username:
                    endpoint = f"/users/{username}/repos"
                    is_authenticated_user = False
                    continue
                raise e

            if not batch or not isinstance(batch, list):
                break

            for r in batch:
                if not include_forks and r.get("fork"):
                    continue
                if visibility == "private" and not r.get("private"):
                    continue
                if visibility == "public" and r.get("private"):
                    continue
                repos.append(r)

            if len(batch) < per_page:
                break
            page += 1

        return repos

    def get_languages(self, owner: str, repo: str) -> Dict[str, int]:
        """Get byte count for languages used in the repository."""
        try:
            return self.get(f"/repos/{owner}/{repo}/languages") or {}
        except GitHubAPIError:
            return {}

    def get_contributors(self, owner: str, repo: str, max_count: int = 15) -> List[Dict[str, Any]]:
        """Get repository contributors."""
        try:
            contributors = self.get(f"/repos/{owner}/{repo}/contributors", params={"per_page": max_count})
            if isinstance(contributors, list):
                return contributors
            return []
        except GitHubAPIError:
            return []

    def get_commit_stats(self, owner: str, repo: str) -> Tuple[int, Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        Quickly discover total commit count, latest commit, and earliest commit
        using the Link header pagination technique.
        Returns: (total_commits, latest_commit, first_commit)
        """
        try:
            # Fetch latest commit (page 1, per_page 1)
            commits, headers = self.get(
                f"/repos/{owner}/{repo}/commits",
                params={"per_page": 1, "page": 1},
                return_headers=True
            )
            if not commits or not isinstance(commits, list) or len(commits) == 0:
                return 0, None, None

            latest_commit = commits[0]
            total_commits = 1

            # Parse Link header to find last page
            # Example Link header:
            # <https://api.github.com/repositories/123/commits?per_page=1&page=45>; rel="last", <...>; rel="next"
            link_header = headers.get("link", "") or headers.get("Link", "")
            if link_header:
                import re
                match = re.search(r'[?&]page=(\d+)[^>]*>;\s*rel="last"', link_header)
                if match:
                    total_commits = int(match.group(1))

            first_commit = None
            if total_commits > 1:
                try:
                    first_batch = self.get(
                        f"/repos/{owner}/{repo}/commits",
                        params={"per_page": 1, "page": total_commits}
                    )
                    if first_batch and isinstance(first_batch, list) and len(first_batch) > 0:
                        first_commit = first_batch[0]
                except Exception:
                    pass

            if not first_commit:
                first_commit = latest_commit

            return total_commits, latest_commit, first_commit

        except GitHubAPIError:
            return 0, None, None

    def get_releases(self, owner: str, repo: str, max_count: int = 5) -> List[Dict[str, Any]]:
        """Get latest releases."""
        try:
            releases = self.get(f"/repos/{owner}/{repo}/releases", params={"per_page": max_count})
            return releases if isinstance(releases, list) else []
        except GitHubAPIError:
            return []

    def get_branches(self, owner: str, repo: str, max_count: int = 30) -> List[str]:
        """Get branch names."""
        try:
            branches = self.get(f"/repos/{owner}/{repo}/branches", params={"per_page": max_count})
            if isinstance(branches, list):
                return [b.get("name") for b in branches if "name" in b]
            return []
        except GitHubAPIError:
            return []

    def get_readme(self, owner: str, repo: str) -> Optional[str]:
        """Fetch and decode the repo's README if present."""
        try:
            data = self.get(f"/repos/{owner}/{repo}/readme")
            if data and "content" in data:
                content = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
                return content
            return None
        except GitHubAPIError:
            return None

    def get_root_files(self, owner: str, repo: str) -> List[str]:
        """List filenames in the root directory of the repo."""
        try:
            contents = self.get(f"/repos/{owner}/{repo}/contents")
            if isinstance(contents, list):
                return [item.get("name", "") for item in contents if "name" in item]
            return []
        except GitHubAPIError:
            return []

    def get_file_content(self, owner: str, repo: str, path: str) -> Optional[str]:
        """Fetch content of a specific file."""
        try:
            data = self.get(f"/repos/{owner}/{repo}/contents/{path.lstrip('/')}")
            if data and "content" in data:
                return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
            return None
        except GitHubAPIError:
            return None
