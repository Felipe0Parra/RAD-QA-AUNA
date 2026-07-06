import fitz  # PyMuPDF
from PyQt5.QtWidgets import QFileDialog, QMessageBox, QWidget, QLabel, QVBoxLayout, QSlider, QPushButton, QHBoxLayout, QScrollArea
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt
try:
    from utils import resource_path
except Exception:
    import importlib.util, os
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
    utils_path = os.path.join(project_root, 'utils.py')
    if os.path.isfile(utils_path):
        spec = importlib.util.spec_from_file_location('utils', utils_path)
        utils = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(utils)
        resource_path = getattr(utils, 'resource_path')
    else:
        raise
class PdfViewer(QWidget):
    def __init__(self, pdf_data: bytes, fecha="", maquina="", tipo_reporte=""):
        super().__init__()
        self.setWindowTitle("Visor de PDF")
        self.setGeometry(200, 200, 800, 600)

        self.pdf_data = pdf_data
        self.zoom = 1.0
        self.current_page = 0
        self.total_pages = 0

        self.initUI(fecha, maquina, tipo_reporte)
        self.load_pdf()
        self.estilo()

    def initUI(self, fecha = "", maquina = "", tipo_reporte = ''):
        self.layout = QVBoxLayout(self)
        
        # Agrega un QScrollArea para contener la etiqueta de imagen
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setWidget(self.label)
        
        self.layout.addWidget(self.scroll_area)

        controls = QHBoxLayout()
        self.prev_button = QPushButton("Anterior")
        self.prev_button.clicked.connect(self.prev_page)
        controls.addWidget(self.prev_button)

        self.next_button = QPushButton("Siguiente")
        self.next_button.clicked.connect(self.next_page)
        controls.addWidget(self.next_button)

        # Create Download Button
        self.download_button = QPushButton("Download PDF")
        self.download_button.clicked.connect(lambda _: self.download_pdf(tipo_reporte=tipo_reporte, maquina=maquina, fecha=fecha))
        controls.addWidget(self.download_button)

        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setMinimum(10)
        self.zoom_slider.setMaximum(300)
        self.zoom_slider.setValue(100)
        self.zoom_slider.valueChanged.connect(self.update_zoom)
        controls.addWidget(self.zoom_slider)

        self.layout.addLayout(controls)

    def download_pdf(self, tipo_reporte="", maquina="", fecha=""):
        # Abrir diálogo para seleccionar ruta de guardado
        default_name = f"{tipo_reporte}_{fecha}.pdf" if tipo_reporte or fecha else "archivo.pdf"
        file_path, _ = QFileDialog.getSaveFileName(self, "Guardar PDF", default_name, "Archivos PDF (*.pdf)")
        if file_path:
            try:
                with open(file_path, "wb") as f:
                    f.write(self.pdf_data)
                QMessageBox.information(self, "Éxito", "PDF guardado exitosamente.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error guardando el PDF:\n{e}")

    def load_pdf(self):
        try:
            self.doc = fitz.open(stream=self.pdf_data, filetype="pdf")
            self.total_pages = self.doc.page_count
            self.show_page()
        except Exception as e:
            print("Error cargando el PDF desde bytes:", e)

    def show_page(self):
        try:
            page = self.doc.load_page(self.current_page)
            mat = fitz.Matrix(self.zoom, self.zoom)
            pix = page.get_pixmap(matrix=mat)

            # Usamos RGB888 en lugar de RGBA8888 para que coincida con PDFNOSE.py
            image = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(image)
            self.label.setPixmap(pixmap)
        except Exception as e:
            print("Error mostrando la página del PDF:", e)
        # ...existing code...

    def update_zoom(self):
        self.zoom = self.zoom_slider.value() / 100
        self.show_page()

    def next_page(self):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.show_page()

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.show_page()

    def estilo(self):
        
        dpi = self.screen().logicalDotsPerInch()
        font_size = int(dpi * 0.145)
        
        ESTILO = resource_path('resources/estilo.qss')
        try:
            with open(ESTILO, "r") as f:
                hoja_estilos = f.read()
                self.setStyleSheet(hoja_estilos)
        except Exception as e:
                print(f"Error loading stylesheet: {e}")