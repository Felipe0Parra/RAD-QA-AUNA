"""C3 (PLAN_AUDITORIA_DOS_EJES_21-07.md §7.3/§7.7a): el físico en jefe
(lamaya) tiene permisos administrativos idénticos a admin."""
from services.permisos import es_admin_equivalente, USUARIOS_ADMIN_EQUIVALENTE


class TestEsAdminEquivalente:

    def test_admin_es_equivalente(self):
        assert es_admin_equivalente("admin") is True

    def test_lamaya_es_equivalente(self):
        assert es_admin_equivalente("lamaya") is True

    def test_otros_fisicos_no_son_equivalentes(self):
        for u in ("accastellanos", "adloaiza", "dmesa", "jjcastillo", "JADIAZ"):
            assert es_admin_equivalente(u) is False, u

    def test_tolera_mayusculas_y_espacios(self):
        assert es_admin_equivalente("LAMAYA") is True
        assert es_admin_equivalente(" admin ") is True

    def test_none_y_vacio_no_lanzan_y_no_son_equivalentes(self):
        assert es_admin_equivalente(None) is False
        assert es_admin_equivalente("") is False

    def test_conjunto_no_crece_por_accidente(self):
        assert USUARIOS_ADMIN_EQUIVALENTE == {"admin", "lamaya"}
