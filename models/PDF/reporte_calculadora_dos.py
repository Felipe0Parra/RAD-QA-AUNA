import os
import pandas as pd
from PyQt5.QtWidgets import QFileDialog, QMessageBox
from models.PDF.pdf import generar_reporte_pdf
from models.PDF.PDFWindow import PdfViewer
from models.PDF.reportes import reporte
try:
    from utils import resource_path
except Exception:
    import importlib.util
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    utils_path = os.path.join(project_root, 'utils.py')
    if os.path.isfile(utils_path):
        spec = importlib.util.spec_from_file_location('utils', utils_path)
        utils = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(utils)
        resource_path = getattr(utils, 'resource_path')
    else:
        raise


# -----------------------------
# Adaptador: dict → DataFrame
# -----------------------------

# Etiquetas legibles para el reporte (trazabilidad P1, Fase K). El código
# crudo ("2000"/"rev1") es el que se persiste en la BD; aquí solo se traduce
# para mostrar, sin mutar el dict `datos` que también usa guardar_datos.
_ETIQUETAS_PROTOCOLO_TRS398 = {
    "2000": "TRS-398 (2000/2005)",
    "rev1": "TRS-398 Rev.1 (2024)",
}


def datos_a_dataframe(datos: dict) -> pd.DataFrame:
    # Z3 (PLAN_REPARACION_DIARIO_Y_ANULACION_05-08.md): "Numero_serie" guardaba
    # el id interno del combo de series (F1, 2026-07-10), no la serie física
    # grabada en la cámara -- el reporte imprimía ese id bajo la fila
    # "Numero_serie", presentándolo como si fuera la serie del equipo.
    # Se resuelve la serie REAL desde equipo_id (services/equipos_service.py)
    # -- correcto también para registros ya guardados, sin reescribir ningún
    # dato histórico (Numero_serie se queda como está en la BD, DA-02/DA-28).
    #
    # Q.4 (PLAN_EQUIPOS_BORRADO_Y_VIGENCIA_10-09.md SS4-bis): C1 (11-08,
    # PLAN_REPARACION_MENSUAL_Y_HALCYON_11-08.md) cambió lo que se GUARDA en
    # "Numero_serie" -- desde entonces ya es la serie real de la cámara, no
    # el id (Z3/F1 solo describía el estado ANTERIOR a C1). Este bloque
    # seguía sobrescribiendo la columna incondicionalmente desde el
    # catálogo, así que si el equipo ya no resolvía (DA-74, borrado real)
    # se borraba la fila entera -- tirando la serie correcta que C1 ya
    # había guardado. Ahora, sin resolución del catálogo, se usa la copia
    # guardada SIEMPRE que no sea el id crudo (formato anterior a C1: la
    # guarda por igualdad distingue las dos épocas sin columna de versión,
    # verificado en el plan que ninguna serie real del catálogo coincide
    # con ningún id existente). Solo se omite la fila cuando lo único
    # disponible es un id sin significado para el físico.
    datos = dict(datos)
    if "Numero_serie" in datos:
        equipo_id = datos.get("equipo_id")
        numero_serie = datos.get("Numero_serie")
        serie_real = None
        if equipo_id:
            from services.equipos_service import EquiposService
            equipo = EquiposService.obtener_por_id(equipo_id)
            if equipo:
                serie_real = equipo.get("serie")
        if serie_real:
            datos["Numero_serie"] = serie_real
        elif numero_serie and str(numero_serie) != str(equipo_id):
            datos["Numero_serie"] = numero_serie
        else:
            del datos["Numero_serie"]

    valores = [
        _ETIQUETAS_PROTOCOLO_TRS398.get(v, v) if k == "protocolo_trs398" else v
        for k, v in datos.items()
    ]
    return pd.DataFrame({
        "": list(datos.keys()),
        "Evaluación": [None] * len(datos),
        "Valores": valores
    })


# -----------------------------------------
# Evaluación automática por umbrales
# -----------------------------------------
def aplicar_umbrales(df: pd.DataFrame, umbrales: dict):
    for key, lim in umbrales.items():
        mask = df[""] == key
        if not mask.any():
            continue
        try:
            val = float(df.loc[mask, "Valores"].values[0])
            if val > lim:
                df.loc[mask, "Evaluación"] = "Fuera del umbral"
            else:
                df.loc[mask, "Evaluación"] = "Dentro del umbral"
        except:
            df.loc[mask, "Evaluación"] = "No aplica"


# -------------------------------------------------
# Función principal para tu cálculo de calibración
# -------------------------------------------------
def generar_reporte_calibracion(
    parent,
    datos: dict,
    maquina: str = "iX",
    tipo_reporte: str = "Calibración Dosimétrica",
    user: str = "Operador",
    role: str = "Físico Médico",
    umbrales: dict = None,
    firma_path: str = None,
    guardar_como: bool = False
):
    """
    parent: ventana que llama (self)
    datos: diccionario de tu cálculo
    """

    # 1) Convertir a DataFrame
    df = datos_a_dataframe(datos)

    # 2) Evaluar con umbrales si existen
    if umbrales:
        aplicar_umbrales(df, umbrales)

    # 3) Logo
    ICONO = resource_path('resources/icons/iconoPDF.png')

    # 4) Generar PDF en memoria
    buffer = generar_reporte_pdf(
        df=df,
        fecha=datos.get("Fecha", ""),
        user=" ",
        tipo_reporte=tipo_reporte,
        maquina=maquina,
        id_maquina=datos.get("equipo_id", ""),
        logo_path=ICONO,
        firma=firma_path,
        role=role,
        temp=True
    )

    # 5) Normalizar bytes
    if isinstance(buffer, bytes):
        pdf_bytes = buffer
    elif hasattr(buffer, 'getvalue'):
        pdf_bytes = buffer.getvalue()
    elif hasattr(buffer, 'data'):
        pdf_bytes = bytes(buffer.data())
    else:
        raise TypeError("Buffer type not supported")

    # 6) Vista previa
    visor = PdfViewer(
        pdf_data=pdf_bytes,
        fecha=datos.get("Fecha", ""),
        maquina=maquina,
        tipo_reporte=tipo_reporte
    )
    visor.show()

    # 7) Guardar si el usuario quiere
    if guardar_como:
        file_name, _ = QFileDialog.getSaveFileName(
            parent,
            "Guardar PDF",
            f"Calibracion_{maquina}_{datos.get('Fecha','')}.pdf",
            "Archivos PDF (*.pdf)"
        )
        if file_name:
            try:
                with open(file_name, "wb") as f:
                    f.write(pdf_bytes)
            except Exception as e:
                QMessageBox.critical(parent, "Error", f"No se pudo guardar el PDF:\n{e}")
