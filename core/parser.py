"""
parser.py — Parse fetched source files into structured metadata using Tree-sitter.

Supported languages
-------------------
- Python (.py)              — functions, classes, imports, docstring detection
- JavaScript/JSX (.js/.jsx) — functions (all forms), classes, imports, JSDoc detection
- TypeScript/TSX (.ts/.tsx) — same as JavaScript
- CSS / HTML                — stored as plain text, parsed=False

Requires (Python 3.12+):
    tree-sitter>=0.25
    tree-sitter-python
    tree-sitter-javascript
    tree-sitter-typescript
"""

import os
from typing import Any

try:
    import tree_sitter_python as _tspython
    import tree_sitter_javascript as _tsjavascript
    import tree_sitter_typescript as _tstypescript
    from tree_sitter import Language, Parser as _TSParser

    _PARSERS: dict[str, _TSParser] = {
        "python":     _TSParser(Language(_tspython.language())),
        "javascript": _TSParser(Language(_tsjavascript.language())),
        "typescript": _TSParser(Language(_tstypescript.language_typescript())),
        "tsx":        _TSParser(Language(_tstypescript.language_tsx())),
    }
    _TREE_SITTER_AVAILABLE = True
except ImportError:
    _PARSERS = {}
    _TREE_SITTER_AVAILABLE = False

# ---------------------------------------------------------------------------
# Extension mappings
# ---------------------------------------------------------------------------

_TS_LANG: dict[str, str] = {
    ".py":  "python",
    ".js":  "javascript",
    ".jsx": "javascript",
    ".ts":  "typescript",
    ".tsx": "tsx",
}

# Human-readable language name written into every result dict
_DISPLAY_LANG: dict[str, str] = {
    ".py":   "python",
    ".js":   "javascript",
    ".jsx":  "javascript",
    ".ts":   "typescript",
    ".tsx":  "typescript",
    ".css":  "css",
    ".html": "html",
}

_PLAIN_TEXT_EXTS = {".css", ".html"}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_files(files: dict[str, str]) -> dict[str, Any]:
    """
    Parse a ``{filename: content}`` dict into structured per-file metadata.

    Returns
    -------
    dict mapping filename → parse result::

        {
            "language":  str,
            "parsed":    bool,
            "functions": [{"name": str, "line": int, "has_doc": bool}, ...],
            "classes":   [str, ...],
            "imports":   [str, ...],
        }
    """
    return {path: _parse_file(path, content) for path, content in files.items()}


# ---------------------------------------------------------------------------
# Per-file dispatch
# ---------------------------------------------------------------------------

def _parse_file(filepath: str, content: str) -> dict[str, Any]:
    ext = os.path.splitext(filepath)[1].lower()
    lang = _DISPLAY_LANG.get(ext, ext.lstrip("."))

    if ext in _PLAIN_TEXT_EXTS:
        return _result(lang, parsed=False)

    ts_lang = _TS_LANG.get(ext)
    if not ts_lang or not _TREE_SITTER_AVAILABLE:
        return _result(lang, parsed=False)

    try:
        parser = _PARSERS[ts_lang]
        source_bytes = content.encode("utf-8", errors="replace")
        tree = parser.parse(source_bytes)
    except Exception as exc:
        print(f"  [warn] Tree-sitter could not parse '{filepath}': {exc}")
        return _result(lang, parsed=False)

    try:
        if ts_lang == "python":
            return _parse_python(tree, source_bytes)
        else:
            return _parse_javascript(tree, source_bytes, lang)
    except Exception as exc:
        print(f"  [warn] Extraction error in '{filepath}': {exc}")
        return _result(lang, parsed=False)


def _result(language: str, parsed: bool = True, **kw) -> dict[str, Any]:
    return {
        "language":  language,
        "parsed":    parsed,
        "functions": kw.get("functions", []),
        "classes":   kw.get("classes", []),
        "imports":   kw.get("imports", []),
    }


# ---------------------------------------------------------------------------
# Python extractor
# ---------------------------------------------------------------------------

def _parse_python(tree, source_bytes: bytes) -> dict[str, Any]:
    functions: list[dict] = []
    classes:   list[str]  = []
    imports:   list[str]  = []

    def walk(node) -> None:
        t = node.type

        if t == "function_definition":
            name_node = node.child_by_field_name("name")
            if name_node:
                functions.append({
                    "name":     name_node.text.decode("utf-8", errors="replace"),
                    "line":     node.start_point[0] + 1,
                    "end_line": node.end_point[0] + 1,
                    "has_doc":  _py_has_docstring(node),
                })
            for child in node.children:
                walk(child)
            return  # children already visited above

        if t == "class_definition":
            name_node = node.child_by_field_name("name")
            if name_node:
                classes.append(name_node.text.decode("utf-8", errors="replace"))
            for child in node.children:
                walk(child)
            return

        if t == "import_statement":
            _py_collect_import(node, imports)

        if t == "import_from_statement":
            _py_collect_from_import(node, imports)

        for child in node.children:
            walk(child)

    walk(tree.root_node)

    return _result(
        "python", parsed=True,
        functions=functions,
        classes=classes,
        imports=sorted(set(imports)),
    )


def _py_has_docstring(func_node) -> bool:
    """True if the function/method body opens with a string literal."""
    body = func_node.child_by_field_name("body")
    if not body:
        return False
    named = [c for c in body.children if c.is_named]
    if not named:
        return False
    first = named[0]
    if first.type == "expression_statement":
        inner = [c for c in first.children if c.is_named]
        if inner and inner[0].type in ("string", "concatenated_string"):
            return True
    return False


def _py_collect_import(node, imports: list[str]) -> None:
    """Handle ``import x`` and ``import x as y``."""
    for child in node.children:
        if child.type == "dotted_name":
            _append_first_id(child, imports)
        elif child.type == "aliased_import":
            name = child.child_by_field_name("name")
            if name:
                _append_first_id(name, imports)


def _py_collect_from_import(node, imports: list[str]) -> None:
    """Handle ``from x.y import z``; skip relative imports."""
    module = node.child_by_field_name("module_name")
    if not module or module.type == "relative_import":
        return
    if module.type == "dotted_name":
        _append_first_id(module, imports)
    elif module.type == "identifier":
        imports.append(module.text.decode("utf-8", errors="replace"))


def _append_first_id(dotted_node, imports: list[str]) -> None:
    """Append only the top-level identifier from a dotted name node."""
    for child in dotted_node.children:
        if child.type == "identifier":
            imports.append(child.text.decode("utf-8", errors="replace"))
            return


# ---------------------------------------------------------------------------
# JavaScript / TypeScript extractor
# ---------------------------------------------------------------------------

_JS_FUNC_DECL_TYPES = {
    "function_declaration",
    "generator_function_declaration",
}

_JS_FUNC_EXPR_TYPES = {
    "arrow_function",
    "function",
    "function_expression",
    "generator_function",
}


def _parse_javascript(tree, source_bytes: bytes, lang_display: str) -> dict[str, Any]:
    functions: list[dict] = []
    classes:   list[str]  = []
    imports:   list[str]  = []

    def walk(node) -> None:
        t = node.type

        # Named function / generator declarations
        if t in _JS_FUNC_DECL_TYPES:
            name_node = node.child_by_field_name("name")
            if name_node:
                functions.append({
                    "name":     name_node.text.decode("utf-8", errors="replace"),
                    "line":     node.start_point[0] + 1,
                    "end_line": node.end_point[0] + 1,
                    "has_doc":  _js_has_jsdoc(node),
                })

        # Arrow / function expressions assigned to a variable:
        # const foo = () => {}  |  const foo = function() {}
        elif t in _JS_FUNC_EXPR_TYPES:
            parent = node.parent
            if parent and parent.type == "variable_declarator":
                name_node = parent.child_by_field_name("name")
                if name_node:
                    # JSDoc comment sits before the variable_declaration (grandparent)
                    grandparent = parent.parent
                    functions.append({
                        "name":     name_node.text.decode("utf-8", errors="replace"),
                        "line":     node.start_point[0] + 1,
                        "end_line": node.end_point[0] + 1,
                        "has_doc":  _js_has_jsdoc(grandparent) if grandparent else False,
                    })

        # Class methods
        elif t == "method_definition":
            name_node = node.child_by_field_name("name")
            if name_node:
                functions.append({
                    "name":     name_node.text.decode("utf-8", errors="replace"),
                    "line":     node.start_point[0] + 1,
                    "end_line": node.end_point[0] + 1,
                    "has_doc":  _js_has_jsdoc(node),
                })

        # Class declarations
        elif t == "class_declaration":
            name_node = node.child_by_field_name("name")
            if name_node:
                classes.append(name_node.text.decode("utf-8", errors="replace"))

        # ES module imports — keep only the package root name
        elif t == "import_statement":
            source = node.child_by_field_name("source")
            if source:
                raw = source.text.decode("utf-8", errors="replace").strip("'\"` ")
                pkg = raw.lstrip("./").split("/")[0]
                if pkg:
                    imports.append(pkg)

        for child in node.children:
            walk(child)

    walk(tree.root_node)

    return _result(
        lang_display, parsed=True,
        functions=functions,
        classes=classes,
        imports=sorted(set(imports)),
    )


def _js_has_jsdoc(node) -> bool:
    """
    True when the immediately preceding named sibling is a ``/** */`` block comment.
    Works for top-level function declarations and class methods alike.
    """
    if node is None:
        return False
    prev = node.prev_named_sibling
    if prev and prev.type == "comment":
        text = prev.text.decode("utf-8", errors="replace").lstrip()
        return text.startswith("/**")
    return False
