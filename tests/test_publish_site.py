"""Check the public allowlist and fast-forward history using a local remote."""

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("publish_site", ROOT / "scripts/publish_site.py")
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


class PublisherTest(unittest.TestCase):
    def test_exact_files_and_existing_branch_history(self):
        with tempfile.TemporaryDirectory(prefix="carrotcore-publisher-test-") as temporary:
            base = Path(temporary)
            repo, remote, build = base / "owner", base / "remote.git", base / "build"
            repo.mkdir()
            build.mkdir()
            subprocess.run(["git", "init", "--quiet", "--bare", str(remote)], check=True)
            publisher.git(repo, "init", "--quiet", "--initial-branch=main")
            publisher.git(repo, "config", "user.name", "Publisher test")
            publisher.git(repo, "config", "user.email", "publisher@example.invalid")
            publisher.git(repo, "remote", "add", "origin", str(remote))
            (repo / "source.txt").write_text("Keep the owner worktree and index")
            publisher.git(repo, "add", "source.txt")
            publisher.git(repo, "commit", "--quiet", "-m", "Source")
            head = publisher.git(repo, "rev-parse", "HEAD")
            (repo / "draft.txt").write_text("An existing staged draft")
            publisher.git(repo, "add", "draft.txt")
            index_before = (repo / ".git/index").read_bytes()
            files = {"index.html": b"<title>Test</title>", "CNAME": b"www.carrotcore.com\n", ".nojekyll": b""}
            for name, content in files.items():
                (build / name).write_bytes(content)
            receipt = {"files": {name: {"sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)} for name, content in files.items()}}
            (build / "build-receipt.json").write_text(json.dumps(receipt))
            verified = publisher.validate_build(build, "www.carrotcore.com")
            (build / "private.txt").write_text("Excluded")
            with self.assertRaisesRegex(ValueError, "exact receipt allowlist"):
                publisher.validate_build(build, "www.carrotcore.com")
            (build / "private.txt").unlink()
            (build / "index.html").write_text("Tampered")
            with self.assertRaisesRegex(ValueError, "saved receipt"):
                publisher.validate_build(build, "www.carrotcore.com")
            first, changed = publisher.publish(repo, verified)
            self.assertTrue(changed)
            second_files = dict(verified, **{"index.html": b"<title>Next build</title>"})
            second, changed = publisher.publish(repo, second_files)
            self.assertTrue(changed)
            self.assertEqual(subprocess.check_output(["git", "--git-dir", str(remote), "rev-parse", second + "^"], text=True).strip(), first)
            self.assertEqual(subprocess.check_output(["git", "--git-dir", str(remote), "ls-tree", "-r", "--name-only", second], text=True).splitlines(), sorted(verified))
            self.assertEqual(publisher.git(repo, "rev-parse", "HEAD"), head)
            self.assertEqual((repo / ".git/index").read_bytes(), index_before)
            self.assertEqual((repo / "draft.txt").read_text(), "An existing staged draft")
            same, changed = publisher.publish(repo, second_files)
            self.assertEqual(same, second)
            self.assertFalse(changed)


if __name__ == "__main__":
    unittest.main()
