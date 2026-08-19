from __future__ import annotations

import logging
import os
import ssl

from pathlib import Path

from typing import Any

from urllib.error import (
    URLError,
)

from urllib.request import (
    Request,
    urlopen,
)


logger = logging.getLogger(
    __name__
)


try:
    import truststore

except ImportError:
    truststore = None


try:
    import certifi

except ImportError:
    certifi = None


EXTRA_CA_ENVIRONMENT_KEYS = (
    "GMM_CA_BUNDLE",
    "SSL_CERT_FILE",
    "REQUESTS_CA_BUNDLE",
)


def _configured_extra_ca_file(
) -> Path | None:
    for key in EXTRA_CA_ENVIRONMENT_KEYS:
        value = os.environ.get(
            key,
            "",
        ).strip()

        if not value:
            continue

        path = (
            Path(
                value
            )
            .expanduser()
        )

        if path.is_file():
            return path

    return None


def tls_backend_name(
) -> str:
    if (
        os.name
        == "nt"
        and truststore
        is not None
    ):
        return (
            "windows-native-truststore"
        )

    if certifi is not None:
        return (
            "python-system+certifi"
        )

    return (
        "python-system"
    )


def create_https_context(
) -> ssl.SSLContext:
    """
    Create a verified HTTPS client context.

    Windows:
        Prefer truststore so certificate validation uses Windows CryptoAPI
        and the native Windows trust store.

    Fallback:
        Python's secure default SSL context, with certifi added when
        available.

    Certificate verification and hostname checks are NEVER disabled.
    """

    extra_ca = (
        _configured_extra_ca_file()
    )

    if (
        os.name
        == "nt"
        and truststore
        is not None
    ):
        context = (
            truststore.SSLContext(
                ssl.PROTOCOL_TLS_CLIENT
            )
        )

        context.check_hostname = True
        context.verify_mode = (
            ssl.CERT_REQUIRED
        )

        if extra_ca is not None:
            context.load_verify_locations(
                cafile=str(
                    extra_ca
                )
            )

        return context

    context = (
        ssl.create_default_context(
            purpose=(
                ssl.Purpose.SERVER_AUTH
            )
        )
    )

    # create_default_context() already loads system trust.
    # certifi is additive here, not a replacement for system CAs.
    if certifi is not None:
        try:
            context.load_verify_locations(
                cafile=(
                    certifi.where()
                )
            )

        except (
            OSError,
            ssl.SSLError,
        ):
            logger.exception(
                "Could not load certifi CA bundle."
            )

    if extra_ca is not None:
        context.load_verify_locations(
            cafile=str(
                extra_ca
            )
        )

    return context


def verified_urlopen(
    request: Request | str,
    *,
    timeout: float,
) -> Any:
    """
    Open HTTPS using a verified SSL context.

    Kept as a tiny wrapper so all updater network paths use the same
    certificate policy:
    - GitHub API
    - release asset downloads
    - source ZIP fallback
    """

    return urlopen(
        request,
        timeout=timeout,
        context=create_https_context(),
    )


def certificate_verification_reason(
    error: BaseException,
) -> str | None:
    current: BaseException | object = (
        error
    )

    visited: set[
        int
    ] = set()

    for _index in range(
        8
    ):
        identity = id(
            current
        )

        if identity in visited:
            break

        visited.add(
            identity
        )

        if isinstance(
            current,
            ssl.SSLCertVerificationError,
        ):
            return str(
                current
            )

        if isinstance(
            current,
            ssl.SSLError,
        ):
            text = str(
                current
            )

            if (
                "CERTIFICATE_VERIFY_FAILED"
                in text
                or "certificate verify failed"
                in text.casefold()
            ):
                return text

        reason = getattr(
            current,
            "reason",
            None,
        )

        if (
            reason is not None
            and reason is not current
        ):
            current = reason
            continue

        cause = getattr(
            current,
            "__cause__",
            None,
        )

        if (
            cause is not None
            and cause is not current
        ):
            current = cause
            continue

        break

    return None


def is_certificate_verification_error(
    error: BaseException,
) -> bool:
    return (
        certificate_verification_reason(
            error
        )
        is not None
    )


__all__ = [
    "EXTRA_CA_ENVIRONMENT_KEYS",
    "certificate_verification_reason",
    "create_https_context",
    "is_certificate_verification_error",
    "tls_backend_name",
    "verified_urlopen",
]
