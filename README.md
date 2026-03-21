# GitHub PR Reviewer

A Python web app that analyzes GitHub pull requests using Claude and stores the reviews locally.

## Features

- Paste any PR URL and get an instant AI code review
- Restricted to configured GitHub organisations
- Review covers correctness, security, code quality, best practices, and performance
- Skips re-analysis if the PR hasn't changed since the last review (head SHA check)
- Refresh button on the review page triggers a new analysis when the PR has new commits
- Full review history per PR — switch between past reviews by SHA and date
- Prompt sent to Claude is stored and viewable for debugging

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

| Variable | Required | Description |
|---|---|---|
| `GITHUB_TOKEN` | Yes | Personal access token with read-only access (`public_repo` or `repo` scope) |
| `ANTHROPIC_API_KEY` | Yes | Your Anthropic API key |
| `ALLOWED_ORGS` | Yes | Comma-separated list of GitHub organisations whose PRs are allowed, e.g. `myorg,anotheraporg` |
| `FLASK_SECRET_KEY` | Yes | Random secret string for Flask sessions |
| `CLAUDE_MODEL` | No | Model to use (default: `claude-sonnet-4-6`) |
| `CLAUDE_MAX_TOKENS` | No | Maximum tokens in the review output (default: `8192`) |
| `MAX_PROMPT_CHARS` | No | Prompt size cap before truncation (default: `120000`) |
| `LOG_LEVEL` | No | `WARNING` (default), `INFO` (token counts), `DEBUG` (verbose) |
| `FLASK_DEBUG` | No | Set to `1` to enable Flask debug mode locally (never use in production) |

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
5. Use the **Refresh review** button on the review page to re-analyze when new commits have been pushed
6. If multiple reviews exist for a PR, use the version dropdown (SHA + date) to browse history
7. Expand **Show prompt sent to Claude** at the bottom of the review page to inspect the exact input used

## Deployment (Debian 13)

```bash
apt install -y docker.io docker-cli
systemctl enable --now docker

# copy files, create .env, then:
docker build -t pr-reviewer .
mkdir -p /opt/pr-reviewer/reviews && chown 1000:1000 /opt/pr-reviewer/reviews

docker run -d \
  --name pr-reviewer \
  --restart unless-stopped \
  --env-file .env \
  -v /opt/pr-reviewer/reviews:/app/reviews \
  -p 127.0.0.1:8000:8000 \
  pr-reviewer
```

Note: Debian 13 ships `docker.io` (daemon) and `docker-cli` (client) as separate packages — both are required.

### nginx + TLS

```bash
apt install -y nginx certbot python3-certbot-nginx
```

`/etc/nginx/sites-available/pr-reviewer`:

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name your.domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_read_timeout 150s;
        proxy_connect_timeout 10s;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
ln -s /etc/nginx/sites-available/pr-reviewer /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
certbot --nginx -d your.domain.com
```

Both `listen 80` and `listen [::]:80` are required — without the IPv6 line, Let's Encrypt's HTTP challenge will fail on dual-stack servers.

`proxy_read_timeout 150s` is necessary because Claude API responses can take over 60 seconds; nginx's default of 60s would cause a 504 before gunicorn finishes.

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
