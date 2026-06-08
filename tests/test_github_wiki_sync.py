from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools import sync_github_wiki


def test_sync_github_wiki_help_works_from_source_checkout() -> None:
    result = subprocess.run(
        [sys.executable, "tools/sync_github_wiki.py", "--help"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Sync repository wiki/*.md source files" in result.stdout
    assert "--dry-run" in result.stdout
    assert "--artifact-dir" in result.stdout


def test_collect_wiki_markdown_uses_root_markdown_only(tmp_path: Path) -> None:
    source_dir = tmp_path / "wiki"
    source_dir.mkdir()
    (source_dir / "Home.md").write_text("# Home\n", encoding="utf-8")
    (source_dir / "_Sidebar.md").write_text("[[Home]]\n", encoding="utf-8")
    (source_dir / "generated.html").write_text("<html></html>\n", encoding="utf-8")
    nested = source_dir / "nested"
    nested.mkdir()
    (nested / "Nested.md").write_text("# Nested\n", encoding="utf-8")

    files = sync_github_wiki.collect_wiki_markdown(source_dir)

    assert [file.target_name for file in files] == ["Home.md", "_Sidebar.md"]


def test_dry_run_writes_clean_markdown_artifact(tmp_path: Path, capsys) -> None:
    source_dir = tmp_path / "wiki"
    artifact_dir = tmp_path / "artifact"
    source_dir.mkdir()
    (source_dir / "Home.md").write_text("# Home\n", encoding="utf-8")
    (source_dir / "_Footer.md").write_text("Footer\n", encoding="utf-8")
    (source_dir / "page.html").write_text("<html></html>\n", encoding="utf-8")

    code = sync_github_wiki.main(
        [
            "--source-dir",
            str(source_dir),
            "--repository",
            "Avnsx/win11_release_guard",
            "--artifact-dir",
            str(artifact_dir),
            "--dry-run",
        ]
    )

    assert code == 0
    output = capsys.readouterr().out
    assert "Dry run" in output
    assert "source: wiki/Home.md" in output
    assert (artifact_dir / "Home.md").read_text(encoding="utf-8") == "# Home\n"
    assert (artifact_dir / "_Footer.md").read_text(encoding="utf-8") == "Footer\n"
    assert not (artifact_dir / "page.html").exists()
    manifest = json.loads((artifact_dir / "wiki-sync-manifest.json").read_text(encoding="utf-8"))
    assert manifest["source"] == "wiki/*.md"
    assert manifest["target"] == "https://github.com/Avnsx/win11_release_guard.wiki.git"
    assert manifest["files"] == ["Home.md", "_Footer.md"]
    assert "Generated GitHub Pages HTML is not included." in manifest["notes"]
    manifest_text = json.dumps(manifest)
    assert "x-access-token" not in manifest_text
    assert ("gh" + "p_") not in manifest_text
    assert ("github" + "_pat_") not in manifest_text
    assert "generated_site" not in manifest_text
    assert "site/" not in manifest_text


def test_push_failure_keeps_markdown_artifact_visible(tmp_path: Path, capsys, monkeypatch) -> None:
    source_dir = tmp_path / "wiki"
    artifact_dir = tmp_path / "artifact"
    source_dir.mkdir()
    (source_dir / "Home.md").write_text("# Home\n", encoding="utf-8")
    monkeypatch.delenv("WRG_WIKI_SYNC_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    code = sync_github_wiki.main(
        [
            "--source-dir",
            str(source_dir),
            "--repository",
            "Avnsx/win11_release_guard",
            "--artifact-dir",
            str(artifact_dir),
            "--push",
        ]
    )

    captured = capsys.readouterr()
    assert code == 1
    assert "GitHub Wiki sync failed" in captured.err
    assert "built-in Actions token" in captured.err
    assert (artifact_dir / "Home.md").read_text(encoding="utf-8") == "# Home\n"
    manifest = json.loads((artifact_dir / "wiki-sync-manifest.json").read_text(encoding="utf-8"))
    assert manifest["files"] == ["Home.md"]


def test_sync_local_wiki_checkout_mirrors_root_markdown(tmp_path: Path) -> None:
    source_dir = tmp_path / "wiki"
    wiki_checkout = tmp_path / "wiki-checkout"
    source_dir.mkdir()
    wiki_checkout.mkdir()
    (source_dir / "Home.md").write_text("# Home\n", encoding="utf-8")
    (source_dir / "_Sidebar.md").write_text("[[Home]]\n", encoding="utf-8")
    (source_dir / "not-markdown.html").write_text("<html></html>\n", encoding="utf-8")
    (wiki_checkout / "Old.md").write_text("# Old\n", encoding="utf-8")
    (wiki_checkout / "asset.png").write_bytes(b"png")

    code = sync_github_wiki.main(
        [
            "--source-dir",
            str(source_dir),
            "--repository",
            "Avnsx/win11_release_guard",
            "--wiki-dir",
            str(wiki_checkout),
        ]
    )

    assert code == 0
    assert (wiki_checkout / "Home.md").read_text(encoding="utf-8") == "# Home\n"
    assert (wiki_checkout / "_Sidebar.md").read_text(encoding="utf-8") == "[[Home]]\n"
    assert not (wiki_checkout / "Old.md").exists()
    assert not (wiki_checkout / "not-markdown.html").exists()
    assert (wiki_checkout / "asset.png").read_bytes() == b"png"


def test_sync_rejects_wiki_repository_name(tmp_path: Path) -> None:
    source_dir = tmp_path / "wiki"
    source_dir.mkdir()
    (source_dir / "Home.md").write_text("# Home\n", encoding="utf-8")

    code = sync_github_wiki.main(
        [
            "--source-dir",
            str(source_dir),
            "--repository",
            "Avnsx/win11_release_guard.wiki",
            "--dry-run",
        ]
    )

    assert code == 1
