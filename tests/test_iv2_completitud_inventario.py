"""IV2 (PLAN_CONTRATO_COMPLETO_19-08.md §6-IV2, DA-40): tripwire de
completitud del inventario del bloque de QC.

No exige que `TABLAS_ANULABLES` esté ya ampliado a las 53 tablas del cierre
completo -- exige que **toda tabla del cierre esté clasificada**, en el
frozenset o en `EXCEPCIONES_INVENTARIO` (`services/anulacion.py`), cada una
con su motivo. Es la garantía que compra DA-40: una tabla descendiente nueva
sin clasificar pone este test en rojo -- exactamente lo que le habría pasado
a `analisis_placa_verificaciones`/`analisis_placa_correcciones` (el hallazgo
que originó `PLAN_CONTRATO_COMPLETO_19-08.md`) si hubiera existido antes.

Por qué NO exige "ya ampliado": ampliar `TABLAS_ANULABLES` antes de que LF
(Fase 3) filtre las lecturas de las 31 tablas nuevas pondría rojo a LE4/ES1
(`test_le4_lecturas_filtran_activo.py`) por lecturas sin filtrar -- ver §2.7
y §4.4 del plan. Clasificar (en el frozenset O en las excepciones, con
motivo) es lo que cierra la clase del defecto; AMPLIAR es una tarea aparte
(MI1, Fase 4) con sus propios prerequisitos.

El cierre transitivo se calcula sobre una BD temporal recién creada (DDL
real vía `Conexion()`) -- no depende de un archivo externo, portable a
cualquier entorno (CI, la máquina del físico)."""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from services.lectura_vigente import (
    RAICES_QC, cierre_transitivo_fk, excepciones_inventario,
    tablas_anulables,
)


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


class TestCompletitudDelInventario:

    def test_toda_tabla_del_cierre_esta_clasificada(self, bd_temporal):
        con = sqlite3.connect(bd_temporal)
        try:
            cierre = cierre_transitivo_fk(con, RAICES_QC)
        finally:
            con.close()

        actuales = tablas_anulables() - RAICES_QC
        excepciones = excepciones_inventario()
        clasificadas = actuales | excepciones

        huecos = cierre - clasificadas
        assert not huecos, (
            f"Tabla(s) descendiente(s) del bloque de QC SIN clasificar -- ni "
            f"en TABLAS_ANULABLES ni en EXCEPCIONES_INVENTARIO "
            f"(services/anulacion.py): {huecos}. Es exactamente el defecto "
            f"que originó PLAN_CONTRATO_COMPLETO_19-08.md "
            f"(analisis_placa_verificaciones/_correcciones quedaron fuera sin "
            f"que nada avisara). Añade la tabla al frozenset si ya versiona, "
            f"o a EXCEPCIONES_INVENTARIO con su motivo si deliberadamente no."
        )

        sobrantes = actuales - cierre
        assert not sobrantes, (
            f"Tabla(s) en TABLAS_ANULABLES que ya NO son descendientes de "
            f"ninguna raíz de QC: {sobrantes}. Revisa si se retiró una FK o "
            f"una raíz."
        )

    def test_una_tabla_del_cierre_sin_clasificar_pone_esto_en_rojo(self, bd_temporal):
        """Rojo-antes-que-verde, reproducible sin editar `anulacion.py`:
        simula exactamente el defecto de origen -- una tabla real del cierre
        (`control_cunas`) que deja de estar clasificada ni en el frozenset
        ni en las excepciones.

        MI1 (PLAN_CONTRATO_COMPLETO_19-08.md §6-MI1) movió las 30 tablas
        PENDIENTE-LF al frozenset -- `analisis_placa_verificaciones` (la
        tabla que esta prueba usaba hasta aquí) ya está genuinamente en
        `TABLAS_ANULABLES`, así que "des-clasificarla" quitándola solo de
        `excepciones_inventario()` ya no reproduce el defecto (sigue
        clasificada por el otro lado). Las dos únicas tablas que vivían
        exclusivamente en `EXCEPCIONES_INVENTARIO` (`equipos_anual`,
        `posicionamiento_reposicionamiento`, ambas retiradas del esquema --
        MI5 y EB7 respectivamente -- así que `EXCEPCIONES_INVENTARIO` quedó
        vacío) tampoco habrían servido de reemplazo: ninguna tenía
        `CREATE TABLE` en `conection.py`, así que jamás aparecían en el
        cierre transitivo calculado sobre esta BD temporal -- simular su
        "des-clasificación" no habría reproducido nada. Se quita en cambio
        una tabla real del frozenset (`control_cunas`) del lado de
        `actuales`, que es la otra forma en que un hueco puede aparecer."""
        con = sqlite3.connect(bd_temporal)
        try:
            cierre = cierre_transitivo_fk(con, RAICES_QC)
        finally:
            con.close()

        actuales = (tablas_anulables() - RAICES_QC) - {"control_cunas"}
        excepciones = excepciones_inventario()
        clasificadas = actuales | excepciones

        huecos = cierre - clasificadas
        assert "control_cunas" in huecos, (
            "el test de completitud debería haber detectado la tabla "
            "deliberadamente 'des-clasificada' en esta prueba -- si no "
            "aparece aquí, IV2 no detectaría el defecto real"
        )
