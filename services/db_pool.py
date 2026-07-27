"""Fachada única de obtención de conexiones para las vistas de control
(P1, PLAN_P1_POOL_CONEXIONES_27-07.md). Reemplaza las 5 copias idénticas
de la clase `DatabaseManager` (deuda F-BD6, INFORME_BARRIDO_BD_RUTAS_24-07.md)
que vivían en seiscientos_mensual.py / ix_anual.py / halcyon_anual.py /
HC_imagenes_mensual.py / ix_imagenes_mensual.py.

SIN ESTADO: cada `obtener_conexion()` devuelve una conexión NUEVA e
independiente de `Conexion().conectar()` (ya trae WAL + busy_timeout=30000 +
foreign_keys=ON vía `aplicar_pragmas_conexion`). No hay pool compartido a
nivel de clase -> desaparece el bug H-B: `PruebaMensual600.__del__ →
limpiar_recursos → cerrar_conexiones()` ya no puede cerrar una conexión que
otra vista viva todavía esté usando, porque no hay nada compartido que cerrar.

`cerrar_conexiones()` queda como no-op deliberado: se conserva porque
`limpiar_recursos()` sigue llamándolo (ver P1.3), pero ya no hace nada -- es
la pieza que elimina H-B sin tocar el árbol de herencia ni `limpiar_recursos`.

El nombre `DatabaseManager` se re-exporta sin cambios desde los 5 módulos
(`from services.db_pool import DatabaseManager`) para que los ~15 call-sites
de producción y los tests que importan ese nombre no cambien.
"""
from data.ManejoDatos import conection as _conection


class DatabaseManager:
    def obtener_conexion(self):
        return _conection.Conexion().conectar()

    def cerrar_conexiones(self):
        # Compatibilidad: ya no hay pool compartido que cerrar.
        pass
