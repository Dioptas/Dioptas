"""The local native transport must stay usable during processing and bad input."""

import io
import json
import queue
import threading
import struct

import pytest

from dioptas.desktop.stdio import serve


def messages(output, binary):
    data = output.getvalue()
    if not binary:
        return [json.loads(line) for line in data.splitlines()]
    result = []
    while data:
        n, = struct.unpack('<I', data[:4])
        header = json.loads(data[4:4+n])
        assert header['buffers'] == []
        result.append(header)
        data = data[4+n:]
    return result

@pytest.mark.parametrize('binary', [False, True])

def test_protocol_rejects_bad_messages_and_still_processes_the_next_command(binary):
    class Session:
        closed = False

        def invoke(self, action, payload=None):
            return {"ok": True, "action": action}

        def close(self):
            self.closed = True

    session = Session()
    stream = io.StringIO('not json\n[]\n{"id":1,"action":42}\n{"id":2,"action":"state"}\n')
    output = io.BytesIO() if binary else io.StringIO()
    serve(stream, output, session, binary=binary)
    replies = messages(output, binary)
    assert len(replies) == 4
    assert sum(not message["result"]["ok"] for message in replies) == 3
    assert next(m for m in replies if m["id"] == 2)["result"]["action"] == "state"
    assert session.closed


@pytest.mark.parametrize('binary', [False, True])
def test_cancel_and_progress_bypass_busy_command_dispatch(binary):
    entered = threading.Event()
    cancelled = threading.Event()
    answered = threading.Event()
    inbox = queue.Queue()

    class Stream:
        def __iter__(self):
            while (line := inbox.get(timeout=5)) is not None:
                yield line

    class Protocol(io.BytesIO if binary else io.StringIO):
        def flush(self):
            if any(m["id"] == 5 for m in messages(self, binary)):
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
    host = threading.Thread(target=serve, args=(Stream(), output, Session()), kwargs={"binary": binary})
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
    replies = {m["id"]: m["result"] for m in messages(output, binary)}
    assert len(replies) == 6
    assert replies[4]["action"] == "progress"
