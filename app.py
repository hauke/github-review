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
    save_metadata, save_ai_review,
    load_reviews, load_metadata, list_all_prs,
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

    # Skip analysis if the PR head commit hasn't changed since the last review
    meta = load_metadata(owner, repo, pr_number)
    if meta and meta.get("head_sha"):
        try:
            current_sha = get_pr_head_sha(owner, repo, pr_number)
            if current_sha == meta["head_sha"]:
                log.info("Cache hit for %s/%s#%d (sha %s)", owner, repo, pr_number, current_sha[:7])
                flash("No changes since the last review — showing existing review.", "success")
                return redirect(url_for("view_review", owner=owner, repo=repo, pr_number=pr_number))
            log.info("SHA changed for %s/%s#%d, running fresh analysis", owner, repo, pr_number)
        except Exception:
            log.warning("SHA check failed for %s/%s#%d, falling through to fresh analysis", owner, repo, pr_number)

    try:
        pr = get_pr_data(pr_url)
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("index"))
    except Exception as e:
        log.exception("Failed to fetch PR data for %s", pr_url)
        flash(f"Failed to fetch PR: {e}", "error")
        return redirect(url_for("index"))

    try:
        review = analyze_pr(pr)
    except Exception as e:
        log.exception("Claude analysis failed for %s/%s#%d", owner, repo, pr_number)
        flash(f"Claude analysis failed: {e}", "error")
        return redirect(url_for("index"))

    save_metadata(pr)
    save_ai_review(pr["owner"], pr["repo"], pr["pr_number"], review)
    stored = load_reviews(pr["owner"], pr["repo"], pr["pr_number"])

    return render_template(
        "review.html",
        allowed_orgs=ALLOWED_ORGS,
        pr=pr,
        review=review,
        stored=stored,
    )


@app.route("/review/<owner>/<repo>/<int:pr_number>")
def view_review(owner, repo, pr_number):
    if owner.lower() not in ALLOWED_ORGS:
        flash("Organisation not allowed.", "error")
        return redirect(url_for("index"))
    meta = load_metadata(owner, repo, pr_number)
    if not meta:
        flash("No stored review found for that PR.", "error")
        return redirect(url_for("index"))
    stored = load_reviews(owner, repo, pr_number)
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
        stored=stored,
        meta=meta,
    )



if __name__ == "__main__":
    app.run(debug=True)
