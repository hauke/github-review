import json
import re
from datetime import datetime, timezone
from pathlib import Path

REVIEWS_DIR = Path("reviews")

_VERSION_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{6})_([0-9a-f]{7})$")


def _pr_dir(owner: str, repo: str, pr_number: int) -> Path:
    return REVIEWS_DIR / f"{owner}_{repo}_{pr_number}"


def save_metadata(pr: dict):
    d = _pr_dir(pr["owner"], pr["repo"], pr["pr_number"])
    d.mkdir(parents=True, exist_ok=True)
    meta = {
        "owner": pr["owner"],
        "repo": pr["repo"],
        "pr_number": pr["pr_number"],
        "title": pr["title"],
        "author": pr["author"],
        "base_branch": pr["base_branch"],
        "head_branch": pr["head_branch"],
        "head_sha": pr.get("head_sha", ""),
        "file_count": len(pr["files"]),
        "pr_url": f"https://github.com/{pr['owner']}/{pr['repo']}/pull/{pr['pr_number']}",
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
    }
    (d / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


def save_review(owner: str, repo: str, pr_number: int, review_text: str, prompt_text: str, sha: str):
    """Save a versioned review in a subdirectory named {timestamp}_{sha7}/."""
    pr_dir = _pr_dir(owner, repo, pr_number)
    pr_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%S")
    vdir = pr_dir / f"{ts}_{sha[:7]}"
    vdir.mkdir(exist_ok=True)
    (vdir / "ai_review.md").write_text(review_text, encoding="utf-8")
    (vdir / "prompt.md").write_text(prompt_text, encoding="utf-8")


def list_review_versions(owner: str, repo: str, pr_number: int) -> list[dict]:
    """Return all versioned reviews for a PR, sorted newest-first."""
    pr_dir = _pr_dir(owner, repo, pr_number)
    if not pr_dir.exists():
        return []
    versions = []
    for entry in pr_dir.iterdir():
        if not entry.is_dir():
            continue
        m = _VERSION_RE.match(entry.name)
        if not m:
            continue
        ts_str, sha7 = m.group(1), m.group(2)
        ts = datetime.strptime(ts_str, "%Y-%m-%dT%H%M%S").replace(tzinfo=timezone.utc)
        versions.append({
            "version_id": entry.name,
            "sha7": sha7,
            "timestamp": ts.strftime("%Y-%m-%d %H:%M") + " UTC",
        })
    versions.sort(key=lambda v: v["version_id"], reverse=True)
    return versions


def load_review_version(owner: str, repo: str, pr_number: int, version_id: str) -> dict:
    """Load a specific review version by its version_id."""
    vdir = _pr_dir(owner, repo, pr_number) / version_id
    ai_path = vdir / "ai_review.md"
    return {"ai": ai_path.read_text(encoding="utf-8") if ai_path.exists() else None}


def load_reviews(owner: str, repo: str, pr_number: int) -> dict:
    """Return the most recent review. Falls back to root-level files for old installs."""
    versions = list_review_versions(owner, repo, pr_number)
    if versions:
        return load_review_version(owner, repo, pr_number, versions[0]["version_id"])
    # Backward compat: pre-versioning installs wrote ai_review.md at the PR dir root
    ai_path = _pr_dir(owner, repo, pr_number) / "ai_review.md"
    return {"ai": ai_path.read_text(encoding="utf-8") if ai_path.exists() else None}


def load_metadata(owner: str, repo: str, pr_number: int) -> dict | None:
    meta_path = _pr_dir(owner, repo, pr_number) / "metadata.json"
    if not meta_path.exists():
        return None
    return json.loads(meta_path.read_text(encoding="utf-8"))


def list_all_prs() -> list[dict]:
    """Return all stored PRs sorted by most recently analyzed."""
    if not REVIEWS_DIR.exists():
        return []
    result = []
    for entry in REVIEWS_DIR.iterdir():
        if not entry.is_dir():
            continue
        meta_path = entry / "metadata.json"
        if not meta_path.exists():
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        result.append(meta)
    result.sort(key=lambda m: m.get("analyzed_at", ""), reverse=True)
    return result
