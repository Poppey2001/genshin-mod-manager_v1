from __future__ import annotations


APP_NAME = "Genshin Mod Manager"

# Interne Version für Vergleiche.
# PEP-440-kompatibel:
# 0.4.0a1 < 0.4.0a2 < 0.4.0b1 < 0.4.0
APP_VERSION = "0.5.9a2"

# Schön dargestellte Version für die Oberfläche.
APP_VERSION_DISPLAY = "0.5.9 Alpha2"


__version__ = APP_VERSION


__all__ = [
    "APP_NAME",
    "APP_VERSION",
    "APP_VERSION_DISPLAY",
    "__version__",
]