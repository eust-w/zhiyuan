import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from adapter.protocol import EpisodeReset, EpisodeStep, build_observation
from adapter.service import AdapterService


class FakeBackend:
    def __init__(self, root: Path):
        self.root = root
        self.steps = 0

    def health(self):
        return {"scene": "market_00_g2", "robot": "G2_omnipicker", "ready": True}

    def reset(self, request: EpisodeReset):
        (self.root / "runs" / request.episode_id / "rgb").mkdir(parents=True)
        (self.root / "runs" / request.episode_id / "depth").mkdir(parents=True)
        return build_observation(
            episode_id=request.episode_id,
            step_id=0,
            rgb_path=f"runs/{request.episode_id}/rgb/000.jpg",
            depth_path=f"runs/{request.episode_id}/depth/000.png",
            pose_matrix=[1.0] * 16,
            distance_to_goal_m=2.0,
            collision=False,
            blocked=False,
            terminated=False,
            truncated=False,
        )

    def step(self, request: EpisodeStep):
        self.steps += 1
        return build_observation(
            episode_id="e1",
            step_id=self.steps,
            rgb_path=f"runs/e1/rgb/{self.steps:03d}.jpg",
            depth_path=f"runs/e1/depth/{self.steps:03d}.png",
            pose_matrix=[1.0] * 16,
            distance_to_goal_m=0.4 if request.action_id == 0 else 1.0,
            collision=False,
            blocked=False,
            terminated=request.action_id == 0,
            truncated=False,
        )

    def close(self, episode_id: str):
        return {"episode_id": episode_id, "closed": True}


class ServiceTests(unittest.TestCase):
    def request(self, url, payload=None):
        body = None if payload is None else json.dumps(payload).encode()
        req = Request(url, data=body, method="POST" if body else "GET", headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=2) as response:
            return response.status, json.loads(response.read())

    def test_health_reset_step_idempotency_and_close(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            backend = FakeBackend(root)
            service = AdapterService(root, backend, port=0)
            thread = threading.Thread(target=service.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{service.port}"
            self.assertTrue(self.request(base + "/health")[1]["ready"])
            status, reset = self.request(
                base + "/v1/episodes/reset",
                {
                    "schema_version": "geniesim-streamvln/v1",
                    "episode_id": "e1",
                    "seed": 1,
                    "instruction": "Go to the red target.",
                    "target_id": "red-target",
                },
            )
            self.assertEqual(status, 200)
            _, first = self.request(base + "/v1/episodes/e1/step", {"request_id": "r1", "action_id": 1})
            _, duplicate = self.request(base + "/v1/episodes/e1/step", {"request_id": "r1", "action_id": 1})
            self.assertEqual(first, duplicate)
            self.assertEqual(backend.steps, 1)
            self.assertEqual(self.request(base + "/v1/episodes/e1/close", {"episode_id": "e1"})[1]["closed"], True)
            service.shutdown()
            thread.join(timeout=2)

    def test_path_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            backend = FakeBackend(root)
            original = backend.step
            def unsafe(request):
                result = original(request)
                result["rgb_path"] = "../../secret.jpg"
                return result
            backend.step = unsafe
            service = AdapterService(root, backend, port=0)
            thread = threading.Thread(target=service.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{service.port}"
            self.request(base + "/v1/episodes/reset", {"episode_id": "e1", "seed": 1, "instruction": "x", "target_id": "y"})
            with self.assertRaises(HTTPError) as error:
                self.request(base + "/v1/episodes/e1/step", {"request_id": "r1", "action_id": 1})
            self.assertEqual(error.exception.code, 400)
            service.shutdown()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()

