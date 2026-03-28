# ── Stage 1: Base image ───────────────────────────────────────────────────
# We start from an official Python 3.11 image, "slim" variant = smaller size
FROM python:3.11-slim

# ── Stage 2: Set working directory ────────────────────────────────────────
# All commands from here run inside /app inside the container
WORKDIR /app

# ── Stage 3: Install system dependencies ──────────────────────────────────
# tree-sitter needs a C compiler to build its native extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# ── Stage 4: Install Python dependencies ──────────────────────────────────
# Copy requirements first (before copying code) so Docker can cache this
# layer — if only your code changes, it won't reinstall all packages again
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Stage 5: Copy project code ────────────────────────────────────────────
# Copy everything except what's in .dockerignore
COPY . .

# ── Stage 6: Expose port ──────────────────────────────────────────────────
# Tell Docker/Railway that this container listens on port 8001
EXPOSE 8001

# ── Stage 7: Start command ────────────────────────────────────────────────
# This runs when the container starts — same as running `python run.py` locally
CMD ["python", "run.py"]
