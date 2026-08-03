"""Saneamiento del catálogo `equipos` (H2.6, PLAN_FASE_H, 2026-07-16;
extendido en H2.10, mismo día, hallazgo posterior a H2.6).

Origen de los cambios: 7 certificados de calibración reales (ADCL University
of Wisconsin + PTW-Freiburg, compilados por el físico en
`CompilCertificates.pdf`) cruzados campo a campo contra las 39 filas de
`equipos` en `AUNA_2026_2/BaseDatosQA.db`. Cada cambio de esta lista está
justificado por un certificado o por confirmación explícita del físico
(nunca por criterio propio sobre un valor clínico) -- ver el detalle en
CLAUDE.md, entradas "H2.6 EJECUTADA" y "H2.10 EJECUTADA".

Cambios, por categoría:
  1. Unificación TN->N (misma cámara física, dos prefijos en el catálogo):
     TN34001/001069 -> N34001/1069; TN31022/152342 -> N31022. Quedan
     marcadas histórico (activo=0, vigente=0 -- antes vigente=None, que es
     por lo que el combo no mostraba nada para estas filas).
  2. Corrección de t_cal/p_cal en las filas VIGENTES de N30013 y N31014:
     tenían grabadas las condiciones AMBIENTALES del día de calibración
     (p.ej. 20.9°C/98.91 kPa) en vez de las condiciones de REFERENCIA a las
     que el certificado ya normalizó el Ndw (22°C/101.325 kPa, ver
     "Comments" de cada certificado ADCL). Como la app usa t_cal/p_cal como
     t0/p0 de kTP, esto es un error dosimétrico activo de ~2% en cualquier
     cálculo con esas 2 cámaras -- verificado con
     services.dosis_service_calculations.factor_ktp.
  3. Corrección de escala del coeficiente de calibración (Cámara de pozo,
     HDR1000 Plus): el certificado de A972662 reporta 4.667e5, pero la fila
     vigente tenía 46670 (factor 10 de más). Verificado que este campo es
     solo de referencia visual en braquiterapia.py/braq_mensual.py (nunca se
     lee de vuelta en ninguna fórmula) -- no hay impacto dosimétrico vivo,
     pero confundía la lectura manual del físico.
  4. Retiro del pozo "A132690 Somer": equipo prestado, ya devuelto (con-
     firmado por el físico 2026-07-16) -- no vuelve a aparecer como activo.
  5. Deduplicación de filas idénticas (N31022 x5, N31010/1822 x2, N34001/1069
     x2, electrómetro CDX-2000B x2): se conserva la más completa (con
     fabricante), el resto queda histórico.
  6. (H2.10) Pozo A972662 vigente (id 16): mismo bug que el punto 2 pero en
     el coeficiente de calibración de pozo (Air Kerma Strength) -- t_cal/
     p_cal tenían las condiciones AMBIENTALES (21.4°C/98.52 kPa) en vez de
     las de REFERENCIA del certificado HDR12115 (22°C/101.325 kPa). El
     valor 466700 y la fecha 07/02/2024 ya estaban correctos (H2.6 solo
     arregló la escala, no las condiciones). Hoy este campo es solo de
     referencia visual (no se lee en ninguna fórmula), pero debe quedar
     correcto igual -- es una magnitud clínicamente esencial (fuerza de
     kerma en aire de la fuente de Ir-192), no un dato decorativo.
  7. (H2.10) Electrómetro CDX-2000B/B091982: la fila id 18 (calibración
     05/02/2024) seguía con vigente=1 al mismo tiempo que la fila id 79
     (recalibración 17/03/2026, también vigente=1) -- dos vigentes
     simultáneas para la misma serie. Se marca id 18 histórica
     (vigente=0); id 79 queda como la única vigente.
  8. (G9, PLAN_G_EQUIPOS_PERMISOS_Y_FECHAS_31-07.md) Las 3 filas ACTIVAS de
     2123/0453/A972662 completan `v1` (voltaje del electrodo colector,
     leído directo de sus certificados ADW39862/ADW39861/HDR12115: todos
     declaran "Collecting Electrode Bias: +300 V") y `h_cal` (asumido 50%
     como humedad de REFERENCIA -- SUPUESTO DE TRABAJO, DA-27, distinto de
     las lecturas directas de v1: los certificados ADCL no declaran
     humedad de referencia). `calibr_fact` no se toca en ninguna de las
     tres (ya correcto desde los puntos 3 y 6 de arriba).
  9. (G7, PLAN_G_EQUIPOS_PERMISOS_Y_FECHAS_31-07.md, DA-23) Las 2 filas con
     el mes y el día invertidos (ids 57/58, "7/28/2025", QDate inválido)
     se normalizan a "28/07/2025" -- confirmado contra el certificado
     HDR12899 ("Calibration Completed: 28/JUL/2025"). Las 10 filas con
     solo el día sin cero a la izquierda (dato correcto, defecto
     cosmético) se dejan sin tocar -- decisión explícita del físico.

Política deliberada: NUNCA se borra una fila (conservar todo el histórico,
igual que en la fusión de BD de 2026-07-03). Las filas redundantes quedan
`activo=0, vigente=0`, no se eliminan -- reversible por diseño.

Idempotente y con guarda de deriva: cada cambio declara su estado ANTES
esperado. Si la fila ya está en el estado DESPUÉS, se salta (ya aplicado).
Si no coincide ni con ANTES ni con DESPUÉS, se salta con una advertencia en
vez de sobrescribir a ciegas (la fila cambió por otra vía desde el análisis
-- requiere revisión humana, no autocorrección)."""
import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.audit_minimo import registrar  # noqa: E402


CAMBIOS = [
    {"id": 26, "motivo": "Unificar TN34001->N34001 (misma camara fisica que "
                         "serie 1069, ver certificado ADW43146); queda historico",
     "antes": {"model": "TN34001", "serie": "001069",
               "fecha_calibr": "9/08/2022", "activo": 1, "vigente": None},
     "despues": {"model": "N34001", "serie": "1069",
                 "fecha_calibr": "09/08/2022", "activo": 0, "vigente": 0}},
    {"id": 27, "motivo": "Unificar TN31022->N31022 (misma camara fisica que "
                         "serie 152342, ver certificado ADW43144); queda historico",
     "antes": {"model": "TN31022", "fecha_calibr": "9/08/2022",
               "activo": 1, "vigente": None},
     "despues": {"model": "N31022", "fecha_calibr": "09/08/2022",
                 "activo": 0, "vigente": 0}},

    {"id": 13, "motivo": "N30013 vigente: t_cal/p_cal tenian las condiciones "
                         "AMBIENTALES del certificado (20.9C/98.91kPa) en vez "
                         "de las de REFERENCIA (22C/101.325kPa, ver Comments "
                         "del certificado ADW39862) -- error de ~2% en kTP",
     "antes": {"t_cal": 20.9, "p_cal": 98.91},
     "despues": {"t_cal": 22.0, "p_cal": 101.325}},
    {"id": 7, "motivo": "N31014 vigente: mismo error que id13 (certificado "
                        "ADW39861) -- t_cal/p_cal ambientales en vez de "
                        "referencia -- error de ~2% en kTP",
     "antes": {"t_cal": 20.9, "p_cal": 98.96},
     "despues": {"t_cal": 22.0, "p_cal": 101.325}},

    {"id": 69, "motivo": "Normalizar formato de fecha (5/02/2024 -> "
                         "05/02/2024), fila historica N31010/1825 2024",
     "antes": {"fecha_calibr": "5/02/2024"},
     "despues": {"fecha_calibr": "05/02/2024"}},
    {"id": 70, "motivo": "Normalizar formato de fecha, fila historica "
                         "N34001/2426",
     "antes": {"fecha_calibr": "5/02/2024"},
     "despues": {"fecha_calibr": "05/02/2024"}},

    {"id": 16, "motivo": "Pozo A972662 vigente: coeficiente de calibracion "
                         "tenia 46670 (factor 10 de menos); certificado "
                         "HDR12115 reporta 4.667e5 = 466700. Solo campo de "
                         "referencia visual (no se lee en ninguna formula), "
                         "sin impacto dosimetrico vivo -- corregido por "
                         "higiene/legibilidad para el fisico",
     "antes": {"calibr_fact": 46670},
     "despues": {"calibr_fact": 466700}},
    {"id": 71, "motivo": "Duplicado erroneo de id16 (mismo evento, año "
                         "transcrito mal como 2025 y escala 4.667 en vez de "
                         "466700) -- queda historico",
     "antes": {"vigente": 1},
     "despues": {"vigente": 0}},

    {"id": 58, "motivo": "Duplicado exacto de id77 (pozo A092535, mismo "
                         "certificado HDR12899) -- queda historico",
     "antes": {"activo": 1, "vigente": 1},
     "despues": {"activo": 0, "vigente": 0}},
    {"id": 57, "motivo": "Duplicado de id77 con escala incorrecta (46470 en "
                         "vez de 464700) -- queda historico",
     "antes": {"activo": 1, "vigente": 1},
     "despues": {"activo": 0, "vigente": 0}},
    {"id": 63, "motivo": "Duplicado de id77 con escala incorrecta (4.647 en "
                         "vez de 464700) -- queda historico",
     "antes": {"activo": 1, "vigente": 1},
     "despues": {"activo": 0, "vigente": 0}},

    {"id": 54, "motivo": "Pozo 'A132690 Somer': equipo prestado, ya "
                         "devuelto (confirmado por el fisico 2026-07-16) -- "
                         "retirado del catalogo activo",
     "antes": {"activo": 1, "vigente": 1},
     "despues": {"activo": 0, "vigente": 0}},
    {"id": 55, "motivo": "Pozo 'A132690 Somer': idem id54",
     "antes": {"activo": 1, "vigente": 1},
     "despues": {"activo": 0, "vigente": 0}},
    {"id": 56, "motivo": "Pozo 'A132690 Somer': idem id54 (esta fila ademas "
                         "tenia p_cal=760, mezcla mmHg/kPa -- ya no importa "
                         "al quedar retirada, no se corrige un valor de un "
                         "equipo que ya no esta en servicio)",
     "antes": {"activo": 1, "vigente": 1},
     "despues": {"activo": 0, "vigente": 0}},

    {"id": 64, "motivo": "Duplicado exacto de id81 (N31010/1822) -- queda "
                         "historico",
     "antes": {"activo": 1, "vigente": 1},
     "despues": {"activo": 0, "vigente": 0}},
    {"id": 65, "motivo": "Duplicado exacto de id80 (N34001/1069) -- queda "
                         "historico",
     "antes": {"activo": 1, "vigente": 1},
     "despues": {"activo": 0, "vigente": 0}},
    {"id": 59, "motivo": "Duplicado exacto de id78 (N31022/152342) -- queda "
                         "historico",
     "antes": {"activo": 1, "vigente": 1},
     "despues": {"activo": 0, "vigente": 0}},
    {"id": 60, "motivo": "Duplicado exacto de id78 (N31022/152342) -- queda "
                         "historico",
     "antes": {"activo": 1, "vigente": 1},
     "despues": {"activo": 0, "vigente": 0}},
    {"id": 61, "motivo": "Duplicado exacto de id78 (N31022/152342) -- queda "
                         "historico",
     "antes": {"activo": 1, "vigente": 1},
     "despues": {"activo": 0, "vigente": 0}},
    {"id": 62, "motivo": "Duplicado exacto de id78 (N31022/152342) -- queda "
                         "historico",
     "antes": {"activo": 1, "vigente": 1},
     "despues": {"activo": 0, "vigente": 0}},
    {"id": 75, "motivo": "Duplicado exacto de id79 (electrometro CDX-2000B, "
                         "recalibracion 2026) -- queda historico",
     "antes": {"activo": 1, "vigente": 1},
     "despues": {"activo": 0, "vigente": 0}},

    {"id": 16, "motivo": "(H2.10) Pozo A972662 vigente: t_cal/p_cal tenian "
                         "las condiciones AMBIENTALES (21.4C/98.52kPa) en "
                         "vez de las de REFERENCIA (22C/101.325kPa, ver "
                         "certificado HDR12115) -- mismo bug que id13/id7, "
                         "hallado al investigar por que A972662 desaparecio "
                         "del selector de braquiterapia tras H2.6",
     "antes": {"t_cal": 21.4, "p_cal": 98.52},
     "despues": {"t_cal": 22.0, "p_cal": 101.325}},
    {"id": 18, "motivo": "(H2.10) Electrometro CDX-2000B/B091982: fila "
                         "vieja (05/02/2024) seguia vigente=1 a la vez que "
                         "la recalibracion id79 (17/03/2026, tambien "
                         "vigente=1) -- dos vigentes simultaneas para la "
                         "misma serie; queda historica",
     "antes": {"vigente": 1},
     "despues": {"vigente": 0}},

    # G9 (PLAN_G_EQUIPOS_PERMISOS_Y_FECHAS_31-07.md, DA-25/DA-26/DA-27/DA-28,
    # 2026-07-31): las 3 filas ACTIVAS de 2123/0453/A972662 quedaron
    # incompletas frente a las de id alto (h_cal/v1 nunca se completaron).
    # No entran en ninguna formula (kTP usa t_cal/p_cal, ya correctos desde
    # H2.6/H2.10), pero DA-25: "que un campo no entre en una formula no es
    # razon para dejarlo mal" -- son parte del registro del certificado.
    # `calibr_fact` NO se toca en ninguna de las tres (ya correcto).
    {"id": 13, "motivo": "(G9) N30013 vigente: v1 (voltaje de electrodo "
                         "colector) sin registrar; certificado ADW39862 "
                         "declara 'Collecting Electrode Bias: +300 V'",
     "antes": {"v1": None},
     "despues": {"v1": 300}},
    {"id": 13, "motivo": "(G9) N30013 vigente: h_cal=33 es la humedad "
                         "AMBIENTAL del dia de calibracion (certificado "
                         "ADW39862, 'Environmental Conditions') -- se "
                         "asume 50% como humedad de REFERENCIA. SUPUESTO "
                         "DE TRABAJO (DA-27): el certificado ADCL no "
                         "declara humedad de referencia, esto NO es una "
                         "lectura del documento",
     "antes": {"h_cal": 33},
     "despues": {"h_cal": 50}},

    {"id": 7, "motivo": "(G9) N31014 vigente: v1 sin registrar; "
                        "certificado ADW39861 declara 'Collecting "
                        "Electrode Bias: +300 V'",
     "antes": {"v1": None},
     "despues": {"v1": 300}},
    {"id": 7, "motivo": "(G9) N31014 vigente: h_cal=33 es la humedad "
                        "AMBIENTAL del certificado ADW39861. SUPUESTO DE "
                        "TRABAJO (DA-27): se asume 50% de referencia, no "
                        "es una lectura del certificado",
     "antes": {"h_cal": 33},
     "despues": {"h_cal": 50}},

    {"id": 16, "motivo": "(G9) Pozo A972662 vigente: v1 sin registrar; "
                         "certificado HDR12115 declara 'Collecting "
                         "Electrode Bias: +300 V'",
     "antes": {"v1": None},
     "despues": {"v1": 300}},
    {"id": 16, "motivo": "(G9) Pozo A972662 vigente: h_cal=38 es la "
                         "humedad AMBIENTAL del certificado HDR12115. "
                         "SUPUESTO DE TRABAJO (DA-27): se asume 50% de "
                         "referencia, no es una lectura del certificado",
     "antes": {"h_cal": 38},
     "despues": {"h_cal": 50}},

    # G7 (PLAN_G_EQUIPOS_PERMISOS_Y_FECHAS_31-07.md, DA-23, 2026-07-31):
    # solo la clase A (mes y dia invertidos, dato INCORRECTO) se corrige.
    # La clase B (10 filas con el dia sin cero, dato correcto, solo
    # cosmetico) se deja tal cual -- decision explicita del fisico.
    {"id": 57, "motivo": "(G7, DA-23) Fecha con mes y dia invertidos "
                         "('7/28/2025', QDate invalido) -- certificado "
                         "HDR12899 confirma 'Calibration Completed: "
                         "28/JUL/2025' -> 28 de julio de 2025",
     "antes": {"fecha_calibr": "7/28/2025"},
     "despues": {"fecha_calibr": "28/07/2025"}},
    {"id": 58, "motivo": "(G7, DA-23) Fecha con mes y dia invertidos, "
                         "misma correccion que id57 (certificado HDR12899)",
     "antes": {"fecha_calibr": "7/28/2025"},
     "despues": {"fecha_calibr": "28/07/2025"}},
]


def aplicar_saneamiento(ruta_db, usuario=None, dry_run=False):
    """Aplica CAMBIOS sobre `ruta_db`. Devuelve un dict con 3 listas:
    'aplicados' (cambiados en esta corrida), 'ya_aplicados' (idempotencia:
    ya estaban en el estado DESPUÉS) y 'con_deriva' (ni ANTES ni DESPUÉS --
    la fila cambió por otra vía, se salta sin tocarla, requiere revisión
    humana)."""
    con = sqlite3.connect(ruta_db)
    resultado = {"aplicados": [], "ya_aplicados": [], "con_deriva": []}
    try:
        cur = con.cursor()
        for cambio in CAMBIOS:
            eq_id = cambio["id"]
            antes, despues, motivo = cambio["antes"], cambio["despues"], cambio["motivo"]
            columnas = list(despues)
            cur.execute(
                f"SELECT {','.join(columnas)} FROM equipos WHERE id = ?", (eq_id,))
            fila = cur.fetchone()
            if fila is None:
                print(f"[saneamiento_h26] AVISO: id={eq_id} no existe, se salta")
                continue

            actual = dict(zip(columnas, fila))
            entrada = {"id": eq_id, "actual": actual, "despues": despues,
                       "motivo": motivo}

            if all(actual[c] == v for c, v in despues.items()):
                resultado["ya_aplicados"].append(entrada)
                continue

            if not all(actual.get(c) == v for c, v in antes.items()):
                print(f"[saneamiento_h26] AVISO: id={eq_id} no coincide con "
                      f"el ANTES esperado ({antes}), estado actual {actual} "
                      f"-- se salta, requiere revision manual")
                resultado["con_deriva"].append(entrada)
                continue

            if dry_run:
                resultado["aplicados"].append(entrada)
                continue

            set_clause = ", ".join(f"{c} = ?" for c in despues)
            cur.execute(f"UPDATE equipos SET {set_clause} WHERE id = ?",
                        (*despues.values(), eq_id))
            # Commit ANTES de auditar: registrar() abre su PROPIA conexión
            # (mismo patrón que el resto de la app, ver audit_minimo.py) --
            # si la UPDATE de esta fila sigue sin confirmar, esa segunda
            # conexión choca con "database is locked". Confirmar fila a
            # fila también deja el script seguro ante una interrupción a
            # medias (progreso parcial, no todo-o-nada).
            con.commit()
            registrar(usuario, "saneamiento_h26", tabla="equipos", ref=eq_id,
                      detalle=motivo, ruta_db=ruta_db)
            resultado["aplicados"].append(entrada)
    finally:
        con.close()
    return resultado


def _main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="Ruta al BaseDatosQA.db")
    parser.add_argument("--usuario", default=None)
    parser.add_argument("--dry-run", action="store_true",
                         help="Solo mostrar que cambiaria, sin escribir")
    args = parser.parse_args()

    r = aplicar_saneamiento(args.db, usuario=args.usuario, dry_run=args.dry_run)
    verbo = "Cambiaria" if args.dry_run else "Aplicado"
    print(f"{verbo} en {len(r['aplicados'])} fila(s) de {len(CAMBIOS)} candidatas:")
    for c in r["aplicados"]:
        print(f"  id={c['id']}: {c['actual']} -> {c['despues']}  ({c['motivo']})")
    if r["ya_aplicados"]:
        print(f"{len(r['ya_aplicados'])} fila(s) ya estaban en el estado "
              f"objetivo (idempotencia, sin cambios).")
    if r["con_deriva"]:
        print(f"¡ATENCION! {len(r['con_deriva'])} fila(s) no coinciden ni "
              f"con el antes ni el despues esperado -- revisar a mano:")
        for c in r["con_deriva"]:
            print(f"  id={c['id']}: actual={c['actual']}")


if __name__ == "__main__":
    _main()
