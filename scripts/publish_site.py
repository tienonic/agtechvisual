"""Validate or publish the exact public build to the gh-pages artifact branch."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BRANCH = "refs/heads/gh-pages"


def validate_build(directory: Path, canonical_cname: str):
    if directory.is_symlink() or any(path.is_symlink() for path in directory.rglob("*")):
        raise ValueError("The public build must not contain symbolic links.")
    receipt_content = (directory / "build-receipt.json").read_bytes()
    receipt = json.loads(receipt_content)
    files = receipt["files"]
    if not {"index.html", "CNAME", ".nojekyll"}.issubset(files):
        raise ValueError("The public build is missing its entry, domain or .nojekyll file.")
    for name, info in files.items():
        path = PurePosixPath(name)
        if path.is_absolute() or path.as_posix() != name or "\\" in name or ":" in name or ".." in path.parts or any(part.lower() == ".git" for part in path.parts):
            raise ValueError("The public receipt contains an unsafe file path.")
        if not re.fullmatch(r"[0-9a-f]{64}", info["sha256"]) or not isinstance(info["bytes"], int) or info["bytes"] < 0:
            raise ValueError("The public receipt contains an invalid file hash or byte count.")
    actual = {path.relative_to(directory).as_posix() for path in directory.rglob("*") if path.is_file()}
    if actual != set(files) | {"build-receipt.json"}:
        raise ValueError("The public build does not match the exact receipt allowlist.")
    verified = {}
    for name, info in files.items():
        content = (directory / name).read_bytes()
        if len(content) != info["bytes"] or hashlib.sha256(content).hexdigest() != info["sha256"]:
            raise ValueError(f"The public file does not match its saved receipt: {name}")
        verified[name] = content
    if verified["CNAME"].decode("utf-8").strip() != canonical_cname.strip():
        raise ValueError("The artifact CNAME does not match the canonical repository CNAME; rebuild first.")
    verified["build-receipt.json"] = receipt_content
    return verified


def git(repo: Path, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def publish(repo: Path, verified, remote="origin"):
    remote_url = git(repo, "remote", "get-url", remote)
    name = git(repo, "config", "user.name")
    email = git(repo, "config", "user.email")
    with tempfile.TemporaryDirectory(prefix="carrotcore-pages-") as temporary:
        staging = Path(temporary)
        git(staging, "init", "--quiet")
        git(staging, "config", "user.name", name)
        git(staging, "config", "user.email", email)
        git(staging, "config", "core.autocrlf", "false")
        lookup = subprocess.run(["git", "ls-remote", "--exit-code", remote_url, BRANCH], capture_output=True, text=True)
        if lookup.returncode not in {0, 2}:
            raise RuntimeError("Could not read the existing gh-pages branch; nothing was published.")
        parent = None
        if lookup.returncode == 0:
            git(staging, "fetch", "--quiet", "--no-tags", remote_url, BRANCH)
            parent = git(staging, "rev-parse", "FETCH_HEAD")
        for path, content in verified.items():
            target = staging / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        git(staging, "add", "--all")
        tree = git(staging, "write-tree")
        algorithm = git(staging, "rev-parse", "--show-object-format")
        staged = git(staging, "ls-tree", "-r", "-z", tree)
        objects = {entry.split("\t", 1)[1]: entry.split("\t", 1)[0].split()[2]
            for entry in staged.split("\0") if entry}
        expected = {path: hashlib.new(algorithm, f"blob {len(content)}\0".encode() + content).hexdigest()
            for path, content in verified.items()}
        if objects != expected:
            raise RuntimeError("Git changed the verified artifact bytes; nothing was published.")
        if parent and tree == git(staging, "rev-parse", parent + "^{tree}"):
            return parent, False
        args = ["commit-tree", tree]
        if parent:
            args.extend(["-p", parent])
        args.extend(["-m", "Publish validated Carrot Core website"])
        commit = git(staging, *args)
        git(staging, "push", "--quiet", remote_url, commit + ":" + BRANCH)
        return commit, True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true", help="Read and validate the build without changing Git or the remote")
    action.add_argument("--publish", action="store_true", help="Push the validated artifact tree to gh-pages with its existing commit as parent")
    parser.add_argument("--directory", type=Path, default=ROOT / "public-site")
    args = parser.parse_args()
    verified = validate_build(args.directory, (ROOT / "CNAME").read_text())
    if args.check:
        print(f"Validated {len(verified)} public files. No Git or remote changes.")
        return
    commit, changed = publish(ROOT, verified)
    print(("Published " if changed else "Already published ") + commit + " on gh-pages.")


if __name__ == "__main__":
    main()
