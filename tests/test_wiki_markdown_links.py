from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WIKI = ROOT / "wiki"
ABSOLUTE_WIKI_PAGE_RE = re.compile(r"https://github\.com/Avnsx/win11_release_guard/wiki/([A-Za-z0-9_.-]+)")
WIKI_LINK_RE = re.compile(r"\[\[([^\]\n]+)\]\]")
MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[([^\]\n]+)\]\(([^)\n]+)\)")
SLUG_ONLY_RE = re.compile(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)+")


@dataclass(frozen=True)
class TableRow:
    path: Path
    line_number: int
    raw: str
    cells: list[str]
    header: list[str]
    is_separator: bool


def _wiki_files() -> list[Path]:
    return sorted(WIKI.glob("*.md"))


def _documentation_files() -> list[Path]:
    return [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md")), *_wiki_files()]


def _split_table_row(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]

    cells: list[str] = []
    current: list[str] = []
    escaped = False
    for char in stripped:
        if char == "|" and not escaped:
            cells.append("".join(current).strip())
            current = []
            continue
        current.append(char)
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
    cells.append("".join(current).strip())
    return cells


def _is_table_separator(line: str) -> bool:
    cells = _split_table_row(line)
    return len(cells) >= 2 and all(re.fullmatch(r":?-{3,}:?", cell.strip()) for cell in cells)


def _looks_like_table_row(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and "|" in stripped[1:]


def _iter_table_rows(path: Path) -> list[TableRow]:
    rows: list[TableRow] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    in_fence = False
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            index += 1
            continue
        if in_fence:
            index += 1
            continue
        if (
            index + 1 < len(lines)
            and _looks_like_table_row(lines[index])
            and _is_table_separator(lines[index + 1])
        ):
            header = _split_table_row(lines[index])
            row_index = index
            while row_index < len(lines) and _looks_like_table_row(lines[row_index]):
                raw = lines[row_index]
                rows.append(
                    TableRow(
                        path=path,
                        line_number=row_index + 1,
                        raw=raw,
                        cells=_split_table_row(raw),
                        header=header,
                        is_separator=row_index == index + 1,
                    )
                )
                row_index += 1
            index = row_index
            continue
        index += 1
    return rows


def _table_rows(paths: list[Path]) -> list[TableRow]:
    rows: list[TableRow] = []
    for path in paths:
        rows.extend(_iter_table_rows(path))
    return rows


def _wiki_target(body: str) -> str:
    return body.rsplit("|", 1)[-1].strip()


def _is_external_or_repo_relative_link(target: str) -> bool:
    normalized = target.strip()
    return (
        "://" in normalized
        or normalized.startswith("#")
        or normalized.startswith("/")
        or normalized.startswith("../")
        or normalized.startswith("./")
        or "/" in normalized
        or normalized.lower().startswith("mailto:")
    )


def _page_path(target: str) -> Path:
    page = target.split("#", 1)[0].strip()
    if page.endswith(".md"):
        page = page[:-3]
    return WIKI / f"{page}.md"


def _is_external_link(target: str) -> bool:
    normalized = target.strip().lower()
    return "://" in normalized or normalized.startswith("mailto:")


def _resolve_local_markdown_target(path: Path, target: str) -> Path | None:
    link = target.split("#", 1)[0].strip()
    if not link or _is_external_link(link) or link.startswith("#"):
        return None
    if path.parent == WIKI and "/" not in link and not link.startswith("."):
        return _page_path(link)
    if link.startswith("/"):
        return ROOT / link.lstrip("/")
    return (path.parent / link).resolve()


def test_wiki_markdown_tables_do_not_use_wiki_link_syntax() -> None:
    findings = [
        f"{row.path.relative_to(ROOT)}:{row.line_number}: {row.raw}"
        for row in _table_rows(_wiki_files())
        if "[[" in row.raw or "]]" in row.raw
    ]

    assert findings == []


def test_readme_and_docs_tables_do_not_use_wiki_link_syntax() -> None:
    paths = [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md"))]
    findings = [
        f"{row.path.relative_to(ROOT)}:{row.line_number}: {row.raw}"
        for row in _table_rows(paths)
        if "[[" in row.raw or "]]" in row.raw
    ]

    assert findings == []


def test_wiki_markdown_tables_have_consistent_column_counts() -> None:
    findings: list[str] = []
    for row in _table_rows(_wiki_files()):
        expected = len(row.header)
        actual = len(row.cells)
        if actual != expected:
            findings.append(
                f"{row.path.relative_to(ROOT)}:{row.line_number}: expected {expected} cells, got {actual}: {row.raw}"
            )

    assert findings == []


def test_wiki_markdown_table_cells_do_not_contain_split_wiki_fragments() -> None:
    findings: list[str] = []
    for row in _table_rows(_wiki_files()):
        for cell in row.cells:
            if ("[[" in cell) != ("]]" in cell):
                findings.append(f"{row.path.relative_to(ROOT)}:{row.line_number}: {cell}")

    assert findings == []


def test_wiki_markdown_why_columns_are_explanatory() -> None:
    findings: list[str] = []
    for row in _table_rows(_wiki_files()):
        if row.is_separator:
            continue
        normalized_header = [cell.strip().lower() for cell in row.header]
        if "why" not in normalized_header or row.cells == row.header:
            continue
        why_cell = row.cells[normalized_header.index("why")].strip()
        if SLUG_ONLY_RE.fullmatch(why_cell) or MARKDOWN_LINK_RE.fullmatch(why_cell):
            findings.append(f"{row.path.relative_to(ROOT)}:{row.line_number}: {why_cell}")

    assert findings == []


def test_all_local_wiki_link_targets_exist() -> None:
    findings: list[str] = []
    for path in _wiki_files():
        text = path.read_text(encoding="utf-8")
        for match in WIKI_LINK_RE.finditer(text):
            target = _wiki_target(match.group(1))
            if "|" in target or not _page_path(target).is_file():
                findings.append(f"{path.relative_to(ROOT)}: [[{match.group(1)}]] -> {target}")
        for match in MARKDOWN_LINK_RE.finditer(text):
            target = match.group(2).strip()
            if _is_external_or_repo_relative_link(target):
                continue
            if not _page_path(target).is_file():
                findings.append(f"{path.relative_to(ROOT)}: [{match.group(1)}]({target})")

    assert findings == []


def test_readme_docs_and_wiki_absolute_wiki_urls_target_existing_pages() -> None:
    findings: list[str] = []
    for path in _documentation_files():
        text = path.read_text(encoding="utf-8")
        for match in ABSOLUTE_WIKI_PAGE_RE.finditer(text):
            target = match.group(1)
            if not _page_path(target).is_file():
                findings.append(f"{path.relative_to(ROOT)}: {match.group(0)}")

    assert findings == []


def test_readme_docs_and_wiki_local_markdown_links_target_existing_files() -> None:
    findings: list[str] = []
    for path in _documentation_files():
        text = path.read_text(encoding="utf-8")
        for match in MARKDOWN_LINK_RE.finditer(text):
            resolved = _resolve_local_markdown_target(path, match.group(2))
            if resolved is None:
                continue
            if not resolved.is_file():
                findings.append(f"{path.relative_to(ROOT)}: [{match.group(1)}]({match.group(2)})")

    assert findings == []


def test_sidebar_wiki_links_target_existing_pages() -> None:
    sidebar = WIKI / "_Sidebar.md"
    findings = []
    for match in WIKI_LINK_RE.finditer(sidebar.read_text(encoding="utf-8")):
        target = _wiki_target(match.group(1))
        if not _page_path(target).is_file():
            findings.append(f"[[{match.group(1)}]] -> {target}")

    assert findings == []


def test_sidebar_keeps_wiki_link_syntax_outside_tables() -> None:
    sidebar = WIKI / "_Sidebar.md"
    text = sidebar.read_text(encoding="utf-8")

    assert _iter_table_rows(sidebar) == []
    assert "[[Quick Start|Quick-Start]]" in text
    assert "[[CLI and RMM Usage|CLI-and-RMM-Usage]]" in text


def test_home_and_release_wiki_pages_have_no_broken_table_link_fragments() -> None:
    home = (WIKI / "Home.md").read_text(encoding="utf-8")
    release = (WIKI / "Release-v0.3.0.md").read_text(encoding="utf-8")

    assert "## Pick Your Path" in home
    assert "[[Quick Start" not in home
    assert "Quick-Start]]" not in home
    release_table_has_wiki_link = any(
        "[[" in row.raw or "]]" in row.raw for row in _iter_table_rows(WIKI / "Release-v0.3.0.md")
    )
    assert not release_table_has_wiki_link
    assert "[Quick Start](Quick-Start)" in release
