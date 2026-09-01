"""A2 (PLAN_REPARACION_ANUAL_27-08.md §Fase 4, AN-7): el anual de iX no
confirma un guardado correcto. `ix_anual.py::guardar_todas_fse` termina
en un `print` a consola; su gemelo `seiscientos_anual.py` sí muestra
`QMessageBox.information` además del print. `B1` (26-08) ya había añadido
el aviso de FALLO a esta copia (`QMessageBox.critical`) sin igualar el de
ÉXITO -- el físico pulsa "Subir", el guardado sale bien, y no ve nada.
"""
import os
import inspect

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ui.paginasControles.PruebasAnuales.ix_anual import PruebaAnualIX


def test_guardar_todas_fse_avisa_exito_con_messagebox():
    fuente = inspect.getsource(PruebaAnualIX._agregar_botones_tabla)
    idx_print_exito = fuente.index('print(f"Tabla(s) {nombre_tabla} subida(s) correctamente")')
    idx_critical = fuente.index("QMessageBox.critical")
    resto = fuente[idx_print_exito:]
    assert "QMessageBox.information" in resto, (
        "el print de éxito de guardar_todas_fse no está seguido de un "
        "QMessageBox.information -- el físico no se entera de que el "
        "guardado salió bien (AN-7)")
    assert idx_critical < idx_print_exito, (
        "el aviso de fallo (QMessageBox.critical, B1) debe seguir antes "
        "del print de éxito -- si el guardado falla, la función ya "
        "retornó (return) antes de llegar aquí")
