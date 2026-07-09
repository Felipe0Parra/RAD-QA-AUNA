"""Lector de las hojas de cálculo TRS-398 del OIEA (IAEA) — Fase D3.

Reemplaza la lectura vía win32com/Excel de `DialogCalculadoraDosis.import_mcc`
por un lector multiplataforma (Linux y Windows) que no depende de tener Excel
instalado ni deja procesos EXCEL.EXE colgados.

Las plantillas oficiales de TRS-398 son un formato FIJO: la hoja de interés se
llama 'Sheet' y cada magnitud vive siempre en la misma celda (verificado
idéntico entre las variantes 6 MV, 6 MV FFF Halcyon y 6 MV 600). Por eso el
mapeo es por coordenada de celda, mucho más robusto que buscar por etiqueta
(el método anterior fallaba con etiquetas duplicadas en la plantilla).

Los `.xls` (BIFF8) vienen cifrados con la contraseña por defecto de Excel
('VelvetSweatshop'): Excel los abre sin pedir clave, pero las librerías chocan
con el cifrado. Se descifran con msoffcrypto antes de leer con xlrd. Los
`.xlsx`/`.xlsm` se leen con openpyxl (data_only) — ojo: en la variante .xlsm
kQ y Dzref quedan como '#NAME?' en caché porque dependen de macros de Excel;
se devuelven como None y quien compare debe tolerarlo.
"""
import io
import os
import re

# Contraseña por defecto con la que Excel "cifra" libros sin clave de usuario.
_PASSWORD_POR_DEFECTO = "VelvetSweatshop"

# Nombre de la hoja de trabajo dentro de la plantilla OIEA.
_HOJA = "Sheet"

# Mapeo celda -> clave lógica. Dos grupos:
#   entradas crudas (para recalcular con el motor de la app) y
#   valores ya calculados por el Excel (para la tabla de comparación).
CELDAS_ENTRADAS = {
    "acelerador":          "D6",
    "potencial_nominal":   "I7",
    "tpr2010":             "I8",
    "tamano_campo":        "E10",
    "zref":                "E11",
    "serie_camara":        "H14",
    "factor_calibracion":  "G19",   # N_D,w
    "profundidad_calib":   "H21",
    "P0":                  "C25",
    "T0":                  "F25",
    "humedad_calib":       "I25",
    "V1_polarizante":      "D27",
    "P_clinica":           "C41",
    "T_clinica":           "F41",
    "humedad_clinica":     "I41",
    "lectura_V1":          "H37",   # dosímetro sin corregir a V1
    "unidades_monitor":    "H38",
    "M1_ratio":            "H39",   # lectura/UM
    "kelec":               "F46",
    "Mplus":               "F48",
    "Mminus":              "J48",
    "V1_recomb":           "F56",
    "V2_recomb":           "I56",
    "M1_recomb":           "F57",
    "M2_recomb":           "I57",
    "a0":                  "E60",
    "a1":                  "G60",
    "a2":                  "I60",
    "zmax":                "H76",
    "PDD_zref":            "H80",
}

CELDAS_CALCULADAS = {
    "ktp":           "I43",
    "kpol":          "I51",
    "ks":            "I62",
    "Mq":            "G67",   # lectura corregida a V1
    "kQ":            "G70",   # factor de calidad del haz
    "Dzref":         "G73",   # dosis en zref (Gy/MU)
    "dosis_maxima":  "H83",   # dosis en zmax, montaje SSD (Gy/MU)
}


def _ref_a_indices(ref):
    """'I43' -> (fila0, col0) en base 0."""
    m = re.match(r"([A-Z]+)(\d+)", ref)
    col = 0
    for ch in m.group(1):
        col = col * 26 + (ord(ch) - 64)
    return int(m.group(2)) - 1, col - 1


def _normalizar(valor):
    """Limpia un valor de celda: '#NAME?'/errores -> None; recorta strings."""
    if valor is None:
        return None
    if isinstance(valor, str):
        v = valor.strip()
        if v == "" or v.startswith("#"):   # #NAME?, #REF!, #VALUE!...
            return None
        return v
    return valor


class _LectorCeldas:
    """Adapta xlrd u openpyxl a una interfaz común: obtener(ref) -> valor."""

    def __init__(self, fn_celda):
        self._fn = fn_celda

    def obtener(self, ref):
        fila, col = _ref_a_indices(ref)
        try:
            return _normalizar(self._fn(fila, col))
        except IndexError:
            return None


def _abrir_xls(ruta):
    import msoffcrypto
    import xlrd

    with open(ruta, "rb") as f:
        off = msoffcrypto.OfficeFile(f)
        if off.is_encrypted():
            off.load_key(password=_PASSWORD_POR_DEFECTO)
            buffer = io.BytesIO()
            off.decrypt(buffer)
            contenido = buffer.getvalue()
        else:
            f.seek(0)
            contenido = f.read()

    libro = xlrd.open_workbook(file_contents=contenido)
    hoja = libro.sheet_by_name(_HOJA)
    return _LectorCeldas(lambda fila, col: hoja.cell_value(fila, col))


def _abrir_xlsx(ruta):
    import openpyxl

    libro = openpyxl.load_workbook(ruta, data_only=True, read_only=True)
    hoja = libro[_HOJA]

    def celda(fila, col):
        # openpyxl es base 1; devuelve el valor cacheado (data_only)
        return hoja.cell(row=fila + 1, column=col + 1).value

    return _LectorCeldas(celda)


def leer_trs398(ruta):
    """Lee una hoja TRS-398 (.xls/.xlsx/.xlsm) y devuelve un dict:

        {
            "archivo": <nombre>,
            "entradas":   {clave: valor, ...},   # datos crudos
            "calculados": {clave: valor, ...},   # resultados del Excel
        }

    Lanza FileNotFoundError si la ruta no existe y ValueError si la extensión
    no es reconocida. Celdas vacías o con error de fórmula devuelven None.
    """
    if not os.path.exists(ruta):
        raise FileNotFoundError(ruta)

    ext = os.path.splitext(ruta)[1].lower()
    if ext == ".xls":
        lector = _abrir_xls(ruta)
    elif ext in (".xlsx", ".xlsm"):
        lector = _abrir_xlsx(ruta)
    else:
        raise ValueError(f"Formato no soportado: {ext} (use .xls, .xlsx o .xlsm)")

    return {
        "archivo": os.path.basename(ruta),
        "entradas": {k: lector.obtener(ref) for k, ref in CELDAS_ENTRADAS.items()},
        "calculados": {k: lector.obtener(ref) for k, ref in CELDAS_CALCULADAS.items()},
    }


# Etiquetas legibles para la tabla de comparación.
ETIQUETAS = {
    "ktp":          "kTP (presión-temperatura)",
    "kpol":         "kpol (polaridad)",
    "ks":           "ks (recombinación)",
    "Mq":           "Mq (lectura corregida)",
    "kQ":           "kQ,Q0 (calidad del haz)",
    "Dzref":        "D(zref) [Gy/UM]",
    "dosis_maxima": "D(zmax) [Gy/UM]",
}


def _recalcular_con_app(entradas):
    """Recalcula las magnitudes con el MISMO motor que usa la calculadora
    (services.dosis_service) a partir de las entradas crudas del Excel.

    Devuelve {clave: valor|None}. Un valor None significa "no recalculable"
    (falta un dato de entrada, o kQ sin modelo de cámara conocido).
    """
    from services.dosis_service import DosisService

    e = entradas
    r = {}

    def num(*claves):
        vals = []
        for c in claves:
            v = e.get(c)
            if v is None or v == "":
                return None
            try:
                vals.append(float(v))
            except (TypeError, ValueError):
                return None
        return vals

    tp = num("T_clinica", "P_clinica", "T0", "P0")
    r["ktp"] = DosisService.factor_tp(*tp) if tp else None

    pol = num("Mplus", "Mminus")
    r["kpol"] = DosisService.factor_k_polaridad(*pol) if pol else None

    rec = num("M1_recomb", "M2_recomb", "a0", "a1", "a2")
    if rec:
        m1, m2, a0, a1, a2 = rec
        r["ks"] = DosisService.Ks_factor(a0, a1, a2, DosisService.cociente_M1M2(m1, m2))
    else:
        r["ks"] = None

    coc = num("lectura_V1", "unidades_monitor")
    cociente = DosisService.cociente_ldv1_um(*coc) if coc else None
    if cociente is not None and None not in (r["ktp"], r["kpol"], r["ks"]):
        r["Mq"] = DosisService.calcular_mq_fot(cociente, r["ktp"], r["kpol"], r["ks"])
    else:
        r["Mq"] = None

    # kQ requiere el modelo de cámara (la clave que resuelve KQ_TPR_TABLE).
    # Pineado a protocolo "2000" A PROPÓSITO (Fase K): las hojas TRS-398 oficiales
    # que el físico usa hoy están calculadas con la TRS-398 original (2000), no
    # con Rev.1 — comparar contra la tabla equivocada produciría rojos engañosos
    # en "Comparar con Excel TRS-398". Si algún día llegan hojas Rev.1, este
    # pineado debe revisarse (p. ej. leyendo el protocolo desde la propia hoja).
    modelo = e.get("_modelo_camara")
    tpr = num("tpr2010")
    if modelo and tpr and DosisService.camara_tiene_kq(modelo, protocolo="2000"):
        r["kQ"] = DosisService.interpolar_kq0(modelo, tpr[0], protocolo="2000")
    else:
        r["kQ"] = None

    cal = num("factor_calibracion")
    if cal and None not in (r["Mq"], r["kQ"]):
        r["Dzref"] = DosisService.calcular_dwref(cal[0], r["Mq"], r["kQ"])
    else:
        r["Dzref"] = None

    pdd = num("PDD_zref")
    if r["Dzref"] is not None and pdd:
        r["dosis_maxima"] = DosisService.dwqzmax_calc(r["Dzref"], pdd[0])
    else:
        r["dosis_maxima"] = None

    return r


def comparar_trs398(datos_excel, modelo_camara=None, tolerancia_rel=0.001):
    """Compara los valores calculados por la app vs los del Excel.

    Args:
        datos_excel: dict devuelto por leer_trs398().
        modelo_camara: modelo de cámara seleccionado en la calculadora
            (necesario para recalcular kQ y, por lo tanto, D(zref)/D(zmax)).
        tolerancia_rel: tolerancia relativa; el redondeo interno de la app
            (4-6 decimales) frente a la precisión completa del Excel produce
            diferencias diminutas — 0.1 % las cubre con holgura.

    Returns:
        Lista de filas dict: magnitud, etiqueta, app, excel, diferencia_rel,
        comparable (ambos valores presentes) y ok (dentro de tolerancia).
    """
    entradas = dict(datos_excel["entradas"])
    entradas["_modelo_camara"] = modelo_camara
    app = _recalcular_con_app(entradas)
    excel = datos_excel["calculados"]

    filas = []
    for clave in CELDAS_CALCULADAS:
        va, vx = app.get(clave), excel.get(clave)
        comparable = va is not None and vx is not None
        dif = ok = None
        if comparable:
            vx_f = float(vx)
            dif = abs(va - vx_f) / abs(vx_f) if vx_f != 0 else abs(va - vx_f)
            ok = dif <= tolerancia_rel
        filas.append({
            "magnitud": clave,
            "etiqueta": ETIQUETAS[clave],
            "app": va,
            "excel": float(vx) if vx is not None else None,
            "diferencia_rel": dif,
            "comparable": comparable,
            "ok": ok,
        })
    return filas
