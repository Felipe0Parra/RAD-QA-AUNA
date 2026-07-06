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
def datos_a_dataframe(datos: dict) -> pd.DataFrame:
    return pd.DataFrame({
        "": list(datos.keys()),
        "Evaluación": [None] * len(datos),
        "Valores": list(datos.values())
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
