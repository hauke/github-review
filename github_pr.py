import logging
import os
import re
import requests

log = logging.getLogger(__name__)

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
ALLOWED_ORGS = [
    o.strip().lower()
    for o in os.environ.get("ALLOWED_ORGS", "").split(",")
    if o.strip()
]

API_BASE = "https://api.github.com"


def _headers():
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def parse_pr_url(url: str) -> tuple[str, str, int]:
    """Parse a GitHub PR URL and return (owner, repo, pr_number)."""
    pattern = r"github\.com/([^/]+)/([^/]+)/pull/(\d+)"
    match = re.search(pattern, url)
    if not match:
        raise ValueError(f"Invalid GitHub PR URL: {url}")
    owner, repo, pr_number = match.group(1), match.group(2), int(match.group(3))
    return owner, repo, pr_number


def validate_repo(owner: str, repo: str):
    """Raise if the repo's organisation is not in the allowed list."""
    if not ALLOWED_ORGS:
        raise RuntimeError("ALLOWED_ORGS is not configured.")
    if owner.lower() not in ALLOWED_ORGS:
        allowed = ", ".join(ALLOWED_ORGS)
        raise ValueError(
            f"Organisation '{owner}' is not allowed. Allowed: {allowed}."
        )


def get_pr_head_sha(owner: str, repo: str, pr_number: int) -> str:
    """Fetch only the head commit SHA of a PR (lightweight check)."""
    resp = requests.get(
        f"{API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}",
        headers=_headers(),
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["head"]["sha"]


def get_pr_data(url: str) -> dict:
    """Fetch PR metadata, file diffs, and existing comments from GitHub."""
    owner, repo, pr_number = parse_pr_url(url)
    validate_repo(owner, repo)

    pr_resp = requests.get(
        f"{API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}",
        headers=_headers(),
        timeout=15,
    )
    pr_resp.raise_for_status()
    pr = pr_resp.json()
    log.debug("PR metadata: title=%r author=%r head=%s base=%s",
              pr["title"], pr["user"]["login"], pr["head"]["ref"], pr["base"]["ref"])

    files_resp = requests.get(
        f"{API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/files",
        headers=_headers(),
        params={"per_page": 100},
        timeout=15,
    )
    files_resp.raise_for_status()
    files = files_resp.json()
    log.debug("Files: %d changed — %s", len(files), [f["filename"] for f in files])

    # Inline review comments — skip outdated ones (position is None)
    review_comments_resp = requests.get(
        f"{API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/comments",
        headers=_headers(),
        params={"per_page": 100},
        timeout=15,
    )
    review_comments_resp.raise_for_status()
    all_review = review_comments_resp.json()
    review_comments = [
        {
            "type": "inline",
            "author": c["user"]["login"],
            "path": c["path"],
            "position": c["position"],
            "diff_hunk": c.get("diff_hunk", ""),
            "body": c["body"],
        }
        for c in all_review
        if c.get("position") is not None
    ]
    log.debug("Inline review comments: %d total, %d active (non-outdated)",
              len(all_review), len(review_comments))

    # General issue-level comments (never outdated)
    issue_comments_resp = requests.get(
        f"{API_BASE}/repos/{owner}/{repo}/issues/{pr_number}/comments",
        headers=_headers(),
        params={"per_page": 100},
        timeout=15,
    )
    issue_comments_resp.raise_for_status()
    issue_comments = [
        {
            "type": "general",
            "author": c["user"]["login"],
            "body": c["body"],
        }
        for c in issue_comments_resp.json()
    ]
    log.debug("General comments: %d", len(issue_comments))

    result = {
        "owner": owner,
        "repo": repo,
        "pr_number": pr_number,
        "head_sha": pr["head"]["sha"],
        "title": pr["title"],
        "body": pr.get("body") or "",
        "author": pr["user"]["login"],
        "base_branch": pr["base"]["ref"],
        "head_branch": pr["head"]["ref"],
        "files": [
            {
                "filename": f["filename"],
                "status": f["status"],
                "additions": f["additions"],
                "deletions": f["deletions"],
                "patch": f.get("patch", ""),
            }
            for f in files
        ],
        "comments": review_comments + issue_comments,
    }
    log.debug("PR data assembled: %d files, %d comments, head_sha=%s",
              len(result["files"]), len(result["comments"]), result["head_sha"][:7])
    return result
