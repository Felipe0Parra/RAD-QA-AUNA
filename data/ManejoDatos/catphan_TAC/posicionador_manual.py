# posicionador_manual.py
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                              QPushButton, QLabel, QSlider, QSizePolicy, QGroupBox, QCheckBox, QComboBox, QListWidget)
from PyQt5.QtCore import Qt
from data.ManejoDatos.catphan_TAC.leer_dicom import GeometriaCatphan
# posicionador_manual.py — reemplaza tu clase PosicionadorDialog completa


""" 
Quiero que el modo de juicio manual tenga más control sobre los ROIS, es decir, cuando esté en modo manual tenga la posibilidad de 
esconder o no cada ROI cada circulo, de tal modo que el usuario vea o no.
"""

class PosicionadorDialog(QDialog):
    """
    Dos modos:
      GLOBAL  — sliders X/Y/θ mueven los 6 ROIs juntos
      INDIVIDUAL — click sobre ROI lo selecciona; sliders dx/dy lo afitan (±3px)

    El phantom es rígido: offset local complementa al global, no lo reemplaza.
    """

    COLORES = {
        "normal":      "lime",
        "seleccionado":"yellow",
        "phantom":     "#8B3C3C",
    }

    def __init__(self, catphan: GeometriaCatphan, corte_255: np.ndarray, parent=None):
        super().__init__(parent)
        self.catphan = catphan
        self.corte   = corte_255
        self._modo_manual_usado = False
        self.setWindowTitle("Ajuste manual de posición — Catphan CTP515")
        self.setMinimumSize(1000, 900)
        

        self._zoom      = 1.0
        self._zoom_min  = 1.0
        self._zoom_max  = 8.0
        self._pan_x     = 0.0
        self._pan_y     = 0.0
        self._panando   = False
        self._pan_start = None
        self._pan_start_offset = None
        self._display_oculto: dict[str, bool] = {nombre: False for nombre in catphan.ROI_CONFIG}

        self._modo           = "global"   # "global" | "individual"
        self._roi_seleccionado = None     # nombre del ROI activo en modo individual
        self._visibilidad_manual: dict[str, bool] = {nombre: True for nombre in catphan.ROI_CONFIG}
        # Window/level
        self._window_center = 128//2
        self._window_width  = 256//2
        self._click_umbral   = 15         # px en pantalla para seleccionar ROI

        self._build_ui()
        self._dibujar()

    # ── UI ───────────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout_main = QVBoxLayout(self)

        # Contenedor horizontal: sliders + canvas + panel manual
        layout_img = QHBoxLayout()

        # Sliders verticales
        layout_sliders = QVBoxLayout()

        self.slider_brillo = QSlider(Qt.Vertical)
        self.slider_brillo.setRange(0, 255)
        self.slider_brillo.setValue(self._window_center)

        self.slider_contraste = QSlider(Qt.Vertical)
        self.slider_contraste.setRange(1,512)
        self.slider_contraste.setValue(self._window_width)

        self.slider_brillo.valueChanged.connect(self._on_window_change)
        self.slider_contraste.valueChanged.connect(self._on_window_change)

        layout_sliders.addWidget(QLabel("Brillo"))
        layout_sliders.addWidget(self.slider_brillo)

        layout_sliders.addWidget(QLabel("Contraste"))
        layout_sliders.addWidget(self.slider_contraste)
        
        # Canvas
        self.fig = Figure(figsize=(45, 65), tight_layout=True)
        self.canvas = FigureCanvas(self.fig)

        layout_img.addLayout(layout_sliders)
        layout_img.addWidget(self.canvas, stretch=1)

        # --- PANEL MANUAL (Ahora a la derecha del canvas) ---
        self.group_manual = QGroupBox("Evaluación visual de ROIs")
        layout_manual = QVBoxLayout(self.group_manual)

        self._checkboxes_visibilidad: dict[str, QCheckBox] = {}
        for nombre, cfg in self.catphan.ROI_CONFIG.items():
            diam = cfg.get("diametro_mm", cfg.get("radio_mm", "?") * 2)
            cb = QCheckBox(f"{nombre} ({diam} mm) — Visible")
            cb.setChecked(True)
            cb.stateChanged.connect(self._on_visibilidad_manual_changed)
            self._checkboxes_visibilidad[nombre] = cb
            layout_manual.addWidget(cb)
        
        layout_manual.addStretch() # Empuja los checkboxes hacia arriba

        self.group_manual.setEnabled(False)
        self.group_manual.setVisible(False)
        
        # Agregamos el panel al layout horizontal
        layout_img.addWidget(self.group_manual)
        # ----------------------------------------------------

        layout_main.addLayout(layout_img)
        
        # Instrucciones
        self.lbl_instruccion = QLabel("")
        self.lbl_instruccion.setAlignment(Qt.AlignCenter)
        layout_main.addWidget(self.lbl_instruccion)

        # Botones de modo
        layout_modo = QHBoxLayout()
        self.btn_global = QPushButton("Modo Global (todos los ROIs)")
        self.btn_global.setCheckable(True)
        self.btn_global.setChecked(True)
        self.btn_global.clicked.connect(lambda: self._cambiar_modo("global"))
        self.btn_individual = QPushButton("Modo Individual (ROI por ROI)")
        self.btn_individual.setCheckable(True)
        self.btn_individual.clicked.connect(lambda: self._cambiar_modo("individual"))
        layout_modo.addWidget(self.btn_global)
        layout_modo.addWidget(self.btn_individual)
        
        self.btn_manual = QPushButton("Modo Manual (juicio visual)")
        self.btn_manual.setCheckable(True)
        self.btn_manual.clicked.connect(lambda: self._cambiar_modo("manual"))
        layout_modo.addWidget(self.btn_manual)
        layout_main.addLayout(layout_modo)
        
        # Ocultación de ROIs
        
        
        self.lista_ocultos = QListWidget()
        self.lista_ocultos.setMaximumHeight(120)
        layout_manual.addWidget(QLabel("ROIS Ocultos"))
        layout_manual.addWidget(self.lista_ocultos) 
        btn_mostrar = QPushButton("Mostrar ROI seleccionado")
        btn_mostrar.clicked.connect(self._mostrar_roi_oculto)
        layout_manual.addWidget(btn_mostrar)

        # Panel global
        self.group_global = QGroupBox("Corrección global")
        layout_global = QVBoxLayout(self.group_global)

        self.slider_gx  = self._make_slider(-50, 50, 0)
        self.slider_gy  = self._make_slider(-50, 50, 0)
        self.slider_ang = self._make_slider(-100, 100, 0)
        self.lbl_gx  = QLabel("Δx = 0.0 px")
        self.lbl_gy  = QLabel("Δy = 0.0 px")
        self.lbl_ang = QLabel("Δθ = 0.0°")

        for lbl, slider, tag in [
            (self.lbl_gx,  self.slider_gx,  "gx"),
            (self.lbl_gy,  self.slider_gy,  "gy"),
            (self.lbl_ang, self.slider_ang, "ang"),
        ]:
            row = QHBoxLayout()
            row.addWidget(lbl, stretch=1)
            row.addWidget(slider, stretch=4)
            layout_global.addLayout(row)

        self.slider_gx.valueChanged.connect(self._on_global_slider)
        self.slider_gy.valueChanged.connect(self._on_global_slider)
        self.slider_ang.valueChanged.connect(self._on_global_slider)
        layout_main.addWidget(self.group_global)

        # Panel individual
        self.group_individual = QGroupBox("Corrección individual  (ROI seleccionado: —)")
        layout_ind = QVBoxLayout(self.group_individual)
        
        self.slider_lx = self._make_slider(
            -self.catphan.MAX_OFFSET_LOCAL * 10,
             self.catphan.MAX_OFFSET_LOCAL * 10, 0)
        self.slider_ly = self._make_slider(
            -self.catphan.MAX_OFFSET_LOCAL * 10,
             self.catphan.MAX_OFFSET_LOCAL * 10, 0)
        self.lbl_lx = QLabel("dx = 0.0 px")
        self.lbl_ly = QLabel("dy = 0.0 px")

        for lbl, slider in [(self.lbl_lx, self.slider_lx), (self.lbl_ly, self.slider_ly)]:
            row = QHBoxLayout()
            row.addWidget(lbl, stretch=1)
            row.addWidget(slider, stretch=4)
            layout_ind.addLayout(row)

        self.slider_lx.valueChanged.connect(self._on_local_slider)
        self.slider_ly.valueChanged.connect(self._on_local_slider)
        self.group_individual.setEnabled(False)
        layout_main.addWidget(self.group_individual)

        # Zoom
        layout_zoom = QHBoxLayout()
        layout_zoom.addWidget(QLabel("Zoom:"))
        self.slider_zoom = self._make_slider(10, 80, 10)
        self.lbl_zoom = QLabel("1.0×")
        self.lbl_zoom.setFixedWidth(20)
        self.slider_zoom.valueChanged.connect(self._on_zoom)
        layout_zoom.addWidget(self.slider_zoom, stretch=5)
        layout_zoom.addWidget(self.lbl_zoom)
        layout_main.addLayout(layout_zoom)

        # Estado
        self.lbl_estado = QLabel("")
        self.lbl_estado.setAlignment(Qt.AlignCenter)
        layout_main.addWidget(self.lbl_estado)

        # Botones
        layout_btn = QHBoxLayout()
        btn_reset_roi = QPushButton("Reset ROI seleccionado")
        btn_reset_roi.clicked.connect(self._reset_roi)
        btn_reset_all = QPushButton("Reset todo")
        btn_reset_all.clicked.connect(self._reset_all)
        btn_ok     = QPushButton("Confirmar")
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        layout_btn.addWidget(btn_reset_roi)
        layout_btn.addWidget(btn_reset_all)
        layout_btn.addStretch()
        layout_btn.addWidget(btn_cancel)
        layout_btn.addWidget(btn_ok)
        layout_main.addLayout(layout_btn)

        # Eventos canvas
        self.canvas.mpl_connect("button_press_event",   self._on_press)
        self.canvas.mpl_connect("button_release_event", self._on_release)
        self.canvas.mpl_connect("motion_notify_event",  self._on_motion)
        self.canvas.mpl_connect("scroll_event",         self._on_scroll)

        self._cambiar_modo("global")

    @staticmethod
    def _make_slider(min_v, max_v, val):
        s = QSlider(Qt.Horizontal)
        s.setRange(min_v, max_v)
        s.setValue(val)
        return s

    # ── modos ─────────────────────────────────────────────────────────────────
    def _on_window_change(self):
        self._window_center = self.slider_brillo.value()
        self._window_width  = self.slider_contraste.value()
        self._dibujar()
    def _cambiar_modo(self, modo):
        self._modo = modo
        if modo == "manual":
            self._modo_manual_usado = True
        self.btn_global.setChecked(modo == "global")
        self.btn_individual.setChecked(modo == "individual")
        self.btn_manual.setChecked(modo == "manual")

        self.group_global.setEnabled(modo == "global")
        self.group_individual.setEnabled(modo == "individual")
        self.group_manual.setEnabled(modo == "manual")
        self.group_manual.setVisible(modo == "manual")

        if modo == "global":
            self._roi_seleccionado = None
            self.lbl_instruccion.setText(
                "Sliders X/Y/θ mueven los 6 ROIs juntos  |  "
                "Click derecho + arrastrar: paneo  |  Rueda: zoom"
            )
        elif modo == "individual":
            self.lbl_instruccion.setText(
                "Click sobre un círculo para seleccionarlo  |  "
                "Luego usa sliders dx/dy para ajuste fino (±3px)"
            )
        else:  # manual
            self._roi_seleccionado = None
            self.lbl_instruccion.setText(
                "Marca cada ROI como visible o no visible según tu criterio visual"
            )
        self._dibujar()

    # ── dibujo ───────────────────────────────────────────────────────────────

    def _limites_zoom(self):
        h, w   = self.corte.shape
        cx, cy = self.catphan.centro_int
        half_w = (w / 2) / self._zoom
        half_h = (h / 2) / self._zoom
        view_cx = cx + self._pan_x
        view_cy = cy + self._pan_y
        x0 = max(0, view_cx - half_w);  x1 = min(w, view_cx + half_w)
        y0 = max(0, view_cy - half_h);  y1 = min(h, view_cy + half_h)
        return x0, x1, y0, y1
    
    def _dibujar(self):
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        vmin = self._window_center - self._window_width / 2
        vmax = self._window_center + self._window_width / 2

        ax.imshow(
            self.corte,
            cmap="gray",
            origin="upper",
            vmin=vmin,
            vmax=vmax
        )
        ax.axis("off")

        c = self.catphan
        cx, cy = c.centro_int

        # Phantom exterior
        ax.add_patch(mpatches.Circle(
            (cx, cy), c.radio_int,
            fill=False, color=self.COLORES["phantom"],
            linewidth=1.2, linestyle="--"
        ))

        # ROIs
        for nombre in c.ROI_CONFIG:
            # centro_px, radio_px = c.obtener_roi(nombre)
            es_seleccionado = (nombre == self._roi_seleccionado)
            if self._display_oculto.get(nombre, False):
                continue  # oculto visualmente, no se dibuja nada

            centro_px, radio_px = c.obtener_roi(nombre)

            if self._modo == "manual":
                es_visible = self._visibilidad_manual.get(nombre, True)
                color = self.COLORES["normal"] if es_visible else "red"
                lw = 1.5
            else:
                color = self.COLORES["seleccionado"] if es_seleccionado else self.COLORES["normal"]
                lw = 2.0 if es_seleccionado else 1.0

            # Posición teórica (sin offset local) en modo individual — overlay de referencia
            if self._modo == "individual" and es_seleccionado:
                centro_teo, radio_teo = c.posicion_roi(
                    c.ROI_CONFIG[nombre]["angulo"], c.ROI_DIST_MM, c.ROI_CONFIG[nombre]["radio_mm"]
                )
                ax.add_patch(mpatches.Circle(
                    centro_teo, radio_teo,
                    fill=False, color="gray", linewidth=0.8, linestyle=":"
                ))

            ax.add_patch(mpatches.Circle(
                centro_px, radio_px,
                fill=False, color=color, linewidth=lw
            ))
            ax.text(
                centro_px[0], centro_px[1] - radio_px - 4,
                nombre, color=color, fontsize=7, ha="center"
            )

        # Crosshair
        ax.axhline(cy, color="cyan", linewidth=0.5, alpha=0.4)
        ax.axvline(cx, color="cyan", linewidth=0.5, alpha=0.4)

        x0, x1, y0, y1 = self._limites_zoom()
        ax.set_xlim(x0, x1)
        ax.set_ylim(y1, y0)

        roi_sel_txt = self._roi_seleccionado or "—"
        ax.set_title(
            f"Modo: {'Global' if self._modo == 'global' else f'Individual [{roi_sel_txt}]'}  |  "
            f"Zoom {self._zoom:.1f}×  |  "
            f"Δx={c.offset_x:.1f}  Δy={c.offset_y:.1f}  Δθ={c.offset_ang:.1f}°",
            fontsize=9
        )
        self._actualizar_labels()
        self.canvas.draw_idle()
    def _on_visibilidad_manual_changed(self):
        for nombre, cb in self._checkboxes_visibilidad.items():
            nuevo_estado = cb.isChecked()
            self._visibilidad_manual[nombre] = nuevo_estado
            if nuevo_estado and self._display_oculto.get(nombre, False):
                self._display_oculto[nombre] = False  # checkbox marcado = des-ocultar
        self._actualizar_lista_ocultos()
        self._dibujar()
    
    def _mostrar_roi_oculto(self):
        item = self.lista_ocultos.currentItem()
        if item is None:
            return
        nombre = item.text().split(" ")[0]
        self._display_oculto[nombre] = False
        self._visibilidad_manual[nombre] = True
        self._checkboxes_visibilidad[nombre].blockSignals(True)
        self._checkboxes_visibilidad[nombre].setChecked(True)
        self._checkboxes_visibilidad[nombre].blockSignals(False)
        self._actualizar_lista_ocultos()
        self._dibujar()
    def _on_press(self, event):
        if event.inaxes is None:
            return
        if event.button == 3 and self._modo == "manual":
            nombre = self._roi_bajo_cursor(event.xdata, event.ydata)
            if nombre:
                self._display_oculto[nombre] = True
                self._visibilidad_manual[nombre] = False
                self._checkboxes_visibilidad[nombre].blockSignals(True)
                self._checkboxes_visibilidad[nombre].setChecked(False)
                self._checkboxes_visibilidad[nombre].blockSignals(False)
                self._actualizar_lista_ocultos()
                self._dibujar()
                return
            # Sin ROI bajo cursor → pan normal
            self._panando = True
            self._pan_start = (event.xdata, event.ydata)
            self._pan_start_offset = (self._pan_x, self._pan_y)

        elif event.button == 3:
            self._panando = True
            self._pan_start = (event.xdata, event.ydata)
            self._pan_start_offset = (self._pan_x, self._pan_y)

        elif event.button == 1 and self._modo == "individual":
            self._seleccionar_roi_cercano(event.xdata, event.ydata)
 
            
    def _roi_bajo_cursor(self, xdata, ydata) -> str | None:
        for nombre in self.catphan.ROI_CONFIG:
            if self._display_oculto.get(nombre, False):
                continue  # ya oculto, no clickeable
            centro_px, radio_px = self.catphan.obtener_roi(nombre)
            dist = np.hypot(xdata - centro_px[0], ydata - centro_px[1])
            if dist < radio_px + 8:
                return nombre
        return None

    def _actualizar_lista_ocultos(self):
        self.lista_ocultos.clear()
        for nombre, oculto in self._display_oculto.items():
            if oculto:
                cfg = self.catphan.ROI_CONFIG[nombre]
                diam = cfg.get("diametro_mm", cfg.get("radio_mm", "?") * 2)
                self.lista_ocultos.addItem(f"{nombre} ({diam} mm)")
    @property
    def visibilidad_manual(self) -> dict[str, bool] | None:
        """None si el usuario nunca entró a modo manual."""
        if not self._modo_manual_usado:
            return None
        return self._visibilidad_manual
    def _actualizar_labels(self):
        c = self.catphan
        self.lbl_gx.setText(f"Δx = {c.offset_x:.1f} px")
        self.lbl_gy.setText(f"Δy = {c.offset_y:.1f} px")
        self.lbl_ang.setText(f"Δθ = {c.offset_ang:.1f}°")

        if self._roi_seleccionado:
            dx, dy = c.offsets_locales[self._roi_seleccionado]
            self.lbl_lx.setText(f"dx = {dx:.1f} px")
            self.lbl_ly.setText(f"dy = {dy:.1f} px")
            self.group_individual.setTitle(
                f"Corrección individual  (ROI seleccionado: {self._roi_seleccionado})"
            )
        else:
            self.lbl_lx.setText("dx = — px")
            self.lbl_ly.setText("dy = — px")
            self.group_individual.setTitle("Corrección individual  (ROI seleccionado: —)")

        self.lbl_estado.setText(
            f"Centro phantom: {c.centro_int}  |  "
            f"Offsets locales: { {k: v for k, v in c.offsets_locales.items() if any(v)} or 'ninguno' }"
        )

    # ── eventos sliders ───────────────────────────────────────────────────────

    def _on_global_slider(self):
        self.catphan.offset_x   = self.slider_gx.value() / 1.0
        self.catphan.offset_y   = self.slider_gy.value() / 1.0
        self.catphan.offset_ang = self.slider_ang.value() / 10.0
        self._dibujar()

    def _on_local_slider(self):
        if not self._roi_seleccionado:
            return
        dx = self.slider_lx.value() / 10.0
        dy = self.slider_ly.value() / 10.0
        self.catphan.offsets_locales[self._roi_seleccionado] = [dx, dy]
        self._dibujar()

    def _on_zoom(self, valor):
        self._zoom = valor / 10.0
        self.lbl_zoom.setText(f"{self._zoom:.1f}×")
        self._dibujar()

    # ── eventos mouse ─────────────────────────────────────────────────────────

  
    def _on_release(self, event):
        self._panando = False

    def _on_motion(self, event):
        if self._panando and event.inaxes and self._pan_start:
            dx = event.xdata - self._pan_start[0]
            dy = event.ydata - self._pan_start[1]
            self._pan_x = self._pan_start_offset[0] - dx
            self._pan_y = self._pan_start_offset[1] - dy
            self._dibujar()

    def _on_scroll(self, event):
        if event.inaxes is None:
            return
        factor     = 1.15 if event.button == "up" else 1 / 1.15
        nuevo_zoom = float(np.clip(self._zoom * factor, self._zoom_min, self._zoom_max))
        if nuevo_zoom == self._zoom:
            return
        if event.xdata is not None:
            cx, cy   = self.catphan.centro_int
            view_cx  = cx + self._pan_x
            view_cy  = cy + self._pan_y
            rel_x    = event.xdata - view_cx
            rel_y    = event.ydata - view_cy
            scale    = nuevo_zoom / self._zoom
            self._pan_x += rel_x * (1 - 1 / scale)
            self._pan_y += rel_y * (1 - 1 / scale)
        self._zoom = nuevo_zoom
        self.slider_zoom.blockSignals(True)
        self.slider_zoom.setValue(int(self._zoom * 10))
        self.slider_zoom.blockSignals(False)
        self.lbl_zoom.setText(f"{self._zoom:.1f}×")
        self._dibujar()

    # ── selección de ROI ──────────────────────────────────────────────────────

    def _seleccionar_roi_cercano(self, xdata, ydata):
        """Selecciona el ROI cuyo centro esté más cerca del click."""
        mejor_nombre = None
        mejor_dist   = float("inf")

        for nombre in self.catphan.ROI_CONFIG:
            centro_px, radio_px = self.catphan.obtener_roi(nombre)
            dist = np.hypot(xdata - centro_px[0], ydata - centro_px[1])
            # Tolera click dentro del círculo o cerca del borde
            if dist < radio_px + 8 and dist < mejor_dist:
                mejor_dist   = dist
                mejor_nombre = nombre

        if mejor_nombre:
            self._roi_seleccionado = mejor_nombre
            # Sincronizar sliders locales con offset actual del ROI
            dx, dy = self.catphan.offsets_locales[mejor_nombre]
            self.slider_lx.blockSignals(True)
            self.slider_ly.blockSignals(True)
            self.slider_lx.setValue(int(dx * 10))
            self.slider_ly.setValue(int(dy * 10))
            self.slider_lx.blockSignals(False)
            self.slider_ly.blockSignals(False)
            self._dibujar()

    # ── reset ─────────────────────────────────────────────────────────────────

    def _reset_roi(self):
        if self._roi_seleccionado:
            self.catphan.reset_offsets_locales(self._roi_seleccionado)
            self.slider_lx.blockSignals(True)
            self.slider_ly.blockSignals(True)
            self.slider_lx.setValue(0)
            self.slider_ly.setValue(0)
            self.slider_lx.blockSignals(False)
            self.slider_ly.blockSignals(False)
            self._dibujar()

    def _reset_all(self):
        self.catphan.offset_x   = 0.0
        self.catphan.offset_y   = 0.0
        self.catphan.offset_ang = 0.0
        self.catphan.reset_offsets_locales()
        self._zoom  = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        for s in [self.slider_gx, self.slider_gy, self.slider_ang,
                  self.slider_lx, self.slider_ly, self.slider_zoom]:
            s.blockSignals(True)
            s.setValue(0)
            s.blockSignals(False)
        self.slider_zoom.setValue(10)
        self.lbl_zoom.setText("1.0×")
        self._roi_seleccionado = None
        self._display_oculto = {nombre: False for nombre in self.catphan.ROI_CONFIG}
        for cb in self._checkboxes_visibilidad.values():
            cb.blockSignals(True)
            cb.setChecked(True)
            cb.blockSignals(False)
        self._visibilidad_manual = {nombre: True for nombre in self.catphan.ROI_CONFIG}
        self._actualizar_lista_ocultos()
        self._dibujar()
        
        

# ── Subclase de geometría ─────────────────────────────────────────────────────
 
class GeometriaCatphanCT(GeometriaCatphan):
    """
    Geometría para el módulo de Número CT (CTP404).
 
    Diferencia clave respecto a GeometriaCatphan: cada ROI tiene su propia
    distancia radial (distancia_mm), por lo que _calcular_roi_float la lee
    del ROI_CONFIG en lugar de usar ROI_DIST_MM fija.
 
    No se usan offsets locales: el phantom CTP404 se ajusta solo de forma
    global (Δx, Δy, Δθ). Esa decisión es intencional.
    """
 
    ROI_CONFIG = {
        "Teflon":       {"angulo": 300, "distancia_mm": 59, "radio_mm": 5},
        "Delrin":       {"angulo":   0, "distancia_mm": 58, "radio_mm": 5},
        "Acrilico":     {"angulo":  60, "distancia_mm": 58, "radio_mm": 5},
        "Poliestireno": {"angulo": 120, "distancia_mm": 59, "radio_mm": 5},
        "LDPE":         {"angulo": 180, "distancia_mm": 59, "radio_mm": 5},
        "PMP":          {"angulo": 240, "distancia_mm": 58, "radio_mm": 5},
        "Aire":         {"angulo": 270, "distancia_mm": 58, "radio_mm": 6},
    }
 
    # offsets locales no aplican; el dict se mantiene vacío para no romper
    # llamadas heredadas que pudieran consultarlo.
    def __init__(self, corte: np.ndarray, tam_px: float):
        super().__init__(corte, tam_px)
        # Sobreescribir offsets_locales con keys del ROI_CONFIG correcto
        self.offsets_locales = {nombre: [0.0, 0.0] for nombre in self.ROI_CONFIG}
 
    def _calcular_roi_float(self, nombre):
        info     = self.ROI_CONFIG[nombre]
        ang_rad  = np.radians(info["angulo"] + self.offset_ang)
        dist_px  = info["distancia_mm"] / self.tam_px
        radio_px = info["radio_mm"]     / self.tam_px

        cx = self.centro[0] + self.offset_x + dist_px * np.cos(ang_rad)
        cy = self.centro[1] + self.offset_y + dist_px * np.sin(ang_rad)

        # Offset local por ROI
        dx, dy = self.offsets_locales[nombre]
        cx += np.clip(dx, -self.MAX_OFFSET_LOCAL, self.MAX_OFFSET_LOCAL)
        cy += np.clip(dy, -self.MAX_OFFSET_LOCAL, self.MAX_OFFSET_LOCAL)

        return cx, cy, radio_px
 
# ── Posicionador ──────────────────────────────────────────────────────────────
 
class PosicionadorDialogCT(QDialog):
    """
    Posicionador manual para el módulo de Número CT (CTP404).
 
    Solo expone ajuste GLOBAL (Δx, Δy, Δθ): mueve los 7 ROIs en bloque.
    No hay modo Individual ni modo Manual — innecesarios para este módulo.
 
    Uso:
        catphan_ct = GeometriaCatphanCT(corte_255, tam_px)
        dlg = PosicionadorDialogCT(catphan_ct, corte_255, parent=self)
        dlg.exec_()
        # catphan_ct.offset_x/y/ang contienen los ajustes del usuario
        # (o 0.0 si canceló / no tocó nada)
    """
 
    COLORES = {
        "normal":  "lime",
        "phantom": "#8B3C3C",
    }
 
    def __init__(self, catphan: GeometriaCatphanCT, corte_255: np.ndarray, parent=None):
        super().__init__(parent)
        self.catphan = catphan
        self.corte   = corte_255
        self.setWindowTitle("Ajuste de posición — Número CT (CTP404)")
        self.setMinimumSize(900, 800)
 
        self._zoom      = 1.0
        self._zoom_min  = 1.0
        self._zoom_max  = 8.0
        self._pan_x     = 0.0
        self._pan_y     = 0.0
        self._panando   = False
        self._pan_start        = None
        self._pan_start_offset = None
 
        self._window_center = 128 // 2
        self._window_width  = 256 // 2
 
        self._build_ui()
        self._dibujar()
 
    # ── construcción UI ───────────────────────────────────────────────────────
 
    def _build_ui(self):
        layout_main = QVBoxLayout(self)
 
        # Fila superior: sliders de brillo/contraste + canvas
        layout_img = QHBoxLayout()
 
        layout_sliders = QVBoxLayout()
        self.slider_brillo = QSlider(Qt.Vertical)
        self.slider_brillo.setRange(0, 255)
        self.slider_brillo.setValue(self._window_center)
 
        self.slider_contraste = QSlider(Qt.Vertical)
        self.slider_contraste.setRange(1, 512)
        self.slider_contraste.setValue(self._window_width)
 
        self.slider_brillo.valueChanged.connect(self._on_window_change)
        self.slider_contraste.valueChanged.connect(self._on_window_change)
 
        layout_sliders.addWidget(QLabel("Brillo"))
        layout_sliders.addWidget(self.slider_brillo)
        layout_sliders.addWidget(QLabel("Contraste"))
        layout_sliders.addWidget(self.slider_contraste)
 
        self.fig    = Figure(figsize=(6, 6), tight_layout=True)
        self.canvas = FigureCanvas(self.fig)
 
        layout_img.addLayout(layout_sliders)
        layout_img.addWidget(self.canvas, stretch=1)
        layout_main.addLayout(layout_img)
 
        # Instrucción
        lbl_instruccion = QLabel(
            "Sliders Δx / Δy / Δθ mueven los 7 ROIs juntos  |  "
            "Click derecho + arrastrar: paneo  |  Rueda: zoom"
        )
        lbl_instruccion.setAlignment(Qt.AlignCenter)
        layout_main.addWidget(lbl_instruccion)
 
        # Panel de corrección global
        group_global   = QGroupBox("Corrección global")
        layout_global  = QVBoxLayout(group_global)
        group_ind = QGroupBox("Ajuste individual de ROIs")
        layout_ind = QVBoxLayout(group_ind)

        # Selector de ROI
        fila_sel = QHBoxLayout()
        fila_sel.addWidget(QLabel("ROI:"))
        self.combo_roi = QComboBox()
        self.combo_roi.addItems(list(self.catphan.ROI_CONFIG.keys()))
        self.combo_roi.currentTextChanged.connect(self._on_roi_seleccionado)
        fila_sel.addWidget(self.combo_roi, stretch=1)

        btn_reset_roi = QPushButton("Reset ROI")
        btn_reset_roi.clicked.connect(self._reset_roi_individual)
        fila_sel.addWidget(btn_reset_roi)
        layout_ind.addLayout(fila_sel)

        # Sliders dx / dy individuales
        MAX = self.catphan.MAX_OFFSET_LOCAL  # límite físico de la clase
        STEPS = MAX * 10  # resolución 0.1 px

        self.slider_ix = self._make_slider(-STEPS, STEPS, 0)
        self.slider_iy = self._make_slider(-STEPS, STEPS, 0)
        self.lbl_ix = QLabel("dx = 0.0 px")
        self.lbl_iy = QLabel("dy = 0.0 px")

        for lbl, slider, tag in [
            (self.lbl_ix, self.slider_ix, "dx"),
            (self.lbl_iy, self.slider_iy, "dy"),
        ]:
            fila = QHBoxLayout()
            fila.addWidget(lbl, stretch=1)
            fila.addWidget(slider, stretch=4)
            layout_ind.addLayout(fila)

        self.slider_ix.valueChanged.connect(self._on_individual_slider)
        self.slider_iy.valueChanged.connect(self._on_individual_slider)

        layout_main.addWidget(group_ind)
        self.slider_gx  = self._make_slider(-50, 50, 0)
        self.slider_gy  = self._make_slider(-50, 50, 0)
        self.slider_ang = self._make_slider(-100, 100, 0)
        self.lbl_gx  = QLabel("Δx = 0.0 px")
        self.lbl_gy  = QLabel("Δy = 0.0 px")
        self.lbl_ang = QLabel("Δθ = 0.0°")
 
        for lbl, slider in [
            (self.lbl_gx,  self.slider_gx),
            (self.lbl_gy,  self.slider_gy),
            (self.lbl_ang, self.slider_ang),
        ]:
            row = QHBoxLayout()
            row.addWidget(lbl, stretch=1)
            row.addWidget(slider, stretch=4)
            layout_global.addLayout(row)
 
        self.slider_gx.valueChanged.connect(self._on_global_slider)
        self.slider_gy.valueChanged.connect(self._on_global_slider)
        self.slider_ang.valueChanged.connect(self._on_global_slider)
        layout_main.addWidget(group_global)
 
        # Zoom
        layout_zoom = QHBoxLayout()
        layout_zoom.addWidget(QLabel("Zoom:"))
        self.slider_zoom = self._make_slider(10, 80, 10)
        self.lbl_zoom = QLabel("1.0×")
        self.lbl_zoom.setFixedWidth(40)
        self.slider_zoom.valueChanged.connect(self._on_zoom)
        layout_zoom.addWidget(self.slider_zoom, stretch=5)
        layout_zoom.addWidget(self.lbl_zoom)
        layout_main.addLayout(layout_zoom)
 
        # Estado
        self.lbl_estado = QLabel("")
        self.lbl_estado.setAlignment(Qt.AlignCenter)
        layout_main.addWidget(self.lbl_estado)
 
        # Botones
        layout_btn = QHBoxLayout()
        btn_reset = QPushButton("Reset todo")
        btn_reset.clicked.connect(self._reset_all)
        btn_ok     = QPushButton("Confirmar")
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        layout_btn.addWidget(btn_reset)
        layout_btn.addStretch()
        layout_btn.addWidget(btn_cancel)
        layout_btn.addWidget(btn_ok)
        layout_main.addLayout(layout_btn)
 
        # Eventos canvas
        self.canvas.mpl_connect("button_press_event",   self._on_press)
        self.canvas.mpl_connect("button_release_event", self._on_release)
        self.canvas.mpl_connect("motion_notify_event",  self._on_motion)
        self.canvas.mpl_connect("scroll_event",         self._on_scroll)
 
    @staticmethod
    def _make_slider(min_v, max_v, val):
        s = QSlider(Qt.Horizontal)
        s.setRange(min_v, max_v)
        s.setValue(val)
        return s
 
    # ── dibujo ────────────────────────────────────────────────────────────────
 
    def _limites_zoom(self):
        h, w   = self.corte.shape
        cx, cy = self.catphan.centro_int
        half_w = (w / 2) / self._zoom
        half_h = (h / 2) / self._zoom
        view_cx = cx + self._pan_x
        view_cy = cy + self._pan_y
        x0 = max(0, view_cx - half_w);  x1 = min(w, view_cx + half_w)
        y0 = max(0, view_cy - half_h);  y1 = min(h, view_cy + half_h)
        return x0, x1, y0, y1
 
    def _dibujar(self):
        self.fig.clear()
        ax = self.fig.add_subplot(111)
 
        vmin = self._window_center - self._window_width / 2
        vmax = self._window_center + self._window_width / 2
        ax.imshow(self.corte, cmap="gray", origin="upper", vmin=vmin, vmax=vmax)
        ax.axis("off")
 
        c = self.catphan
        cx, cy = c.centro_int
 
        # Contorno del phantom
        ax.add_patch(mpatches.Circle(
            (cx, cy), c.radio_int,
            fill=False, color=self.COLORES["phantom"],
            linewidth=1.2, linestyle="--"
        ))
 
        # ROIs
        for nombre in c.ROI_CONFIG:
            centro_px, radio_px = c.obtener_roi(nombre)
            ax.add_patch(mpatches.Circle(
                centro_px, radio_px,
                fill=False, color=self.COLORES["normal"], linewidth=1.2
            ))
            ax.text(
                centro_px[0], centro_px[1] - radio_px - 4,
                nombre, color=self.COLORES["normal"], fontsize=7, ha="center"
            )
 
        # Crosshair
        ax.axhline(cy, color="cyan", linewidth=0.5, alpha=0.4)
        ax.axvline(cx, color="cyan", linewidth=0.5, alpha=0.4)
 
        x0, x1, y0, y1 = self._limites_zoom()
        ax.set_xlim(x0, x1)
        ax.set_ylim(y1, y0)
 
        ax.set_title(
            f"Número CT — Zoom {self._zoom:.1f}×  |  "
            f"Δx={c.offset_x:.1f}  Δy={c.offset_y:.1f}  Δθ={c.offset_ang:.1f}°",
            fontsize=9
        )
 
        self.lbl_gx.setText(f"Δx = {c.offset_x:.1f} px")
        self.lbl_gy.setText(f"Δy = {c.offset_y:.1f} px")
        self.lbl_ang.setText(f"Δθ = {c.offset_ang:.1f}°")
        self.lbl_estado.setText(f"Centro phantom: {c.centro_int}")
 
        self.canvas.draw_idle()
    
    
    def _on_roi_seleccionado(self, nombre: str):
        """Sincroniza sliders con el offset actual del ROI seleccionado."""
        dx, dy = self.catphan.offsets_locales[nombre]
        MAX_STEPS = self.catphan.MAX_OFFSET_LOCAL * 10

        # Bloquear señales para no disparar _on_individual_slider
        for s in (self.slider_ix, self.slider_iy):
            s.blockSignals(True)

        self.slider_ix.setValue(int(round(dx * 10)))
        self.slider_iy.setValue(int(round(dy * 10)))

        for s in (self.slider_ix, self.slider_iy):
            s.blockSignals(False)

        self.lbl_ix.setText(f"dx = {dx:.1f} px")
        self.lbl_iy.setText(f"dy = {dy:.1f} px")

    def _on_individual_slider(self):
        nombre = self.combo_roi.currentText()
        dx = self.slider_ix.value() / 10.0
        dy = self.slider_iy.value() / 10.0

        self.catphan.offsets_locales[nombre] = [dx, dy]

        self.lbl_ix.setText(f"dx = {dx:.1f} px")
        self.lbl_iy.setText(f"dy = {dy:.1f} px")
        self._dibujar()

    def _reset_roi_individual(self):
        nombre = self.combo_roi.currentText()
        self.catphan.reset_offsets_locales(nombre)

        for s in (self.slider_ix, self.slider_iy):
            s.blockSignals(True)
            s.setValue(0)
            s.blockSignals(False)

        self.lbl_ix.setText("dx = 0.0 px")
        self.lbl_iy.setText("dy = 0.0 px")
        self._dibujar()
    # ── eventos sliders ───────────────────────────────────────────────────────
 
    def _on_window_change(self):
        self._window_center = self.slider_brillo.value()
        self._window_width  = self.slider_contraste.value()
        self._dibujar()
 
    def _on_global_slider(self):
        self.catphan.offset_x   = float(self.slider_gx.value())
        self.catphan.offset_y   = float(self.slider_gy.value())
        self.catphan.offset_ang = self.slider_ang.value() / 10.0
        self._dibujar()
 
    def _on_zoom(self, valor):
        self._zoom = valor / 10.0
        self.lbl_zoom.setText(f"{self._zoom:.1f}×")
        self._dibujar()
 
    # ── eventos mouse ─────────────────────────────────────────────────────────
    def _on_press(self, event):
        if event.inaxes is None:
            return
        if event.button == 3 and self._modo == "manual":
            nombre = self._roi_bajo_cursor(event.xdata, event.ydata)
            if nombre:
                self._display_oculto[nombre] = True
                self._visibilidad_manual[nombre] = False
                self._checkboxes_visibilidad[nombre].blockSignals(True)
                self._checkboxes_visibilidad[nombre].setChecked(False)
                self._checkboxes_visibilidad[nombre].blockSignals(False)
                self._actualizar_lista_ocultos()
                self._dibujar()
                return
            # Sin ROI bajo cursor → pan normal
            self._panando = True
            self._pan_start = (event.xdata, event.ydata)
            self._pan_start_offset = (self._pan_x, self._pan_y)

        elif event.button == 3:
            self._panando = True
            self._pan_start = (event.xdata, event.ydata)
            self._pan_start_offset = (self._pan_x, self._pan_y)

        elif event.button == 1 and self._modo == "individual":
            self._seleccionar_roi_cercano(event.xdata, event.ydata)
 
    
    def _on_release(self, event):
        self._panando = False
 
    def _on_motion(self, event):
        if self._panando and event.inaxes and self._pan_start:
            dx = event.xdata - self._pan_start[0]
            dy = event.ydata - self._pan_start[1]
            self._pan_x = self._pan_start_offset[0] - dx
            self._pan_y = self._pan_start_offset[1] - dy
            self._dibujar()
 
    def _on_scroll(self, event):
        if event.inaxes is None:
            return
        factor     = 1.15 if event.button == "up" else 1 / 1.15
        nuevo_zoom = float(np.clip(self._zoom * factor, self._zoom_min, self._zoom_max))
        if nuevo_zoom == self._zoom:
            return
        if event.xdata is not None:
            cx, cy  = self.catphan.centro_int
            view_cx = cx + self._pan_x
            view_cy = cy + self._pan_y
            rel_x   = event.xdata - view_cx
            rel_y   = event.ydata - view_cy
            scale   = nuevo_zoom / self._zoom
            self._pan_x += rel_x * (1 - 1 / scale)
            self._pan_y += rel_y * (1 - 1 / scale)
        self._zoom = nuevo_zoom
        self.slider_zoom.blockSignals(True)
        self.slider_zoom.setValue(int(self._zoom * 10))
        self.slider_zoom.blockSignals(False)
        self.lbl_zoom.setText(f"{self._zoom:.1f}×")
        self._dibujar()
 
    # ── reset ─────────────────────────────────────────────────────────────────
 
    
    def _reset_all(self):
        self.catphan.offset_x   = 0.0
        self.catphan.offset_y   = 0.0
        self.catphan.offset_ang = 0.0
        self.catphan.reset_offsets_locales()  # ← agregar esta línea

        self._zoom  = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0

        for s in [self.slider_gx, self.slider_gy, self.slider_ang, self.slider_zoom]:
            s.blockSignals(True)
            s.setValue(0 if s is not self.slider_zoom else 10)
            s.blockSignals(False)

        # Resetear también sliders individuales
        for s in (self.slider_ix, self.slider_iy):
            s.blockSignals(True)
            s.setValue(0)
            s.blockSignals(False)

        self.lbl_ix.setText("dx = 0.0 px")
        self.lbl_iy.setText("dy = 0.0 px")
        self.lbl_zoom.setText("1.0×")
        self._dibujar()
        