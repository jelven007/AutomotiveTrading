from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from trading.binance_runtime.overview import (
        SpotAccountSnapshot,
        UsdmAccountSnapshot,
    )


class CandidateRuntime(Protocol):
    async def validate(self) -> object: ...

    async def read_spot(self) -> "SpotAccountSnapshot": ...

    async def read_usdm(self) -> "UsdmAccountSnapshot": ...

    async def stop(self) -> None: ...


class CandidateRuntimeFactory(Protocol):
    async def __call__(
        self,
        api_key: str,
        api_secret: str,
    ) -> CandidateRuntime: ...


class RuntimeManager(Protocol):
    @property
    def current(self) -> CandidateRuntime | None: ...

    async def build_candidate(
        self,
        api_key: str,
        api_secret: str,
    ) -> CandidateRuntime: ...

    async def replace(self, candidate: CandidateRuntime) -> None: ...

    async def stop(self) -> None: ...


__all__ = ["CandidateRuntime", "CandidateRuntimeFactory", "RuntimeManager"]
