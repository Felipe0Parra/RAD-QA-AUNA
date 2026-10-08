"""GI.4 (PLAN_REPARACIONES_IMAGENES_FISICOS_06-10.md): kV, mA y espesor de corte son OBLIGATORIOS para guardar una prueba de imagen (decision D1 del
fisico, 06-10), y esta es la UNICA definicion de de donde sale cada uno y de cuando no sirve.

Antes la guarda de la pantalla miraba los globales del ULTIMO volumen cargado (`kv_actual`, `ma_actual`, `espesor_corte_val`) con un unico aviso, y el escritor
(`guardar_prueba_completa_catphan`) usaba, por su cuenta, la adquisicion de la categoria o, si no la habia, los argumentos de la llamada: dos reglas distintas
para la misma pregunta. Con dos carpetas en una sesion la guarda pasaba cuando el escritor iba a reventar con `IntegrityError` (`pruebas.espesor_corte` es NOT
NULL) o bloqueaba datos completos. Aqui las dos cosas se contestan con la misma funcion: `evaluar_categoria`.

Sin Qt ni BD: la usan la pantalla, el escritor y la ventana de metadatos.

Regla de resolucion (la misma que ya aplicaba el escritor): si la prueba tiene SU adquisicion registrada (la del volumen con el que se corrio), los tres datos
salen de ella y de ninguna otra parte -- nunca se completa un dato que falta con el de otra carpeta; si no la tiene (llamadores anteriores, resultados reabiertos),
cuentan los globales. Un dato sirve si es un numero finito mayor que cero.
"""
import math
import numbers
from dataclasses import dataclass, field

DATOS = ("kv", "ma", "espesor_corte")

CAUSA_NO_PUBLICADO = "no_publicado"  # la serie no trae el dato (etiqueta ausente o vacia)
CAUSA_NO_VALIDO = "no_valido"        # la serie trae algo que no es un numero positivo (0, negativo, texto...)
CAUSA_SIN_SERIE = "sin_serie"        # no hay serie DICOM con la que se haya corrido la prueba

# Con la unidad entre corchetes (D.1 de PLAN_NAVEGACION_Y_UNIDADES_10-09.md) y sin género que choque con el verbo: el dato se llama por su magnitud.
_ROTULO = {"kv": "La tensión del tubo [kV]", "ma": "La corriente del tubo [mA]", "espesor_corte": "El espesor de corte [mm]"}


def _como_se_dice(valor) -> str:
    """El valor tal como lo leería una persona: un número sin comillas (pydicom entrega `DSfloat`/`IS`, cuyo `repr` lleva comillas: `'0.0'`); lo demás, su `repr`."""
    if isinstance(valor, numbers.Real) and not isinstance(valor, bool):
        return f"{float(valor):g}"
    return repr(valor)


def redondear_espesor(valor):
    """El espesor tal como se registra y se evalúa: a un decimal. Única definición: la usan `_parametros_de_volumen` (lo que se guarda con la prueba) y la ventana de
    metadatos (lo que avisa antes de analizar), para que no puedan decir cosas distintas de la misma serie."""
    return round(valor, 1) if isinstance(valor, numbers.Real) and not isinstance(valor, bool) else valor


ETIQUETA_PRUEBA = {
    "espesor": "Espesor de corte", "tamano_pixel": "Tamaño de píxel", "resolucion_contraste": "Resolución de contraste",
    "resolucion_espacial": "Resolución espacial", "valores_ct": "Valores CT", "linealidad_ct": "Linealidad CT", "uniformidad": "Uniformidad",
}


def etiqueta_de(categoria) -> str:
    """El nombre de la prueba tal como lo ve el físico (el de su pestaña); `None` = una prueba cualquiera."""
    if categoria is None:
        return "prueba de imagen"
    return ETIQUETA_PRUEBA.get(categoria, str(categoria).replace("_", " "))


class ParametrosObligatoriosFaltantes(Exception):
    """El escritor se niega a guardar pruebas cuyo kV, mA o espesor no sirven. El mensaje es el que se le dice al fisico."""


@dataclass(frozen=True)
class Faltante:
    dato: str            # uno de DATOS (o "serie")
    causa: str           # NO_PUBLICADO | NO_VALIDO | SIN_SERIE
    valor: object = None

    def texto(self, serie: str = "la serie con la que se corrió esta prueba") -> str:
        """Lo que se le dice al físico. `serie` es cómo nombrar la serie en la frase (la guarda dice la de la prueba; la ventana, la que se acaba de cargar)."""
        if self.causa == CAUSA_SIN_SERIE:
            return ("No hay una serie DICOM cargada con la que se haya corrido esta prueba; "
                    "cargue la carpeta y repita el análisis.")
        rotulo = _ROTULO[self.dato]
        if self.causa == CAUSA_NO_PUBLICADO:
            return f"{rotulo}: {serie} no publica este dato; es obligatorio para guardar."
        return f"{rotulo}: {serie} publica {_como_se_dice(self.valor)}, que no es un valor válido; es obligatorio para guardar."


@dataclass(frozen=True)
class Parametros:
    kv: object
    ma: object
    espesor_corte: object
    origen: str                          # "categoria" | "globales"
    faltantes: tuple = field(default_factory=tuple)

    @property
    def completo(self) -> bool:
        return not self.faltantes


def sirve(valor) -> bool:
    """Un numero finito mayor que cero (un `bool` no es un numero aqui)."""
    return (isinstance(valor, numbers.Real) and not isinstance(valor, bool)
            and math.isfinite(valor) and valor > 0)


def faltantes_de(kv, ma, espesor_corte, hay_serie: bool = True) -> tuple:
    """Los datos que no sirven, en orden kV, mA, espesor. Con `hay_serie=False` y nada que evaluar: un unico `SIN_SERIE`."""
    valores = {"kv": kv, "ma": ma, "espesor_corte": espesor_corte}
    if not hay_serie and all(v is None for v in valores.values()):
        return (Faltante("serie", CAUSA_SIN_SERIE),)
    resultado = []
    for dato in DATOS:
        valor = valores[dato]
        if valor is None:
            resultado.append(Faltante(dato, CAUSA_NO_PUBLICADO))
        elif not sirve(valor):
            resultado.append(Faltante(dato, CAUSA_NO_VALIDO, valor))
    return tuple(resultado)


def evaluar_categoria(categoria, adquisicion_por_categoria, kv=None, ma=None, espesor_corte=None) -> Parametros:
    """kV, mA y espesor con los que se guardaria la prueba `categoria`, de donde salieron y cuales no sirven.

    `adquisicion_por_categoria`: `{categoria: {"kv", "ma", "espesor_corte", ...}}` (lo que registra `_registrar_adquisicion`). `kv`, `ma` y `espesor_corte`:
    los globales / argumentos de la llamada, que solo cuentan si la prueba no tiene su adquisicion."""
    propia = (adquisicion_por_categoria or {}).get(categoria)
    if propia:
        kv_c, ma_c, esp_c = propia.get("kv"), propia.get("ma"), propia.get("espesor_corte")
        return Parametros(kv_c, ma_c, esp_c, "categoria", faltantes_de(kv_c, ma_c, esp_c))
    return Parametros(kv, ma, espesor_corte, "globales", faltantes_de(kv, ma, espesor_corte, hay_serie=False))


def aviso_de_faltantes(parametros: Parametros, etiqueta_prueba: str) -> str:
    """El texto que se le dice al físico cuando la prueba `etiqueta_prueba` no se puede guardar: nombra cada dato y su causa, y qué hacer."""
    lineas = "\n".join(f"  - {f.texto()}" for f in parametros.faltantes)
    cola = "" if any(f.causa == CAUSA_SIN_SERIE for f in parametros.faltantes) else (
        "\n\nRepita el análisis con una serie que publique estos datos.")
    return f"No se puede guardar la prueba «{etiqueta_prueba}»:\n{lineas}{cola}"
