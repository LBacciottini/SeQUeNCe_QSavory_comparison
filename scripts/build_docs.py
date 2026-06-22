#!/usr/bin/env python3
"""Generate API reference pages and build the MkDocs site."""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
from datetime import datetime, timezone


ROOT = pathlib.Path(__file__).resolve().parents[1]
GENERATED = ROOT / "docs" / "generated"
TEMPLATE = ROOT / "scripts" / "templates" / "api_page.md.tmpl"
PYTHON_API = GENERATED / "api" / "python.md"
JULIA_API = GENERATED / "api" / "julia.md"
MANIFEST = GENERATED / "manifest.json"


PYTHON_MODULES = [
    "sequence_qsavory_comparison.common.config",
    "sequence_qsavory_comparison.common.models",
    "sequence_qsavory_comparison.common.outputs",
    "sequence_qsavory_comparison.common.plotting",
    "sequence_qsavory_comparison.common.validation",
    "sequence_qsavory_comparison.cli.jobs",
    "sequence_qsavory_comparison.cli.run_batch",
    "sequence_qsavory_comparison.cli.run_sweep",
    "sequence_qsavory_comparison.sequence.mapping",
    "sequence_qsavory_comparison.sequence.simulation",
    "sequence_qsavory_comparison.sequence.elementary",
]


def rel(path: pathlib.Path) -> str:
    return path.relative_to(ROOT).as_posix()


def render_template(**values: str) -> str:
    rendered = TEMPLATE.read_text(encoding="utf-8")
    for key, value in values.items():
        rendered = rendered.replace("{{" + key + "}}", value)
    return rendered.rstrip() + "\n"


def slug(value: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in value.lower()).strip("-")


def clean_generated() -> None:
    if GENERATED.exists():
        shutil.rmtree(GENERATED)
    (GENERATED / "api").mkdir(parents=True, exist_ok=True)


def write_generated_index() -> None:
    (GENERATED / "index.md").write_text(
        "\n".join(
            [
                "# Generated Documentation",
                "",
                "This section is rebuilt by `scripts/build_docs.py` from source docstrings and generator templates.",
                "",
                "- [API Reference](api/index.md)",
                "- [Python API](api/python.md)",
                "- [Julia API](api/julia.md)",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (GENERATED / "api" / "index.md").write_text(
        "\n".join(
            [
                "# Generated API Reference",
                "",
                "These pages are generated from the curated Python module list and exported Julia docstrings.",
                "",
                "- [Python API](python.md)",
                "- [Julia API](julia.md)",
                "",
            ]
        ),
        encoding="utf-8",
    )


def write_python_api() -> None:
    index_lines = []
    body_lines = []
    for module in PYTHON_MODULES:
        anchor = "module-" + slug(module)
        index_lines.append(f"- [`{module}`](#{anchor})")
        body_lines.extend(
            [
                f'<a id="{anchor}"></a>',
                f"## `{module}`",
                "",
                f"::: {module}",
                "",
            ]
        )
    PYTHON_API.write_text(
        render_template(
            title="Python API",
            language="Python",
            source_summary="Selected public modules in `sequence_qsavory_comparison`.",
            intro=(
                "The Python API page is generated with `mkdocstrings` from the curated module list "
                "in `scripts/build_docs.py`."
            ),
            index="\n".join(index_lines),
            body="\n".join(body_lines).rstrip(),
        ),
        encoding="utf-8",
    )


def run_julia_api() -> None:
    cmd = [
        "julia",
        "--project=julia/SeQUeNCeQSavoryComparison",
        "scripts/generate_julia_api.jl",
        str(JULIA_API),
        str(TEMPLATE),
    ]
    subprocess.run(cmd, cwd=ROOT, check=True)


def write_manifest() -> None:
    manifest = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator": rel(pathlib.Path(__file__).resolve()),
        "template": rel(TEMPLATE),
        "outputs": {
            "index": rel(GENERATED / "index.md"),
            "api_index": rel(GENERATED / "api" / "index.md"),
            "python_api": rel(PYTHON_API),
            "julia_api": rel(JULIA_API),
        },
        "python_modules": PYTHON_MODULES,
        "julia_project": "julia/SeQUeNCeQSavoryComparison",
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_mkdocs() -> None:
    env = os.environ.copy()
    python_path = str(ROOT / "python" / "src")
    env["PYTHONPATH"] = python_path + os.pathsep + env.get("PYTHONPATH", "")
    subprocess.run([sys.executable, "-m", "mkdocs", "build", "--strict"], cwd=ROOT, env=env, check=True)


def main() -> None:
    clean_generated()
    write_generated_index()
    write_python_api()
    run_julia_api()
    write_manifest()
    run_mkdocs()


if __name__ == "__main__":
    main()
