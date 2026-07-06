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

def cargar_imagen(path):
    import cv2
    img = cv2.imread(path)
    if img is None:
        raise ValueError("No se pudo cargar la imagen.")
    return img

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

def calcular_altura_media(perfil_invertido):
    import numpy as np
    return (np.max(perfil_invertido) + np.min(perfil_invertido)) / 2

def hallar_interceptos(perfil, linea):
    interceptos = []
    for i in range(len(perfil) - 1):
        y1 = perfil[i]
        y2 = perfil[i + 1]

        if (y1 <= linea and y2 >= linea) or (y1 >= linea and y2 <= linea):
            x_cruce = i + (linea - y1) / (y2 - y1) 
            interceptos.append(x_cruce)
    return interceptos

def encontrar_anchura(interceptos):
    if len(interceptos) >= 2:
        fhmw = interceptos[-1] - interceptos[0]
        return fhmw
    else: 
        return
    

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

def guardar_datos(picos, distancias_px, cm_por_pixel=None, control = "B", interceptos=None, anchura=None, diferencias=None):
    import numpy as np
    datos = []
    if control == "B":
        datos.append(f"   Líneas detectadas: {len(picos)}")
        
        if cm_por_pixel:
            distancias_mm = distancias_px * (cm_por_pixel * 10)
            datos.append(f"   Distancias (mm): {[round(d, 2) for d in distancias_mm]}")
            datos.append(f"   Promedio (mm): {np.mean(distancias_mm):.2f}")
            datos.append(f"   Desviación estándar (mm): {np.std(distancias_mm):.2f}")

        else:
            datos.append("   No se puede convertir a milímetros: DPI no disponible.")
        datos.append("=" * 60)

    elif control == "C":
        anchura_mm = anchura * (cm_por_pixel * 10) if cm_por_pixel else None
        interceptos_mm = [x * (cm_por_pixel * 10) for x in interceptos] if cm_por_pixel and interceptos else None
        datos.append(f"Posición de los interceptos: {[f'{x:.2f} (mm)' for x in interceptos_mm]}")
        datos.append(f"Anchura a mitad de altura: {anchura_mm:.2f} (mm)" if anchura_mm else "No hay anchura")

    return "\n".join(datos)

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

def normalizar_perfil(perfil):
    import numpy as np
    perfil_normalizado = 100 * (perfil - np.min(perfil)) / (np.max(perfil) - np.min(perfil))
    return perfil_normalizado

def informacion_perfil(perfil, cm_por_pixel, sigma_suavizado=2):
    """
    Calcula interceptos al 50% del máximo sobre el perfil suavizado.
    El suavizado elimina cruces espurios por ruido en la penumbra sin
    desplazar el borde real (el gradiente es suave allí).
    """
    import numpy as np
    from scipy.ndimage import gaussian_filter1d

    # Invertir y normalizar 0-100
    perfil_inv = np.max(perfil) - perfil
    rango = np.max(perfil_inv) - np.min(perfil_inv)
    if rango == 0:
        rango = 1
    perfil_inv = 100 * (perfil_inv - np.min(perfil_inv)) / rango

    # Suavizar ANTES de buscar cruces — elimina ruido local en penumbra
    perfil_suave = gaussian_filter1d(perfil_inv, sigma=sigma_suavizado)

    max_val    = np.max(perfil_suave)
    min_val    = np.min(perfil_suave)
    media_altura = (max_val + min_val) / 2   # sigue siendo 50% del rango

    # Cruces sobre el perfil suavizado
    cruces_80    = hallar_interceptos(perfil_suave, max_val * 0.8)
    cruces_20    = hallar_interceptos(perfil_suave, max_val * 0.2)
    cruces_media = hallar_interceptos(perfil_suave, media_altura)

    # Filtro adicional: quedarse solo con el cruce más externo de cada lado
    # Esto descarta cualquier cruce espurio interior al campo
    cruces_media = _filtrar_cruces_externos(cruces_media, len(perfil_suave))

    ancho_media = encontrar_anchura(cruces_media)

    def calcular_penumbras(cr80, cr20, cm_por_pixel):
        if not cr80 or not cr20:
            return None, None
        cr80 = sorted(cr80)
        cr20 = sorted(cr20)
        c80_izq = cr80[0]
        candidatos_izq = [c for c in cr20 if c < c80_izq]
        pen_izq = abs(c80_izq - max(candidatos_izq)) if candidatos_izq else None
        c80_der = cr80[-1]
        candidatos_der = [c for c in cr20 if c > c80_der]
        pen_der = abs(min(candidatos_der) - c80_der) if candidatos_der else None
        return pen_izq, pen_der

    penumbra_izq, penumbra_der = calcular_penumbras(cruces_80, cruces_20, cm_por_pixel)

    if ancho_media is not None:
        print(f"Tamaño de Campo: {ancho_media * cm_por_pixel * 10:.2f} (mm)")
    else:
        print("Tamaño de Campo: No disponible")

    return (perfil_inv, media_altura,
            cruces_80, cruces_20, cruces_media, ancho_media,
            penumbra_izq, penumbra_der)


def _filtrar_cruces_externos(cruces, largo_perfil):
    """
    De todos los cruces detectados, conserva solo el más a la izquierda
    y el más a la derecha. Descarta cruces interiores causados por ruido
    o por variaciones de flatness dentro del campo.
    Si hay 0 o 1 cruce, devuelve tal cual.
    """
    if len(cruces) < 2:
        return cruces
    return [min(cruces), max(cruces)]
def interseccion(p1, p2, p3, p4):
    """Calcula el punto de intersección entre las líneas p1-p2 y p3-p4."""
    def det(a, b):
        return a[0]*b[1] - a[1]*b[0]
    
    xdiff = (p1[0] - p2[0], p3[0] - p4[0])
    ydiff = (p1[1] - p2[1], p3[1] - p4[1])

    div = det(xdiff, ydiff)
    if div == 0:
        raise Exception('Líneas no se cruzan')

    d = (det(p1, p2), det(p3, p4))
    x = det(d, xdiff) / div
    y = det(d, ydiff) / div
    return int(x), int(y)

def detectar_contornos(img, umbral=240, area_min=200, debug=False, cm_por_pixel=None):
    import math, cv2, numpy as np

    dpi = int(round(2.54 / cm_por_pixel))
    if 199 < dpi <= 200:   escala = 1
    elif 299 < dpi <= 300: escala = 1.5
    elif 599 < dpi <= 600: escala = 3
    else:                  escala = 1

    img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = img_gray.shape
    red_inv = cv2.bitwise_not(img_gray)
    output = img.copy()

    # ── Cruz: tomar el contorno más cercano al centro de la imagen ──
    _, cruz_thresh = cv2.threshold(red_inv, umbral, 255, cv2.THRESH_BINARY)
    contornos_cruz, _ = cv2.findContours(
        cruz_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    centro_img = np.array([w / 2, h / 2])
    cruz = None
    mejor_dist = float('inf')

    for cnt in contornos_cruz:
        area = cv2.contourArea(cnt)
        if area < area_min or area > (w * h * 0.05):   # descarta bordes y gigantes
            continue
        M = cv2.moments(cnt)
        if M['m00'] == 0:
            continue
        cx = M['m10'] / M['m00']
        cy = M['m01'] / M['m00']
        dist = np.linalg.norm(np.array([cx, cy]) - centro_img)
        if dist < mejor_dist:
            mejor_dist = dist
            cruz = (int(cx), int(cy))

    if cruz is not None:
        cv2.drawMarker(output, cruz, (0, 0, 255),
                       markerType=cv2.MARKER_CROSS, markerSize=20, thickness=2)
    # --- Detectar puntos (esquinas) ---
    # --- Detectar puntos de esquinas ---
    h, w = img_gray.shape

    # Tamaño de región de búsqueda en cada esquina
    margen = int(min(h, w) * 0.28)

    # Regiones de interés (ROIs)
    zonas = {
        "arriba_izq": (0, margen, 0, margen),
        "arriba_der": (0, margen, w - margen, w),
        "abajo_izq": (h - margen, h, 0, margen),
        "abajo_der": (h - margen, h, w - margen, w),
    }

    puntos = {}

    for nombre, (y1, y2, x1, x2) in zonas.items():

        roi = img_gray[y1:y2, x1:x2]

        # Blur para eliminar textura y gradientes suaves
        blur = cv2.GaussianBlur(roi, (9, 9), 0)

        # Resaltar objetos oscuros pequeños
        diff = cv2.subtract(blur, roi)

        # Threshold sobre diferencia local
        _, th = cv2.threshold(diff, 1, 255, cv2.THRESH_BINARY)

        # Limpiar ruido
        kernel = np.ones((3,3), np.uint8)

        th = cv2.morphologyEx(
            th,
            cv2.MORPH_OPEN,
            kernel
        )

        # Componentes conectados
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(th)

        mejor_punto = None
        mejor_area = 0

        for i in range(1, num_labels):

            area = stats[i, cv2.CC_STAT_AREA]
            

            # Filtrar ruido diminuto y manchas gigantes
            if  8*escala < area < 300*escala:

                cx, cy = centroids[i]

                # Coordenadas globales
                cx_global = int(cx + x1)
                cy_global = int(cy + y1)

                # Elegir el blob más grande válido
                if area > mejor_area:

                    mejor_area = area
                    mejor_punto = (cx_global, cy_global)

        if mejor_punto is None:
            raise ValueError(f"No se encontró punto en {nombre}")

        puntos[nombre] = mejor_punto

        if debug:

            cv2.circle(output, mejor_punto, 8, (0,255,0), -1)

            cv2.putText(
                output,
                nombre,
                (mejor_punto[0] + 10, mejor_punto[1]),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0,255,0),
                1
            )

    puntos = ajustar_esquinas_manual(img, puntos, cm_por_pixel)

    arriba_izq = puntos["arriba_izq"]
    arriba_der = puntos["arriba_der"]
    abajo_izq = puntos["abajo_izq"]
    abajo_der = puntos["abajo_der"]
    
    # --- Medidas en mm ---
    lado_arriba = math.hypot(arriba_der[0] - arriba_izq[0], arriba_der[1] - arriba_izq[1])
    lado_abajo = math.hypot(abajo_der[0] - abajo_izq[0], abajo_der[1] - abajo_izq[1])
    lado_izquierda = math.hypot(arriba_izq[0] - abajo_izq[0], arriba_izq[1] - abajo_izq[1])
    lado_derecha = math.hypot(arriba_der[0] - abajo_der[0], arriba_der[1] - abajo_der[1])

    print(f"Lado arriba: {lado_arriba * cm_por_pixel * 10:.2f} mm")
    print(f"Lado abajo: {lado_abajo * cm_por_pixel * 10:.2f} mm")
    print(f"Lado izquierda: {lado_izquierda * cm_por_pixel * 10:.2f} mm")
    print(f"Lado derecha: {lado_derecha * cm_por_pixel * 10:.2f} mm")

    # --- Centro geométrico como intersección de diagonales ---
    centro_teorico = interseccion(abajo_izq, arriba_der, abajo_der, arriba_izq)
    print(f"Centro: {centro_teorico}")
    #print("Cruz:", cruz)

    #print("Puntos ordenados:")
    #print("Arriba izq:", arriba_izq)
    #print("Arriba der:", arriba_der)
    #print("Abajo izq:", abajo_izq)
    #print("Abajo der:", abajo_der)

    if debug:
        cv2.imshow("Detección de contornos", output)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    esquinas = {
        "arriba_izq": arriba_izq,
        "arriba_der": arriba_der,
        "abajo_izq": abajo_izq,
        "abajo_der": abajo_der
    }

    return cruz, esquinas, centro_teorico, lado_arriba, lado_izquierda

def ajustar_esquinas_manual(img, puntos, cm_por_pixel):

    import cv2
    import numpy as np

    img_base = img.copy()

    h, w = img.shape[:2]

    max_w = 600
    max_h = 400

    escala = min(max_w / w, max_h / h)

    if escala > 1:
        escala = 1

    # Imagen SOLO para mostrar
    img_display_base = cv2.resize(
        img_base,
        None,
        fx=escala,
        fy=escala
    )

    # Puntos visuales
    puntos_display = {}

    for nombre, (x,y) in puntos.items():

        puntos_display[nombre] = (
            int(x * escala),
            int(y * escala)
        )

    punto_activo = [None]

    radio = 20

    colores = {
        "arriba_izq": (0,0,255),
        "arriba_der": (255,0,0),
        "abajo_izq": (0,255,0),
        "abajo_der": (0,165,255)
    }

    def redibujar():

        temp = img_display_base.copy()

        for nombre, (x,y) in puntos_display.items():

            cv2.circle(
                temp,
                (x,y),
                2,
                colores[nombre],
                -1
            )

            cv2.putText(
                temp,
                nombre,
                (x+10, y-10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                colores[nombre],
                1
            )
        
        cv2.imshow("Ajustar esquinas", temp)
    
   

    def mouse(event, x, y, flags, param):

        if event == cv2.EVENT_LBUTTONDOWN:

            for nombre, (px,py) in puntos_display.items():

                dist = ((x-px)**2 + (y-py)**2)**0.5

                if dist < radio:

                    punto_activo[0] = nombre
                    break

        elif event == cv2.EVENT_MOUSEMOVE:

            if punto_activo[0] is not None:

                # Actualiza visual
                puntos_display[punto_activo[0]] = (x,y)

                # Actualiza REAL
                puntos[punto_activo[0]] = (
                    int(x / escala),
                    int(y / escala)
                )

                redibujar()

        elif event == cv2.EVENT_LBUTTONUP:

            punto_activo[0] = None

    cv2.namedWindow(
        "Ajustar esquinas",
        cv2.WINDOW_NORMAL
    )

    cv2.setMouseCallback(
        "Ajustar esquinas",
        mouse
    )

    redibujar()

    while True:

        key = cv2.waitKey(1) & 0xFF

        # ENTER
        if key == 13:
            cv2.destroyAllWindows()
            break

        # ESC
        elif key == 27:

            cv2.destroyAllWindows()
            return None

    cv2.destroyAllWindows()

    return puntos




def analisis_campo(cruces_media_h = None, cruces_media_v = None,  cm_por_pixel = None, cruz = None, centro_teorico = None, arriba_izq = None, 
                arriba_der = None, abajo_izq = None, abajo_der = None, media_izq = None, media_der = None, media_arr = None, media_aba = None):
    #print("************************************************************************************************************")
    #print("                                          ANÁLISIS GENERAL                                                  ")
    #print("                                  ---------------------------------                                         ")

    # 1. Calcular intersecciones
    try:
        
        intersecciones = [(i, j) for i in cruces_media_h for j in cruces_media_v]

        # 2. Ordenar intersecciones
        intersecciones_ordenadas = sorted(intersecciones, key=lambda p: (p[0], p[1]))
        punto_inicio = intersecciones_ordenadas[0]
        punto_final = intersecciones_ordenadas[-1]

        # 3. Diagonal contraria
        punto_arriba_derecha = min(intersecciones, key=lambda p: (p[1], -p[0]))
        punto_abajo_izquierda = max(intersecciones, key=lambda p: (p[1], -p[0]))

        # 4. Centro calculado por perfiles
        centro_calculado_v = (cruces_media_v[0] + cruces_media_v[-1]) / 2
        centro_calculado_h = (cruces_media_h[0] + cruces_media_h[-1]) / 2

        # 5. Centro detectado por cruz
        centro_imagen_v = cruz[1]
        centro_imagen_h = cruz[0]
        


        centro_teorico_v = centro_teorico[1]
        centro_teorico_h = centro_teorico[0]
        delta_cruz_x = (cruz[0] - centro_teorico[0]) * cm_por_pixel * 10
        delta_cruz_y = (cruz[1] - centro_teorico[1]) * cm_por_pixel * 10
        print(f"Cruz vs centro geométrico: Δx={delta_cruz_x:.2f}mm, Δy={delta_cruz_y:.2f}mm")
        magnitud = np.sqrt(delta_cruz_x**2 + delta_cruz_y**2)
        from PyQt5.QtWidgets import QMessageBox
        
   
        # 6. Mostrar centros
        #print(f"Centro teorico x: {centro_teorico_h * cm_por_pixel * 10:.2f}")
        #print(f"Centro teorico y: {centro_teorico_v * cm_por_pixel * 10:.2f}\n")
        #print(f"Centro calculado x: {centro_calculado_h * cm_por_pixel * 10:.2f}")
        #print(f"Centro calculado y: {centro_calculado_v * cm_por_pixel * 10:.2f}\n")

        # 7. Desplazamientos
        desplazamiento_v = centro_teorico_v - centro_calculado_v
        desplazamiento_h = centro_teorico_h - centro_calculado_h

        #print(f"Desplazamiento en x: {desplazamiento_h * cm_por_pixel * 10:.2f}")
        #print(f"Desplazamiento en y: {desplazamiento_v * cm_por_pixel * 10:.2f}\n")

        #print("************************************************************************************************************")

        #print("************************************************************************************************************")
        #print("                                 INTERPRETACIÓN DE EXCESO DE CAMPO                                          ")
        #print("                            -------------------------------------------                                     ")

        # Para las franjas del inicio: arriba e izquierda
        if arriba_izq != 0 and arriba_der != 0 and abajo_izq != 0 and abajo_der == 0:

            exceso_arriba_izq = (arriba_izq[1] - cruces_media_v[0]) * (cm_por_pixel * 10)
            exceso_arriba_der = (arriba_der[1] - cruces_media_v[0]) * (cm_por_pixel * 10)    

            exceso_izquierda_ar = (arriba_izq[0] - cruces_media_h[0]) * (cm_por_pixel * 10)
            exceso_izquierda_ab = (abajo_izq[0] - cruces_media_h[0]) * (cm_por_pixel * 10)

            # ARRIBA
            #print(f"{'Exceso' if exceso_arriba_izq > 0 else 'Falta'} ARRIBA (izq): {abs(exceso_arriba_izq):.2f} mm")
            #print(f"{'Exceso' if exceso_arriba_der > 0 else 'Falta'} ARRIBA (der): {abs(exceso_arriba_der):.2f} mm")

            # IZQUIERDA
            #print(f"{'Exceso' if exceso_izquierda_ar > 0 else 'Falta'} IZQUIERDA (arriba): {abs(exceso_izquierda_ar):.2f} mm")
            #print(f"{'Exceso' if exceso_izquierda_ab > 0 else 'Falta'} IZQUIERDA (abajo): {abs(exceso_izquierda_ab):.2f} mm")

            #print("************************************************************************************************************")
            QMessageBox.information(
                None,
                "Desplazamiento del Isocentro",
                f"Desplazamiento del isocentro respecto al campo:\n\n"
                f"ΔX = {delta_cruz_x:.2f} mm\n"
                f"ΔY = {delta_cruz_y:.2f} mm\n"
                f"|Δ| = {magnitud:.2f} mm"
            )
            return (punto_inicio, punto_final, punto_arriba_derecha, punto_abajo_izquierda,
                    centro_calculado_h, centro_calculado_v, desplazamiento_h, desplazamiento_v,
                    exceso_arriba_izq, exceso_arriba_der, exceso_izquierda_ar, exceso_izquierda_ab)

        # Para las franjas de la mitad: centro de cada lado
        elif arriba_izq == 0 and arriba_der == 0 and abajo_izq == 0 and abajo_der == 0:

            exceso_izquierda = (media_izq[0] - cruces_media_h[0]) * (cm_por_pixel * 10)
            exceso_derecha   = (cruces_media_h[-1] - media_der[0]) * (cm_por_pixel * 10)

            exceso_arriba = (media_arr[1] - cruces_media_v[0]) * (cm_por_pixel * 10)
            exceso_abajo  = (cruces_media_v[-1] - media_aba[1]) * (cm_por_pixel * 10)

            #print(f"{'Exceso' if exceso_izquierda > 0 else 'Falta'} Izquierda: {abs(exceso_izquierda):.2f} mm")
            #print(f"{'Exceso' if exceso_derecha > 0 else 'Falta'} Derecha:   {abs(exceso_derecha):.2f} mm")
            #print(f"{'Exceso' if exceso_arriba > 0 else 'Falta'} Arriba:    {abs(exceso_arriba):.2f} mm")
            #print(f"{'Exceso' if exceso_abajo > 0 else 'Falta'} Abajo:     {abs(exceso_abajo):.2f} mm")

            #print("************************************************************************************************************")
            return (punto_inicio, punto_final, punto_arriba_derecha, punto_abajo_izquierda,
                    centro_calculado_h, centro_calculado_v, desplazamiento_h, desplazamiento_v,
                    exceso_izquierda, exceso_derecha, exceso_arriba, exceso_abajo)

        # Para las franjas del final: derecha y abajo
        elif arriba_izq == 0 and arriba_der != 0 and abajo_izq != 0 and abajo_der != 0:

            exceso_abajo_izq = (cruces_media_v[-1] - abajo_izq[1]) * (cm_por_pixel * 10)
            exceso_abajo_der = (cruces_media_v[-1] - abajo_der[1]) * (cm_por_pixel * 10)

            exceso_derecha_ar = (cruces_media_h[-1] - arriba_der[0]) * (cm_por_pixel * 10)
            exceso_derecha_ab = (cruces_media_h[-1] - abajo_der[0]) * (cm_por_pixel * 10)

            # ABAJO
            #print(f"{'Exceso' if exceso_abajo_izq > 0 else 'Falta'} ABAJO (izq): {abs(exceso_abajo_izq):.2f} mm")
            #print(f"{'Exceso' if exceso_abajo_der > 0 else 'Falta'} ABAJO (der): {abs(exceso_abajo_der):.2f} mm")

            # DERECHA
            #print(f"{'Exceso' if exceso_derecha_ar > 0 else 'Falta'} DERECHA (arriba): {abs(exceso_derecha_ar):.2f} mm")
            #print(f"{'Exceso' if exceso_derecha_ab > 0 else 'Falta'} DERECHA (abajo): {abs(exceso_derecha_ab):.2f} mm")

            #print("************************************************************************************************************")
            return (punto_inicio, punto_final, punto_arriba_derecha, punto_abajo_izquierda,
                    centro_calculado_h, centro_calculado_v, desplazamiento_h, desplazamiento_v,
                    exceso_abajo_izq, exceso_abajo_der, exceso_derecha_ar, exceso_derecha_ab)

        # Perfil general: medir todos los lados
        else:
            exceso_arriba_izq = (arriba_izq[1] - cruces_media_v[0]) * (cm_por_pixel * 10)
            exceso_arriba_der = (arriba_der[1] - cruces_media_v[0]) * (cm_por_pixel * 10)

            exceso_abajo_izq = (cruces_media_v[-1] - abajo_izq[1]) * (cm_por_pixel * 10)
            exceso_abajo_der = (cruces_media_v[-1] - abajo_der[1]) * (cm_por_pixel * 10)

            exceso_izquierda_ar = (arriba_izq[0] - cruces_media_h[0]) * (cm_por_pixel * 10)
            exceso_izquierda_ab = (abajo_izq[0] - cruces_media_h[0]) * (cm_por_pixel * 10)

            exceso_derecha_ar = (cruces_media_h[-1] - arriba_der[0]) * (cm_por_pixel * 10)
            exceso_derecha_ab = (cruces_media_h[-1] - abajo_der[0]) * (cm_por_pixel * 10)

            # ARRIBA
            #print(f"{'Exceso' if exceso_arriba_izq > 0 else 'Falta'} ARRIBA (izq): {abs(exceso_arriba_izq):.2f} mm")
            #print(f"{'Exceso' if exceso_arriba_der > 0 else 'Falta'} ARRIBA (der): {abs(exceso_arriba_der):.2f} mm")

            # ABAJO
            #print(f"{'Exceso' if exceso_abajo_izq > 0 else 'Falta'} ABAJO (izq): {abs(exceso_abajo_izq):.2f} mm")
            #print(f"{'Exceso' if exceso_abajo_der > 0 else 'Falta'} ABAJO (der): {abs(exceso_abajo_der):.2f} mm")

            # IZQUIERDA
            #print(f"{'Exceso' if exceso_izquierda_ar > 0 else 'Falta'} IZQUIERDA (arriba): {abs(exceso_izquierda_ar):.2f} mm")
            #print(f"{'Exceso' if exceso_izquierda_ab > 0 else 'Falta'} IZQUIERDA (abajo): {abs(exceso_izquierda_ab):.2f} mm")

            # DERECHA
            #print(f"{'Exceso' if exceso_derecha_ar > 0 else 'Falta'} DERECHA (arriba): {abs(exceso_derecha_ar):.2f} mm")
            #print(f"{'Exceso' if exceso_derecha_ab > 0 else 'Falta'} DERECHA (abajo): {abs(exceso_derecha_ab):.2f} mm")
            #print("************************************************************************************************************")
            return (punto_inicio, punto_final, punto_arriba_derecha, punto_abajo_izquierda,
                    centro_calculado_h, centro_calculado_v, desplazamiento_h, desplazamiento_v,
                    exceso_arriba_izq, exceso_arriba_der, exceso_abajo_izq, exceso_abajo_der,
                    exceso_izquierda_ar, exceso_izquierda_ab, exceso_derecha_ar, exceso_derecha_ab)
    except Exception as e:
        print("Imagen no subida o inadecuada: ", e)

def graficar_analisis_campo(
    img_R, cruz, cruces_media, cruces_media_h, centro_calculado_h, centro_calculado_v,
    punto_inicio, punto_final, punto_arriba_derecha, punto_abajo_izquierda,
    perfil_v_inv, media_altura, cruces_80, cruces_20,
    perfil_h_inv, media_altura_h, cruces_80_h, cruces_20_h,
    conversion,
    arriba_izq, arriba_der, abajo_izq, abajo_der,
    exceso_arriba_izq, exceso_arriba_der,
    exceso_abajo_izq, exceso_abajo_der,
    exceso_izquierda_ar, exceso_izquierda_ab,
    exceso_derecha_ar, exceso_derecha_ab,
    lado_arriba, lado_izquierda, canvas=None ):
    def mm_a_px(mm):
        return mm / conversion

    def etiquetar_exceso(texto, x, y):
        ax_img.text(x, y, texto, fontsize=8, color='black', ha='center', va='center')

    if canvas is not None:
        fig = canvas.figure
        fig.clear()
    else:
        fig = plt.figure(figsize=(12, 8))
    
    import matplotlib.gridspec as gridspec
    gs = gridspec.GridSpec(2, 2, width_ratios=[1.5, 1], figure=fig)

    ax_img = fig.add_subplot(gs[:, 0])
    ax_perfil_v = fig.add_subplot(gs[0, 1])
    ax_perfil_h = fig.add_subplot(gs[1, 1])

    ax_img.imshow(img_R, cmap="Reds")
    ax_img.plot(cruz[0], cruz[1], 'o', ms=5, color='red')

    for y in cruces_media:
        ax_img.plot([cruces_media_h[0], cruces_media_h[-1]], [y, y], color='black', linestyle='--', linewidth=1)
    for x in cruces_media_h:
        ax_img.plot([x, x], [cruces_media[0], cruces_media[-1]], color='black', linestyle='--', linewidth=1)

    ax_img.axvline(centro_calculado_h, color='mediumvioletred', linestyle='--', linewidth=1)
    ax_img.axhline(centro_calculado_v, color='mediumvioletred', linestyle='--', linewidth=1)
    ax_img.plot(centro_calculado_h, centro_calculado_v, 'x', color='blue', markersize=6)

    for x in cruces_media_h:
        for y in cruces_media:
            ax_img.plot(x, y, 'bo', ms=3)

    ax_img.plot([punto_inicio[0], punto_final[0]], [punto_inicio[1], punto_final[1]], '--', linewidth=0.8, color='deeppink')
    ax_img.plot([punto_arriba_derecha[0], punto_abajo_izquierda[0]], [punto_arriba_derecha[1], punto_abajo_izquierda[1]], '--', color='deeppink', linewidth=0.8)

    # Cuadro real (líneas azules)
    ax_img.plot([arriba_izq[0], arriba_der[0]], [arriba_izq[1], arriba_der[1]], color='blue', linewidth=1)
    ax_img.plot([abajo_izq[0], abajo_der[0]], [abajo_izq[1], abajo_der[1]], color='blue', linewidth=1)
    ax_img.plot([arriba_izq[0], abajo_izq[0]], [arriba_izq[1], abajo_izq[1]], color='blue', linewidth=1)
    ax_img.plot([arriba_der[0], abajo_der[0]], [arriba_der[1], abajo_der[1]], color='blue', linewidth=1)

    ax_img.plot([arriba_izq[0], abajo_der[0]], [arriba_izq[1], abajo_der[1]], color='blue', linestyle='--', linewidth=1)
    ax_img.plot([arriba_der[0], abajo_izq[0]], [arriba_der[1], abajo_izq[1]], color='blue', linestyle='--', linewidth=1)

    
        # Excesos como trapecios (positivos o negativos)
    if exceso_arriba_izq != 0 or exceso_arriba_der != 0:
        puntos = [
            (arriba_izq[0], arriba_izq[1] - mm_a_px(exceso_arriba_izq)),
            (arriba_der[0], arriba_der[1] - mm_a_px(exceso_arriba_der)),
            (arriba_der[0], arriba_der[1]),
            (arriba_izq[0], arriba_izq[1])
        ]
        mpl = get_matplotlib_components()
        Polygon = mpl['Polygon']
        ax_img.add_patch(Polygon(puntos, closed=True, color='gray', alpha=0.3))

    if exceso_abajo_izq != 0 or exceso_abajo_der != 0:
        puntos = [
            (abajo_izq[0], abajo_izq[1]),
            (abajo_der[0], abajo_der[1]),
            (abajo_der[0], abajo_der[1] + mm_a_px(exceso_abajo_der)),
            (abajo_izq[0], abajo_izq[1] + mm_a_px(exceso_abajo_izq))
        ]
        ax_img.add_patch(Polygon(puntos, closed=True, color='gray', alpha=0.3))

    if exceso_izquierda_ar != 0 or exceso_izquierda_ab != 0:
        puntos = [
            (arriba_izq[0] - mm_a_px(exceso_izquierda_ar), arriba_izq[1]),
            (arriba_izq[0], arriba_izq[1]),
            (abajo_izq[0], abajo_izq[1]),
            (abajo_izq[0] - mm_a_px(exceso_izquierda_ab), abajo_izq[1])
        ]
        ax_img.add_patch(Polygon(puntos, closed=True, color='gray', alpha=0.3))

    if exceso_derecha_ar != 0 or exceso_derecha_ab != 0:
        puntos = [
            (arriba_der[0], arriba_der[1]),
            (arriba_der[0] + mm_a_px(exceso_derecha_ar), arriba_der[1]),
            (abajo_der[0] + mm_a_px(exceso_derecha_ab), abajo_der[1]),
            (abajo_der[0], abajo_der[1])
        ]
        plt, _, _, = _get_mpl()
        ax_img.add_patch(Polygon(puntos, closed=True, color='gray', alpha=0.3))

        # Etiquetas de exceso (ahora también si son negativos)
    if exceso_arriba_izq != 0:
        y = arriba_izq[1] - mm_a_px(exceso_arriba_izq) - 5 if exceso_arriba_izq > 0 else arriba_izq[1] + 5
        etiquetar_exceso(f"{exceso_arriba_izq:.1f} mm", arriba_izq[0], y)
    if exceso_arriba_der != 0:
        y = arriba_der[1] - mm_a_px(exceso_arriba_der) - 5 if exceso_arriba_der > 0 else arriba_der[1] + 5
        etiquetar_exceso(f"{exceso_arriba_der:.1f} mm", arriba_der[0], y)
    if exceso_abajo_izq != 0:
        y = abajo_izq[1] + mm_a_px(exceso_abajo_izq) + 5 if exceso_abajo_izq > 0 else abajo_izq[1] - 5
        etiquetar_exceso(f"{exceso_abajo_izq:.1f} mm", abajo_izq[0], y)
    if exceso_abajo_der != 0:
        y = abajo_der[1] + mm_a_px(exceso_abajo_der) + 5 if exceso_abajo_der > 0 else abajo_der[1] - 5
        etiquetar_exceso(f"{exceso_abajo_der:.1f} mm", abajo_der[0], y)
    if exceso_izquierda_ar != 0:
        x = arriba_izq[0] - mm_a_px(exceso_izquierda_ar) - 5 if exceso_izquierda_ar > 0 else arriba_izq[0] + 5
        etiquetar_exceso(f"{exceso_izquierda_ar:.1f} mm", x, arriba_izq[1])
    if exceso_izquierda_ab != 0:
        x = abajo_izq[0] - mm_a_px(exceso_izquierda_ab) - 5 if exceso_izquierda_ab > 0 else abajo_izq[0] + 5
        etiquetar_exceso(f"{exceso_izquierda_ab:.1f} mm", x, abajo_izq[1])
    if exceso_derecha_ar != 0:
        x = arriba_der[0] + mm_a_px(exceso_derecha_ar) + 5 if exceso_derecha_ar > 0 else arriba_der[0] - 5
        etiquetar_exceso(f"{exceso_derecha_ar:.1f} mm", x, arriba_der[1])
    if exceso_derecha_ab != 0:
        x = abajo_der[0] + mm_a_px(exceso_derecha_ab) + 5 if exceso_derecha_ab > 0 else abajo_der[0] - 5
        etiquetar_exceso(f"{exceso_derecha_ab:.1f} mm", x, abajo_der[1])
    
    """ax_img.axhline(60, color='cornflowerblue', linestyle='--', linewidth=1, label=f'{860}')
    ax_img.axhline(130, color='cornflowerblue', linestyle='--', linewidth=1, label=f'{930}')    
    
    ax_img.axvline(60, color='cornflowerblue', linestyle='--', linewidth=1, label=f'{860}')
    ax_img.axvline(130, color='cornflowerblue', linestyle='--', linewidth=1, label=f'{930}')

    ax_img.axhline(840, color='cornflowerblue', linestyle='--', linewidth=1, label=f'{860}')
    ax_img.axhline(911, color='cornflowerblue', linestyle='--', linewidth=1, label=f'{930}')    
    
    ax_img.axvline(840, color='cornflowerblue', linestyle='--', linewidth=1, label=f'{860}')
    ax_img.axvline(911, color='cornflowerblue', linestyle='--', linewidth=1, label=f'{930}')"""

    ax_img.set_title("Placa con diferencias de campo")
    ax_img.axis('on')

    # Perfil vertical
    # DESPUÉS
    x_mm_v = np.arange(len(perfil_v_inv)) * conversion
    ax_perfil_v.plot(x_mm_v, perfil_v_inv, color='black', label='perfil_v invertido')
    ax_perfil_v.plot(np.array(cruces_media) * conversion, [media_altura] * len(cruces_media), 'x', color='green', label='Interceptos media')
    for i, y in enumerate(cruces_80):
        ax_perfil_v.axvline(y * conversion, color='hotpink', linestyle='--', linewidth=1, label='80%' if i == 0 else "")
    for i, y in enumerate(cruces_20):
        ax_perfil_v.axvline(y * conversion, color='deeppink', linestyle='--', linewidth=1, label='20%' if i == 0 else "")
    ax_perfil_v.set_xlabel("Fila (mm)")
    ax_perfil_v.set_ylabel("Intensidad (invertida)")
    ax_perfil_v.legend()
    ax_perfil_v.grid(True)

    # Perfil horizontal
    # DESPUÉS
    x_mm_h = np.arange(len(perfil_h_inv)) * conversion
    ax_perfil_h.plot(x_mm_h, perfil_h_inv, color='black', label='perfil_h invertido')
    ax_perfil_h.plot(np.array(cruces_media_h) * conversion, [media_altura_h] * len(cruces_media_h), 'x', color='green', label='Interceptos media')
    for i, x in enumerate(cruces_80_h):
        ax_perfil_h.axvline(x * conversion, color='hotpink', linestyle='--', linewidth=1, label='80%' if i == 0 else "")
    for i, x in enumerate(cruces_20_h):
        ax_perfil_h.axvline(x * conversion, color='deeppink', linestyle='--', linewidth=1, label='20%' if i == 0 else "")
    ax_perfil_h.set_xlabel("Columna (mm)")
    ax_perfil_h.set_ylabel("Intensidad (invertida)")
    ax_perfil_h.legend()
    ax_perfil_h.grid(True)

    if canvas is not None:
        canvas.draw()
    else:
        plt.show()

    #plt.tight_layout()
    #plt.show()
    return ax_img, fig

def analizar_cuadrado(imagen_path, metodo=True, fila_especifica_x=None, fila_especifica_y=None, filtro=None, mostrar=True, canvas=None):
    import cv2
    import numpy as np

    img = cv2.imread(imagen_path)
    cm_por_pixel = metadata(imagen_path)
    cruz, esquinas, centro_teorico, lado_arriba, lado_izquierda = detectar_contornos(img, area_min=10,cm_por_pixel=cm_por_pixel)
    imagen_proc = preprocesar_imagen(img, filtro=filtro)

    perfil_v = np.mean(imagen_proc, axis=1)
    perfil_h = np.mean(imagen_proc, axis=0)

    perfil_inv_h, altura_h, cruces_80_h, cruces_20_h, cruces_media_h, ancho_media_h, penumbra_izq_h, penumbra_der_h = informacion_perfil(perfil_h, cm_por_pixel)
    perfil_inv_v, altura_v, cruces_80_v, cruces_20_v, cruces_media_v, ancho_media_v, penumbra_izq_v, penumbra_der_v = informacion_perfil(perfil_v, cm_por_pixel)

    # Extraer los puntos de esquina desde el diccionario
    arriba_izq = esquinas['arriba_izq']
    arriba_der = esquinas['arriba_der']
    abajo_izq = esquinas['abajo_izq']
    abajo_der = esquinas['abajo_der']

    # --- Análisis del campo: obtenemos ahora valores extendidos ---
    (punto_inicio, punto_final, punto_arriba_derecha, punto_abajo_izquierda, centro_calculado_h, centro_calculado_v,
        desplazamiento_h, desplazamiento_v, exceso_arriba_izq, exceso_arriba_der, exceso_abajo_izq, exceso_abajo_der, 
        exceso_izquierda_ar, exceso_izquierda_ab, exceso_derecha_ar, exceso_derecha_ab) = analisis_campo(cruces_media_h, 
        cruces_media_v,  cm_por_pixel, cruz, centro_teorico, arriba_izq, arriba_der, abajo_izq , abajo_der
    )

    if mostrar or canvas is not None:
        _ = graficar_analisis_campo(
            img_R                 =  imagen_proc,
            cruz                  =  cruz,
            cruces_media          =  cruces_media_v,
            cruces_media_h        =  cruces_media_h,
            centro_calculado_h    =  centro_calculado_h,
            centro_calculado_v    =  centro_calculado_v,
            punto_inicio          =  punto_inicio,
            punto_final           =  punto_final,
            punto_arriba_derecha  = punto_arriba_derecha,
            punto_abajo_izquierda = punto_abajo_izquierda,
            perfil_v_inv          = perfil_inv_v,
            media_altura          = altura_v,
            cruces_80             = cruces_80_v,
            cruces_20             = cruces_20_v,
            perfil_h_inv          = perfil_inv_h,
            media_altura_h        = altura_h,
            cruces_80_h           = cruces_80_h,
            cruces_20_h           = cruces_20_h,
            conversion            = cm_por_pixel * 10,
            arriba_izq            = arriba_izq,
            arriba_der            = arriba_der,
            abajo_izq             = abajo_izq,
            abajo_der             = abajo_der,
            exceso_arriba_izq     = exceso_arriba_izq,
            exceso_arriba_der     =  exceso_arriba_der,
            exceso_abajo_izq      = exceso_abajo_izq,
            exceso_abajo_der      = exceso_abajo_der,
            exceso_izquierda_ar   = exceso_izquierda_ar,
            exceso_izquierda_ab   = exceso_izquierda_ab,
            exceso_derecha_ar     = exceso_derecha_ar,
            exceso_derecha_ab     = exceso_derecha_ab,
            lado_arriba           = lado_arriba,
            lado_izquierda        = lado_izquierda
        )
        
    # Reporte
    interceptos = {'horizontal': cruces_media_h, 'vertical': cruces_media_v}
    anchura = {'horizontal': ancho_media_h, 'vertical': ancho_media_v}
    penumbra_izquierda = {'horizontal': penumbra_izq_h, 'vertical': penumbra_izq_v}
    penumbra_derecha = {'horizontal': penumbra_der_h, 'vertical': penumbra_der_v}

    reporte = generar_reporte(
        picos                  = None,
        distancias_px          = None,
        cm_por_pixel           = cm_por_pixel,
        control                = "C",
        interceptos            = interceptos,
        anchura                = anchura,
        penumbra_izquierda     = penumbra_izquierda,
        penumbra_derecha       = penumbra_derecha,
        centro_calculado_h     = centro_calculado_h,
        centro_calculado_v     = centro_calculado_v,
        desplazamiento_h       = desplazamiento_h,
        desplazamiento_v       = desplazamiento_v,
        exceso_arriba          = (exceso_arriba_izq + exceso_arriba_der) / 2,
        exceso_abajo           = (exceso_abajo_izq + exceso_abajo_der) / 2,
        exceso_izquierda       = (exceso_izquierda_ar + exceso_izquierda_ab) / 2,
        exceso_derecha         = (exceso_derecha_ar + exceso_derecha_ab) / 2
    )

    return reporte

# Ejemplo de uso
if __name__ == "__main__":
    tipo_imagen = 1
    if tipo_imagen  == 2:
        resultado = analizar_cuadrado(
            imagen_path="IMAGENES/EPSON001_200_Copy.JPG",
            metodo=True,                   # False = analizar fila específica
            fila_especifica_x = 134+25,
            fila_especifica_y = 728,        # Define la fila si metodo=False
            filtro=None,                   # Si es None devuelve la imagen original en un solo canal 
            mostrar=True,                   # Graficar los resultados
        )
        #print(resultado)
    elif tipo_imagen == 1:
        resultado = analizar_lineas(
            imagen_path="IMAGENES/imagen1_200_copa.JPG",
            metodo=True,                    # False = analizar fila específica
            fila_especifica=50,              # Define la fila si metodo=False
            umbral_relativo=-0.5,            # Ajusta la desviación estandar para el umbral (se necesita en 1)
            distancia_minima=45,            # Ajustar según separación de líneas
            mostrar=True,                   # Graficar los resultados
            filtro=None                # 'clahe' o 'bilateral'
        )
        #print(resultado)
    else:    
        print("Seleccione una opción disponible")