"""D.1 (PLAN_NAVEGACION_Y_UNIDADES_10-09.md SS5, SS0.11): 428 unidades
escritas a mano entre parentesis contra 2 sitios que usan el registro
declarado (`services/unidades_qc.py`). El fisico fijo el corchete como
"regla universal para indicar unidades en toda la aplicacion" -- la
tarea correcta es derivar la unidad del registro, no sustituir 428
cadenas a mano (eso solo garantiza que la 429a nazca igual de mal).

ALCANCE EJECUTADO EN ESTA RONDA (11-09-2026, Sonnet): dado el tamano real
medido (314 sitios con unidad real entre parentesis, en 24 archivos) y la
advertencia explicita del propio plan -- "cualquier conversion masiva
tiene que ser una lista revisada a mano, no una sustitucion automatica",
con el caso real de `Analisis_PlacaRC.py:279` ("Interceptos (V)", la V es
vertical, no voltios) como prueba de que un tercio de un token que PARECE
unidad no siempre lo es -- convertir los 314 sitios uno a uno excede el
alcance seguro de esta sesion. Se entrega el TRIPWIRE (la garantia
permanente que exige el plan: "ninguna unidad nueva nace entre
parentesis") mas el censo completo, revisado lo suficiente para separar
unidades reales de falsos positivos (plurales en espanol tipo "grupo(s)",
excluidos por el patron), y CON la unica trampa conocida ya documentada
como excepcion permanente. La conversion linea por linea de los 314
sitios (D.1 fase 2) queda como tarea declarada, no ejecutada -- ver
PLAN_NAVEGACION_Y_UNIDADES_10-09.md SS5 y CLAUDE.md.

Garantia real que este test SI cumple hoy: ningun sitio de produccion
puede empezar a escribir una unidad real entre parentesis sin que este
test lo note (falla si aparece un tuple nuevo que no este en el censo
congelado de abajo) -- la superficie de la deuda dejo de poder crecer en
silencio, aunque no se haya achicado todavia.
"""
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXCLUDE_DIRS = {".venv", "tests", "build", "__pycache__", ".git", ".pytest_cache", "resources"}

# Unidades fisicas reales que este tripwire reconoce -- deliberadamente
# NO incluye tokens ambiguos de una letra que colisionan con plurales en
# espanol u otros usos (ver el patron de espacio-obligatorio mas abajo,
# que ya filtra la mayoria; los que quedan se revisaron a mano).
UNIDADES_CONOCIDAS = {
    "mm", "cm", "m", "km", "um", "\u00b5m", "kg", "g", "mg", "s", "ms", "min", "h", "hr",
    "%", "Ci", "mCi", "GBq", "MBq", "Bq", "kPa", "Pa", "mmHg", "Gy", "cGy", "mGy", "Gy/UM",
    "cGy/UM", "cGy/MU", "Gy/MU", "nC", "pC", "uC", "\u00b5C", "nA", "uA", "\u00b5A", "mA", "A",
    "V", "kV", "mV", "MV", "MeV", "keV", "eV", "HU", "UM", "MU", "U", "lp/mm", "lp/cm",
    "\u00b0C", "\u00b0", "deg", "rpm", "N", "J", "W", "Hz", "kHz", "dpi", "px",
}

# Requiere un espacio (o inicio de cadena) antes del parentesis -- excluye
# el plural en espanol ("grupo(s)", sin espacio) y acepta la anotacion de
# unidad real ("Tiempo integrado (s)", con espacio). Medido contra los
# falsos positivos reales del censo del 11-09: sin este requisito, "(s)"
# aparecia ~30 veces mas, casi todas plurales.
PATRON = re.compile(r"(?<=\s)\(([^()]{1,10})\)")


def censar_unidades_entre_parentesis():
    sitios = set()
    for path in sorted(ROOT.rglob("*.py")):
        if any(parte in EXCLUDE_DIRS for parte in path.parts):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        for nodo in ast.walk(tree):
            if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
                for m in PATRON.finditer(nodo.value):
                    token = m.group(1).strip()
                    if token in UNIDADES_CONOCIDAS:
                        sitios.add((str(path.relative_to(ROOT).as_posix()), nodo.lineno, token))
    return sitios


BASELINE_D1_PENDIENTE = {
    # NOTA: generado programaticamente (censo del 11-09), no revisado uno a
    # uno. Cada entrada es UNIDAD REAL escrita entre parentesis, pendiente
    # de migrar a services/unidades_qc.py + corchetes -- D.1 fase 1.
    # EXCEPCION PERMANENTE conocida, incluida a proposito en este conjunto
    # para que jamas se convierta por accidente:
    #   ('analisisImagenes/Analisis_PlacaRC.py', 279, 'V') -- label='Interceptos (V)',
    #   la V es "vertical", no voltios (SS0.13 del plan). Object Qt de conversion
    #   automatica la volveria una unidad falsa con aspecto de correcta.

    ('analisisImagenes/ActividadFuente.py', 48, 'nA'),
    ('analisisImagenes/ActividadFuente.py', 51, 'mm'),
    ('analisisImagenes/ActividadFuente.py', 52, 'nA'),
    ('analisisImagenes/ActividadFuente.py', 140, 's'),
    ('analisisImagenes/ActividadFuente.py', 141, 's'),
    ('analisisImagenes/Analisis_Catphan_TAC.py', 1008, 'HU'),
    ('analisisImagenes/Analisis_PlacaCuadrada.py', 257, 'mm'),
    ('analisisImagenes/Analisis_PlacaCuadrada.py', 267, 'mm'),
    ('analisisImagenes/Analisis_PlacaRC.py', 213, 'mm'),
    ('analisisImagenes/Analisis_PlacaRC.py', 279, 'V'),
    ('analisisImagenes/Analisis_PlacaRC.py', 281, 'mm'),
    ('analisisImagenes/Analisis_PlacaRC.py', 318, 'mm'),
    ('analisisImagenes/Analisis_PlacaRC.py', 323, 'px'),
    ('analisisImagenes/Analisis_PlacaRC.py', 411, 'mm'),
    ('analisisImagenes/Analisis_PlacaRC.py', 412, 'mm'),
    ('analisisImagenes/Analisis_PlacaRC.py', 413, 'mm'),
    ('analisisImagenes/Analisis_PlacaRC.py', 422, 'mm'),
    ('analisisImagenes/Analisis_PlacaRC.py', 423, 'mm'),
    ('analisisImagenes/Analisis_PlacaRC.py', 548, 'mm'),
    ('analisisImagenes/Analisis_PlacaRC.py', 1207, 'mm'),
    ('analisisImagenes/Analisis_PlacaRC.py', 1221, 'mm'),
    ('data/ManejoDatos/Tablas_Anuales/tablas_anuales.py', 250, 'mm'),
    ('data/ManejoDatos/Tablas_Anuales/tablas_anuales.py', 255, 'cm'),
    ('data/ManejoDatos/Tablas_Anuales/tablas_anuales.py', 256, '%'),
    ('data/ManejoDatos/Tablas_Anuales/tablas_anuales.py', 256, 'cm'),
    ('data/ManejoDatos/Tablas_Anuales/tablas_anuales.py', 404, '%'),
    ('data/ManejoDatos/Tablas_Anuales/tablas_anuales.py', 419, '%'),
    ('data/ManejoDatos/Tablas_Anuales/tablas_anuales.py', 433, 'cm'),
    ('data/ManejoDatos/Tablas_Anuales/tablas_anuales.py', 436, '%'),
    ('data/ManejoDatos/Tablas_Anuales/tablas_anuales.py', 502, 'mm'),
    ('data/ManejoDatos/Tablas_Anuales/tablas_anuales.py', 511, 'cm'),
    ('data/ManejoDatos/Tablas_Anuales/tablas_anuales.py', 512, 'cm'),
    ('data/ManejoDatos/Tablas_Anuales/tablas_anuales.py', 513, 'cm'),
    ('data/ManejoDatos/Tablas_Anuales/tablas_anuales.py', 514, '%'),
    ('data/ManejoDatos/Tablas_Anuales/tablas_anuales.py', 524, 'mm'),
    ('data/ManejoDatos/Tablas_Anuales/tablas_anuales.py', 646, '%'),
    ('data/ManejoDatos/Tablas_Anuales/tablas_anuales.py', 699, '%'),
    ('data/ManejoDatos/Tablas_Anuales/tablas_anuales.py', 762, '%'),
    ('data/ManejoDatos/Tablas_Anuales/tablas_anuales.py', 762, 'cm'),
    ('data/ManejoDatos/Tablas_Anuales/tablas_anuales.py', 908, 'cGy/UM'),
    ('data/ManejoDatos/Tablas_Anuales/tablas_anuales.py', 910, '%'),
    ('data/ManejoDatos/Tablas_Anuales/tablas_anuales.py', 911, '%'),
    ('data/ManejoDatos/Tablas_Anuales/tablas_anuales.py', 912, '%'),
    ('data/ManejoDatos/Tablas_Anuales/tablas_anuales.py', 913, '%'),
    ('data/ManejoDatos/Tablas_Anuales/tablas_anuales.py', 924, 'MV'),
    ('data/ManejoDatos/Tablas_Anuales/tablas_anuales.py', 925, 'cGy/UM'),
    ('data/ManejoDatos/Tablas_Anuales/tablas_anuales.py', 927, '%'),
    ('data/ManejoDatos/Tablas_Anuales/tablas_anuales.py', 928, '%'),
    ('data/ManejoDatos/Tablas_Anuales/tablas_anuales.py', 929, '%'),
    ('data/ManejoDatos/Tablas_Anuales/tablas_anuales.py', 930, '%'),
    ('data/ManejoDatos/Tablas_Anuales/tablas_anuales.py', 937, '%'),
    ('data/ManejoDatos/catphan_TAC/catphan_db.py', 1591, 'mm'),
    ('data/ManejoDatos/catphan_TAC/catphan_db.py', 1734, 'cm'),
    ('data/ManejoDatos/catphan_TAC/catphan_db.py', 1861, 'HU'),
    ('data/ManejoDatos/catphan_TAC/leer_dicom.py', 956, 'mm'),  # A.1 (18-09): 951->956
    ('data/ManejoDatos/conection.py', 1788, 'HU'),  # R.1 (11-09): 1649->1734; T.0 (16-09): 1734->1788
    ('data/ManejoDatos/conection.py', 1811, 'HU'),  # R.1 (11-09): 1672->1757; T.0 (16-09): 1757->1811
    ('data/ManejoDatos/conection.py', 1825, '%'),  # R.1 (11-09): 1686->1771; T.0 (16-09): 1771->1825
    ('data/ManejoDatos/load.py', 3025, 'cm'),
    ('data/ManejoDatos/load.py', 3062, 'mm'),
    ('data/ManejoDatos/load.py', 3063, 'mm'),
    ('data/ManejoDatos/load.py', 3064, 'mm'),
    ('data/ManejoDatos/load.py', 3065, '%'),
    ('data/ManejoDatos/load.py', 3083, '%'),
    ('data/ManejoDatos/load.py', 3154, '°'),
    ('data/ManejoDatos/load.py', 3341, 'cGy/UM'),
    ('data/ManejoDatos/load.py', 3343, '%'),
    ('data/ManejoDatos/load.py', 3344, '%'),
    ('data/ManejoDatos/load.py', 3345, '%'),
    ('data/ManejoDatos/load.py', 3346, '%'),
    ('data/ManejoDatos/load.py', 3360, 'MV'),
    ('data/ManejoDatos/load.py', 3361, 'cGy/UM'),
    ('data/ManejoDatos/load.py', 3363, '%'),
    ('data/ManejoDatos/load.py', 3364, '%'),
    ('data/ManejoDatos/load.py', 3365, '%'),
    ('data/ManejoDatos/load.py', 3366, '%'),
    ('data/ManejoDatos/load.py', 3374, '%'),
    ('data/ManejoDatos/load.py', 3529, 'cm'),
    ('data/ManejoDatos/load.py', 3604, '%'),
    ('data/ManejoDatos/load.py', 3604, 'cm'),
    ('data/ManejoDatos/load.py', 3672, '%'),
    ('data/ManejoDatos/load.py', 4094, 'mm'),
    ('data/ManejoDatos/load.py', 4095, 'mm'),
    ('data/ManejoDatos/load.py', 4128, 'mm'),
    ('data/ManejoDatos/load.py', 4158, 'mm'),
    ('models/PDF/Anual/reportes_anuales.py', 342, '%'),
    ('models/PDF/Anual/reportes_anuales.py', 353, '%'),
    ('models/PDF/Anual/reportes_anuales.py', 375, '%'),
    ('models/PDF/Anual/reportes_anuales.py', 385, '%'),
    ('models/PDF/Anual/reportes_anuales.py', 430, '%'),
    ('models/PDF/Anual/reportes_anuales.py', 440, '%'),
    ('models/PDF/Anual/reportes_anuales.py', 486, '%'),
    ('models/PDF/Anual/reportes_anuales.py', 496, '%'),
    ('models/PDF/Anual/reportes_anuales.py', 507, '%'),
    ('models/PDF/Anual/reportes_anuales.py', 517, '%'),
    ('models/PDF/Anual/reportes_anuales.py', 537, '%'),
    ('models/PDF/Anual/reportes_anuales.py', 537, 'cm'),
    ('models/PDF/Anual/reportes_anuales.py', 547, '%'),
    ('models/PDF/Anual/reportes_anuales.py', 547, 'cm'),
    ('models/PDF/Anual/reportes_anuales.py', 670, 'mm'),
    ('models/PDF/Anual/reportes_anuales.py', 691, '%'),
    ('models/PDF/Anual/reportes_anuales.py', 691, 'cm'),
    ('models/PDF/Anual/reportes_anuales.py', 727, 'cm'),
    ('models/PDF/Anual/reportes_anuales.py', 755, '%'),
    ('models/PDF/Anual/reportes_anuales.py', 755, 'cGy/UM'),
    ('models/PDF/Anual/reportes_anuales.py', 760, '%'),
    ('models/PDF/Anual/reportes_anuales.py', 765, '%'),
    ('models/PDF/Anual/reportes_anuales.py', 770, '%'),
    ('models/PDF/Anual/reportes_anuales.py', 777, 'nC'),
    ('models/PDF/Anual/reportes_anuales.py', 802, 'cm'),
    ('models/PDF/Imagenes/reportes_control_sistema_imagenes.py', 606, 'kV'),
    ('models/PDF/Imagenes/reportes_control_sistema_imagenes.py', 607, 'mA'),
    ('models/PDF/Imagenes/reportes_control_sistema_imagenes.py', 608, 'mm'),
    ('models/PDF/Imagenes/reportes_control_sistema_imagenes.py', 714, 'mm'),
    ('models/PDF/Imagenes/reportes_control_sistema_imagenes.py', 747, 'mm'),
    ('models/PDF/Imagenes/reportes_control_sistema_imagenes.py', 767, 'cm'),
    ('models/PDF/Imagenes/reportes_control_sistema_imagenes.py', 851, '%'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 801, 'cm'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1075, 'mm'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1096, '%'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1096, 'cm'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1115, 'cm'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1144, 'mm'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1145, 'mm'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1146, 'mm'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1149, '%'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1150, '%'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1151, '%'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1152, '%'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1153, '%'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1154, '%'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1175, '%'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1176, '%'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1177, '%'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1178, '%'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1179, '%'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1180, '%'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1247, 'mm'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1248, 'mm'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1251, '%'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1252, '%'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1253, '%'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1254, '%'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1255, '%'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1256, '%'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1329, '°C'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1330, 'mmHg'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1331, '%'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1354, '°C'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1355, 'mmHg'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1356, '%'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1357, 'mm'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1366, 'mm'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1366, 'nA'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1386, 'A'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1386, 'V'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1499, 'mm'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1500, 'nA'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1547, 'nC'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1555, 'nC'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1556, 's'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1557, 'nA'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1565, 'nC'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1565, 's'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1585, '%'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1587, 's'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1633, 's'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1634, 's'),
    ('models/PDF/pdf.py', 1533, 'mm'),
    ('models/PDF/pdf.py', 1534, 'mm'),
    ('models/PDF/pdf.py', 1599, 'mm'),
    ('models/PDF/pdf.py', 1600, 'mm'),
    ('models/PDF/pdf.py', 1654, 'mm'),
    ('models/PDF/pdf.py', 1970, 'mm'),
    ('models/PDF/pdf.py', 2146, '°'),
    ('models/PDF/pdf.py', 2147, '°'),
    ('models/PDF/pdf.py', 2198, '°'),
    ('models/PDF/pdf.py', 2199, '°'),
    ('services/MLCs_calibration_service.py', 112, 'mm'),
    ('services/MLCs_calibration_service.py', 256, 'mm'),
    ('services/MLCs_calibration_service.py', 315, 'mm'),
    ('services/MLCs_calibration_service.py', 423, 'mm'),
    ('services/MLCs_calibration_service.py', 513, 'mm'),
    ('services/MLCs_calibration_service.py', 614, 'mm'),
    ('services/MLCs_calibration_service.py', 665, 'mm'),
    ('services/MLCs_calibration_service.py', 674, 'mm'),
    ('services/MLCs_calibration_service.py', 767, 'mm'),
    ('services/MLCs_calibration_service.py', 786, 'mm'),
    ('services/MLCs_calibration_service.py', 809, 'mm'),
    ('services/MLCs_calibration_service.py', 824, 'mm'),
    ('services/MLCs_calibration_service.py', 848, 'mm'),
    ('services/MLCs_calibration_service.py', 1032, 'mm'),
    ('services/MLCs_calibration_service.py', 1146, 'mm'),
    ('services/MLCs_calibration_service.py', 1149, 'mm'),
    ('services/MLCs_calibration_service.py', 1150, 'mm'),
    ('services/MLCs_calibration_service.py', 1163, 'mm'),
    ('services/MLCs_calibration_service.py', 1205, '°'),
    ('services/MLCs_calibration_service.py', 1257, 'mm'),
    ('services/MLCs_calibration_service.py', 1592, 'mm'),
    ('services/MLCs_calibration_service.py', 1593, 'mm'),
    ('services/MLCs_calibration_service.py', 1691, '°'),
    ('services/mcc_metrics.py', 55, '%'),
    ('services/mcc_metrics.py', 62, '%'),
    ('ui/paginasControles/PruebasAnuales/halcyon_anual.py', 106, '°'),
    ('ui/paginasControles/PruebasAnuales/halcyon_anual.py', 120, 'mm'),
    ('ui/paginasControles/PruebasAnuales/halcyon_anual.py', 126, '%'),
    ('ui/paginasControles/PruebasAnuales/halcyon_anual.py', 126, 'cm'),
    ('ui/paginasControles/PruebasAnuales/halcyon_anual.py', 164, '%'),
    ('ui/paginasControles/PruebasAnuales/halcyon_anual.py', 164, 'cm'),
    ('ui/paginasControles/PruebasAnuales/halcyon_anual.py', 184, 'nC'),
    ('ui/paginasControles/PruebasAnuales/halcyon_anual.py', 192, 'cm'),
    ('ui/paginasControles/PruebasAnuales/ix_anual.py', 160, '%'),
    ('ui/paginasControles/PruebasAnuales/ix_anual.py', 171, '%'),
    ('ui/paginasControles/PruebasAnuales/ix_anual.py', 195, '%'),
    ('ui/paginasControles/PruebasAnuales/ix_anual.py', 276, 'nC'),
    ('ui/paginasControles/PruebasAnuales/ix_anual.py', 293, 'nC'),
    ('ui/paginasControles/PruebasAnuales/ix_anual.py', 305, 'nC'),
    ('ui/paginasControles/PruebasAnuales/seiscientos_anual.py', 207, '%'),
    ('ui/paginasControles/PruebasAnuales/seiscientos_anual.py', 217, '%'),
    ('ui/paginasControles/PruebasAnuales/seiscientos_anual.py', 234, '%'),
    ('ui/paginasControles/PruebasAnuales/seiscientos_anual.py', 234, 'cm'),
    ('ui/paginasControles/PruebasAnuales/seiscientos_anual.py', 287, 'nC'),
    ('ui/paginasControles/PruebasAnuales/seiscientos_anual.py', 292, 'nC'),
    ('ui/paginasControles/PruebasAnuales/seiscientos_anual.py', 299, 'nC'),
    ('ui/paginasControles/PruebasAnuales/seiscientos_anual.py', 321, 'nC'),
    ('ui/paginasControles/PruebasDiarias/braquiterapia.py', 1515, 'mm'),
    ('ui/paginasControles/PruebasDiarias/braquiterapia.py', 2383, 'nC'),
    ('ui/paginasControles/PruebasDiarias/braquiterapia.py', 2384, 's'),
    ('ui/paginasControles/PruebasDiarias/braquiterapia.py', 2385, 'nA'),
    ('ui/paginasControles/PruebasDiarias/braquiterapia.py', 2387, '%'),
    ('ui/paginasControles/PruebasDiarias/braquiterapia.py', 2927, 'nA'),
    ('ui/paginasControles/PruebasDiarias/braquiterapia.py', 2927, 'nC'),
    ('ui/paginasControles/PruebasDiarias/braquiterapia.py', 2927, 's'),
    ('ui/paginasControles/PruebasDiarias/braquiterapia.py', 2928, 'nC'),
    ('ui/paginasControles/PruebasDiarias/braquiterapia.py', 2942, 'nC'),
    ('ui/paginasControles/PruebasDiarias/braquiterapia.py', 2942, 's'),
    ('ui/paginasControles/PruebasDiarias/braquiterapia.py', 2946, '%'),
    ('ui/paginasControles/PruebasDiarias/braquiterapia.py', 2946, 's'),
    ('ui/paginasControles/PruebasDiarias/braquiterapia.py', 3062, 'nC'),
    ('ui/paginasControles/PruebasDiarias/braquiterapia.py', 3062, 's'),
    ('ui/paginasControles/PruebasDiarias/braquiterapia.py', 3377, 'nC'),
    ('ui/paginasControles/PruebasMensuales/braq_mensual.py', 236, '°C'),
    ('ui/paginasControles/PruebasMensuales/braq_mensual.py', 237, 'mmHg'),
    ('ui/paginasControles/PruebasMensuales/braq_mensual.py', 238, '%'),
    ('ui/paginasControles/PruebasMensuales/braq_mensual.py', 239, '°C'),
    ('ui/paginasControles/PruebasMensuales/braq_mensual.py', 240, 'mmHg'),
    ('ui/paginasControles/PruebasMensuales/braq_mensual.py', 241, '%'),
    ('ui/paginasControles/PruebasMensuales/braq_mensual.py', 544, 'mm'),
    ('ui/paginasControles/PruebasMensuales/braq_mensual.py', 544, 'nA'),
    ('ui/paginasControles/PruebasMensuales/braq_mensual.py', 618, 'A'),
    ('ui/paginasControles/PruebasMensuales/braq_mensual.py', 618, 'V'),
    ('ui/paginasControles/PruebasMensuales/braq_mensual.py', 1201, 'mm'),
    ('ui/paginasControles/PruebasMensuales/braq_mensual.py', 1201, 'nA'),
    ('ui/paginasControles/PruebasMensuales/braq_mensual.py', 1232, 'A'),
    ('ui/paginasControles/PruebasMensuales/braq_mensual.py', 1232, 'V'),
    ('ui/paginasControles/PruebasMensuales/halcyon_mensual.py', 164, '°'),
    ('ui/paginasControles/PruebasMensuales/halcyon_mensual.py', 184, 'mm'),
    ('ui/paginasControles/PruebasMensuales/halcyon_mensual.py', 191, '%'),
    ('ui/paginasControles/PruebasMensuales/halcyon_mensual.py', 191, 'cm'),
    ('ui/paginasControles/PruebasMensuales/halcyon_mensual.py', 203, '%'),
    ('ui/paginasControles/PruebasMensuales/halcyon_mensual.py', 203, 'cm'),
    ('ui/paginasControles/PruebasMensuales/halcyon_mensual.py', 217, 'cm'),
    ('ui/paginasControles/PruebasMensuales/seiscientos_mensual.py', 1256, 'mm'),
    ('ui/paginasControles/PruebasMensuales/seiscientos_mensual.py', 1514, 'mm'),
    ('ui/paginasControles/PruebasMensuales/seiscientos_mensual.py', 1518, 'mm'),
    ('ui/paginasControles/PruebasMensuales/seiscientos_mensual.py', 1691, '°'),
    ('ui/paginasControles/PruebasMensuales/seiscientos_mensual.py', 2305, 'cm'),
    ('ui/paginasControles/PruebasMensuales/tac_mensual.py', 760, 'MeV'),
    ('ui/paginasControles/PruebasMensuales/tac_mensual.py', 1595, 'mm'),
    ('ui/paginasControles/PruebasMensuales/tac_mensual.py', 1738, 'cm'),
    ('ui/paginasControles/PruebasMensuales/tac_mensual.py', 1865, 'HU'),
    ('ui/paginasGuia/SQLtoEXCEL.py', 317, 'cGy/UM'),
    ('ui/paginasGuia/SQLtoEXCEL.py', 318, '%'),
    ('ui/paginasGuia/SQLtoEXCEL.py', 319, '%'),
    ('ui/paginasGuia/SQLtoEXCEL.py', 321, '%'),
    ('ui/paginasGuia/SQLtoEXCEL.py', 322, '%'),
    ('ui/paginasGuia/SQLtoEXCEL.py', 323, '%'),
    ('ui/paginasGuia/SQLtoEXCEL.py', 324, '%'),
    ('ui/paginasGuia/SQLtoEXCEL.py', 325, '%'),
    ('ui/paginasGuia/SQLtoEXCEL.py', 326, '%'),
    ('ui/paginasGuia/SQLtoEXCEL.py', 327, '%'),
    ('ui/paginasGuia/SQLtoEXCEL.py', 328, '%'),
    ('ui/paginasGuia/dialogs.py', 1655, '°C'),
    ('ui/paginasGuia/dialogs.py', 1665, 'kPa'),
    ('ui/paginasGuia/dialogs.py', 1676, '%'),
    ('ui/paginasGuia/dialogs.py', 1705, '°C'),
    ('ui/paginasGuia/dialogs.py', 1714, 'kPa'),
    ('ui/paginasGuia/dialogs.py', 1724, '%'),
    ('ui/paginasGuia/dialogs.py', 1778, 'V'),
    ('ui/paginasGuia/dialogs.py', 1781, 'nC'),
    ('ui/paginasGuia/dialogs.py', 1788, 'nC'),
    ('ui/paginasGuia/dialogs.py', 1793, 'nC'),
    ('ui/paginasGuia/dialogs.py', 1798, 'nC'),
    ('ui/paginasGuia/dialogs.py', 1803, 'nC'),
    ('ui/paginasGuia/dialogs.py', 1814, 'UM'),
    ('ui/paginasGuia/dialogs.py', 1949, '%'),
    ('ui/paginasGuia/dialogs.py', 1950, '%'),
    ('ui/paginasGuia/dialogs.py', 1951, '%'),
    ('ui/paginasGuia/dialogs.py', 1978, 'V'),
    ('ui/paginasGuia/dialogs.py', 2161, 'Gy/UM'),
    ('ui/paginasGuia/dialogs.py', 2178, '%'),
    ('ui/paginasGuia/dialogs.py', 2206, '%'),
    ('ui/paginasGuia/dialogs.py', 2228, 'Gy/MU'),
    ('ui/paginasGuia/dialogs.py', 3033, 'UM'),  # R.3 (11-09): 3014->3033
    ('ui/paginasGuia/dialogs.py', 3059, 'cGy/UM'),  # R.3 (11-09): 3040->3059
    ('ui/paginasGuia/equipos.py', 128, '%'),
    ('ui/paginasGuia/equipos.py', 128, 'kPa'),
    ('ui/paginasGuia/equipos.py', 128, '°C'),
    ('ui/paginasGuia/equipos.py', 188, 'nA'),
    ('ui/paginasGuia/equipos.py', 188, 'nC'),
    ('ui/paginasGuia/equipos.py', 555, '%'),
    ('ui/paginasGuia/equipos.py', 555, 'kPa'),
    ('ui/paginasGuia/equipos.py', 555, '°C'),
    ('ui/util_fechas.py', 26, 'px'),
}


class TestNingunaUnidadNuevaEntreParentesis:
    def test_el_censo_actual_no_supera_el_congelado(self):
        """La garantia permanente: si aparece un sitio NUEVO (no estaba en
        el censo del 11-09), este test falla -- hay que declarar la
        unidad en services/unidades_qc.py y usar corchetes, no anadir un
        parentesis mas a mano."""
        actual = censar_unidades_entre_parentesis()
        nuevos = actual - BASELINE_D1_PENDIENTE
        assert nuevos == set(), (
            f"Unidad nueva escrita entre parentesis -- usa "
            f"services/unidades_qc.py + corchetes en su lugar: {sorted(nuevos)}")

    def test_la_trampa_v_vertical_sigue_ahi_y_sigue_siendo_parentesis(self):
        """Analisis_PlacaRC.py:279 -- 'Interceptos (V)', V de vertical, NO
        voltios (SS0.13 del plan). Si esta linea cambia de numero o de
        texto, hay que re-verificar a mano antes de tocarla -- una
        conversion automatica la convertiria en una unidad falsa con
        aspecto de correcta."""
        path = ROOT / "analisisImagenes" / "Analisis_PlacaRC.py"
        texto = path.read_text(encoding="utf-8")
        assert "label='Interceptos (V)'" in texto, (
            "la linea de la trampa V-vertical cambio -- revisar a mano "
            "antes de dar por buena cualquier conversion cercana")

    def test_el_censo_congelado_sigue_siendo_valido_linea_por_linea(self):
        """Si CUALQUIER entrada del censo congelado ya no aparece donde se
        dijo (la linea se movio, el texto cambio), este test lo nota --
        evita que el censo se quede citando lineas fantasma."""
        actual = censar_unidades_entre_parentesis()
        fantasmas = BASELINE_D1_PENDIENTE - actual
        assert fantasmas == set(), (
            f"Sitios del censo que ya NO estan donde se dijo (la linea "
            f"cambio o el texto ya no tiene parentesis -- si se convirtio "
            f"a corchetes, retiralo de BASELINE_D1_PENDIENTE; si solo se "
            f"movio, actualiza el numero de linea): {sorted(fantasmas)}")
