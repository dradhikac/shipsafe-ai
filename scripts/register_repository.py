"""CLI script to connect and register a real Git repository."""

import argparse
import os
import sys

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from shipsafe.database import SessionLocal, init_db
from shipsafe.core.repo_manager import RepositoryManager


def main():
    parser = argparse.ArgumentParser(description="Connect and register a Git repository in ShipSafe AI.")
    parser.add_argument("--url", required=True, help="GitHub repository URL (e.g. https://github.com/owner/repo)")
    parser.add_argument("--branch", default=None, help="Branch name (default: auto-detected default branch)")
    parser.add_argument("--name", default=None, help="Optional display name for repository")
    parser.add_argument("--token", default=None, help="Optional GitHub access token for private repositories")

    args = parser.parse_args()

    init_db()
    db = SessionLocal()

    print(f"\n[ShipSafe Connect] Connecting repository: {args.url}")
    print("[1/4] Validating GitHub URL format...")
    is_valid, owner, repo_name, err = RepositoryManager.validate_github_url(args.url)
    if not is_valid:
        print(f"Error: {err}", file=sys.stderr)
        sys.exit(1)

    print(f"[2/4] Fetching repository into managed workspace for {owner}/{repo_name}...")
    try:
        repo = RepositoryManager.connect_repository(
            db=db,
            url=args.url,
            branch=args.branch,
            display_name=args.name,
            token=args.token
        )
        print("[3/4] Auto-detected branch and commit...")
        print(f"      Default Branch: {repo.default_branch}")
        print(f"      Selected Branch: {repo.selected_branch}")
        print(f"      Available Branches: {', '.join(repo.available_branches or [])}")
        print(f"      Latest Commit: {repo.latest_commit_sha}")
        print(f"      Files Count: {repo.files_count}")

        print("\n[4/4] Connected successfully!")
        print(f"Repository ID: {repo.id}")
        print(f"Repository: {repo.display_name}")
        print(f"Status: NOT ANALYZED")
        print("Ready for analysis or monitoring.")
    except Exception as e:
        print(f"\n[ShipSafe Connect Error] Repository connection failed: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
