"""G.2 (PLAN_HANDOFF_IMAGENES_22-09.md): genera la tabla de coeficientes de atenuación de los materiales del
CTP404, `resources/archivos_json/poder_frenado_materiales.json`, desde UNA fuente y con UNA fórmula.

QUÉ ES ESA TABLA. Para la prueba de linealidad del número CT la aplicación necesita, por cada material del módulo
CTP404 y por cada energía, el coeficiente lineal de atenuación μ [1/cm] contra el que se ajusta el HU medido.
Antes eran siete filas tecleadas a mano, una sola energía (0.12 MeV) y tres filas donde μ ≠ (μ/ρ)·ρ: el aire
(0.145 × 0.0013 = 0.00019, decía 0.00089), el LDPE (0.164 × 0.92 = 0.151, decía 0.136: el valor del PMP copiado) y el
Delrin (0.154 × 1.42 = 0.219, decía 0.213). El nombre de la clave, `poder_frenado`, tampoco era el de lo que
guardaba: un coeficiente MÁSICO de atenuación.

MÉTODO (el que se ve aquí, sin caja negra):
  1. μ/ρ de cada ELEMENTO [cm²/g] = NIST, Hubbell y Seltzer (1995), NISTIR 5632, Tabla 3
     (https://physics.nist.gov/PhysRefData/XrayMassCoef/tab3.html), copiado abajo a 80, 100, 150 y 200 keV.
  2. μ/ρ del MATERIAL = regla de mezclas, Σ wᵢ·(μ/ρ)ᵢ, con las fracciones en masa wᵢ que salen de la fórmula
     química y de los pesos atómicos estándar (o, para el aire, de la composición del aire seco de NIST).
  3. μ/ρ a la energía pedida = interpolación log-log entre las dos energías tabuladas que la rodean (la que
     recomienda NIST). Las energías salen de `analisisImagenes/catphan/protocolos.py`: la energía de la linealidad
     de cada equipo es la de su protocolo (E [keV] = kVp, convención de constancia, no la energía efectiva).
  4. μ [1/cm] = (μ/ρ) · ρ, con ρ la densidad nominal del material del CTP404 (las que ya usaba la tabla).

CONTROL. `verificar_contra_compuestos()` compara la regla de mezclas con las tablas de COMPUESTOS de NIST (Tabla 4:
polietileno, poliestireno, PMMA, Teflón, aire seco), copiadas abajo, a 100 y 150 keV. Y `--verificar` regenera la
tabla en memoria y falla si el JSON del repositorio no es exactamente lo que sale de aquí: nadie edita el JSON a mano.

USO (desde `Codigo_radqa/`, sin red y sin dependencias fuera de la biblioteca estándar):
    python scripts/generar_tabla_mu.py             # escribe el JSON
    python scripts/generar_tabla_mu.py --verificar # falla si el JSON no coincide con lo generado
"""
from __future__ import annotations

import json
import math
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from analisisImagenes.catphan.atenuacion import clave_energia  # noqa: E402  (una sola definición de la clave)

RUTA_JSON = RAIZ / "resources" / "archivos_json" / "poder_frenado_materiales.json"

FUENTE = ("NIST XCOM / Hubbell y Seltzer (1995), 'Tables of X-Ray Mass Attenuation Coefficients and Mass "
          "Energy-Absorption Coefficients', NISTIR 5632, Tabla 3 (elementos) y Tabla 4 (compuestos, solo control). "
          "https://physics.nist.gov/PhysRefData/XrayMassCoef/ ; datos copiados el 24-09-2026.")

# ---------------------------------------------------------------------------
# μ/ρ de los ELEMENTOS [cm²/g], NIST Tabla 3, por energía [keV]
# ---------------------------------------------------------------------------
MU_RHO_ELEMENTOS = {
    "H":  {80: 0.3091, 100: 0.2944, 150: 0.2651, 200: 0.2429},
    "C":  {80: 0.1610, 100: 0.1514, 150: 0.1347, 200: 0.1229},
    "N":  {80: 0.1639, 100: 0.1529, 150: 0.1353, 200: 0.1233},
    "O":  {80: 0.1678, 100: 0.1551, 150: 0.1361, 200: 0.1237},
    "F":  {80: 0.1639, 100: 0.1496, 150: 0.1298, 200: 0.1176},
    "Ar": {80: 0.2760, 100: 0.2043, 150: 0.1427, 200: 0.1205},
}

# Pesos atómicos estándar [g/mol] (IUPAC)
PESOS_ATOMICOS = {"H": 1.00794, "C": 12.0107, "N": 14.0067, "O": 15.9994, "F": 18.9984032, "Ar": 39.948}

# ---------------------------------------------------------------------------
# Los siete materiales del CTP404, EN EL ORDEN DE LA TABLA DE LA PANTALLA
# ---------------------------------------------------------------------------
# `formula` = átomos por unidad de fórmula; `fracciones_masa` = composición dada directamente (aire seco de NIST).
# `densidad` [g/cm³] = nominal del CTP404, la que ya usaba la tabla anterior (no se cambia aquí).
# PMP y LDPE tienen la MISMA composición (CH2): comparten μ/ρ y difieren solo en la densidad. Eso es lo que la
# tabla anterior olvidó al copiar el μ del PMP en el LDPE.
MATERIALES = {
    "Aire":         {"fracciones_masa": {"C": 0.000124, "N": 0.755268, "O": 0.231781, "Ar": 0.012827},
                     "densidad": 0.0013, "composicion": "aire seco, NIST"},
    "PMP":          {"formula": {"C": 1, "H": 2}, "densidad": 0.83, "composicion": "(C6H12)n = CH2"},
    "LDPE":         {"formula": {"C": 1, "H": 2}, "densidad": 0.92, "composicion": "(C2H4)n = CH2"},
    "Poliestireno": {"formula": {"C": 1, "H": 1}, "densidad": 1.03, "composicion": "(C8H8)n = CH"},
    "Acrilico":     {"formula": {"C": 5, "H": 8, "O": 2}, "densidad": 1.18, "composicion": "PMMA, C5H8O2"},
    "Delrin":       {"formula": {"C": 1, "H": 2, "O": 1}, "densidad": 1.42, "composicion": "POM, CH2O"},
    "Teflon":       {"formula": {"C": 2, "F": 4}, "densidad": 2.16, "composicion": "PTFE, C2F4"},
}

# ---------------------------------------------------------------------------
# Solo para CONTROLAR la regla de mezclas: μ/ρ de COMPUESTOS [cm²/g], NIST Tabla 4
# ---------------------------------------------------------------------------
COMPUESTOS_NIST = {   # material del CTP404 -> {keV: μ/ρ}
    "Aire":         {100: 0.1541, 150: 0.1356},   # aire seco
    "PMP":          {100: 0.1719, 150: 0.1534},   # polietileno (misma composición, CH2)
    "LDPE":         {100: 0.1719, 150: 0.1534},   # polietileno
    "Poliestireno": {100: 0.1624, 150: 0.1448},
    "Acrilico":     {100: 0.1641, 150: 0.1456},   # polimetilmetacrilato
    "Teflon":       {100: 0.1500, 150: 0.1310},   # politetrafluoroetileno
}                                                 # (el Delrin no está en la Tabla 4 de NIST)

DECIMALES_MU_RHO = 4   # NIST da cuatro cifras significativas
DECIMALES_MU = 5


def fracciones_masa(material: dict) -> dict:
    """Fracciones en masa de un material: dadas, o calculadas de la fórmula química."""
    if "fracciones_masa" in material:
        total = sum(material["fracciones_masa"].values())
        return {el: w / total for el, w in material["fracciones_masa"].items()}
    masas = {el: n * PESOS_ATOMICOS[el] for el, n in material["formula"].items()}
    total = sum(masas.values())
    return {el: m / total for el, m in masas.items()}


def mu_rho_elemento(simbolo: str, energia_kev: float) -> float:
    """μ/ρ [cm²/g] de un elemento a `energia_kev`: el valor tabulado, o la interpolación log-log entre las
    dos energías tabuladas que la rodean. Fuera del rango tabulado NO se extrapola: falla."""
    tabla = MU_RHO_ELEMENTOS[simbolo]
    if energia_kev in tabla:
        return tabla[energia_kev]
    puntos = sorted(tabla)
    if not puntos[0] < energia_kev < puntos[-1]:
        raise ValueError(f"{energia_kev} keV fuera del rango tabulado {puntos[0]}-{puntos[-1]} keV")
    e1 = max(p for p in puntos if p < energia_kev)
    e2 = min(p for p in puntos if p > energia_kev)
    m1, m2 = tabla[e1], tabla[e2]
    t = (math.log(energia_kev) - math.log(e1)) / (math.log(e2) - math.log(e1))
    return math.exp(math.log(m1) + t * (math.log(m2) - math.log(m1)))


def mu_rho_material(material: dict, energia_kev: float) -> float:
    """μ/ρ [cm²/g] del material a `energia_kev`: regla de mezclas sobre sus elementos."""
    return sum(w * mu_rho_elemento(el, energia_kev) for el, w in fracciones_masa(material).items())


def energias_del_catalogo_mev() -> list:
    """Las energías de la linealidad de los equipos con protocolo, ordenadas: una sola fuente."""
    from analisisImagenes.catphan.protocolos import PROTOCOLOS
    return sorted({p.energia_linealidad_mev for p in PROTOCOLOS.values() if p.energia_linealidad_mev})


def generar(energias_mev=None) -> dict:
    """La tabla completa, en memoria. Función pura."""
    energias_mev = list(energias_mev) if energias_mev is not None else energias_del_catalogo_mev()
    salida = {
        "_fuente": {
            "referencia": FUENTE,
            "metodo": ("mu_rho = regla de mezclas sobre mu/rho elemental (NIST Tabla 3), interpolada log-log a la "
                       "energía; mu = mu_rho * densidad"),
            "unidades": {"mu_rho": "cm2/g", "densidad": "g/cm3", "mu": "1/cm"},
            "energia": "E [MeV] = kVp/1000 del protocolo de cada equipo (convención de constancia)",
            "generado_por": "scripts/generar_tabla_mu.py -- no editar este archivo a mano",
        }
    }
    for energia in energias_mev:
        filas = {}
        for nombre, material in MATERIALES.items():
            mu_rho = round(mu_rho_material(material, energia * 1000), DECIMALES_MU_RHO)
            densidad = material["densidad"]
            filas[nombre] = {"mu_rho": mu_rho, "densidad": densidad,
                             "mu": round(mu_rho * densidad, DECIMALES_MU)}
        salida[clave_energia(energia)] = filas
    return salida


def verificar_contra_compuestos(tolerancia_relativa: float = 0.005) -> list:
    """Regla de mezclas contra las tablas de compuestos de NIST, a 100 y 150 keV. Devuelve las filas que se
    desvían más de `tolerancia_relativa` (lista vacía = todo coincide)."""
    malas = []
    for nombre, por_energia in COMPUESTOS_NIST.items():
        for kev, esperado in por_energia.items():
            obtenido = mu_rho_material(MATERIALES[nombre], kev)
            if abs(obtenido - esperado) / esperado > tolerancia_relativa:
                malas.append((nombre, kev, esperado, round(obtenido, 5)))
    return malas


def como_texto(tabla: dict) -> str:
    return json.dumps(tabla, indent=4, ensure_ascii=False) + "\n"


def main(argv) -> int:
    tabla = generar()
    texto = como_texto(tabla)
    if "--verificar" in argv:
        actual = RUTA_JSON.read_text(encoding="utf-8") if RUTA_JSON.exists() else ""
        if actual != texto:
            print(f"{RUTA_JSON} NO coincide con lo que genera este script. Regenerarlo: "
                  f"python scripts/generar_tabla_mu.py")
            return 1
        print("La tabla de μ del repositorio coincide con la generada.")
        return 0
    malas = verificar_contra_compuestos()
    if malas:
        print("La regla de mezclas se desvía de NIST (compuestos):", malas)
        return 2
    RUTA_JSON.write_text(texto, encoding="utf-8")
    print(f"Escrito {RUTA_JSON} con las energías {[clave_energia(e) for e in energias_del_catalogo_mev()]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
