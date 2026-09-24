"""Check repository-relative Markdown links without network access."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
SKIP_SCHEMES = ("http://", "https://", "mailto:", "ftp://", "data:")


class BrokenLink:
    def __init__(self, source: Path, target: str, resolved: Path) -> None:
        self.source = source
        self.target = target
        self.resolved = resolved

    def format(self) -> str:
        return f"{self.source.as_posix()}: unresolved repository-relative link {self.target!r} -> {self.resolved.as_posix()}"


def iter_markdown_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    readme = repo_root / "README.md"
    contributing = repo_root / "CONTRIBUTING.md"
    if readme.is_file():
        files.append(readme)
    if contributing.is_file():
        files.append(contributing)
    docs = repo_root / "docs"
    if docs.is_dir():
        files.extend(sorted(p for p in docs.rglob("*.md") if p.is_file()))
    return files


def extract_link_targets(text: str) -> list[str]:
    targets: list[str] = []
    for match in LINK_RE.finditer(text):
        raw = match.group(1).strip().strip("<>")
        if not raw:
            continue
        targets.append(raw)
    return targets


def should_skip(target: str) -> bool:
    lowered = target.lower()
    if lowered.startswith(SKIP_SCHEMES):
        return True
    if target.startswith("#"):
        return True
    if lowered.startswith(("www.", "//")):
        return True
    return False


def local_path_part(target: str) -> str | None:
    if should_skip(target):
        return None
    path_part = target.split("#", 1)[0].split("?", 1)[0]
    if not path_part:
        return None
    return path_part


def resolve_target(source: Path, target: str) -> Path:
    return (source.parent / target).resolve()


def exists_locally(resolved: Path) -> bool:
    if resolved.exists():
        return True
    if resolved.suffix.lower() == ".html":
        md_sibling = resolved.with_suffix(".md")
        if md_sibling.exists():
            return True
    return False


def find_broken_links(repo_root: Path, files: list[Path] | None = None) -> list[BrokenLink]:
    repo_root = repo_root.resolve()
    broken: list[BrokenLink] = []
    for source in files or iter_markdown_files(repo_root):
        text = source.read_text(encoding="utf-8")
        for target in extract_link_targets(text):
            path_part = local_path_part(target)
            if path_part is None:
                continue
            resolved = resolve_target(source, path_part)
            if exists_locally(resolved):
                continue
            broken.append(BrokenLink(source=source.relative_to(repo_root), target=target, resolved=resolved))
    return broken


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root (default: parent of scripts/)",
    )
    args = parser.parse_args(argv)
    broken = find_broken_links(args.root)
    if not broken:
        print("All repository-relative Markdown links resolved.")
        return 0
    print(f"Found {len(broken)} broken repository-relative Markdown link(s):")
    for item in broken:
        print(f"  {item.format()}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
