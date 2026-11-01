"""The local native transport must stay usable during processing and bad input."""

import io
import json
import queue
import threading

from dioptas.desktop.stdio import serve


def test_protocol_rejects_bad_messages_and_still_processes_the_next_command():
    class Session:
        closed = False

        def invoke(self, action, payload=None):
            return {"ok": True, "action": action}

        def close(self):
            self.closed = True

    session = Session()
    stream = io.StringIO('not json\n[]\n{"id":1,"action":42}\n{"id":2,"action":"state"}\n')
    output = io.StringIO()
    serve(stream, output, session)
    messages = [json.loads(line) for line in output.getvalue().splitlines()]
    assert len(messages) == 4
    assert sum(not message["result"]["ok"] for message in messages) == 3
    assert next(m for m in messages if m["id"] == 2)["result"]["action"] == "state"
    assert session.closed


def test_cancel_and_progress_bypass_busy_command_dispatch():
    entered = threading.Event()
    cancelled = threading.Event()
    answered = threading.Event()
    inbox = queue.Queue()

    class Stream:
        def __iter__(self):
            while (line := inbox.get(timeout=5)) is not None:
                yield line

    class Protocol(io.StringIO):
        def flush(self):
            messages = [json.loads(line) for line in self.getvalue().splitlines()]
            if any(m["id"] == 5 for m in messages):
                answered.set()

    class Session:
        def invoke(self, action, payload=None):
            if action == "blocked":
                entered.set()
                assert cancelled.wait(5), "Cancel was queued behind blocked processing"
            if action == "cancel_refinement":
                cancelled.set()
            return {"ok": True, "action": action}

        def close(self):
            pass

    output = Protocol()
    host = threading.Thread(target=serve, args=(Stream(), output, Session()))
    host.start()
    try:
        # Occupy every request worker. Cancel must still be read immediately.
        for identifier in range(4):
            inbox.put(json.dumps({"id": identifier, "action": "blocked"}))
        assert entered.wait(5)
        inbox.put(json.dumps({"id": 4, "action": "progress"}))
        inbox.put(json.dumps({"id": 5, "action": "cancel_refinement"}))
        assert answered.wait(5)
        assert cancelled.is_set()
    finally:
        cancelled.set()
        inbox.put(None)
        host.join(timeout=5)
    assert not host.is_alive()
    replies = {m["id"]: m["result"] for m in map(json.loads, output.getvalue().splitlines())}
    assert len(replies) == 6
    assert replies[4]["action"] == "progress"
