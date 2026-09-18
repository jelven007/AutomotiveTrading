from decimal import Decimal

from qt_common.idempotency import request_fingerprint


def test_request_fingerprint_is_stable_for_equivalent_payloads() -> None:
    first = request_fingerprint(
        tenant_id="tenant-a",
        method="post",
        path="/orders",
        payload={"quantity": 100, "price": Decimal("12.30")},
    )
    second = request_fingerprint(
        tenant_id="tenant-a",
        method="POST",
        path="/orders",
        payload={"price": Decimal("12.30"), "quantity": 100},
    )

    assert first == second
    assert len(first) == 64


def test_request_fingerprint_is_tenant_scoped() -> None:
    first = request_fingerprint("tenant-a", "POST", "/orders", {"quantity": 100})
    second = request_fingerprint("tenant-b", "POST", "/orders", {"quantity": 100})

    assert first != second
