import numpy as np
import cv2
from pylinac import PicketFence
from pylinac import Starshot
from pylinac.picketfence import MLC
import pydicom
import pydicom.data
import matplotlib.pyplot as plt
from scipy.signal import find_peaks
import matplotlib.patches as mpatches
from matplotlib.figure import Figure
from matplotlib.collections import LineCollection
from matplotlib.patches import FancyArrowPatch, Circle, Wedge
from matplotlib.gridspec import GridSpec
from matplotlib.ticker import MaxNLocator

class MLC_MEASSUREMENT():
    def __init__(self):
        """
        Iniciar la clase de MLC_MEASSUREMENT 
        """
    def picket_fence(self, dicom_file, tolerance, action_tolerance):
        self.pf = PicketFence(dicom_file, mlc=MLC.MILLENNIUM)
        self.pf.analyze(tolerance=tolerance, action_tolerance=action_tolerance, edge_threshold=3)
        dicom_info = pydicom.dcmread(dicom_file)
        print("Información DICOM")
        print(dicom_info)
        print("Diccionario con resultados")
        
       
        
        for m in self.pf.mlc_meas[:10]:
            print(vars(m))
        
        print("DATOS MLC")
        print(self.pf)
        print("DATOS MLC MEAS")
        print(self.pf.mlc_meas)        
        
        
        #print(f" Numero de hojas : {num_leaves}")
        
    
        
       
        return self.pf
                
#############################################################################################

import matplotlib.patches as mpatches
from matplotlib.figure import Figure
from matplotlib.collections import LineCollection
from matplotlib.patches import FancyArrowPatch, Rectangle


# ────────────────────────────────────────────────────────────────
#  Paleta
# ────────────────────────────────────────────────────────────────
_COL_OK      = "#4CAF82"
_COL_WARN    = "#E8A838"
_COL_FAIL    = "#E05252"
_COL_BG      = "#f4f6f8"
_COL_GRID    = "#cccccc"
_COL_TEXT    = "#1a1a2e"
_COL_SUBTEXT = "#555577"
_COL_LINE    = "#aaaaaa"
_COL_A       = "#3A7FC1"   # azul banco A
_COL_B       = "#E8834A"   # naranja banco B
_COL_ZERO    = "#888888"
_COL_CIRCLE = "#27F5D3"


def _error_color(error_abs, tol, action_tol=None):
    """Devuelve color según magnitud del error."""
    
   
    if action_tol < error_abs < tol :
        return _COL_WARN
    if error_abs  > tol:
        return _COL_FAIL
    
    
    return _COL_OK
 
def _style_ax(ax):
    """Aplica estilo coherente a un eje."""
    ax.set_facecolor(_COL_BG)
    ax.tick_params(colors=_COL_TEXT, labelsize=7)
    ax.xaxis.label.set_color(_COL_TEXT)
    ax.yaxis.label.set_color(_COL_TEXT)
    ax.title.set_color(_COL_TEXT)
    for spine in ax.spines.values():
        spine.set_edgecolor(_COL_LINE)
    ax.grid(color=_COL_GRID, linewidth=0.4, zorder=0)
 
 
def _spoke_color(deviation_deg, tolerance_deg, action_deg=None):
    """Devuelve color según la desviación angular del rayo."""
    if action_deg and abs(deviation_deg) > action_deg:
        return _COL_FAIL
    if abs(deviation_deg) > tolerance_deg:
        return _COL_FAIL
    if abs(deviation_deg) > tolerance_deg * 0.80:
        return _COL_WARN
    return _COL_OK
 

# ────────────────────────────────────────────────────────────────
#  Vista 1: PEINE
# ────────────────────────────────────────────────────────────────
def _dibujar_peine(fig, canvas, processed):
    """
    Peine físico:
    eje X  = offset del picket desde el CAX (mm)
    eje Y  = índice de lámina (posición física a lo largo del MLC)
    segmento horizontal = lámina; color = error relativo a tolerancia
    """
    fig.clear()
    fig.patch.set_facecolor(_COL_BG)
    ax = fig.add_subplot(111)
    ax.set_facecolor(_COL_BG)

    hojas     = processed["leafs"]
    tol       = processed["tolerance"]
    action    = processed["action_tolerance"]
    offsets   = processed["offsets_cax"]      # list[float], len = n_pickets
    n_pick    = processed["n_pickets"]

    if not hojas or not offsets:
        ax.text(0.5, 0.5, "Sin datos", transform=ax.transAxes,
                ha="center", va="center", color=_COL_TEXT)
        canvas.draw()
        return

    leaf_nums = [h["leaf"] for h in hojas]
    n_leaves  = len(leaf_nums)

    # Altura de cada diente del peine (separación entre láminas)
    leaf_height = 0.70  # en unidades de índice de lámina

    # ── Dibujar cada diente ──────────────────────────────────────
    segments = []
    colors   = []

    for row_i, hoja in enumerate(hojas):
        y = row_i  # posición vertical = índice de lámina
        for col_i, err in enumerate(hoja["errors"]):
            if col_i >= len(offsets):
                continue
            x_center = offsets[col_i]
            half_w   = 5  + (err)           # anchura del diente en mm (visual)
            color    = _error_color(abs(err), tol, action)

            segments.append([(x_center - half_w, y),
                            (x_center + half_w, y)])
            colors.append(color)

    lc = LineCollection(segments, colors=colors, linewidths=4.5,
                        capstyle="round", zorder=3)
    ax.add_collection(lc)

    # ── Líneas verticales de cada picket (el "palo" del peine) ──
    x_min_data = min(offsets) - 8
    x_max_data = max(offsets) + 8

    for col_i, x in enumerate(offsets):
        ax.axvline(x, color=_COL_LINE, linewidth=0.8, zorder=1)

    # ── Zonas clicables (rectángulos invisibles por picket) ──────
    # Se guardan para el handler de clicks
    picket_zones = []
    zone_width = abs(offsets[1] - offsets[0]) * 0.85 if n_pick > 1 else 10
    for col_i, x in enumerate(offsets):
        r = Rectangle(
            (x - zone_width / 2, -0.5),
            zone_width,
            n_leaves,
            facecolor="none",
            edgecolor="none",
            picker=True,
            zorder=5,
        )
        r._picket_idx = col_i          # metadato para el handler
        ax.add_patch(r)
        picket_zones.append(r)

    # ── Etiquetas de picket ──────────────────────────────────────
    for col_i, x in enumerate(offsets):
        ax.text(x, n_leaves + 0.3,
                f"P{col_i}\n{x:+.1f}mm",
                ha="center", va="bottom",
                fontsize=7, color=_COL_SUBTEXT)

    # ── Eje Y: números de lámina ──────────────────────────────────
    step = max(1, n_leaves // 20)     # evitar saturación
    ax.set_yticks(range(0, n_leaves, step))
    ax.set_yticklabels([str(leaf_nums[i]) for i in range(0, n_leaves, step)],
                    fontsize=7, color=_COL_TEXT)

    # ── Línea de tolerancia (referencia visual) ──────────────────
    # No aplica en eje X aquí, solo anotación
    ax.text(x_max_data, -0.8,
            f"Tol: {tol} mm | Act: {action} mm",
            ha="right", va="top", fontsize=7.5, color=_COL_SUBTEXT)

    # ── Leyenda compacta ─────────────────────────────────────────
    legend_patches = [
        mpatches.Patch(color=_COL_OK,   label="Dentro de tol."),
        mpatches.Patch(color=_COL_WARN, label=f">{tol*0.8:.2f} mm (límite)"),
        mpatches.Patch(color=_COL_FAIL, label=f"Fuera (>{tol} mm)"),
    ]
    fig.legend(
        handles=legend_patches,
        loc="lower center",
        ncol=3,
        fontsize=7,
        framealpha=0.2,
        labelcolor=_COL_TEXT,
        facecolor=_COL_BG,
        bbox_to_anchor=(0.5, 0.0)
    )
    

    # ── Estilo de ejes ───────────────────────────────────────────
    ax.set_ylim(-1, n_leaves + 1)
    ax.set_xlabel("Posición del picket (mm desde CAX)", fontsize=9,
                color=_COL_TEXT)
    ax.set_ylabel("Número de lámina", fontsize=9, color=_COL_TEXT)
    ax.set_title("Picket Fence — Vista de peine",
                fontsize=11, fontweight="bold", color=_COL_TEXT, pad=40)

    ax.tick_params(colors=_COL_TEXT, labelsize=7)
    for spine in ax.spines.values():
        spine.set_edgecolor(_COL_LINE)
    ax.set_facecolor(_COL_BG)
    ax.xaxis.label.set_color(_COL_TEXT)
    ax.yaxis.label.set_color(_COL_TEXT)
    ax.grid(axis="x", color=_COL_GRID, linewidth=0.5, zorder=0)

    # ── Indicador de interactividad ──────────────────────────────
    ax.text(0.5, 1.02,
            "↓  Click sobre un picket para ver su perfil de errores",
            transform=ax.transAxes, ha="center", va="bottom",
            fontsize=7.5, color=_COL_SUBTEXT, style="italic")

    fig.tight_layout(rect=[0, 0.06, 1, 0.95])
    canvas.draw()

    return picket_zones   # devueltos para que el handler los conozca


# ────────────────────────────────────────────────────────────────
#  Vista 2: BARRAS DE UN PICKET
# ────────────────────────────────────────────────────────────────
def _dibujar_picket_detalle(fig, canvas, processed, picket_idx):
    """
    Barras horizontales de error (mm) para cada lámina del picket
    seleccionado.  Orden: láminas de menor a mayor número (eje Y).
    """
    fig.clear()
    fig.patch.set_facecolor(_COL_BG)
    ax = fig.add_subplot(111)
    ax.set_facecolor(_COL_BG)

    hojas   = processed["leafs"]
    tol     = processed["tolerance"]
    action  = processed["action_tolerance"]
    offsets = processed["offsets_cax"]

    offset_mm = offsets[picket_idx] if picket_idx < len(offsets) else 0.0

    # Recolectar datos de este picket para todas las láminas
    leaf_nums = []
    errors    = []
    for hoja in hojas:
        if picket_idx < len(hoja["errors"]):
            leaf_nums.append(hoja["leaf"])
            errors.append(abs(hoja["errors"][picket_idx]))

    if not errors:
        ax.text(0.5, 0.5, "Sin datos para este picket",
                transform=ax.transAxes, ha="center", va="center",
                color=_COL_TEXT)
        canvas.draw()
        return

    y_pos  = np.arange(len(leaf_nums))
    colors = [_error_color(e, tol, action) for e in errors]

    bars = ax.barh(y_pos, errors, color=colors, height=0.65,
                edgecolor="none", zorder=3)

    # ── Etiqueta de valor en cada barra ──────────────────────────
    max_err = max(errors) if errors else tol
    for bar, val, color in zip(bars, errors, colors):
        x_label = bar.get_width() + max_err * 0.02
        ax.text(x_label, bar.get_y() + bar.get_height() / 2,
                f"{val:.4f}",
                va="center", ha="left", fontsize=6.5,
                color=color)

    # ── Líneas de referencia ─────────────────────────────────────
    ax.axvline(tol, color=_COL_FAIL, linewidth=1.2,
            linestyle="--", label=f"Tolerancia ({tol} mm)", zorder=4)
    ax.axvline(action, color="#E05252AA", linewidth=0.8,
            linestyle=":", label=f"Acción ({action} mm)", zorder=4)

    # ── Eje Y: números de lámina ─────────────────────────────────
    step = max(1, len(leaf_nums) // 25)
    ax.set_yticks(y_pos[::step])
    ax.set_yticklabels([str(leaf_nums[i]) for i in range(0, len(leaf_nums), step)],
                    fontsize=6.5, color=_COL_TEXT)

    # ── Estilo ───────────────────────────────────────────────────
    ax.set_xlabel("Error absoluto (mm)", fontsize=9, color=_COL_TEXT)
    ax.set_ylabel("Número de lámina",    fontsize=9, color=_COL_TEXT)
    ax.set_title(
        f"Picket {picket_idx}  |  offset: {offset_mm:+.1f} mm desde CAX",
        fontsize=11, fontweight="bold", color=_COL_TEXT, pad=8
    )
    ax.set_xlim(0, max(max_err * 1.35, tol * 1.5))
    ax.set_ylim(-0.5, len(leaf_nums) - 0.5)

    ax.tick_params(colors=_COL_TEXT, labelsize=7)
    for spine in ax.spines.values():
        spine.set_edgecolor(_COL_LINE)
    ax.grid(axis="x", color=_COL_GRID, linewidth=0.5, zorder=0)

    ax.legend(fontsize=7.5, framealpha=0.25,
            labelcolor=_COL_TEXT, facecolor=_COL_BG,
            loc="lower right")

    # ── Estadísticas breves ──────────────────────────────────────
    n_fail = sum(1 for e in errors if e > tol)
    pct_ok = (len(errors) - n_fail) / len(errors) * 100 if errors else 100
    ax.text(0.02, 0.01,
            f"Láminas OK: {pct_ok:.1f}%  |  Fuera de tol: {n_fail}",
            transform=ax.transAxes, ha="left", va="bottom",
            fontsize=7, color=_COL_SUBTEXT)

    # ── Instrucción de regreso ────────────────────────────────────
    ax.text(0.5, 1.02,
            "↑  Click en fondo para volver al peine",
            transform=ax.transAxes, ha="center", va="bottom",
            fontsize=7.5, color=_COL_SUBTEXT, style="italic")

    fig.tight_layout()
    canvas.draw()


# ────────────────────────────────────────────────────────────────
#  Conexión de interactividad
# ────────────────────────────────────────────────────────────────
def _conectar_interactividad(fig, canvas, data, processed):
    """
    Registra los event handlers de Matplotlib para:
    - click en zona de picket  → detalle del picket
    - click en fondo           → volver al peine

    Devuelve un dict con el estado de navegación por si necesitas
    consultarlo desde fuera.
    """
    estado = {
        "vista":       "peine",     # "peine" | "picket"
        "picket_idx":  None,
        "cid_press":   None,
    }

    # Dibujar peine inicial y obtener las zonas clicables
    _dibujar_peine(fig, canvas, processed)

    def _on_click(event):
        if event.button != 3:  # solo clic derecho
            return

        if event.inaxes is None:
            return
        ax = fig.axes[0]

        if estado["vista"] == "peine":
            # ¿Cayó dentro de alguna zona de picket?
            offsets   = processed["offsets_cax"]
            n_pick    = processed["n_pickets"]

            if not offsets:
                return

            zone_width = abs(offsets[1] - offsets[0]) * 0.85 if n_pick > 1 else 10
            x_click    = event.xdata
            y_click    = event.ydata
            n_leaves   = len(processed["leafs"])

            hit = None
            for col_i, x in enumerate(offsets):
                if (abs(x_click - x) <= zone_width / 2
                        and -0.5 <= y_click <= n_leaves - 0.5):
                    hit = col_i
                    break

            if hit is not None:
                estado["vista"]      = "picket"
                estado["picket_idx"] = hit
                _dibujar_picket_detalle(fig, canvas, processed, hit)

        elif estado["vista"] == "picket":
            # Cualquier click fuera de una barra regresa al peine
            # (simplificación: cualquier click en el fondo del eje)
            estado["vista"]      = "peine"
            estado["picket_idx"] = None
            _dibujar_peine(fig, canvas, processed)
        # print(f"Click recibido: xdata={event.xdata}, ydata={event.ydata}, vista={estado['vista']}")
        # print(f"x_click={x_click:.2f}, offsets={offsets}, zone_width={zone_width:.2f}, n_leaves={n_leaves}, y_click={y_click:.2f}")
        if event.inaxes is None:
            print("Click fuera de ejes")

    cid = canvas.mpl_connect("button_press_event", _on_click)
    estado["cid_press"] = cid

    return estado
    

def _dibujar_perfiles_picket(fig, canvas, processed):
    """
    Un subplot por picket.  Eje X = número de lámina, eje Y = error con signo (mm).
    El signo importa para detectar bias sistemático (todas las láminas desplazadas
    en la misma dirección) vs. ruido aleatorio.
 
    Layout: hasta 5 columnas, filas calculadas dinámicamente.
    """
    fig.clear()
    fig.patch.set_facecolor(_COL_BG)
 
    hojas    = processed["leafs"]
    n_pick   = processed["n_pickets"]
    tol      = processed["tolerance"]
    action   = processed["action_tolerance"]
    offsets  = processed["offsets_cax"]
 
    if not hojas or n_pick == 0:
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, "Sin datos", transform=ax.transAxes,
                ha="center", va="center", color=_COL_TEXT)
        canvas.draw()
        return
 
    leaf_nums = [h["leaf"] for h in hojas]
 
    ncols = min(n_pick, 5)
    nrows = int(np.ceil(n_pick / ncols))
    gs    = GridSpec(nrows, ncols, figure=fig,
                     hspace=0.55, wspace=0.35,
                     left=0.06, right=0.97, top=0.90, bottom=0.08)
 
    y_abs_max = 0.0
    # Pre-calcular rango global para escala uniforme
    for hoja in hojas:
        for e in hoja["errors"]:
            if abs(e) > y_abs_max:
                y_abs_max = abs(e)
    y_lim = max(y_abs_max * 1.25, tol * 1.5)
 
    for p_idx in range(n_pick):
        row = p_idx // ncols
        col = p_idx  % ncols
        ax  = fig.add_subplot(gs[row, col])
        _style_ax(ax)
 
        # Extraer errores con signo para este picket
        errors_signed = []
        valid_leaves  = []
        for hoja in hojas:
            if p_idx < len(hoja["errors"]):
                errors_signed.append(hoja["errors"][p_idx])
                valid_leaves.append(hoja["leaf"])
 
        if not errors_signed:
            ax.text(0.5, 0.5, "—", transform=ax.transAxes,
                    ha="center", va="center", color=_COL_SUBTEXT, fontsize=8)
            continue
 
        errors_arr = np.array(errors_signed)
        x          = np.arange(len(valid_leaves))
 
        # Barras coloreadas por magnitud absoluta
        bar_colors = [_error_color(abs(e), tol, action) for e in errors_arr]
        ax.bar(x, errors_arr, color=bar_colors, width=0.8,
               edgecolor="none", zorder=3, alpha=0.85)
 
        # Líneas de tolerancia
        ax.axhline( tol,    color=_COL_FAIL, linewidth=0.9, linestyle="--", zorder=4)
        ax.axhline(-tol,    color=_COL_FAIL, linewidth=0.9, linestyle="--", zorder=4)
        ax.axhline( action, color="#E05252AA", linewidth=0.6, linestyle=":", zorder=4)
        ax.axhline(-action, color="#E05252AA", linewidth=0.6, linestyle=":", zorder=4)
        ax.axhline(0,       color=_COL_ZERO, linewidth=0.7, zorder=2)
 
        # Estadísticas del picket
        mean_e = float(np.mean(errors_arr))
        std_e  = float(np.std(errors_arr))
 
        ax.set_title(
            f"Picket {p_idx} mm",
            fontsize=7.5, fontweight="bold", color=_COL_TEXT, pad=3
        )
 
        # Eje X: mostrar solo algunos leaf_nums para no saturar
        step = max(1, len(valid_leaves) // 10)
        ax.set_xticks(x[::step])
        ax.set_xticklabels([str(valid_leaves[i]) for i in range(0, len(valid_leaves), step)],
                           fontsize=5.5, rotation=45)
        ax.set_ylim(-y_lim, y_lim)
        ax.set_xlabel("Lámina", fontsize=6, color=_COL_TEXT)
        if col == 0:
            ax.set_ylabel("Error (mm)", fontsize=6, color=_COL_TEXT)
 
        # Anotación μ ± σ
        ax.text(0.97, 0.97,
                f"μ={mean_e:+.3f}\nσ={std_e:.3f}",
                transform=ax.transAxes, ha="right", va="top",
                fontsize=5.5, color=_COL_SUBTEXT,
                bbox=dict(facecolor=_COL_BG, edgecolor=_COL_LINE,
                          boxstyle="round,pad=0.2", alpha=0.8))
 
    # Leyenda global
    legend_patches = [
        mpatches.Patch(color=_COL_OK,   label="Dentro de tol."),
        mpatches.Patch(color=_COL_WARN, label="≥80 % tol."),
        mpatches.Patch(color=_COL_FAIL, label="Fuera de tol."),
    ]
    fig.legend(handles=legend_patches, loc="upper center",
               ncol=3, fontsize=7, framealpha=0.3,
               labelcolor=_COL_TEXT, facecolor=_COL_BG,
               bbox_to_anchor=(0.5, 0.98))
 
    fig.suptitle("Perfiles de error por picket (con signo)",
                 fontsize=11, fontweight="bold", color=_COL_TEXT, y=0.995)
 
    canvas.draw()
 
 
# ═════════════════════════════════════════════════════════════════════════════
#  2. ASIMETRÍA BANCOS A / B  (Millennium 120: A = láminas 1-60, B = 61-120)
# ═════════════════════════════════════════════════════════════════════════════




# ═════════════════════════════════════════════════════════════════════════════
#  3. VARIANZA INTER-PICKET
# ═════════════════════════════════════════════════════════════════════════════
def _dibujar_varianza_interpicket(fig, canvas, processed):
    """
    Para cada lámina calcula mean y std de su error a través de todos los pickets.
 
    Panel izquierdo  : std por lámina (barras horizontales) — alta std indica
                       comportamiento mecánico inconsistente.
    Panel derecho    : heatmap de error con signo (lámina × picket) — permite ver
                       si la varianza es aleatoria o sigue un patrón espacial.
 
    Umbral de alerta: std > tol * 0.3 se considera varianza significativa.
    """
    fig.clear()
    fig.patch.set_facecolor(_COL_BG)
 
    hojas  = processed["leafs"]
    n_pick = processed["n_pickets"]
    tol    = processed["tolerance"]
 
    if not hojas or n_pick < 2:
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5,
                "Se necesitan al menos 2 pickets para\ncalcular varianza inter-picket.",
                transform=ax.transAxes, ha="center", va="center",
                color=_COL_TEXT, fontsize=9)
        canvas.draw()
        return
 
    leaf_nums = [h["leaf"] for h in hojas]
    n_leaves  = len(leaf_nums)
 
    # ── Construir matriz de errores (con signo) ────────────────────
    # Forma: (n_leaves, n_pick)
    error_matrix = np.full((n_leaves, n_pick), np.nan)
    for row_i, hoja in enumerate(hojas):
        for col_i, err in enumerate(hoja["errors"]):
            if col_i < n_pick:
                error_matrix[row_i, col_i] = err
 
    means_per_leaf = np.nanmean(error_matrix, axis=1)   # (n_leaves,)
    std_per_leaf   = np.nanstd( error_matrix, axis=1)   # (n_leaves,)
 
    std_threshold = tol * 0.3
 
    # ── Layout ───────────────────────────────────────────────────
    gs = GridSpec(1, 2, figure=fig,
                  width_ratios=[1, 1.6],
                  hspace=0.0, wspace=0.35,
                  left=0.08, right=0.97, top=0.88, bottom=0.08)
 
    ax_std  = fig.add_subplot(gs[0])
    ax_heat = fig.add_subplot(gs[1])
 
    # ── Panel izquierdo: std por lámina ───────────────────────────
    _style_ax(ax_std)
    y_pos  = np.arange(n_leaves)
    std_colors = [(_COL_FAIL if s > std_threshold else
                   (_COL_WARN if s > std_threshold * 0.7 else _COL_OK))
                  for s in std_per_leaf]
 
    ax_std.barh(y_pos, std_per_leaf, color=std_colors,
                height=0.7, edgecolor="none", zorder=3, alpha=0.85)
    ax_std.axvline(std_threshold, color=_COL_FAIL, linewidth=1.0,
                   linestyle="--", zorder=4,
                   label=f"Umbral ({std_threshold:.3f} mm)")
    ax_std.set_xlabel("Desv. estándar inter-picket (mm)", fontsize=8, color=_COL_TEXT)
    ax_std.set_ylabel("Número de lámina", fontsize=8, color=_COL_TEXT)
    ax_std.set_title("Variabilidad\npor lámina", fontsize=9, fontweight="bold",
                      color=_COL_TEXT)
    ax_std.legend(fontsize=6.5, framealpha=0.3, labelcolor=_COL_TEXT, facecolor=_COL_BG)
 
    # Eje Y: números de lámina
    step = max(1, n_leaves // 25)
    ax_std.set_yticks(y_pos[::step])
    ax_std.set_yticklabels([str(leaf_nums[i]) for i in range(0, n_leaves, step)],
                            fontsize=6)
    ax_std.set_ylim(-0.5, n_leaves - 0.5)
 
    # Anotación de láminas con std alta
    n_high_std = int(np.sum(std_per_leaf > std_threshold))
    ax_std.text(0.97, 0.01,
                f"Láminas alta var.: {n_high_std}",
                transform=ax_std.transAxes, ha="right", va="bottom",
                fontsize=7, color=(_COL_FAIL if n_high_std > 0 else _COL_OK),
                fontweight="bold")
 
    # ── Panel derecho: heatmap error con signo ────────────────────
    _style_ax(ax_heat)
 
    # Escala simétrica centrada en 0
    vmax = max(np.nanmax(np.abs(error_matrix)), tol * 0.5)
 
    im = ax_heat.imshow(
        error_matrix,
        aspect="auto",
        cmap="plasma",      # rojo = positivo, azul = negativo
        vmin=-vmax, vmax=vmax,
        interpolation="nearest",
        origin="upper"
    )
 
    # Marcar con contorno las celdas fuera de tolerancia
    from matplotlib.patches import Rectangle
    for row_i in range(n_leaves):
        for col_i in range(n_pick):
            val = error_matrix[row_i, col_i]
            if not np.isnan(val) and abs(val) > tol:
                ax_heat.add_patch(Rectangle(
                    (col_i - 0.5, row_i - 0.5), 1, 1,
                    fill=False, edgecolor="#E05252", linewidth=1.5, zorder=4
                ))
 
    ax_heat.set_xticks(range(n_pick))
    ax_heat.set_xticklabels([f"P{i}" for i in range(n_pick)], fontsize=8)
    ax_heat.set_xlabel("Picket", fontsize=8, color=_COL_TEXT)
    ax_heat.set_ylabel("Número de lámina", fontsize=8, color=_COL_TEXT)
    ax_heat.set_title("Error con signo (mm)\nlámina × picket",
                       fontsize=9, fontweight="bold", color=_COL_TEXT)
 
    step_h = max(1, n_leaves // 25)
    ax_heat.set_yticks(y_pos[::step_h])
    ax_heat.set_yticklabels([str(leaf_nums[i]) for i in range(0, n_leaves, step_h)],
                             fontsize=6)
 
    cbar = fig.colorbar(im, ax=ax_heat, fraction=0.035, pad=0.03)
    cbar.set_label("Error con signo (mm)", fontsize=7.5, color=_COL_TEXT)
    cbar.ax.tick_params(labelsize=6.5, colors=_COL_TEXT)
    cbar.ax.axhline(y= tol, color=_COL_FAIL, linewidth=1.2, linestyle="--")
    cbar.ax.axhline(y=-tol, color=_COL_FAIL, linewidth=1.2, linestyle="--")
 
    fig.suptitle(
        f"Varianza inter-picket  |  umbral std = {std_threshold:.3f} mm  "
        f"(30 % tol)  |  {n_high_std} láminas sobre umbral",
        fontsize=10, fontweight="bold", color=_COL_TEXT, y=0.97
    )
    canvas.draw()
 


def _dibujar_analisis_estadistico(fig, canvas, processed):
    fig.clear()
    fig.patch.set_facecolor(_COL_BG)

    hojas   = processed["leafs"]
    n_pick  = processed["n_pickets"]
    tol     = processed["tolerance"]
    action  = processed["action_tolerance"]
    offsets = processed["offsets_cax"]
    n_leaves = len(hojas)

    if not hojas or n_pick == 0:
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, "Sin datos", transform=ax.transAxes,
                ha="center", va="center", color=_COL_TEXT)
        canvas.draw()
        return

    leaf_nums = [h["leaf"] for h in hojas]

    # ── Matriz de errores (n_leaves × n_pick) ─────────────────────────────────
    error_matrix = np.full((n_leaves, n_pick), np.nan)
    for row_i, hoja in enumerate(hojas):
        for col_i, err in enumerate(hoja["errors"]):
            if col_i < n_pick:
                error_matrix[row_i, col_i] = err

    # ── error_picket: picket_mean_error, picket_max_error ─────────────────────
    picket_mean_error = np.nanmean(np.abs(error_matrix), axis=0)   # (n_pick,)
    picket_max_error  = np.nanmax( np.abs(error_matrix), axis=0)   # (n_pick,)

    # ── leaf_error: std inter-picket por lámina ───────────────────────────────
    leaf_error = np.nanstd(error_matrix, axis=1)                   # (n_leaves,)

    # ── highest_leaf_errors: leaf_out, picket_asociado, desviacion ───────────
    top_n = 10
    worst_indices = np.argsort([h["max_error"] for h in hojas])[::-1][:top_n]
    highest_leaf_errors = []
    for idx in worst_indices:
        h = hojas[idx]
        picket_asociado = int(np.argmax(np.abs(h["errors"])))
        highest_leaf_errors.append({
            "leaf_out":        h["leaf"],
            "picket_asociado": picket_asociado,
            "desviacion":      h["max_error"],
            "over_action":     h["over_action"],
            "over_tol":        h["over_tol"],
        })

    # ── Distancia entre pickets ───────────────────────────────────────────────
    if offsets and len(offsets) > 1:
        dists = [abs(offsets[i+1] - offsets[i]) for i in range(len(offsets)-1)]
    else:
        dists = []

    over_action = [h for h in hojas if h["over_action"]]
    over_tol    = [h for h in hojas if h["over_tol"]]

    # ═════════════════════════════════════════════════════════════════════════
    #  Layout: 2×2 arriba + tabla abajo
    # ═════════════════════════════════════════════════════════════════════════
    gs = GridSpec(3, 2, figure=fig,
                  height_ratios=[1, 1, 0.9],
                  hspace=0.55, wspace=0.35,
                  left=0.08, right=0.97, top=0.93, bottom=0.05)

    # ── [0,0] picket_mean_error y picket_max_error por picket ────────────────
    ax1 = fig.add_subplot(gs[0, 0])
    _style_ax(ax1)
    x_pick = np.arange(n_pick)
    ax1.bar(x_pick - 0.2, picket_mean_error, 0.35,
            color=_COL_A, label="picket_mean_error", alpha=0.85, zorder=3)
    ax1.bar(x_pick + 0.2, picket_max_error,  0.35,
            color=_COL_B, label="picket_max_error",  alpha=0.85, zorder=3)
    ax1.axhline(tol,    color=_COL_FAIL, linewidth=1.0, linestyle="--", zorder=4)
    ax1.axhline(action, color=_COL_WARN, linewidth=0.8, linestyle=":",  zorder=4)
    ax1.set_xticks(x_pick)
    ax1.set_xticklabels([f"P{i}" for i in range(n_pick)], fontsize=7)
    ax1.set_xlabel("Picket", fontsize=8, color=_COL_TEXT)
    ax1.set_ylabel("Error (mm)", fontsize=8, color=_COL_TEXT)
    ax1.set_title("Error medio y máx por picket", fontsize=9,
                  fontweight="bold", color=_COL_TEXT)
    ax1.legend(fontsize=6.5, framealpha=0.3, labelcolor=_COL_TEXT, facecolor=_COL_BG)

    # ── [0,1] leaf_error (std inter-picket) por lámina ───────────────────────
    ax2 = fig.add_subplot(gs[0, 1])
    _style_ax(ax2)
    std_threshold = tol * 0.3
    std_colors = [_COL_FAIL if s > std_threshold else
                  (_COL_WARN if s > std_threshold * 0.7 else _COL_OK)
                  for s in leaf_error]
    ax2.barh(np.arange(n_leaves), leaf_error,
             color=std_colors, height=0.7, edgecolor="none", alpha=0.85, zorder=3)
    ax2.axvline(std_threshold, color=_COL_FAIL, linewidth=1.0,
                linestyle="--", zorder=4, label=f"Umbral {std_threshold:.3f} mm")
    step = max(1, n_leaves // 20)
    ax2.set_yticks(np.arange(0, n_leaves, step))
    ax2.set_yticklabels([str(leaf_nums[i]) for i in range(0, n_leaves, step)], fontsize=6)
    ax2.set_xlabel("leaf_error — desv. estándar inter-picket (mm)", fontsize=8, color=_COL_TEXT)
    ax2.set_ylabel("Lámina", fontsize=8, color=_COL_TEXT)
    ax2.set_title("Desv. estándar por lámina (leaf_error)", fontsize=9,
                  fontweight="bold", color=_COL_TEXT)
    ax2.legend(fontsize=6.5, framealpha=0.3, labelcolor=_COL_TEXT, facecolor=_COL_BG)

    # ── [1,0] Distancia entre pickets ────────────────────────────────────────
    ax3 = fig.add_subplot(gs[1, 0])
    _style_ax(ax3)
    if dists:
        x_d = np.arange(len(dists))
        mean_dist = np.mean(dists)
        bar_colors_d = [_COL_FAIL if abs(d - mean_dist) > mean_dist * 0.05
                        else _COL_OK for d in dists]
        ax3.bar(x_d, dists, color=bar_colors_d, alpha=0.85, zorder=3)
        ax3.axhline(mean_dist, color=_COL_A, linewidth=1.0, linestyle="--",
                    label=f"Media: {mean_dist:.2f} mm", zorder=4)
        ax3.set_xticks(x_d)
        ax3.set_xticklabels([f"P{i}→P{i+1}" for i in range(len(dists))], fontsize=6.5)
        ax3.legend(fontsize=6.5, framealpha=0.3, labelcolor=_COL_TEXT, facecolor=_COL_BG)
    else:
        ax3.text(0.5, 0.5, "Un solo picket", transform=ax3.transAxes,
                 ha="center", va="center", color=_COL_SUBTEXT)
    ax3.set_ylabel("Distancia (mm)", fontsize=8, color=_COL_TEXT)
    ax3.set_title("Distancia entre pickets consecutivos", fontsize=9,
                  fontweight="bold", color=_COL_TEXT)

    # ── [1,1] Resumen — campos de configuracion_picketfence ──────────────────
    ax4 = fig.add_subplot(gs[1, 1])
    ax4.set_axis_off()
    ax4.set_facecolor(_COL_BG)

    n_over_action = len(over_action)
    n_over_tol    = len(over_tol)
    summary_lines = [
        ("Láminas sobre action_tolerance:",          f"{n_over_action}",  _COL_FAIL if n_over_action else _COL_OK),
        ("Láminas sobre tolerancia:",                f"{n_over_tol}",     _COL_FAIL if n_over_tol    else _COL_OK),
        ("",                                          "",                  _COL_TEXT),
        ("Error global máximo (mm):",                f"{processed['max_error_mm']:.4f}",  _COL_TEXT),
        (f"  Lámina {processed['max_error_leaf']} — Picket {processed['max_error_picket']}", "", _COL_SUBTEXT),
        ("",                                          "",                  _COL_TEXT),
        ("% láminas aprobadas:",                     f"{processed['percent_passing']:.1f}%", _COL_TEXT),
        ("Espaciado medio (spacing_mm):",            f"{processed['spacing_mm']:.2f} mm",   _COL_TEXT),
        ("Skew MLC:",                                f"{processed['skew']:.6f}°",            _COL_TEXT),
        ("Tolerancia:",                              f"{tol} mm",         _COL_TEXT),
        ("Action tolerance:",                        f"{action} mm",      _COL_TEXT),
    ]
    for i, (label, value, color) in enumerate(summary_lines):
        ax4.text(0.04, 0.97 - i * 0.088, f"{label}  {value}",
                 transform=ax4.transAxes, ha="left", va="top",
                 fontsize=7.5, color=color,
                 fontweight="bold" if i < 2 else "normal")
    ax4.set_title("Resumen — configuracion_picketfence", fontsize=9,
                  fontweight="bold", color=_COL_TEXT)

    # ── [2,:] Tabla highest_leaf_errors ──────────────────────────────────────
    ax5 = fig.add_subplot(gs[2, :])
    ax5.set_axis_off()
    ax5.set_facecolor(_COL_BG)
    ax5.set_title(f"highest_leaf_errors — top {top_n} láminas por desviación",
                  fontsize=9, fontweight="bold", color=_COL_TEXT, pad=4)

    col_labels = ["leaf_out", "picket_asociado", "desviacion (mm)", "Sobre tol.", "Sobre action"]
    table_data = [
        [str(w["leaf_out"]),
         str(w["picket_asociado"]),
         f"{w['desviacion']:.4f}",
         "SÍ" if w["over_tol"]    else "NO",
         "SÍ" if w["over_action"] else "NO"]
        for w in highest_leaf_errors
    ]
    cell_colors = []
    for w in highest_leaf_errors:
        row_c = [_COL_BG, _COL_BG, _COL_BG]
        row_c.append(_COL_FAIL if w["over_tol"]    else _COL_OK)
        row_c.append(_COL_FAIL if w["over_action"] else _COL_OK)
        cell_colors.append(row_c)

    if table_data:
        tbl = ax5.table(
            cellText=table_data,
            colLabels=col_labels,
            cellColours=cell_colors,
            loc="center",
            cellLoc="center",
        )
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(7.5)
        tbl.scale(1, 1.4)
        for (row, col), cell in tbl.get_celld().items():
            cell.set_edgecolor(_COL_LINE)
            if row == 0:
                cell.set_facecolor(_COL_TEXT)
                cell.set_text_props(color="white", fontweight="bold")

    fig.suptitle("Análisis estadístico — Picket Fence",
                 fontsize=12, fontweight="bold", color=_COL_TEXT, y=0.99)
    canvas.draw()


# DATOS FINALES:


# MODELO DE BASE DE DATOS 

from data.ManejoDatos.conection import Conexion

# tabla 1: ref_control / equipo / usuario / usuario 2 / Tolerancia / Action tolerance / 

def pf_db_insertion(ref, fecha, equipo ,action_tolerance, tolerance, fisico_1, fisico_2, imagen):
    print("pf_db_insertion called")
    try:   
        conn = Conexion().conectar()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM configuracion_picketfence WHERE ref=?", (ref,))
        cursor.execute(""" UPDATE configuracion_picketfence SET fecha=?, equipo=?, fisico_1=?, fisico_2=?, tolerancia=?, action_tolerance=?, imagen_mlc=? WHERE ref=?""", ( fecha, equipo, fisico_1, fisico_2, tolerance, action_tolerance, imagen, ref))
        if cursor.rowcount == 0:  
            cursor.execute(""" 
                    INSERT OR REPLACE INTO configuracion_picketfence 
                    (ref, fecha ,equipo, fisico_1, fisico_2, tolerancia, action_tolerance, imagen_mlc) VALUES (?,?,?,?,?,?,?,?)
                           """, (ref, fecha, equipo, fisico_1, fisico_2, tolerance, action_tolerance, imagen))
        
        conn.commit()
        
        
    except Exception as e:
        print(f"Error en pf_db creando tabla: {e}")

def pf_picket_error_insertion(ref,processed):
    try:
        conn = Conexion().conectar()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM error_picket WHERE ref=?", (ref,))

        for ps in processed["picket_stats"]:
            cursor.execute("""
                UPDATE error_picket
                SET picket_mean_error=?, picket_max_error=?
                WHERE ref=? AND picket=?
            """, (ps["picket_mean_error"], ps["picket_max_error"], ref, ps["picket"]))

            if cursor.rowcount == 0:
                cursor.execute("""
                    INSERT INTO error_picket (ref, picket, picket_mean_error, picket_max_error)
                    VALUES (?,?,?,?)
                """, (ref, ps["picket"], ps["picket_mean_error"], ps["picket_max_error"]))

        conn.commit()
    except Exception as e:
        print(f"Error en pf_picket_error_insertion: {e}")


def pf_leaf_error_insertion(ref, processed):
    try:
        conn = Conexion().conectar()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM leaf_error WHERE ref=?", (ref,))
        
        for hoja in processed["leafs"]:
            cursor.execute("""
                UPDATE leaf_error SET error=?
                WHERE ref=? AND leaf=?
            """, (hoja["leaf_error"], ref, hoja["leaf"]))

            if cursor.rowcount == 0:
                cursor.execute("""
                    INSERT INTO leaf_error (ref, leaf, error)
                    VALUES (?,?,?)
                """, (ref, hoja["leaf"], hoja["leaf_error"]))

        conn.commit()
    except Exception as e:
        print(f"Error en pf_leaf_error_insertion: {e}")

def pf_highest_leaf_errors_insertion(ref, processed, top_n=10):
    peores = sorted(processed["leafs"], key=lambda h: h["max_error"], reverse=True)[:top_n]

    
    try:
        conn = Conexion().conectar()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM highest_leaf_errors WHERE ref=?", (ref,))

        for hoja in peores:
            picket_asociado = int(hoja["errors"].index(max(hoja["errors"], key=abs)))

            cursor.execute("""
                UPDATE highest_leaf_errors
                SET leaf_out=?, picket_asociado=?, desviacion=?
                WHERE ref=? AND leaf_out=?
            """, (hoja["leaf"], picket_asociado, hoja["max_error"], ref, hoja["leaf"]))

            if cursor.rowcount == 0:
                cursor.execute("""
                    INSERT INTO highest_leaf_errors (ref, leaf_out, picket_asociado, desviacion)
                    VALUES (?,?,?,?)
                """, (ref, hoja["leaf"], picket_asociado, hoja["max_error"]))

        conn.commit()
    except Exception as e:
        print(f"Error en pf_highest_leaf_errors_insertion: {e}")
    
    
    
    
# tabla 2: ref_control / Num pickets / Picket{} / Error por Picket  / Desviación estandar
# tabla 3: ref_control / Lamina {} / Varianza por lamina / 
# tabla 4: ref_control / Lamina fuera de tolerancia / Picket / Desviación

# ═════════════════════════════════════════════════════════════════
#  Clase de servicio
# ═════════════════════════════════════════════════════════════════
class STARSHOT_MEASUREMENT:
    """
    Envuelve pylinac.Starshot y expone un método analyze() que
    devuelve el objeto Starshot ya analizado (igual que picket_fence
    devuelve el objeto PicketFence).
    """
 
    def __init__(self):
        self.ss = None
 
    def analyze(self, dicom_file: str, tolerance: float = 1.0, sid: float = 1000,
                recursive: bool = True) -> "Starshot":
        """
        Parámetros
        ----------
        dicom_file : ruta al .dcm del spoke shot
        tolerance  : radio máximo del círculo de convergencia (mm)
        recursive  : búsqueda recursiva de centro (más precisa)
 
        Retorna el objeto Starshot analizado.
        """
        kwargs = {}
        if sid is not None:
            kwargs["sid"] = sid

        self.ss = Starshot(dicom_file, **kwargs)
        
        self.ss.analyze(tolerance=tolerance, recursive=recursive)
        return self.ss
 
 

 
 
# ══════════════════════════════════════════════════════════════════
#  Estadisticas:
# ══════════════════════════════════════════════════════════════════

from itertools import combinations

def calcular_intersecciones_filtradas(lines, angles_deg, umbral_paralelo=15.0):
    """
    Calcula intersecciones entre pares de líneas, filtrando pares
    casi paralelos (|Δangle| < umbral_paralelo o > 180-umbral).
    
    Con 6 spokes en 180°, los spokes opuestos tienen Δangle ≈ 0° → filtrar.
    """
    def interseccion(l1, l2):
        x1, y1 = l1.point1.x, l1.point1.y
        x2, y2 = l1.point2.x, l1.point2.y
        x3, y3 = l2.point1.x, l2.point1.y
        x4, y4 = l2.point2.x, l2.point2.y
        denom = (x1-x2)*(y3-y4) - (y1-y2)*(x3-x4)
        if abs(denom) < 1e-10:
            return None
        t = ((x1-x3)*(y3-y4) - (y1-y3)*(x3-x4)) / denom
        return np.array([x1 + t*(x2-x1), y1 + t*(y2-y1)])

    resultados = []
    n = len(lines)
    for i, j in combinations(range(n), 2):
        # Diferencia angular entre spokes (módulo 180° porque son líneas)
        da = abs(angles_deg[i] - angles_deg[j]) % 180
        da = min(da, 180 - da)  # siempre en [0°, 90°]
        if da < umbral_paralelo:
            continue  # spokes casi opuestos → intersección espuria lejana
        pt = interseccion(lines[i], lines[j])
        if pt is not None:
            resultados.append((i, j, pt, da))
    return resultados



def _dibujar_residuos_starshot(fig, canvas, estadisticas: dict):
    """
    Tab 'Residuos': scatter de intersecciones + histograma.
    Requiere que estadisticas tenga '_puntos_mm' y '_distancias_mm'
    (campos internos añadidos por analisis_profundo_starshot).
    """
    fig.clear()
    fig.patch.set_facecolor(_COL_BG)

    puntos_mm     = estadisticas.get("_puntos_mm")
    distancias_mm = estadisticas.get("_distancias_mm")
    cx_mm         = estadisticas.get("_cx_mm", 0.0)
    cy_mm         = estadisticas.get("_cy_mm", 0.0)

    if puntos_mm is None or len(puntos_mm) == 0:
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, "Sin intersecciones válidas",
                transform=ax.transAxes, ha="center", va="center",
                color=_COL_TEXT)
        canvas.draw()
        return

    ax1 = fig.add_subplot(121, aspect="equal")
    ax2 = fig.add_subplot(122)
    for ax in (ax1, ax2):
        ax.set_facecolor(_COL_BG)
        ax.tick_params(colors=_COL_TEXT)
        for spine in ax.spines.values():
            spine.set_edgecolor(_COL_SUBTEXT)

    res = estadisticas["residuos_interseccion"]
    tol_plot = res["max_mm"] * 1.4

    # ── Scatter de intersecciones ────────────────────────────────
    sc = ax1.scatter(
        puntos_mm[:, 0], puntos_mm[:, 1],
        c=distancias_mm, cmap="RdYlGn_r",
        vmin=0, vmax=res["max_mm"],
        s=60, zorder=4, edgecolors="none"
    )
    # Centro pylinac
    ax1.plot(cx_mm, cy_mm, "+", color="#c1df08",
             markersize=14, markeredgewidth=2, label="Centro pylinac", zorder=5)
    # Círculo de radio RMS
    theta = np.linspace(0, 2*np.pi, 200)
    ax1.plot(cx_mm + res["rms_mm"]*np.cos(theta),
             cy_mm + res["rms_mm"]*np.sin(theta),
             "--", color="#4fc3f7", linewidth=1.2, label=f"RMS={res['rms_mm']:.4f} mm")
    ax1.plot(cx_mm + res["max_mm"]*np.cos(theta),
             cy_mm + res["max_mm"]*np.sin(theta),
             "--", color="#ef5350", linewidth=1.0, label=f"Máx={res['max_mm']:.4f} mm")

    cb = fig.colorbar(sc, ax=ax1, fraction=0.046, pad=0.04)
    cb.set_label("Distancia al centro (mm)", color=_COL_TEXT, fontsize=8)
    cb.ax.yaxis.set_tick_params(color=_COL_TEXT)
    ax1.set_title("Intersecciones entre spokes", color=_COL_TEXT, fontsize=10)
    ax1.set_xlabel("X (mm)", color=_COL_TEXT, fontsize=8)
    ax1.set_ylabel("Y (mm)", color=_COL_TEXT, fontsize=8)
    ax1.legend(fontsize=7, facecolor=_COL_BG, labelcolor=_COL_TEXT)

    # ── Histograma de residuos ───────────────────────────────────
    ax2.hist(distancias_mm, bins=max(5, len(distancias_mm)//2),
             color="#4fc3f7", edgecolor=_COL_BG, alpha=0.85)
    ax2.axvline(res["mean_mm"], color="#c1df08", linewidth=1.5,
                linestyle="--", label=f"Media={res['mean_mm']:.4f} mm")
    ax2.axvline(res["rms_mm"],  color="#4fc3f7", linewidth=1.5,
                linestyle=":",  label=f"RMS={res['rms_mm']:.4f} mm")
    ax2.axvline(res["p95_mm"],  color="#ef5350", linewidth=1.5,
                linestyle="-.", label=f"P95={res['p95_mm']:.4f} mm")
    ax2.set_title("Distribución de residuos", color=_COL_TEXT, fontsize=10)
    ax2.set_xlabel("Distancia al centro (mm)", color=_COL_TEXT, fontsize=8)
    ax2.set_ylabel("Frecuencia", color=_COL_TEXT, fontsize=8)
    ax2.legend(fontsize=7, facecolor=_COL_BG, labelcolor=_COL_TEXT)

    fig.tight_layout()
    canvas.draw()


def _dibujar_uniformidad_angular(fig, canvas, estadisticas: dict):
    """
    Tab 'Uniformidad': barplot de separaciones angulares vs ideal.
    """
    fig.clear()
    fig.patch.set_facecolor(_COL_BG)
    ax = fig.add_subplot(111)
    ax.set_facecolor(_COL_BG)
    ax.tick_params(colors=_COL_TEXT)
    for spine in ax.spines.values():
        spine.set_edgecolor(_COL_SUBTEXT)

    uni   = estadisticas["uniformidad_angular"]
    seps  = uni["separaciones_deg"]
    errs  = uni["errores_sep_deg"]
    ideal = uni["ideal_sep_deg"]
    n     = len(seps)
    x     = np.arange(n)

    colors = ["#ef5350" if abs(e) > 1.5 else "#4fc3f7" for e in errs]
    bars = ax.bar(x, seps, color=colors, alpha=0.85, edgecolor=_COL_BG, width=0.6)
    ax.axhline(ideal, color="#c1df08", linewidth=1.5,
               linestyle="--", label=f"Ideal = {ideal:.1f}°")

    # Anotaciones de error encima de cada barra
    for i, (bar, err) in enumerate(zip(bars, errs)):
        ax.text(bar.get_x() + bar.get_width()/2,
                bar.get_height() + 0.05,
                f"{err:+.3f}°",
                ha="center", va="bottom",
                color=_COL_TEXT, fontsize=8)

    ax.set_xticks(x)
    ax.set_xticklabels([f"Gap {i+1}" for i in range(n)], color=_COL_TEXT)
    ax.set_ylabel("Separación angular (°)", color=_COL_TEXT)
    ax.set_title(
        f"Uniformidad angular entre spokes  |  "
        f"Max error: {uni['max_error_sep_deg']:.3f}°  |  "
        f"σ: {uni['std_sep_deg']:.4f}°",
        color=_COL_TEXT, fontsize=10
    )
    ax.legend(fontsize=8, facecolor=_COL_BG, labelcolor=_COL_TEXT)
    ax.set_ylim(0, max(seps) * 1.2)
    fig.tight_layout()
    canvas.draw()


def _dibujar_colinealidad_starshot(fig, canvas, estadisticas: dict):
    """
    Tab 'Colinealidad': distancia entre spokes opuestos (deben ser 0 idealmente).
    """
    fig.clear()
    fig.patch.set_facecolor(_COL_BG)
    ax = fig.add_subplot(111)
    ax.set_facecolor(_COL_BG)
    ax.tick_params(colors=_COL_TEXT)
    for spine in ax.spines.values():
        spine.set_edgecolor(_COL_SUBTEXT)

    pares = estadisticas.get("colinealidad_opuestos", [])

    if not pares:
        ax.text(0.5, 0.5, "No se detectaron pares opuestos",
                transform=ax.transAxes, ha="center", va="center",
                color=_COL_TEXT)
        canvas.draw()
        return

    etiquetas = [f"{p['angulo_i']:.1f}° ↔ {p['angulo_j']:.1f}°" for p in pares]
    valores   = [p["dist_mm"] for p in pares]
    colors    = ["#ef5350" if v > 0.2 else "#4fc3f7" for v in valores]

    x = np.arange(len(pares))
    bars = ax.bar(x, valores, color=colors, alpha=0.85,
                  edgecolor=_COL_BG, width=0.5)

    for bar, val in zip(bars, valores):
        ax.text(bar.get_x() + bar.get_width()/2,
                bar.get_height() + 0.002,
                f"{val:.4f} mm",
                ha="center", va="bottom",
                color=_COL_TEXT, fontsize=9)

    ax.axhline(0, color=_COL_SUBTEXT, linewidth=0.8, linestyle="--")
    ax.set_xticks(x)
    ax.set_xticklabels(etiquetas, color=_COL_TEXT, fontsize=9)
    ax.set_ylabel("Distancia entre líneas opuestas (mm)", color=_COL_TEXT)
    ax.set_title("Colinealidad de spokes opuestos  |  Ideal = 0 mm",
                 color=_COL_TEXT, fontsize=10)
    ax.set_ylim(0, max(valores) * 1.4 if valores else 1)
    fig.tight_layout()
    canvas.draw()


# ══════════════════════════════════════════════════════════════════
#  analisis_profundo_starshot — versión corregida con campos internos
# ══════════════════════════════════════════════════════════════════

    
    
# ══════════════════════════════════════════════════════════════════
#  Procesado de datos (→ dict estandarizado)
# ══════════════════════════════════════════════════════════════════
def _encontrar_isocentro_geometrico(ss_obj) -> tuple:
    """
    Isocentro = intersección del spoke más cercano a 0° con el más
    cercano a 90°.  Fallbacks: centroide de intersecciones → shape/2.
    Devuelve (iso_x_px, iso_y_px) en coordenadas de píxel del array.
    """
    angles = list(ss_obj.angles)
    lines  = ss_obj.lines

    def _interseccion(l1, l2):
        x1, y1 = l1.point1.x, l1.point1.y
        x2, y2 = l1.point2.x, l1.point2.y
        x3, y3 = l2.point1.x, l2.point1.y
        x4, y4 = l2.point2.x, l2.point2.y
        denom = (x1-x2)*(y3-y4) - (y1-y2)*(x3-x4)
        if abs(denom) < 1e-10:
            return None
        t = ((x1-x3)*(y3-y4) - (y1-y3)*(x3-x4)) / denom
        return (x1 + t*(x2-x1), y1 + t*(y2-y1))

    def _mas_cercano_a(angulo_objetivo):
        mejor_idx, mejor_diff = None, 999.0
        for i, a in enumerate(angles):
            for ref in [angulo_objetivo, angulo_objetivo + 180]:
                diff = min(abs((a % 360) - (ref % 360)),
                           360 - abs((a % 360) - (ref % 360)))
                if diff < mejor_diff:
                    mejor_diff, mejor_idx = diff, i
        return mejor_idx

    idx_0  = _mas_cercano_a(0)
    idx_90 = _mas_cercano_a(90)

    if idx_0 is not None and idx_90 is not None and idx_0 != idx_90:
        pt = _interseccion(lines[idx_0], lines[idx_90])
        if pt is not None:
            return pt

    # Fallback 1: centroide de todas las intersecciones no paralelas
    from itertools import combinations
    puntos = []
    for i, j in combinations(range(len(lines)), 2):
        da = min(abs(angles[i] - angles[j]) % 180,
                 180 - abs(angles[i] - angles[j]) % 180)
        if da < 15.0:
            continue
        pt = _interseccion(lines[i], lines[j])
        if pt is not None:
            puntos.append(pt)
    if puntos:
        return (float(np.mean([p[0] for p in puntos])),
                float(np.mean([p[1] for p in puntos])))

    # Fallback 2: centro geométrico del array
    return (ss_obj.image.shape[1] / 2, ss_obj.image.shape[0] / 2)


def analisis_profundo_starshot(ss_obj, rd) -> dict:
    from itertools import combinations

    dpmm   = ss_obj.image.dpmm
    angles = list(rd.angles)
    lines  = ss_obj.lines

    # ✅ Isocentro geométrico en lugar del centro del wobble
    iso_x_px, iso_y_px = _encontrar_isocentro_geometrico(ss_obj)

    def interseccion(l1, l2):
        x1, y1 = l1.point1.x, l1.point1.y
        x2, y2 = l1.point2.x, l1.point2.y
        x3, y3 = l2.point1.x, l2.point1.y
        x4, y4 = l2.point2.x, l2.point2.y
        denom = (x1-x2)*(y3-y4) - (y1-y2)*(x3-x4)
        if abs(denom) < 1e-10:
            return None
        t = ((x1-x3)*(y3-y4) - (y1-y3)*(x3-x4)) / denom
        return np.array([x1+t*(x2-x1), y1+t*(y2-y1)])

    intersecciones = []
    for i, j in combinations(range(len(lines)), 2):
        da = abs(angles[i] - angles[j]) % 180
        da = min(da, 180 - da)
        if da < 15.0:
            continue
        pt = interseccion(lines[i], lines[j])
        if pt is not None:
            intersecciones.append((i, j, pt, da))

    puntos_px = np.array([p for _, _, p, _ in intersecciones])

    # Convertir isocentro y puntos a mm
    img_cx = ss_obj.image.shape[1] / 2
    img_cy = ss_obj.image.shape[0] / 2
    puntos_mm = (puntos_px - np.array([img_cx, img_cy])) / dpmm

    # ✅ cx_mm, cy_mm ahora son el isocentro geométrico, no el wobble
    cx_mm = (iso_x_px - img_cx) / dpmm
    cy_mm = (iso_y_px - img_cy) / dpmm

    # ✅ Distancias al isocentro geométrico, no al wobble
    iso_centro = np.array([iso_x_px, iso_y_px])
    distancias_px = np.linalg.norm(puntos_px - iso_centro, axis=1)
    distancias_mm = distancias_px / dpmm

    residuos = {
        "mean_mm" : float(np.mean(distancias_mm)),
        "std_mm"  : float(np.std(distancias_mm, ddof=1)) if len(distancias_mm) > 1 else 0.0,
        "rms_mm"  : float(np.sqrt(np.mean(distancias_mm**2))),
        "max_mm"  : float(np.max(distancias_mm)),
        "min_mm"  : float(np.min(distancias_mm)),
        "p95_mm"  : float(np.percentile(distancias_mm, 95)),
        "n"       : len(distancias_mm),
    }
    idx_peor = int(np.argmax(distancias_mm))
    i_p, j_p, _, da_p = intersecciones[idx_peor]
    residuos["par_peor"]        = (i_p, j_p)
    residuos["angulo_par_peor"] = float(da_p)

    # Uniformidad angular — sin cambios, no depende del centro
    n_spokes  = len(angles)
    ideal_sep = 180.0 / n_spokes
    angles_s  = sorted(angles)
    seps = []
    for k in range(n_spokes):
        delta = (angles_s[(k+1) % n_spokes] - angles_s[k]) % 180
        seps.append(delta)
    seps = np.array(seps)
    errores_sep = seps - ideal_sep

    uniformidad = {
        "ideal_sep_deg"     : ideal_sep,
        "separaciones_deg"  : seps.tolist(),
        "errores_sep_deg"   : errores_sep.tolist(),
        "max_error_sep_deg" : float(np.max(np.abs(errores_sep))),
        "std_sep_deg"       : float(np.std(seps, ddof=1)) if len(seps) > 1 else 0.0,
    }

    # Colinealidad — sin cambios, es distancia entre líneas opuestas
    colinealidad = []
    usados = set()
    for i in range(n_spokes):
        if i in usados:
            continue
        diffs = [(min(abs(angles[i]-angles[j]) % 180,
                      180 - abs(angles[i]-angles[j]) % 180), j)
                 for j in range(n_spokes) if j != i and j not in usados]
        if not diffs:
            continue
        da_min, j_op = min(diffs)
        if da_min < 15.0:
            l1, l2 = lines[i], lines[j_op]
            dx = l1.point2.x - l1.point1.x
            dy = l1.point2.y - l1.point1.y
            norm = np.sqrt(dx**2 + dy**2)
            if norm > 1e-10:
                dist_px = abs(dy*(l2.point1.x - l1.point1.x) -
                              dx*(l2.point1.y - l1.point1.y)) / norm
                colinealidad.append({
                    "spoke_i"  : i,
                    "spoke_j"  : j_op,
                    "angulo_i" : float(angles[i]),
                    "angulo_j" : float(angles[j_op]),
                    "dist_mm"  : float(dist_px / dpmm),
                })
            usados.update([i, j_op])

    return {
        "residuos_interseccion"  : residuos,
        "uniformidad_angular"    : uniformidad,
        "colinealidad_opuestos"  : colinealidad,
        "offset_centroide_mm"    : float(np.linalg.norm(
                                       puntos_mm.mean(axis=0) - np.array([cx_mm, cy_mm]))),
        "n_intersecciones_usadas": len(intersecciones),
        "_puntos_mm"             : puntos_mm,
        "_distancias_mm"         : distancias_mm,
        "_cx_mm"                 : cx_mm,   # ✅ ahora es el isocentro geométrico
        "_cy_mm"                 : cy_mm,
    }


def procesar_data_starshot(ss_obj, tolerance: float) -> dict:
    rd = ss_obj.results_data()

    # ✅ Isocentro geométrico como referencia de desviaciones
    iso_x_px, iso_y_px = _encontrar_isocentro_geometrico(ss_obj)

    radius_mm = float(rd.circle_radius_mm)
    passed    = bool(rd.passed)
    dpmm      = ss_obj.image.dpmm
    img_cx    = ss_obj.image.shape[1] / 2
    img_cy    = ss_obj.image.shape[0] / 2

    # Centro del wobble en mm respecto al isocentro geométrico
    # (útil para reportar el desplazamiento mecánico)
    wobble_cx_px, wobble_cy_px = rd.circle_center_x_y
    cx_mm = (wobble_cx_px - iso_x_px) / dpmm  # desplazamiento del wobble al isocentro
    cy_mm = (wobble_cy_px - iso_y_px) / dpmm

    spokes = []
    for line, angle in zip(ss_obj.lines, rd.angles):
        angle_real = float(np.degrees(np.arctan2(
            line.point2.y - line.point1.y,
            line.point2.x - line.point1.x
        ))) + 90
        nominal      = round(angle_real / 30.0) * 30.0
        dev          = (angle_real - nominal + 180) % 360 - 180
        passed_spoke = abs(dev) <= tolerance
        spokes.append({
            "angle_deg"      : nominal,
            "angle_real_deg" : angle_real,
            "deviation_deg"  : dev,
            "passed"         : passed_spoke,
        })

    try:
        img_array = ss_obj.image.array
    except Exception:
        img_array = None

    return {
        "passed"       : passed,
        "tolerance_mm" : tolerance,
        "radius_mm"    : radius_mm,
        "center_x_mm"  : cx_mm,   # ✅ desplazamiento wobble→isocentro
        "center_y_mm"  : cy_mm,
        "spokes"       : spokes,
        "n_spokes"     : len(spokes),
        "image_array"  : img_array,
    }
 
 


# ══════════════════════════════════════════════════════════════════
#  Vista 1 : RUEDA DE RAYOS (spoke wheel)
# ══════════════════════════════════════════════════════════════════
def dibujar_spoke_wheel(fig, canvas, processed: dict):
    """
    Representa los rayos como líneas radiales centradas en el
    isocentro (0,0).  El círculo de convergencia se muestra
    escalado.  Color por estado de cada rayo.
    """
    fig.clear()
    fig.patch.set_facecolor(_COL_BG)
    ax = fig.add_subplot(111, aspect="equal")
    ax.set_facecolor(_COL_BG)
 
    spokes     = processed["spokes"]
    tol        = processed["tolerance_mm"]
    radius     = processed["radius_mm"]
    cx, cy     = processed["center_x_mm"], processed["center_y_mm"]
 
    if not spokes:
        ax.text(0.5, 0.5, "Sin rayos detectados",
                transform=ax.transAxes, ha="center", va="center",
                color=_COL_TEXT, fontsize=11)
        canvas.draw()
        return
 
    # Longitud visual de los rayos (en mm representados)
    ray_len = max(tol * 20, 30)
 
    # ── Dibujar cada rayo ────────────────────────────────────────
    for spoke in spokes:
        angle_rad = np.deg2rad(spoke["angle_real_deg"])
        dev       = spoke["deviation_deg"]
        color     = _spoke_color(dev, tol * 0.03)   # tol en deg aprox
 
        dx = np.cos(angle_rad) * ray_len
        dy = np.sin(angle_rad) * ray_len
        ax.plot([0, dx], [0, dy],
                color=color, linewidth=2.0, alpha=0.85, zorder=3)
        ax.plot([0, -dx], [0, -dy],
                color=color, linewidth=2.0, alpha=0.85, zorder=3)
 
        # Etiqueta angular en la punta del rayo
        lx = np.cos(angle_rad) * (ray_len + tol * 2)
        ly = np.sin(angle_rad) * (ray_len + tol * 2)
        ax.text(lx, ly, f"{spoke['angle_deg']:.0f}°",
                ha="center", va="center",
                fontsize=7, color=_COL_SUBTEXT)
 
    # ── Círculo de convergencia (tamaño real en mm) ──────────────
    circle = Circle((0, 0), radius,
                     edgecolor=_COL_CIRCLE, facecolor=_COL_CIRCLE + "33",
                     linewidth=2.0, zorder=5, label=f"Convergencia ({radius:.3f} mm)")
    ax.add_patch(circle)
 
    # ── Tolerancia (círculo de referencia) ───────────────────────
    circle_tol = Circle((0, 0), tol,
                         edgecolor=_COL_FAIL, facecolor="none",
                         linewidth=1.4, linestyle="--", zorder=4,
                         label=f"Tolerancia ({tol:.1f} mm)")
    ax.add_patch(circle_tol)
 
    # ── Cruz en el isocentro ─────────────────────────────────────
    ax.plot(0, 0, "+", color=_COL_TEXT,
            markersize=14, markeredgewidth=2, zorder=6, label="Isocentro (0,0)")
 
    # ── Centro del círculo de convergencia ───────────────────────
    ax.plot(0, 0, "o", color=_COL_CIRCLE,
            markersize=7, zorder=7, label=f"Centro ({cx:+.3f}, {cy:+.3f}) mm")
 
    # ── Leyenda ──────────────────────────────────────────────────
    legend_patches = [
        mpatches.Patch(color=_COL_OK,     label="Dentro de tol."),
        mpatches.Patch(color=_COL_WARN,   label="Cerca del límite"),
        mpatches.Patch(color=_COL_FAIL,   label="Fuera de tol."),
        mpatches.Patch(color=_COL_CIRCLE, label=f"Radio: {radius:.3f} mm"),
    ]
    fig.legend(handles=legend_patches, loc="lower center", ncol=4,
               fontsize=7, framealpha=0.3, labelcolor=_COL_TEXT,
               facecolor=_COL_BG, bbox_to_anchor=(0.5, 0.0))
 
    # ── Estilo ───────────────────────────────────────────────────
    margin = ray_len * 1.25
    ax.set_xlim(-margin, margin)
    ax.set_ylim(-margin, margin)
    ax.set_xlabel("X (mm)", fontsize=9, color=_COL_TEXT)
    ax.set_ylabel("Y (mm)", fontsize=9, color=_COL_TEXT)
    ax.set_title("Spoke Shot — Convergencia de rayos",
                 fontsize=11, fontweight="bold", color=_COL_TEXT, pad=36)
    ax.tick_params(colors=_COL_TEXT, labelsize=7)
    for spine in ax.spines.values():
        spine.set_edgecolor(_COL_LINE)
    ax.grid(color=_COL_GRID, linewidth=0.5, zorder=0)
    ax.text(0.5, 1.02,
            "↓  Click sobre un rayo para ver su detalle",
            transform=ax.transAxes, ha="center", va="bottom",
            fontsize=7.5, color=_COL_SUBTEXT, style="italic")
 
    fig.tight_layout(rect=[0, 0.06, 1, 0.95])
    canvas.draw()
 
 
# ══════════════════════════════════════════════════════════════════
#  Vista 2 : DETALLE DE UN RAYO
# ══════════════════════════════════════════════════════════════════
def dibujar_spoke_detalle(fig, canvas, processed: dict, spoke_idx: int):
    """
    Panel de detalle para el rayo seleccionado:
    - Visualización angular ampliada (sector del círculo)
    - Barra de error vs tolerancia
    - Texto de métricas
    """
    fig.clear()
    fig.patch.set_facecolor(_COL_BG)
 
    spokes = processed["spokes"]
    tol    = processed["tolerance_mm"]
 
    if spoke_idx >= len(spokes):
        canvas.draw()
        return
 
    spoke  = spokes[spoke_idx]
    angle  = spoke["angle_deg"]
    dev    = spoke["deviation_deg"]
    color  = _spoke_color(dev, 1.5)
 
    # ── Layout 1×2 ───────────────────────────────────────────────
    ax_polar = fig.add_subplot(121, polar=True)
    ax_bar   = fig.add_subplot(122)
 
    fig.patch.set_facecolor(_COL_BG)
    ax_polar.set_facecolor(_COL_BG)
    ax_bar.set_facecolor(_COL_BG)
 
    # ── Gráfico polar: posición del rayo ─────────────────────────
    theta = np.deg2rad(angle)
    ax_polar.plot([theta, theta], [0, 1],
                  color=color, linewidth=3.0, label="Rayo real", zorder=4)
    ax_polar.plot([theta + np.pi, theta + np.pi], [0, 1],
                  color=color, linewidth=3.0, zorder=4)
 
    # Ideal (sin desviación)
    theta_ideal = np.deg2rad(angle - dev)
    ax_polar.plot([theta_ideal, theta_ideal], [0, 1],
                  color=_COL_SUBTEXT, linewidth=1.2,
                  linestyle="--", label="Ideal", zorder=3)
    ax_polar.plot([theta_ideal + np.pi, theta_ideal + np.pi], [0, 1],
                  color=_COL_SUBTEXT, linewidth=1.2, linestyle="--", zorder=3)
 
    # Zona de tolerancia angular
    tol_angular = 1.5 # grados
    tol_rad = np.deg2rad(tol_angular)
    theta_range = np.linspace(theta_ideal - tol_rad, theta_ideal + tol_rad, 60)
    ax_polar.fill_between(theta_range, 0.0, 1.0,
                           color=_COL_OK, alpha=0.15)
 
    ax_polar.set_rlim(0, 1)
    ax_polar.set_rticks([])
    ax_polar.set_title(f"Rayo {spoke_idx} — {angle:.1f}°",
                       fontsize=10, fontweight="bold", color=_COL_TEXT, pad=14)
    ax_polar.tick_params(colors=_COL_TEXT, labelsize=7)
    ax_polar.legend(fontsize=7, loc="lower right",
                    framealpha=0.2, labelcolor=_COL_TEXT,
                    facecolor=_COL_BG)
    ax_polar.set_facecolor(_COL_BG)
    ax_polar.spines["polar"].set_edgecolor(_COL_LINE)
 
    # ── Barra de error ───────────────────────────────────────────
    categories = ["Desviación"]
    values     = [abs(dev)]
    bar_colors = [color]
 
    bars = ax_bar.barh(categories, values, color=bar_colors,
                       height=0.4, edgecolor="none", zorder=3)
    ax_bar.axvline(1.5, color=_COL_FAIL, linewidth=1.5,
                   linestyle="--", label=f"Tol angular (≈{tol_angular:.2f}°)", zorder=4)
 
    for bar, val in zip(bars, values):
        ax_bar.text(bar.get_width() + 0.002, bar.get_y() + bar.get_height() / 2,
                    f"{val:.4f}°",
                    va="center", ha="left", fontsize=9, color=color)
 
    ax_bar.set_xlim(0, max(abs(dev) * 1.5, 1.5) + 0.01)
    ax_bar.set_xlabel("Desviación angular (°)", fontsize=9, color=_COL_TEXT)
    ax_bar.set_title("Error angular del rayo",
                     fontsize=10, fontweight="bold", color=_COL_TEXT)
    ax_bar.tick_params(colors=_COL_TEXT, labelsize=8)
    for spine in ax_bar.spines.values():
        spine.set_edgecolor(_COL_LINE)
    ax_bar.grid(axis="x", color=_COL_GRID, linewidth=0.5, zorder=0)
    ax_bar.legend(fontsize=7, framealpha=0.2, labelcolor=_COL_TEXT,
                  facecolor=_COL_BG)
 
    # ── Métricas en texto ─────────────────────────────────────────
    estado_str = "✓ Aprobado" if spoke["passed"] else "✗ Fuera de tolerancia"
    ax_bar.text(0.02, 0.08,
                f"{estado_str}\nÁngulo: {angle:.2f}°   Desviación: {dev:+.4f}°",
                transform=ax_bar.transAxes, ha="left", va="bottom",
                fontsize=7.5, color=color)
 
    ax_bar.text(0.5, 1.05,
                "↑  Click en fondo para volver a la vista de rayos",
                transform=ax_bar.transAxes, ha="center", va="bottom",
                fontsize=7.5, color=_COL_SUBTEXT, style="italic")
 
    fig.tight_layout()
    canvas.draw()
 
 
# ══════════════════════════════════════════════════════════════════
#  Vista 3 : IMAGEN DICOM CON OVERLAY
# ══════════════════════════════════════════════════════════════════
def dibujar_starshot_imagen(fig, canvas, ss_obj, processed: dict):
    fig.clear()
    ax = fig.add_subplot(111)
    ax.set_facecolor(_COL_BG)

    img_array = processed.get("image_array")
    if img_array is None:
        ax.text(0.5, 0.5, "Imagen no disponible",
                transform=ax.transAxes, ha="center", va="center",
                color=_COL_TEXT)
        canvas.draw()
        return

    ax.imshow(img_array, cmap="gray", origin="upper",
              aspect="equal", interpolation="lanczos")

    tol  = processed["tolerance_mm"]
    dpmm = ss_obj.image.dpmm

    # ── Isocentro real = centro geométrico de la imagen ──────────
    # Intersección de los ejes 0° y 90°: esta es la referencia
    # global correcta para el cálculo de desviaciones.
    # NO es ss_obj.wobble.center (ese es el centro del círculo de
    # convergencia, que puede estar desplazado del isocentro).
    iso_x, iso_y = _encontrar_isocentro_geometrico(ss_obj)

    # ── Rayos detectados ─────────────────────────────────────────
    for spoke in ss_obj.lines:
        try:
            x_start = spoke.point1.x
            y_start = spoke.point1.y
            x_end   = spoke.point2.x
            y_end   = spoke.point2.y
            dev     = float(getattr(spoke, "deviation", 0))
            color   = _spoke_color(dev, 1.5)
            ax.plot([x_start, x_end], [y_start, y_end],
                    color=color, linewidth=1.5, alpha=0.85)
        except Exception:
            pass

    # ── Círculo de convergencia (wobble) ─────────────────────────
    # Se dibuja en su posición real — puede NO coincidir con el
    # isocentro si hay desalineación mecánica. Eso es información.
    try:
        cx_px, cy_px =  _encontrar_isocentro_geometrico(ss_obj)
       
        r_px  = ss_obj.wobble.radius

        circle = Circle((cx_px, cy_px), r_px,
                        edgecolor=_COL_CIRCLE, facecolor="none",
                        linewidth=2.0, zorder=5,
                        label="Círculo de convergencia")
        ax.add_patch(circle)
        # Marcador pequeño diferenciado para el centro del wobble
        ax.plot(cx_px, cy_px, "o", color=_COL_CIRCLE,
                markersize=6, zorder=6, label="Centro wobble")
    except Exception as e:
        print(e)

    # ── Isocentro real (centro geométrico de la imagen) ──────────
    # Cruz amarilla + líneas de referencia de ejes 0° y 90°
    ax.plot(iso_x, iso_y, "+", color="#c1df08",
            markersize=16, markeredgewidth=2.5,
            zorder=7, label="Isocentro (0°∩90°)")

    ax.axhline(iso_y, color="#c1df08", linewidth=0.6,
               alpha=0.4, linestyle="--", zorder=4)
    ax.axvline(iso_x, color="#c1df08", linewidth=0.6,
               alpha=0.4, linestyle="--", zorder=4)

    # ── Leyenda ──────────────────────────────────────────────────
    legend_patches = [
        mpatches.Patch(color=_COL_OK,     label="Dentro de tol."),
        mpatches.Patch(color=_COL_WARN,   label="Cerca del límite"),
        mpatches.Patch(color=_COL_FAIL,   label="Fuera de tol."),
        mpatches.Patch(color=_COL_CIRCLE, label="Círculo de convergencia"),
    ]
    ax.legend(handles=legend_patches, loc="lower left",
              fontsize=7, framealpha=0.5, facecolor="#1a1a1a",
              labelcolor="white")

    ax.set_axis_off()
    ax.set_title("Imagen DICOM — Spoke Shot",
                 fontsize=11, fontweight="bold")
    fig.tight_layout()
    canvas.draw()

 
# ══════════════════════════════════════════════════════════════════
#  Conexión de interactividad
# ══════════════════════════════════════════════════════════════════
def conectar_interactividad_starshot(fig, canvas, ss_obj, processed: dict) -> dict:
    """
    Registra eventos de click para navegación:
      - Click en zona de un rayo  → detalle del rayo
      - Click en fondo            → volver a la rueda
 
    Devuelve dict de estado de navegación.
    """
    estado = {
        "vista"     : "wheel",   # "wheel" | "spoke"
        "spoke_idx" : None,
        "cid_press" : None,
    }
 
    # Dibujo inicial
    dibujar_spoke_wheel(fig, canvas, processed)
 
    def _on_click(event):
        if event.button != 3:  # solo clic derecho
            return

        if event.inaxes is None:
            return
 
        if estado["vista"] == "wheel":
            # Detectar cuál rayo fue clickeado (eje polar → cartesiano)
            x_click = event.xdata
            y_click = event.ydata
            if x_click is None or y_click is None:
                return
 
            angle_click = np.degrees(np.arctan2(y_click, x_click)) % 360
 
            best_idx  = None
            best_diff = 180.0
            for i, spoke in enumerate(processed["spokes"]):
                a = spoke["angle_deg"] % 360
                diff = min(abs(angle_click - a),
                           abs(angle_click - a + 360),
                           abs(angle_click - a - 360))
                # También considerar el rayo opuesto
                a_opp = (a + 180) % 360
                diff_opp = min(abs(angle_click - a_opp),
                               abs(angle_click - a_opp + 360),
                               abs(angle_click - a_opp - 360))
                diff = min(diff, diff_opp)
                if diff < best_diff:
                    best_diff = diff
                    best_idx  = i
 
            # Solo activar si el click fue en la zona de rayos
            ray_len = max(processed["tolerance_mm"] * 20, 30)
            dist    = np.sqrt(x_click**2 + y_click**2)
            if best_idx is not None and best_diff < 15 and dist > 2:
                estado["vista"]     = "spoke"
                estado["spoke_idx"] = best_idx
                dibujar_spoke_detalle(fig, canvas, processed, best_idx)
 
        elif estado["vista"] == "spoke":
            estado["vista"]     = "wheel"
            estado["spoke_idx"] = None
            dibujar_spoke_wheel(fig, canvas, processed)
 
    cid = canvas.mpl_connect("button_press_event", _on_click)
    estado["cid_press"] = cid
 
    return estado




# administración de datos


def starshot_insert(ref, fecha, equipo ,sid, tolerance, fisico_1, fisico_2, imagen):
    print("pf_db_insertion called")
    try:   
        conn = Conexion().conectar()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM configuracion_starshot WHERE ref=?", (ref,))
        
        cursor.execute(""" UPDATE configuracion_starshot SET fecha=?, equipo=?, fisico_1=?, fisico_2=?, tolerancia=?, sid=?, imagen_mlc_spoke=? WHERE ref=?""", ( fecha, equipo, fisico_1, fisico_2, tolerance, sid, imagen, ref))
        if cursor.rowcount == 0:  
            cursor.execute(""" 
                    INSERT OR REPLACE INTO configuracion_starshot 
                    (ref, fecha ,equipo, fisico_1, fisico_2, tolerancia, sid, imagen_mlc_spoke) VALUES (?,?,?,?,?,?,?,?)
                           """, (ref, fecha, equipo, fisico_1, fisico_2, tolerance, sid, imagen))
        
        conn.commit()
        
        
    except Exception as e:
        print(f"Error en pf_db creando tabla: {e}")



def starshot_residual_statistics_insert(ref, estadisticas):
    
    processed = {
                'error_medio_mm': estadisticas['residuos_interseccion']['mean_mm'],
                'std_mm': estadisticas['residuos_interseccion']['std_mm'],
                'rms_mm': estadisticas['residuos_interseccion']['rms_mm'],
                'p95_mm': estadisticas['residuos_interseccion']['p95_mm'],
                'separacion_angular' : estadisticas['uniformidad_angular']['separaciones_deg']
                
            }
    try:
        conn = Conexion().conectar()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM estadisticas_starshot WHERE ref = ?", (ref,))
        
        
        
        cursor.execute("""
            INSERT INTO estadisticas_starshot
            (ref, std_mm, rms_mm, pm_95)
            VALUES (?, ?, ?, ?)
        """, (
            ref,
            processed['std_mm'],
            processed['rms_mm'],
            processed['p95_mm']
        ))
        conn.commit()
    except Exception as e:
        print(f"Error en la funcion starshot_residual_statistics_insert {e}")
    
    
    
    
def starshot_angles_insertion(ref,processed):
    processed = {
            'angulo': [s['angle_deg'] for s in processed['spokes']],
            'angulo_calculado': [s['angle_real_deg'] for s in processed['spokes']],
            'desvacion': [s['deviation_deg'] for s in processed['spokes']]
        }
    try:
        conn = Conexion().conectar()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM angulo_starshot WHERE ref=?", (ref,))

        for i in range(len(processed['angulo'])):
            cursor.execute("""
                INSERT INTO angulo_starshot (
                    ref,
                    spoke_index,
                    angulo_nominal_deg,
                    angulo_real_deg,
                    desviacion_deg
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                ref,
                i,
                processed['angulo'][i],
                processed['angulo_calculado'][i],
                processed['desvacion'][i]
            ))
        conn.commit()
    except Exception as e:
        print(f"Error en pf_picket_error_insertion: {e}")
        
        
def starshot_angular_uniformity_insert(ref, estadisticas):

    processed = {
        'ideal_sep_deg': estadisticas['uniformidad_angular']['ideal_sep_deg'],
        'separaciones_deg': estadisticas['uniformidad_angular']['separaciones_deg'],
        'errores_sep_deg': estadisticas['uniformidad_angular']['errores_sep_deg']
    }

    try:
        conn = Conexion().conectar()
        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM uniformidad_angular_starshot WHERE ref=?",
            (ref,)
        )

        for i, (sep, err) in enumerate(zip(
            processed['separaciones_deg'],
            processed['errores_sep_deg']
        )):

            cursor.execute("""
                INSERT INTO uniformidad_angular_starshot (
                    ref,
                    gap_index,
                    spoke_inicial,
                    spoke_final,
                    separacion_deg,
                    separacion_ideal_deg,
                    error_deg
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                ref,
                i,
                i,
                i + 1,
                sep,
                processed['ideal_sep_deg'],
                err
            ))

        conn.commit()

    except Exception as e:
        print(f"Error en starshot_angular_uniformity_insert: {e}")

    finally:
        conn.close()
