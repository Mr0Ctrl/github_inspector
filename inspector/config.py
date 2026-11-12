import os
import re
from pathlib import Path
from typing import Optional, Dict

def parse_env_file(filepath: Path) -> Dict[str, str]:
    """Parse a .env file without external dependencies."""
    env_vars = {}
    if not filepath.exists() or not filepath.is_file():
        return env_vars

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue
            # Look for KEY=VALUE
            if "=" in line:
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip()
                # Remove surrounding quotes (single or double)
                if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]
                # Strip inline comments if value is not quoted
                elif " #" in val:
                    val = val.split(" #", 1)[0].strip()
                env_vars[key] = val
    return env_vars

def clean_github_username(user_input: str) -> str:
    """
    Extract pure username from raw username or full GitHub URL.
    Examples:
      - 'octocat' -> 'octocat'
      - 'https://github.com/octocat' -> 'octocat'
      - 'github.com/octocat/' -> 'octocat'
      - 'https://github.com/octocat?tab=repositories' -> 'octocat'
    """
    if not user_input:
        return ""
    clean = user_input.strip()
    # Strip URL protocol and domain if present
    clean = re.sub(r"^https?://(www\.)?github\.com/", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"^github\.com/", "", clean, flags=re.IGNORECASE)
    # Remove query params or fragments
    clean = clean.split("?")[0].split("#")[0]
    # Remove leading/trailing slashes
    clean = clean.strip("/")
    # If path had subpaths like 'octocat/repo', take the first segment
    if "/" in clean:
        clean = clean.split("/")[0]
    return clean

class Config:
    def __init__(self, env_path: Optional[str] = None):
        self.env_path = Path(env_path) if env_path else Path(".env")
        self._loaded_env: Dict[str, str] = {}
        self.load()

    def load(self):
        # Look for .env in current directory or script directory
        candidates = [
            self.env_path,
            Path.cwd() / ".env",
            Path(__file__).resolve().parent.parent / ".env"
        ]
        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                self._loaded_env = parse_env_file(candidate)
                self.env_path = candidate
                break

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        # Priority: System environment > .env file > default
        return os.environ.get(key, self._loaded_env.get(key, default))

    @property
    def token(self) -> Optional[str]:
        token = (
            self.get("GITHUB_TOKEN")
            or self.get("GH_TOKEN")
            or self.get("GITHUB_API_KEY")
            or self.get("GITHUB_PAT")
        )
        return token.strip() if token else None

    @property
    def username(self) -> str:
        raw = (
            self.get("GITHUB_USERNAME")
            or self.get("GITHUB_USER")
            or self.get("GITHUB_USER_URL")
            or self.get("GH_USER")
            or ""
        )
        return clean_github_username(raw)

    @property
    def output_dir(self) -> Path:
        out = self.get("OUTPUT_DIR", "./reports")
        return Path(out).resolve()

    @property
    def include_forks(self) -> bool:
        val = str(self.get("INCLUDE_FORKS", "true")).strip().lower()
        return val in ("true", "1", "yes", "y")

    @property
    def repo_visibility(self) -> str:
        # 'all', 'public', or 'private'
        val = str(self.get("REPO_VISIBILITY", "all")).strip().lower()
        if val in ("public", "private", "all"):
            return val
        return "all"
