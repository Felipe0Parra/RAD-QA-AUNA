"""Las pruebas no dejan sus copias en el disco: `pytest.ini` borra el `tmp_path` de cada prueba que pasa y conserva el de la que falla.

El 25-11-2026 la suite repartida llegó a 30 GB en /tmp: cada prueba copia la base (86 MB) y pytest guardaba las copias hasta el final del proceso."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

PRUEBAS = '''
def test_pasa(tmp_path):
    (tmp_path / "copia.db").write_bytes(b"x" * 1024)


def test_falla(tmp_path):
    (tmp_path / "copia.db").write_bytes(b"x" * 1024)
    assert False
'''


def test_la_configuracion_de_la_suite_borra_los_temporales_de_las_pruebas_que_pasan(pytestconfig):
    assert pytestconfig.getini("tmp_path_retention_policy") == "failed"


def test_con_el_pytest_ini_del_repositorio_la_que_pasa_no_deja_su_copia_y_la_que_falla_si(tmp_path):
    proyecto = tmp_path / "proyecto"
    (proyecto / "tests").mkdir(parents=True)
    shutil.copy2(RAIZ / "pytest.ini", proyecto / "pytest.ini")
    (proyecto / "tests" / "test_copias.py").write_text(PRUEBAS, encoding="utf-8")
    base = tmp_path / "base"
    entorno = {k: v for k, v in os.environ.items() if k != "PYTEST_ADDOPTS"}
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-c", str(proyecto / "pytest.ini"),
                        "--rootdir", str(proyecto), "--basetemp", str(base)], cwd=proyecto, env=entorno, capture_output=True, text=True, timeout=120)
    assert "1 failed, 1 passed" in r.stdout, r.stdout + r.stderr
    assert sorted(p.name for p in base.iterdir() if p.is_dir() and not p.is_symlink()) == ["test_falla0"]
    assert (base / "test_falla0" / "copia.db").is_file()
