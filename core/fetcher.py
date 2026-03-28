import os
from github import Github, GithubException

SUPPORTED_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".css": "css",
    ".html": "html",
}

SKIP_DIRS = {"node_modules", ".git", "dist", "build", "__pycache__"}

MAX_FILE_SIZE_BYTES = 100 * 1024  # 100 KB

README_NAMES = {"README.md", "readme.md", "README"}


def fetch_repo_files(repo_url: str, github_token: str) -> tuple[dict[str, str], dict[str, int]]:
    """
    Fetch all supported source files from a public or private GitHub repository.

    Args:
        repo_url:     Full GitHub URL, e.g. "https://github.com/owner/repo"
        github_token: Personal access token for the GitHub API

    Returns:
        files:     dict mapping relative file path → file content (str)
        breakdown: dict mapping language name → number of files detected
    """
    repo_path = _parse_repo_path(repo_url)

    g = Github(github_token)
    repo = g.get_repo(repo_path)

    files: dict[str, str] = {}
    language_counts: dict[str, int] = {}

    _walk_contents(repo, "", files, language_counts)

    return files, language_counts


def _parse_repo_path(url: str) -> str:
    """Extract 'owner/repo' from a GitHub URL."""
    url = url.rstrip("/")
    if url.startswith("https://github.com/"):
        return url[len("https://github.com/"):]
    if url.startswith("http://github.com/"):
        return url[len("http://github.com/"):]
    if url.startswith("github.com/"):
        return url[len("github.com/"):]
    # Assume it's already in owner/repo format
    return url


def _is_skipped_path(path: str) -> bool:
    """Return True if any path segment is in the skip list."""
    parts = path.replace("\\", "/").split("/")
    return any(part in SKIP_DIRS for part in parts)


def _walk_contents(repo, path: str, files: dict, language_counts: dict) -> None:
    """Recursively walk repository contents and collect matching files."""
    try:
        contents = repo.get_contents(path)
    except GithubException as exc:
        print(f"  [warn] Could not read path '{path}': {exc.status} {exc.data}")
        return

    for item in contents:
        if _is_skipped_path(item.path):
            continue

        if item.type == "dir":
            _walk_contents(repo, item.path, files, language_counts)
            continue

        _, ext = os.path.splitext(item.name)
        ext = ext.lower()

        is_readme = item.name in README_NAMES
        if not is_readme and ext not in SUPPORTED_EXTENSIONS:
            continue

        if item.size > MAX_FILE_SIZE_BYTES:
            print(f"  [skip] {item.path} ({item.size // 1024} KB > 100 KB limit)")
            continue

        try:
            content = item.decoded_content.decode("utf-8", errors="replace")
        except (GithubException, AssertionError) as exc:
            print(f"  [warn] Could not decode {item.path}: {exc}")
            continue

        if is_readme:
            files["__readme__"] = content
        else:
            files[item.path] = content
            lang = SUPPORTED_EXTENSIONS[ext]
            language_counts[lang] = language_counts.get(lang, 0) + 1


def detect_primary_language(language_counts: dict[str, int]) -> str:
    """Return the language with the highest file count, or 'unknown'."""
    if not language_counts:
        return "unknown"
    return max(language_counts, key=language_counts.__getitem__)
