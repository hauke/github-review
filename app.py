import logging
import os
from flask import Flask, render_template, request, flash, redirect, url_for
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "WARNING").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

from github_pr import get_pr_data, get_pr_head_sha, parse_pr_url, validate_repo, ALLOWED_ORGS
from analyzer import analyze_pr
from storage import (
    save_metadata, save_review,
    load_reviews, load_review_version, list_review_versions,
    load_metadata, list_all_prs,
)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-me-in-production")

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)


@app.route("/", methods=["GET"])
def index():
    past_prs = list_all_prs()
    return render_template("index.html", allowed_orgs=ALLOWED_ORGS, past_prs=past_prs)


def _sha_unchanged(owner: str, repo: str, pr_number: int) -> bool:
    """Return True if the stored head SHA matches the current PR head SHA."""
    meta = load_metadata(owner, repo, pr_number)
    if not (meta and meta.get("head_sha")):
        return False
    try:
        return get_pr_head_sha(owner, repo, pr_number) == meta["head_sha"]
    except Exception:
        log.warning("SHA check failed for %s/%s#%d, treating as changed", owner, repo, pr_number)
        return False


def _fetch_analyze_save(owner: str, repo: str, pr_number: int) -> dict:
    """Fetch PR data from GitHub, run Claude analysis, and persist results.

    Returns the pr dict on success. Raises ValueError or RuntimeError on failure.
    """
    pr_url = f"https://github.com/{owner}/{repo}/pull/{pr_number}"
    pr = get_pr_data(pr_url)
    review, prompt = analyze_pr(pr)
    save_metadata(pr)
    save_review(owner, repo, pr_number, review, prompt, pr["head_sha"])
    return pr


@app.route("/analyze", methods=["POST"])
@limiter.limit("5 per minute; 30 per hour", deduct_when=lambda r: r.status_code == 200)
def analyze():
    pr_url = request.form.get("pr_url", "").strip()
    if not pr_url:
        flash("Please enter a PR URL.", "error")
        return redirect(url_for("index"))

    try:
        owner, repo, pr_number = parse_pr_url(pr_url)
        validate_repo(owner, repo)
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("index"))

    log.info("Analysis requested: %s/%s#%d", owner, repo, pr_number)

    if _sha_unchanged(owner, repo, pr_number):
        log.info("Cache hit for %s/%s#%d", owner, repo, pr_number)
        flash("No changes since the last review — showing existing review.", "success")
        return redirect(url_for("view_review", owner=owner, repo=repo, pr_number=pr_number))

    try:
        _fetch_analyze_save(owner, repo, pr_number)
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("index"))
    except Exception as e:
        log.exception("Analysis failed for %s/%s#%d", owner, repo, pr_number)
        flash(str(e), "error")
        return redirect(url_for("index"))

    return redirect(url_for("view_review", owner=owner, repo=repo, pr_number=pr_number))


@app.route("/review/<owner>/<repo>/<int:pr_number>/refresh", methods=["POST"])
@limiter.limit("5 per minute; 30 per hour", deduct_when=lambda r: r.status_code == 200)
def refresh_review(owner, repo, pr_number):
    if owner.lower() not in ALLOWED_ORGS:
        flash("Organisation not allowed.", "error")
        return redirect(url_for("index"))

    if _sha_unchanged(owner, repo, pr_number):
        flash("No new changes in the PR since the last review.", "success")
        return redirect(url_for("view_review", owner=owner, repo=repo, pr_number=pr_number))

    try:
        _fetch_analyze_save(owner, repo, pr_number)
    except Exception as e:
        log.exception("Analysis failed for %s/%s#%d", owner, repo, pr_number)
        flash(str(e), "error")
        return redirect(url_for("view_review", owner=owner, repo=repo, pr_number=pr_number))

    flash("Review updated with the latest changes.", "success")
    return redirect(url_for("view_review", owner=owner, repo=repo, pr_number=pr_number))


@app.route("/review/<owner>/<repo>/<int:pr_number>")
def view_review(owner, repo, pr_number):
    if owner.lower() not in ALLOWED_ORGS:
        flash("Organisation not allowed.", "error")
        return redirect(url_for("index"))
    meta = load_metadata(owner, repo, pr_number)
    if not meta:
        flash("No stored review found for that PR.", "error")
        return redirect(url_for("index"))

    versions = list_review_versions(owner, repo, pr_number)
    version_id = request.args.get("version")
    if version_id:
        if not any(v["version_id"] == version_id for v in versions):
            flash("Review version not found.", "error")
            return redirect(url_for("view_review", owner=owner, repo=repo, pr_number=pr_number))
        stored = load_review_version(owner, repo, pr_number, version_id)
    else:
        stored = load_reviews(owner, repo, pr_number)
        version_id = versions[0]["version_id"] if versions else None

    # Build a minimal pr dict from metadata (no live GitHub fetch needed)
    pr = {
        "owner": meta["owner"],
        "repo": meta["repo"],
        "pr_number": meta["pr_number"],
        "title": meta["title"],
        "author": meta["author"],
        "base_branch": meta["base_branch"],
        "head_branch": meta["head_branch"],
        "files": [None] * meta["file_count"],  # only used for len()
    }
    return render_template(
        "review.html",
        allowed_orgs=ALLOWED_ORGS,
        pr=pr,
        review=stored["ai"] or "",
        prompt=stored.get("prompt") or "",
        meta=meta,
        versions=versions,
        current_version_id=version_id,
    )



if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1")
