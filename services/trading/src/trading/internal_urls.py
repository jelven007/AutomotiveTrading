from urllib.parse import urlparse


def validate_internal_service_url(
    base_url: str,
    *,
    service_host: str,
    allow_insecure_internal_http: bool,
) -> None:
    parsed = urlparse(base_url)
    if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("internal service URL must be a valid HTTPS URL")
    if parsed.scheme == "https":
        return
    allowed_http_hosts = {service_host, "127.0.0.1", "localhost"}
    if (
        allow_insecure_internal_http
        and parsed.scheme == "http"
        and parsed.hostname in allowed_http_hosts
    ):
        return
    raise ValueError("internal service URL must use HTTPS")
