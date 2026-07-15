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

# Mapeo de la hoja de ELECTRONES (auditoría 2026-07-10 contra las 53 hojas de
# electrones del corpus 2024: layout FIJO, igual de estable que el de
# fotones, verificado en las 4 energías iX 6/9/12/15 MeV). Mismas claves
# lógicas de CELDAS_CALCULADAS (ktp/kpol/ks/Mq/kQ/Dzref/dosis_maxima) para que
# comparar_trs398/ETIQUETAS no necesiten duplicarse por tipo de haz.
#
# NO se mapea "zref" (I11, calidad R50,w derivada) ni r50w: 10/53 hojas del
# corpus lo tienen sobreescrito a mano por el físico (p. ej. 1.4 en vez del
# 1.33 calculado) -- comparar esa celda produciría un rojo engañoso por un
# uso legítimo del formato, no un error de cálculo.
CELDAS_ENTRADAS_ELECTRONES = {
    "acelerador":          "D6",
    "energia_nominal":     "I7",
    "r50_medido":          "I8",
    "serie_camara":        "H14",
    "factor_calibracion":  "G19",   # N_D,w
    "profundidad_calib":   "H20",
    "P0":                  "C23",
    "T0":                  "F23",
    "humedad_calib":       "I23",
    "V1_polarizante":      "D25",
    "P_clinica":           "C43",
    "T_clinica":           "F43",
    "humedad_clinica":     "I43",
    "lectura_V1":          "H40",
    "unidades_monitor":    "H41",
    "M1_ratio":            "H42",
    "kelec":               "F48",
    "Mplus":               "F50",
    "Mminus":              "J50",
    "V1_recomb":           "F57",
    "V2_recomb":           "I57",
    "M1_recomb":           "F58",
    "M2_recomb":           "I58",
    "a0":                  "E61",
    "a1":                  "G61",
    "a2":                  "I61",
    "zmax":                "H83",
    "PDD_zref":            "H86",
}

CELDAS_CALCULADAS_ELECTRONES = {
    "ktp":           "I45",
    "kpol":          "I53",
    "ks":            "I63",
    "Mq":            "G68",   # lectura corregida a V1
    "kQ":            "I72",   # Table 18/20 (Q0=Co-60), a la calidad R50,w
    "Dzref":         "G80",   # dosis en zref (Gy/MU)
    "dosis_maxima":  "H89",   # dosis en zmax, montaje SSD (Gy/MU)
    # H3.2 (auditoría 2026-07-14): celdas D11/I11 verificadas contra el
    # corpus real (varias energías/meses, valor exacto = 1.029*R50-0.06 y
    # 0.6*Q-0.1). Q(R50) casi nunca se sobreescribe (1/73 hojas, con una
    # entrada rota, no deliberada); zref SÍ tiene un patrón sistemático:
    # 15/73 hojas -- TODAS de 6 MeV, en prácticamente todos los meses de
    # 2024 -- traen 1.4 fijo en vez de la fórmula (convención clínica de
    # esta institución para 6 MeV). El comparador las muestra igual
    # (honestidad > silencio, mismo principio que H3.1); la UI avisa que
    # una diferencia aquí no es necesariamente un error.
    "beam_quality_r50": "D11",
    "zref":             "I11",
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


def _detectar_tipo_haz(lector):
    """Lee A2 ('...in a high-energy photon-beam' / '...in an electron-beam')
    para elegir el mapa de celdas correcto. Ambos layouts comparten fila/hoja
    pero difieren en las filas de abajo (electrones tiene 2 filas más de
    encabezado en la sección 1) -- por eso el mapeo por coordenada NO es
    intercambiable entre haces, a diferencia de entre variantes del mismo haz
    (6 MV / 6 MV FFF / 600, verificado idéntico en D3).

    Devuelve "fotones" (default si no se reconoce -- preserva el
    comportamiento pre-E5, cuando solo existía el mapa de fotones) o
    "electrones".
    """
    valor = lector.obtener("A2")
    if isinstance(valor, str):
        v = valor.lower()
        if "electron" in v:
            return "electrones"
        if "photon" in v:
            return "fotones"
    return "fotones"


def leer_trs398(ruta):
    """Lee una hoja TRS-398 (.xls/.xlsx/.xlsm) y devuelve un dict:

        {
            "archivo": <nombre>,
            "tipo_haz": "fotones" | "electrones",
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

    tipo_haz = _detectar_tipo_haz(lector)
    if tipo_haz == "electrones":
        mapa_entradas, mapa_calculadas = CELDAS_ENTRADAS_ELECTRONES, CELDAS_CALCULADAS_ELECTRONES
    else:
        mapa_entradas, mapa_calculadas = CELDAS_ENTRADAS, CELDAS_CALCULADAS

    return {
        "archivo": os.path.basename(ruta),
        "tipo_haz": tipo_haz,
        "entradas": {k: lector.obtener(ref) for k, ref in mapa_entradas.items()},
        "calculados": {k: lector.obtener(ref) for k, ref in mapa_calculadas.items()},
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
    # Solo aplican a electrones (R50 no es un concepto de haces de fotones,
    # que usan TPR20,10) -- explícito en el propio texto porque ETIQUETAS es
    # un dict compartido; comparar_trs398 ya despacha por tipo_haz y nunca
    # itera estas 2 claves para una hoja de fotones (CELDAS_CALCULADAS no las
    # tiene), pero el texto no debe depender de eso para ser correcto.
    "beam_quality_r50": "Q(R50) (calidad de haz, electrones)",
    "zref":             "zref (profundidad de referencia, electrones)",
}


def _recalcular_con_app(entradas, tipo_haz="fotones"):
    """Recalcula las magnitudes con el MISMO motor que usa la calculadora
    (services.dosis_service) a partir de las entradas crudas del Excel.

    Devuelve {clave: valor|None}. Un valor None significa "no recalculable"
    (falta un dato de entrada, o kQ sin modelo de cámara conocido). ktp/kpol/
    ks son física genérica idéntica para ambos haces; Mq/kQ/Dzref/dosis_maxima
    bifurcan por tipo_haz (E5, auditoría 2026-07-10).
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
    modelo = e.get("_modelo_camara")
    cal = num("factor_calibracion")
    pdd = num("PDD_zref")

    if tipo_haz == "electrones":
        if cociente is not None and None not in (r["ktp"], r["kpol"], r["ks"]):
            r["Mq"] = DosisService.calcular_mq_elec(cociente, r["ktp"], r["kpol"], r["ks"])
        else:
            r["Mq"] = None

        # kQ de electrones se interpola a la CALIDAD R50,w (no al R50 medido
        # crudo -- mismo fix de E2/E3), pineado a protocolo "2000" por la
        # misma razón que fotones (ver más abajo).
        r50m = num("r50_medido")
        r50w = DosisService.r50_quality(r50m[0]) if r50m else None
        # H3.2: Q(R50) y zref no dependen de la cámara (a diferencia de kQ) --
        # se calculan siempre que haya R50 medido, con o sin modelo elegido.
        r["beam_quality_r50"] = r50w
        r["zref"] = DosisService.r50_depth(r50w) if r50w is not None else None
        if (modelo and r50w is not None
                and DosisService.camara_tiene_kq_electrones(modelo, protocolo="2000")):
            r["kQ"] = DosisService.interpolar_r50(modelo, r50w, protocolo="2000")
        else:
            r["kQ"] = None
    else:
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
        tpr = num("tpr2010")
        if modelo and tpr and DosisService.camara_tiene_kq(modelo, protocolo="2000"):
            r["kQ"] = DosisService.interpolar_kq0(modelo, tpr[0], protocolo="2000")
        else:
            r["kQ"] = None

    if cal and None not in (r["Mq"], r["kQ"]):
        r["Dzref"] = DosisService.calcular_dwref(cal[0], r["Mq"], r["kQ"])
    else:
        r["Dzref"] = None

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
    tipo_haz = datos_excel.get("tipo_haz") or "fotones"
    app = _recalcular_con_app(entradas, tipo_haz=tipo_haz)
    excel = datos_excel["calculados"]

    # Mismas 7 claves lógicas en ambos mapas (E5) -- ETIQUETAS no necesita
    # bifurcar por tipo_haz.
    claves = CELDAS_CALCULADAS_ELECTRONES if tipo_haz == "electrones" else CELDAS_CALCULADAS
    filas = []
    for clave in claves:
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
