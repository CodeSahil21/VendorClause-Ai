# Standard library
import asyncio
import json
import logging
import signal
import uuid
from typing import Any

# Local
from src.retrieval.fusion import _get_cross_encoder
from src.retrieval.graph import build_graph, close_graph_resources
from src.shared.database_service import get_database_service
from src.shared.langfuse_config import trace_query, update_trace
from src.shared.redis_client import close_shared_redis, create_redis_client

logger = logging.getLogger(__name__)


class QueryWorker:
    def __init__(self):
        self.redis = create_redis_client()
        self.db = get_database_service()
        self.graph = build_graph()
        self._active_tasks: set[asyncio.Task] = set()
        self._shutdown_event: asyncio.Event | None = None
        self._heartbeat_task: asyncio.Task | None = None

    async def _publish_stream(self, session_id: str, event: str, payload: dict) -> None:
        channel = f"query:stream:{session_id}"
        await self.redis.publish(channel, json.dumps({"event": event, "payload": payload}))

    @staticmethod
    def _build_initial_state(
        question: str,
        session_id: str,
        document_id: str,
        user_id: str,
        chat_history: list[dict[str, Any]],
    ) -> dict[str, Any]:
        # Seed canonical defaults so all nodes observe a consistent state shape,
        # including graph_only paths that may skip the rewriter node.
        return {
            "question": question,
            "session_id": session_id,
            "document_id": document_id,
            "user_id": user_id,
            "chat_history": chat_history,
            "crag_iteration": 0,
            "rewritten_query": question,
            "sub_queries": [],
            "intent": "factual",
            "jurisdiction": "unknown",
            "clause_types": [],
            "entities": [],
            "strategy": "hybrid",
            "mem0_context": "",
        }

    @trace_query(name="retrieval_pipeline")
    async def _process_query(self, payload: dict) -> None:
        question = payload.get("question", "")
        session_id = payload.get("sessionId", "")
        document_id = payload.get("documentId", "")
        user_id = payload.get("userId", "")

        if not all([question, session_id, document_id, user_id]):
            logger.error("Invalid query payload: %s", payload)
            if session_id:
                await self._publish_stream(
                    session_id,
                    "stream:error",
                    {"message": "Invalid query payload: required fields are missing."},
                )
            return

        update_trace({
            "session_id": session_id,
            "document_id": document_id,
            "user_id": user_id,
            "stage": "query_start",
        })

        try:
            await asyncio.to_thread(
                self.db.save_message,
                session_id,
                "USER",
                question,
                None,
            )
        except Exception:
            logger.warning("Failed to persist USER message for session %s", session_id)

        chat_history = await asyncio.to_thread(self.db.get_chat_history, session_id, 6)

        initial_state = self._build_initial_state(
            question=question,
            session_id=session_id,
            document_id=document_id,
            user_id=user_id,
            chat_history=chat_history,
        )

        try:
            await self.graph.ainvoke(
                initial_state,
                config={"configurable": {"thread_id": f"{session_id}:{uuid.uuid4()}"}},
            )
        except asyncio.CancelledError:
            logger.warning("Query cancelled for session %s", session_id)
            await self._publish_stream(
                session_id,
                "stream:error",
                {"message": "Query interrupted while shutting down."},
            )
            raise
        except Exception as exc:
            logger.exception("Query processing failed for session %s", session_id)
            await self._publish_stream(session_id, "stream:error", {"message": str(exc)})

    def _install_signal_handlers(self) -> None:
        def _request_shutdown() -> None:
            if self._shutdown_event is not None and not self._shutdown_event.is_set():
                logger.info("Shutdown signal received")
                self._shutdown_event.set()

        for sig_name in ("SIGTERM", "SIGINT"):
            sig = getattr(signal, sig_name, None)
            if sig is None:
                continue
            try:
                asyncio.get_running_loop().add_signal_handler(sig, _request_shutdown)
            except (NotImplementedError, RuntimeError):
                signal.signal(sig, lambda _s, _f: _request_shutdown())

    async def _heartbeat_loop(self) -> None:
        while self._shutdown_event is not None and not self._shutdown_event.is_set():
            try:
                await self.redis.set("query-worker:heartbeat", "1", ex=15)
            except Exception:
                logger.warning("Failed to publish QueryWorker heartbeat", exc_info=True)
            await asyncio.sleep(5)

    async def _shutdown(self, pubsub) -> None:
        from src.retrieval.nodes.mcp_orchestrator import _mcp_client

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            await asyncio.gather(self._heartbeat_task, return_exceptions=True)

        if self._active_tasks:
            logger.info("Cancelling %d active query tasks", len(self._active_tasks))
            for task in list(self._active_tasks):
                task.cancel()
            await asyncio.gather(*self._active_tasks, return_exceptions=True)

        await pubsub.punsubscribe("query:request:*")
        await pubsub.close()
        await _mcp_client.aclose()
        await self.redis.close()
        await close_shared_redis()
        close_graph_resources()

    async def run(self) -> None:
        self._shutdown_event = asyncio.Event()
        self._install_signal_handlers()

        # Pre-warm cross-encoder after the event loop is running.
        asyncio.get_running_loop().run_in_executor(None, _get_cross_encoder)

        pubsub = self.redis.pubsub()
        await pubsub.psubscribe("query:request:*")
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        logger.info("QueryWorker subscribed to query:request:*")

        try:
            while not self._shutdown_event.is_set():
                message = await pubsub.get_message(ignore_subscribe_messages=False, timeout=1.0)
                if not message or message.get("type") != "pmessage":
                    continue

                try:
                    data = json.loads(message.get("data", "{}"))
                except Exception:
                    logger.error("Invalid query message payload: %s", message)
                    continue

                task = asyncio.create_task(self._process_query(data))
                self._active_tasks.add(task)
                task.add_done_callback(self._active_tasks.discard)
        finally:
            await self._shutdown(pubsub)


async def main() -> None:
    worker = QueryWorker()
    await worker.run()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
