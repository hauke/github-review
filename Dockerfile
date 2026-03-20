FROM python:3.13-slim

WORKDIR /app

# Install dependencies first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY analyzer.py app.py github_pr.py storage.py ./
COPY templates/ templates/

# Create a non-root user and give it ownership of the reviews volume
RUN adduser --disabled-password --no-create-home appuser \
    && mkdir -p reviews \
    && chown appuser:appuser reviews

VOLUME ["/app/reviews"]

USER appuser

EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120", "app:app"]
