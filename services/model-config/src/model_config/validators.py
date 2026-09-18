import ipaddress
import socket
from collections.abc import Callable
from urllib.parse import urlsplit

Resolver = Callable[[str], list[str]]


class UnsafeEndpointError(ValueError):
    pass


def system_resolver(hostname: str) -> list[str]:
    return sorted(
        {
            str(result[4][0])
            for result in socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
        }
    )


def validate_base_url_syntax(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme != "https":
        raise UnsafeEndpointError("model endpoint must use HTTPS")
    if not parsed.hostname:
        raise UnsafeEndpointError("model endpoint must include a hostname")
    if parsed.username or parsed.password:
        raise UnsafeEndpointError("model endpoint must not include credentials")
    if parsed.fragment:
        raise UnsafeEndpointError("model endpoint must not include a fragment")
    if parsed.hostname.lower() == "localhost" or parsed.hostname.lower().endswith(".local"):
        raise UnsafeEndpointError("local model endpoints are not allowed")
    try:
        literal_ip = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        return parsed.hostname
    _reject_non_public_address(literal_ip)
    return parsed.hostname


def validate_connection_target(
    url: str,
    *,
    resolver: Resolver = system_resolver,
    recheck: bool = True,
) -> frozenset[str]:
    hostname = validate_base_url_syntax(url)
    addresses = _resolve_and_validate(hostname, resolver)
    if recheck:
        addresses = _resolve_and_validate(hostname, resolver)
    return addresses


def _resolve_and_validate(hostname: str, resolver: Resolver) -> frozenset[str]:
    try:
        addresses = frozenset(resolver(hostname))
    except OSError as error:
        raise UnsafeEndpointError("model endpoint DNS resolution failed") from error
    if not addresses:
        raise UnsafeEndpointError("model endpoint did not resolve")
    for address in addresses:
        try:
            parsed_address = ipaddress.ip_address(address)
        except ValueError as error:
            raise UnsafeEndpointError("DNS returned an invalid IP address") from error
        _reject_non_public_address(parsed_address)
    return addresses


def _reject_non_public_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> None:
    if not address.is_global:
        raise UnsafeEndpointError("model endpoint resolves to a non-public address")
