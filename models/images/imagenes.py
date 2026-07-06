from PyQt5.QtWidgets import QLabel
from PyQt5.QtCore import pyqtSignal

class ImagenInteractiva(QLabel):
    ruedaScroll = pyqtSignal(int)  # señal personalizada

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        self.ruedaScroll.emit(delta)
