# SPDX-License-Identifier: MIT
import gc

from dioptas.model.util.signal import Signal, WeakRefList


def test_weakreflist_with_objects():
    weak_ref_list = WeakRefList()

    class A(str):
        pass

    a = A()
    weak_ref_list.append(a)
    assert len(weak_ref_list) == 1
    assert weak_ref_list[0]() == a

    del a
    gc.collect()
    assert len(weak_ref_list) == 0


def test_weakreflist_with_bound_methods():
    weak_ref_list = WeakRefList()

    class A:
        def method(self):
            return "lala"

    a = A()
    weak_ref_list.append(a.method)

    assert len(weak_ref_list) == 1
    assert weak_ref_list[0]()() == "lala"

    del a
    gc.collect()
    assert len(weak_ref_list) == 0


def test_weakreflist_with_insertion():
    weak_ref_list = WeakRefList()

    class A:
        def method(self):
            return "lala"

    a = A()
    weak_ref_list.insert(0, a.method)

    assert len(weak_ref_list) == 1
    assert weak_ref_list[0]()() == "lala"

    del a
    gc.collect()
    assert len(weak_ref_list) == 0


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
