"""Copy a reviewed shared explorer release, with source hashes."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    "index.template.html", "explorer.js", "explorer.css", "city.js",
    "vendor/OFL.txt", "vendor/source-serif-4-latin.woff2",
)


def refresh(source: Path):
    destination = ROOT / "web/explorer"
    hashes = {}
    for name in FILES:
        path = source / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Missing or symbolic shared asset: {name}")
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    for name in FILES:
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, target)
    (destination / "release.json").write_text(json.dumps({
        "schemaVersion": 1,
        "origin": "Shared research explorer",
        "files": hashes,
    }, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Shared explorer source directory")
    refresh(parser.parse_args().source)
