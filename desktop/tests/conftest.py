"""Release scientific model cycles on the test's processing thread."""

import gc
import threading
import weakref

import pytest


@pytest.fixture(autouse=True)
def release_scientific_cycles(monkeypatch):
    from dioptas.desktop.session import DesktopSession

    sessions = []
    initialize = DesktopSession.__init__

    def track(session, *args, **kwargs):
        initialize(session, *args, **kwargs)
        sessions.append((threading.get_ident(), weakref.ref(session)))

    monkeypatch.setattr(DesktopSession, "__init__", track)
    yield
    for owner, reference in sessions:
        session = reference()
        if owner == threading.get_ident() and session is not None:
            session.close()
    # Direct-session tests own native objects on this thread. Do not leave
    # garbage for a later DesktopBridge worker's gc.collect() to release.
    gc.collect()
