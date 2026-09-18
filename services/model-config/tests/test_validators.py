from collections.abc import Iterator

import pytest
from model_config.validators import UnsafeEndpointError, validate_connection_target


def resolver_sequence(*answers: list[str]):
    values: Iterator[list[str]] = iter(answers)

    def resolve(_: str) -> list[str]:
        return next(values)

    return resolve


@pytest.mark.parametrize(
    "url",
    [
        "http://api.example.com/v1",
        "https://127.0.0.1/v1",
        "https://169.254.169.254/latest/meta-data",
        "https://user:password@api.example.com/v1",
    ],
)
def test_unsafe_base_urls_are_rejected(url: str) -> None:
    with pytest.raises(UnsafeEndpointError):
        validate_connection_target(url, resolver=lambda _: ["93.184.216.34"])


def test_private_dns_result_is_rejected() -> None:
    with pytest.raises(UnsafeEndpointError):
        validate_connection_target(
            "https://api.example.com/v1",
            resolver=lambda _: ["10.0.0.8"],
        )


def test_dns_rebinding_is_rejected_during_connection_recheck() -> None:
    resolver = resolver_sequence(["93.184.216.34"], ["127.0.0.1"])

    with pytest.raises(UnsafeEndpointError):
        validate_connection_target(
            "https://api.example.com/v1",
            resolver=resolver,
            recheck=True,
        )


def test_public_https_endpoint_is_allowed() -> None:
    addresses = validate_connection_target(
        "https://api.example.com/v1",
        resolver=lambda _: ["93.184.216.34"],
        recheck=True,
    )

    assert addresses == frozenset({"93.184.216.34"})
