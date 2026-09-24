"""G.2 (PLAN_HANDOFF_IMAGENES_22-09.md): lector de la tabla de coeficientes de atenuación de los materiales
del CTP404 (`resources/archivos_json/poder_frenado_materiales.json`).

La tabla NO se edita a mano: la genera `scripts/generar_tabla_mu.py` (fuente NIST, regla de mezclas, μ = (μ/ρ)·ρ)
y una prueba exige que el JSON coincida con lo que ese script produce. Este módulo solo la LEE, y define en un
solo sitio cómo se llama la clave de cada energía, para que la aplicación y el script no puedan discrepar.

La energía de la linealidad de cada equipo no se elige: es la de su protocolo (`ProtocoloEquipo.
energia_linealidad_mev`, catálogo de `A.2`). Un equipo sin protocolo no tiene energía, y NO se inventa una.
"""
from __future__ import annotations

import json
import os
from typing import Optional

from analisisImagenes.catphan.protocolos import PROTOCOLOS

NOMBRE_ARCHIVO = "poder_frenado_materiales.json"   # el nombre histórico; lo que guarda es μ/ρ, ρ y μ


def clave_energia(energia_mev: float) -> str:
    """Clave del JSON para una energía: 0.12 -> 'energia_0.12MeV', 0.1 -> 'energia_0.1MeV'."""
    return f"energia_{energia_mev:g}MeV"


def energia_de_linealidad_mev(equipo: Optional[str]) -> Optional[float]:
    """La energía de la linealidad del `equipo` (su protocolo), o `None` si no tiene protocolo."""
    protocolo = PROTOCOLOS.get(equipo)
    if protocolo is None or not protocolo.energia_linealidad_mev:
        return None
    return protocolo.energia_linealidad_mev


def ruta_de_la_tabla() -> Optional[str]:
    """Busca `resources/archivos_json/<archivo>` subiendo desde este módulo (funciona en el repositorio y en
    el ejecutable empaquetado)."""
    base = os.path.dirname(os.path.abspath(__file__))
    for arriba in range(1, 6):
        candidata = os.path.abspath(os.path.join(base, *[".."] * arriba, "resources", "archivos_json",
                                                 NOMBRE_ARCHIVO))
        if os.path.exists(candidata):
            return candidata
    return None


def cargar_tabla(ruta: Optional[str] = None) -> dict:
    """El JSON completo. Lanza `FileNotFoundError` si no está y `ValueError` si no se puede leer."""
    ruta = ruta or ruta_de_la_tabla()
    if not ruta:
        raise FileNotFoundError(f"No se encontró el archivo de materiales {NOMBRE_ARCHIVO}")
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


def materiales_a_energia(energia_mev: float, ruta: Optional[str] = None) -> dict:
    """`{material: {'mu_rho', 'densidad', 'mu'}}` a esa energía. Lanza `KeyError` si la tabla no la trae:
    nunca se interpola ni se aproxima con otra energía en silencio."""
    tabla = cargar_tabla(ruta)
    clave = clave_energia(energia_mev)
    if clave not in tabla:
        raise KeyError(f"La tabla de materiales no tiene datos para {energia_mev:g} MeV ({clave})")
    return tabla[clave]
