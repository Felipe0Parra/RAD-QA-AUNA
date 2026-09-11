from analisisImagenes.Analisis_PlacaRC import *
from resources.utils.matplotlib_lazy import get_matplotlib_components
from matplotlib.patches import Polygon
import numpy as np
""" =======================================================================================
                                    Funciones Generales
    ======================================================================================="""
def mm_a_px(mm, cm_por_pixel):
    return mm / (cm_por_pixel * 10)

def etiquetar_exceso(ax, texto, x, y):
    ax.text(x, y, texto, fontsize=8, color='black', ha='center', va='center')

def extraer_esquinas(diccionario):
    return (
        tuple(map(float, diccionario['arriba_izq'])),
        tuple(map(float, diccionario['arriba_der'])),
        tuple(map(float, diccionario['abajo_izq'])),
        tuple(map(float, diccionario['abajo_der']))
    )

def dibujar_cuadro(ax, esquinas_dict, color='k', estilo='-', ancho=1.2, diagonales=True):
    arriba_izq, arriba_der, abajo_izq, abajo_der = extraer_esquinas(esquinas_dict)

    ax.plot([arriba_izq[0], arriba_der[0]], [arriba_izq[1], arriba_der[1]], color=color, linestyle=estilo, linewidth=ancho)
    ax.plot([abajo_izq[0], abajo_der[0]], [abajo_izq[1], abajo_der[1]], color=color, linestyle=estilo, linewidth=ancho)
    ax.plot([arriba_izq[0], abajo_izq[0]], [arriba_izq[1], abajo_izq[1]], color=color, linestyle=estilo, linewidth=ancho)
    ax.plot([arriba_der[0], abajo_der[0]], [arriba_der[1], abajo_der[1]], color=color, linestyle=estilo, linewidth=ancho)
    if diagonales:
        ax.plot([arriba_izq[0], abajo_der[0]], [arriba_izq[1], abajo_der[1]], color=color, linestyle='--', linewidth=1)
        ax.plot([arriba_der[0], abajo_izq[0]], [arriba_der[1], abajo_izq[1]], color=color, linestyle='--', linewidth=1)

def dibujar_excesos(ax, esquinas_dict, excesos, cm_por_pixel, posicion):
    arriba_izq, arriba_der, abajo_izq, abajo_der = extraer_esquinas(esquinas_dict)
    ex0, ex1, ex2, ex3 = excesos

    if posicion == "superior":
        if ex0 != 0 or ex1 != 0:
            puntos = [
                (arriba_izq[0], arriba_izq[1] - mm_a_px(ex0, cm_por_pixel)),
                (arriba_der[0], arriba_der[1] - mm_a_px(ex1, cm_por_pixel)),
                (arriba_der[0], arriba_der[1]),
                (arriba_izq[0], arriba_izq[1])
            ]
            ax.add_patch(Polygon(puntos, closed=True, color='gray', alpha=0.3))
        if ex2 != 0 or ex3 != 0:
            puntos = [
                (arriba_izq[0] - mm_a_px(ex2, cm_por_pixel), arriba_izq[1]),
                (arriba_izq[0], arriba_izq[1]),
                (abajo_izq[0], abajo_izq[1]),
                (abajo_izq[0] - mm_a_px(ex3, cm_por_pixel), abajo_izq[1])
            ]
            ax.add_patch(Polygon(puntos, closed=True, color='gray', alpha=0.3))

    elif posicion == "inferior":
        if ex0 != 0 or ex1 != 0:
            puntos = [
                (abajo_izq[0], abajo_izq[1]),
                (abajo_der[0], abajo_der[1]),
                (abajo_der[0], abajo_der[1] + mm_a_px(ex1, cm_por_pixel)),
                (abajo_izq[0], abajo_izq[1] + mm_a_px(ex0, cm_por_pixel))
            ]
            ax.add_patch(Polygon(puntos, closed=True, color='gray', alpha=0.3))
        if ex2 != 0 or ex3 != 0:
            puntos = [
                (arriba_der[0], arriba_der[1]),
                (arriba_der[0] + mm_a_px(ex2, cm_por_pixel), arriba_der[1]),
                (abajo_der[0] + mm_a_px(ex3, cm_por_pixel), abajo_der[1]),
                (abajo_der[0], abajo_der[1])
            ]
            ax.add_patch(Polygon(puntos, closed=True, color='gray', alpha=0.3))

def etiquetar_excesos(ax, esquinas_dict, excesos, cm_por_pixel, posicion):
    arriba_izq, arriba_der, abajo_izq, abajo_der = extraer_esquinas(esquinas_dict)
    ex0, ex1, ex2, ex3 = excesos

    if posicion == "superior":
        if ex0 != 0:
            y = arriba_izq[1] - mm_a_px(ex0, cm_por_pixel) - 20 if ex0 > 0 else arriba_izq[1] + 5
            etiquetar_exceso(ax, f"{-ex0:.1f} mm", arriba_izq[0], y)
        if ex1 != 0:
            y = arriba_der[1] - mm_a_px(ex1, cm_por_pixel) - 20 if ex1 > 0 else arriba_der[1] + 5
            etiquetar_exceso(ax, f"{-ex1:.1f} mm", arriba_der[0], y)

    elif posicion == "izquierda":
        if ex2 != 0:
            x = arriba_izq[0] - mm_a_px(-ex2, cm_por_pixel) - 20 if ex2 > 0 else arriba_izq[0] + 5
            etiquetar_exceso(ax, f"{-ex2:.1f} mm", x, arriba_izq[1])
        if ex3 != 0:
            x = abajo_izq[0] - mm_a_px(-ex3, cm_por_pixel) - 20 if ex3 > 0 else abajo_izq[0] + 5
            etiquetar_exceso(ax, f"{-ex3:.1f} mm", x, abajo_izq[1])

    elif posicion == "inferior":
        if ex0 != 0:
            y = abajo_izq[1] + mm_a_px(ex0, cm_por_pixel) + 20 if ex0 > 0 else abajo_izq[1] - 5
            etiquetar_exceso(ax, f"{-ex0:.1f} mm", abajo_izq[0], y)
        if ex1 != 0:
            y = abajo_der[1] + mm_a_px(ex1, cm_por_pixel) + 20 if ex1 > 0 else abajo_der[1] - 5
            etiquetar_exceso(ax, f"{ex1:.1f} mm", abajo_der[0], y)

    elif posicion == "derecha":
        if ex2 != 0:
            x = arriba_der[0] + mm_a_px(-ex2, cm_por_pixel) + 20 if ex2 > 0 else arriba_der[0] - 5
            etiquetar_exceso(ax, f"{-ex2:.1f} mm", x, arriba_der[1])
        if ex3 != 0:
            x = abajo_der[0] + mm_a_px(-ex3, cm_por_pixel) + 20 if ex3 > 0 else abajo_der[0] - 5
            etiquetar_exceso(ax, f"{-ex3:.1f} mm", x, abajo_der[1])

def perfil_promediado_horizontal(imagen, fila_inicio, fila_fin):
    import numpy as np
    return np.mean(imagen[fila_inicio:fila_fin, :], axis=0), np.mean(imagen[:,fila_inicio:fila_fin], axis=1)

""" =======================================================================================
                                    Estudio General de los perfiles
    ======================================================================================="""
def analizar_franja(imagen_proc, imagen_path, ini_f, fin_f, cm_por_pixel, cruz, centro_teorico,
                    arriba_izq, arriba_der, abajo_izq, abajo_der,
                    arriba_izqg, arriba_derg, abajo_izqg, abajo_derg,
                    medio_izq=None, medio_der=None, medio_arr=None, medio_aba=None, mostrar=False, canvas = None):

    perfil_h, perfil_v = perfil_promediado_horizontal(imagen_proc, ini_f, fin_f)

    #print("Perfil Horizontal:")
    perfil_h_inv, altura_h, cruces_80_h, cruces_20_h, cruces_media_h, ancho_media_h, penumbra_izq_h, penumbra_der_h = informacion_perfil(perfil_h, cm_por_pixel)

    #print("Perfil Vertical:")
    perfil_v_inv, altura_v, cruces_80_v, cruces_20_v, cruces_media_v, ancho_media_v, penumbra_izq_v, penumbra_der_v = informacion_perfil(perfil_v, cm_por_pixel)

    analisis_args = [cruces_media_h, cruces_media_v, cm_por_pixel, cruz, centro_teorico, arriba_izq, arriba_der, abajo_izq, abajo_der]
    if all(v is not None for v in [medio_izq, medio_der, medio_arr, medio_aba]):
        analisis_args.extend([medio_izq, medio_der, medio_arr, medio_aba])

    resultados = analisis_campo(*analisis_args)

    if mostrar or canvas is not None:
        ax_img, fig = graficar_analisis_campo(
            img_R                 = imagen_proc,
            cruz                  = cruz,
            cruces_media          = cruces_media_v,
            cruces_media_h        = cruces_media_h,
            centro_calculado_h    = resultados[4],
            centro_calculado_v    = resultados[5],
            punto_inicio          = resultados[0],
            punto_final           = resultados[1],
            punto_arriba_derecha  = resultados[2],
            punto_abajo_izquierda = resultados[3],
            perfil_v_inv          = perfil_v_inv,
            media_altura          = altura_v,
            cruces_80             = cruces_80_v,
            cruces_20             = cruces_20_v,
            perfil_h_inv          = perfil_h_inv,
            media_altura_h        = altura_h,
            cruces_80_h           = cruces_80_h,
            cruces_20_h           = cruces_20_h,
            conversion            = cm_por_pixel * 10,
            arriba_izq            = arriba_izqg,
            arriba_der            = arriba_derg,
            abajo_izq             = abajo_izqg,
            abajo_der             = abajo_derg,
            exceso_arriba_izq     = resultados[-4] if len(resultados) >= 11 else 0,
            exceso_arriba_der     = resultados[-3] if len(resultados) >= 11 else 0,
            exceso_abajo_izq      = resultados[-4] if len(resultados) >= 11 else 0,
            exceso_abajo_der      = resultados[-3] if len(resultados) >= 11 else 0,
            exceso_izquierda_ar   = resultados[-2] if len(resultados) >= 11 else 0,
            exceso_izquierda_ab   = resultados[-2] if len(resultados) >= 11 else 0,
            exceso_derecha_ar     = resultados[-1] if len(resultados) >= 11 else 0,
            exceso_derecha_ab     = resultados[-1] if len(resultados) >= 11 else 0,
            lado_arriba           = None,
            lado_izquierda        = None,
            canvas=canvas
        )

        ax_img.axhline(ini_f, color='cornflowerblue', linestyle=':', linewidth=1)
        ax_img.axhline(fin_f, color='cornflowerblue', linestyle=':', linewidth=1)
        ax_img.axvline(ini_f, color='cornflowerblue', linestyle=':', linewidth=1)
        ax_img.axvline(fin_f, color='cornflowerblue', linestyle=':', linewidth=1)

        if canvas is not None:
            fig.tight_layout(rect=[0, 0.03, 1, 0.95])
            canvas.draw()
        else:
            mlp = get_matplotlib_components()
            plt = mlp['plt']
            plt.tight_layout(rect=[0, 0.03, 1, 0.95])
            plt.show()

    return {
    "perfil_h_inv": perfil_h_inv,
    "perfil_v_inv": perfil_v_inv,
    "cruces_media_h": cruces_media_h,
    "cruces_media_v": cruces_media_v,
    "ancho_media_h": ancho_media_h,
    "ancho_media_v": ancho_media_v,
    "penumbra_izquierda": {
        "horizontal": penumbra_izq_h,
        "vertical": penumbra_izq_v
    },
    "penumbra_derecha": {
        "horizontal": penumbra_der_h,
        "vertical": penumbra_der_v
    },
    "anchura": {
        "horizontal": ancho_media_h,
        "vertical": ancho_media_v
    },
    "excesos": resultados[-4:] if len(resultados) >= 11 else resultados[-2:]
    }

def grafica_3perfiles(imagen_proc, resultados, esquinas, cm_por_pixel, canvas=None):
    try:
        if canvas is not None:
            fig = canvas.figure
            fig.clear()
        else:
            mlp = get_matplotlib_components()
            plt = mlp['plt']
            plt.close('all')  # Cierra figuras previas si no se usa canvas
            fig = plt.figure(figsize=(12, 8))

        mlp = get_matplotlib_components()
        plt = mlp['plt']
        from matplotlib.gridspec import GridSpec
        gs = GridSpec(2, 2, width_ratios=[1.5, 1], figure=fig)
        ax_img = fig.add_subplot(gs[:, 0])
        ax_perfil_v = fig.add_subplot(gs[0, 1])
        ax_perfil_h = fig.add_subplot(gs[1, 1])

        #------------------ Imagen marcada con excesos según la franja ----------------------
        ax_img.imshow(imagen_proc, cmap="Reds")
        for k in range(len(resultados)):
            excesos = resultados[k]['excesos']
            esquinas_dict = esquinas

            if k == 0:
                dibujar_cuadro(ax_img, esquinas_dict, color="dimgray")
                dibujar_excesos(ax_img, esquinas_dict, excesos, cm_por_pixel, "superior")
                etiquetar_excesos(ax_img, esquinas_dict, excesos, cm_por_pixel, "superior")
                etiquetar_excesos(ax_img, esquinas_dict, excesos, cm_por_pixel, "izquierda")

            elif k == 2:
                dibujar_excesos(ax_img, esquinas_dict, excesos, cm_por_pixel, "inferior")
                etiquetar_excesos(ax_img, esquinas_dict, excesos, cm_por_pixel, "inferior")
                etiquetar_excesos(ax_img, esquinas_dict, excesos, cm_por_pixel, "derecha")
        ax_img.set_title("Placa Marcada con diferencias de Campo")

        #------------------ Perfiles verticales ----------------------
        # DESPUÉS
        conv = cm_por_pixel * 10
        for datos, color, label in zip(
            [resultados[0], resultados[1], resultados[2]],
            ['royalblue', 'lightskyblue', 'dodgerblue'],
            ['Perfil 1', 'Perfil 2', 'Perfil 3']
        ):
            pv = datos["perfil_v_inv"]
            ax_perfil_v.plot(np.arange(len(pv)) * conv, pv, color=color, label=label)

        ax_perfil_v.set_xlabel("Fila (mm)")

        for datos, color, label in zip(
            [resultados[0], resultados[1], resultados[2]],
            ['crimson', 'lightpink', 'deeppink'],
            ['Perfil 1', 'Perfil 2', 'Perfil 3']
        ):
            ph = datos["perfil_h_inv"]
            ax_perfil_h.plot(np.arange(len(ph)) * conv, ph, color=color, label=label)

        ax_perfil_h.set_xlabel("Columna (mm)")
        ax_perfil_h.set_ylabel("Intensidad (invertida)")
        ax_perfil_v.legend()
        ax_perfil_v.grid(True)
        ax_perfil_h.legend()
        ax_perfil_h.grid(True)

        if canvas is not None:
            fig.tight_layout(rect=[0, 0.03, 1, 0.95])
            canvas.draw()
        else:
            fig.tight_layout(rect=[0, 0.03, 1, 0.95])
            plt.show()
    except Exception as e:
        print(e)

""" =======================================================================================
                    Correcciones con respecto a lo ideal y al cuadro marcado
    ======================================================================================="""
def verificar_cuadro_derecho(arriba_izq, arriba_der, abajo_izq, abajo_der, tolerancia_angulo=5, tolerancia_lado_mm=0.5,
                            tolerancia_ejes_mm=0.5, cm_por_pixel=(25.4)/200):
    """
    Verifica si un cuadro está derecho basado en ángulos (~90°), longitudes (~iguales) y orientación (horizontal/vertical).

    Parámetros:
        arriba_izq, arriba_der, abajo_izq, abajo_der : tuplas (x, y)
        tolerancia_angulo : en grados
        tolerancia_lado_mm : tolerancia en mm para diferencias de lados opuestos
        tolerancia_ejes_mm : desviación máxima de alineación vertical/horizontal en mm
        cm_por_pixel : conversión de pixel a cm

    Retorna:
        is_perfecto : bool
    """
    import numpy as np

    #print(f"{':' * 108}")

    def angulo_entre(v1, v2):
        v1 = np.array(v1)
        v2 = np.array(v2)
        cos_theta = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
        cos_theta = np.clip(cos_theta, -1.0, 1.0)
        return np.degrees(np.arccos(cos_theta))

    def distancia_mm(p1, p2):
        dist = np.linalg.norm(np.subtract(p2, p1))
        return dist * cm_por_pixel * 10  # a mm

    # Vectores entre puntos
    vec_top    = np.subtract(arriba_der, arriba_izq)
    vec_right  = np.subtract(abajo_der, arriba_der)
    vec_bottom = np.subtract(abajo_izq, abajo_der)
    vec_left   = np.subtract(arriba_izq, abajo_izq)

    # Ángulos
    angulos = [
        angulo_entre(vec_top, vec_right),
        angulo_entre(vec_right, vec_bottom),
        angulo_entre(vec_bottom, vec_left),
        angulo_entre(vec_left, vec_top)
    ]

    #print("\n       Verificación de ortogonalidad:")
    #print("  ------------------------------------------")

    ortogonal = all(90 - tolerancia_angulo <= a <= 90 + tolerancia_angulo for a in angulos)
    #print("· Ángulos correctos (~90°)" if ortogonal else "· Ángulos desviados")

    # Lados en mm
    lado_sup = distancia_mm(arriba_izq, arriba_der)
    lado_inf = distancia_mm(abajo_izq, abajo_der)
    lado_izq = distancia_mm(arriba_izq, abajo_izq)
    lado_der = distancia_mm(arriba_der, abajo_der)

    #print("\n       Verificación de simetría:")
    #print("----------------------------------------")
    #print(f"- Lado superior:  {lado_sup:.2f} mm")
    #print(f"- Lado inferior:  {lado_inf:.2f} mm")
    #print(f"- Lado izquierdo: {lado_izq:.2f} mm")
    #print(f"- Lado derecho:   {lado_der:.2f} mm")

    simetrico = (
        abs(lado_sup - lado_inf) <= tolerancia_lado_mm and
        abs(lado_izq - lado_der) <= tolerancia_lado_mm
    )
    #print("· Lados simétricos" if simetrico else "· Lados deformados")

    # Alineación con ejes (en mm)
    vertical_incl_izq  = abs(vec_left[0] * cm_por_pixel * 10)
    vertical_incl_der  = abs(vec_right[0] * cm_por_pixel * 10)
    horizontal_incl_top = abs(vec_top[1] * cm_por_pixel * 10)
    horizontal_incl_bot = abs(vec_bottom[1] * cm_por_pixel * 10)

    #print("\n       Verificación de alineación con ejes (en mm):")
    #print("--------------------------------------------------")
    #print(f"- Desviación vertical izquierda:  {vertical_incl_izq:.2f} mm")
    #print(f"- Desviación vertical derecha:    {vertical_incl_der:.2f} mm")
    #print(f"- Desviación horizontal superior: {horizontal_incl_top:.2f} mm")
    #print(f"- Desviación horizontal inferior: {horizontal_incl_bot:.2f} mm")

    vertical_ok = vertical_incl_izq <= tolerancia_ejes_mm and vertical_incl_der <= tolerancia_ejes_mm
    horizontal_ok = horizontal_incl_top <= tolerancia_ejes_mm and horizontal_incl_bot <= tolerancia_ejes_mm

    """if vertical_ok and horizontal_ok:
        #print("· Cuadro alineado a los ejes")
    else:
        #print("· Cuadro no alineado")
        if not vertical_ok:
            #print("  ↪ Lados verticales inclinados")
        if not horizontal_ok:
            #print("  ↪ Lados horizontales inclinados")

    if ortogonal and simetrico and horizontal_ok and vertical_ok:
        #print("\n · El cuadro está derecho")
    else:
        #print("\n · El cuadro está torcido")"""

    #print(f"{':' * 108}\n")

    return {
        "angulos": angulos,
        "lados_mm": {
            "arriba": lado_sup,
            "abajo": lado_inf,
            "izquierda": lado_izq,
            "derecha": lado_der,
        },
        "alineacion_mm": {
            "vertical_izquierda": vertical_incl_izq,
            "vertical_dererecha": vertical_incl_der,
            "horizontal_arriba": horizontal_incl_top,
            "horizontal_abajo": horizontal_incl_bot,
        },
        "estado": {
            "ortogonal": ortogonal,
            "simetrico": simetrico,
            "alineado_horizontal": horizontal_ok,
            "alineado_vertical": vertical_ok,
            "torcido": not (ortogonal and simetrico and horizontal_ok and vertical_ok)
        }
    }

def corregir_cuadro_a_recto_mm(esquinas_dict, cm_por_pixel=10):
    import numpy as np

    arriba_izq = esquinas_dict["arriba_izq"]
    arriba_der = esquinas_dict["arriba_der"]
    abajo_izq  = esquinas_dict["abajo_izq"]
    abajo_der = esquinas_dict["abajo_der"]

    # Centro del cuadro
    xc = (arriba_izq[0] + arriba_der[0] + abajo_der[0] + abajo_izq[0]) / 4
    yc = (arriba_izq[1] + arriba_der[1] + abajo_der[1] + abajo_izq[1]) / 4
    centro_correccion = ((xc * cm_por_pixel * 10), (yc * cm_por_pixel * 10))

    # Ancho y alto promedio en píxeles
    ancho_top = np.linalg.norm(np.subtract(arriba_der, arriba_izq))
    ancho_bottom = np.linalg.norm(np.subtract(abajo_der, abajo_izq))
    ancho_prom = (ancho_top + ancho_bottom) / 2

    alto_left = np.linalg.norm(np.subtract(abajo_izq, arriba_izq))
    alto_right = np.linalg.norm(np.subtract(abajo_der, arriba_der))
    alto_prom = (alto_left + alto_right) / 2

    # Nuevos puntos corregidos (cuadro ortogonal centrado)
    arriba_izq_n = (xc - ancho_prom/2, yc - alto_prom/2)
    arriba_der_n = (xc + ancho_prom/2, yc - alto_prom/2)
    abajo_izq_n  = (xc - ancho_prom/2, yc + alto_prom/2)
    abajo_der_n  = (xc + ancho_prom/2, yc + alto_prom/2)

    mm_por_pixel = cm_por_pixel * 10

    #print("\n Correcciones aplicadas a los vértices (en mm):")
    #print("---------------------------------------------------")
    etiquetas = ['arriba_izq', 'arriba_der', 'abajo_izq', 'abajo_der']
    originales = [arriba_izq, arriba_der, abajo_izq, abajo_der]
    corregidos = [arriba_izq_n, arriba_der_n, abajo_izq_n, abajo_der_n]

    # Calcular las correcciones en mm
    correcciones_mm = {}
    for nombre, p_old, p_new in zip(etiquetas, originales, corregidos):
        delta = np.subtract(p_new, p_old)
        delta_mm = np.array(delta) * mm_por_pixel
        correcciones_mm[nombre] = {
            "Δx": f"{delta_mm[0]:.2f}",
            "Δy": f"{delta_mm[1]:.2f}",
            "|Δ|": f"{np.linalg.norm(delta_mm):.2f}"
        }

    return {
        "arriba_izq": arriba_izq_n,
        "arriba_der": arriba_der_n,
        "abajo_izq":  abajo_izq_n,
        "abajo_der":  abajo_der_n
    }, centro_correccion, ancho_prom * mm_por_pixel, alto_prom * mm_por_pixel, correcciones_mm

def comparar_campo_ideal(ancho_mm, alto_mm, campo_nominal_mm=100):
    mitad = campo_nominal_mm / 2
    exceso_arriba    = (alto_mm / 2) - mitad
    exceso_abajo     = (alto_mm / 2) - mitad
    exceso_izquierda = (ancho_mm / 2) - mitad
    exceso_derecha   = (ancho_mm / 2) - mitad
    #print("\n Comparación con campo ideal de 100x100 mm:")
    #print("--------------------------------------------------------")
    #print("\n Nota: \n    - Si el resultado es positivo: cuadro es más grande de lo que debería en esa dirección. \n    - Si el resultado es negativo: cuadro es más pqueño de lo que debería en esa dirección.")
    #print(f"- Exceso   ARRIBA:    {exceso_arriba:.2f} mm")
    #print(f"- Exceso   ABAJO:     {exceso_abajo:.2f} mm")
    #print(f"- Exceso   IZQUIERDA: {exceso_izquierda:.2f} mm")
    #print(f"- Exceso   DERECHA:   {exceso_derecha:.2f} mm")

    return {
        "arriba_izq":exceso_arriba,
        "arriba_der": exceso_abajo,
        "abajo_izq": exceso_izquierda,
        "abajo_der": exceso_derecha
    }

def grafica_correciones(imagen_proc, esquinas, esquinas_corregidas, esquinas_ideal, resultados, cm_por_pixel, excesos_ideal, canvas=None):
    izquierda = resultados[0]["cruces_media_h"][0]
    derecha = resultados[2]["cruces_media_h"][-1]
    arriba = resultados[0]["cruces_media_v"][0]
    abajo = resultados[2]["cruces_media_v"][-1]

    if canvas is not None:
        fig = canvas.figure
        fig.clear()
    else:
        mlp = get_matplotlib_components()
        plt = mlp['plt']
        plt.close('all')  # Cierra figuras anteriores si no se usa canvas
        fig = plt.figure(figsize=(12, 8))
    from matplotlib.gridspec import GridSpec
    gs = GridSpec(1, 3, width_ratios=[1, 1, 1], figure=fig)
    ax_img = fig.add_subplot(gs[0])
    ax_cor = fig.add_subplot(gs[1])
    ax_der = fig.add_subplot(gs[2])

    # ----------- 1. Placa con excesos --------------
    ax_img.imshow(imagen_proc, cmap="Reds")
    ax_img.set_title("Placa con Diferencias de Campo")
    ax_img.axis('on')

    dibujar_excesos(ax_img, esquinas, resultados[0]['excesos'], cm_por_pixel, "superior")
    etiquetar_excesos(ax_img, esquinas, resultados[0]['excesos'], cm_por_pixel, "superior")
    etiquetar_excesos(ax_img, esquinas, resultados[0]['excesos'], cm_por_pixel, "izquierda")

    dibujar_excesos(ax_img, esquinas, resultados[2]['excesos'], cm_por_pixel, "inferior")
    etiquetar_excesos(ax_img, esquinas, resultados[2]['excesos'], cm_por_pixel, "inferior")
    etiquetar_excesos(ax_img, esquinas, resultados[2]['excesos'], cm_por_pixel, "derecha")

    dibujar_cuadro(ax_img, esquinas, color='dimgrey')

    # ----------- 2. Cuadro corregido --------------
    ax_cor.imshow(imagen_proc, cmap="Reds")
    dibujar_cuadro(ax_cor, esquinas, color='dimgrey', ancho=1.2, estilo='-', diagonales=True)
    dibujar_cuadro(ax_cor, esquinas_corregidas, color='k', ancho=1.2, estilo='-', diagonales=True)

    ax_cor.axhline(arriba,  color='slategray', linewidth=1.2, linestyle='--')
    ax_cor.axhline(abajo,   color='slategray', linewidth=1.2, linestyle='--')
    ax_cor.axvline(izquierda, color='slategray', linewidth=1.2, linestyle='--')
    ax_cor.axvline(derecha,   color='slategray', linewidth=1.2, linestyle='--')
    ax_cor.set_title("Placa Corregida")

    # ----------- 3. Cuadro corregido vs ideal --------------
    ax_der.imshow(imagen_proc, cmap="Reds")
    dibujar_cuadro(ax_der, esquinas_corregidas, color='darkred', ancho=1.2, estilo='-', diagonales=True)
    dibujar_cuadro(ax_der, esquinas_ideal, color='dimgrey', ancho=1.2, estilo='-', diagonales=True)

    # Conexiones entre puntos corregidos e ideales
    pares = [
        (esquinas_corregidas["arriba_izq"], esquinas_ideal["arriba_izq"]),
        (esquinas_corregidas["arriba_der"], esquinas_ideal["arriba_der"]),
        (esquinas_corregidas["abajo_izq"],  esquinas_ideal["abajo_izq"]),
        (esquinas_corregidas["abajo_der"],  esquinas_ideal["abajo_der"]),
    ]
    for (x_old, y_old), (x_new, y_new) in pares:
        ax_der.plot([x_old, x_new], [y_old, y_new], color='gray', linestyle=':', linewidth=1)

    # Marcar puntos
    for punto in esquinas_corregidas.values():
        ax_der.plot(*punto, 'ro', markersize=4)
    for punto in esquinas_ideal.values():
        ax_der.plot(*punto, 'o', markersize=4, color="dimgrey")

    # Dibujar y etiquetar excesos arriba/inferior
    for pos in ["superior", "inferior"]:
        dibujar_excesos(ax_der, esquinas_ideal, list(excesos_ideal.values()), cm_por_pixel, posicion=pos)
        etiquetar_excesos(ax_der, esquinas_ideal, [-v for v in excesos_ideal.values()], cm_por_pixel, posicion=pos)

    ax_der.set_title("Placa Corregida y Alineada")

    if canvas is not None:
        fig.tight_layout(rect=[0, 0.03, 1, 0.95])
        canvas.draw()
        #print("Se dibujó en canvas:", canvas)

    else:
        fig.tight_layout(rect=[0, 0.03, 1, 0.95])
        plt.show()
        #print("Se dibujó el matplot, y el canvas acá es:", canvas)

def aplicar_excesos(esquinas, resultados, cm_por_pixel):
    import numpy as np

    def mm_a_px(mm): return mm / (cm_por_pixel * 10)
    cruce_izq = resultados[0]["cruces_media_h"][0]
    cruce_der = resultados[2]["cruces_media_h"][-1]
    cruce_arr = resultados[0]["cruces_media_v"][0]
    cruce_aba = resultados[2]["cruces_media_v"][-1]

    # Extraer excesos
    ex_ar_izq = resultados[0]['excesos'][0]
    ex_ar_der = resultados[0]['excesos'][1]
    ex_izq_ar = resultados[0]['excesos'][2]
    ex_izq_ab = resultados[0]['excesos'][3]

    ex_ab_izq = resultados[2]['excesos'][0]
    ex_ab_der = resultados[2]['excesos'][1]
    ex_der_ar = resultados[2]['excesos'][2]
    ex_der_ab = resultados[2]['excesos'][3]

    #--------- Correcciones de los bordes con los excesos------------

        # Izquierda:
    ajuste_izq_ar = cruce_izq - mm_a_px(ex_izq_ar) #if ex_izq_ar >= 0 else cruce_izq + mm_a_px(ex_izq_ar)
    ajuste_izq_ab = cruce_izq - mm_a_px(ex_izq_ab) #if ex_izq_ab >= 0 else cruce_izq + mm_a_px(ex_izq_ab)

        # Derecha:
    ajuste_der_ar = cruce_der - mm_a_px(ex_der_ar) #if ex_der_ar >= 0 else cruce_der + mm_a_px(ex_der_ar)
    ajuste_der_ab = cruce_der - mm_a_px(ex_der_ab) #if ex_der_ab >= 0 else cruce_der + mm_a_px(ex_der_ab)

        # Arriba:
    ajuste_ar_izq = cruce_arr - mm_a_px(-ex_ar_izq) #if ex_ar_izq >= 0 else cruce_arr + mm_a_px(ex_ar_izq)
    ajuste_ar_der = cruce_arr - mm_a_px(-ex_ar_der) #if ex_ar_der >= 0 else cruce_arr + mm_a_px(ex_ar_der)

        # Abajo:
    ajuste_ab_izq = cruce_aba - mm_a_px(ex_ab_izq) #if ex_ab_izq >= 0 else cruce_aba + mm_a_px(ex_ab_izq)
    ajuste_ab_der = cruce_aba - mm_a_px(ex_ab_der) #if ex_ab_der >= 0 else cruce_aba + mm_a_px(ex_ab_der)


    # Aplicar excesos (según dirección y convención de signo)
    return {
        "arriba_izq": (
            ajuste_izq_ar,
            ajuste_ar_izq
        ),
        "arriba_der": (
            ajuste_der_ar,
            ajuste_ar_der
        ),
        "abajo_izq": (
            ajuste_izq_ab,
            ajuste_ab_izq
        ),
        "abajo_der": (
            ajuste_der_ab,
            ajuste_ab_der
        ),
    }

def placa_corregida(imagen_proc, cm_por_pixel=None, resultados=None, mostrar=False, esquinas=None, canvas = None, campo_nominal_mm=100):
    #print("\n                                   Simetría de los puntos de referencia")
    verificacion_inicial  = verificar_cuadro_derecho(*extraer_esquinas(esquinas), cm_por_pixel=cm_por_pixel)

    # Corregidas es solo con excesos
    esquinas_corregidas = aplicar_excesos(esquinas, resultados, cm_por_pixel=cm_por_pixel)

    # Dice lo que tiene y lo que hace falta para estar recto y alineadp
    #print("\n                                  Generando cuadro ideal perfectamente alineado")
    esquinas_ideal, _ , _ , _, _ = corregir_cuadro_a_recto_mm(esquinas_corregidas, cm_por_pixel=cm_por_pixel)


    #print("\n                               Simetría de los puntos corregidos (con angulos)")
    verificacion_ideal  = verificar_cuadro_derecho(*extraer_esquinas(esquinas_ideal), cm_por_pixel=cm_por_pixel)
    esquinas_ideal, centro_corr, ancho_mm, alto_mm, correcciones_mm = corregir_cuadro_a_recto_mm(esquinas_corregidas, cm_por_pixel=cm_por_pixel)

    excesos_ideal = comparar_campo_ideal(ancho_mm, alto_mm, campo_nominal_mm)

    if mostrar or canvas is not None:
        grafica_correciones(imagen_proc, esquinas, esquinas_corregidas, esquinas_ideal, resultados, cm_por_pixel, excesos_ideal, canvas=canvas)

    return {
    "verificacion_inicial": verificacion_inicial,
    "verificacion_ideal": verificacion_ideal,
    "centro_corregido": centro_corr,
    "dimensiones": {"ancho": ancho_mm, "alto": alto_mm},
    "excesos_ideal": excesos_ideal,
    "esquinas_corregidas": esquinas_corregidas,
    "esquinas_ideal": esquinas_ideal,
    "correcciones":correcciones_mm
    }

def analizar_cuadrado2(imagen_path, filtro=None, mostrar=True, canvas=None):
    import cv2
    import numpy as np

    img = cv2.imread(imagen_path)
    cm_por_pixel = metadata(imagen_path)
    dpi = int(round(2.54 / cm_por_pixel, 1))
    escala = {200: 1, 300: 1.5, 599:3, 600: 3}.get(dpi, 1)

    cruz, esquinas, centro_teorico, lado_arriba, lado_izquierda = detectar_contornos(img, area_min=10, cm_por_pixel=cm_por_pixel)
    imagen_proc = preprocesar_imagen(img, filtro=filtro)
    campo_nominal_mm = round((lado_arriba * cm_por_pixel * 10) / 5) * 5

    # Valores base comunes si todo es igual para las 3 franjas
    arriba_izq, arriba_der, abajo_izq, abajo_der = extraer_esquinas(esquinas)
    y_top = arriba_izq[1]    # fila superior del campo
    y_bot = abajo_izq[1]     # fila inferior del campo
    alto_px = y_bot - y_top  # alto del campo en píxeles

    medio_arr = ((arriba_izq[0] + arriba_der[0]) / 2, (arriba_izq[1] + arriba_der[1]) / 2)
    medio_aba = ((abajo_izq [0] + abajo_der[0])  / 2, (abajo_izq [1] + abajo_der [1]) / 2)
    medio_izq = ((arriba_izq[0] + abajo_izq[0])  / 2, (arriba_izq[1] + abajo_izq [1]) / 2)
    medio_der = ((arriba_der[0] + abajo_der[0])  / 2, (arriba_der[1] + abajo_der [1]) / 2)


    franjas = [
        {"ini": int(y_top + 0.05 * alto_px), "fin": int(y_top + 0.15 * alto_px),
        "arriba_izq": arriba_izq, "arriba_der": arriba_der,
        "abajo_izq": abajo_izq,   "abajo_der": 0,
        "medio_izq": None, "medio_der": None, "medio_arr": None, "medio_aba": None},

        {"ini": int(y_top + 0.42 * alto_px), "fin": int(y_top + 0.58 * alto_px),
        "arriba_izq": 0, "arriba_der": 0, "abajo_izq": 0, "abajo_der": 0,
        "medio_izq": medio_izq, "medio_der": medio_der,
        "medio_arr": medio_arr, "medio_aba": medio_aba},

        {"ini": int(y_top + 0.85 * alto_px), "fin": int(y_top + 0.95 * alto_px),
        "arriba_izq": 0, "arriba_der": arriba_der,
        "abajo_izq": abajo_izq,  "abajo_der": abajo_der,
        "medio_izq": None, "medio_der": None, "medio_arr": None, "medio_aba": None}
    ]
    resultados = []

    for i, franja in enumerate(franjas, start=1):
        #print(f"\n{'*' * 30}\nPERFILES FRANJA {i}\n{'*' * 30}")
        resultado = analizar_franja(
            imagen_proc, imagen_path,
            int(franja["ini"]), int(franja["fin"]),
            cm_por_pixel, cruz, centro_teorico,
            franja["arriba_izq"], franja["arriba_der"],
            franja["abajo_izq"], franja["abajo_der"],
            arriba_izq, arriba_der, abajo_izq, abajo_der,
            franja.get("medio_izq"), franja.get("medio_der"),
            franja.get("medio_arr"), franja.get("medio_aba"),
            mostrar=mostrar, canvas=canvas
        )
        resultados.append(resultado)


    if mostrar or (canvas is not None):
        grafica_3perfiles(imagen_proc, resultados, esquinas, cm_por_pixel, canvas=canvas)


    analisis_placa = placa_corregida(imagen_proc, cm_por_pixel = cm_por_pixel, resultados=resultados,
                    mostrar=mostrar, esquinas=esquinas, canvas=canvas, campo_nominal_mm=campo_nominal_mm)


    graficas = []

    # Agrega la gráfica de los 3 perfiles
    graficas.append(lambda c: grafica_3perfiles(imagen_proc, resultados, esquinas, cm_por_pixel, canvas=c))

    for i, franja in enumerate(franjas, start=1):
        ini = int(franja["ini"] )
        fin = int(franja["fin"] )

        args = dict(
            imagen_proc=imagen_proc,
            imagen_path=imagen_path,
            ini_f=ini,
            fin_f=fin,
            cm_por_pixel=cm_por_pixel,
            cruz=cruz,
            centro_teorico=centro_teorico,
            arriba_izq=franja["arriba_izq"],
            arriba_der=franja["arriba_der"],
            abajo_izq=franja["abajo_izq"],
            abajo_der=franja["abajo_der"],
            arriba_izqg=arriba_izq,
            arriba_derg=arriba_der,
            abajo_izqg=abajo_izq,
            abajo_derg=abajo_der,
            medio_izq=franja.get("medio_izq"),
            medio_der=franja.get("medio_der"),
            medio_arr=franja.get("medio_arr"),
            medio_aba=franja.get("medio_aba"),
            mostrar=mostrar
        )

        # Captura explícita de `args` en el entorno de la lambda
        graficas.append((lambda args_capturados=args:
                        lambda c: analizar_franja(**args_capturados, canvas=c))())


    # Agrega la gráfica de corrección
    graficas.append(lambda c: grafica_correciones(
        imagen_proc, esquinas, analisis_placa["esquinas_corregidas"],
        analisis_placa["esquinas_ideal"], resultados, cm_por_pixel,
        analisis_placa["excesos_ideal"], canvas=c
    ))

    return {
        "franjas": resultados,
        "verificacion": analisis_placa,
        "cm_por_pixel": cm_por_pixel,
        "dpi": dpi,
        "graficas": graficas
    }

def generar_reporte_completo(resultados_dict):
    franjas = resultados_dict["franjas"]
    verificacion = resultados_dict["verificacion"]
    cm_por_pixel = resultados_dict["cm_por_pixel"]
    dpi = resultados_dict["dpi"]

    def format_val_mm(valor):
        return "{:.2f} mm".format(valor) if valor and abs(valor) > 1e-4 else "No cumple"

    def html_doble_columna(ancho_h, pen_izq_h, pen_der_h, ancho_v, pen_izq_v, pen_der_v, conversion):
        def format_val(valor):
            # C.6 (PLAN_NAVEGACION_Y_UNIDADES_10-09.md §4, SS0.7): `valor`
            # es None cuando `calcular_penumbras` no pudo medir por ese
            # lado -- un hecho de la placa, no un incumplimiento. La
            # guarda vieja (`valor and abs(valor) > 1e-4`) tambien
            # mandaba un 0.0 legitimo a "No cumple".
            if valor is None:
                return "No medible"
            return "{:.3f} mm".format(valor * conversion)

        return f"""
        <table style="width:100%; margin-bottom:1px; border-spacing:0; table-layout:fixed; font-family:Arial, sans-serif;">
        <tr>
            <th style="text-align:left; width:49%; padding:2px 2px;"><b>Perfil Horizontal:</b></th>
            <th style="text-align:left; width:49%; padding:2px 2px;"><b>Perfil Vertical:</b></th>
        </tr>
        <tr>
            <td style="padding:2px 2px; vertical-align:top;">
                <b>&nbsp;&nbsp;&nbsp;&nbsp;Tamaño de Campo  =</b> <span style='font-weight:normal'>{format_val(ancho_h)}</span><br>
                <b>&nbsp;&nbsp;&nbsp;&nbsp;Penumbra izquierda =</b> <span style='font-weight:normal'>{format_val(pen_izq_h)}</span><br>
                <b>&nbsp;&nbsp;&nbsp;&nbsp;Penumbra derecha =</b> <span style='font-weight:normal'>{format_val(pen_der_h)}</span>
            </td>
            <td style="padding:2px 2px; vertical-align:top;">
                <b>&nbsp;&nbsp;&nbsp;&nbsp;Tamaño de Campo =</b> <span style='font-weight:normal'>{format_val(ancho_v)}</span><br>
                <b>&nbsp;&nbsp;&nbsp;&nbsp;Penumbra izquierda =</b> <span style='font-weight:normal'>{format_val(pen_izq_v)}</span><br>
                <b>&nbsp;&nbsp;&nbsp;&nbsp;Penumbra derecha =</b> <span style='font-weight:normal'>{format_val(pen_der_v)}</span>
            </td>
        </tr>
        </table>
        """

    def html_excesos_por_franja(i, excesos, conversion):
        def format_exceso(label, valor):
            return f"&nbsp;&nbsp;&nbsp;&nbsp;<b>{label}:</b> <span style='font-weight:normal'>{format_val_mm(valor * conversion)}</span><br>"

        if i == 1:
            return f"""
            <b>Diferencias de Campo Franja 1  (Arriba - Izquierda):</b><br>
            {format_exceso("Arriba izquierda", excesos[0])}
            {format_exceso("Arriba derecha", excesos[1])}
            {format_exceso("Izquierda arriba", excesos[2])}
            {format_exceso("Izquierda abajo", excesos[3])}
            """
        elif i == 2:
            return f"""
            <b>Diferencias de Campo  Franja 2 (Mitad de cada lado):</b><br>
            {format_exceso("Arriba", excesos[0])}
            {format_exceso("Abajo", excesos[1])}
            {format_exceso("Izquierda", excesos[2])}
            {format_exceso("Derecha", excesos[3])}
            """
        elif i == 3:
            return f"""
            <b>Diferencias de Campo  Franja 3 (Abajo - Derecha):</b><br>
            {format_exceso("Abajo izquierda", excesos[0])}
            {format_exceso("Abajo derecha", excesos[1])}
            {format_exceso("Derecha arriba", excesos[2])}
            {format_exceso("Derecha abajo", excesos[3])}
            """
        else:
            return "<i>Franja no reconocida para mostrar excesos.</i>"

    def diccionario_a_tabla(dic):
        def format_key(k):
            return k.replace("_", " ").capitalize()

        def format_val(v):
            if isinstance(v, float):
                return "{:.2f}".format(v)
            return str(v)

        html = "<table cellspacing='2' cellpadding='3' style='margin-bottom:6px; font-family:Arial, sans-serif;'>"
        for k, v in dic.items():
            html += f"<tr><td><b>{format_key(k)}</b></td><td><span style='font-weight:normal'>{format_val(v)} mm</span></td></tr>"
        html += "</table>"
        return html

    def estado_legible(estado):
        vertical_ok   = estado.get("alineado_vertical", False)
        horizontal_ok = estado.get("alineado_horizontal", False)
        ortogonal     = estado.get("ortogonal", False)
        simetrico     = estado.get("simetrico", False)

        partes = []

        if vertical_ok and horizontal_ok:
            partes.append("· Cuadro alineado a los ejes")
        else:
            partes.append("· Cuadro no alineado")
            if not vertical_ok:
                partes.append("&nbsp;&nbsp;&nbsp;&nbsp;↪ Lados verticales inclinados")
            if not horizontal_ok:
                partes.append("&nbsp;&nbsp;&nbsp;&nbsp;↪ Lados horizontales inclinados")

        if ortogonal and simetrico and horizontal_ok and vertical_ok:
            partes.append("<br>· El cuadro está derecho")
        else:
            partes.append("<br>· El cuadro está torcido")

        return "<div style='margin-top:6px; margin-bottom:10px; font-family:Arial, sans-serif;'>" + "<br>".join(partes) + "</div>"


    # Armado del HTML completo
    html = []
    html.append("<div style='text-transform: none;'>")
    html.append("<br><b style='font-family:Arial, sans-serif;'>Análisis completo de la placa</b><br>")

    conversion = cm_por_pixel * 10 if cm_por_pixel else 1

    for i, franja in enumerate(franjas, 1):
        html.append(f"<b style='font-family:Arial, sans-serif;'>Franja {i}</b>")

        ancho_h = franja["anchura"].get("horizontal")
        pen_izq_h = franja["penumbra_izquierda"].get("horizontal")
        pen_der_h = franja["penumbra_derecha"].get("horizontal")

        ancho_v = franja["anchura"].get("vertical")
        pen_izq_v = franja["penumbra_izquierda"].get("vertical")
        pen_der_v = franja["penumbra_derecha"].get("vertical")

        html.append(html_doble_columna(ancho_h, pen_izq_h, pen_der_h, ancho_v, pen_izq_v, pen_der_v, conversion))

        excesos = franja.get("excesos", [])
        html.append(f"""
        <div style="margin-top:8px; margin-bottom:12px; padding:6px; border:1px solid #ddd;">
        {html_excesos_por_franja(i, excesos, conversion)}
        </div>
        """)

    # En el bloque principal de generación de HTML:
    html.append("<b style='font-family:Arial, sans-serif;'>Verificación de alineación</b>")

        # Tabla con dos columnas para Inicial y Corregido
    html.append("""
    <table style='width:100%; border-spacing:10px;'>
    <tr>
    <td style='vertical-align:top; width:50%; font-family:Arial, sans-serif;border-left:10px'>
    <b>Cuadro Inicial (marcado en la placa)</b><br>
    """ +
    "<b>Dimensiones</b>" +
    diccionario_a_tabla(verificacion["verificacion_inicial"]["lados_mm"]) +
    "<b>Desviaciones</b>" +
    diccionario_a_tabla(verificacion["verificacion_inicial"]["alineacion_mm"]) +
    "<b>Alineación</b>" +
    estado_legible(verificacion["verificacion_inicial"]["estado"]) +
    "<b>Correcciones a los vértices:</b>" +
    diccionario_a_tabla(verificacion["correcciones"]) +"""
    </td>

    <td style='vertical-align:top; width:50%; font-family:Arial, sans-serif;'>
    <b>Cuadro Corregido con ángulos</b><br>
    """ +
    "<b>Dimensiones</b>" +
    diccionario_a_tabla(verificacion["verificacion_ideal"]["lados_mm"]) +
    "<b>Desviaciones</b>" +
    diccionario_a_tabla(verificacion["verificacion_ideal"]["alineacion_mm"]) +
    "<b>Alineación</b>" +
    estado_legible(verificacion["verificacion_ideal"]["estado"]) +

    "<b>Centro y dimensiones del cuadro corregido</b>" +
    diccionario_a_tabla({
        "Centro (x, y)": f"({verificacion['centro_corregido'][0]:.2f}, {verificacion['centro_corregido'][1]:.2f})",
        "Ancho": f"{verificacion['dimensiones']['ancho']:.2f}",
        "Alto": f"{verificacion['dimensiones']['alto']:.2f}"
    }) +

    "<b>Diferencias respecto al campo ideal</b>" +
    diccionario_a_tabla(verificacion["excesos_ideal"]) + """
    </td>
    </tr>
    </table>
    """)


    return "\n".join(html)

if __name__ == "__main__":
    # Ruta de la imagen que quieres analizar
    imagen_path = 'IMAGENES/campo_corto_cuadrado.png'

    # Llamada a la función modular
    resultados = analizar_cuadrado2(
        imagen_path=imagen_path,
        filtro=None,       # Puede ser "gauss", "mediana", "blur", o None
        mostrar=False      # Mostrar gráficas con matplotlib
    )
