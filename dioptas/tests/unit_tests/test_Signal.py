# SPDX-License-Identifier: MIT
import gc

import pytest

from dioptas.model.util.signal import Signal


def test_signal_with_sole_functions():
    signal = Signal()
    memory = []

    def f():
        memory.append(1)

    signal.connect(f)
    signal.emit()
    assert memory == [1]

    signal.disconnect(f)
    signal.emit()
    assert memory == [1]


def test_signal_with_bound_methods():
    signal = Signal()
    memory = []

    class A:
        def method(self):
            memory.append(1)

    a = A()
    signal.connect(a.method)
    signal.emit()
    assert memory == [1]

    signal.disconnect(a.method)
    signal.emit()
    assert memory == [1]


def test_bound_method_is_weakly_referenced():
    signal = Signal()
    memory = []

    class A:
        def method(self):
            memory.append(1)

    a = A()
    signal.connect(a.method)
    del a
    gc.collect()
    signal.emit()
    assert memory == []


def test_signal_with_signal():
    signal = Signal()
    memory = []

    signal2 = Signal()

    def f():
        memory.append(1)

    signal.connect(f)
    signal2.connect(signal)
    signal2.emit()

    assert memory == [1]

    signal2.disconnect(signal)
    signal2.emit()
    assert memory == [1]


def test_signal_with_priority():
    signal = Signal()
    memory = []

    def f():
        memory.append(1)

    def g():
        memory.append(2)

    signal.connect(f)
    signal.connect(g, priority=True)
    signal.emit()

    assert memory == [2, 1]


def test_emitted_args_are_passed_to_accepting_listeners_only():
    signal = Signal(float)
    memory = []

    def no_args():
        memory.append("none")

    def with_args(value):
        memory.append(value)

    signal.connect(no_args)
    signal.connect(with_args)
    signal.emit(1.5)

    assert memory == ["none", 1.5]


def test_blocked_attribute():
    signal = Signal()
    memory = []
    signal.connect(memory.append)

    signal.blocked = True
    assert signal.blocked is True
    signal.emit(1)
    assert memory == []

    signal.blocked = False
    assert signal.blocked is False
    signal.emit(1)
    assert memory == [1]


def test_block_unblock_methods():
    signal = Signal()
    memory = []

    def f():
        memory.append(1)

    signal.connect(f)
    signal.block()
    signal.emit()
    assert memory == []
    signal.unblock()
    signal.emit()
    assert memory == [1]


def test_clear():
    signal = Signal()
    memory = []

    def f():
        memory.append(1)

    signal.connect(f)
    signal.clear()
    signal.emit()
    assert memory == []


def test_has_listener():
    signal = Signal()

    def f():
        pass

    class A:
        def method(self):
            pass

    a = A()
    assert not signal.has_listener(f)
    signal.connect(f)
    signal.connect(a.method)
    assert signal.has_listener(f)
    assert signal.has_listener(a.method)

    signal.disconnect(f)
    assert not signal.has_listener(f)
    assert signal.has_listener(a.method)


def test_disconnecting_unconnected_handle_is_silent():
    signal = Signal()

    def f():
        pass

    signal.disconnect(f)  # must not raise


def test_listener_exceptions_propagate_unwrapped():
    signal = Signal()

    def boom():
        raise ValueError("boom")

    signal.connect(boom)
    with pytest.raises(ValueError, match="boom"):
        signal.emit()


def test_paused_batches_emissions():
    signal = Signal(int)
    memory = []
    signal.connect(memory.append)

    with signal.paused():
        signal.emit(1)
        signal.emit(2)
        assert memory == []
    assert memory == [1, 2]


def test_paused_with_reducer_emits_once():
    signal = Signal(int)
    memory = []
    signal.connect(memory.append)

    with signal.paused(reducer=lambda a, b: b):
        signal.emit(1)
        signal.emit(2)
        signal.emit(3)
    assert memory == [3]


def test_paused_flush_exceptions_propagate_unwrapped():
    signal = Signal()

    def boom():
        raise ValueError("boom")

    signal.connect(boom)
    with pytest.raises(ValueError, match="boom"):
        with signal.paused():
            signal.emit()
