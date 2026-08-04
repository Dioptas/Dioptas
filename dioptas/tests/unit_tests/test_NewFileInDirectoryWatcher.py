# SPDX-License-Identifier: MIT

"""The watcher polls the directory rather than listening for OS file events,
because those events never reach a network-filesystem client — the situation
at nearly every beamline. Polling also makes the tests deterministic: each
test drives poll_once() by hand instead of sleeping and hoping."""

import os
import shutil
import time

from ...model.util.NewFileWatcher import NewFileInDirectoryWatcher

unittest_data_path = os.path.join(os.path.dirname(__file__), "../data")


def make_watcher(tmp_path, **kwargs):
    kwargs.setdefault("file_types", ["tif"])
    watcher = NewFileInDirectoryWatcher(str(tmp_path), **kwargs)
    received = []
    watcher.file_added.connect(received.append)
    # what activate() does, minus the poll thread — the tests poll by hand
    watcher._take_baseline()
    return watcher, received


def test_new_file_is_emitted_once_written_and_stable(tmp_path):
    watcher, received = make_watcher(tmp_path)

    destination = os.path.join(tmp_path, "image_003.tif")
    shutil.copy2(os.path.join(unittest_data_path, "image_001.tif"), destination)

    # first sighting only records the file; the second poll finds it
    # unchanged and announces it
    watcher.poll_once()
    assert received == []
    watcher.poll_once()
    assert received == [os.path.abspath(destination)]

    # and never again
    watcher.poll_once()
    assert received == [os.path.abspath(destination)]


def test_growing_file_is_held_back_until_it_stops_changing(tmp_path):
    watcher, received = make_watcher(tmp_path)

    destination = tmp_path / "image_003.tif"
    with open(destination, "wb") as f:
        f.write(b"x" * 100)
        f.flush()
        watcher.poll_once()
        f.write(b"x" * 100)
        # mtime resolution can be coarser than this test is fast
        os.utime(destination, (time.time(), time.time() + 1))

    watcher.poll_once()
    assert received == [], "file changed between polls, must not be announced"
    watcher.poll_once()
    assert received == [str(destination)]


def test_empty_file_is_not_announced(tmp_path):
    watcher, received = make_watcher(tmp_path)

    destination = tmp_path / "image_003.tif"
    destination.touch()
    watcher.poll_once()
    watcher.poll_once()
    assert received == [], "a zero-byte placeholder is not a finished file"

    destination.write_bytes(b"content")
    watcher.poll_once()
    watcher.poll_once()
    assert received == [str(destination)]


def test_preexisting_files_are_not_emitted(tmp_path):
    (tmp_path / "old_image.tif").write_bytes(b"already there")
    watcher, received = make_watcher(tmp_path)

    watcher.poll_once()
    watcher.poll_once()
    assert received == []

    (tmp_path / "new_image.tif").write_bytes(b"new")
    watcher.poll_once()
    watcher.poll_once()
    assert received == [str(tmp_path / "new_image.tif")]


def test_only_watched_file_types_are_announced(tmp_path):
    watcher, received = make_watcher(tmp_path)

    (tmp_path / "notes.txt").write_bytes(b"not an image")
    (tmp_path / "image.tif").write_bytes(b"image")
    (tmp_path / "loud_image.TIF").write_bytes(b"image")  # detectors shout
    watcher.poll_once()
    watcher.poll_once()
    assert sorted(received) == [
        str(tmp_path / "image.tif"),
        str(tmp_path / "loud_image.TIF"),
    ]


def test_changing_the_path_starts_fresh(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (second / "existing.tif").write_bytes(b"was there before the switch")

    watcher, received = make_watcher(first)
    watcher.path = str(second)

    watcher.poll_once()
    watcher.poll_once()
    assert received == [], "files present before the switch are not new"

    (second / "fresh.tif").write_bytes(b"new")
    watcher.poll_once()
    watcher.poll_once()
    assert received == [str(second / "fresh.tif")]


def test_unreadable_directory_is_survived(tmp_path):
    watcher, received = make_watcher(tmp_path / "does_not_exist")
    watcher.poll_once()
    assert received == []


def test_batch_of_files_is_emitted_in_mtime_order(tmp_path):
    watcher, received = make_watcher(tmp_path)

    now = time.time()
    for index, name in enumerate(["c.tif", "a.tif", "b.tif"]):
        (tmp_path / name).write_bytes(b"image")
        os.utime(tmp_path / name, (now + index, now + index))

    watcher.poll_once()
    watcher.poll_once()
    assert received == [
        str(tmp_path / "c.tif"),
        str(tmp_path / "a.tif"),
        str(tmp_path / "b.tif"),
    ]


def test_deactivating_from_inside_a_handler_does_not_deadlock(tmp_path):
    # handlers run on the poll thread; a handler turning the watcher off
    # must not make deactivate() join the thread it is running on
    watcher = NewFileInDirectoryWatcher(
        str(tmp_path), file_types=["tif"], poll_interval=0.02
    )
    received = []

    def handler(path):
        received.append(path)
        watcher.deactivate()

    watcher.file_added.connect(handler)
    watcher.activate()
    try:
        (tmp_path / "image.tif").write_bytes(b"image")
        timeout = time.time() + 5.0
        while not received and time.time() < timeout:
            time.sleep(0.01)
    finally:
        watcher.deactivate()

    assert received == [str(tmp_path / "image.tif")]
    watcher._poll_thread.join(timeout=5.0)
    assert not watcher._poll_thread.is_alive()
    assert not watcher.active


def test_end_to_end_with_the_poll_thread(tmp_path):
    watcher = NewFileInDirectoryWatcher(
        str(tmp_path), file_types=["tif"], poll_interval=0.02
    )
    received = []
    watcher.file_added.connect(received.append)
    watcher.activate()
    try:
        destination = os.path.join(tmp_path, "image_003.tif")
        shutil.copy2(os.path.join(unittest_data_path, "image_001.tif"), destination)

        timeout = time.time() + 5.0
        while not received and time.time() < timeout:
            time.sleep(0.01)
    finally:
        watcher.deactivate()

    assert received == [os.path.abspath(destination)]
    assert not watcher._poll_thread.is_alive()
