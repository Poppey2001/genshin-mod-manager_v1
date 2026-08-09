from __future__ import annotations

import logging
import sys

from PySide6.QtGui import (
    QIcon,
)

from PySide6.QtWidgets import (
    QApplication,
    QMessageBox,
)

from app.config import (
    ensure_app_directories,
    load_config,
)

from app.i18n import (
    set_language,
    tr,
)

from app.main_window import (
    MainWindow,
)

from app.platform_support import (
    configure_windows_app_id,
    resource_path,
)


APP_NAME = "Genshin Mod Manager"
APP_VERSION =  "0.4.0-alpha.1"


def configure_logging(
) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s | "
            "%(levelname)s | "
            "%(name)s | "
            "%(message)s"
        ),
    )


def handle_unexpected_exception(
    exception_type: type[BaseException],
    exception_value: BaseException,
    traceback_object,
) -> None:
    if issubclass(
        exception_type,
        KeyboardInterrupt,
    ):
        sys.__excepthook__(
            exception_type,
            exception_value,
            traceback_object,
        )

        return

    logging.error(
        "Ein unerwarteter Fehler ist aufgetreten.",
        exc_info=(
            exception_type,
            exception_value,
            traceback_object,
        ),
    )

    QMessageBox.critical(
        None,
        tr(
            "app.error."
            "unexpected.title"
        ),
        tr(
            "app.error."
            "unexpected.message",
            error_type=(
                exception_type.__name__
            ),
            error=exception_value,
        ),
    )


def create_application(
) -> QApplication:
    configure_windows_app_id()

    application = QApplication(
        sys.argv
    )

    application.setApplicationName(
        APP_NAME
    )

    application.setApplicationVersion(
        APP_VERSION
    )

    application.setOrganizationName(
        "GenshinModManager"
    )

    icon_path = resource_path(
        "assets",
        "icons",
        "app.png",
    )

    if icon_path.is_file():
        application.setWindowIcon(
            QIcon(
                str(icon_path)
            )
        )

    return application


def main(
) -> int:
    configure_logging()

    sys.excepthook = (
        handle_unexpected_exception
    )

    logger = logging.getLogger(
        __name__
    )

    logger.info(
        "%s %s wird gestartet.",
        APP_NAME,
        APP_VERSION,
    )

    try:
        ensure_app_directories()

        config = load_config()

        # ----------------------------------------------
        # WICHTIG:
        # Sprache setzen, BEVOR MainWindow und dessen
        # Seiten erzeugt werden.
        # ----------------------------------------------

        if not set_language(
            config.language
        ):
            config.language = "de"

            set_language(
                "de"
            )

        logger.info(
            "Aktives Profil: %s",
            config.selected_profile,
        )

        logger.info(
            "Sprache: %s",
            config.language,
        )

        application = (
            create_application()
        )

        window = MainWindow(
            config=config
        )

        window.show()

        exit_code = (
            application.exec()
        )

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
    raise SystemExit(
        main()
    )