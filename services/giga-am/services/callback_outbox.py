"""Durable, bounded callback delivery. Mount the database directory persistently."""
import asyncio
import json
import logging
import sqlite3
import time
from pathlib import Path
from contextlib import contextmanager

from config import settings

logger = logging.getLogger(__name__)


class CallbackOutbox:
    @contextmanager
    def connect(self):
        path = Path(settings.callback_outbox_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(path)
        db.execute("""CREATE TABLE IF NOT EXISTS callbacks (
            task_id TEXT PRIMARY KEY, payload TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0, next_attempt REAL NOT NULL DEFAULT 0,
            state TEXT NOT NULL DEFAULT 'pending')""")
        try:
            with db:
                yield db
        finally:
            db.close()

    def enqueue(self, callback_url, task_id, status, result=None, error=None):
        payload = json.dumps(dict(callback_url=callback_url, task_id=task_id,
                                  status=status, result=result, error=error))
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO callbacks(task_id, payload) VALUES (?, ?)",
                       (task_id, payload))

    async def deliver(self, sender, task_id=None):
        # Claim and reserve an attempt atomically, including across processes.
        # An interrupted attempt becomes eligible again after its lease expires.
        with self.connect() as db:
            row = db.execute("""UPDATE callbacks SET attempts=attempts+1, next_attempt=?
                WHERE task_id=(SELECT task_id FROM callbacks
                    WHERE state='pending' AND attempts<? AND next_attempt<=?
                    AND (? IS NULL OR task_id=?) ORDER BY next_attempt LIMIT 1)
                RETURNING task_id, payload, attempts""",
                (time.time() + settings.callback_timeout + 60,
                 settings.callback_max_attempts, time.time(), task_id, task_id)).fetchone()
        if row is None:
            return
        task_id, payload, attempts = row
        delivered = False
        try:
            delivered = await asyncio.wait_for(sender(**json.loads(payload)),
                                                settings.callback_timeout)
        except Exception:
            logger.exception("Callback attempt failed for task %s", task_id)
        with self.connect() as db:
            db.execute("UPDATE callbacks SET state=?, next_attempt=? WHERE task_id=?",
                       ("delivered" if delivered else "pending",
                        time.time() + settings.callback_retry_seconds, task_id))
        if not delivered:
            logger.warning("Callback undelivered for task %s after %s attempt(s)", task_id, attempts)

    async def run(self, sender):
        while True:
            try:
                await self.deliver(sender)
            except Exception:
                logger.exception("Callback outbox worker failed")
            await asyncio.sleep(1)


callback_outbox = CallbackOutbox()
