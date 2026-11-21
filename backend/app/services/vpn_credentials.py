"""Validity metadata comes from the signed leaf certificate, never download time."""
from dataclasses import dataclass
from datetime import datetime, timezone
import re
from cryptography import x509
from cryptography.x509.oid import NameOID

PROFILE_SECONDS = 24 * 60 * 60


@dataclass(frozen=True)
class CertificateDetails:
    issued_at: datetime
    expires_at: datetime
    serial: int
    pem: str

    def usable(self, now=None):
        now = now or datetime.now(timezone.utc)
        return (self.issued_at <= now < self.expires_at
                and 0 < (self.expires_at - self.issued_at).total_seconds() <= PROFILE_SECONDS)


def certificate_details(config: str, client_name: str) -> CertificateDetails:
    try:
        sections = re.findall(r'<cert>\s*(.*?)\s*</cert>', config, re.DOTALL)
        if len(sections) != 1:
            raise ValueError()
        blocks = re.findall(r'-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----', sections[0], re.DOTALL)
        if len(blocks) != 1:
            raise ValueError()
        cert = x509.load_pem_x509_certificate(blocks[0].encode())
        names = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        if len(names) != 1 or names[0].value != client_name:
            raise ValueError()
        return CertificateDetails(cert.not_valid_before_utc, cert.not_valid_after_utc,
                                  cert.serial_number, blocks[0])
    except (ValueError, TypeError):
        raise ValueError('Invalid VPN client certificate') from None
