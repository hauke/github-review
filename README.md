# GitHub PR Reviewer

A Python web app that analyzes GitHub pull requests using Claude and stores the reviews locally.

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
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

```bash
ln -s /etc/nginx/sites-available/pr-reviewer /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
certbot --nginx -d your.domain.com
```

Both `listen 80` and `listen [::]:80` are required — without the IPv6 line, Let's Encrypt's HTTP challenge will fail on dual-stack servers.

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
