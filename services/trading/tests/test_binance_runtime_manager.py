import pytest
from trading.binance_runtime.manager import (
    RuntimeSwapError,
    SingleNautilusRuntimeManager,
)


class FakeCandidate:
    def __init__(self, *, stop_error: bool = False) -> None:
        self.stop_error = stop_error
        self.stop_count = 0

    async def validate(self) -> object:
        return object()

    async def stop(self) -> None:
        self.stop_count += 1
        if self.stop_error:
            raise RuntimeError("stop failed")


class CandidateFactory:
    def __init__(self, candidate: FakeCandidate) -> None:
        self.candidate = candidate
        self.calls: list[tuple[str, str]] = []

    async def __call__(self, api_key: str, api_secret: str) -> FakeCandidate:
        self.calls.append((api_key, api_secret))
        return self.candidate


@pytest.mark.asyncio
async def test_runtime_manager_builds_and_replaces_candidate() -> None:
    first = FakeCandidate()
    second = FakeCandidate()
    factory = CandidateFactory(first)
    manager = SingleNautilusRuntimeManager(factory)

    built = await manager.build_candidate("key", "secret")
    await manager.replace(built)
    factory.candidate = second
    replacement = await manager.build_candidate("new-key", "new-secret")
    await manager.replace(replacement)

    assert factory.calls == [("key", "secret"), ("new-key", "new-secret")]
    assert manager.current is second
    assert first.stop_count == 1


@pytest.mark.asyncio
async def test_runtime_manager_preserves_current_when_shutdown_fails() -> None:
    current = FakeCandidate(stop_error=True)
    candidate = FakeCandidate()
    manager = SingleNautilusRuntimeManager(CandidateFactory(candidate))
    await manager.replace(current)

    with pytest.raises(RuntimeSwapError, match="replace Binance runtime"):
        await manager.replace(candidate)

    assert manager.current is current
    assert candidate.stop_count == 1
