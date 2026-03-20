import json
from datetime import datetime, timezone
from pathlib import Path

REVIEWS_DIR = Path("reviews")


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


def save_ai_review(owner: str, repo: str, pr_number: int, text: str):
    d = _pr_dir(owner, repo, pr_number)
    d.mkdir(parents=True, exist_ok=True)
    (d / "ai_review.md").write_text(text, encoding="utf-8")


def load_reviews(owner: str, repo: str, pr_number: int) -> dict:
    d = _pr_dir(owner, repo, pr_number)
    ai_path = d / "ai_review.md"
    ai = ai_path.read_text(encoding="utf-8") if ai_path.exists() else None
    return {"ai": ai}


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
