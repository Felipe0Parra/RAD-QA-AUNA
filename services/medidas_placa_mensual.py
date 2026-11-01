"""D.1 (PLAN_ANALISIS_PELICULAS_08-10.md, DA-84): LA lista de lo que se guarda del analisis mensual de aceleradores -- los datos FINALES de la capa que el fisico reporta.

El fisico lo dijo el 11-10: «los importantes son los datos finales, FWHM, desfase por lado y ya». De la capa reportada se guardan su estado («ok», o el motivo por el que no se midio: sin el
un vacio se confundiria con un cero), el FWHM crossplane e inplane y el desfase de cada lado (radiacion - luz, positivo hacia afuera); todo lo demas (las otras capas y el gris, la meseta, las
penumbras, los centros, el campo luminoso, la cuadratura y el barrido) se mide, se muestra y se vuelve a calcular al abrir con la imagen, los puntos, los parametros, el piso y la version
que si se guardan.

UNA sola lista. De ella salen, cada uno a la hora de usarla (leen `MEDIDAS_GUARDADAS` en cada llamada, no una copia hecha al importar):
  * el `CREATE TABLE` de `analisis_placa_mensual` y su migracion aditiva (`Conexion.crearTablaAnalisisPlacaMensual`, `data/ManejoDatos/conection.py`);
  * el escritor (`services.placa_mensual.sql_insert` y `guardar`);
  * el lector (`services.placa_mensual.leer`) y la comparacion de lo guardado con lo recalculado (`diferencias`).
Anadir o quitar un valor es UNA linea de esta lista, y las claves de `analisisImagenes.placa_mensual.valores_medidos` (`CLAVES_DE_VALORES_MEDIDOS`, la definicion de lo que el motor entrega) tienen
que ser exactamente estos nombres: una prueba lo fija (si no, el escritor dejaria fuera una clave del motor sin decirlo).

Un modulo pequeno SIN dependencias del proyecto: lo importa `conection.py` (que no puede importar nada que importe a `conection.py`) y lo importa el servicio.

`nombre`: el de la columna y el de la clave de `valores_medidos`. `unidad`: la del valor guardado ("" si es un texto). `tipo`: el tipo de la columna ("TEXT" o "REAL"). `admite_nulo`: False solo
para el estado (toda fila dice si la capa se midio); los numeros quedan vacios cuando no se midieron, nunca en cero.

Un valor OBLIGATORIO (`admite_nulo=False`) solo se EXIGE al crear la tabla: SQLite no agrega una columna NOT NULL (sin valor por omision) a una tabla ya creada, asi que en una base ya desplegada la migracion
aditiva (`Conexion.crearTablaAnalisisPlacaMensual`) la agrega admitiendo NULL y lo AVISA por consola; anadir un valor obligatorio pide ademas una migracion que reconstruya la tabla (como las de E10 o EB2d).
Anadir un valor que admite NULL sigue siendo UNA linea, en las bases nuevas y en las ya desplegadas (una prueba lo fija para cada valor de la lista).
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class MedidaGuardada:
    nombre: str
    unidad: str
    tipo: str
    admite_nulo: bool = True


MEDIDAS_GUARDADAS = (
    MedidaGuardada("estado", "", "TEXT", admite_nulo=False),
    MedidaGuardada("fwhm_crossplane_mm", "mm", "REAL"),
    MedidaGuardada("fwhm_inplane_mm", "mm", "REAL"),
    MedidaGuardada("desfase_izquierdo_mm", "mm", "REAL"),
    MedidaGuardada("desfase_derecho_mm", "mm", "REAL"),
    MedidaGuardada("desfase_superior_mm", "mm", "REAL"),
    MedidaGuardada("desfase_inferior_mm", "mm", "REAL"),
)

# CD.6b (PLAN_CURVA_DOSIS_PELICULAS_22-10.md, DA-92, DC16): se guarda SIEMPRE la netOD (la lista de arriba, que no cambia) y, cuando la regla del boton lo permite para la capa reportada
# (`analisisImagenes.placa_mensual.se_puede_pasar_a_dosis`), TAMBIEN sus valores en dosis y la copia de la curva con que se midieron. No van en el `CREATE TABLE` de D.1 (que no cambia): las agrega
# su bucle aditivo (`Conexion.crearTablaAnalisisPlacaMensual`, `ALTER TABLE ADD COLUMN`) en una base nueva y en una ya desplegada, AL FINAL: detras de `fecha_registro` y antes de `activo` en una base
# nueva, detras de `activo` en una desplegada (nadie lee por posicion, MI0: columnas explicitas). TODAS admiten NULL: un analisis sin dosis (sin curva, o con una capa
# que no cumple la regla) las deja vacias, nunca en cero (DA-88); un registro de antes de CD.6b tambien. `estado_dosis` vacio = no se midio en dosis; con texto = se midio, «ok» o el motivo
# («no medible en dosis: ...», sin numeros). `curva`: la copia (JSON) de la curva, de su calibracion, de la cadena de captura de la pelicula y de la base de cada capa (DA-81: al reabrir se usa ESA).
# Las claves de `analisisImagenes.placa_mensual.valores_medidos_en_dosis` (`CLAVES_DE_VALORES_MEDIDOS_EN_DOSIS`) son exactamente las de `MEDIDAS_GUARDADAS_EN_DOSIS`: una prueba lo fija.
MEDIDAS_GUARDADAS_EN_DOSIS = (
    MedidaGuardada("estado_dosis", "", "TEXT"),
    MedidaGuardada("fwhm_crossplane_dosis_mm", "mm", "REAL"),
    MedidaGuardada("fwhm_inplane_dosis_mm", "mm", "REAL"),
    MedidaGuardada("desfase_izquierdo_dosis_mm", "mm", "REAL"),
    MedidaGuardada("desfase_derecho_dosis_mm", "mm", "REAL"),
    MedidaGuardada("desfase_superior_dosis_mm", "mm", "REAL"),
    MedidaGuardada("desfase_inferior_dosis_mm", "mm", "REAL"),
)
COLUMNA_DE_LA_CURVA = MedidaGuardada("curva", "", "TEXT")
COLUMNAS_DE_LA_DOSIS = MEDIDAS_GUARDADAS_EN_DOSIS + (COLUMNA_DE_LA_CURVA,)      # en este orden (el `CREATE TABLE`, la migracion, el escritor y el lector las leen de aqui)
