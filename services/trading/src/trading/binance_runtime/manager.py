import asyncio

from trading.binance_runtime.ports import (
    CandidateRuntime,
    CandidateRuntimeFactory,
)


class RuntimeSwapError(RuntimeError):
    pass


class SingleNautilusRuntimeManager:
    def __init__(self, factory: CandidateRuntimeFactory) -> None:
        self._factory = factory
        self._current: CandidateRuntime | None = None
        self._lock = asyncio.Lock()

    @property
    def current(self) -> CandidateRuntime | None:
        return self._current

    async def build_candidate(
        self,
        api_key: str,
        api_secret: str,
    ) -> CandidateRuntime:
        return await self._factory(api_key, api_secret)

    async def replace(self, candidate: CandidateRuntime) -> None:
        async with self._lock:
            previous = self._current
            if previous is candidate:
                return
            try:
                if previous is not None:
                    await previous.stop()
            except Exception:
                await self._stop_quietly(candidate)
                raise RuntimeSwapError("unable to replace Binance runtime") from None
            self._current = candidate

    async def stop(self) -> None:
        async with self._lock:
            current = self._current
            self._current = None
            if current is not None:
                await current.stop()

    @staticmethod
    async def _stop_quietly(candidate: CandidateRuntime) -> None:
        try:
            await candidate.stop()
        except Exception:
            return


__all__ = ["RuntimeSwapError", "SingleNautilusRuntimeManager"]
