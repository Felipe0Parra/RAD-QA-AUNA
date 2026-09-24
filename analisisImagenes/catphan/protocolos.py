"""A.2 (PLAN_HANDOFF_IMAGENES_22-09.md, ajuste 23-09): el protocolo de
adquisición FIJO de cada equipo de imagen, y la comparación contra lo que
dice el DICOM.

Qué es un "protocolo" aquí (§0.8): un dato DECLARADO. La aplicación no se
adapta al protocolo que traigan las imágenes -- eso rompería la
reproducibilidad por equipo --; hace tres cosas: lo declara antes de adquirir
(`G.1`), lo compara al cargar (`A.3`) y deja escrita la desviación con la
prueba (`pruebas.desviacion_protocolo`, `E.2`). **Fuera de protocolo NO
bloquea**: la toma no la controla la aplicación (palabras del físico); se
puede analizar, pero el resultado queda marcado como no comparable con la
línea base en vez de mezclarse con ella en silencio.

Dónde vive: versionado, junto a `perfiles.py` y con la misma forma (un
registro por equipo, mismas claves). El físico decidió el 23-09 que el
protocolo es fijo y que cambiarlo corta la línea base, así que cambiarlo tiene
que ser un acto deliberado, revisado y fechado -- un commit con su motivo --,
igual que los umbrales de `perfiles.py` (principio del plan del 18-09: *lo
normativo, versionado; las líneas base, en la BD*).

Un solo catálogo, varios consumidores: `A.2` (la guarda, este archivo), `A.3`
(la ventana de metadatos), `G.1` (el encabezado), `G.2` (la energía de la
linealidad), `B.3` (el corrimiento de escala) y `E.2` (el PDF). Ninguno copia
un valor: todos leen la misma fila, así que no pueden discrepar entre sí.

`test_a2_protocolos_por_equipo.py` es el censo obligatorio: si un equipo de
`perfiles.PERFILES` queda sin protocolo, o un campo comparado sin regla, un
test falla.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from analisisImagenes.catphan.serie import identificar_equipo_por_datos

# Los campos que se comparan, en el orden en que se muestran. `campo` es la
# clave de `serie.adquisicion_de_serie` Y el atributo homónimo de
# `ProtocoloEquipo` -- un solo nombre, para que no haya una tabla de
# traducción que pueda desincronizarse.
#
#   (grupo, campo, etiqueta que ve el físico, ¿numérico?)
#
# Las unidades van entre corchetes (regla del 10-09, `DP-96`).
CAMPOS_COMPARADOS = (
    ("identidad", "modelo", "Modelo", False),
    ("identidad", "estacion", "Estación", False),
    ("adquisicion", "descripcion_serie", "Protocolo (descripción de la serie)", False),
    ("adquisicion", "kv", "kV", True),
    ("adquisicion", "ma", "mA", True),
    ("adquisicion", "mas", "mAs", True),
    ("adquisicion", "espesor_mm", "Espesor de corte [mm]", True),
    ("adquisicion", "fov_mm", "FOV [mm]", True),
    ("adquisicion", "kernel", "Kernel", False),
    ("adquisicion", "filtro", "Filtro", False),
)

# Dónde salió cada valor, y cuándo -- la misma trazabilidad que `referencias_qc`.
_ORIGEN = (
    "Decisión del físico del 23-09-2026 (§0.8 de PLAN_HANDOFF_IMAGENES_22-09.md): "
    "valores medidos de los encabezados DICOM de {serie}."
)

_POSICION_FANTOMA = (
    "en posición estándar, la misma en los tres equipos (sin invertir 180°)"
)
_CONDICION_POSICION = (
    "confirmar la posición del fantoma, igual en los tres equipos "
    "(la serie del Halcyon del 12-09 se adquirió invertida 180°)"
)


@dataclass(frozen=True)
class ProtocoloEquipo:
    """La fila del catálogo de un equipo de imagen. Un valor `None` en un
    campo comparado significa "el equipo no lo publica: no se exige" (el iX no
    trae `SeriesDescription` ni `FilterType`), no "cualquier valor vale"."""

    equipo: str  # 'Tomógrafo' | 'Clinac ix' | 'Halcyon' -- EXACTO (= perfiles.PERFILES)

    # --- identidad esperada: lo que el DICOM debe decir ---------------------
    fabricante: str
    modelo: str
    estacion: str
    numero_serie_equipo: str  # informativo: una consola reemplazada puede cambiarlo

    # --- protocolo de adquisición (mismas claves que `adquisicion_de_serie`) -
    descripcion_serie: Optional[str]  # SeriesDescription; None si el equipo no lo publica
    kv: float
    ma: float
    mas: float
    espesor_mm: float
    fov_mm: float
    kernel: Optional[str]
    filtro: Optional[str]

    # --- tolerancia por campo; lo que no figura es EXACTO -------------------
    # mA y mAs exactos porque ningún protocolo elegido modula la corriente
    # [medido: `XRayTubeCurrent` constante en las 380 imágenes del tomógrafo];
    # si algún día lo hace, la tolerancia se escribe AQUÍ, no en el código.
    tolerancias: dict = field(default_factory=dict)

    # --- otros consumidores del mismo catálogo ------------------------------
    energia_linealidad_mev: float = 0.0  # G.2
    corrimiento_hu_esperado: float = 0.0  # B.3 (≈ +490 en el iX, ≈ 0 en los otros)
    corrimiento_hu_tolerancia: float = 30.0  # B.3
    posicion_fantoma: str = _POSICION_FANTOMA  # G.1
    condiciones_pendientes: tuple = ()  # G.1: condiciones de consola SIN confirmar
    origen: str = ""


PROTOCOLO_TOMOGRAFO = ProtocoloEquipo(
    equipo="Tomógrafo",
    fabricante="Siemens Healthineers",
    modelo="SOMATOM go.Sim",
    estacion="CT128260",
    numero_serie_equipo="128260",
    descripcion_serie="RT_CABEZA 2,00 Qr40 S2",
    kv=120.0,
    ma=200,
    mas=250,
    espesor_mm=2.0,
    fov_mm=550.0,
    kernel="Qr40f",
    filtro="W1",
    tolerancias={"espesor_mm": 0.05, "fov_mm": 1.0},
    energia_linealidad_mev=0.120,
    corrimiento_hu_esperado=0.0,
    condiciones_pendientes=(_CONDICION_POSICION,),
    origen=_ORIGEN.format(serie="`QA tomografo Catphan` (adquirida el 2026-08-31)"),
)

PROTOCOLO_HALCYON = ProtocoloEquipo(
    equipo="Halcyon",
    fabricante="Varian Medical Systems",
    modelo="Halcyon - PVA",
    estacion="Halcyon",
    numero_serie_equipo="1161",
    descripcion_serie="Pelvis_iCBCT_2.0_IQ!",
    kv=125.0,
    ma=80,
    mas=1074,
    espesor_mm=2.0,
    fov_mm=491.0,
    # El Halcyon deja `ConvolutionKernel` en la cadena 'None' y publica su
    # filtro en `FilterType`: el kernel no se exige, el filtro sí.
    kernel=None,
    filtro="Tit V2,HF V2",
    tolerancias={"espesor_mm": 0.05, "fov_mm": 1.0},
    energia_linealidad_mev=0.125,
    corrimiento_hu_esperado=0.0,
    condiciones_pendientes=(
        "confirmar que 'Pelvis_iCBCT_2.0_IQ!' está guardado en la lista de protocolos "
        "de la consola y, si la consola lo permite, protegido contra edición",
        _CONDICION_POSICION,
    ),
    origen=_ORIGEN.format(serie="`QA Halcyon Catphan` (adquirida el 2026-09-12)"),
)

PROTOCOLO_CLINAC_IX = ProtocoloEquipo(
    equipo="Clinac ix",
    fabricante="Varian Medical Systems",
    modelo="OBI Cone-beam CT",
    estacion="IX5005",
    numero_serie_equipo="505",
    # El iX no publica `SeriesDescription` ni `FilterType` [medido]: no se exigen.
    descripcion_serie=None,
    kv=100.0,
    ma=80,
    mas=724,
    espesor_mm=2.5,
    fov_mm=250.0,
    kernel="Ram-Lak",
    filtro=None,
    tolerancias={"espesor_mm": 0.05, "fov_mm": 1.0},
    energia_linealidad_mev=0.100,
    # El OBI entrega números de CBCT, no HU: fondo ≈ +490 donde debería ser ≈ 0
    # [medido]; en la sesión 30 otro preset dio ≈ −410 (§0.10.1).
    corrimiento_hu_esperado=490.0,
    condiciones_pendientes=(
        "confirmar el nombre del preset del OBI que da 100 kV / 80 mA / full-fan "
        "(coincide con 'High-Quality Head' [inferido]; el DICOM no trae el nombre)",
        _CONDICION_POSICION,
    ),
    origen=_ORIGEN.format(serie="`Catphandiciembre` (adquirida el 2025-12-14)"),
)

PROTOCOLOS = {
    "Tomógrafo": PROTOCOLO_TOMOGRAFO,
    "Clinac ix": PROTOCOLO_CLINAC_IX,
    "Halcyon": PROTOCOLO_HALCYON,
}


@dataclass(frozen=True)
class FilaProtocolo:
    """Una fila de la comparación, tal como la muestra la ventana de `A.3`.

    `cumple` es `True`/`False`, o `None` cuando la fila no se evalúa porque el
    protocolo no exige ese dato (el equipo no lo publica)."""

    grupo: str  # 'identidad' | 'adquisicion'
    campo: str
    etiqueta: str
    esperado: object
    encontrado: object
    tolerancia: float
    cumple: Optional[bool]


# El rótulo del aviso, con UNA sola definición: lo usa el texto que se archiva
# con cada prueba y el título de la confirmación de la ventana de A.3.
ROTULO_FUERA_DE_PROTOCOLO = "Adquisición fuera de protocolo"

# Estados de la identidad (`ComparacionProtocolo.identidad`):
COINCIDE = "coincide"                # el DICOM es del equipo seleccionado
OTRO_EQUIPO = "otro_equipo"          # el DICOM es de otro equipo conocido
NO_IDENTIFICADO = "no_identificado"  # el DICOM no es de ningún equipo conocido
SIN_PROTOCOLO = "sin_protocolo"      # el equipo seleccionado no tiene protocolo de imagen
SIN_EQUIPO = "sin_equipo"            # no hay equipo seleccionado con el que comparar


@dataclass(frozen=True)
class ComparacionProtocolo:
    equipo_seleccionado: Optional[str]
    equipo_identificado: Optional[str]
    identidad: str
    filas: tuple
    advertencia_identidad: Optional[str] = None
    protocolo: Optional[ProtocoloEquipo] = None
    # descripción cruda del DICOM, para poder nombrar "de qué equipo son las
    # imágenes" cuando no coincide
    imagenes_de: str = ""

    @property
    def fuera_de_protocolo(self) -> list:
        """Filas de adquisición que no cumplen (las de identidad se reportan
        aparte: si el equipo es otro, el protocolo del seleccionado no aplica)."""
        return [f for f in self.filas if f.grupo == "adquisicion" and f.cumple is False]

    def desviacion_texto(self) -> Optional[str]:
        """El texto que se archiva en `pruebas.desviacion_protocolo`, o `None`
        si no hay nada que archivar (identidad coincide y todo cumple).

        Una sola línea, en el idioma del físico y sin símbolos (`DA-18`)."""
        if self.identidad == SIN_EQUIPO:
            return None
        if self.identidad == SIN_PROTOCOLO:
            return (f"El equipo seleccionado ({self.equipo_seleccionado!r}) no tiene "
                    f"protocolo de imagen en el catálogo: no hay con qué comparar")
        if self.identidad == OTRO_EQUIPO:
            return (f"Las imágenes son de {self.imagenes_de} (equipo identificado: "
                    f"{self.equipo_identificado}) y se seleccionó {self.equipo_seleccionado}")
        if self.identidad == NO_IDENTIFICADO:
            return (f"Las imágenes son de un equipo no reconocido ({self.imagenes_de}); "
                    f"no se pudo comparar con el protocolo de {self.equipo_seleccionado}")
        lineas = []
        if self.advertencia_identidad:
            lineas.append(f"Identidad: {self.advertencia_identidad}")
        if self.fuera_de_protocolo:
            lineas.append(ROTULO_FUERA_DE_PROTOCOLO + ": "
                          + "; ".join(_texto_fila(f) for f in self.fuera_de_protocolo))
        return ". ".join(lineas) if lineas else None


def _fmt(valor) -> str:
    if valor is None:
        return "no publicado"
    if isinstance(valor, float):
        return str(int(valor)) if valor == int(valor) else f"{valor:g}"
    return str(valor)


def texto_exigido(f: FilaProtocolo) -> str:
    """Lo que el protocolo exige en esa fila, con su tolerancia si la tiene."""
    if f.esperado is None:
        return "no se exige"
    return _fmt(f.esperado) + (f" ± {_fmt(f.tolerancia)}" if f.tolerancia else "")


def texto_encontrado(f: FilaProtocolo) -> str:
    """Lo que dice el DICOM en esa fila ('no publicado' si falta)."""
    return _fmt(f.encontrado)


def _texto_fila(f: FilaProtocolo) -> str:
    return f"{f.etiqueta}: {texto_encontrado(f)} (exigido {texto_exigido(f)})"


def _cumple(esperado, encontrado, tolerancia: float, numerico: bool) -> Optional[bool]:
    if esperado is None:
        return None  # el protocolo no lo exige
    if encontrado is None:
        return False  # se exige y el DICOM no lo publica: no se puede verificar
    if numerico:
        try:
            return abs(float(encontrado) - float(esperado)) <= float(tolerancia) + 1e-9
        except (TypeError, ValueError):
            return False  # un valor que no es número no puede cumplir un valor numérico
    return str(encontrado).strip() == str(esperado).strip()


def comparar_con_protocolo(equipo_seleccionado: Optional[str], adquisicion: Optional[dict]) -> ComparacionProtocolo:
    """Compara la adquisición de una serie contra el protocolo del equipo
    seleccionado. Función pura: ni lee archivos ni toca la BD.

    `adquisicion` es el diccionario de `serie.adquisicion_de_serie` (o el JSON
    guardado en `pruebas.adquisicion_dicom`, que tiene las mismas claves).

    Nunca bloquea ni lanza por un equipo desconocido: un equipo que no está en
    el catálogo devuelve `SIN_PROTOCOLO`, uno que no se reconoce `NO_IDENTIFICADO`
    -- "advertir sin bloquear" (el mapa no puede ser una constante que impida
    trabajar el día que entre otro acelerador).
    """
    adq = adquisicion or {}
    imagenes_de = " / ".join(str(p) for p in (adq.get("modelo"), adq.get("estacion")) if p) or "equipo sin identificar"

    if not equipo_seleccionado:
        return ComparacionProtocolo(equipo_seleccionado, None, SIN_EQUIPO, (), imagenes_de=imagenes_de)

    protocolo = PROTOCOLOS.get(equipo_seleccionado)
    identificado, advertencia = identificar_equipo_por_datos(
        adq.get("fabricante"), adq.get("modelo"), adq.get("numero_serie_equipo"), adq.get("estacion"))

    if protocolo is None:
        return ComparacionProtocolo(equipo_seleccionado, identificado, SIN_PROTOCOLO, (),
                                    advertencia, None, imagenes_de)

    filas = []
    for grupo, campo, etiqueta, numerico in CAMPOS_COMPARADOS:
        esperado = getattr(protocolo, campo)
        encontrado = adq.get(campo)
        tolerancia = protocolo.tolerancias.get(campo, 0.0)
        filas.append(FilaProtocolo(grupo, campo, etiqueta, esperado, encontrado, tolerancia,
                                   _cumple(esperado, encontrado, tolerancia, numerico)))

    if identificado is None:
        identidad = NO_IDENTIFICADO
    elif identificado != equipo_seleccionado:
        identidad = OTRO_EQUIPO
    else:
        identidad = COINCIDE
        # Mismo equipo por fabricante+modelo, pero la estación (u otro dato de
        # identidad) no es la registrada: probablemente una consola renombrada.
        # Se advierte, no se calla, aunque la regla de identificación (que
        # tolera serie/estación) no haya generado texto.
        fallos = [f for f in filas if f.grupo == "identidad" and f.cumple is False]
        if fallos and not advertencia:
            advertencia = "; ".join(_texto_fila(f) for f in fallos)
    return ComparacionProtocolo(equipo_seleccionado, identificado, identidad, tuple(filas),
                                advertencia, protocolo, imagenes_de)
