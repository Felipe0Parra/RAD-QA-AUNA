"""Lector de archivos .mcc (formato CC-Export de PTW BeamScan/MEPHYSTO).

Reescrito en Fase D4.1a (auditoria 2026-07-10, PLAN_FASE_K_D4.md Seccion 3).
La version anterior asumia exactamente 3 scans por archivo en orden fijo
(PDD, INPLANE, CROSSPLANE) y llamaba a `pymcc.readmcc.read_file` -- un modulo
que nunca se importa en el archivo (NameError garantizado en cuanto se
invocara `pylinac_analysis`). El corpus real (~/Documents/Archivos_UseApp/
Archivos QA/) muestra dos patrones que ese diseno no soporta:
  - Un mismo .mcc puede traer 1, 2 o 3 scans (un CRIN de electrones no tiene
    PDD; algunas energias reparten PDD y CRIN en archivos separados).
  - Una energia puede repetirse el mismo mes por una repeticion/redo: ej.
    IX/Electrones/Febrero trae "E06 ... PDDCRIN ... 11'50'15.mcc" (PDD
    11:45, INPLANE 11:46, CROSSPLANE 11:48) y ademas "E06 ... PDD ...
    11'57'56.mcc" (un PDD repetido a las 11:56, sin CRIN). El PDD "bueno"
    para 6mev es el mas reciente (11:56), pero INPLANE/CROSSPLANE solo
    existen en el primer archivo -- por eso la agregacion en agregar_carpeta
    se hace por (energia, curve_type), nunca por archivo completo.

Por eso cada scan se identifica por su propio campo SCAN_CURVETYPE (nunca
por indice de aparicion ni por el nombre de archivo).
"""
from __future__ import annotations

import glob
import os
from dataclasses import dataclass
from datetime import datetime

CURVE_TYPES = ("PDD", "INPLANE_PROFILE", "CROSSPLANE_PROFILE")


class ErrorLecturaMCC(Exception):
    """Un archivo .mcc no se pudo parsear (formato inesperado/incompleto)."""


@dataclass
class EscaneoMCC:
    """Un solo bloque BEGIN_SCAN..END_SCAN de un archivo .mcc.

    col2/col3 son las columnas 2 y 3 crudas de BEGIN_DATA tal cual las
    reporta el software PTW (columna 1 = posicion/profundidad en mm). Cual
    de las dos es la dosis corregida final se resuelve en D4.1b: ese es el
    paso de descubrimiento empirico contra dosimetriaMen, no este lector.
    """
    curve_type: str
    meas_date: datetime
    energia: str
    modalidad: str
    posiciones: list
    col2: list
    col3: list
    archivo: str


def normalizar_energia(energy, radiation):
    """Misma convencion que ENERGIAS en ix_mensual.py/seiscientos_mensual.py."""
    if energy is None or radiation is None:
        raise ValueError("No se pudo detectar energia o tipo de radiacion")
    energy_int = int(round(float(energy)))
    if radiation == "X":
        return f"{energy_int}mv"
    elif radiation == "EL":
        return f"{energy_int}mev"
    raise ValueError(f"Tipo de radiacion desconocido: {radiation}")


def _parsear_fecha(valor):
    # Formato observado en el corpus real: "28-Feb-2026 11:19:44"
    return datetime.strptime(valor.strip(), "%d-%b-%Y %H:%M:%S")


def leer_mcc(ruta_archivo):
    """Parsea un .mcc y devuelve la lista de EscaneoMCC que contiene (1 a 3,
    segun cuantos BEGIN_SCAN traiga). No asume cuantos scans hay ni en que
    orden vienen, ni que MODALITY/ENERGY sean identicos entre scans.
    """
    escaneos = []
    campos = {}
    filas = []
    en_scan = False
    en_datos = False

    def cerrar_scan_actual():
        curve_type = campos.get("SCAN_CURVETYPE")
        energy = campos.get("ENERGY")
        modality = campos.get("MODALITY")
        meas_date = campos.get("MEAS_DATE")
        if not (curve_type and energy and modality and meas_date):
            raise ErrorLecturaMCC(
                f"{ruta_archivo}: scan sin SCAN_CURVETYPE/ENERGY/MODALITY/"
                "MEAS_DATE (archivo truncado o formato inesperado)")
        if curve_type not in CURVE_TYPES:
            raise ErrorLecturaMCC(
                f"{ruta_archivo}: SCAN_CURVETYPE desconocido '{curve_type}'")
        posiciones, col2, col3 = [], [], []
        for fila in filas:
            partes = fila.split()
            if len(partes) != 3:
                continue
            p, a, b = partes
            posiciones.append(float(p))
            col2.append(float(a))
            col3.append(float(b))
        escaneos.append(EscaneoMCC(
            curve_type=curve_type,
            meas_date=_parsear_fecha(meas_date),
            energia=normalizar_energia(energy, modality.strip().upper()),
            modalidad=modality.strip().upper(),
            posiciones=posiciones, col2=col2, col3=col3,
            archivo=ruta_archivo))

    with open(ruta_archivo) as f:
        for linea_cruda in f:
            linea = linea_cruda.strip()
            if linea.startswith("BEGIN_SCAN") and not linea.startswith("BEGIN_SCAN_DATA"):
                en_scan = True
                campos = {}
                filas = []
                continue
            if linea.startswith("END_SCAN") and not linea.startswith("END_SCAN_DATA"):
                if en_scan:
                    cerrar_scan_actual()
                en_scan = False
                continue
            if not en_scan:
                continue
            if linea.startswith("BEGIN_DATA"):
                en_datos = True
                continue
            if linea.startswith("END_DATA"):
                en_datos = False
                continue
            if en_datos:
                filas.append(linea)
                continue
            if "=" in linea:
                clave, _, valor = linea.partition("=")
                campos[clave.strip()] = valor.strip()

    if not escaneos:
        raise ErrorLecturaMCC(f"{ruta_archivo}: no se encontro ningun BEGIN_SCAN valido")
    return escaneos


def agregar_carpeta(ruta_carpeta):
    """Recorre todos los .mcc de una carpeta (un mes + una maquina/seccion,
    ej. ".../Febrero/IX/Fotones") y agrupa por (energia, curve_type).

    Para cada combinacion (energia, curve_type) se queda con el EscaneoMCC
    de MEAS_DATE mas reciente -- puede salir de un archivo distinto al de
    otro curve_type de la MISMA energia (ver docstring del modulo, caso E06).
    Archivos individuales rotos no interrumpen el resto de la carpeta: se
    devuelven en "errores" con su ruta y el motivo.

    Devuelve {"datos": {energia: {curve_type: EscaneoMCC}}, "errores": [(ruta, msg)]}.
    """
    datos = {}
    errores = []
    rutas = sorted(glob.glob(os.path.join(ruta_carpeta, "*.mcc")))
    for ruta in rutas:
        try:
            escaneos = leer_mcc(ruta)
        except (ErrorLecturaMCC, ValueError, OSError) as exc:
            errores.append((ruta, str(exc)))
            continue
        for escaneo in escaneos:
            por_curva = datos.setdefault(escaneo.energia, {})
            actual = por_curva.get(escaneo.curve_type)
            if actual is None or escaneo.meas_date > actual.meas_date:
                por_curva[escaneo.curve_type] = escaneo
    return {"datos": datos, "errores": errores}
