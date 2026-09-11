"""C.1 (PLAN_NAVEGACION_Y_UNIDADES_10-09.md §4): el código del formato
oficial (code_1, p.ej. "IDC-F-RT-118") y su versión (code_2, p.ej. "V.04")
ya están declarados por pantalla en data/widgets.xlsx y se muestran en la
UI -- el PDF los tiraba (mensual/anual, que ni siquiera pasaban
`id_maquina`) o los truncaba (diario, sin la versión). Una función única
en vez de repetir `self.code_1.text()` en cada sitio.
"""


def codigo_de_formato(pantalla):
    """Código de formato + versión, unidos ("IDC-F-RT-118 V.04"), leídos
    de los widgets `code_1`/`code_2` de la pantalla que llama. Algunas
    pantallas (TAC, las hojas de imágenes) no declaran esos widgets en
    widgets.xlsx -- para ellas se devuelve cadena vacía, exactamente como
    el reporte se veía antes de esta tarea, no se inventa nada."""
    code_1 = getattr(pantalla, "code_1", None)
    code_2 = getattr(pantalla, "code_2", None)
    texto_1 = code_1.text().strip() if code_1 is not None else ""
    texto_2 = code_2.text().strip() if code_2 is not None else ""
    if texto_1 and texto_2:
        return f"{texto_1} {texto_2}"
    return texto_1
