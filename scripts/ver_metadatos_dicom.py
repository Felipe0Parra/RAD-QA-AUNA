#!/usr/bin/env python3
"""
Lista los metadatos de una carpeta de imagenes DICOM: de que equipo son, con que
kV y que corriente se adquirieron, y si la carpeta trae mas de una serie.

Es una herramienta de SOLO LECTURA: abre los archivos, lee los encabezados y no
escribe nada. No toca la base de datos ni la aplicacion.

Uso (Windows, desde la carpeta del codigo):

    .venv\\Scripts\\python scripts\\ver_metadatos_dicom.py "C:\\ruta\\a\\la\\carpeta"

Uso (Linux/Mac):

    python3 scripts/ver_metadatos_dicom.py "/ruta/a/la/carpeta"

Opciones:

    --completo        Vuelca TODAS las etiquetas del primer corte de cada serie,
                      no solo las de la tabla resumen.
    --tag NOMBRE      Muestra el reparto de valores de una etiqueta concreta
                      (p. ej. --tag ExposureTime). Se puede repetir.
    --csv ARCHIVO     Escribe una fila por imagen en un CSV, para abrirlo en Excel.
    --recursivo       Entra tambien en las subcarpetas.

Se pueden pasar varias carpetas de una vez:

    python3 scripts/ver_metadatos_dicom.py carpeta1 carpeta2 carpeta3
"""

import argparse
import collections
import csv
import os
import sys

try:
    import pydicom
except ImportError:
    sys.exit(
        "Falta pydicom. Instalelo con:  pip install pydicom\n"
        "(en Windows, dentro del entorno:  .venv\\Scripts\\pip install pydicom)"
    )


# Las etiquetas que contestan "de que equipo es esto y como se adquirio".
# El orden es el orden en que salen impresas.
ETIQUETAS = [
    ("Fabricante",        "Manufacturer"),
    ("Modelo",            "ManufacturerModelName"),
    ("Estacion",          "StationName"),
    ("Institucion",       "InstitutionName"),
    ("Modalidad",         "Modality"),
    ("Descripcion serie", "SeriesDescription"),
    ("Protocolo",         "ProtocolName"),
    ("Fecha del estudio", "StudyDate"),
    ("Paciente",          "PatientName"),
    ("kV",                "KVP"),
    ("Corriente [mA]",    "XRayTubeCurrent"),
    ("Exposicion [mAs]",  "Exposure"),
    ("Tiempo exp. [ms]",  "ExposureTime"),
    ("CTDIvol [mGy]",     "CTDIvol"),
    ("Espesor corte [mm]","SliceThickness"),
    ("Kernel",            "ConvolutionKernel"),
    ("Filtro",            "FilterType"),
    ("Diametro recon.",   "ReconstructionDiameter"),
    ("Tamano de pixel",   "PixelSpacing"),
    ("Matriz",            "_matriz"),
    ("Ventana centro",    "WindowCenter"),
    ("Ventana ancho",     "WindowWidth"),
    ("Pendiente (slope)", "RescaleSlope"),
    ("Corte (intercept)", "RescaleIntercept"),
]

# Modalidades que SI son cortes de imagen. Lo demas (RTSTRUCT, RTPLAN, RTDOSE)
# puede convivir en la carpeta sin que eso la haga mixta.
MODALIDADES_IMAGEN = {"CT", "MR", "PT", "CR", "DX", "RTIMAGE", "US", "NM"}

# Modelo/estacion esperados por equipo. Sirve para decir "esto es el Halcyon"
# sin que haya que reconocerlo de memoria. Si un equipo no esta aqui, el script
# no se inventa nada: dice "no reconocido".
EQUIPOS_CONOCIDOS = [
    ("Tomografo (SOMATOM go.Sim)", "SOMATOM go.Sim", "CT128260"),
    ("Halcyon",                    "Halcyon",        "Halcyon"),
    ("Clinac iX (OBI CBCT)",       "OBI",            "IX5005"),
    ("Clinac iX (OBI CBCT)",       "On-Board",       "IX5005"),
]


def valor(ds, tag):
    """Devuelve el valor de una etiqueta como texto, o '-' si no esta."""
    if tag == "_matriz":
        filas = getattr(ds, "Rows", None)
        cols = getattr(ds, "Columns", None)
        return f"{filas}x{cols}" if filas and cols else "-"
    v = getattr(ds, tag, None)
    if v is None:
        return "-"
    if isinstance(v, (list, tuple)) or v.__class__.__name__ == "MultiValue":
        return ", ".join(str(x) for x in v)
    return str(v)


def reconocer_equipo(modelo, estacion):
    """Traduce modelo/estacion al nombre del equipo, o dice que no lo reconoce."""
    for nombre, patron_modelo, patron_estacion in EQUIPOS_CONOCIDOS:
        if patron_modelo.lower() in modelo.lower() or patron_estacion.lower() == estacion.lower():
            return nombre
    return "NO RECONOCIDO"


def recoger_archivos(carpeta, recursivo):
    """Devuelve la lista de rutas candidatas. No filtra por extension: hay
    equipos que exportan DICOM sin .dcm, y pydicom ya dira si no lo es."""
    rutas = []
    if recursivo:
        for raiz, _dirs, archivos in os.walk(carpeta):
            for a in sorted(archivos):
                rutas.append(os.path.join(raiz, a))
    else:
        for a in sorted(os.listdir(carpeta)):
            ruta = os.path.join(carpeta, a)
            if os.path.isfile(ruta):
                rutas.append(ruta)
    return rutas


def leer_carpeta(carpeta, recursivo):
    """Lee los encabezados y agrupa por serie. Devuelve (series, ilegibles)."""
    series = collections.OrderedDict()
    ilegibles = []
    for ruta in recoger_archivos(carpeta, recursivo):
        try:
            ds = pydicom.dcmread(ruta, stop_before_pixels=True, force=True)
            # force=True lee casi cualquier cosa; si no hay SOPClassUID no es DICOM.
            if not hasattr(ds, "SOPClassUID") and not hasattr(ds, "Modality"):
                ilegibles.append((os.path.basename(ruta), "no parece DICOM"))
                continue
        except Exception as e:
            ilegibles.append((os.path.basename(ruta), f"{type(e).__name__}: {e}"))
            continue
        uid = str(getattr(ds, "SeriesInstanceUID", "<sin SeriesInstanceUID>"))
        series.setdefault(uid, []).append(ds)

    # Un RTSTRUCT o un RTPLAN no es una serie de imagenes: vive en la misma
    # carpeta pero no es un corte. Se separa para no marcar como "mixta" una
    # carpeta que solo trae su estructura al lado.
    imagenes, no_imagen = collections.OrderedDict(), collections.OrderedDict()
    for uid, datasets in series.items():
        if str(getattr(datasets[0], "Modality", "")).upper() in MODALIDADES_IMAGEN:
            imagenes[uid] = datasets
        else:
            no_imagen[uid] = datasets
    return imagenes, no_imagen, ilegibles


def imprimir_serie(uid, datasets, n_total_carpeta, completo):
    primero = datasets[0]
    modelo = valor(primero, "ManufacturerModelName")
    estacion = valor(primero, "StationName")
    equipo = reconocer_equipo(modelo, estacion)

    print(f"  Serie {uid[-20:]}  ({len(datasets)} de {n_total_carpeta} archivos)")
    print(f"  EQUIPO: {equipo}")
    print("  " + "-" * 60)

    for etiqueta, tag in ETIQUETAS:
        # Si la etiqueta no es constante dentro de la serie, se dice.
        distintos = collections.Counter(valor(ds, tag) for ds in datasets)
        if len(distintos) == 1:
            print(f"    {etiqueta:<20}: {next(iter(distintos))}")
        else:
            comunes = distintos.most_common(3)
            resumen = "  ".join(f"{v} (x{n})" for v, n in comunes)
            extra = f"  [+{len(distintos) - 3} valores mas]" if len(distintos) > 3 else ""
            print(f"    {etiqueta:<20}: VARIA -> {resumen}{extra}")

    if completo:
        print()
        print("    --- todas las etiquetas del primer corte de esta serie ---")
        for elem in primero:
            if elem.tag.group == 0x7FE0:   # datos de pixel, no se imprimen
                continue
            print(f"    {str(elem.tag):<12} {elem.name:<38} = {elem.repval[:70]}")
    print()


def imprimir_carpeta(carpeta, args):
    print("=" * 78)
    print(f"CARPETA: {carpeta}")
    print("=" * 78)

    if not os.path.isdir(carpeta):
        print("  No existe o no es una carpeta.\n")
        return []

    series, no_imagen, ilegibles = leer_carpeta(carpeta, args.recursivo)
    n_no_imagen = sum(len(v) for v in no_imagen.values())
    n_total = sum(len(v) for v in series.values()) + n_no_imagen + len(ilegibles)

    if not series:
        print("  No se encontro ninguna serie de imagenes DICOM legible.\n")
        return []

    print(f"  {n_total} archivo(s), {len(series)} serie(s) de imagen")
    if len(series) > 1:
        print("  *** ATENCION: la carpeta es MIXTA, trae mas de una serie de imagen. ***")
        print("  *** El programa se queda con la MAYORITARIA y descarta el resto. ***")
    if n_no_imagen:
        modalidades = sorted({str(getattr(d[0], "Modality", "?")) for d in no_imagen.values()})
        print(f"  ({n_no_imagen} archivo(s) que no son cortes: {', '.join(modalidades)}. "
              "El programa los ignora; es normal.)")
    print()

    for uid, datasets in sorted(series.items(), key=lambda kv: -len(kv[1])):
        imprimir_serie(uid, datasets, n_total, args.completo)

    for etiqueta_pedida in args.tag:
        print(f"  Reparto de la etiqueta '{etiqueta_pedida}':")
        cuenta = collections.Counter()
        for datasets in series.values():
            for ds in datasets:
                cuenta[valor(ds, etiqueta_pedida)] += 1
        for v, n in cuenta.most_common():
            print(f"    {v}  x{n}")
        print()

    if ilegibles:
        print(f"  {len(ilegibles)} archivo(s) no se pudieron leer como DICOM:")
        for nombre, motivo in ilegibles[:10]:
            print(f"    {nombre}: {motivo}")
        if len(ilegibles) > 10:
            print(f"    ... y {len(ilegibles) - 10} mas")
        print()

    filas = []
    for uid, datasets in series.items():
        for ds in datasets:
            fila = {"carpeta": carpeta, "serie_uid": uid}
            fila["equipo_reconocido"] = reconocer_equipo(
                valor(ds, "ManufacturerModelName"), valor(ds, "StationName")
            )
            for etiqueta, tag in ETIQUETAS:
                fila[etiqueta] = valor(ds, tag)
            filas.append(fila)
    return filas


def main():
    p = argparse.ArgumentParser(
        description="Lista los metadatos de carpetas de imagenes DICOM (solo lectura).",
    )
    p.add_argument("carpetas", nargs="+", help="Una o mas carpetas con imagenes DICOM")
    p.add_argument("--completo", action="store_true",
                   help="Vuelca TODAS las etiquetas del primer corte de cada serie")
    p.add_argument("--tag", action="append", default=[],
                   help="Muestra el reparto de una etiqueta concreta (repetible)")
    p.add_argument("--csv", metavar="ARCHIVO",
                   help="Escribe una fila por imagen en este CSV")
    p.add_argument("--recursivo", action="store_true",
                   help="Entra tambien en las subcarpetas")
    args = p.parse_args()

    todas = []
    for carpeta in args.carpetas:
        todas.extend(imprimir_carpeta(carpeta, args))

    if args.csv and todas:
        columnas = list(todas[0].keys())
        with open(args.csv, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=columnas)
            w.writeheader()
            w.writerows(todas)
        print(f"CSV escrito: {args.csv}  ({len(todas)} filas)")


if __name__ == "__main__":
    main()
