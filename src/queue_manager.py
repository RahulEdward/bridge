"""
Queue Manager — async task queue for serializing MT5 instance operations.
Uses asyncio.Queue as the default backend. Optionally uses Redis if available.

Prevents race conditions when multiple requests try to create/start/stop
the same user's instance simultaneously.
"""

import asyncio
import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional, Callable, Awaitable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class QueueTask:
    task_id: str
    user_id: str
    action: str  # create | start | stop | restart | destroy
    params: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "pending"  # pending | processing | completed | failed
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class QueueManager:
    """
    Per-user task queue ensuring operations on the same account are serialized.
    Different users can be processed concurrently.
    """

    def __init__(self):
        self._user_locks: Dict[str, asyncio.Lock] = {}
        self._task_counter = 0
        self._tasks: Dict[str, QueueTask] = {}
        self._handlers: Dict[str, Callable[..., Awaitable]] = {}
        self._worker_task: Optional[asyncio.Task] = None
        self._queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        # Redis client (optional)
        self._redis = None

    async def start(self):
        """Start the queue worker."""
        self._running = True
        self._worker_task = asyncio.create_task(self._process_loop())
        await self._try_connect_redis()
        logger.info("Queue Manager started")

    async def stop(self):
        """Stop the queue worker."""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        if self._redis:
            try:
                await self._redis.close()
            except Exception:
                pass
        logger.info("Queue Manager stopped")

    def register_handler(self, action: str, handler: Callable[..., Awaitable]):
        """Register a handler for a specific action type."""
        self._handlers[action] = handler

    async def enqueue(
        self, user_id: str, action: str, params: Dict[str, Any] = None
    ) -> QueueTask:
        """Add a task to the queue. Returns immediately with task reference."""
        self._task_counter += 1
        task_id = f"task_{self._task_counter}_{user_id}"

        task = QueueTask(
            task_id=task_id,
            user_id=user_id,
            action=action,
            params=params or {},
        )
        self._tasks[task_id] = task

        await self._queue.put(task)

        # Publish to Redis if available
        if self._redis:
            try:
                await self._redis.publish(
                    "mt5_gateway:tasks",
                    json.dumps({"task_id": task_id, "user_id": user_id, "action": action}),
                )
            except Exception:
                pass

        logger.info(f"Task enqueued: {task_id} ({action} for {user_id})")
        return task

    def get_task(self, task_id: str) -> Optional[QueueTask]:
        return self._tasks.get(task_id)

    def get_user_lock(self, user_id: str) -> asyncio.Lock:
        """Get or create a per-user lock."""
        if user_id not in self._user_locks:
            self._user_locks[user_id] = asyncio.Lock()
        return self._user_locks[user_id]

    async def _process_loop(self):
        """Main processing loop — picks tasks from queue and executes them."""
        while self._running:
            try:
                task = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            # Process in background, but serialize per user
            asyncio.create_task(self._execute_task(task))

    async def _execute_task(self, task: QueueTask):
        """Execute a single task, holding the per-user lock."""
        lock = self.get_user_lock(task.user_id)

        async with lock:
            task.status = "processing"
            handler = self._handlers.get(task.action)

            if not handler:
                task.status = "failed"
                task.error = f"No handler for action: {task.action}"
                logger.error(task.error)
                return

            try:
                result = await handler(task.user_id, task.params)
                task.status = "completed"
                task.result = result
                logger.info(f"Task completed: {task.task_id}")
            except Exception as e:
                task.status = "failed"
                task.error = str(e)
                logger.error(f"Task failed: {task.task_id} — {e}")

    async def _try_connect_redis(self):
        """Try to connect to Redis. Falls back to in-memory queue if unavailable."""
        try:
            import redis.asyncio as aioredis
            self._redis = aioredis.from_url(
                "redis://localhost:6379", decode_responses=True
            )
            await self._redis.ping()
            logger.info("Redis connected — using Redis for task pub/sub")
        except Exception:
            self._redis = None
            logger.info("Redis not available — using in-memory queue (fine for single-node)")


# Singleton
queue_manager = QueueManager()
