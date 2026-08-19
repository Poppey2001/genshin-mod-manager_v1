from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from .component_update_service import ComponentUpdateService


class ComponentSignals(QObject):
    finished = Signal(object)
    failed = Signal(str)


class ComponentUpdateWorker(QRunnable):
    def __init__(self, service: ComponentUpdateService) -> None:
        super().__init__()
        self.service = service
        self.signals = ComponentSignals()
        self.setAutoDelete(True)

    @Slot()
    def run(self) -> None:
        try:
            result = self.service.check_and_install()
        except Exception as error:
            self.signals.failed.emit(f"{type(error).__name__}: {error}")
            return
        self.signals.finished.emit(result)
