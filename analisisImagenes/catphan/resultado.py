"""B.1 (PLAN_CATPHAN_AUTOMATICO_POR_EQUIPO_18-09.md): estructuras de
resultado del motor -- cada número lleva su unidad explícita, sin
ambigüedad de qué representa (D-15: dos definiciones de rango de HU;
D-20: `resolucion_espacial` mezcla lp/mm y lp/cm en la misma columna;
D-21: `error_relativo` mezcla número y texto).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Metrica:
    nombre: str
    valor: Optional[float]
    unidad: str


@dataclass
class ResultadoModulo:
    modulo: str
    corte_indice: Optional[int]
    corte_z_mm: Optional[float]
    sop_uid: Optional[str]
    metricas: dict  # {nombre: Metrica}
    imagen_png: Optional[bytes] = None


@dataclass
class ResultadoCatphan:
    equipo_detectado: Optional[str]
    orientacion: str  # 'normal' | 'invertido'
    roll_deg: Optional[float]
    origen_indice: Optional[int]
    modulos: dict  # {'CTP404': ResultadoModulo, 'CTP486': ..., 'CTP515': ..., 'CTP528': ...}
    version_motor: str
    advertencias: list = field(default_factory=list)

    def metrica(self, modulo: str, nombre: str) -> Optional[Metrica]:
        """Atajo: `resultado.metrica('CTP404', 'espesor_mm')`."""
        mod = self.modulos.get(modulo)
        if mod is None:
            return None
        return mod.metricas.get(nombre)
