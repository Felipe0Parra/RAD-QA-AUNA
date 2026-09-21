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


# ---------------------------------------------------------------------------
# Detección con pylinac
# ---------------------------------------------------------------------------

def detectar_modulos_pylinac(ruta_dicom: str) -> dict[str, ResultadoModulo]:
    from pylinac import CatPhan504

    from analisisImagenes.catphan.serie import leer_serie

    resultados = {}

    try:
        # A.2 (PLAN_CATPHAN_AUTOMATICO_POR_EQUIPO_18-09.md): se pasa la
        # LISTA de rutas de la serie elegida por `leer_serie` (la misma
        # función que ordena el volumen del visor, A.1), no la carpeta
        # cruda -- así el índice que devuelve pylinac se refiere exactamente
        # a los mismos archivos que `DicomVolume.cortes`, incluso si la
        # carpeta tuviera una segunda serie o un RTSTRUCT (D-06).
        rutas = [corte.ruta for corte in leer_serie(ruta_dicom).cortes]
        ct = CatPhan504(rutas)
        ct.analyze()

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

    modulo_a_attr = {
        "CTP404": "ctp404",
        "CTP486": "ctp486",
        "CTP515": "ctp515",
        "CTP528": "ctp528",
    }

    for nombre, attr in modulo_a_attr.items():
        modulo_pylinac = getattr(ct, attr, None)
        if modulo_pylinac is None:
            resultados[nombre] = ResultadoModulo(
                nombre=nombre,
                descripcion=DESCRIPCION_MODULOS[nombre],
                idx_corte=None,
                confiable=False,
                error="Módulo no encontrado en el scan.",
            )
            continue

        try:
            # D-02: `slice_num` ya es 0-based (solo los TÍTULOS de las
            # figuras de pylinac suman 1) -- no se le resta 1 aquí.
            idx = int(modulo_pylinac.slice_num)
            resultados[nombre] = ResultadoModulo(
                nombre=nombre,
                descripcion=DESCRIPCION_MODULOS[nombre],
                idx_corte=idx,
                confiable=True,
            )
        except Exception as e:
            resultados[nombre] = ResultadoModulo(
                nombre=nombre,
                descripcion=DESCRIPCION_MODULOS[nombre],
                idx_corte=None,
                confiable=False,
                error=str(e),
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
