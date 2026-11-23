from resources.utils.matplotlib_lazy import get_matplotlib_components
from scipy.signal import find_peaks, peak_widths
from analisisImagenes.pelicula import clase_resolucion, escala_mm, leer_pelicula
from scipy.ndimage import gaussian_filter1d
from scipy import interpolate
import numpy as np
# La escala del escaneo, la misma de la posición inicial y del mensual; la cabecera solo se clasifica
ESCALA_DEL_PROCEDIMIENTO = {"resolucion_escaneo_dpi": 600.0, "resoluciones_de_editor_dpi": [72.0, 96.0], "tolerancia_dpi_relativa": 0.01}
# La regla de la tira: las líneas van cada 10 mm; la resolución real pone al menos 3 distancias entre líneas, y la mitad o más, a 10 mm ±10 %
REGLA_DE_LA_TIRA = {"paso_mm": 10.0, "tolerancia_relativa": 0.10, "distancias_minimas": 3, "resoluciones_candidatas_dpi": [200.0, 300.0, 600.0]}
# La capa que mide cada filtro: la que dicen la figura y el informe
CAPA_DEL_FILTRO = {"verde": "capa verde con CLAHE", "clahe": "gris con CLAHE", "bilateral": "gris binarizado", None: "capa roja"}
# Helper para obtener componentes matplotlib cuando se necesiten
def _get_mpl():
    """Obtiene componentes matplotlib de forma diferida"""
    mpl = get_matplotlib_components()
    return mpl['plt'], mpl['Figure'], mpl['GridSpec']

def metadata(imagen_path, distancias_px=None):
    """(cm por píxel, aviso): la resolución real es la declarada si la regla de la tira la confirma o, si no, la única candidata que la confirme; sin ninguna, (None, aviso con el motivo).
    Una resolución se confirma si al menos 3 distancias entre líneas, y la mitad o más de ellas, salen a 10 mm ±10 % con ella. Con 600 declarados y menos de 3 distancias, 600 sin comprobar."""
    with open(imagen_path, "rb") as archivo:
        pelicula = leer_pelicula(archivo.read())
    P, R = ESCALA_DEL_PROCEDIMIENTO, REGLA_DE_LA_TIRA
    clase = clase_resolucion(pelicula.dpi, P)
    declarada = {"coincide": P["resolucion_escaneo_dpi"], "otra": pelicula.dpi}.get(clase)
    alto, ancho = pelicula.validos.shape
    partes = [f"{pelicula.formato or 'formato desconocido'}, {pelicula.bits} bits por canal, {ancho} × {alto} px",
              {"editor": f"el archivo declara {pelicula.dpi or 0:.4g} dpi, lo que escribe un editor al guardar un recorte",
               "sin_dato": "el archivo no declara su resolución"}.get(clase, f"resolución declarada {pelicula.dpi or 0:.4g} dpi")]
    if pelicula.fecha_escaneo is not None:
        partes.append(f"escaneada el {pelicula.fecha_escaneo.isoformat()}")
    distancias = np.asarray([] if distancias_px is None else distancias_px, dtype=float)
    n = len(distancias)
    escala = lambda dpi: escala_mm(dpi, {**P, "resolucion_escaneo_dpi": dpi})  # la única conversión de una resolución en escala
    if n < R["distancias_minimas"]:
        if clase == "coincide":  # la cabecera declara los 600 del procedimiento y no hay líneas para contradecirla
            return escala(declarada) / 10, None
        partes.append(f"no hay líneas suficientes para decidir la resolución con la regla de la tira (líneas cada {R['paso_mm']:g} mm): hacen falta {R['distancias_minimas']} distancias entre líneas y hay {n}")
        partes.append("sin una resolución confirmada no hay milímetros ni medidas")
        return None, ". ".join(partes) + "."
    en_regla = lambda dpi: int(np.sum(np.abs(distancias * escala(dpi) - R["paso_mm"]) <= R["tolerancia_relativa"] * R["paso_mm"]))
    confirma = lambda dpi: en_regla(dpi) >= max(R["distancias_minimas"], n / 2)
    regla = lambda dpi: (f"con {dpi:g} dpi, {en_regla(dpi)} de las {n} distancias entre líneas salen a {R['paso_mm']:g} mm ±{R['tolerancia_relativa'] * 100:g} %"
                         f" (la mediana, {float(np.median(distancias)) * escala(dpi):.2f} mm)")
    confirmadas = [c for c in R["resoluciones_candidatas_dpi"] if confirma(c)]
    elegida = declarada if declarada and confirma(declarada) else (confirmadas[0] if len(confirmadas) == 1 else None)
    if elegida is not None and clase == "coincide" and elegida == declarada:
        return escala(elegida) / 10, None
    if elegida is not None:
        partes.append(regla(elegida) + (": la regla de la tira confirma la declarada y se mide con ella" if elegida == declarada else
                                         f": la regla de la tira confirma {elegida:g} dpi, la resolución real, y se mide con ella"))
        return escala(elegida) / 10, ". ".join(partes) + "."
    if declarada:
        partes.append(regla(declarada) + ": la regla de la tira no confirma la declarada")
    partes.append(f"las líneas cuadran con {' y '.join(f'{c:g}' for c in confirmadas)} dpi: la resolución es ambigua" if confirmadas else
                  f"ninguna resolución candidata ({', '.join(f'{c:g}' for c in R['resoluciones_candidatas_dpi'])} dpi) cumple la regla de la tira")
    partes.append("sin una resolución confirmada no hay milímetros ni medidas")
    return None, ". ".join(partes) + "."

def preprocesar_imagen(imagen_bgr, filtro='verde'):
    import cv2
    if filtro == 'verde':  # la capa verde con el mismo CLAHE de siempre
        return cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(cv2.split(imagen_bgr)[1])
    gray = cv2.cvtColor(imagen_bgr, cv2.COLOR_BGR2GRAY)
    
    if filtro == 'clahe':
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        return clahe.apply(gray)
    
    elif filtro == 'bilateral':
        bilateral = cv2.bilateralFilter(imagen_bgr, 7, 60, 60)
        gray_bilateral = cv2.cvtColor(bilateral, cv2.COLOR_BGR2GRAY)
        binary = cv2.adaptiveThreshold(gray_bilateral, 255,
                                       cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                       cv2.THRESH_BINARY, 11, 2)
        return binary
    elif filtro is None:
        img_B, img_G, img_R = cv2.split(imagen_bgr)
        return img_R  # Retorna la imagen original en un solo canal si no se aplica filtro
    else:
        raise ValueError("Filtro no reconocido. Usa 'verde', 'clahe' o 'bilateral'.")

def obtener_perfil(imagen_gray_eq, metodo, fila_especifica):
    import numpy as np
    if metodo:  # Promedio vertical
        return np.mean(imagen_gray_eq, axis=0)
    elif not metodo and fila_especifica is not None:
        if 0 <= fila_especifica < imagen_gray_eq.shape[0]:
            return imagen_gray_eq[fila_especifica, :]
        else:
            raise ValueError("Fila fuera del rango de la imagen.")
    else:
        raise ValueError("Método inválido o falta fila_especifica.")

def detectar_picos(perfil, umbral_relativo=1.0, distancia_minima=30):
    import numpy as np
    perfil_invertido = np.max(perfil) - perfil
    umbral = np.mean(perfil_invertido) + umbral_relativo * np.std(perfil_invertido)
    picos, _ = find_peaks(perfil_invertido, height=umbral, distance=distancia_minima)
    return picos

def analizar_circulos_perfil(perfil_invertido, picos, izq_ips, der_ips, umbral, rel=7, dist=45, sigma=2, ventana=None):
    """
    Detecta los máximos circulares (campos irradiados) tras eliminar los picos duros del perfil.
    
    Parámetros:
        perfil_invertido : np.ndarray
            Perfil 1D invertido de intensidad.
        picos : np.ndarray
            Índices de los picos principales detectados.
        izq_ips, der_ips : np.ndarray
            Límites izquierdo y derecho de los anchos de los picos (float).
        umbral : float
            Umbral original para detección de picos.
        rel : float
            Corrección al umbral para detectar los máximos suaves (default: 7).
        dist : int
            Distancia mínima entre picos secundarios (default: 45).
        sigma : float
            Sigma para el suavizado (default: 4).
        ventana : float
            Distancia máxima entre una línea y su mancha [px]; sin mancha en ella, None.

    Retorna:
        perfil_interpolado : np.ndarray
        picos_circulos : np.ndarray
        diferencias : list[int | None], una por línea: la distancia a la mancha más cercana
    """
    # Copiamos y vaciamos el perfil en los anchos de los picos fuertes
    import numpy as np
    # Si no hay picos o los anchos son None, retornar vacíos
    if izq_ips is None or der_ips is None or len(picos) == 0:
        return perfil_invertido, np.array([]), []

    perfil_filtrado = perfil_invertido.copy().astype(float)
    for izq, der in zip(izq_ips, der_ips):
        i0 = int(np.floor(izq))
        i1 = int(np.ceil(der))
        perfil_filtrado[i0:i1+1] = np.nan

    # Suavizado
    perfil_filtrado = gaussian_filter1d(perfil_filtrado, sigma=sigma)
    x = np.arange(len(perfil_invertido))
    mask = ~np.isnan(perfil_filtrado)
    
    # Interpolación
    interp = interpolate.interp1d(x[mask], perfil_filtrado[mask], kind='quadratic', fill_value='extrapolate')
    perfil_interpolado = interp(x)

    # Detección de los nuevos picos (círculos suaves)
    picos_circulos, _ = find_peaks(perfil_interpolado, height=umbral - rel, distance=dist, prominence=5)

    # Cada línea con la mancha más cercana dentro de su ventana; sin mancha, None (no medible)
    diferencias = []
    for p1 in picos:
        cerca = [abs(p2 - p1) for p2 in picos_circulos if ventana is None or abs(p2 - p1) <= ventana]
        diferencias.append(min(cerca) if cerca else None)

    # Mensajes opcionales
    #print(f"Líneas detectadas: {len(picos)}")
    #print(f"Máximos filtrado e interpolado: {len(picos_circulos)}")
    #print(f"Posición de la línea: {picos}")
    #print(f"Posición del círculo: {picos_circulos}")
    #print(f"Distancias: {diferencias}\n")

    return perfil_interpolado, picos_circulos, diferencias

def calcular_distancias(picos):
    import numpy as np
    return np.diff(picos)

def graficar_resultados(img_original, perfil, picos, metodo, fila_especifica, filtro, control="B",
    altura=None, interceptos=None, canvas=None, perfil_v=None, altura_v=None, interceptos_v=None, cm_por_pixel=None,
    perfil_invertido=None, perfil_interpolado=None, picos2=None, izq_ips=None, der_ips=None):
    import cv2
    if canvas is not None:
        fig = canvas.figure
        fig.clear()
    else:
        plt, _, gridspec, _ = _get_mpl()
        fig = plt.figure(figsize=(12, 8))

    import matplotlib.gridspec as gridspec
    import numpy as np

    gs = gridspec.GridSpec(2, 2, width_ratios=[1, 2])

    if control == "B":
        if izq_ips is None:
            izq_ips = np.array([])
        if der_ips is None:
            der_ips = np.array([])

        # Ejes
        ax_res = fig.add_subplot(gs[:, 1])   # Perfil (derecha)
        ax_img = fig.add_subplot(gs[0, 0])   # Imagen original (arriba izquierda)
        ax_img_p = fig.add_subplot(gs[1, 0]) # Imagen con líneas (abajo izquierda)

        if cm_por_pixel:
            x_mm = np.arange(len(perfil)) * cm_por_pixel * 10


        # Perfil
        ax_res.plot(x_mm, perfil_invertido, color='lightblue', linestyle='-', linewidth=1.5, label='Perfil original')
        ax_res.plot(x_mm, perfil_interpolado, color='purple', alpha=0.5, linestyle='--', linewidth=1, label='Perfil interpolado')
        ax_res.plot(np.array(picos)* cm_por_pixel * 10, perfil_invertido[picos], 'x', color='red', label='Líneas marcadas')
        if picos2 is not None and len(picos2) > 0:
            picos2_int = np.array(picos2, dtype=int)
            ax_res.plot(picos2_int * cm_por_pixel * 10, perfil_interpolado[picos2_int], 'x', color='orange', label='Máximo del Campo')

        if len(izq_ips) > 0 and len(der_ips) > 0:
            for x in np.array(izq_ips) * cm_por_pixel * 10:
                ax_res.axvline(x, linestyle=":", color='gray', alpha=0.5)
            for x in np.array(der_ips)* cm_por_pixel * 10:
                ax_res.axvline(x, linestyle=":", color='gray', alpha=0.5)

        ax_res.set_title(f"Perfil de intensidad invertido ({CAPA_DEL_FILTRO.get(filtro, filtro)})")
        ax_res.set_xlabel("Posición (mm)")
        ax_res.set_ylabel("Intensidad")
        ax_res.legend()

        # Imagen original
        ax_img.imshow(cv2.cvtColor(img_original, cv2.COLOR_BGR2RGB))
        ax_img.set_title("Imagen original")
        ax_img.axis("off")

        # Imagen con líneas detectadas
        ax_img_p.imshow(cv2.cvtColor(img_original, cv2.COLOR_BGR2RGB))
        for x in picos:
            ax_img_p.axvline(x, linestyle=':', color='red')
        for x in picos2:
            ax_img_p.axvline(x, linestyle=':', color='orange')
        ax_img_p.set_title("Imagen con líneas detectadas")
        ax_img_p.axis("off")

        if cm_por_pixel:
            x_mm = np.arange(len(perfil)) * cm_por_pixel * 10
        else:
            x_mm = np.arange(len(perfil))

        if canvas is not None:
            fig.tight_layout(rect=[0, 0.03, 1, 0.95])
            canvas.draw()
        else:
            plt.tight_layout(rect=[0, 0.03, 1, 0.95])
            plt.show()

    elif control == "C":
        ax_img = fig.add_subplot(gs[0, 0])
        ax_proc = fig.add_subplot(gs[1, 0])
        ax_perfil = fig.add_subplot(gs[:, 1])
        fig.suptitle('Resultados', fontsize=16)

        ax_img.imshow(cv2.cvtColor(img_original, cv2.COLOR_BGR2RGB))
        ax_img.set_title('Imagen Original')
        ax_img.axis('off')

        gray = cv2.cvtColor(img_original, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        imagen_clahe = clahe.apply(gray)
        cmap_proc = 'gray' if control == "B" else 'Reds'
        ax_proc.imshow(imagen_clahe, cmap=cmap_proc)
        ax_proc.set_title('Imagen Procesada')
        ax_proc.axis('off')

        if cm_por_pixel:
            x_mm = np.arange(len(perfil)) * cm_por_pixel * 10
            if perfil_v is not None:
                x_mm_v = np.arange(len(perfil_v)) * cm_por_pixel * 10
        else:
            x_mm = np.arange(len(perfil))
            if perfil_v is not None:
                x_mm_v = np.arange(len(perfil_v))
        colorddd = "#61BBF6CE"
        colorddds = "#1924BD"
        ax_perfil.plot(x_mm, perfil, label="Perfil horizontal", color = colorddd)
        if perfil_v is not None:
            ax_perfil.plot(x_mm_v, perfil_v, label="Perfil vertical",color = colorddds)
        if altura is not None:
            ax_perfil.axhline(y=altura, color='red', linestyle='--', label='Altura Media', linewidth = 0.5)
        if interceptos is not None and altura is not None and cm_por_pixel:
            ax_perfil.plot(np.array(interceptos) * cm_por_pixel * 10, [altura] * len(interceptos), 'x', color='mediumvioletred', label='Interceptos (H)')
        if interceptos_v is not None and altura_v is not None and cm_por_pixel:
            ax_perfil.plot(np.array(interceptos_v) * cm_por_pixel * 10, [altura_v] * len(interceptos_v), 'x', color='deeppink', label='Interceptos (V)')
        ax_perfil.set_title("Perfiles de dosis (horizontal y vertical)")
        ax_perfil.set_xlabel("Posición (mm)")
        ax_perfil.grid(True)
        ax_perfil.legend()

        if canvas is not None:
            fig.tight_layout(rect=[0, 0.03, 1, 0.95])
            canvas.draw()
        else:
            plt.tight_layout(rect=[0, 0.03, 1, 0.95])
            plt.show()

def generar_reporte(
    picos, distancias_px, cm_por_pixel=None, control="B", interceptos=None, anchura=None, diferencias=None,
    centro_calculado_h=None, centro_calculado_v=None, desplazamiento_h=None, desplazamiento_v=None,
    exceso_arriba=None, exceso_abajo=None, exceso_izquierda=None, exceso_derecha=None,
    penumbra_izquierda=None, penumbra_derecha=None, cruz=None, aviso=None, capa=None, paradas=None, no_medibles=None):
    import numpy as np
    reporte = []
    reporte.append("<b>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;RESULTADO DE ANÁLISIS DE LA IMAGEN</b>")
    if aviso:  # la cabecera no declara los 600 ppp del procedimiento
        reporte.append(f"<br>{aviso}<br>")
        if not cm_por_pixel:  # «otra»: sin la escala no hay medidas
            return "".join(reporte)

    conversion = cm_por_pixel * 10 if cm_por_pixel else None
    hay_distancias = bool(cm_por_pixel and distancias_px is not None and len(distancias_px) > 0)
    if control == "B":
        if capa:  # la capa que de verdad se midió
            reporte.append(f"<br><b>Capa medida:</b> {capa}<br>")
        reporte.append("<br><b>Líneas Detectadas:</b><br>")
        if paradas is not None:
            reporte.append(f"&nbsp;&nbsp;&nbsp;&nbsp;<b>Paradas en la tira:</b> <span style='font-weight:normal'>{paradas}</span><br>")
        if hay_distancias:
            distancias_mm = distancias_px * conversion
            distancias_mm_list = [round(float(d), 2) for d in distancias_mm]
            reporte.append(f"&nbsp;&nbsp;&nbsp;&nbsp;<b>Distancias entre líneas(mm):</b> <span style='font-weight:normal'>{distancias_mm_list}</span><br>")
            reporte.append(f"&nbsp;&nbsp;&nbsp;&nbsp;<b>Promedio =</b> <span style='font-weight:normal'>{np.mean(distancias_mm):.2f} mm</span><br>")
            reporte.append(f"&nbsp;&nbsp;&nbsp;&nbsp;<b>Desviación estándar =</b> <span style='font-weight:normal'>{np.std(distancias_mm):.2f} mm</span><br>")
        else:
            reporte.append("&nbsp;&nbsp;<b>No se puede convertir a milímetros o no hay distancias detectadas.</b><br>")
        for texto in no_medibles or []:
            reporte.append(f"&nbsp;&nbsp;&nbsp;&nbsp;<span style='font-weight:normal'>No medible, fuera de los promedios: {texto}</span><br>")

        reporte.append("<br><b>Alineación del campo con las líneas</b><br>")
        if diferencias is not None and len(diferencias) > 0:
            if cm_por_pixel:
                diferencias_mm = [round(float(d * conversion), 2) for d in diferencias]
                reporte.append(f"&nbsp;&nbsp;&nbsp;&nbsp;<b>Desplazamientos entre líneas y centros circulares (mm):</b> <span style='font-weight:normal'>{diferencias_mm}</span><br>")
                if hay_distancias:  # la página lee los pares «Promedio»/«Desviación estándar» por orden: sin el de las distancias, este se leería como suyo
                    reporte.append(f"&nbsp;&nbsp;&nbsp;&nbsp;<b>Promedio =</b> <span style='font-weight:normal'>{np.mean(diferencias_mm):.2f} mm</span><br>")
                    reporte.append(f"&nbsp;&nbsp;&nbsp;&nbsp;<b>Desviación estándar =</b> <span style='font-weight:normal'>{np.std(diferencias_mm):.2f} mm</span><br>")
            else:
                diferencias_list = [float(d) for d in diferencias]
                reporte.append(f"&nbsp;&nbsp;&nbsp;&nbsp;<b>Desplazamientos entre líneas y centros circulares (px):</b> <span style='font-weight:normal'>{diferencias_list}</span><br>")
                reporte.append(f"&nbsp;&nbsp;&nbsp;&nbsp;<b>Promedio =</b> <span style='font-weight:normal'>{np.mean(diferencias):.2f} px</span><br>")
                reporte.append(f"&nbsp;&nbsp;&nbsp;&nbsp;<b>Desviación estándar =</b> <span style='font-weight:normal'>{np.std(diferencias):.2f} px</span><br>")
        else:
            reporte.append("&nbsp;&nbsp;<b>No hay diferencias detectadas.</b><br>")
    elif control == "C":
        if cm_por_pixel:
            conversion = cm_por_pixel * 10
            if isinstance(interceptos, dict) and isinstance(anchura, dict):
                inter_h = interceptos.get('horizontal')
                ancho_h = anchura.get('horizontal')
                pen_izq_h = penumbra_izquierda.get('horizontal') if isinstance(penumbra_izquierda, dict) else None
                pen_der_h = penumbra_derecha.get('horizontal') if isinstance(penumbra_derecha, dict) else None
                inter_v = interceptos.get('vertical')
                ancho_v = anchura.get('vertical')
                pen_izq_v = penumbra_izquierda.get('vertical') if isinstance(penumbra_izquierda, dict) else None
                pen_der_v = penumbra_derecha.get('vertical') if isinstance(penumbra_derecha, dict) else None

                # Tabla de perfiles horizontal y vertical
                reporte.append("""
                <table style="width:100%; margin-bottom:1px; border-spacing:0; table-layout:fixed;">
                <tr>
                    <th style="text-align:left; width:49%; padding:2px 2px;"><b>Perfil Horizontal:</b></th>
                    <th style="text-align:left; width:49%; padding:2px 2px;"><b>Perfil Vertical:</b></th>
                </tr>
                <tr>
                    <td style="padding:2px 2px; vertical-align:top;">
                        <b>&nbsp;&nbsp;&nbsp;&nbsp;Anchura a mitad de altura =</b> <span style='font-weight:normal'>{:.2f} mm</span><br>
                        <b>&nbsp;&nbsp;&nbsp;&nbsp;Penumbra izquierda =</b> <span style='font-weight:normal'>{:.2f} mm</span><br>
                        <b>&nbsp;&nbsp;&nbsp;&nbsp;Penumbra derecha =</b> <span style='font-weight:normal'>{:.2f} mm</span>
                    </td>
                    <td style="padding:2px 2px; vertical-align:top;">
                        <b>&nbsp;&nbsp;&nbsp;&nbsp;Anchura a mitad de altura =</b> <span style='font-weight:normal'>{:.2f} mm</span><br>
                        <b>&nbsp;&nbsp;&nbsp;&nbsp;Penumbra izquierda =</b> <span style='font-weight:normal'>{:.2f} mm</span><br>
                        <b>&nbsp;&nbsp;&nbsp;&nbsp;Penumbra derecha =</b> <span style='font-weight:normal'>{:.2f} mm</span>
                    </td>
                </tr>
                </table>
                """.format(
                    ancho_h * conversion, pen_izq_h * conversion, pen_der_h * conversion,
                    ancho_v * conversion, pen_izq_v * conversion, pen_der_v * conversion
                ))

                # Tabla de coincidencia de campo y excesos
                reporte.append("""
                <table style="width:100%; margin-bottom:1px; border-spacing:0; table-layout:fixed;">
                <tr>
                    <th style="text-align:left; width:49%; padding:2px 2px;"><b>Coincidencia de campo</b></th>
                    <th style="text-align:left; width:49%; padding:2px 2px;"><b>Excesos de campo</b></th>
                </tr>
                <tr>
                    <td style="padding:2px 2px; vertical-align:top;">
                        <b>&nbsp;&nbsp;Posición del centro de la placa:</b><br>
                        &nbsp;&nbsp;&nbsp;&nbsp;<b>En X =</b> <span style='font-weight:normal'>{:.2f} mm</span><br>
                        &nbsp;&nbsp;&nbsp;&nbsp;<b>En Y =</b> <span style='font-weight:normal'>{:.2f} mm</span><br>
                        <b>&nbsp;&nbsp;Posición del centro calculado con el perfil:</b><br>
                        &nbsp;&nbsp;&nbsp;&nbsp;<b>En X =</b> <span style='font-weight:normal'>{:.2f} mm</span><br>
                        &nbsp;&nbsp;&nbsp;&nbsp;<b>En Y =</b> <span style='font-weight:normal'>{:.2f} mm</span>
                    </td>
                    <td style="padding:2px 2px; vertical-align:top;">
                        <b>&nbsp;&nbsp;&nbsp;&nbsp;Exceso arriba:</b> <span style='font-weight:normal'>{}</span><br>
                        <b>&nbsp;&nbsp;&nbsp;&nbsp;Exceso abajo:</b> <span style='font-weight:normal'>{}</span><br>
                        <b>&nbsp;&nbsp;&nbsp;&nbsp;Exceso izquierda:</b> <span style='font-weight:normal'>{}</span><br>
                        <b>&nbsp;&nbsp;&nbsp;&nbsp;Exceso derecha:</b> <span style='font-weight:normal'>{}</span>
                    </td>
                </tr>
                </table>
                """.format(
                    cruz[0] * conversion, cruz[1] * conversion,
                    centro_calculado_h * conversion, centro_calculado_v * conversion,
                    f"{exceso_arriba:.2f} mm" if exceso_arriba and exceso_arriba > 0.01 else "0 mm",
                    f"{exceso_abajo:.2f} mm" if exceso_abajo and exceso_abajo > 0.01 else "0 mm",
                    f"{exceso_izquierda:.2f} mm" if exceso_izquierda and exceso_izquierda > 0.01 else "0 mm",
                    f"{exceso_derecha:.2f} mm" if exceso_derecha and exceso_derecha > 0.01 else "0 mm"
                ))
    else:
        reporte.append("<b>No se puede convertir a milímetros: DPI no disponible.</b><br>")

    return "".join(reporte)

def analizar_lineas(imagen_path, metodo=True, fila_especifica=None, umbral_relativo=1.0, distancia_minima=None, mostrar=True,
                    filtro='verde', canvas=None):    
    import cv2
    import numpy as np
    img = cv2.imread(imagen_path)
    imagen_proc = preprocesar_imagen(img, filtro=filtro)

    if distancia_minima is None:
        distancia_minima = 20 if metodo else 200

    perfil = obtener_perfil(imagen_proc, metodo, fila_especifica)
    picos = detectar_picos(perfil, umbral_relativo, distancia_minima)
    # Inicializa distancias como array vacío por defecto
    distancias = np.array([])
    if len(picos) > 1:
        distancias = calcular_distancias(picos)
    cm_por_pixel, aviso = metadata(imagen_path, distancias)
    if cm_por_pixel is None:  # la resolución no se confirma: no se mide ni se dibuja, y el lienzo no conserva la película anterior
        if canvas is not None:
            canvas.figure.clear()
            canvas.draw()
        return generar_reporte(picos, distancias, aviso=aviso)

    # Una parada por línea: dos picos a menos de medio paso de la regla son la misma línea (queda el más alto)
    paso_px = REGLA_DE_LA_TIRA["paso_mm"] / (cm_por_pixel * 10)
    lineas = picos  # todos los picos finos se apartan antes de buscar las manchas
    picos = detectar_picos(perfil, umbral_relativo, max(distancia_minima, int(paso_px / 2)))

    # Invertir el perfil
    max_val = np.max(perfil)
    perfil_invertido = max_val - perfil

    # Calcular umbral absoluto
    umbral = np.mean(perfil_invertido) + umbral_relativo * np.std(perfil_invertido)

    # Calcular anchos de los picos principales
    izq_ips, der_ips = None, None
    if len(picos) > 0:
        # Ancho físico deseado en mm
        ancho_mm = 1 # 1 mm de ancho de pico esperado
        if cm_por_pixel:
            ancho_px = ancho_mm / (cm_por_pixel * 10)
            izq_ips = lineas - ancho_px / 2
            der_ips = lineas + ancho_px / 2
        else:
            anchos, alturas_rel, izq_ips, der_ips = peak_widths(perfil_invertido, picos, rel_height=0.3)
            # --- FILTRO DE ANCHOS ATÍPICOS ---
            anchos_validos = anchos[anchos < np.median(anchos) * 1.3]  # Puedes ajustar el factor 1.5
            if len(anchos_validos) > 0:
                ancho_promedio = np.mean(anchos_validos)
                for i, ancho in enumerate(anchos):
                    if ancho > np.median(anchos) * 1.5:
                        # Corrige izq_ips y der_ips para este pico
                        centro = (izq_ips[i] + der_ips[i]) / 2
                        izq_ips[i] = centro - ancho_promedio / 2
                        der_ips[i] = centro + ancho_promedio / 2


    # Calcular perfil interpolado y picos suaves
    perfil_interpolado, picos2, diferencias = analizar_circulos_perfil(
        perfil_invertido, picos, izq_ips, der_ips, umbral, rel=22, dist=distancia_minima + 20, ventana=paso_px / 2)
    # Una parada es una línea con su mancha a menos de medio paso; las distancias, entre paradas seguidas
    no_medibles = [f"el pico en {p * cm_por_pixel * 10:.1f} mm no tiene mancha a menos de {REGLA_DE_LA_TIRA['paso_mm'] / 2:g} mm: no es una parada"
                   for p, d in zip(picos, diferencias) if d is None]
    picos = np.array([p for p, d in zip(picos, diferencias) if d is not None], dtype=int)
    diferencias = [d for d in diferencias if d is not None]
    distancias = calcular_distancias(picos) if len(picos) > 1 else np.array([])
    no_medibles += [f"entre las paradas {i + 1} y {i + 2} hay {d * cm_por_pixel * 10:.2f} mm: falta una parada medible entre ellas"
                    for i, d in enumerate(distancias) if d > 1.5 * paso_px]
    distancias = distancias[distancias <= 1.5 * paso_px]

    if cm_por_pixel:
        distancias_mm = distancias * (cm_por_pixel * 10)
    else:
        distancias_mm = None

    if mostrar or canvas is not None:
        graficar_resultados(img_original = img, perfil = perfil, picos = picos, metodo = metodo, fila_especifica = fila_especifica,
            filtro = filtro, control = "B", canvas = canvas, cm_por_pixel = cm_por_pixel, perfil_invertido = perfil_invertido,
            perfil_interpolado = perfil_interpolado, picos2 = picos2, izq_ips = izq_ips, der_ips = der_ips
        )

    reporte = generar_reporte(picos, distancias, cm_por_pixel, control="B", interceptos=None, anchura=None, diferencias=diferencias, aviso=aviso,
                              capa=CAPA_DEL_FILTRO.get(filtro, filtro), paradas=len(picos), no_medibles=no_medibles)
    return reporte
