import asyncio

import pytest

from app.services.ai_runtime import (
    AIBusyUnloadingError,
    AIInferencesInProgressError,
    AIUnloadInProgressError,
    InferenceGate,
)


def test_unload_is_refused_while_an_inference_is_running() -> None:
    gate = InferenceGate()

    async def scenario() -> None:
        async with gate.inference():
            with pytest.raises(AIInferencesInProgressError):
                async with gate.unload():
                    raise AssertionError("o unload não deve começar")

    asyncio.run(scenario())
    assert gate.in_flight == 0
    assert gate.unloading is False


def test_new_inference_is_blocked_during_unload() -> None:
    gate = InferenceGate()
    started = asyncio.Event()
    release = asyncio.Event()

    async def do_unload() -> None:
        async with gate.unload():
            started.set()
            await release.wait()

    async def scenario() -> None:
        task = asyncio.create_task(do_unload())
        await started.wait()
        with pytest.raises(AIBusyUnloadingError):
            async with gate.inference():
                raise AssertionError("a inferência não deve começar")
        release.set()
        await task

    asyncio.run(scenario())
    assert gate.unloading is False


def test_failed_unload_releases_the_gate() -> None:
    gate = InferenceGate()

    async def scenario() -> None:
        with pytest.raises(RuntimeError):
            async with gate.unload():
                raise RuntimeError("ollama falhou")
        async with gate.inference():
            assert gate.unloading is False

    asyncio.run(scenario())


def test_second_unload_is_rejected_while_one_is_running() -> None:
    gate = InferenceGate()
    started = asyncio.Event()
    release = asyncio.Event()

    async def first() -> None:
        async with gate.unload():
            started.set()
            await release.wait()

    async def scenario() -> None:
        task = asyncio.create_task(first())
        await started.wait()
        with pytest.raises(AIUnloadInProgressError):
            async with gate.unload():
                pass
        release.set()
        await task

    asyncio.run(scenario())
