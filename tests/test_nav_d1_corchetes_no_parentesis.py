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

    ('analisisImagenes/ActividadFuente.py', 61, 'nA'),  # V.1 (28-09): 48->61, TRS-398 en factores_correccion
    ('analisisImagenes/ActividadFuente.py', 64, 'mm'),  # V.1 (28-09): 51->64
    ('analisisImagenes/ActividadFuente.py', 65, 'nA'),  # V.1 (28-09): 52->65
    ('analisisImagenes/ActividadFuente.py', 153, 's'),  # V.1 (28-09): 140->153
    ('analisisImagenes/ActividadFuente.py', 154, 's'),  # V.1 (28-09): 141->154
    ('analisisImagenes/Analisis_Catphan_TAC.py', 1057, 'HU'),  # D.0 (23-09): 1008->1017; D.1 (23-09): 1017->1063; B.1 (23-09): 1063->1085; G.3 (24-09): 1085->1093; E.1 (24-09): 1093->1057
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
    ('data/ManejoDatos/catphan_TAC/catphan_db.py', 1657, 'mm'),  # A.1 (23-09): 1591->1638; A.2 (23-09): 1638->1644; G.2 (24-09): 1644->1648; G.3 (24-09): 1648->1657
    ('data/ManejoDatos/catphan_TAC/catphan_db.py', 1800, 'cm'),  # A.1 (23-09): 1734->1781; A.2 (23-09): 1781->1787; G.2 (24-09): 1787->1791; G.3 (24-09): 1791->1800
    ('data/ManejoDatos/catphan_TAC/catphan_db.py', 1927, 'HU'),  # A.1 (23-09): 1861->1908; A.2 (23-09): 1908->1914; G.2 (24-09): 1914->1918; G.3 (24-09): 1918->1927
    ('data/ManejoDatos/catphan_TAC/leer_dicom.py', 1366, 'mm'),  # A.1 (18-09): 951->956; C.2 (22-09): 956->1142->1164; D.0 (23-09): 1164->1258; D.1 (23-09): 1258->1290; A.1 (23-09): 1290->1294; A.3 (23-09): 1294->1319; B.2 (25-09): 1319->1351; B.3 (25-09): 1351->1366
    ('data/ManejoDatos/conection.py', 1908, 'HU'),  # R.1 (11-09): 1649->1734; T.0 (16-09): 1734->1788; B.1 (21-09): 1788->1817; A.1 (23-09): 1817->1857; A.2 (23-09): 1857->1861; G.2 (24-09): 1861->1882; G.3 (24-09): 1882->1908
    ('data/ManejoDatos/conection.py', 1931, 'HU'),  # R.1 (11-09): 1672->1757; T.0 (16-09): 1757->1811; B.1 (21-09): 1811->1840; A.1 (23-09): 1840->1880; A.2 (23-09): 1880->1884; G.2 (24-09): 1884->1905; G.3 (24-09): 1905->1931
    ('data/ManejoDatos/conection.py', 1945, '%'),  # R.1 (11-09): 1686->1771; T.0 (16-09): 1771->1825; B.1 (21-09): 1825->1854; A.1 (23-09): 1854->1894; A.2 (23-09): 1894->1898; G.2 (24-09): 1898->1919; G.3 (24-09): 1919->1945
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
    ('models/PDF/Imagenes/reportes_control_sistema_imagenes.py', 854, 'mm'),  # E.3 (24-09): 714->730; E.2 (24-09): 730->808; G.2 (24-09): 808->809; G.3 (24-09): 809->845; B.3 (25-09): 845->854
    ('models/PDF/Imagenes/reportes_control_sistema_imagenes.py', 887, 'mm'),  # E.3 (24-09): 747->763; E.2 (24-09): 763->841; G.2 (24-09): 841->842; G.3 (24-09): 842->878; B.3 (25-09): 878->887
    ('models/PDF/Imagenes/reportes_control_sistema_imagenes.py', 907, 'cm'),  # E.3 (24-09): 767->783; E.2 (24-09): 783->861; G.2 (24-09): 861->862; G.3 (24-09): 862->898; B.3 (25-09): 898->907
    ('models/PDF/Imagenes/reportes_control_sistema_imagenes.py', 991, '%'),  # E.3 (24-09): 851->867; E.2 (24-09): 867->945; G.2 (24-09): 945->946; G.3 (24-09): 946->982; B.3 (25-09): 982->991
    ('models/PDF/Mensuales/reportes_mensuales.py', 802, 'cm'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1076, 'mm'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1097, '%'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1097, 'cm'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1116, 'cm'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1145, 'mm'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1146, 'mm'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1147, 'mm'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1150, '%'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1151, '%'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1152, '%'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1153, '%'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1154, '%'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1155, '%'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1176, '%'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1177, '%'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1178, '%'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1179, '%'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1180, '%'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1181, '%'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1248, 'mm'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1249, 'mm'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1252, '%'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1253, '%'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1254, '%'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1255, '%'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1256, '%'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1257, '%'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1330, '°C'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1331, 'mmHg'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1332, '%'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1355, '°C'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1356, 'mmHg'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1357, '%'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1358, 'mm'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1367, 'mm'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1367, 'nA'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1387, 'A'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1387, 'V'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1504, 'mm'),
    ('models/PDF/Mensuales/reportes_mensuales.py', 1505, 'nA'),  # V.3 (28-09): 1500->1505
    ('models/PDF/Mensuales/reportes_mensuales.py', 1552, 'nC'),  # V.3 (28-09): 1547->1552
    ('models/PDF/Mensuales/reportes_mensuales.py', 1560, 'nC'),  # V.3 (28-09): 1555->1560
    ('models/PDF/Mensuales/reportes_mensuales.py', 1561, 's'),  # V.3 (28-09): 1556->1561
    ('models/PDF/Mensuales/reportes_mensuales.py', 1562, 'nA'),  # V.3 (28-09): 1557->1562
    ('models/PDF/Mensuales/reportes_mensuales.py', 1570, 'nC'),  # V.3 (28-09): 1565->1570
    ('models/PDF/Mensuales/reportes_mensuales.py', 1570, 's'),  # V.3 (28-09): 1565->1570
    ('models/PDF/Mensuales/reportes_mensuales.py', 1590, '%'),  # V.3 (28-09): 1585->1590
    ('models/PDF/Mensuales/reportes_mensuales.py', 1592, 's'),  # V.3 (28-09): 1587->1592
    ('models/PDF/Mensuales/reportes_mensuales.py', 1638, 's'),  # V.3 (28-09): 1633->1638
    ('models/PDF/Mensuales/reportes_mensuales.py', 1639, 's'),  # V.3 (28-09): 1634->1639
    ('models/PDF/pdf.py', 1591, 'mm'),  # E.1 (24-09): 1533->1546; E.2 (24-09): 1546->1581; G.3 (24-09): 1581->1591
    ('models/PDF/pdf.py', 1592, 'mm'),  # E.1 (24-09): 1534->1547; E.2 (24-09): 1547->1582; G.3 (24-09): 1582->1592
    ('models/PDF/pdf.py', 1657, 'mm'),  # E.1 (24-09): 1599->1612; E.2 (24-09): 1612->1647; G.3 (24-09): 1647->1657
    ('models/PDF/pdf.py', 1658, 'mm'),  # E.1 (24-09): 1600->1613; E.2 (24-09): 1613->1648; G.3 (24-09): 1648->1658
    ('models/PDF/pdf.py', 1712, 'mm'),  # E.1 (24-09): 1654->1667; E.2 (24-09): 1667->1702; G.3 (24-09): 1702->1712
    ('models/PDF/pdf.py', 2028, 'mm'),  # E.1 (24-09): 1970->1983; E.2 (24-09): 1983->2018; G.3 (24-09): 2018->2028
    ('models/PDF/pdf.py', 2204, '°'),  # E.1 (24-09): 2146->2159; E.2 (24-09): 2159->2194; G.3 (24-09): 2194->2204
    ('models/PDF/pdf.py', 2205, '°'),  # E.1 (24-09): 2147->2160; E.2 (24-09): 2160->2195; G.3 (24-09): 2195->2205
    ('models/PDF/pdf.py', 2256, '°'),  # E.1 (24-09): 2198->2211; E.2 (24-09): 2211->2246; G.3 (24-09): 2246->2256
    ('models/PDF/pdf.py', 2257, '°'),  # E.1 (24-09): 2199->2212; E.2 (24-09): 2212->2247; G.3 (24-09): 2247->2257
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
    ('ui/paginasControles/PruebasDiarias/braquiterapia.py', 1516, 'mm'),  # V.3 (28-09): 1515->1516
    ('ui/paginasControles/PruebasDiarias/braquiterapia.py', 2385, 'nC'),  # V.3 (28-09): 2383->2385
    ('ui/paginasControles/PruebasDiarias/braquiterapia.py', 2386, 's'),  # V.3 (28-09): 2384->2386
    ('ui/paginasControles/PruebasDiarias/braquiterapia.py', 2387, 'nA'),  # V.3 (28-09): 2385->2387
    ('ui/paginasControles/PruebasDiarias/braquiterapia.py', 2389, '%'),  # V.3 (28-09): 2387->2389
    ('ui/paginasControles/PruebasDiarias/braquiterapia.py', 2929, 'nA'),  # V.3 (28-09): 2927->2929
    ('ui/paginasControles/PruebasDiarias/braquiterapia.py', 2929, 'nC'),  # V.3 (28-09): 2927->2929
    ('ui/paginasControles/PruebasDiarias/braquiterapia.py', 2929, 's'),  # V.3 (28-09): 2927->2929
    ('ui/paginasControles/PruebasDiarias/braquiterapia.py', 2930, 'nC'),  # V.3 (28-09): 2928->2930
    ('ui/paginasControles/PruebasDiarias/braquiterapia.py', 2944, 'nC'),  # V.3 (28-09): 2942->2944
    ('ui/paginasControles/PruebasDiarias/braquiterapia.py', 2944, 's'),  # V.3 (28-09): 2942->2944
    ('ui/paginasControles/PruebasDiarias/braquiterapia.py', 2948, '%'),  # V.3 (28-09): 2946->2948
    ('ui/paginasControles/PruebasDiarias/braquiterapia.py', 2948, 's'),  # V.3 (28-09): 2946->2948
    ('ui/paginasControles/PruebasDiarias/braquiterapia.py', 3064, 'nC'),  # V.3 (28-09): 3062->3064
    ('ui/paginasControles/PruebasDiarias/braquiterapia.py', 3064, 's'),  # V.3 (28-09): 3062->3064
    ('ui/paginasControles/PruebasDiarias/braquiterapia.py', 3379, 'nC'),  # V.3 (28-09): 3377->3379
    ('ui/paginasControles/PruebasMensuales/braq_mensual.py', 239, '°C'),  # V.3 (28-09): 236->239
    ('ui/paginasControles/PruebasMensuales/braq_mensual.py', 240, 'mmHg'),  # V.3 (28-09): 237->240
    ('ui/paginasControles/PruebasMensuales/braq_mensual.py', 241, '%'),  # V.3 (28-09): 238->241
    ('ui/paginasControles/PruebasMensuales/braq_mensual.py', 242, '°C'),  # V.3 (28-09): 239->242
    ('ui/paginasControles/PruebasMensuales/braq_mensual.py', 243, 'mmHg'),  # V.3 (28-09): 240->243
    ('ui/paginasControles/PruebasMensuales/braq_mensual.py', 244, '%'),  # V.3 (28-09): 241->244
    ('ui/paginasControles/PruebasMensuales/braq_mensual.py', 547, 'mm'),  # V.3 (28-09): 544->547
    ('ui/paginasControles/PruebasMensuales/braq_mensual.py', 547, 'nA'),  # V.3 (28-09): 544->547
    ('ui/paginasControles/PruebasMensuales/braq_mensual.py', 621, 'A'),  # V.3 (28-09): 618->621
    ('ui/paginasControles/PruebasMensuales/braq_mensual.py', 621, 'V'),  # V.3 (28-09): 618->621
    ('ui/paginasControles/PruebasMensuales/braq_mensual.py', 1204, 'mm'),  # V.3 (28-09): 1201->1204
    ('ui/paginasControles/PruebasMensuales/braq_mensual.py', 1204, 'nA'),  # V.3 (28-09): 1201->1204
    ('ui/paginasControles/PruebasMensuales/braq_mensual.py', 1243, 'A'),  # V.3 (28-09): 1232->1243
    ('ui/paginasControles/PruebasMensuales/braq_mensual.py', 1243, 'V'),  # V.3 (28-09): 1232->1243
    ('ui/paginasControles/PruebasMensuales/halcyon_mensual.py', 164, '°'),
    ('ui/paginasControles/PruebasMensuales/halcyon_mensual.py', 184, 'mm'),
    ('ui/paginasControles/PruebasMensuales/halcyon_mensual.py', 191, '%'),
    ('ui/paginasControles/PruebasMensuales/halcyon_mensual.py', 191, 'cm'),
    ('ui/paginasControles/PruebasMensuales/halcyon_mensual.py', 203, '%'),
    ('ui/paginasControles/PruebasMensuales/halcyon_mensual.py', 203, 'cm'),
    ('ui/paginasControles/PruebasMensuales/halcyon_mensual.py', 217, 'cm'),
    ('ui/paginasControles/PruebasMensuales/seiscientos_mensual.py', 1273, 'mm'),  # A.2 (21-09): 1256->1269; B.3 (21-09): 1269->1270; C.1 (25-09): 1270->1273
    ('ui/paginasControles/PruebasMensuales/seiscientos_mensual.py', 1531, 'mm'),  # A.2 (21-09): 1514->1527; B.3 (21-09): 1527->1528; C.1 (25-09): 1528->1531
    ('ui/paginasControles/PruebasMensuales/seiscientos_mensual.py', 1535, 'mm'),  # A.2 (21-09): 1518->1531; B.3 (21-09): 1531->1532; C.1 (25-09): 1532->1535
    ('ui/paginasControles/PruebasMensuales/seiscientos_mensual.py', 1708, '°'),  # A.2 (21-09): 1691->1704; B.3 (21-09): 1704->1705; C.1 (25-09): 1705->1708
    ('ui/paginasControles/PruebasMensuales/seiscientos_mensual.py', 2500, 'cm'),  # A.2 (21-09): 2305->2364; B.3 (21-09): 2364->2425; B.4 (21-09): 2425->2497; C.1 (25-09): 2497->2500
    ('ui/paginasControles/PruebasMensuales/tac_mensual.py', 1654, 'mm'),  # D.1 (23-09): 1595->1602; A.1 (23-09): 1602->1645; A.2 (23-09): 1645->1651; A.3 (23-09): 1651->1653; G.1 (24-09): 1653->1688; G.2 (24-09): 1688->1682; G.3 (24-09): 1682->1705; C.1 (25-09): 1705->1654
    ('ui/paginasControles/PruebasMensuales/tac_mensual.py', 1797, 'cm'),  # D.1 (23-09): 1738->1745; A.1 (23-09): 1745->1788; A.2 (23-09): 1788->1794; A.3 (23-09): 1794->1796; G.1 (24-09): 1796->1831; G.2 (24-09): 1831->1825; G.3 (24-09): 1825->1848; C.1 (25-09): 1848->1797
    ('ui/paginasControles/PruebasMensuales/tac_mensual.py', 1924, 'HU'),  # D.1 (23-09): 1865->1872; A.1 (23-09): 1872->1915; A.2 (23-09): 1915->1921; A.3 (23-09): 1921->1923; G.1 (24-09): 1923->1958; G.2 (24-09): 1958->1952; G.3 (24-09): 1952->1975; C.1 (25-09): 1975->1924
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
