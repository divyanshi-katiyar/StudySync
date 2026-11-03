"""Real-time push with Server-Sent Events (SSE).

Why SSE and not Socket.io: the app only needs server -> browser updates (new notification, "something changed in your group").
SSE is plain HTTP, needs no extra package, works with the existing JWT bearer header (the client reads the stream with fetch),
and Week 1 listed it as the one-way alternative to Socket.io. User actions still travel over normal REST calls.

Flow: a service writes to the database and calls queue_event(); the app flushes the queued events to the Hub only after the
response is built (so the transaction has been committed and a client that reloads immediately sees the new data); each
connected stream has its own queue and writes events out as they arrive.
"""
import json
import queue
import threading
import time

from flask import g

QUEUE_SIZE = 200


class Subscriber:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.queue: queue.Queue = queue.Queue(maxsize=QUEUE_SIZE)


class Hub:
    def __init__(self):
        self._subs: dict[str, set[Subscriber]] = {}
        self._lock = threading.Lock()
        self._counter = 0

    def subscribe(self, user_id: str, max_per_user: int):
        with self._lock:
            subs = self._subs.setdefault(user_id, set())
            if len(subs) >= max_per_user:
                return None
            sub = Subscriber(user_id)
            subs.add(sub)
            return sub

    def unsubscribe(self, sub: Subscriber):
        with self._lock:
            subs = self._subs.get(sub.user_id)
            if subs:
                subs.discard(sub)
                if not subs:
                    del self._subs[sub.user_id]

    def count(self, user_id: str | None = None) -> int:
        with self._lock:
            if user_id:
                return len(self._subs.get(user_id, ()))
            return sum(len(s) for s in self._subs.values())

    def publish(self, user_ids, event_type: str, data: dict):
        with self._lock:
            self._counter += 1
            event_id = self._counter
            targets = [s for uid in set(user_ids) for s in self._subs.get(uid, ())]
        for sub in targets:
            try:
                sub.queue.put_nowait((event_id, event_type, data))
            except queue.Full:  # a stalled client: drop its backlog and tell it to reload everything
                try:
                    while True:
                        sub.queue.get_nowait()
                except queue.Empty:
                    pass
                sub.queue.put_nowait((event_id, "resync", {}))


def queue_event(user_ids, event_type: str, data: dict):
    """Remember an event for the current request; it is sent after the response succeeds."""
    user_ids = list(user_ids)
    if user_ids:
        g.setdefault("pending_events", []).append((user_ids, event_type, data))


def flush_events(hub: Hub, status_code: int):
    events = g.pop("pending_events", [])
    if status_code < 400:
        for user_ids, event_type, data in events:
            hub.publish(user_ids, event_type, data)


def format_event(event_id: int, event_type: str, data: dict) -> str:
    return f"id: {event_id}\nevent: {event_type}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"


def event_stream(hub: Hub, sub: Subscriber, user_id: str, expires_at: float, heartbeat: float):
    """Generator behind GET /api/stream. Ends when the access token expires so the client must refresh and reconnect."""
    try:
        yield "retry: 3000\n\n"
        yield format_event(0, "ready", {"userId": user_id})
        while True:
            remaining = expires_at - time.time()
            if remaining <= 0:
                yield format_event(0, "token-expired", {})
                return
            try:
                event_id, event_type, data = sub.queue.get(timeout=max(0.05, min(heartbeat, remaining)))
            except queue.Empty:
                yield ": ping\n\n"  # keeps proxies from closing an idle connection
                continue
            yield format_event(event_id, event_type, data)
    finally:
        hub.unsubscribe(sub)
