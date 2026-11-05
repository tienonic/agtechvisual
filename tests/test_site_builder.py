"""Public record preservation and export-boundary checks (stdlib only)."""

import copy
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.site_builder import ASSETS, adapt, build_site, validate_snapshot
from src.public_ai import import_public_ai, load_public_ai

ROOT = Path(__file__).resolve().parents[1]


class PublicSiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((ROOT / "data/public-dashboard.json").read_text())

    def test_source_values_and_duplicate_records_survive(self):
        source = (ROOT / "analytical.html").read_text()
        marker = "const DATA = "
        original, _ = json.JSONDecoder().raw_decode(source[source.index(marker) + len(marker):])
        self.assertEqual(self.data, original)
        dataset, shards = adapt(self.data)
        self.assertEqual(len(dataset["nodes"]), self.data["stats"]["total"])
        self.assertEqual(dataset["edges"], [])
        self.assertEqual(len({n["id"] for n in dataset["nodes"]}), len(dataset["nodes"]))
        restored = [shards[i // 100][node["id"]]["record"] for i, node in enumerate(dataset["nodes"])]
        self.assertEqual(restored, self.data["companies"])
        duplicate = copy.deepcopy(self.data)
        duplicate["companies"] = [duplicate["companies"][0]] * 2
        duplicate["stats"]["total"] = 2
        nodes, _ = adapt(duplicate)
        self.assertNotEqual(nodes["nodes"][0]["id"], nodes["nodes"][1]["id"])

    def test_public_fields_are_explicit(self):
        changed = copy.deepcopy(self.data)
        changed["companies"][0]["private_notes"] = "Not public"
        with self.assertRaisesRegex(ValueError, "allowlist"):
            validate_snapshot(changed)
        changed = copy.deepcopy(self.data)
        changed["companies"][0]["website"] = "file:///private/record"
        with self.assertRaisesRegex(ValueError, "private or local"):
            validate_snapshot(changed)

    def test_saved_funding_keeps_zero_and_missing_distinct(self):
        data = copy.deepcopy(self.data)
        data["companies"] = [copy.deepcopy(data["companies"][0]) for _ in range(2)]
        data["companies"][0]["funding"] = 0
        data["companies"][1]["funding"] = None
        data["stats"]["total"] = 2
        dataset, _ = adapt(data)
        zero, missing = [node["metrics"]["Saved funding"] for node in dataset["nodes"]]
        self.assertEqual(zero["value"], 0)
        self.assertIsNone(missing["value"])
        self.assertIn("A zero means no positive amount was saved, not no funding.", zero["note"])

    def test_missing_database_does_not_replace_the_public_snapshot(self):
        from src.cli import cmd_dashboard
        before = (ROOT / "data/public-dashboard.json").read_bytes()
        with tempfile.TemporaryDirectory(prefix="agtech-no-db-") as temp:
            missing = Path(temp) / "missing.db"
            with patch("src.cli.DB_PATH", missing), redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit):
                    cmd_dashboard(None)
            self.assertFalse(missing.exists())
        self.assertEqual((ROOT / "data/public-dashboard.json").read_bytes(), before)

    def test_import_rejects_private_datasets_and_unreachable_files(self):
        with tempfile.TemporaryDirectory(prefix="agtech-import-") as temp:
            source, cache = Path(temp) / "source", Path(temp) / "cache"
            (source / "datasets").mkdir(parents=True)
            (source / "details/ai").mkdir(parents=True)
            entry = {"id": "ai", "label": "AI", "public": True, "nodeCount": 1, "edgeCount": 0, "url": "datasets/ai.json"}
            manifest = {"datasets": [entry]}
            dataset = {"id": "ai", "nodes": [{"id": "example", "kind": "Source record", "detailUrl": "../details/ai/0000.json"}], "edges": []}
            shard = {"datasetId": "ai", "records": {"example": {"record": {"website": "https://example.org/home/terms"}}}}
            names = ["datasets/ai.json", "details/ai/0000.json", "manifest.public.json"]
            allowlist = {"manifest": "manifest.public.json", "files": names}
            for name, data in {"public-files.json": allowlist, "manifest.public.json": manifest,
                    "datasets/ai.json": dataset, "details/ai/0000.json": shard}.items():
                (source / name).write_text(json.dumps(data))
            receipt = import_public_ai(source, cache)
            self.assertEqual(set(receipt["files"]), set(names) - {"manifest.public.json"})
            self.assertFalse((cache / "manifest.public.json").exists())
            self.assertEqual(load_public_ai(cache)[0], receipt)
            allowlist["files"] = names + ["datasets/private.json"]
            (source / "public-files.json").write_text(json.dumps(allowlist))
            with self.assertRaisesRegex(ValueError, "another dataset"):
                import_public_ai(source, cache)
            allowlist["files"] = names + ["details/ai/0001.json"]
            (source / "public-files.json").write_text(json.dumps(allowlist))
            (source / "details/ai/0001.json").write_text(json.dumps(shard))
            with self.assertRaisesRegex(ValueError, "reachable public allowlist"):
                import_public_ai(source, cache)
            (cache / "private.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "exact public allowlist"):
                load_public_ai(cache)

    def test_build_has_only_public_files_and_resolvable_evidence(self):
        with tempfile.TemporaryDirectory(prefix="agtech-public-") as temp:
            root = Path(temp)
            for name in ("data", "web"):
                import shutil
                shutil.copytree(ROOT / name, root / name)
            for name in ("analytical.html", "CNAME"):
                (root / name).write_bytes((ROOT / name).read_bytes())
            receipt = build_site(root, root / "public-site")
            output = root / "public-site"
            actual = {p.relative_to(output).as_posix() for p in output.rglob("*") if p.is_file()}
            self.assertEqual(actual, set(receipt["files"]) | {"build-receipt.json"})
            self.assertEqual((output / "CNAME").read_bytes(), (ROOT / "CNAME").read_bytes())
            self.assertEqual(receipt["snapshotSha256"], hashlib.sha256((ROOT / "data/public-dashboard.json").read_bytes()).hexdigest())
            dataset = json.loads((output / "explorer-data/agtech.json").read_text())
            for node in dataset["nodes"]:
                path = output / "explorer-data" / node["detailUrl"]
                self.assertIn(node["id"], json.loads(path.read_text())["records"])
            manifest = json.loads((output / "explorer-data/manifest.json").read_text())
            self.assertEqual([entry["id"] for entry in manifest["datasets"]], ["agtech", "ai"])
            self.assertEqual(manifest["defaultSelection"], ["agtech"])
            ai_receipt, ai_artifacts = load_public_ai(root / "data/public-ai")
            self.assertEqual(ai_receipt["sourceRecordCount"], 5715)
            self.assertEqual(ai_receipt["relationshipEndpointCount"], 8)
            self.assertEqual({name.removeprefix("explorer-data/") for name in actual
                if name.startswith(("explorer-data/datasets/", "explorer-data/details/ai/"))}, set(ai_receipt["files"]))
            for entry in manifest["datasets"]:
                saved = json.loads((output / "explorer-data" / entry["url"]).read_text())
                self.assertEqual(len(saved["nodes"]), entry["nodeCount"])
                self.assertEqual(len(saved["edges"]), entry["edgeCount"])
            for name, content in ai_artifacts.items():
                self.assertEqual((output / "explorer-data" / name).read_bytes(), content)
            for name in ASSETS:
                self.assertEqual((output / "explorer-assets" / name).read_bytes(), (ROOT / "web/explorer" / name).read_bytes())
            first_receipt = (output / "build-receipt.json").read_bytes()
            build_site(root, output)
            self.assertEqual((output / "build-receipt.json").read_bytes(), first_receipt)
            (output / "private.txt").write_text("Not an allowed public file")
            with self.assertRaisesRegex(ValueError, "Unexpected file"):
                build_site(root, output)
            (output / "private.txt").unlink()
            from src.dashboard_template import render_dashboard
            render_dashboard(self.data, root / "index.html")
            regenerated = json.loads((root / "data/public-dashboard.json").read_text())
            self.assertEqual(regenerated, self.data)
            self.assertIn('"title":"Carrot Core"', (root / "index.html").read_text())
            self.assertEqual(json.loads((output / "build-receipt.json").read_text())["datasets"]["agtech"]["sourceRecordCount"], len(self.data["companies"]))


if __name__ == "__main__":
    unittest.main()
