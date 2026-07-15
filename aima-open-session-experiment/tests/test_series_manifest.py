import json
import tempfile
import unittest
from pathlib import Path


from scripts.series_manifest import load_manifest, validate_manifest


class SeriesManifestTests(unittest.TestCase):
    def test_valid_manifest_has_four_episodes_and_real_ratio_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "frame.jpg"
            source.write_bytes(b"jpg")
            manifest = {
                "schema_version": "aima-vln-series/v1",
                "real_ratio_target": 0.75,
                "episodes": [
                    {
                        "episode": f"stage{i}",
                        "title": f"Stage {i}",
                        "segments": [
                            {
                                "segment_id": f"stage{i}-01",
                                "source": "frame.jpg",
                                "source_type": "real_recording",
                                "evidence_ref": "evidence/log.txt",
                                "duration_s": 2.0,
                                "layout": "landscape",
                                "narration": "说明这一段真实证据。",
                                "subtitle": ["真实录屏"],
                            }
                        ],
                    }
                    for i in range(4)
                ],
            }
            path = root / "series.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            loaded = load_manifest(path)
            self.assertEqual(validate_manifest(loaded, root), [])

    def test_invalid_manifest_reports_missing_source_and_unlabelled_segment(self):
        manifest = {
            "schema_version": "aima-vln-series/v1",
            "real_ratio_target": 0.75,
            "episodes": [
                {
                    "episode": "stage0",
                    "title": "Stage 0",
                    "segments": [
                        {
                            "segment_id": "stage0-01",
                            "source": "missing.mp4",
                            "source_type": "",
                            "evidence_ref": "",
                            "duration_s": 0,
                            "layout": "square",
                        }
                    ],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            errors = validate_manifest(manifest, Path(tmp))
        self.assertTrue(any("episodes" in error for error in errors))
        self.assertTrue(any("missing.mp4" in error for error in errors))
        self.assertTrue(any("source_type" in error for error in errors))
        self.assertTrue(any("duration_s" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
