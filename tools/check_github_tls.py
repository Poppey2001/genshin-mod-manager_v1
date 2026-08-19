#!/usr/bin/env python3
from __future__ import annotations

import sys

from urllib.request import (
    Request,
)

from app.services.network_tls import (
    tls_backend_name,
    verified_urlopen,
)


def main(
) -> int:
    print(
        "TLS backend:",
        tls_backend_name(),
    )

    request = Request(
        "https://api.github.com/",
        headers={
            "Accept": (
                "application/vnd.github+json"
            ),
            "User-Agent": (
                "Genshin-Mod-Manager-TLS-Test"
            ),
        },
    )

    try:
        with verified_urlopen(
            request,
            timeout=20,
        ) as response:
            print(
                "GitHub HTTPS:",
                response.status,
            )

    except Exception as error:
        print(
            "GitHub HTTPS FAILED:",
            repr(
                error
            ),
            file=sys.stderr,
        )

        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
