import json
import tempfile
import unittest
from pathlib import Path

from adapter.manifest import build_manifest, sha256_file, write_manifest


class ManifestTests(unittest.TestCase):
    def test_manifest_marks_experiment_non_official_and_is_reproducible(self):
        manifest = build_manifest(
            run_id="20260713T120000Z-smoke",
            stage="stage0",
            sources={"geniesim": "a04fe4f7fda0", "streamvln": "e48f6ff7e920"},
            config={"scene": "market_00_g2"},
        )
        self.assertFalse(manifest["official"])
        self.assertEqual(manifest["run_id"], "20260713T120000Z-smoke")
        self.assertIn("sources", manifest)

    def test_write_manifest_and_hash_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "artifact.bin"
            path.write_bytes(b"abc")
            self.assertEqual(sha256_file(path), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
            output = Path(tmp) / "run-manifest.json"
            write_manifest(output, {"official": False, "run_id": "r1"})
            self.assertFalse(json.loads(output.read_text(encoding="utf-8"))["official"])


if __name__ == "__main__":
    unittest.main()

