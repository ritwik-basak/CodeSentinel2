"""
embedder.py — Convert parsed code into vector embeddings using BGE-small-en-v1.5.

Three chunk types are produced per file:
  • function   — one per function; includes extracted source code
  • class      — one per class; lists its methods
  • file       — one per file; summarises imports / function / class counts

CSS and HTML files are skipped entirely.
"""

from __future__ import annotations

import os
from typing import Any

MODEL_NAME = "BAAI/bge-small-en-v1.5"
SKIP_LANGUAGES = {"css", "html"}

_model = None


# ---------------------------------------------------------------------------
# Model loader (lazy, singleton)
# ---------------------------------------------------------------------------

def _get_model():
    global _model
    if _model is None:
        print("Loading embedding model...")
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(MODEL_NAME)
    return _model


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def embed_chunks(
    parsed: dict[str, Any],
    files: dict[str, str],
) -> list[dict[str, Any]]:
    """
    Build and embed all chunks for every parsed source file.

    Parameters
    ----------
    parsed : output of ``core.parser.parse_files``
    files  : output of ``core.fetcher.fetch_repo_files``  (filename → raw content)

    Returns
    -------
    List of chunk dicts.  Every dict contains an ``embedding`` field
    (list[float] of length 384).
    """
    model = _get_model()
    chunks: list[dict[str, Any]] = []

    for filepath, parse_result in parsed.items():
        lang = parse_result["language"]
        if lang in SKIP_LANGUAGES or not parse_result["parsed"]:
            continue

        raw_content = files.get(filepath, "")
        lines = raw_content.splitlines()

        functions: list[dict] = parse_result["functions"]
        classes:   list[str]  = parse_result["classes"]
        imports:   list[str]  = parse_result["imports"]

        # Functions sorted by line for source-window extraction
        sorted_funcs = sorted(functions, key=lambda f: f["line"])
        func_lines   = [f["line"] for f in sorted_funcs]

        # Approximate class definition line numbers from raw source
        class_line_map = _find_class_lines(lines, classes, lang)

        # ── Function chunks ────────────────────────────────────────────────
        for i, func in enumerate(sorted_funcs):
            next_func_line = func_lines[i + 1] if i + 1 < len(func_lines) else None
            source = _extract_source(lines, func["line"], next_func_line)
            chunks.append({
                "chunk_id":      f"{filepath}::{func['name']}",
                "chunk_type":    "function",
                "filename":      filepath,
                "function_name": func["name"],
                "class_name":    None,
                "language":      lang,
                "line":          func["line"],
                "has_doc":       func["has_doc"],
                "text":          _function_text(filepath, func, lang, source),
                "embedding":     None,
            })

        # ── Class chunks ───────────────────────────────────────────────────
        sorted_classes = sorted(class_line_map.items(), key=lambda x: x[1])
        for j, (class_name, class_line) in enumerate(sorted_classes):
            next_class_line = sorted_classes[j + 1][1] if j + 1 < len(sorted_classes) else None
            methods = [
                f["name"] for f in functions
                if class_line < f["line"] < (next_class_line or float("inf"))
            ]
            chunks.append({
                "chunk_id":      f"{filepath}::class::{class_name}",
                "chunk_type":    "class",
                "filename":      filepath,
                "function_name": None,
                "class_name":    class_name,
                "language":      lang,
                "line":          class_line,
                "has_doc":       None,
                "text":          _class_text(filepath, class_name, lang, methods),
                "embedding":     None,
            })

        # ── File summary chunk ─────────────────────────────────────────────
        chunks.append({
            "chunk_id":      f"{filepath}::__file__",
            "chunk_type":    "file",
            "filename":      filepath,
            "function_name": None,
            "class_name":    None,
            "language":      lang,
            "line":          None,
            "has_doc":       None,
            "text":          _file_text(filepath, lang, functions, classes, imports),
            "embedding":     None,
        })

    # ── Batch embed all chunks ─────────────────────────────────────────────
    if chunks:
        texts      = [c["text"] for c in chunks]
        embeddings = model.encode(texts, show_progress_bar=True, batch_size=64)
        for chunk, emb in zip(chunks, embeddings):
            chunk["embedding"] = emb.tolist()

    return chunks


# ---------------------------------------------------------------------------
# Source extraction
# ---------------------------------------------------------------------------

def _extract_source(lines: list[str], start_line: int, next_line: int | None) -> str:
    """
    Return the raw source lines for a function starting at ``start_line``
    (1-indexed).  Stops just before ``next_line`` (or at EOF), trimming
    trailing blank lines.
    """
    start_idx = start_line - 1
    end_idx   = (next_line - 1) if next_line is not None else len(lines)

    chunk = list(lines[start_idx:end_idx])
    while chunk and not chunk[-1].strip():
        chunk.pop()

    return "\n".join(chunk)


def _find_class_lines(lines: list[str], classes: list[str], lang: str) -> dict[str, int]:
    """
    Scan raw source lines to find the 1-indexed line where each class is defined.
    Uses the first non-comment line containing ``class <ClassName>``.
    Falls back to line 1 for any class that cannot be located.
    """
    result: dict[str, int] = {}
    for name in classes:
        pattern = f"class {name}"
        for i, line in enumerate(lines, start=1):
            stripped = line.lstrip()
            # Skip comment lines
            if lang == "python" and stripped.startswith("#"):
                continue
            if lang in ("javascript", "typescript") and stripped.startswith("//"):
                continue
            if pattern in line:
                result[name] = i
                break
        if name not in result:
            result[name] = 1  # fallback — class not found in source scan
    return result


# ---------------------------------------------------------------------------
# Chunk text builders
# ---------------------------------------------------------------------------

def _function_text(filepath: str, func: dict, lang: str, source: str) -> str:
    has_doc_str = "yes" if func["has_doc"] else "no"
    return (
        f"File: {filepath}\n"
        f"Function: {func['name']} (line {func['line']})\n"
        f"Language: {lang}\n"
        f"Has documentation: {has_doc_str}\n"
        f"\n"
        f"{source}"
    )


def _class_text(filepath: str, class_name: str, lang: str, methods: list[str]) -> str:
    methods_str = ", ".join(methods) if methods else "none"
    return (
        f"File: {filepath}\n"
        f"Class: {class_name}\n"
        f"Language: {lang}\n"
        f"Methods: {methods_str}"
    )


def _file_text(
    filepath: str,
    lang: str,
    functions: list[dict],
    classes: list[str],
    imports: list[str],
) -> str:
    imports_str = ", ".join(imports) if imports else "none"
    return (
        f"File: {filepath}\n"
        f"Language: {lang}\n"
        f"Total functions: {len(functions)}\n"
        f"Total classes: {len(classes)}\n"
        f"Imports: {imports_str}"
    )
