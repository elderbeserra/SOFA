from PyQt5.QtCore import QObject, pyqtSignal


class SignalBus(QObject):
    __instance: 'SignalBus | None' = None
    updProgress = pyqtSignal(float)
    videoProcessed = pyqtSignal()
    uptLabelSlicer = pyqtSignal(int, str)

    @staticmethod
    def instance() -> 'SignalBus':
        if not SignalBus.__instance:
            SignalBus.__instance = SignalBus()
        return SignalBus.__instance
