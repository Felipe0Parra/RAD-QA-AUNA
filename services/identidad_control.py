"""FS.1 (PLAN_REPARACIONES_IMAGENES_FISICOS_06-10.md, DP-154): la IDENTIDAD de un control, en un solo sitio.

Hasta FS.1 había tres búsquedas del «control de este periodo», cada una con su propia regla:
`data/ManejoDatos/load.py::create_control` (por mes y filtrando `control`), `PruebaAnual600.create_control`
(`fecha LIKE '%AAAA%'`) y la precarga de físicos `actualizar_fisicos` (por mes y SIN filtrar `control`). Una regla repetida
tres veces ya divergió tres veces: «Imágenes anual» (que usa la del mensual con tipo «Anual») identificaba el control por
MES y, iniciada en otro mes que el anual, creaba un SEGUNDO control anual del mismo año; y la precarga de un mes con
control anual prestaba los físicos del anual al mensual y al revés (medido el 06-10 en `verificacion/` y en
`PLAN_GUARDADO_SIN_ESPESOR_Y_RESPALDOS_05-10_anexo/logs/VERIF_06-10/`).

La identidad es un dato del dominio, no de la pantalla:

* **mensual** = (equipo, «Mensual», mes y año): el día NUNCA es parte de la llave (F2 del 23-07);
* **anual** = (equipo, «Anual», año): el mes tampoco.

Las dos formas de fecha que convive en `controles.fecha` («MM/yyyy» y «dd/MM/yyyy», DP-32) dan el mismo periodo.

Este módulo es PURO: no importa Qt ni la capa de datos; recibe el cursor ya abierto. La regla del Físico 1 (D2 del plan:
*«el físico 1 para crear un control nuevo sea obligatoriamente el que tiene la sesión iniciada»*) también vive aquí, en el
SERVICIO, para que ningún camino la salte; las pantallas solo la hacen visible (FS.2).
"""
from services.anulacion import filtro_activo
from services.fechas_control import mes_anio_de_fecha

TIPOS_DE_CONTROL = ("Mensual", "Anual")


def _anio_de_fecha(fecha):
    """Año de `controles.fecha`: el último segmento separado por «/» si son 4 dígitos («06/2026», «15/06/2026», «2026»)."""
    ultimo = (fecha or "").strip().split("/")[-1]
    if len(ultimo) == 4 and ultimo.isascii() and ultimo.isdigit():
        return int(ultimo)
    return None


def periodo(tipo, fecha):
    """Periodo que identifica a un control de ese `tipo`: `(mes, anio)` si es «Mensual», `anio` si es «Anual»; `None` si la
    fecha no se puede leer (nunca lanza por la fecha). Un `tipo` desconocido SÍ lanza `ValueError`: adivinarlo
    reintroduciría una tercera regla."""
    if tipo == "Mensual":
        mes, anio = mes_anio_de_fecha(fecha)
        return None if mes is None else (mes, anio)
    if tipo == "Anual":
        return _anio_de_fecha(fecha)
    raise ValueError(f"tipo de control desconocido: {tipo!r} (se esperaba uno de {TIPOS_DE_CONTROL})")


def buscar_control_vigente(cursor, equipo, tipo, fecha):
    """El control VIGENTE de `equipo` y `tipo` que corresponde a `fecha`: `(id, fecha, user_id, user_id_f2)` o `None`.

    Lectura de BLOQUE (DA-47/LR3): filtra `control` y la vigencia (`filtro_activo`), y ordena por `id` para que el desempate
    sea siempre el mismo. La comparación del equipo es EXACTA (la grafía histórica no se normaliza al buscar, DA-15). Si
    hubiera más de un control vigente del mismo periodo (lo que «Imágenes anual» fabricaba: dos anuales del mismo año), se
    elige el de menor `id` y se avisa en consola."""
    buscado = periodo(tipo, fecha)
    if buscado is None:
        return None
    cursor.execute(
        "SELECT id, fecha, user_id, user_id_f2 FROM controles WHERE equipo = ? AND control = ?"
        f"{filtro_activo('controles')} ORDER BY id",
        (equipo, tipo))
    coincidencias = [fila for fila in cursor.fetchall() if periodo(tipo, fila[1]) == buscado]
    if not coincidencias:
        return None
    if len(coincidencias) > 1:
        print(f"identidad_control: hay {len(coincidencias)} controles vigentes de {equipo} ({tipo}) para {buscado}: "
              f"ids {[f[0] for f in coincidencias]}; se usa el {coincidencias[0][0]}")
    return tuple(coincidencias[0])


def fisico_1_de_control_nuevo(nombre_sesion, recibido):
    """Físico 1 con el que NACE un control: quien tiene la sesión (D2). Sin objeto de sesión (llamadores antiguos o pruebas
    que no lo tienen) se conserva lo recibido: la conducta de siempre."""
    return nombre_sesion or recibido


def fisico_1_de_control_existente(recibido, nombre_sesion):
    """Físico 1 con el que se ACTUALIZA un control que ya existía: lo que muestre el formulario («Iniciar» actualiza los
    físicos de un control existente, D2). Si lo recibido no es un nombre (la pantalla anual pasaba el `id` del combo, un
    entero), cae a la sesión: la conducta de antes."""
    if isinstance(recibido, str) and recibido.strip():
        return recibido
    return nombre_sesion
