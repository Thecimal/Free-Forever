import time

import pytest

from qs_orchestrator.composite import CompositeSource, elapsed_ms
from qs_orchestrator.contract import Result, Task
from qs_orchestrator.source import Availability, Source


class StubSource:
    type = "api"
    capabilities = frozenset({"text"})

    def __init__(self, source_id):
        self.id = source_id

    def execute(self, task):
        raise AssertionError("not used")

    def availability(self):
        return Availability(True)


class AlwaysFails(CompositeSource):
    def execute(self, task):
        return self._all_failed(["x: boom", "y: bang"], time.perf_counter())


def test_base_class_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        CompositeSource([StubSource("a")], source_id="c")


def test_empty_sources_are_rejected_with_the_subclass_name():
    with pytest.raises(ValueError) as info:
        AlwaysFails([], source_id="c")
    assert str(info.value) == "AlwaysFails needs at least one source"


def test_subclass_is_a_source_with_shared_attributes():
    composite = AlwaysFails([StubSource("a")], source_id="pool")
    assert isinstance(composite, Source)
    assert composite.id == "pool"
    assert composite.type == "composite"
    assert composite.capabilities == frozenset({"text"})
    assert composite.availability() == Availability(True)


def test_all_failed_builds_the_standard_error_result():
    result = AlwaysFails([StubSource("a")], source_id="pool").execute(Task(prompt="p"))
    assert isinstance(result, Result)
    assert result.status == "error"
    assert result.source == "pool"
    assert result.content == ""
    assert result.model == ""
    assert result.error == "all sources failed: x: boom; y: bang"
    assert isinstance(result.latency_ms, int) and result.latency_ms >= 0


def test_elapsed_ms_is_a_non_negative_int():
    assert isinstance(elapsed_ms(time.perf_counter()), int)
    assert elapsed_ms(time.perf_counter()) >= 0
