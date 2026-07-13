"""Loopback HTTP service that keeps Isaac operations behind one small contract."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from typing import Any, Protocol
from urllib.parse import unquote, urlparse

from .protocol import EpisodeReset, EpisodeStep, ProtocolError, safe_relative_path


class Backend(Protocol):
    def health(self) -> dict[str, Any]: ...

    def reset(self, request: EpisodeReset) -> dict[str, Any]: ...

    def step(self, request: EpisodeStep) -> dict[str, Any]: ...

    def close(self, episode_id: str) -> dict[str, Any]: ...


class AdapterService:
    def __init__(self, root: Path, backend: Backend, *, host: str = "127.0.0.1", port: int = 5802):
        self.root = root.expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.backend = backend
        self._lock = Lock()
        self._active: set[str] = set()
        self._request_cache: dict[tuple[str, str], dict[str, Any]] = {}
        service = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                service._dispatch(self, "GET")

            def do_POST(self):  # noqa: N802
                service._dispatch(self, "POST")

            def log_message(self, format: str, *args: Any) -> None:
                return

        self._httpd = ThreadingHTTPServer((host, port), Handler)
        self._httpd.daemon_threads = True
        self.host = host
        self.port = int(self._httpd.server_address[1])

    def serve_forever(self) -> None:
        self._httpd.serve_forever(poll_interval=0.1)

    def shutdown(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()

    def _dispatch(self, handler: BaseHTTPRequestHandler, method: str) -> None:
        try:
            parsed = urlparse(handler.path)
            if method == "GET" and parsed.path == "/health":
                payload = dict(self.backend.health())
                payload.update({"service": "geniesim-streamvln", "host": self.host, "port": self.port})
                self._write(handler, 200, payload)
                return
            if method != "POST":
                raise ProtocolError("method not allowed")
            # Close has no request fields; accepting an empty body keeps the
            # endpoint convenient for curl while still requiring JSON for
            # reset/step payloads.
            path_parts = [unquote(part) for part in parsed.path.split("/") if part]
            if path_parts == ["v1", "episodes", "reset"]:
                payload = self._read_json(handler)
                reset = EpisodeReset.from_json(payload)
                with self._lock:
                    self._active.add(reset.episode_id)
                result = self._normalize_response(self.backend.reset(reset))
                self._write(handler, 200, result)
                return
            if len(path_parts) == 4 and path_parts[:2] == ["v1", "episodes"] and path_parts[3] == "step":
                payload = self._read_json(handler)
                episode_id = path_parts[2]
                step = EpisodeStep.from_json(payload)
                with self._lock:
                    if episode_id not in self._active:
                        raise KeyError(f"unknown episode: {episode_id}")
                    cache_key = (episode_id, step.request_id)
                    if cache_key in self._request_cache:
                        self._write(handler, 200, self._request_cache[cache_key])
                        return
                result = self._normalize_response(self.backend.step(step))
                with self._lock:
                    self._request_cache[cache_key] = result
                self._write(handler, 200, result)
                return
            if len(path_parts) == 5 and path_parts[:3] == ["v1", "debug", "episodes"] and path_parts[4] == "step":
                payload = self._read_json(handler)
                episode_id = path_parts[3]
                step = EpisodeStep.from_debug_json(payload)
                with self._lock:
                    if episode_id not in self._active:
                        raise KeyError(f"unknown episode: {episode_id}")
                    cache_key = (episode_id, f"debug:{step.request_id}")
                    if cache_key in self._request_cache:
                        self._write(handler, 200, self._request_cache[cache_key])
                        return
                result = self._normalize_response(self.backend.step(step))
                with self._lock:
                    self._request_cache[cache_key] = result
                self._write(handler, 200, result)
                return
            if len(path_parts) == 4 and path_parts[:2] == ["v1", "episodes"] and path_parts[3] == "close":
                episode_id = path_parts[2]
                with self._lock:
                    if episode_id not in self._active:
                        raise KeyError(f"unknown episode: {episode_id}")
                    self._active.remove(episode_id)
                result = self.backend.close(episode_id)
                self._write(handler, 200, result)
                return
            raise ProtocolError("unknown endpoint")
        except KeyError as exc:
            self._write(handler, 404, {"error": str(exc)})
        except ProtocolError as exc:
            self._write(handler, 400, {"error": str(exc)})
        except Exception as exc:  # pragma: no cover - defensive boundary
            print(json.dumps({"event": "http_backend_error", "error_type": type(exc).__name__, "error": str(exc)}), flush=True)
            self._write(handler, 500, {"error": f"internal adapter error: {type(exc).__name__}"})

    @staticmethod
    def _read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
        raw_length = handler.headers.get("Content-Length", "0")
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise ProtocolError("invalid Content-Length") from exc
        if length < 0 or length > 1_048_576:
            raise ProtocolError("request body is too large")
        try:
            payload = json.loads(handler.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProtocolError("request body must be UTF-8 JSON") from exc
        if not isinstance(payload, dict):
            raise ProtocolError("request body must be a JSON object")
        return payload

    def _normalize_response(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ProtocolError("backend response must be an object")
        for key in ("rgb_path", "depth_path"):
            value = payload.get(key)
            if not isinstance(value, str) or not value:
                raise ProtocolError(f"backend response missing {key}")
            relative = Path(value)
            if relative.is_absolute() or ".." in relative.parts:
                raise ProtocolError(f"backend response path escapes root: {key}")
            payload[key] = safe_relative_path(self.root, self.root / relative)
        return payload

    @staticmethod
    def _write(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json; charset=utf-8")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)
