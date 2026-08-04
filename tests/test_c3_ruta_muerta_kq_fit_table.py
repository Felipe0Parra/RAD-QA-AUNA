"""C3 (PLAN_NUCLEO_04-08.md §Bloque C): blindar la ruta muerta de
`Q0_FIT_TABLE`/`KQ_TPR2010_BASED`.

Hallazgo D1-H2 (2026-07-07, aún vigente): ocho filas de `Q0_FIT_TABLE`
(`calculadora_dosis_Tablas.py`) tienen copiados los coeficientes a/b de
`Q0_TABLE` -- si algún día se conectara `KQ_TPR2010_BASED`/`get_ab` a la UI
en vez de `interpolar_kq0` (que usa `KQ_TPR_TABLE`, la ruta real), daría un
kQ≈1.105 en vez de ≈0.99: un error de dosis de ~11%. No hay coeficientes a/b
reales publicados con los que corregir la tabla (verificado contra las dos
versiones de TRS-398), así que no se corrige el dato -- se blinda la ruta.

Este test no repara nada: solo garantiza que nadie vuelva a cablear
`get_ab`/`KQ_TPR2010_BASED` en una ruta alcanzable desde producción. Si
alguna vez hace falta conectarla de verdad, hará falta antes resolver
D1-H2 (los coeficientes a/b reales) y entonces se ajusta/retira este test a
propósito -- no se lo debe silenciar sin esa corrección.

Alcance: todo el código de producción de `Codigo_radqa/` (excluidos
tests/build/venv/recursos), salvo los dos archivos donde la función
DEFINE su propia implementación dormida
(`services/dosis_service_calculations.py`, `services/dosis_service.py`) --
ahí `get_ab` llama a `KQ_TPR2010_BASED` como parte de su propio cuerpo, eso
es la definición inerte, no un cableado a producción.
"""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXCLUDE_DIRS = {
    ".venv", "tests", "build", "__pycache__", ".git", ".pytest_cache",
    "resources", "models", "mcc_PTW_read",
}
NOMBRES_PROHIBIDOS = {"get_ab", "KQ_TPR2010_BASED"}
ARCHIVOS_DEFINICION = {
    ROOT / "services" / "dosis_service_calculations.py",
    ROOT / "services" / "dosis_service.py",
}


def _archivos_produccion():
    for path in ROOT.rglob("*.py"):
        if any(parte in EXCLUDE_DIRS for parte in path.parts):
            continue
        yield path


def _nombre_llamado(node):
    """Nombre simple de la función/método invocada en un ast.Call, sin
    resolver el objeto (cubre tanto `get_ab(...)` como `DosisService.
    get_ab(...)` / `algo.get_ab(...)`)."""
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _llamadas_prohibidas(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    hallazgos = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            nombre = _nombre_llamado(node)
            if nombre in NOMBRES_PROHIBIDOS:
                hallazgos.append((nombre, node.lineno))
    return hallazgos


class TestRutaMuertaKqFitTableBlindada:
    def test_get_ab_y_kq_tpr2010_based_no_se_llaman_fuera_de_su_definicion(self):
        violaciones = []
        for path in _archivos_produccion():
            if path.resolve() in ARCHIVOS_DEFINICION:
                continue
            for nombre, lineno in _llamadas_prohibidas(path):
                violaciones.append(f"{path.relative_to(ROOT)}:{lineno} llama a {nombre}(...)")

        assert not violaciones, (
            "get_ab()/KQ_TPR2010_BASED() se están llamando fuera de su "
            "definición dormida -- D1-H2 sigue sin resolver (8 filas de "
            "Q0_FIT_TABLE con coeficientes a/b copiados de Q0_TABLE, "
            "kQ≈1.105 en vez de ≈0.99, ~11% de error de dosis). Antes de "
            "cablear esta ruta hay que resolver D1-H2. Hallazgos:\n"
            + "\n".join(violaciones)
        )

    def test_produccion_sigue_usando_interpolar_kq0_no_get_ab(self):
        """Ancla positiva: la ruta REAL (interpolar_kq0, vía KQ_TPR_TABLE)
        sigue siendo la que usa la calculadora -- si este assert falla junto
        con el anterior, alguien migró la UI a la ruta muerta a propósito y
        hay que revisar D1-H2 antes de aceptar el cambio."""
        dialogs = ROOT / "ui" / "paginasGuia" / "dialogs.py"
        texto = dialogs.read_text(encoding="utf-8")
        assert "interpolar_kq0" in texto
