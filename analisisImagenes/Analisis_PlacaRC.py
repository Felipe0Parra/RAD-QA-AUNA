from resources.utils.matplotlib_lazy import get_matplotlib_components
from scipy.signal import find_peaks, peak_widths
from PIL import Image
from scipy.ndimage import gaussian_filter1d
from scipy import interpolate
import numpy as np
# Helper para obtener componentes matplotlib cuando se necesiten
def _get_mpl():
    """Obtiene componentes matplotlib de forma diferida"""
    mpl = get_matplotlib_components()
    return mpl['plt'], mpl['Figure'], mpl['GridSpec']

def metadata(imagen_path):
    imagen = Image.open(imagen_path)
    dpi = imagen.info.get("dpi")
    cm_por_pixel = None

    if dpi:
        x_dpi = dpi[0]
        cm_por_pixel = 2.54 / x_dpi  # 2.54 cm por pulgada
        print("DPI: ", x_dpi)
        #print(f"DPI: {dpi[0]} x {dpi[1]}")
        #print(f"Cada píxel mide aproximadamente {cm_por_pixel:.4f} cm")
    else:
        x_dpi = 300 
        cm_por_pixel = 2.54/x_dpi
        print("No se encontró información de DPI en la imagen.")
    

    return cm_por_pixel

def preprocesar_imagen(imagen_bgr, filtro='clahe'):
    import cv2
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
        raise ValueError("Filtro no reconocido. Usa 'clahe' o 'bilateral'.")

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

def analizar_circulos_perfil(perfil_invertido, picos, izq_ips, der_ips, umbral, rel=7, dist=45, sigma=2):
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

    Retorna:
        perfil_interpolado : np.ndarray
        picos_circulos : np.ndarray
        diferencias : list[int]
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

    # Comparación con los picos originales
    diferencias = [abs(p2 - p1) for p1, p2 in zip(picos, picos_circulos)]

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

        ax_res.set_title("Perfil de intensidad invertido (canal rojo)")
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
    penumbra_izquierda=None, penumbra_derecha=None, cruz=None):  
    import numpy as np
    reporte = []
    reporte.append("<b>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;RESULTADO DE ANÁLISIS DE LA IMAGEN</b>")

    conversion = cm_por_pixel * 10 if cm_por_pixel else None

    if control == "B":
        reporte.append("<br><b>Líneas Detectadas:</b><br>")
        if cm_por_pixel and distancias_px is not None and len(distancias_px) > 0:
            distancias_mm = distancias_px * conversion
            distancias_mm_list = [round(float(d), 2) for d in distancias_mm]
            reporte.append(f"&nbsp;&nbsp;&nbsp;&nbsp;<b>Distancias entre líneas(mm):</b> <span style='font-weight:normal'>{distancias_mm_list}</span><br>")
            reporte.append(f"&nbsp;&nbsp;&nbsp;&nbsp;<b>Promedio =</b> <span style='font-weight:normal'>{np.mean(distancias_mm):.2f} mm</span><br>")
            reporte.append(f"&nbsp;&nbsp;&nbsp;&nbsp;<b>Desviación estándar =</b> <span style='font-weight:normal'>{np.std(distancias_mm):.2f} mm</span><br>")
        else:
            reporte.append("&nbsp;&nbsp;<b>No se puede convertir a milímetros o no hay distancias detectadas.</b><br>")

        reporte.append("<br><b>Alineación del campo con las líneas</b><br>")
        if diferencias is not None and len(diferencias) > 0:
            if cm_por_pixel:
                diferencias_mm = [round(float(d * conversion), 2) for d in diferencias]
                reporte.append(f"&nbsp;&nbsp;&nbsp;&nbsp;<b>Desplazamientos entre líneas y centros circulares (mm):</b> <span style='font-weight:normal'>{diferencias_mm}</span><br>")
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
                    filtro='clahe', canvas=None):    
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
    cm_por_pixel = metadata(imagen_path)

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
            izq_ips = picos - ancho_px / 2
            der_ips = picos + ancho_px / 2
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
        perfil_invertido, picos, izq_ips, der_ips, umbral, rel=22, dist=distancia_minima + 20)

    if cm_por_pixel:
        distancias_mm = distancias * (cm_por_pixel * 10)
    else:
        distancias_mm = None

    if mostrar or canvas is not None:
        graficar_resultados(img_original = img, perfil = perfil, picos = picos, metodo = metodo, fila_especifica = fila_especifica,
            filtro = filtro, control = "B", canvas = canvas, cm_por_pixel = cm_por_pixel, perfil_invertido = perfil_invertido,
            perfil_interpolado = perfil_interpolado, picos2 = picos2, izq_ips = izq_ips, der_ips = der_ips
        )

    reporte = generar_reporte(picos, distancias, cm_por_pixel, control="B", interceptos=None, anchura=None, diferencias=diferencias)
    return reporte
