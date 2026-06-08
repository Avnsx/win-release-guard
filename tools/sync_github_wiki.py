from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = REPO_ROOT / "wiki"
DEFAULT_COMMIT_MESSAGE = "Sync GitHub Wiki from source Markdown"
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


@dataclass(frozen=True)
class WikiSourceFile:
    source_path: Path
    target_name: str


@dataclass(frozen=True)
class SyncResult:
    source_files: tuple[WikiSourceFile, ...]
    copied: tuple[str, ...]
    removed: tuple[str, ...]
    changed: bool


class WikiSyncError(RuntimeError):
    pass


def _resolve_existing_source_dir(path: Path) -> Path:
    source_dir = path.resolve()
    if not source_dir.is_dir():
        raise WikiSyncError(f"Wiki source directory does not exist: {source_dir}")
    return source_dir


def _validate_repository(repository: str) -> str:
    if not REPOSITORY_RE.fullmatch(repository):
        raise WikiSyncError("Repository must be in owner/name form.")
    if repository.endswith(".wiki"):
        raise WikiSyncError("Repository must be the main repository name, not the .wiki repository name.")
    return repository


def _wiki_remote_url(repository: str) -> str:
    return f"https://github.com/{_validate_repository(repository)}.wiki.git"


def _wiki_source_sort_key(path: Path) -> tuple[int, str]:
    special_order = {"Home.md": 0, "_Sidebar.md": 1, "_Footer.md": 2}
    return (special_order.get(path.name, 3), path.name.casefold())


def collect_wiki_markdown(source_dir: Path = DEFAULT_SOURCE_DIR) -> tuple[WikiSourceFile, ...]:
    source_root = _resolve_existing_source_dir(source_dir)
    files = tuple(
        WikiSourceFile(source_path=path, target_name=path.name)
        for path in sorted(source_root.glob("*.md"), key=_wiki_source_sort_key)
        if path.is_file()
    )
    if not files:
        raise WikiSyncError(f"No wiki/*.md source files found in {source_root}")
    return files


def _same_file_bytes(left: Path, right: Path) -> bool:
    if not right.is_file():
        return False
    return left.read_bytes() == right.read_bytes()


def _remove_stale_markdown_files(target_dir: Path, source_names: set[str]) -> list[str]:
    removed: list[str] = []
    for existing in sorted(target_dir.glob("*.md"), key=lambda item: item.name.casefold()):
        if existing.name not in source_names:
            existing.unlink()
            removed.append(existing.name)
    return removed


def sync_markdown_to_wiki_dir(source_files: Sequence[WikiSourceFile], wiki_dir: Path) -> SyncResult:
    target_dir = wiki_dir.resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    source_names = {source.target_name for source in source_files}
    removed = _remove_stale_markdown_files(target_dir, source_names)
    copied: list[str] = []
    for source in source_files:
        target = target_dir / source.target_name
        if not _same_file_bytes(source.source_path, target):
            shutil.copy2(source.source_path, target)
            copied.append(source.target_name)
    changed = bool(copied or removed)
    return SyncResult(
        source_files=tuple(source_files),
        copied=tuple(copied),
        removed=tuple(removed),
        changed=changed,
    )


def write_source_artifact(source_files: Sequence[WikiSourceFile], artifact_dir: Path, *, repository: str) -> Path:
    target_dir = artifact_dir.resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    source_names = {source.target_name for source in source_files}
    _remove_stale_markdown_files(target_dir, source_names)
    for source in source_files:
        shutil.copy2(source.source_path, target_dir / source.target_name)
    manifest = {
        "repository": _validate_repository(repository),
        "source": "wiki/*.md",
        "target": f"https://github.com/{repository}.wiki.git",
        "files": [source.target_name for source in source_files],
        "notes": [
            "Only source Markdown files are included.",
            "Generated GitHub Pages HTML is not included.",
            "_Sidebar.md and _Footer.md are preserved when present.",
        ],
    }
    manifest_path = target_dir / "wiki-sync-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest_path


def _run_git(args: Sequence[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=env,
        check=True,
        text=True,
    )


def _git_has_changes(repo_dir: Path) -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain", "--", "*.md"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


@contextmanager
def _git_askpass_env(auth_value: str) -> Iterator[dict[str, str]]:
    if not auth_value:
        raise WikiSyncError("A built-in Actions token is required for GitHub Wiki push.")
    with tempfile.TemporaryDirectory(prefix="wrg-git-askpass-") as directory:
        askpass = Path(directory) / ("askpass.cmd" if os.name == "nt" else "askpass.sh")
        if os.name == "nt":
            askpass.write_text(
                "@echo off\r\n"
                "echo %~1 | findstr /I \"Username\" >nul\r\n"
                "if not errorlevel 1 (\r\n"
                "  echo x-access-token\r\n"
                ") else (\r\n"
                "  echo %WRG_WIKI_SYNC_TOKEN%\r\n"
                ")\r\n",
                encoding="utf-8",
            )
        else:
            askpass.write_text(
                "#!/bin/sh\n"
                "case \"$1\" in\n"
                "*Username*) printf '%s\\n' 'x-access-token' ;;\n"
                "*) printf '%s\\n' \"$WRG_WIKI_SYNC_TOKEN\" ;;\n"
                "esac\n",
                encoding="utf-8",
            )
            askpass.chmod(askpass.stat().st_mode | stat.S_IXUSR)
        env = os.environ.copy()
        env["GIT_ASKPASS"] = str(askpass)
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["WRG_WIKI_SYNC_TOKEN"] = auth_value
        yield env


def _clone_wiki(repository: str, destination: Path, *, auth_value: str) -> None:
    remote_url = _wiki_remote_url(repository)
    with _git_askpass_env(auth_value) as env:
        try:
            _run_git(["clone", "--depth", "1", remote_url, str(destination)], cwd=REPO_ROOT, env=env)
        except subprocess.CalledProcessError as exc:
            raise WikiSyncError(
                "GitHub Wiki clone failed. The repository wiki may need to be initialized manually first, "
                "or GitHub may reject the built-in Actions token for this wiki repository."
            ) from exc


def push_wiki_sync(
    *,
    repository: str,
    source_files: Sequence[WikiSourceFile],
    commit_message: str,
    auth_value: str,
) -> SyncResult:
    with tempfile.TemporaryDirectory(prefix="wrg-github-wiki-") as directory:
        wiki_dir = Path(directory) / "wiki"
        _clone_wiki(repository, wiki_dir, auth_value=auth_value)
        result = sync_markdown_to_wiki_dir(source_files, wiki_dir)
        if not result.changed or not _git_has_changes(wiki_dir):
            return result
        _run_git(["config", "user.name", "github-actions[bot]"], cwd=wiki_dir)
        _run_git(["config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], cwd=wiki_dir)
        _run_git(["add", "--all", "--", "*.md"], cwd=wiki_dir)
        _run_git(["commit", "-m", commit_message], cwd=wiki_dir)
        with _git_askpass_env(auth_value) as env:
            _run_git(["push"], cwd=wiki_dir, env=env)
        return result


def _repository_from_environment() -> str | None:
    repository = os.environ.get("GITHUB_REPOSITORY")
    return repository if repository else None


def _auth_value_from_environment() -> str:
    return os.environ.get("WRG_WIKI_SYNC_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sync repository wiki/*.md source files to the GitHub internal Wiki repository.",
    )
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR, help="Directory containing wiki/*.md.")
    parser.add_argument(
        "--wiki-dir",
        type=Path,
        help="Existing local wiki checkout to update instead of cloning the GitHub Wiki repository.",
    )
    parser.add_argument(
        "--repository",
        default=_repository_from_environment(),
        help="Main GitHub repository in owner/name form. Defaults to GITHUB_REPOSITORY.",
    )
    parser.add_argument("--commit-message", default=DEFAULT_COMMIT_MESSAGE, help="Commit message for real Wiki pushes.")
    parser.add_argument("--artifact-dir", type=Path, help="Write a clean Markdown artifact for manual Wiki sync fallback.")
    parser.add_argument("--dry-run", action="store_true", help="List source files and write artifacts without cloning or pushing.")
    parser.add_argument("--push", action="store_true", help="Clone the .wiki.git repository, commit, and push Markdown changes.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        repository = _validate_repository(args.repository or "")
        source_files = collect_wiki_markdown(args.source_dir)
        if args.artifact_dir:
            manifest_path = write_source_artifact(source_files, args.artifact_dir, repository=repository)
            print(f"Wrote GitHub Wiki Markdown artifact manifest: {manifest_path}")
        if args.dry_run:
            print("Dry run: no GitHub Wiki clone, commit, or push was attempted.")
            for source in source_files:
                print(f"source: wiki/{source.target_name}")
            return 0
        if args.wiki_dir:
            result = sync_markdown_to_wiki_dir(source_files, args.wiki_dir)
            print(
                "Updated local Wiki checkout: "
                f"{len(result.copied)} copied, {len(result.removed)} removed."
            )
            return 0
        if not args.push:
            raise WikiSyncError("Use --dry-run, --wiki-dir, or --push.")
        result = push_wiki_sync(
            repository=repository,
            source_files=source_files,
            commit_message=args.commit_message,
            auth_value=_auth_value_from_environment(),
        )
    except (OSError, subprocess.CalledProcessError, WikiSyncError) as exc:
        print(f"GitHub Wiki sync failed: {exc}", file=sys.stderr)
        return 1
    if result.changed:
        print(f"Synced GitHub Wiki Markdown: {len(result.copied)} copied, {len(result.removed)} removed.")
    else:
        print("GitHub Wiki already matches source Markdown.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
