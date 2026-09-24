from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_markdown_links.py"
SPEC = importlib.util.spec_from_file_location("check_markdown_links", MODULE_PATH)
assert SPEC and SPEC.loader
check_markdown_links = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_markdown_links)


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_valid_relative_links_pass(tmp_path: Path):
    _write(tmp_path / "README.md", "[docs](docs/guide.md) [dir](docs/)")
    _write(tmp_path / "CONTRIBUTING.md", "[readme](README.md)")
    _write(tmp_path / "docs" / "guide.md", "[back](../README.md)")
    broken = check_markdown_links.find_broken_links(tmp_path)
    assert broken == []


def test_broken_relative_link_is_reported(tmp_path: Path):
    _write(tmp_path / "README.md", "See [missing](docs/does-not-exist.md).")
    _write(tmp_path / "CONTRIBUTING.md", "ok")
    _write(tmp_path / "docs" / "guide.md", "ok")
    broken = check_markdown_links.find_broken_links(tmp_path)
    assert len(broken) == 1
    assert broken[0].source == Path("README.md")
    assert "docs/does-not-exist.md" in broken[0].target
    message = broken[0].format()
    assert "README.md" in message
    assert "docs/does-not-exist.md" in message


def test_external_and_anchor_links_are_ignored(tmp_path: Path):
    _write(
        tmp_path / "README.md",
        "\n".join(
            [
                "[web](https://example.com/page)",
                "[mail](mailto:dev@example.com)",
                "[anchor](#section)",
                "![img](https://example.com/logo.png)",
            ]
        ).replace("\\n", "
"),
    )
    _write(tmp_path / "CONTRIBUTING.md", "ok")
    _write(tmp_path / "docs" / "guide.md", "ok")
    assert check_markdown_links.find_broken_links(tmp_path) == []


def test_jekyll_html_link_resolves_to_markdown_sibling(tmp_path: Path):
    _write(tmp_path / "README.md", "ok")
    _write(tmp_path / "CONTRIBUTING.md", "ok")
    _write(tmp_path / "docs" / "index.md", "[page](GUIDE.html)")
    _write(tmp_path / "docs" / "GUIDE.md", "ok")
    assert check_markdown_links.find_broken_links(tmp_path) == []


def test_repository_docs_have_no_broken_relative_links():
    repo_root = Path(__file__).resolve().parents[1]
    broken = check_markdown_links.find_broken_links(repo_root)
    assert broken == [], "
".join(item.format() for item in broken)
