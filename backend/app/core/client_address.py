"""One explicit proxy contract; never select a caller's first forwarded address."""
import ipaddress

from backend.app.core.config import settings
from backend.app.core.exceptions import MirrageException


def parse_address(value):
    if not value or "%" in value:
        raise ValueError("Expected an unscoped IP literal")
    address = ipaddress.ip_address(value.strip())
    return address.ipv4_mapped if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped else address


def otp_client_address(request):
    try:
        peer = parse_address(request.client.host if request.client else None)
        trusted = any(peer in ipaddress.ip_network(network) for network in settings.OTP_TRUSTED_PROXY_CIDRS)
        if not trusted:
            return str(peer)  # Ignore all supplied proxy headers from direct/untrusted clients.
        values = request.headers.getlist("x-mirrage-client-ip")
        if len(values) != 1:
            raise ValueError("Trusted proxy did not provide exactly one client identity")
        return str(parse_address(values[0]))
    except (ValueError, TypeError):
        raise MirrageException(503, "OTP requests are temporarily unavailable", "OTP_CLIENT_ADDRESS_UNAVAILABLE") from None
