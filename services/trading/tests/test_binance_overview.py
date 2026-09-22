from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest
from sqlalchemy.orm import Session
from trading.api.binance_overview import get_binance_overview_service
from trading.binance.errors import BinanceConnectorError
from trading.binance_runtime.overview import (
    BinanceOverviewService,
    SpotAccountSnapshot,
    SpotBalance,
    UsdmAccountSnapshot,
    UsdmBalance,
    UsdmPosition,
)
from trading.main import create_app
from trading.models import (
    AccountStatus,
    ConnectionStatus,
    CredentialType,
    MarketGroup,
    TradingAccount,
    TradingProvider,
)
from trading.security import Principal, get_principal


class FakeRuntime:
    def __init__(
        self,
        *,
        spot_error: Exception | None = None,
        usdm_error: Exception | None = None,
    ) -> None:
        self.spot_error = spot_error
        self.usdm_error = usdm_error
        self.spot_calls = 0
        self.usdm_calls = 0

    async def read_spot(self) -> SpotAccountSnapshot:
        self.spot_calls += 1
        if self.spot_error is not None:
            raise self.spot_error
        return SpotAccountSnapshot(
            balances=[
                SpotBalance(
                    asset="BTC",
                    free=Decimal("0.25"),
                    locked=Decimal("0"),
                    total=Decimal("0.25"),
                ),
                SpotBalance(
                    asset="ETH",
                    free=Decimal("0"),
                    locked=Decimal("0"),
                    total=Decimal("0"),
                ),
            ],
            as_of=datetime(2026, 9, 21, tzinfo=UTC),
        )

    async def read_usdm(self) -> UsdmAccountSnapshot:
        self.usdm_calls += 1
        if self.usdm_error is not None:
            raise self.usdm_error
        return UsdmAccountSnapshot(
            balances=[
                UsdmBalance(
                    asset="USDT",
                    wallet_balance=Decimal("1000"),
                    available_balance=Decimal("800"),
                    unrealized_pnl=Decimal("12.5"),
                )
            ],
            positions=[
                UsdmPosition(
                    symbol="BTCUSDT",
                    side="long",
                    quantity=Decimal("0.01"),
                    entry_price=Decimal("60000"),
                    mark_price=Decimal("61250"),
                    unrealized_pnl=Decimal("12.5"),
                    leverage=5,
                    margin_mode="cross",
                ),
                UsdmPosition(
                    symbol="ETHUSDT",
                    side="flat",
                    quantity=Decimal("0"),
                    entry_price=Decimal("0"),
                    mark_price=None,
                    unrealized_pnl=Decimal("0"),
                    leverage=None,
                    margin_mode=None,
                ),
            ],
            as_of=datetime(2026, 9, 21, tzinfo=UTC),
        )

    async def validate(self) -> object:
        await self.read_spot()
        await self.read_usdm()
        return object()

    async def stop(self) -> None:
        return None


class FakeRuntimeManager:
    def __init__(self, current: FakeRuntime | None) -> None:
        self.current = current


def add_account(session: Session) -> TradingAccount:
    account = TradingAccount(
        tenant_id="tenant-a",
        alias="主账号",
        market_group=MarketGroup.BINANCE,
        provider=TradingProvider.BINANCE,
        account_slot="primary",
        environment="demo",
        credential_type=CredentialType.HMAC,
        api_key_fingerprint="sha256:1234567890abcdef",
        status=AccountStatus.READ_ONLY,
        connection_status=ConnectionStatus.CONNECTED,
        trading_enabled=False,
        is_active=False,
        can_read=True,
        ip_restricted=False,
        can_spot_trade=True,
        can_margin_trade=False,
        can_futures_trade=True,
        can_withdraw=False,
        can_internal_transfer=False,
        can_universal_transfer=False,
        last_permission_check_at=datetime(2026, 9, 21),
        created_by="user-a",
    )
    session.add(account)
    session.commit()
    return account


@pytest.mark.asyncio
async def test_overview_requires_bound_account(session: Session) -> None:
    overview_service = BinanceOverviewService(session, FakeRuntimeManager(FakeRuntime()))

    with pytest.raises(LookupError, match="not bound"):
        await overview_service.get("tenant-a")


@pytest.mark.asyncio
async def test_overview_filters_zero_balances_and_positions(session: Session) -> None:
    add_account(session)
    overview_service = BinanceOverviewService(session, FakeRuntimeManager(FakeRuntime()))

    overview = await overview_service.get("tenant-a")

    assert overview.account.environment == "demo"
    assert overview.permissions.status == "ok"
    assert overview.spot.status == "ok"
    assert [balance.asset for balance in overview.spot.data.balances] == ["BTC"]
    assert overview.usdm.status == "ok"
    assert [position.symbol for position in overview.usdm.data.positions] == ["BTCUSDT"]
    assert not session.dirty


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failed_section", "error_code"),
    [
        ("spot", "binance.spot_unavailable"),
        ("usdm", "binance.usdm_unavailable"),
    ],
)
async def test_overview_degrades_only_the_failed_product(
    session: Session,
    failed_section: str,
    error_code: str,
) -> None:
    add_account(session)
    error = BinanceConnectorError(error_code, "temporary failure")
    runtime = FakeRuntime(
        spot_error=error if failed_section == "spot" else None,
        usdm_error=error if failed_section == "usdm" else None,
    )
    overview_service = BinanceOverviewService(session, FakeRuntimeManager(runtime))

    overview = await overview_service.get("tenant-a")

    failed = getattr(overview, failed_section)
    successful = overview.usdm if failed_section == "spot" else overview.spot
    assert failed.status == "error"
    assert failed.error.code == error_code
    assert successful.status == "ok"
    assert overview.permissions.status == "ok"


@pytest.mark.asyncio
async def test_overview_reuses_snapshot_until_forced_refresh(session: Session) -> None:
    add_account(session)
    runtime = FakeRuntime()
    overview_service = BinanceOverviewService(
        session,
        FakeRuntimeManager(runtime),
        cache_ttl_seconds=5,
    )

    first = await overview_service.get("tenant-a")
    second = await overview_service.get("tenant-a")
    refreshed = await overview_service.get("tenant-a", refresh=True)

    assert second is first
    assert refreshed is not first
    assert runtime.spot_calls == 2
    assert runtime.usdm_calls == 2


@pytest.mark.asyncio
async def test_overview_endpoint_returns_sectioned_payload(session: Session) -> None:
    add_account(session)
    service = BinanceOverviewService(session, FakeRuntimeManager(FakeRuntime()))
    app = create_app()
    app.dependency_overrides[get_principal] = lambda: Principal(
        user_id="user-a",
        tenant_id="tenant-a",
        roles=("tenant_admin",),
        mfa_verified_at=None,
    )
    app.dependency_overrides[get_binance_overview_service] = lambda: service

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/trading/binance/overview")

    assert response.status_code == 200
    assert response.json()["spot"]["status"] == "ok"
    assert response.json()["usdm"]["status"] == "ok"
    assert response.json()["permissions"]["status"] == "ok"
