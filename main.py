from __future__ import annotations

import logging
import sys
from pathlib import Path
from app.platform_support import (
    configure_windows_app_id,
    resource_path,

)
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QIcon
from app.main_window import MainWindow
from app.config import ensure_app_directories, load_config

APP_NAME = "Genshin Mod Manager"
APP_VERSION = "0.1.0"


def main() -> int:
    configure_windows_app_id()

    app = QApplication(
        sys.argv
    )

    icon_path = resource_path(
        "assets",
        "icons",
        "app.png",
    )

    if icon_path.is_file():
        app.setWindowIcon(
            QIcon(
                str(icon_path)
            )
        )

    config = load_config()

    window = MainWindow(
        config=config
    )

    window.show()

    return app.exec()

def configure_logging() -> None:
    """Konfiguriert die Konsolenausgabe für Fehler und Statusmeldungen."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def handle_unexpected_exception(
    exception_type: type[BaseException],
    exception_value: BaseException,
    traceback_object,
) -> None:
    """
    Fängt unerwartete Fehler ab und zeigt eine verständliche Meldung an.
    KeyboardInterrupt wird normal an Python weitergereicht.
    """
    if issubclass(exception_type, KeyboardInterrupt):
        sys.__excepthook__(
            exception_type,
            exception_value,
            traceback_object,
        )
        return

    logging.exception(
        "Ein unerwarteter Fehler ist aufgetreten.",
        exc_info=(
            exception_type,
            exception_value,
            traceback_object,
        ),
    )

    QMessageBox.critical(
        None,
        "Unerwarteter Fehler",
        (
            "Der Genshin Mod Manager musste wegen eines Fehlers "
            "beendet werden.\n\n"
            f"{exception_type.__name__}: {exception_value}"
        ),
    )


def create_application() -> QApplication:
    """Erstellt und konfiguriert die Qt-Anwendung."""
    application = QApplication(sys.argv)

    application.setApplicationName(APP_NAME)
    application.setApplicationVersion(APP_VERSION)
    application.setOrganizationName("GenshinModManager")

    return application


def main() -> int:
    configure_logging()
    sys.excepthook = handle_unexpected_exception

    logger = logging.getLogger(__name__)
    logger.info("%s %s wird gestartet.", APP_NAME, APP_VERSION)

    try:
        ensure_app_directories()
        config = load_config()

        logger.info(
            "Aktives Profil: %s",
            config.selected_profile,
        )

        application = create_application()

        window = MainWindow(config=config)
        window.show()

        exit_code = application.exec()

        logger.info(
            "%s wurde mit Exit-Code %s beendet.",
            APP_NAME,
            exit_code,
        )

        return exit_code

    except Exception:
        logger.exception(
            "Die Anwendung konnte nicht gestartet werden."
        )
        return 1

if __name__ == "__main__":
    raise SystemExit(main())