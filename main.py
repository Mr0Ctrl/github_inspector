#!/usr/bin/env python3
"""
Fully AI-generated repository.
GitHub Account & Repository Inspector for LLM Wikis.
"""
import sys
import argparse
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from inspector.config import Config, clean_github_username
from inspector.client import GitHubClient, GitHubAPIError
from inspector.analyzer import RepoAnalyzer
from inspector.markdown_generator import MarkdownGenerator

def print_banner():
    print("=" * 65)
    print("  GitHub Account & Repository Inspector for LLM Wikis")
    print("=" * 65)

def main():
    parser = argparse.ArgumentParser(
        description="Inspect GitHub account and generate LLM-ready markdown wiki for all repositories."
    )
    parser.add_argument("--env", type=str, default=".env", help="Path to .env configuration file (default: .env)")
    parser.add_argument("-u", "--user", type=str, help="GitHub username or profile URL (overrides .env)")
    parser.add_argument("-t", "--token", type=str, help="GitHub Personal Access Token (overrides .env)")
    parser.add_argument("-o", "--output", type=str, help="Output directory for generated markdown wiki (overrides .env)")
    parser.add_argument("--repo", type=str, help="Analyze only a single specific repository name")
    parser.add_argument("--visibility", choices=["all", "public", "private"], help="Filter repository visibility")
    parser.add_argument("--no-forks", action="store_true", help="Exclude forked repositories")

    args = parser.parse_args()

    print_banner()

    # Load configuration
    config = Config(env_path=args.env)

    token = args.token or config.token
    raw_user = args.user or config.username
    username = clean_github_username(raw_user)
    output_dir = Path(args.output).resolve() if args.output else config.output_dir
    visibility = args.visibility or config.repo_visibility
    include_forks = not args.no_forks if args.no_forks else config.include_forks

    if not token and not username:
        print("\n[ERROR] Neither GitHub token nor username was provided.")
        print("Set .env file or pass --user <username> / --token <token>.")
        print("\nExample .env:")
        print("  GITHUB_TOKEN=ghp_yourPersonalAccessTokenHere")
        print("  GITHUB_USERNAME=yourUsernameOrUrl\n")
        sys.exit(1)

    print("[*] Configuration:")
    print(f"    - Target User   : {username if username else '(Authenticated Token Owner)'}")
    print(f"    - Auth Token    : {'[Provided]' if token else '[Unauthenticated]'}")
    print(f"    - Output Dir    : {output_dir}")
    print(f"    - Visibility    : {visibility}")
    print(f"    - Include Forks : {include_forks}")
    print()

    client = GitHubClient(token=token)

    # Check connection and rate limit
    try:
        rl_data = client.get_rate_limit()
        core_rl = rl_data.get("resources", {}).get("core", {})
        if core_rl:
            print(f"[*] GitHub API Quota: {core_rl.get('remaining')}/{core_rl.get('limit')} requests remaining.")
            if core_rl.get('remaining', 0) < 50:
                print("    [WARN] API rate limit is running low.")
    except Exception as e:
        print(f"    [WARN] Could not check rate limit: {e}")

    # Fetch User Profile
    print("[*] Fetching profile information...")
    try:
        user_profile = client.get_user_profile(username=username)
        username = user_profile.get("login", username)
        print(f"    [OK] Profile: {user_profile.get('name') or username} (@{username})")
        if user_profile.get("bio"):
            print(f"    [OK] Bio: {user_profile.get('bio')}")
        print(f"    [OK] Public Repos: {user_profile.get('public_repos', 0)}")
        if "total_private_repos" in user_profile:
            print(f"    [OK] Private Repos: {user_profile.get('total_private_repos', 0)}")
    except GitHubAPIError as e:
        print(f"[ERROR] Failed to fetch user profile: {e}")
        sys.exit(1)

    # Fetch Repositories
    print(f"\n[*] Fetching repository list for @{username}...")
    try:
        raw_repos = client.get_user_repos(
            username=username,
            visibility=visibility,
            include_forks=include_forks
        )
    except GitHubAPIError as e:
        print(f"[ERROR] Failed to list repositories: {e}")
        sys.exit(1)

    if args.repo:
        raw_repos = [r for r in raw_repos if r.get("name", "").lower() == args.repo.lower()]
        if not raw_repos:
            print(f"[ERROR] Specific repository '{args.repo}' not found.")
            sys.exit(1)

    total_count = len(raw_repos)
    print(f"    [OK] Found {total_count} matching repositories to inspect.\n")

    if total_count == 0:
        print("No repositories found to inspect with current filters.")
        return

    analyzer = RepoAnalyzer(client)
    analyzed_reports = []

    print("[*] Inspecting repositories and extracting metrics:")
    for idx, r in enumerate(raw_repos, 1):
        repo_name = r.get("name")
        owner_name = r.get("owner", {}).get("login", username)
        print(f"    [{idx}/{total_count}] Analyzing {owner_name}/{repo_name}...", end="", flush=True)
        try:
            report = analyzer.analyze(r)
            analyzed_reports.append(report)
            fw_info = f" ({len(report.all_frameworks)} frameworks)" if report.all_frameworks else ""
            print(f" Done [{report.primary_language}{fw_info}, {report.commit_count} commits]")
        except Exception as e:
            print(f" Failed: {e}")

    # Generate Markdown Files
    print(f"\n[*] Generating markdown files into: {output_dir}...")
    generator = MarkdownGenerator(output_dir)
    generator.generate_all(user_profile, analyzed_reports)

    print(f"    [OK] Generated {len(analyzed_reports)} repository dossier files in: {output_dir / 'repos'}")
    print(f"    [OK] Generated master index in: {output_dir / 'INDEX.md'}")

    # Final rate limit check
    if client.last_rate_limit_remaining is not None:
        print(f"\n[*] GitHub API Quota remaining: {client.last_rate_limit_remaining} requests.")

    print("\n" + "=" * 65)
    print("  Inspection complete. Files are ready.")
    print("=" * 65)

if __name__ == "__main__":
    main()
