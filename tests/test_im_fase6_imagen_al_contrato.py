"""Fase 6 -- IM1/IM2/IM3/IM4 (PLAN_CONTRATO_COMPLETO_19-08.md §6-IM): la
imagen del análisis de placa entra al contrato anular+insertar.

**IMG-2, el defecto que cierra IM1**: `crear_algo` mutaba el bloque vigente
de `preguntas` con un `UPDATE ... SET imagen = ?` -- el mismo patrón G1/G2
que toda la Fase 5 eliminó del resto del bloque de QC. Medido en el rebuild
del 19-08: subir `placa_ref6` tres veces y luego otra imagen distinta dejó
**solo la última**; 9 imágenes se destruyeron sin rastro.

Los cuatro subs, y qué prueba cada uno aquí:

  - **IM1**: cada guardado de imagen deja una generación recuperable, y
    hereda el texto del bloque vigente en vez de nacer con las 14 columnas
    en NULL. Es lo que este archivo prueba con más detalle.
  - **IM2**: la fila de auditoría (UNA por clic, A6.3) dice QUÉ imagen se
    guardó. `crear_algo` devuelve `(nombre, bytes)` para que su único
    llamador lo escriba.
  - **IM3** ([[DA-65]]): `self.res` se limpia al entrar a `analizar_imagen`,
    para que un análisis fallido no deje vivo el resultado del anterior.
  - **IM4**: existe un lector -- `imagen_vigente(ref)` -- que devuelve la
    imagen del bloque VIGENTE.

Lo que este archivo NO cubre, a propósito:
  - La atomicidad entre la fila de auditoría y la imagen ([[DP-43]],
    [[DA-64]]): siguen siendo transacciones distintas, por decisión.
  - IMG-1 (el fallo de DPI de `analizar_cuadrado2`): va al plan de imágenes.
    IM3 solo impide que ese fallo se traduzca en datos equivocados.
"""
import os
import sqlite3

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QMessageBox, QWidget

import data.ManejoDatos.conection as conection_mod
from data.ManejoDatos.conection import Conexion
from data.ManejoDatos.load import crear_algo, imagen_vigente

COLUMNAS_TEXTO = [
    "iso_mec", "reticulo_cent", "bordes_coin", "camilla_vert_rango",
    "camilla_vert_desp", "camilla_iso_desp", "telem_rango", "telem_desp",
    "camp_luz_desp", "puntero_telem_diff", "laser_techo", "laser_lateral27",
    "laser_lateral9", "observaciones",
]


@pytest.fixture(scope="module")
def app():
    instancia = QApplication.instance() or QApplication([])
    yield instancia


@pytest.fixture
def bd_temporal(monkeypatch, tmp_path):
    ruta = str(tmp_path / "test.db")
    monkeypatch.setattr(conection_mod, "ruta_base_datos", lambda: ruta)
    Conexion._instance = None
    conexion = Conexion()
    con = conexion.con
    con.execute("INSERT INTO users (fullname) VALUES ('fisico de prueba')")
    con.execute(
        "INSERT INTO controles (id, equipo, control, fecha, user_id) "
        "VALUES (952, 'Clinac 600', 'Mensual', '01/06/2026', 'fisico de prueba')")
    con.commit()
    yield ruta
    conexion.con.close()
    Conexion._instance = None


@pytest.fixture(autouse=True)
def sin_dialogos(monkeypatch):
    """Trampa 2 de CLAUDE.md: un QMessageBox sin mockear cuelga el test
    esperando un clic. `critical` imprime en vez de callar -- un
    early-return silencioso dentro de `crear_algo` es exactamente lo que
    costó un diagnóstico equivocado en EB2b."""
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)
    monkeypatch.setattr(
        QMessageBox, "critical",
        lambda *a, **k: print("QMessageBox.critical:", a[1:]))


def _pelado():
    obj = QWidget.__new__(QWidget)
    QWidget.__init__(obj)
    return obj


def _guardar_imagen(ruta_db, ref, ruta_archivo):
    obj = _pelado()
    obj.imagen_path = str(ruta_archivo)
    return crear_algo(obj, ref, None)


def _filas(ruta_db, ref):
    con = sqlite3.connect(ruta_db)
    try:
        con.row_factory = sqlite3.Row
        return con.execute(
            "SELECT rowid, * FROM preguntas WHERE ref = ? ORDER BY rowid",
            (ref,)).fetchall()
    finally:
        con.close()


class TestIM1ElBloqueVigenteYaNoSeMuta:

    def test_la_imagen_anterior_sobrevive_anulada(self, app, bd_temporal, tmp_path):
        """El corazón de IMG-2: antes, el segundo guardado destruía la
        primera imagen. Ahora queda recuperable."""
        img1 = tmp_path / "primera.png"
        img1.write_bytes(b"PRIMERA imagen")
        img2 = tmp_path / "segunda.png"
        img2.write_bytes(b"SEGUNDA imagen, distinta")

        _guardar_imagen(bd_temporal, 952, img1)
        _guardar_imagen(bd_temporal, 952, img2)

        filas = _filas(bd_temporal, 952)
        assert len(filas) == 2, f"debía quedar la anulada + la nueva: {filas}"
        anuladas = [f for f in filas if f["activo"] == 0]
        vigentes = [f for f in filas if f["activo"] == 1]
        assert len(anuladas) == 1 and len(vigentes) == 1

        assert bytes(anuladas[0]["imagen"]) == b"PRIMERA imagen", (
            "la generación anterior debía conservar SU imagen -- es "
            "exactamente lo que IMG-2 destruía")
        assert bytes(vigentes[0]["imagen"]) == b"SEGUNDA imagen, distinta"

    def test_nueve_guardados_dejan_nueve_generaciones(self, app, bd_temporal, tmp_path):
        """El escenario literal del rebuild del 19-08 (subir varias veces y
        luego otra distinta), que dejó solo la última. Ahora ninguna se
        pierde."""
        for i in range(9):
            img = tmp_path / f"img{i}.png"
            img.write_bytes(f"imagen numero {i}".encode())
            _guardar_imagen(bd_temporal, 952, img)

        filas = _filas(bd_temporal, 952)
        assert len(filas) == 9
        assert sum(1 for f in filas if f["activo"] == 1) == 1
        guardadas = {bytes(f["imagen"]) for f in filas}
        assert guardadas == {f"imagen numero {i}".encode() for i in range(9)}, (
            "las 9 imágenes debían seguir todas en la BD -- ninguna pisada")

    def test_el_texto_vigente_se_hereda_en_el_bloque_nuevo(
            self, app, bd_temporal, tmp_path):
        """Sin composición, el bloque nuevo nacería con las 14 columnas de
        texto en NULL y el reemplazo perdería los aspectos mecánicos ya
        guardados -- convertiría IM1 en un defecto peor que IMG-2."""
        con = sqlite3.connect(bd_temporal)
        con.execute(
            "INSERT INTO preguntas (ref, iso_mec, observaciones, activo) "
            "VALUES (952, 1.25, 'el retículo está descentrado', 1)")
        con.commit()
        con.close()

        img = tmp_path / "placa.png"
        img.write_bytes(b"analisis de placa")
        _guardar_imagen(bd_temporal, 952, img)

        vigentes = [f for f in _filas(bd_temporal, 952) if f["activo"] == 1]
        assert len(vigentes) == 1
        assert vigentes[0]["iso_mec"] == 1.25
        assert vigentes[0]["observaciones"] == "el retículo está descentrado"
        assert bytes(vigentes[0]["imagen"]) == b"analisis de placa"

    def test_sin_bloque_previo_inserta_igual(self, app, bd_temporal, tmp_path):
        """[[DA-63]]: guardar la imagen ANTES de llenar los aspectos
        mecánicos sigue funcionando. `ref=6` y `ref=10` en producción son
        exactamente eso -- imagen con las 14 columnas de texto en NULL."""
        img = tmp_path / "sola.png"
        img.write_bytes(b"imagen sin texto todavia")
        _guardar_imagen(bd_temporal, 952, img)

        filas = _filas(bd_temporal, 952)
        assert len(filas) == 1
        assert bytes(filas[0]["imagen"]) == b"imagen sin texto todavia"
        assert all(filas[0][c] is None for c in COLUMNAS_TEXTO)

    def test_no_borra_nunca(self, app, bd_temporal, tmp_path):
        """La regla del contrato: nada del bloque de QC se borra. El conteo
        total solo puede crecer."""
        total_previo = 0
        for i in range(4):
            img = tmp_path / f"i{i}.png"
            img.write_bytes(f"contenido {i}".encode())
            _guardar_imagen(bd_temporal, 952, img)
            total = len(_filas(bd_temporal, 952))
            assert total > total_previo, (
                f"el total de filas bajó de {total_previo} a {total} -- "
                f"algo borró una generación")
            total_previo = total

    def test_una_imagen_ilegible_no_toca_la_base(self, app, bd_temporal, tmp_path):
        """Si la ruta dejó de ser legible entre el análisis y el clic, se
        avisa y NO se escribe nada. Antes esto se propagaba hasta el slot de
        Qt, que lo atrapaba: el físico veía 'no pasó nada', sin mensaje."""
        img = tmp_path / "buena.png"
        img.write_bytes(b"imagen valida")
        _guardar_imagen(bd_temporal, 952, img)
        antes = _filas(bd_temporal, 952)

        resultado = _guardar_imagen(bd_temporal, 952, tmp_path / "no_existe.png")

        assert resultado is None
        despues = _filas(bd_temporal, 952)
        assert len(despues) == len(antes), (
            "un fallo al leer el archivo no debe dejar rastro en la BD")
        vigentes = [f for f in despues if f["activo"] == 1]
        assert len(vigentes) == 1
        assert bytes(vigentes[0]["imagen"]) == b"imagen valida", (
            "el bloque vigente anterior debía quedar intacto")


class TestIM2LaAuditoriaDiceQueImagen:

    def test_crear_algo_devuelve_nombre_y_tamano(self, app, bd_temporal, tmp_path):
        img = tmp_path / "placa_ref6.png"
        contenido = b"contenido de la placa" * 10
        img.write_bytes(contenido)

        resultado = _guardar_imagen(bd_temporal, 952, img)

        assert resultado == ("placa_ref6.png", len(contenido))

    def test_sin_imagen_seleccionada_devuelve_none(self, app, bd_temporal):
        obj = _pelado()
        obj.imagen_path = None
        assert crear_algo(obj, 952, None) is None

    def test_crear_algo_no_escribe_su_propia_fila_de_auditoria(
            self, app, bd_temporal, tmp_path):
        """A6.3, "una acción una fila": la fila la escribe
        `guardar_analisis_e_imagen`, que es el único llamador y ya está
        declarado como responsable en el ALLOWLIST de A6.1. Si `crear_algo`
        auditara por su cuenta habría 2 filas por 1 clic."""
        img = tmp_path / "placa.png"
        img.write_bytes(b"contenido")
        _guardar_imagen(bd_temporal, 952, img)

        con = sqlite3.connect(bd_temporal)
        filas = con.execute(
            "SELECT accion, tabla FROM audit_log WHERE tabla = 'preguntas'").fetchall()
        con.close()
        assert filas == [], (
            f"crear_algo no debe auditar por su cuenta (auditar=False): {filas}")


class TestIM5LaImagenYSusValoresViajanJuntos:
    """IM5 (Fase 6, 25-08): `guardar_analisis_placa600` se tragaba su propia
    excepción (rollback + aviso) y devolvía `None`, indistinguible de un
    guardado bueno -- el llamador seguía adelante y guardaba **la imagen
    igual**, dejándola sin los valores que la explican.

    Se ve en producción: `ref=1` y `ref=5` tienen imagen y **0 filas** en
    `analisis_placa_*`. Ahora devuelve `True`/`False` y el llamador
    (`guardar_analisis_e_imagen`) no toca la imagen si los valores fallaron.
    El comportamiento del botón se prueba en
    `test_a6_3_auditoria_mensual.py`; aquí se fija el contrato de la
    función."""

    def test_devuelve_true_cuando_guarda(self, app, bd_temporal):
        """Datos con la forma REAL que produce `analizar_cuadrado2` -- el
        mismo constructor que usa el test de EB2a, para no inventar aquí una
        segunda idea de qué forma tienen."""
        from data.ManejoDatos.load import guardar_analisis_placa600

        def _verificacion(base):
            return {
                "angulos": [base, base + 1, base + 2, base + 3],
                "lados_mm": {"arriba": base, "abajo": base + 1,
                             "izquierda": base + 2, "derecha": base + 3},
                "alineacion_mm": {"vertical_izquierda": base,
                                  "vertical_dererecha": base + 1,
                                  "horizontal_arriba": base + 2,
                                  "horizontal_abajo": base + 3},
                "estado": {"ortogonal": True, "simetrico": True,
                           "alineado_horizontal": True,
                           "alineado_vertical": True, "torcido": False},
            }

        datos = {
            "cm_por_pixel": 0.1,
            "franjas": [{
                "anchura": {"horizontal": 10.0, "vertical": 20.0},
                "penumbra_izquierda": {"horizontal": 1.0, "vertical": 2.0},
                "penumbra_derecha": {"horizontal": 1.5, "vertical": 2.5},
                "excesos": [0.1, 0.2, 0.3, 0.4],
            }],
            "verificacion": {
                "verificacion_inicial": _verificacion(1.0),
                "verificacion_ideal": _verificacion(11.0),
                "correcciones": {"arriba_izq": {"Δx": 1.0, "Δy": 2.0}},
                "excesos_ideal": {"arriba_izq": 0.1, "arriba_der": 0.2,
                                  "abajo_izq": 0.3, "abajo_der": 0.4},
            },
        }
        assert guardar_analisis_placa600(952, datos) is True

    def test_devuelve_false_cuando_los_datos_no_sirven(self, app, bd_temporal):
        from data.ManejoDatos.load import guardar_analisis_placa600
        # Sin la clave `cm_por_pixel` la función revienta por dentro; lo que
        # importa es que el fallo llegue al llamador como False en vez de
        # confundirse con un guardado bueno.
        assert guardar_analisis_placa600(952, {}) is False


class TestIM4ElLectorQueNoExistia:

    def test_devuelve_la_imagen_del_bloque_vigente(self, app, bd_temporal, tmp_path):
        img = tmp_path / "placa.png"
        img.write_bytes(b"la imagen guardada")
        _guardar_imagen(bd_temporal, 952, img)

        assert imagen_vigente(952) == b"la imagen guardada"

    def test_ignora_las_generaciones_anuladas(self, app, bd_temporal, tmp_path):
        """La razón por la que el lector filtra `activo`: tras IM1 hay
        varias generaciones del mismo `ref`, y devolver una histórica
        mostraría al físico una imagen que él ya reemplazó."""
        for nombre in ("vieja", "nueva"):
            img = tmp_path / f"{nombre}.png"
            img.write_bytes(f"imagen {nombre}".encode())
            _guardar_imagen(bd_temporal, 952, img)

        assert imagen_vigente(952) == b"imagen nueva"

    def test_sin_imagen_devuelve_none(self, app, bd_temporal):
        con = sqlite3.connect(bd_temporal)
        con.execute("INSERT INTO preguntas (ref, iso_mec, activo) VALUES (952, 1.0, 1)")
        con.commit()
        con.close()
        assert imagen_vigente(952) is None

    def test_sin_fila_devuelve_none(self, app, bd_temporal):
        assert imagen_vigente(952) is None
