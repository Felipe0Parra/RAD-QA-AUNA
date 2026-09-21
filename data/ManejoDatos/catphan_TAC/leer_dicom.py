import os
import gc
import weakref
from PyQt5.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QSlider, QWidget, QPushButton, QFileDialog, QDialog, QFrame, QApplication)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
import pyqtgraph as pg
from data.ManejoDatos.catphan_TAC.slice_matcher import detectar_y_resolver_modulos
from analisisImagenes.catphan.serie import leer_serie
import pydicom
import pydicom.data
class DicomVolume:
    """
    Clase para cargar, procesar y acceder a volúmenes DICOM de tomografía.
    No incluye métodos de visualización, permitiendo su uso en cualquier interfaz (PyQt, Streamlit, CLI, etc.).

    Mejoras implementadas:
    - Gestión optimizada de memoria con liberación automática, evitando fugas de memoria
    - Cache inteligente para cortes normalizados, es decir, solo guarda los últimos N cortes usados
    - Carga progresiva de datos, evitando cargar todo en memoria si no es necesario
    """

    def __init__(self, ruta_carpeta):
        #print("DicomVolume __init__ called")

        """
        Inicializa la clase y carga los archivos DICOM de la carpeta especificada.
        """
        self.ruta_carpeta = ruta_carpeta
        self.cortes = []
        self.volumen = None
        self.volumen_hu = None
        self.pixel_spacing = None
        self.slice_thickness = None

        # Gestión de memoria mejorada
        self._cache_cortes_norm = {}  # Cache para cortes normalizados
        self._max_cache_size = 10  # Máximo número de cortes en cache
        self._memory_threshold = 500 * 1024 * 1024  # 500MB threshold, es decir, si el volumen es mayor a esto, usa carga optimizada
        self._observers = weakref.WeakSet()  # Referencias débiles a observadores

        self._load_dicoms()

    """Carga y procesa los archivos DICOM en la carpeta especificada con gestión optimizada de memoria."""
    def _load_dicoms(self):
        import pydicom

        # A.1 (PLAN_CATPHAN_AUTOMATICO_POR_EQUIPO_18-09.md): el orden de los
        # cortes y la elección de serie única se delegan en `leer_serie`, la
        # MISMA función que usará el motor (B.1) -- para que el visor y el
        # motor no puedan volver a divergir sobre qué es "el corte i" (D-01,
        # D-06). Antes: `sorted(..., key=SliceLocation)`, ausente en los CBCT
        # de Varian (Halcyon, iX) -> volumen barajado.
        self.serie_uid = None
        self.series_descartadas = {}
        self.no_imagen = 0
        self.avisos = []

        try:
            serie = leer_serie(self.ruta_carpeta)
            self.serie_uid = serie.serie_uid
            self.series_descartadas = serie.series_descartadas
            self.no_imagen = serie.no_imagen
            self.avisos = serie.avisos

            for uid, n in serie.series_descartadas.items():
                print(f"Advertencia: se descartaron {n} corte(s) de la serie {uid} "
                      "(no es la serie mayoritaria de la carpeta).")
            if serie.no_imagen:
                print(f"Advertencia: {serie.no_imagen} archivo(s) de la carpeta "
                      "no son CT Image Storage y se ignoraron.")
            for aviso in serie.avisos:
                print(f"Advertencia: {aviso}")

            dicoms = [pydicom.dcmread(corte.ruta) for corte in serie.cortes]
            total_memory = sum(
                ds.pixel_array.nbytes for ds in dicoms if hasattr(ds, 'pixel_array')
            )

            #print(f"Memoria estimada del volumen: {total_memory / (1024*1024):.1f} MB")

            self.cortes = dicoms

            if self.cortes:
                # Extraer metadatos del primer corte (ahora el primero en
                # posición espacial real, no el primero que devolvió el disco)
                self.pixel_spacing = getattr(self.cortes[0], 'PixelSpacing', None)
                self.slice_thickness = getattr(self.cortes[0], 'SliceThickness', None)
                self.kv = getattr(self.cortes[0], 'KVP', None)
                self.ma = getattr(self.cortes[0], 'XRayTubeCurrent', None)
                self.espesor_corte = getattr(self.cortes[0], 'SliceThickness', None)

                # Carga optimizada del volumen
                if total_memory > self._memory_threshold:
                    print("⚠️ Volumen grande detectado. Usando carga optimizada...")
                    self._load_large_volume()
                else:
                    self._load_standard_volume()
            else:
                self.volumen = None
                self.volumen_hu = None

        except Exception as e:
            print(f"Error durante la carga de DICOM: {e}")
            self.volumen = None
            self.volumen_hu = None

    def _load_standard_volume(self):
        """Carga estándar para volúmenes pequeños/medianos."""
        try:
            import numpy as np
            # Apilar los cortes para formar el volumen 3D
            pixel_arrays = [ds.pixel_array for ds in self.cortes]
            self.volumen = np.stack(pixel_arrays, axis=0)

            # Liberar memoria de arrays individuales
            del pixel_arrays
            gc.collect()

            # Convertir a Hounsfield Units
            slope = float(getattr(self.cortes[0], 'RescaleSlope', 1))
            intercept = float(getattr(self.cortes[0], 'RescaleIntercept', 0))

            # Usar float32 para ahorrar memoria
            self.volumen_hu = (self.volumen.astype(np.float32) * slope + intercept)

        except Exception as e:
            print(f"Advertencia: Error en conversión HU: {e}")
            self.volumen_hu = self.volumen.astype(np.float32) if self.volumen is not None else None

    def _load_large_volume(self):
        """Carga optimizada para volúmenes grandes."""
        try:
            import numpy as np
            # Para volúmenes grandes, usar dtype más eficiente
            first_array = self.cortes[0].pixel_array
            dtype = np.float32 if first_array.dtype in [np.float64, np.int32, np.int64] else first_array.dtype

            # Pre-asignar memoria
            shape = (len(self.cortes), *first_array.shape)
            self.volumen = np.empty(shape, dtype=dtype)

            # Cargar slice por slice para controlar memoria
            slope = float(getattr(self.cortes[0], 'RescaleSlope', 1))
            intercept = float(getattr(self.cortes[0], 'RescaleIntercept', 0))

            for i, ds in enumerate(self.cortes):
                self.volumen[i] = ds.pixel_array.astype(dtype)
                # Liberar memoria del dataset después de usar
                if hasattr(ds, 'pixel_array'):
                    delattr(ds, '_pixel_array')

            # Convertir a HU con tipo eficiente
            self.volumen_hu = self.volumen * slope + intercept

            # Forzar garbage collection
            gc.collect()

        except Exception as e:
            print(f"Advertencia: Error en carga optimizada: {e}")
            self.volumen_hu = None

    """Métodos para obtener información del volumen"""
    def get_shape(self):
        """
        Devuelve la forma del volumen HU (número de cortes, alto, ancho).
        """
        if self.volumen_hu is not None:
            return self.volumen_hu.shape
        return None

    def get_pixel_spacing(self):
        """
        Devuelve el tamaño de píxel en mm (lista de dos valores).
        """
        return self.pixel_spacing

    def get_slice_thickness(self):
        """
        Devuelve el espesor de corte en mm.
        """
        return self.slice_thickness

    def get_num_cortes(self):
        """
        Devuelve el número de cortes en el volumen.
        """
        if self.volumen_hu is not None:
            return self.volumen_hu.shape[0]
        return 0

    def get_corte(self, idx):
        """
        Devuelve el corte HU en la posición idx.
        """
        if self.volumen_hu is not None and 0 <= idx < self.volumen_hu.shape[0]:
            return self.volumen_hu[idx]
        return None

    def get_corte_normalizado(self, idx, min_hu, max_hu):
        """
        Devuelve el corte idx normalizado al rango [0, 255] para visualización.
        Los valores fuera de [min_hu, max_hu] se recortan.
        Implementa cache inteligente LRU para mejorar rendimiento y calidad.
        """
        import numpy as np
        # Crear clave de cache
        cache_key = (idx, min_hu, max_hu)

        # Verificar cache con prioridad LRU
        if cache_key in self._cache_cortes_norm:
            # Mover al final para LRU (most recently used)
            corte_cached = self._cache_cortes_norm.pop(cache_key)
            self._cache_cortes_norm[cache_key] = corte_cached
            return corte_cached

        corte = self.get_corte(idx)
        if corte is None:
            return None

        # Normalización optimizada con precisión mejorada
        corte_clip = np.clip(corte.astype(np.float32), min_hu, max_hu)
        corte_norm = ((corte_clip - min_hu) / (max_hu - min_hu) * 255).astype(np.uint8)

        # Gestión inteligente del cache (LRU)
        if len(self._cache_cortes_norm) >= self._max_cache_size:
            # Remover el menos usado recientemente (LRU)
            oldest_key = next(iter(self._cache_cortes_norm))
            del self._cache_cortes_norm[oldest_key]

        # Agregar al cache
        self._cache_cortes_norm[cache_key] = corte_norm

        return corte_norm

    def get_volumen_normalizado(self, wl:int, ww:int):
        """
        Aplica ventana de visualización usando nivel (wl) y ancho (ww).
        wl = Window Level (centro)
        ww = Window Width (contraste)
        Optimización para procesamiento de volumen completo con mejor precisión.
        """
        import numpy as np
        if self.volumen_hu is None:
            return None

        if ww <= 0:
            ww = 1  # Evita división por cero

        min_hu = wl - ww / 2
        max_hu = wl + ww / 2

        #print(f"Aplicando ventana: Nivel={wl}, Ancho={ww} => Rango HU [{min_hu}, {max_hu}]")

        # Usar operaciones vectorizadas más eficientes
        volumen_clip = np.clip(self.volumen_hu, min_hu, max_hu)

        # Evitar conversiones innecesarias - mantener precisión
        volumen_norm = (volumen_clip - min_hu) / (max_hu - min_hu)

        # Conversión final optimizada
        return (volumen_norm * 255).astype(np.uint8)

    def clear_cache(self):
        """Libera el cache de cortes normalizados para ahorrar memoria."""
        self._cache_cortes_norm.clear()
        gc.collect()

    def get_memory_usage(self):
        """Retorna el uso estimado de memoria en MB."""
        total = 0
        if self.volumen is not None:
            total += self.volumen.nbytes
        if self.volumen_hu is not None:
            total += self.volumen_hu.nbytes

        # Agregar cache
        for corte in self._cache_cortes_norm.values():
            total += corte.nbytes

        return total / (1024 * 1024)  # MB

    def __del__(self):
        """Destructor para limpieza de memoria."""
        try:
            self.clear_cache()
            if hasattr(self, 'volumen'):
                del self.volumen
            if hasattr(self, 'volumen_hu'):
                del self.volumen_hu
        except:
            pass

# Visualización optimizada con matplotlib
def mostrar_cortes_interactivo(volumen, idx=[0], canvas=None, on_idx_change=None):
    import matplotlib.pyplot as plt

    if volumen is None:
        print("No hay volumen cargado para mostrar.")
        return

    if canvas is not None:
        fig = canvas.figure
        fig.clear()
    else:
        fig = plt.figure(figsize=(15, 10))

    ax = fig.add_subplot(111)

    # MEJORAR CALIDAD DE IMAGEN con interpolación bicúbica
    im = ax.imshow(volumen[idx[0]],
                   cmap='gray',
                   interpolation='bicubic',  # Mejor interpolación para calidad
                   vmin=0, vmax=255,
                   aspect='equal')  # Mantener aspecto correcto

    ax.set_title(f"Corte {idx[0] + 1}")
    ax.axis('off')

    def on_scroll(event):
        if event.button == 'up':
            idx[0] = min(idx[0] + 1, volumen.shape[0] - 1)
        elif event.button == 'down':
            idx[0] = max(idx[0] - 1, 0)

        # Actualización optimizada
        im.set_array(volumen[idx[0]])  # Más eficiente que set_data
        ax.set_title(f"Corte {idx[0] + 1}")
        fig.canvas.draw_idle()  # draw_idle es más eficiente

        if on_idx_change:
            on_idx_change(idx[0])
        return idx[0]

    fig.canvas.mpl_connect('scroll_event', on_scroll)

    if canvas is not None:
        fig.tight_layout(rect=[0, 0.03, 1, 0.95])
        canvas.draw_idle()  # Usar draw_idle aquí también

    return fig


# geometria_catphan.py
import cv2
import numpy as np


class GeometriaCatphan:
    RADIO_PHANTOM_MM = 100.0
    TOLERANCIA       = 0.12
    ROI_DIST_MM      = 50.0
    MAX_OFFSET_LOCAL = 3    # px — límite físico razonado

    ROI_CONFIG = {
        "15mm": {"angulo": -87.4, "radio_mm": 6.0, "diametro_mm": 15},
        "9mm":  {"angulo": -69.1, "radio_mm": 3.5, "diametro_mm": 9},
        "8mm":  {"angulo": -52.7, "radio_mm": 3.0, "diametro_mm": 8},
        "7mm":  {"angulo": -38.5, "radio_mm": 2.5, "diametro_mm": 7},
        "6mm":  {"angulo": -25.1, "radio_mm": 2.0, "diametro_mm": 6},
        "5mm":  {"angulo": -12.9, "radio_mm": 1.5, "diametro_mm": 5},
    }

    def __init__(self, corte: np.ndarray, tam_px: float):
        self.tam_px       = tam_px
        self._corte_blur  = cv2.GaussianBlur(corte, (5, 5), 1.2)
        self.centro, self.radio = self._detectar_phantom()

        # Offsets globales
        self.offset_x   = 0.0
        self.offset_y   = 0.0
        self.offset_ang = 0.0

        # Offsets locales por ROI — inician en cero
        self.offsets_locales = {nombre: [0.0, 0.0] for nombre in self.ROI_CONFIG}

    # ── detección ────────────────────────────────────────────────────────────

    def _detectar_phantom(self):
        radio_nominal_px = self.RADIO_PHANTOM_MM / self.tam_px
        min_r = int(radio_nominal_px * (1 - self.TOLERANCIA))
        max_r = int(radio_nominal_px * (1 + self.TOLERANCIA))
        if min_r == max_r:
            max_r = min_r + 1

        circles = cv2.HoughCircles(
            self._corte_blur, cv2.HOUGH_GRADIENT,
            dp=1.2, minDist=self._corte_blur.shape[0] // 2,
            param1=50, param2=30,
            minRadius=min_r, maxRadius=max_r,
        )

        h, w = self._corte_blur.shape
        if circles is None:
            print("⚠️ Phantom no detectado. Usando centro geométrico.")
            return (w / 2.0, h / 2.0), radio_nominal_px

        mejor = self._seleccionar_mejor(circles[0], radio_nominal_px)
        cx, cy, r = float(mejor[0]), float(mejor[1]), float(mejor[2])
        return (cx, cy), r

    def _seleccionar_mejor(self, candidatos, radio_nominal_px):
        h, w   = self._corte_blur.shape
        cx_img = w / 2.0;  cy_img = h / 2.0
        diagonal = np.hypot(h, w)
        scores = []

        for c in candidatos:
            cx, cy, r = float(c[0]), float(c[1]), float(c[2])
            dist   = np.hypot(cx - cx_img, cy - cy_img)
            s_cent = 1.0 - min(dist / (diagonal * 0.3), 1.0)
            err_r  = abs(r - radio_nominal_px) / radio_nominal_px
            s_rad  = 1.0 - min(err_r / 0.15, 1.0)
            margen = min(cx - r, cy - r, w - cx - r, h - cy - r)
            s_borde = 1.0 if margen > 5 else 0.0
            mask   = np.zeros(self._corte_blur.shape, np.uint8)
            cv2.circle(mask, (int(round(cx)), int(round(cy))), int(round(r * 0.7)), 1, -1)
            vals   = self._corte_blur[mask == 1]
            hu_m   = float(np.mean(vals)) if len(vals) > 0 else 999.0
            s_hu   = float(np.exp(-((hu_m - 128) / 60) ** 2))
            scores.append(s_cent * 0.4 + s_rad * 0.3 + s_borde * 0.2 + s_hu * 0.1)

        return candidatos[int(np.argmax(scores))]

    # ── API de posiciones ─────────────────────────────────────────────────────

    def obtener_roi(self, nombre):
        """
        Fuente única de verdad para posición de cada ROI.
        Aplica: geometría base + offset global + offset local.
        Retorna (centro_int, radio_int).
        """
        cx, cy, r = self._calcular_roi_float(nombre)
        return (int(round(cx)), int(round(cy))), int(round(r))

    def obtener_roi_float(self, nombre):
        """Versión subpíxel para cálculos de métricas."""
        cx, cy, r = self._calcular_roi_float(nombre)
        return (cx, cy), r

    def _calcular_roi_float(self, nombre):
        info      = self.ROI_CONFIG[nombre]
        ang_rad   = np.radians(info["angulo"] + self.offset_ang)
        dist_px   = self.ROI_DIST_MM / self.tam_px
        radio_px  = info["radio_mm"]  / self.tam_px

        # Posición geométrica base + offset global
        cx = self.centro[0] + self.offset_x + dist_px * np.cos(ang_rad)
        cy = self.centro[1] + self.offset_y + dist_px * np.sin(ang_rad)

        # Offset local (limitado a MAX_OFFSET_LOCAL)
        dx, dy = self.offsets_locales[nombre]
        cx += np.clip(dx, -self.MAX_OFFSET_LOCAL, self.MAX_OFFSET_LOCAL)
        cy += np.clip(dy, -self.MAX_OFFSET_LOCAL, self.MAX_OFFSET_LOCAL)

        return cx, cy, radio_px

    def posicion_roi(self, angulo_deg, distancia_mm, radio_mm):
        """Compatibilidad con código existente — para ROIs de fondo."""
        dist_px  = distancia_mm / self.tam_px
        radio_px = radio_mm     / self.tam_px
        ang_rad  = np.radians(angulo_deg + self.offset_ang)
        cx = self.centro[0] + self.offset_x + dist_px * np.cos(ang_rad)
        cy = self.centro[1] + self.offset_y + dist_px * np.sin(ang_rad)
        return (int(round(cx)), int(round(cy))), int(round(radio_px))

    def posicion_roi_float(self, angulo_deg, distancia_mm, radio_mm):
        dist_px  = distancia_mm / self.tam_px
        radio_px = radio_mm     / self.tam_px
        ang_rad  = np.radians(angulo_deg + self.offset_ang)
        cx = self.centro[0] + self.offset_x + dist_px * np.cos(ang_rad)
        cy = self.centro[1] + self.offset_y + dist_px * np.sin(ang_rad)
        return (cx, cy), radio_px

    def reset_offsets_locales(self, nombre=None):
        if nombre:
            self.offsets_locales[nombre] = [0.0, 0.0]
        else:
            for k in self.offsets_locales:
                self.offsets_locales[k] = [0.0, 0.0]

    @property
    def centro_int(self):
        return (int(round(self.centro[0] + self.offset_x)),
                int(round(self.centro[1] + self.offset_y)))

    @property
    def radio_int(self):
        return int(round(self.radio))

#-----------------------------------------------------------
# loading_dialog.py   <-- ponlo al lado de tus demás módulos
# -----------------------------------------------------------
from PyQt5.QtWidgets import QDialog, QLabel, QVBoxLayout
from PyQt5.QtCore import Qt

class LoadingDialog(QDialog):
    """Diálogo muy sencillo que solo muestra un texto (o GIF) de carga."""
    def __init__(self, parent=None, mensaje="Calculando, espere…"):
        super().__init__(parent, Qt.WindowTitleHint | Qt.WindowSystemMenuHint)
        self.setModal(True)                 # bloquea interacción con la ventana principal
        self.setWindowTitle("Procesando")
        self.setFixedSize(260, 80)          # tamaño pequeño, sin botones

        # Si quieres un gif animado, sustituye el QLabel por QMovie.
        etiqueta = QLabel(mensaje, self)
        etiqueta.setAlignment(Qt.AlignCenter)

        layout = QVBoxLayout(self)
        layout.addWidget(etiqueta)
        self.setLayout(layout)

class VisualizadorDicom(QWidget):
    corte_seleccionado = pyqtSignal(int)
    imagen_cargada = pyqtSignal(object)


    def __init__(self, parent=None, target_canvas=None):
        #print("VisualizadorDicom __init__ called")

        super().__init__(parent)
        self.idx_actual = 0
        self.vol = None
        self.target_canvas = target_canvas
        self.use_external_canvas = target_canvas is not None

        # Mejoras de rendimiento UI
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._actualizar_ventana_debounced)
        self._debounce_delay = 25  # Reducido de 50ms a 25ms para mayor responsividad
        self._pending_update = False

        # Gestión de recursos
        self._scroll_connection_id = None
        self._current_figure = None

        # Configurar matplotlib para imágenes médicas
        self._configurar_matplotlib()

        pg.setConfigOptions(imageAxisOrder='row-major')  # Configuración para médicas
        self.initUI()

    def _configurar_matplotlib(self):
        """Configuraciones optimizadas de matplotlib para imágenes médicas."""
        try:
            import matplotlib
            # Configuraciones para mejor calidad y rendimiento
            matplotlib.rcParams['image.interpolation'] = 'bicubic'
            matplotlib.rcParams['image.cmap'] = 'gray'
            matplotlib.rcParams['image.origin'] = 'upper'
            matplotlib.rcParams['figure.max_open_warning'] = 0
            matplotlib.rcParams['axes.formatter.useoffset'] = False
        except Exception as e:
            print(f"Warning: No se pudieron configurar parámetros matplotlib: {e}")

    def initUI(self):
        #print("Inicializando la interfaz de VisualizadorDicom...")

        # Crear el layout principal
        if not self.layout():
            self.layout_principal = QVBoxLayout()
            self.setLayout(self.layout_principal)
        else:
            print("El widget ya tiene un layout asignado.")

        # Contenedor para la gráfica y controles
        self.contenedor_grafica = QWidget()
        layout_grafica = QVBoxLayout(self.contenedor_grafica)

        # Solo creamos nuestro propio visor si no hay canvas externo
        if not self.use_external_canvas:
            # Área de visualización con PyQtGraph
            self.imageView = pg.ImageView()
            self.imageView.ui.roiBtn.hide()     # Ocultar botón ROI
            self.imageView.ui.menuBtn.hide()    # Ocultar botón menú
            self.layout_principal.addWidget(self.imageView)

        # Etiqueta para mostrar info del corte
        self.info_label = QLabel("Corte: 0/0")
        layout_grafica.addWidget(self.info_label)

        # Controles de nivel y ventana
        slider_layout = QVBoxLayout()
        #Control de cortes
        self.slider_corte = QSlider(Qt.Horizontal)
        self.slider_corte.setRange(0, 381)
        slider_layout.addWidget(self.slider_corte)
        # Control de nivel (brillo)
        self.slider_wl = QSlider(Qt.Horizontal)
        self.slider_wl.setRange(-1000, 500)
        self.slider_wl.setValue(40)
        self.slider_wl_label = QLabel("Nivel (brillo): 40")
        slider_layout.addWidget(self.slider_wl_label)
        slider_layout.addWidget(self.slider_wl)

        # Control de ventana (contraste)
        self.slider_ww = QSlider(Qt.Horizontal)
        self.slider_ww.setRange(1, 2000)
        self.slider_ww.setValue(400)
        self.slider_ww_label = QLabel("Ventana (contraste): 400")
        slider_layout.addWidget(self.slider_ww_label)
        slider_layout.addWidget(self.slider_ww)

        layout_grafica.addLayout(slider_layout)

        # Botones
        self.lbl_imagen = QLabel("Cargar DICOM")
        self.lbl_imagen.setAlignment(Qt.AlignCenter)
        self.sel_imagen_btn = QPushButton("Seleccionar Imagen DICOM")
        self.layout_principal.addWidget(self.sel_imagen_btn)
        #print("Botón 'Seleccionar Imagen DICOM' agregado al layout.")

        self.elegir_corte_btn = QPushButton("Elegir Corte")
        layout_grafica.addWidget(self.elegir_corte_btn)


        # Agregar el contenedor de la gráfica al layout principal
        self.layout_principal.addWidget(self.contenedor_grafica)

        self.elegir_corte_btn.hide()

        # Conectar eventos con debouncing para mejor rendimiento
        self.slider_wl.valueChanged.connect(self._on_slider_changed)
        self.slider_ww.valueChanged.connect(self._on_slider_changed)
        self.slider_corte.valueChanged.connect(self._on_slider_changed)
        self.sel_imagen_btn.clicked.connect(self.seleccionar_carpeta)
        #print("Conexión del botón 'Seleccionar Imagen DICOM' establecida.")
        #self.elegir_corte_btn.clicked.connect(lambda: print("\nBotón elegir corte presionado"))
        self.elegir_corte_btn.clicked.connect(self.elegir_corte)


        # Ocultar controles inicialmente
        self.slider_wl.hide()
        self.slider_ww.hide()
        self.slider_wl_label.hide()
        self.slider_ww_label.hide()
        self.info_label.hide()

    def seleccionar_carpeta(self):
        opciones = QFileDialog.Options()
        self.ruta_carpeta = QFileDialog.getExistingDirectory(
            self, "Seleccionar Carpeta DICOM", "", options=opciones
        )

        if self.ruta_carpeta:
            self.visualizar_imagen_cargada()
            return self.ruta_carpeta

        return None

    def visualizar_imagen_cargada(self, ruta_carpeta=None):
        if ruta_carpeta:
            self.ruta_carpeta = ruta_carpeta


        # Cargar volumen DICOM
        self.vol = DicomVolume(self.ruta_carpeta)
        if self.vol.volumen_hu is None:
            print("Error: No se pudo cargar el volumen DICOM.")
            return
        else:
            self.sel_imagen_btn.hide()

        ##############################################################################
        """                          INTERFAZ D CARGA                              """
        ##############################################################################

        self.loading_dialog = LoadingDialog(self, "Detectando módulos…")
        self.loading_dialog.show()

        # ¡IMPORTANTE!  Forzamos a Qt a procesar todos los eventos pendientes
        # (pintado del dialogo, movimiento del ratón, etc.) antes de que
        # la UI se bloquee por la función larga.
        QApplication.processEvents()

        #print("\n   ⋇⋇ Volumen DICOM cargado correctamente.")

        # Mostrar controles
        self.slider_wl.show()
        self.slider_ww.show()
        self.slider_wl_label.show()
        self.slider_ww_label.show()
        self.info_label.show()
        self.elegir_corte_btn.show()

        # Aplicar ventana inicial
        self.actualizar_ventana()

        # Emitir señal
        #print("\n   ⪧ Señal de imagen enviada generada")

        self.resultados, self.cortes = detectar_y_resolver_modulos(
            ruta_dicom=self.ruta_carpeta,
        )
            # ------------------------------------------------------------------
        # 4️⃣  Ocultar dialogo y continuar con el resto de la UI
        # ------------------------------------------------------------------
        self.loading_dialog.close()          # o .accept() / .hide()
        del self.loading_dialog              # liberar referencia

        # ------------------------------------------------------------------
        # ------------------------------------------------------------------
        self.imagen_cargada.emit(self.vol)



        print(self.cortes)
        print("VISUALIZADOR QUE EMITE:", id(self))
        self.mostrar_popup_cortes(self.resultados)
        # parametros de la adquisición
        self.kv = self.vol.kv
        self.ma = self.vol.ma
        self.espesor_corte = self.vol.espesor_corte

        # Mostrar uso de memoria
        #print(f"   📊 Uso de memoria del volumen: {self.vol.get_memory_usage():.1f} MB")

##########################################################################################################################################


##########################################################################################################################################

    def _on_slider_changed(self):
        """Maneja cambios en sliders con debouncing optimizado para mejor rendimiento."""
        self._pending_update = True
        self._debounce_timer.stop()
        self._debounce_timer.start(self._debounce_delay)

        # Actualización inmediata de labels sin redibujado
        cortex = self.slider_corte.value()
        wl = self.slider_wl.value()
        ww = self.slider_ww.value()
        self.slider_wl_label.setText(f"Nivel (WL): {wl}")
        self.slider_ww_label.setText(f"Ancho (WW): {ww}")

        self.idx_actual = cortex
        self.info_label.setText(f"Corte: {self.idx_actual + 1}/{self.vol.get_num_cortes()}" if self.vol else "")

    def _actualizar_ventana_debounced(self):
        """Actualización optimizada de ventana con mejor calidad de imagen."""
        import numpy as np
        if not self._pending_update or not self.vol or self.vol.volumen_hu is None:
            return

        try:
            wl = self.slider_wl.value()
            ww = self.slider_ww.value()
            min_hu = wl - ww / 2
            max_hu = wl + ww / 2

            if self.use_external_canvas:
                # Obtener corte con mayor precisión
                corte_hu = self.vol.get_corte(self.idx_actual)
                if corte_hu is None:
                    return

                # Aplicar ventana con precision float32 para mejor calidad
                corte_clip = np.clip(corte_hu.astype(np.float32), min_hu, max_hu)
                corte_norm = ((corte_clip - min_hu) / (max_hu - min_hu) * 255).astype(np.uint8)

                # Limpiar conexiones anteriores
                self._cleanup_canvas_connections()

                # Configurar canvas optimizado
                if self._current_figure is None:
                    self._current_figure = self.target_canvas.figure

                fig = self._current_figure
                fig.clear()
                ax = fig.add_subplot(111)

                # MEJORAR INTERPOLACIÓN - Usar 'bicubic' para mejor calidad visual
                im = ax.imshow(corte_norm,
                              cmap='gray',
                              interpolation='bicubic',  # Cambio clave para mejor calidad
                              aspect='equal',
                              vmin=0, vmax=255)

                ax.set_title(f'Corte {self.idx_actual + 1}/{self.vol.get_num_cortes()}',
                            fontsize=10, pad=8)
                ax.axis('off')

                self.slider_corte.setMinimum(0)
                self.slider_corte.setMaximum(self.vol.get_num_cortes()-1)
                fig.tight_layout(pad=0.5)
                self.target_canvas.draw_idle()
                self._precargar_cortes_adyacentes(self.idx_actual)

                # Conectar evento de scroll optimizado
                # def on_scroll(event):
                #     if event.button == 'up':
                #         self.idx_actual = min(self.idx_actual + 1, self.vol.get_num_cortes() - 1)
                #     elif event.button == 'down':
                #         self.idx_actual = max(self.idx_actual - 1, 0)

                #     # Actualizar con cache optimizado
                #     corte_norm_new = self.vol.get_corte_normalizado(self.idx_actual, min_hu, max_hu)
                #     im.set_array(corte_norm_new)  # Más eficiente que set_data
                #     ax.set_title(f"Corte {self.idx_actual + 1}/{self.vol.get_num_cortes()}")
                #     self.info_label.setText(f"Corte: {self.idx_actual + 1}/{self.vol.get_num_cortes()}")
                #     fig.canvas.draw_idle()  # draw_idle es más eficiente

                # Registrar conexión
               # self._scroll_connection_id = fig.canvas.mpl_connect('scroll_event', on_scroll)

                # Renderizado optimizado
                # fig.tight_layout(pad=0.5)
                # self.target_canvas.draw_idle()  # draw_idle en lugar de draw()

                # Pre-cargar cortes adyacentes para navegación fluida
                self._precargar_cortes_adyacentes(self.idx_actual)

            else:
                # Modo PyQtGraph mantiene su configuración optimizada
                self.actualizar_ventana()

            self._pending_update = False

        except Exception as e:
            print(f"Error en actualización de ventana: {e}")
            self._pending_update = False

    def actualizar_ventana(self):
        import numpy as np





        # Obtener valores de los sliders
        wl = self.slider_wl.value()
        ww = self.slider_ww.value()

        # Actualizar etiquetas
        self.slider_wl_label.setText(f"Nivel (brillo): {wl}")
        self.slider_ww_label.setText(f"Ventana (contraste): {ww}")

        # Calcular rango de HU
        min_hu = wl - ww/2
        max_hu = wl + ww/2

        if self.use_external_canvas:
            # Limpiar conexión anterior
            self._cleanup_canvas_connections()

            # Modo canvas externo (matplotlib)
            # Normalizar solo el corte actual para mostrar en matplotlib
            corte_norm = self.vol.get_corte_normalizado(self.idx_actual, min_hu, max_hu)

            # Reutilizar figura si existe
            if self._current_figure is None:
                self._current_figure = self.target_canvas.figure

            fig = self._current_figure
            fig.clear()
            ax = fig.add_subplot(111)
            im = ax.imshow(corte_norm, cmap='gray', vmin=0, vmax=255, interpolation='nearest')
            ax.set_title(f"Corte {self.idx_actual + 1}/{self.vol.get_num_cortes()}")
            ax.axis('off')

            self.slider_corte.setMinimum(0)
            self.slider_corte.setMaximum(self.vol.get_num_cortes()-1)
            fig.tight_layout(pad=0.5)
            self.target_canvas.draw_idle()
            self._precargar_cortes_adyacentes(self.idx_actual)

            # Conectar evento de scroll con mejor gestión
            # def on_scroll(event):
            #     if event.button == 'up':
            #         self.idx_actual = min(self.idx_actual + 1, self.vol.get_num_cortes() - 1)
            #     elif event.button == 'down':
            #         self.idx_actual = max(self.idx_actual - 1, 0)

            #     # Actualizar corte usando cache
            #     corte_norm_new = self.vol.get_corte_normalizado(self.idx_actual, min_hu, max_hu)
            #     im.set_data(corte_norm_new)
            #     im.set_clim(vmin=0, vmax=255)  # Optimización: evitar recálculo
            #     ax.set_title(f"Corte {self.idx_actual + 1}/{self.vol.get_num_cortes()}")
            #     self.info_label.setText(f"Corte: {self.idx_actual + 1}/{self.vol.get_num_cortes()}")
            #     fig.canvas.draw_idle()

            # Registrar conexión para limpieza posterior
#            self._scroll_connection_id = fig.canvas.mpl_connect('scroll_event', on_scroll)

            fig.tight_layout()
            self.target_canvas.draw()
        else:
            # Modo PyQtGraph (propio visualizador)
            # Normalizar volumen para PyQtGraph
            # Aprovecha que PyQtGraph tiene su propio manejo de niveles
            volumen_norm = self.vol.volumen_hu.astype(np.float32)

            # Configurar ImageView con nuevo volumen y niveles
            self.imageView.setImage(volumen_norm)
            self.imageView.setLevels(min_hu, max_hu)

            # Conectar cambio de slice
            try:
                self.imageView.sigTimeChanged.disconnect()
            except:
                pass
            self.imageView.sigTimeChanged.connect(self.actualizar_indice)

        # Actualizar info
        self.info_label.setText(f"Corte: {self.idx_actual + 1}/{self.vol.get_num_cortes()}")

    def _cleanup_canvas_connections(self):
        """Limpia conexiones anteriores para evitar memory leaks."""
        if self._scroll_connection_id and self._current_figure:
            try:
                self._current_figure.canvas.mpl_disconnect(self._scroll_connection_id)
            except:
                pass
        self._scroll_connection_id = None

    def _precargar_cortes_adyacentes(self, idx_central):
        """Pre-carga los cortes adyacentes para navegación más fluida."""
        if not self.vol or self.vol.volumen_hu is None:
            return

        # Pre-cargar hasta 2 cortes en cada dirección
        wl = self.slider_wl.value()
        ww = self.slider_ww.value()
        min_hu = wl - ww / 2
        max_hu = wl + ww / 2

        indices_precargar = []
        for offset in [-2, -1, 1, 2]:
            idx = idx_central + offset
            if 0 <= idx < self.vol.get_num_cortes():
                indices_precargar.append(idx)

        # Pre-cargar en segundo plano sin bloquear UI
        QTimer.singleShot(100, lambda: self._ejecutar_precarga(indices_precargar, min_hu, max_hu))

    def _ejecutar_precarga(self, indices, min_hu, max_hu):
        """Ejecuta la pre-carga sin bloquear la UI."""
        try:
            for idx in indices[:2]:  # Limitar a 2 para no saturar memoria
                cache_key = (idx, min_hu, max_hu)
                if cache_key not in self.vol._cache_cortes_norm:
                    self.vol.get_corte_normalizado(idx, min_hu, max_hu)
        except Exception as e:
            print(f"Error en pre-carga: {e}")

    def actualizar_indice(self, idx):
        self.idx_actual = int(idx)
        self.info_label.setText(f"Corte: {self.idx_actual + 1}/{self.vol.get_num_cortes()}")

    def elegir_corte(self):
        if self.vol is None:
            print("Error: No hay volumen cargado.")
            return
        #print(f"    ✓ Corte seleccionado: {self.idx_actual}")
        print(f"Tamaño de pixel: {self.vol.get_pixel_spacing()}")
        print(f"Espesor de corte del metadata (mm): {self.vol.get_slice_thickness()}")
        self.corte_seleccionado.emit(self.idx_actual)
        return self.idx_actual


    def mostrar_popup_cortes(self, resultados):
        """
        Muestra un popup simple con el número de corte sugerido para cada módulo.
        No realiza ningún análisis ni dispara ninguna acción.
        El usuario lee los números, cierra el popup, y continúa.

        Args:
            resultados:    Dict { nombre: ResultadoModulo } de pylinac.
            parent_widget: Widget PyQt5 padre.
        """


        dialogo = QDialog(self)
        dialogo.setWindowTitle("Cortes sugeridos — CatPhan 504")
        dialogo.setMinimumWidth(380)
        dialogo.setMaximumWidth(480)

        layout = QVBoxLayout(dialogo)
        layout.setSpacing(8)

        lbl_intro = QLabel(
            "Pylinac identificó los siguientes cortes para cada módulo.<br>"
            "<small>Navega hasta el corte indicado en el visualizador antes de iniciar cada análisis.</small>"
        )
        lbl_intro.setTextFormat(Qt.RichText)
        lbl_intro.setWordWrap(True)
        layout.addWidget(lbl_intro)

        # Separador
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep)

        # Una fila por módulo
        for nombre, resultado in resultados.items():
            fila = QHBoxLayout()

            # Indicador de confianza
            icono = "🟢" if resultado.confiable else "🟡"

            # Nombre + descripción
            lbl_nombre = QLabel(f"{icono}  <b>{nombre}</b>  <small>— {resultado.descripcion}</small>")
            lbl_nombre.setTextFormat(Qt.RichText)

            # Número de corte
            if resultado.idx_corte is not None:
                txt_corte = f"Corte <b>{resultado.idx_corte + 1} (± 1)</b>"
            else:
                txt_corte = "<span style='color:#cc8800'>No detectado</span>"
                if resultado.error:
                    txt_corte += f"<br><small>{resultado.error[:50]}</small>"

            lbl_corte = QLabel(txt_corte)
            lbl_corte.setTextFormat(Qt.RichText)
            lbl_corte.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

            fila.addWidget(lbl_nombre, stretch=3)
            fila.addWidget(lbl_corte, stretch=1)
            layout.addLayout(fila)

        # Separador
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep2)

        # Botón cerrar
        btn_cerrar = QPushButton("Entendido")
        btn_cerrar.setDefault(True)
        btn_cerrar.clicked.connect(dialogo.accept)
        layout.addWidget(btn_cerrar, alignment=Qt.AlignRight)



        dialogo.setAttribute(Qt.WA_DeleteOnClose, False)
        dialogo.setModal(False)

        dialogo.open()

        dialogo.activateWindow()

    def __del__(self):
        """Destructor para limpieza de recursos."""
        try:
            self._cleanup_canvas_connections()
            if hasattr(self, '_debounce_timer'):
                self._debounce_timer.stop()
            if hasattr(self, 'vol') and self.vol:
                self.vol.clear_cache()
        except:
            pass

if __name__ == "__main__":
    ruta = "C:/Users/penak/OneDrive/Documents/SEMESTRE 8/PRUEBA_IMAGEN_KAROL/CATPHANKV"
    vol = DicomVolume(ruta)
    vol_normalizado = vol.get_volumen_normalizado(wl=40, ww=400)
    print("Dimensiones:", vol.get_shape())
    print("Tamaño de pixel:", vol.get_pixel_spacing())
    print("Espesor de corte:", vol.get_slice_thickness())
    fig = mostrar_cortes_interactivo(vol_normalizado)
