"""
slice_matcher.py

Detecta los cortes de cada módulo del CatPhan 504 con pylinac y muestra
un popup informativo con los números de corte sugeridos.

El popup NO realiza ningún análisis ni dispara ninguna acción.
Solo informa al usuario qué corte corresponde a cada módulo.
El dict retornado por detectar_y_resolver_modulos es lo que el código
principal debe usar para continuar.

Integración mínima:
    from slice_matcher import detectar_y_resolver_modulos

    cortes = detectar_y_resolver_modulos(
        ruta_dicom=self.ruta_carpeta,
        parent_widget=self
    )
    # cortes = {"CTP404": 234, "CTP486": 126, "CTP515": 184, "CTP528": 284}
    # A partir de aquí el código principal decide qué hacer con esos índices.

Dependencias:
    pip install pylinac pyqt5
"""

import os
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Optional
from PyQt5.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QFrame
    )
from PyQt5.QtCore import Qt

DESCRIPCION_MODULOS = {
    "CTP404": "Espesor de corte / linealidad",
    "CTP486": "Uniformidad de campo",
    "CTP515": "Resolución de contraste",
    "CTP528": "Resolución espacial",
}


@dataclass
class ResultadoModulo:
    nombre: str
    descripcion: str
    idx_corte: Optional[int]
    confiable: bool
    error: Optional[str] = None
    # D.1 (23-09, PLAN_HANDOFF_IMAGENES_22-09.md): orientación y giro que
    # midió el motor para ESTA serie (el fantoma es rígido -- los cuatro
    # módulos comparten el mismo valor). "normal"/0.0 si no se pudo medir
    # (mismo comportamiento que antes de D.1).
    orientacion: str = "normal"
    roll_deg: float = 0.0


# ---------------------------------------------------------------------------
# Detección con pylinac
# ---------------------------------------------------------------------------

def detectar_modulos_pylinac(ruta_dicom: str) -> dict[str, ResultadoModulo]:
    # D.1 (23-09): antes corría CatPhan504 puro (sin volteo ni límite de
    # homogeneidad por equipo) -- por eso fallaba con el iX y con el
    # fantoma invertido. Pasa a usar el motor ya validado (B.1/B.2, plan
    # del 18-09), que además entrega orientación y giro.
    from analisisImagenes.catphan import motor
    from analisisImagenes.catphan.perfiles import PERFILES
    from analisisImagenes.catphan.serie import identificar_equipo, leer_serie

    resultados = {}

    try:
        serie = leer_serie(ruta_dicom)
        # A.2 (PLAN_CATPHAN_AUTOMATICO_POR_EQUIPO_18-09.md): se usa la
        # LISTA de rutas de la serie elegida por `leer_serie` (la misma
        # función que ordena el volumen del visor, A.1), no la carpeta
        # cruda -- así el índice que devuelve pylinac se refiere exactamente
        # a los mismos archivos que `DicomVolume.cortes`, incluso si la
        # carpeta tuviera una segunda serie o un RTSTRUCT (D-06).
        equipo, _advertencia = identificar_equipo(serie)
        # Equipo no identificable (aún no se cargó A.2/A.3, o serie de un
        # equipo nuevo): perfil neutro -- D.1 no depende de saber de qué
        # equipo es la serie para detectar cortes, orientación y giro.
        perfil = PERFILES.get(equipo) if equipo else SimpleNamespace(
            limite_variacion_hu=None, nombre=equipo, visibility_threshold=None,
        )
        resultado = motor.analizar(serie, perfil)
    except Exception as e:
        print(f"⚠️  pylinac no pudo analizar el volumen: {e}")
        for nombre in DESCRIPCION_MODULOS:
            resultados[nombre] = ResultadoModulo(
                nombre=nombre,
                descripcion=DESCRIPCION_MODULOS[nombre],
                idx_corte=None,
                confiable=False,
                error=str(e),
            )
        return resultados

    n_cortes = len(serie.cortes)
    for nombre in DESCRIPCION_MODULOS:
        modulo_res = resultado.modulos.get(nombre)
        if modulo_res is None:
            resultados[nombre] = ResultadoModulo(
                nombre=nombre,
                descripcion=DESCRIPCION_MODULOS[nombre],
                idx_corte=None,
                confiable=False,
                error="Módulo no encontrado en el scan.",
                orientacion=resultado.orientacion,
                roll_deg=resultado.roll_deg,
            )
            continue

        try:
            # D-02: `corte_indice` ya es 0-based (solo los TÍTULOS de las
            # figuras de pylinac suman 1) -- no se le resta 1 aquí. Es el
            # índice en el marco que analizó el motor (volteado si la
            # serie está invertida); la app siempre muestra el volumen SIN
            # voltear, así que se traduce al índice físico real (D-01/D.1:
            # dos marcos de referencia).
            idx = int(modulo_res.corte_indice)
            if resultado.orientacion == "invertido":
                idx = n_cortes - 1 - idx
            resultados[nombre] = ResultadoModulo(
                nombre=nombre,
                descripcion=DESCRIPCION_MODULOS[nombre],
                idx_corte=idx,
                confiable=True,
                orientacion=resultado.orientacion,
                roll_deg=resultado.roll_deg,
            )
        except Exception as e:
            resultados[nombre] = ResultadoModulo(
                nombre=nombre,
                descripcion=DESCRIPCION_MODULOS[nombre],
                idx_corte=None,
                confiable=False,
                error=str(e),
                orientacion=resultado.orientacion,
                roll_deg=resultado.roll_deg,
            )

    return resultados


# ---------------------------------------------------------------------------
# Popup informativo — solo muestra números de corte, no hace nada más
# ---------------------------------------------------------------------------





# ---------------------------------------------------------------------------
# Función principal de integración
# ---------------------------------------------------------------------------

def detectar_y_resolver_modulos(
    ruta_dicom: str,
    parent_widget=None,
    callback_progreso=None,
) -> dict[str, int]:
    """
    Detecta módulos con pylinac, muestra el popup informativo, y retorna
    el dict con los índices de corte para que el código principal los use.

    El popup es solo informativo — no bloquea ni modifica los resultados.

    Args:
        ruta_dicom:        Ruta a la carpeta con archivos .dcm
        parent_widget:     Widget PyQt5 padre para el popup.
        callback_progreso: fn(str, int) opcional para barra de progreso.

    Returns:
        { "CTP404": 233, "CTP486": 125, ... } — índices 0-based.
        Solo incluye módulos que pylinac detectó con éxito.
    """
    if callback_progreso:
        callback_progreso("Analizando con pylinac...", 0)

    print("\n⟳  Detectando módulos con pylinac...")
    resultados = detectar_modulos_pylinac(ruta_dicom)

    if callback_progreso:
        callback_progreso("Detección completa", 90)

    # Mostrar popup si hay un widget padre disponible
    if parent_widget is not None:
        mostrar_popup_cortes(resultados, parent_widget=parent_widget)

    if callback_progreso:
        callback_progreso("completo", 100)

    # Retornar solo los módulos detectados con éxito
    cortes = {
        nombre: resultado.idx_corte
        for nombre, resultado in resultados.items()
        if resultado.confiable and resultado.idx_corte is not None
    }

    print(f"\n✓  Módulos detectados: {list(cortes.keys())}")
    for nombre, idx in cortes.items():
        print(f"   {nombre:10s} → corte {idx + 1:4d}")

    return resultados, cortes





# ---------------------------------------------------------------------------
# CLI de prueba
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    RUTA_DICOM = "ruta/a/tu/carpeta/dicom"

    if not os.path.isdir(RUTA_DICOM):
        print("Edita RUTA_DICOM antes de correr el script.")
        sys.exit(1)

    cortes = detectar_y_resolver_modulos(ruta_dicom=RUTA_DICOM)

    print("\nCortes detectados:")
    for modulo, idx in cortes.items():
        print(f"  {modulo:10s} → corte {idx + 1:4d}")
