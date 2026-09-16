"""Fuente única de rutas de las BD de referencia para los tests (DP-104).

Las BD de referencia viven FUERA del repo, y el físico las reorganiza
legítimamente: el 15-09-2026 se detectó que las había movido de
`AUNA_2026_2/` a `AUNA_2026_2/BasesDeDatos/` (md5 intactos). Cada test
construía la ruta a su manera -- `ROOT.parent / ...`, `"..", ".."` o una
ruta absoluta escrita a mano -- y la mudanza dejó 37 tests en SKIP en 12
archivos. Ninguno FALLÓ (todos tienen su `skipif`), y justo por eso no se
notaba: la suite seguía en verde con 37 comprobaciones menos. Aquí se
centraliza, igual que `_corpus.py` hizo con el corpus de archivos del
físico (HI-0): cuando las BD se muevan otra vez, se edita SOLO este archivo.

Este archivo NO empieza por `test_`, así pytest no lo colecciona. Solo
declara RUTAS: no abre ninguna BD. Cada test sigue copiando a un temporal
antes de conectar (regla de sesión: nunca conectar directo a una BD de
referencia -- `Conexion()` commitea aunque no cambie nada y altera el md5).
"""
from pathlib import Path

# Codigo_radqa/tests/_bd_referencia.py -> AUNA_2026_2/BasesDeDatos
CARPETA_BD = Path(__file__).resolve().parent.parent.parent / "BasesDeDatos"

# Copia de producción del 21-08-2026 -- NO la producción actual (ver la
# tabla de BD de referencia en CLAUDE.md). Los tests que la llaman
# "producción" fijan líneas base medidas sobre ESTE archivo (p. ej. los
# 109 huérfanos de FK1), así que el nombre de su variable no se cambia.
BD_QA = CARPETA_BD / "BaseDatosQA.db"

# Estructura primitiva: artefacto de referencia para probar la migración.
BD_A_AJUSTAR = CARPETA_BD / "BaseDatosQA(A_Ajustar).db"

# Línea de PRUEBA del rebuild del 11-09-2026. No desciende de producción
# (ver la corrección de linaje de PLAN_PUNTEROS_A_EQUIPOS_11-09.md).
BD_REBUILD_11_09 = CARPETA_BD / "BaseDatosQA(Rebuild_11-09-2026).db"

# Copia MÁS RECIENTE de la producción REAL (entregada por el físico el
# 15-09-2026, ya pasada por la herramienta de migración con R.1). Es la que
# describe el estado verdadero de la BD en uso -- `BD_QA` es del 21-08 y no
# sirve para medir producción. Añadida en T.0
# (PLAN_COPIA_GUARDADA_Y_REPORTES_16-09.md), que exige ensayar toda
# migración de esquema sobre una copia de la producción real.
BD_REBUILD_14_09 = CARPETA_BD / "BaseDatosQA(Rebuild_14-09-2026).db"
