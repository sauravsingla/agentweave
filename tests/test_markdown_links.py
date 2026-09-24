"""Offline path checks for Markdown links, not a complete Markdown parser."""

import os
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

import pytest


ROOT = Path(__file__).resolve().parents[1]
# Inline destinations (including images) and reference definitions; titles are optional.
DESTINATION = r'(?:<([^>\n]+)>|([^\s)]+))(?:\s+["\'][^\n]*?["\'])?'
LINKS = re.compile(r"\]\(\s*" + DESTINATION + r"\s*\)")
REFERENCES = re.compile(r"^ {0,3}\[[^\]\n]+\]:\s*" + DESTINATION, re.MULTILINE)


def markdown_files(root):
    for directory, dirs, files in os.walk(root):
        dirs[:] = sorted(
            d
            for d in dirs
            if not d.startswith(".")
            and d not in {"build", "dist", "node_modules", "__pycache__"}
            and not d.endswith(".egg-info")
        )
        yield from (Path(directory) / name for name in sorted(files) if name.endswith(".md"))


def broken_links(document, root):
    text = document.read_text(encoding="utf-8")
    # Code examples are not rendered links. Retain newlines for useful line numbers.
    text = re.sub(
        r"^ {0,3}(`{3,}|~{3,})[^\n]*\n.*?^ {0,3}\1\s*$",
        lambda m: "\n" * m.group().count("\n"),
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    text = re.sub(r"(`+).*?\1", lambda m: " " * len(m.group()), text)
    failures = []
    for pattern in (LINKS, REFERENCES):
        for match in pattern.finditer(text):
            target = match.group(1) or match.group(2)
            url = urlsplit(target)
            if url.scheme or url.netloc or not url.path or url.path.startswith("/"):
                continue
            path = document.parent / unquote(url.path)
            if path.exists():
                continue
            # Jekyll renders docs/*.md as *.html; require the source to exist.
            if path.suffix == ".html" and path.resolve().is_relative_to(root / "docs"):
                if path.with_suffix(".md").is_file():
                    continue
            line = text[: match.start()].count("\n") + 1
            failures.append(f"{document.relative_to(root)}:{line}: {target}")
    return failures


def test_repository_markdown_links():
    failures = [failure for doc in markdown_files(ROOT) for failure in broken_links(doc, ROOT)]
    assert not failures, "Broken repository-relative links:\n" + "\n".join(failures)


def test_markdown_discovery(tmp_path):
    for name in (
        "README.md",
        "CONTRIBUTING.md",
        "docs/nested/page.md",
        "examples/README.md",
        ".venv/no.md",
    ):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    assert {p.relative_to(tmp_path).as_posix() for p in markdown_files(tmp_path)} == {
        "README.md",
        "CONTRIBUTING.md",
        "docs/nested/page.md",
        "examples/README.md",
    }


@pytest.mark.parametrize(
    "link",
    [
        "[file](../existing.txt#section)",
        "[directory](../docs/)",
        "![image](../existing.txt)",
        "[space](<../with space.txt>)",
        '[encoded](../with%20space.txt "title")',
        "[ref]: ../existing.txt",
        "[external](https://invalid.example/missing)",
        "[mail](mailto:test@example.com)",
        "[anchor](#missing)",
        "![external](//invalid.example/image.png)",
        "`[code](missing.txt)`",
        "```md\n[code](missing.txt)\n```",
        "~~~md\n[code](missing.txt)\n~~~",
        "[site](page.html)",
    ],
)
def test_valid_or_ignored_links(tmp_path, link):
    docs = tmp_path / "docs"
    docs.mkdir()
    for name in ("existing.txt", "with space.txt", "docs/page.md"):
        (tmp_path / name).touch()
    document = docs / "README.md"
    document.write_text(link, encoding="utf-8")
    assert broken_links(document, tmp_path) == []


@pytest.mark.parametrize(
    "link", ["[broken](missing.py)", "[ref]: missing.py", "![image](missing.py)"]
)
def test_broken_target_reports_document_and_path(tmp_path, link):
    document = tmp_path / "README.md"
    document.write_text("# Heading\n" + link, encoding="utf-8")
    assert broken_links(document, tmp_path) == ["README.md:2: missing.py"]


def test_missing_generated_page_is_not_ignored(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    document = docs / "README.md"
    document.write_text("[missing](absent.html)", encoding="utf-8")
    assert broken_links(document, tmp_path)
