"""HI-1 (PLAN_HI): el fixture autouse de sesion (tests/conftest.py) redirige
ruta_base_datos() a una BD temporal ANTES del primer test -- ningun test debe
poder crear/tocar Codigo_radqa/BaseDatosQA.db (archivo huerfano de desarrollo,
documentado en CLAUDE.md/H2.4: incluso con git stash de H2.4, la suite seguia
creando ese archivo porque algun test instanciaba Conexion()/EquiposService
sin parchear su propia ruta). Este test fija que ya no puede volver a pasar,
incluso si un test futuro se olvida de parchear su ruta.
"""
import os

from data.ManejoDatos.conection import Conexion, ruta_datos


def _ruta_real_dev():
    """Ruta real de BaseDatosQA.db en modo desarrollo, calculada de forma
    independiente del parche de sesion (ruta_datos no se toca, solo
    ruta_base_datos -- ver tests/conftest.py)."""
    return ruta_datos("BaseDatosQA.db")


class TestAislamientoDeLaBDRealEntreTests:
    def test_instanciar_conexion_no_toca_el_archivo_real_de_desarrollo(self):
        Conexion._instance = None
        try:
            Conexion()  # si el aislamiento fallara, esto crearia la ruta real
            assert not os.path.exists(_ruta_real_dev())
        finally:
            if Conexion._instance is not None:
                Conexion._instance.con.close()
            Conexion._instance = None
