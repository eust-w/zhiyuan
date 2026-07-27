import json
import tempfile
import unittest
from pathlib import Path

from scripts.challenge_video_contract import scan_public_bundle
from scripts.synthesize_challenge_voice import (
    build_voice_metadata,
    choose_voice,
    load_narration,
    pause_schedule,
    run_with_retries,
    split_sections,
    split_text_chunks,
    validate_audio,
)


ROOT = Path(__file__).resolve().parents[1]


class ChallengeVoiceTests(unittest.TestCase):
    def test_loads_eight_ordered_narration_sections(self):
        source = load_narration(ROOT / "content/challenge-video/narration-sections.json")
        sections = split_sections(source)

        self.assertEqual(len(sections), 8)
        self.assertEqual(sections[0]["chapter_id"], "hook")
        self.assertEqual(sections[-1]["chapter_id"], "closing")

    def test_chunks_never_exceed_260_characters(self):
        text = "第一句很短。" + "甲" * 290 + "，最后一句结束。"

        chunks = split_text_chunks(text, max_chars=260)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk["text"]) <= 260 for chunk in chunks))
        self.assertEqual("".join(chunk["text"] for chunk in chunks), text)

    def test_pause_schedule_uses_sentence_boundaries(self):
        self.assertEqual(pause_schedule("第一句。第二句。"), [320, 320])
        self.assertEqual(pause_schedule("先做一件事；再做另一件事。"), [220, 320])

    def test_voice_selection_prefers_deep_male_candidate(self):
        candidates = [
            {"voice": "zh-CN-YunjianNeural", "rate": "-6%", "pitch": "-6Hz"},
            {"voice": "zh-CN-YunxiNeural", "rate": "-8%", "pitch": "-4Hz"},
        ]

        selected = choose_voice(candidates, {"zh-CN-YunxiNeural", "zh-CN-YunjianNeural"})

        self.assertEqual(selected["voice"], "zh-CN-YunjianNeural")

    def test_voice_selection_records_fallback(self):
        candidates = [
            {"voice": "zh-CN-YunjianNeural", "rate": "-6%", "pitch": "-6Hz"},
            {"voice": "zh-CN-YunxiNeural", "rate": "-8%", "pitch": "-4Hz"},
        ]

        selected = choose_voice(candidates, {"zh-CN-YunxiNeural"})

        self.assertEqual(selected["voice"], "zh-CN-YunxiNeural")
        self.assertEqual(selected["selection"], "fallback")

    def test_retry_stops_after_success(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "voice.mp3"
            attempts = []

            def operation():
                attempts.append(1)
                if len(attempts) < 3:
                    raise RuntimeError("temporary failure")
                output.write_bytes(b"audio")

            run_with_retries(
                operation,
                output,
                validator=lambda path: path.read_bytes() == b"audio",
                attempts=3,
            )

            self.assertEqual(len(attempts), 3)

    def test_retry_raises_after_three_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "voice.mp3"
            attempts = []

            def operation():
                attempts.append(1)
                raise RuntimeError("temporary failure")

            with self.assertRaisesRegex(RuntimeError, "after 3 attempts"):
                run_with_retries(
                    operation,
                    output,
                    validator=lambda _path: False,
                    attempts=3,
                )

            self.assertEqual(len(attempts), 3)

    def test_zero_byte_audio_is_rejected_without_probing(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "voice.mp3"
            output.touch()

            self.assertFalse(validate_audio(output, probe=lambda _path: 1.0))

    def test_metadata_has_hashes_durations_and_no_public_hits(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            work = Path(directory)
            narration = work / "narration.json"
            narration.write_text(
                json.dumps(
                    {
                        "sections": [
                            {"chapter_id": "hook", "title": "开场", "text": "真实录屏开始。"}
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            audio = work / "hook.mp3"
            audio.write_bytes(b"audio")
            combined = work / "challenge-voice.mp3"
            combined.write_bytes(b"combined")

            metadata = build_voice_metadata(
                root=ROOT,
                narration_path=narration,
                selected={
                    "voice": "zh-CN-YunjianNeural",
                    "rate": "-6%",
                    "pitch": "-6Hz",
                    "selection": "preferred",
                },
                section_outputs=[("hook", audio)],
                audition_outputs=[],
                combined_output=combined,
                duration_probe=lambda path: 12.5 if path == combined else 2.5,
            )

            self.assertEqual(metadata["section_count"], 1)
            self.assertIn("sha256", metadata["sections"][0])
            self.assertEqual(metadata["duration_s"], 12.5)
            self.assertEqual(scan_public_bundle(metadata), [])


if __name__ == "__main__":
    unittest.main()
