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

# Rebuild del 21-09-2026: la copia con las sesiones de imágenes 47 (Halcyon) y 48
# (Tomógrafo) que el físico analizó ese día, y la 42 (Tomógrafo, 07/2026). La usa
# el informe PDF de CatPhan (E.1/E.3/E.2 de PLAN_HANDOFF_IMAGENES_22-09.md).
BD_REBUILD_21_09 = CARPETA_BD / "BaseDatosQA(Rebuild_21-09-2026).db"

# Rebuild del 08-10-2026 (copia del físico, md5 a56c1f81d9ad80ef8958f106470e139a): la que trae los
# dos controles del 27-09-2026 (refs 37 y 39) con los que el físico vio fallar el guardado del mensual
# de braquiterapia ("UNIQUE constraint failed: MaximosCamaras.ref, MaximosCamaras.posicion").
# La usa BM.1 (PLAN_GUARDADO_BRAQUI_MENSUAL_15-10.md). SIEMPRE se copia a un temporal antes de abrirla.
BD_REBUILD_08_10 = CARPETA_BD / "BaseDatosQA(Rebuild_08-10-2026).db"

# Copia de la PRODUCCION REAL al 05-10-2026 14:19 (entregada por el fisico el 06-10; md5 del .db 5f2ff402a09e9aad13ec9f2b4556f933). Son TRES archivos que van JUNTOS (`.db`, `-wal` y `-shm`): el `-wal`
# guarda la ultima transaccion y copiar solo el `.db` da otra base. La usaban `test_gi0b_observador_renombres.py` (que la declaraba para si) y, desde E.2 (PLAN_ANALISIS_PELICULAS_08-10.md), la prueba de
# «Imagen del campo» del mensual del 600 y del iX: sus 19 mensuales y los 10 con imagen vieja son los casos reales. SIEMPRE se copia (los tres archivos) a un temporal antes de abrirla; abrirla con
# `Conexion()` la cambia (md5), y abrirla con `sqlite3` absorbe el WAL y lo borra.
BD_PRODUCCION_06_10 = CARPETA_BD / "BaseDatosQA(Produccion_2026-10-06).db"
