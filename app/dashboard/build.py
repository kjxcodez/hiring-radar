"""Dashboard generator for hiring-radar.

Produces a fully static, self-contained single-HTML dashboard by compiling
individual templates, stylesheets, and scripts, then embedding the company database.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
import orjson

from app.models import Company


def resolve_includes(text: str, base_dir: Path, _chain: tuple[str, ...] = ()) -> str:
    """Recursively resolve '## include <relative/path>' directives.

    Args:
        text: The template text containing include directives.
        base_dir: The base directory to resolve relative paths against.
        _chain: The current stack of file paths to detect circular dependencies.

    Returns:
        The fully resolved text content with all includes recursively substituted.
    """
    if len(_chain) > 20:
        raise ValueError(f"Exceeded maximum include recursion depth of 20. Chain: {' -> '.join(_chain)}")

    lines = []
    # Pattern to match: optional spaces + ## + optional spaces + include + whitespace + path
    pattern = re.compile(r"^(\s*)##\s*include\s+(.+)$")

    for line in text.splitlines():
        match = pattern.match(line)
        if match:
            indent = match.group(1)
            include_path_str = match.group(2).strip()
            target_path = (base_dir / include_path_str).resolve()

            if not target_path.exists():
                referencing_file = _chain[-1] if _chain else "root template"
                raise FileNotFoundError(
                    f"Included file '{include_path_str}' not found. "
                    f"Referenced from '{referencing_file}' (resolved path: {target_path})"
                )

            canonical_path_str = str(target_path)
            if canonical_path_str in _chain:
                cycle = " -> ".join(_chain) + f" -> {canonical_path_str}"
                raise ValueError(f"Circular dependency detected in includes: {cycle}")

            content = target_path.read_text(encoding="utf-8")
            resolved_content = resolve_includes(content, base_dir, _chain + (canonical_path_str,))

            # Indent all lines of the resolved file to match the reference line's indentation
            if indent:
                indented_lines = [indent + l if l else l for l in resolved_content.splitlines()]
                lines.append("\n".join(indented_lines))
            else:
                lines.append(resolved_content)
        else:
            lines.append(line)

    return "\n".join(lines)


def build_dashboard(input_path: Path, output_path: Path) -> None:
    """Build a static self-contained HTML dashboard from the local database.

    Loads the database JSON file, compiles the HTML template from the source
    components in app/dashboard/src/, serializes the Company objects, embeds
    them directly into the output, and writes the output.
    """
    if not input_path.exists():
        raise FileNotFoundError(
            f"Input database not found at {input_path}. Please run discovery first."
        )

    try:
        raw_data = orjson.loads(input_path.read_bytes())
        companies = [Company.model_validate(c) for c in raw_data]
    except Exception as exc:
        raise ValueError(f"Failed to load or validate database at {input_path}: {exc}") from exc

    # Locate source directories
    dashboard_dir = Path(__file__).parent
    src_root = dashboard_dir / "src"
    root_template_path = src_root / "dashboard.htmlx"

    if not root_template_path.exists():
        raise FileNotFoundError(f"Root template dashboard.htmlx not found at {root_template_path}")

    # Compile the HTML template by recursively resolving includes
    try:
        template_content = root_template_path.read_text(encoding="utf-8")
        compiled_html = resolve_includes(template_content, src_root, (str(root_template_path.resolve()),))
    except Exception as exc:
        raise ValueError(f"Failed to compile dashboard template: {exc}") from exc

    # Serialize companies to JSON safely.
    # Note: Pydantic v2 mode='json' converts datetime objects to strings.
    serialized_list = [c.model_dump(mode="json") for c in companies]
    embedded_json = json.dumps(serialized_list, ensure_ascii=False)

    # Embed inside HTML template
    html_content = compiled_html.replace("__COMPANIES_JSON_PLACEHOLDER__", embedded_json)

    # Ensure parent directories of output exist
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_content, encoding="utf-8")
