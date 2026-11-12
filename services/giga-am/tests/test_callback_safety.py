import asyncio
import io
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Avoid importing GPU/model dependencies for route and delivery unit tests.
pipeline = types.ModuleType("services.pipeline_service")
pipeline.PipelineService = type("PipelineService", (), {})
sys.modules.setdefault("services.pipeline_service", pipeline)

import httpx
from fastapi import HTTPException, UploadFile
from config import settings
from utils.callback_network import CallbackBackend, validate_callback_url
from utils.file_validation import read_upload_with_limit
from services.callback_outbox import CallbackOutbox
from routes import transcribe_async as route


class SafetyTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old = settings.model_dump()
        settings.callback_allowed_hosts = ["hooks.example"]
        settings.callback_allowed_networks = ["192.0.2.0/24"]
        settings.callback_outbox_path = self.temp.name + "/outbox.sqlite3"

    def tearDown(self):
        for key, value in self.old.items():
            setattr(settings, key, value)
        self.temp.cleanup()

    async def test_filename_source_and_missing_name(self):
        self.assertEqual(await read_upload_with_limit(
            UploadFile(io.BytesIO(b"audio"), filename="wrong.exe"), "audio.WAV"), b"audio")
        for name in ("audio.exe", ""):
            with self.assertRaises(HTTPException):
                await read_upload_with_limit(UploadFile(io.BytesIO(b"audio"), filename="audio.wav"), name)

    async def test_url_validation_before_task_creation(self):
        for url in ("ftp://hooks.example", "https://evil.example", "https://user@hooks.example", "no-url"):
            with self.assertRaises(ValueError):
                validate_callback_url(url)
            with patch.object(route.task_manager, "create_task") as create:
                with self.assertRaises(HTTPException) as caught:
                    await route.transcribe_async(UploadFile(io.BytesIO(b"a")), "a.wav", url)
                self.assertEqual(caught.exception.status_code, 400)
                create.assert_not_called()
        self.assertEqual(validate_callback_url("https://hooks.example/path").host, "hooks.example")

    async def test_valid_url_still_accepted(self):
        with patch.object(route, "process_task_background", AsyncMock()):
            response = await route.transcribe_async(
                UploadFile(io.BytesIO(b"audio"), filename="wrong.exe"),
                "audio.wav", "https://hooks.example/path")
            self.assertEqual(response.status_code, 202)
            await asyncio.gather(*route.BACKGROUND_TASKS)
        import json
        route.task_manager.tasks.pop(json.loads(response.body)["task_id"])

    async def test_dns_pinning_and_peer_policy(self):
        backend = CallbackBackend()
        stream = AsyncMock()
        stream.get_extra_info = lambda key: ("192.0.2.10", 443)
        backend.backend.connect_tcp = AsyncMock(return_value=stream)
        loop = asyncio.get_running_loop()
        with patch.object(loop, "getaddrinfo", AsyncMock(return_value=[(2, 1, 6, "", ("192.0.2.10", 443))])):
            await backend.connect_tcp("hooks.example", 443, timeout=1)
            self.assertEqual(backend.backend.connect_tcp.call_args.args[0], "192.0.2.10")
            stream.get_extra_info = lambda key: ("127.0.0.1", 443)
            with self.assertRaises(ValueError):
                await backend.connect_tcp("hooks.example", 443, timeout=1)
            stream.aclose.assert_awaited_once()
        backend.backend.connect_tcp.reset_mock()
        with patch.object(loop, "getaddrinfo", AsyncMock(return_value=[(2, 1, 6, "", ("127.0.0.1", 443))])):
            with self.assertRaises(ValueError):
                await backend.connect_tcp("hooks.example", 443, timeout=1)
            backend.backend.connect_tcp.assert_not_called()

    async def test_response_limit_and_log_prefix(self):
        settings.callback_response_max_bytes = 8192
        class Body(httpx.AsyncByteStream):
            closed = False
            reads = 0
            async def __aiter__(self):
                for _ in range(100):
                    self.reads += 1
                    yield b"x" * 4096
            async def aclose(self):
                self.closed = True
        body = Body()
        transport = httpx.MockTransport(lambda req: httpx.Response(200, stream=body))
        with patch.object(route, "CallbackTransport", return_value=transport):
            self.assertFalse(await route.send_webhook_callback("https://hooks.example", "task", "completed"))
        self.assertTrue(body.closed)
        self.assertLessEqual(body.reads, 3)
        transport = httpx.MockTransport(lambda req: httpx.Response(500, stream=httpx.ByteStream(b"x" * 5000)))
        with patch.object(route, "CallbackTransport", return_value=transport), self.assertLogs(route.logger, "ERROR") as logs:
            self.assertFalse(await route.send_webhook_callback("https://hooks.example", "task", "failed"))
        self.assertLess(len(logs.output[0]), 1200)

    async def test_durable_bounded_retries(self):
        outbox = CallbackOutbox()
        outbox.enqueue("https://hooks.example", "task", "completed", result={"text": "test"})
        sender = AsyncMock(return_value=False)
        for _ in range(settings.callback_max_attempts + 2):
            with CallbackOutbox().connect() as db:
                db.execute("UPDATE callbacks SET next_attempt=0")
            await CallbackOutbox().deliver(sender)
        self.assertEqual(sender.await_count, settings.callback_max_attempts)
        with CallbackOutbox().connect() as db:
            self.assertEqual(db.execute("SELECT state FROM callbacks").fetchone()[0], "pending")

    async def test_real_http_transport(self):
        settings.callback_allowed_hosts = ["localhost"]
        settings.callback_allowed_networks = ["127.0.0.0/8", "::1/128"]
        received = []
        async def handle(reader, writer):
            headers = await reader.readuntil(b"\r\n\r\n")
            received.append(headers)
            writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok")
            await writer.drain()
            writer.close()
            await writer.wait_closed()
        server = await asyncio.start_server(handle, "127.0.0.1", 0)
        try:
            port = server.sockets[0].getsockname()[1]
            # Keep DNS deterministic while exercising a real socket and peer check.
            loop = asyncio.get_running_loop()
            original = loop.getaddrinfo
            async def resolve(host, port, **kwargs):
                return await original("127.0.0.1", port, **kwargs)
            with patch.object(loop, "getaddrinfo", resolve):
                self.assertTrue(await route.send_webhook_callback(
                    f"http://localhost:{port}/hook", "task", "completed"))
            self.assertIn(b"POST /hook HTTP/1.1", received[0])
            self.assertIn(b"Host: localhost:", received[0])
        finally:
            server.close()
            await server.wait_closed()

    async def test_both_transcription_outcomes_persist_callback(self):
        for fails in (False, True):
            task = route.task_manager.create_task("a.wav", b"a", {"callback_url": "https://hooks.example"})
            process = AsyncMock(side_effect=ValueError("failed")) if fails else AsyncMock(return_value={"text": "ok"})
            with patch.object(route.pipeline_service, "process_audio_sync", process, create=True), patch.object(route, "send_webhook_callback", AsyncMock(return_value=False)), patch.object(route, "send_inngest_event", AsyncMock()):
                await route.process_task_background(task.task_id)
            with CallbackOutbox().connect() as db:
                row = db.execute("SELECT state, attempts, payload FROM callbacks WHERE task_id=?", (task.task_id,)).fetchone()
            self.assertEqual(row[:2], ("pending", 1))
            self.assertIn('"status": "failed"' if fails else '"status": "completed"', row[2])
            route.task_manager.tasks.pop(task.task_id)

    async def test_success_stops_retries(self):
        outbox = CallbackOutbox()
        outbox.enqueue("https://hooks.example", "task", "failed", error="test")
        sender = AsyncMock(return_value=True)
        await outbox.deliver(sender)
        await CallbackOutbox().deliver(sender)
        sender.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
