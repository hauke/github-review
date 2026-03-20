# GitHub PR Reviewer

A Python web app that analyzes GitHub pull requests using Claude and optionally posts the review as a PR comment.

## Features

- Paste any PR URL and get an instant AI code review
- Restricted to a single configured repository
- Review covers correctness, security, code quality, best practices, and performance
- Skips re-analysis if the PR hasn't changed since the last review

## Setup

**1. Install dependencies**

```bash
pip install -r requirements.txt
```

**2. Configure environment**

```bash
cp .env.example .env
```

Edit `.env`:

| Variable | Description |
|---|---|
| `GITHUB_TOKEN` | Personal access token with read-only access (`public_repo` or `repo` scope) |
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `ALLOWED_ORGS` | Comma-separated list of GitHub organisations whose PRs are allowed, e.g. `myorg,anotheraporg` |
| `FLASK_SECRET_KEY` | Random secret string for Flask sessions |

**3. Run**

```bash
python app.py
```

Open [http://localhost:5000](http://localhost:5000).

## Usage

1. Paste a pull request URL (e.g. `https://github.com/myorg/myrepo/pull/42`)
2. Click **Analyze PR**
3. Read Claude's review — it includes a summary, issues by severity, suggestions, and a verdict
4. Re-submitting the same PR URL will reuse the existing review if the PR hasn't changed

## Project Structure

```
├── app.py           # Flask routes
├── github_pr.py     # GitHub API: fetch PR data
├── analyzer.py      # Claude integration
├── storage.py       # Save/load reviews from disk
├── templates/
│   ├── index.html   # PR list and submission form
│   └── review.html  # Review display
├── requirements.txt
└── .env.example
```
