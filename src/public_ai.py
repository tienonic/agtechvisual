"""Import only the AI map's explicit public artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import posixpath
import re

ARTIFACT = re.compile(r"(?:datasets/ai\.json|details/ai/\d{4}\.json)\Z")
PRIVATE_PATH = re.compile(r"(?:(?<![\w./:])/(?:mnt/[a-z]/|home/)|[a-z]:[\\/](?:Users|Windows)[\\/]|file://)", re.I)


def sha256(content):
    return hashlib.sha256(content).hexdigest()


def read_public(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("Public AI files must be ordinary files.")
    content = path.read_bytes()
    if PRIVATE_PATH.search(content.decode("utf-8")):
        raise ValueError("A public AI artifact contains a local path.")
    return content


def reachable_files(entry, artifacts):
    if entry.get("id") != "ai" or entry.get("public") is not True or entry.get("url") != "datasets/ai.json":
        raise ValueError("Only the explicit public AI dataset can be imported.")
    dataset = json.loads(artifacts["datasets/ai.json"])
    if dataset.get("id") != "ai":
        raise ValueError("The imported dataset is not AI.")
    nodes = dataset["nodes"]
    ids = {node["id"] for node in nodes}
    if len(ids) != len(nodes):
        raise ValueError("The AI dataset has repeated record IDs.")
    if entry["nodeCount"] != len(nodes) or entry["edgeCount"] != len(dataset["edges"]):
        raise ValueError("The AI manifest counts do not match its records.")
    reachable = {"datasets/ai.json"}
    shards = {}
    for node in nodes:
        reference = node.get("detailUrl")
        if not reference:
            continue
        name = posixpath.normpath(posixpath.join("datasets", reference))
        if not ARTIFACT.fullmatch(name) or not name.startswith("details/ai/"):
            raise ValueError("An AI detail endpoint leaves the public AI allowlist.")
        reachable.add(name)
        if name not in artifacts:
            raise ValueError("A reachable AI detail shard is missing.")
        if name not in shards:
            shards[name] = json.loads(artifacts[name])
        shard = shards[name]
        if shard.get("datasetId") != "ai" or node["id"] not in shard["records"]:
            raise ValueError("An AI detail shard has the wrong dataset or record.")
    for edge in dataset["edges"]:
        if edge["source"] not in ids or edge["target"] not in ids:
            raise ValueError("An AI edge points outside its dataset.")
    if set(artifacts) != reachable:
        raise ValueError("The AI import contains files outside its reachable public allowlist.")
    return dataset


def import_public_ai(source: Path, destination: Path):
    allowlist_content = read_public(source / "public-files.json")
    allowlist = json.loads(allowlist_content)
    names = allowlist["files"]
    if allowlist.get("manifest") != "manifest.public.json" or len(names) != len(set(names)):
        raise ValueError("The public AI allowlist is invalid.")
    if "manifest.public.json" not in names or any(name != "manifest.public.json" and not ARTIFACT.fullmatch(name) for name in names):
        raise ValueError("The public AI allowlist contains another dataset or an unexpected file.")
    manifest_content = read_public(source / "manifest.public.json")
    manifest = json.loads(manifest_content)
    if len(manifest["datasets"]) != 1:
        raise ValueError("The public AI manifest must select AI alone.")
    entry = manifest["datasets"][0]
    artifacts = {name: read_public(source / name) for name in names if name != "manifest.public.json"}
    dataset = reachable_files(entry, artifacts)
    source_records = sum(node.get("kind") != "Relationship endpoint" for node in dataset["nodes"])
    receipt = {
        "schemaVersion": 1, "dataset": entry,
        "source": "Public AI business map publication",
        "sourceAllowlistSha256": sha256(allowlist_content),
        "sourceManifestSha256": sha256(manifest_content),
        "sourceAllowlistFiles": names,
        "sourceRecordCount": source_records,
        "relationshipEndpointCount": len(dataset["nodes"]) - source_records,
        "files": {name: {"sha256": sha256(content), "bytes": len(content)} for name, content in sorted(artifacts.items())},
    }
    destination.mkdir(parents=True, exist_ok=True)
    actual = {p.relative_to(destination).as_posix() for p in destination.rglob("*") if p.is_file()}
    if actual - (set(artifacts) | {"import-receipt.json"}):
        raise ValueError("The AI cache contains unexpected files; import into a fresh directory.")
    for name, content in artifacts.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    (destination / "import-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def load_public_ai(cache: Path):
    receipt = json.loads(read_public(cache / "import-receipt.json"))
    if any(not ARTIFACT.fullmatch(name) for name in receipt["files"]):
        raise ValueError("The AI cache contains a file outside its public allowlist.")
    expected = set(receipt["files"]) | {"import-receipt.json"}
    actual = {p.relative_to(cache).as_posix() for p in cache.rglob("*") if p.is_file()}
    if actual != expected or any(p.is_symlink() for p in cache.rglob("*")):
        raise ValueError("The AI cache does not match its exact public allowlist.")
    artifacts = {}
    for name, info in receipt["files"].items():
        content = read_public(cache / name)
        if sha256(content) != info["sha256"] or len(content) != info["bytes"]:
            raise ValueError("A public AI cache artifact changed without a new import.")
        artifacts[name] = content
    reachable_files(receipt["dataset"], artifacts)
    return receipt, artifacts
