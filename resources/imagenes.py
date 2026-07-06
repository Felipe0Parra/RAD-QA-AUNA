from PyQt5.QtWidgets import QApplication, QLabel, QWidget, QVBoxLayout
from PyQt5.QtGui import QPixmap, QPainter, QBrush
from PyQt5.QtCore import Qt
import sys

class RoundImageWidget(QWidget):
    def __init__(self, image_path, size=100):
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        # Cargar la imagen
        pixmap = QPixmap(image_path)
        pixmap = pixmap.scaled(size, size, Qt.KeepAspectRatioByExpanding)

        # Crear un pixmap redondo
        rounded_pixmap = QPixmap(size, size)
        rounded_pixmap.fill(Qt.transparent)

        painter = QPainter(rounded_pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        brush = QBrush(pixmap)
        
        # Dibujar un círculo y recortar la imagen
        painter.setBrush(brush)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, size, size)
        painter.end()

        # Crear un QLabel para mostrar la imagen redonda
        label = QLabel(self)
        label.setPixmap(rounded_pixmap)

        # Diseño
        layout = QVBoxLayout()
        layout.addWidget(label)
        self.setLayout(layout)

'''if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = RoundImageWidget("braquiterapia.jpg", size=100)  # Reemplaza con tu imagen
    window.show()
    sys.exit(app.exec())
'''