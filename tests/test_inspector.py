import unittest
import tempfile
import shutil
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from inspector.config import clean_github_username, parse_env_file, Config
from inspector.framework_detector import FrameworkDetector
from inspector.analyzer import format_duration, categorize_scale, RepoReport, ContributorInfo, ReleaseInfo
from inspector.markdown_generator import MarkdownGenerator, sanitize_filename

class DummyClient:
    def __init__(self, files_dict=None):
        self.files_dict = files_dict or {}

    def get_file_content(self, owner, repo, path):
        return self.files_dict.get(path)

class TestInspector(unittest.TestCase):
    def test_clean_username(self):
        self.assertEqual(clean_github_username("octocat"), "octocat")
        self.assertEqual(clean_github_username("https://github.com/octocat"), "octocat")
        self.assertEqual(clean_github_username("http://github.com/octocat/"), "octocat")
        self.assertEqual(clean_github_username("github.com/octocat?tab=repositories"), "octocat")
        self.assertEqual(clean_github_username("https://github.com/octocat/my-repo"), "octocat")

    def test_env_parser(self):
        with tempfile.NamedTemporaryFile("w+", delete=False) as f:
            f.write("# Sample env\n")
            f.write("GITHUB_TOKEN=\"ghp_sample123\"\n")
            f.write("GITHUB_USERNAME=https://github.com/octocat # Profile link\n")
            f.write("OUTPUT_DIR='./my_reports'\n")
            f_path = Path(f.name)

        try:
            parsed = parse_env_file(f_path)
            self.assertEqual(parsed.get("GITHUB_TOKEN"), "ghp_sample123")
            self.assertEqual(parsed.get("GITHUB_USERNAME"), "https://github.com/octocat")
            self.assertEqual(parsed.get("OUTPUT_DIR"), "./my_reports")
        finally:
            f_path.unlink()

    def test_framework_detector(self):
        client = DummyClient({
            "requirements.txt": "fastapi==0.100.0\nuvicorn\ntorch>=2.0\nlangchain\n",
            "package.json": '{"dependencies": {"react": "^18.0.0", "next": "13.4.0", "tailwindcss": "^3.0"}}'
        })
        detector = FrameworkDetector(client)
        detected = detector.detect("testowner", "testrepo", ["requirements.txt", "package.json", "Dockerfile"])
        
        self.assertIn("Docker", detected.get("DevOps & Infrastructure", []))
        self.assertIn("FastAPI", detected.get("Web Frameworks", []))
        self.assertIn("Next.js", detected.get("Web Frameworks", []))
        self.assertIn("React", detected.get("Web Frameworks", []))
        self.assertIn("PyTorch", detected.get("AI / Data Science & ML", []))
        self.assertIn("LangChain", detected.get("AI / Data Science & ML", []))

    def test_duration_and_scale(self):
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=400)
        dur = format_duration(start, now)
        self.assertIn("year", dur)

        lbl, note = categorize_scale(50 * 1024, 500)
        self.assertIn("Micro", lbl)
        lbl, note = categorize_scale(500 * 1024, 2000)
        self.assertIn("Small", lbl)
        lbl, note = categorize_scale(5 * 1024 * 1024, 10000)
        self.assertIn("Medium", lbl)

    def test_markdown_generator(self):
        temp_dir = Path(tempfile.mkdtemp())
        try:
            gen = MarkdownGenerator(temp_dir)
            report = RepoReport(
                name="ai-agent",
                full_name="testuser/ai-agent",
                owner="testuser",
                html_url="https://github.com/testuser/ai-agent",
                description="Intelligent AI Agent framework",
                visibility="Public",
                is_fork=False,
                is_archived=False,
                default_branch="main",
                license_name="MIT License",
                homepage="https://agent.example.com",
                topics=["ai", "agents", "python"],
                size_kb=3200,
                code_bytes=94000,
                scale_label="Small (91.8 KB code)",
                asset_breakdown_note="Source code: 91.8 KB (Disk: 3200 KB).",
                primary_language="Python",
                language_breakdown={"Python": {"bytes": 80000, "percentage": 85.0}, "Shell": {"bytes": 14000, "percentage": 15.0}},
                frameworks_by_category={"AI / Data Science & ML": ["PyTorch", "LangChain"], "Web Frameworks": ["FastAPI"]},
                all_frameworks=["FastAPI", "LangChain", "PyTorch"],
                created_at="2023-01-01T10:00:00Z",
                pushed_at="2024-02-01T12:00:00Z",
                updated_at="2024-02-01T12:00:00Z",
                first_commit_date="2023-01-01T10:00:00Z",
                latest_commit_date="2024-02-01T12:00:00Z",
                development_length="1 year, 1 month",
                days_since_last_push=30,
                activity_status="Active Development",
                commit_count=150,
                branches=["main", "feature/rag"],
                branch_count=2,
                releases=[ReleaseInfo(tag_name="v1.0.0", name="First Release", published_at="2023-06-01T00:00:00Z", html_url="https://github.com/testuser/ai-agent/releases/tag/v1.0.0")],
                releases_count=1,
                latest_release=ReleaseInfo(tag_name="v1.0.0", name="First Release", published_at="2023-06-01T00:00:00Z", html_url="https://github.com/testuser/ai-agent/releases/tag/v1.0.0"),
                contributors=[ContributorInfo(login="testuser", contributions=150, html_url="https://github.com/testuser", percentage=100.0)],
                contributors_count=1,
                top_contributor_share=100.0,
                collaboration_style="Solo Project",
                stars_count=42,
                forks_count=5,
                watchers_count=42,
                open_issues_count=2,
                root_files=["requirements.txt", "Dockerfile", "README.md", "main.py"],
                readme_excerpt="This is an intelligent agent.",
                llm_summary="ai-agent is an active Python repo.",
                is_stub_or_empty=False,
                repo_classification="Substantive Project",
                stub_reason=None,
                lines_added=4500,
                lines_deleted=1200,
                net_lines=3300,
                total_churn=5700,
                avg_churn_per_commit=38.0,
                change_intensity="Additive growth"
            )

            profile = {
                "login": "testuser",
                "name": "Test User",
                "bio": "Software Architect",
                "html_url": "https://github.com/testuser"
            }

            gen.generate_all(profile, [report])

            repo_md = temp_dir / "repos" / "ai-agent.md"
            index_md = temp_dir / "INDEX.md"

            self.assertTrue(repo_md.exists())
            self.assertTrue(index_md.exists())

            repo_content = repo_md.read_text(encoding="utf-8")
            self.assertIn("---", repo_content)
            self.assertIn('primary_language: "Python"', repo_content)
            self.assertIn("FastAPI", repo_content)
            self.assertIn("150 commits", repo_content)
            self.assertIn("4,500", repo_content)
            self.assertIn("Substantive Project", repo_content)

            index_content = index_md.read_text(encoding="utf-8")
            self.assertIn("Test User", index_content)
            self.assertIn("ai-agent", index_content)
            self.assertIn("Substantive Codebases", index_content)
        finally:
            shutil.rmtree(temp_dir)

if __name__ == "__main__":
    unittest.main()
