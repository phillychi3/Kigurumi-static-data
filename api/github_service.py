import json
import os
import subprocess
import time
import uuid
import httpx
from typing import Any, Dict


async def create_github_pr(
    file_path: str, new_data: Any, commit_message: str, pr_title: str, pr_body: str
) -> Dict[str, Any]:
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        raise Exception("GitHub token not configured")

    repo_owner = os.getenv("GITHUB_REPO_OWNER", "phillychi3")
    repo_name = os.getenv("GITHUB_REPO_NAME", "Kigurumi-static-data")

    branch_name = f"update-data-{uuid.uuid4().hex[:8]}"

    try:
        base_dir = os.path.join(os.path.dirname(__file__), "..")

        subprocess.run(["git", "checkout", "main"], cwd=base_dir, check=True)
        subprocess.run(["git", "pull", "origin", "main"], cwd=base_dir, check=True)

        subprocess.run(["git", "checkout", "-b", branch_name], cwd=base_dir, check=True)

        full_path = os.path.join(base_dir, file_path)
        with open(full_path, "w", encoding="utf-8") as f:
            json.dump(new_data, f, ensure_ascii=False, indent=2)

        subprocess.run(["git", "add", file_path], cwd=base_dir, check=True)
        subprocess.run(
            ["git", "commit", "-m", commit_message], cwd=base_dir, check=True
        )

        subprocess.run(["git", "push", "origin", branch_name], cwd=base_dir, check=True)

        time.sleep(3)

        result = subprocess.run(
            ["git", "ls-remote", "--heads", "origin", branch_name],
            cwd=base_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        if not result.stdout.strip():
            raise Exception(f"Branch {branch_name} not found on remote")

        async with httpx.AsyncClient() as client:
            headers = {
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {github_token}",
                "X-GitHub-Api-Version": "2022-11-28",
            }

            pr_data = {
                "title": pr_title,
                "head": branch_name,
                "base": "main",
                "body": pr_body,
            }

            response = await client.post(
                f"https://api.github.com/repos/{repo_owner}/{repo_name}/pulls",
                headers=headers,
                json=pr_data,
            )

            if response.status_code == 201:
                pr_info = response.json()
                return {
                    "success": True,
                    "pr_url": pr_info["html_url"],
                    "pr_number": pr_info["number"],
                    "branch_name": branch_name,
                }
            else:
                error_detail = f"GitHub API Error - Status: {response.status_code}"
                try:
                    error_response = response.json()
                    error_detail += (
                        f", Response: {json.dumps(error_response, indent=2)}"
                    )
                except Exception:
                    error_detail += f", Text: {response.text}"

                try:
                    subprocess.run(
                        ["git", "checkout", "main"], cwd=base_dir, check=False
                    )
                    subprocess.run(
                        ["git", "branch", "-D", branch_name], cwd=base_dir, check=False
                    )
                    subprocess.run(
                        ["git", "push", "origin", "--delete", branch_name],
                        cwd=base_dir,
                        check=False,
                    )
                except Exception:
                    pass

                raise Exception(f"Failed to create PR: {error_detail}")

    except subprocess.CalledProcessError as e:
        raise Exception(f"Git operation failed: {str(e)}")
    except Exception as e:
        raise Exception(f"Failed to create PR: {str(e)}")
