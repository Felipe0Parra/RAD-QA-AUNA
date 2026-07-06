# Sistema de Control de Calidad para Equipos de Radioterapia

Sistema integral para gestión de controles de calidad en equipos de radioterapia, braquiterapia y tomografía computarizada.

---

## 📋 Tabla de Contenidos
    Presione ctrl + click en el item que quiere ver
- [Descripción General](#-descripción-general)
- [Requisitos](#-requisitos)
- [Instalación](#-instalación)
- [Estructura del Proyecto](#-estructura-del-proyecto)
- [Flujo de la Aplicación](#-flujo-de-la-aplicación)
- [Guía para Desarrolladores](#-guía-para-desarrolladores)
- [Base de Datos](#-base-de-datos)
- [Cómo Agregar Nuevas Funcionalidades](#-cómo-agregar-nuevas-funcionalidades)
- [Testing](#-testing)
- [Troubleshooting](#-troubleshooting)

---

## 🎯 Descripción General

Este sistema permite:
- ✅ Realizar controles de calidad **diarios, mensuales y anuales**
- ✅ Analizar imágenes médicas (DICOM, películas radiográficas, placas)
- ✅ Calcular parámetros físicos (actividad de fuente, números CT, uniformidad, etc.)
- ✅ Generar reportes PDF automáticos
- ✅ Gestionar usuarios y equipos
- ✅ Visualizar datos históricos en gráficos y tablas

### Equipos Soportados
- **Aceleradores Lineales**: Halcyon, IX, 600
- **Braquiterapia**: Fuentes de Iridio-192
- **Tomografía**: Análisis CatPhan completo

---

## 💻 Requisitos

### Software
- Python 3.8+
- PyQt5
- OpenCV
- NumPy
- pandas
- pydicom
- matplotlib
- ReportLab
- pylinac (para validación)

### Instalación
```bash
pip install -r requirements.txt
```

### Ejecución
```bash
python main.py
```

---

## 📁 Estructura del Proyecto

```
Controles/
│
├── main.py                          # ⭐ PUNTO DE ENTRADA - Inicia la aplicación
├── requirements.txt                 # Dependencias del proyecto
├── utils.py                         # Utilidades generales
├── infoWidgets.csv                  # Configuración de widgets de interfaz
│
├── ui/                              # 🖼️ INTERFAZ DE USUARIO
│   ├── mainpages.py                 # Ventana principal y navegación
│   ├── paginasEntrReg/              # Login, registro, recuperación
│   ├── paginasGuia/                 # Selección de equipos y tipos de prueba
│   └── paginasControles/            # Páginas de controles específicos
│       ├── PruebasDiarias/          # Controles diarios por equipo
│       ├── PruebasMensuales/        # Controles mensuales por equipo
│       └── PruebasAnuales/          # Controles anuales
│
├── analisisImagenes/                # 🔬 PROCESAMIENTO Y ANÁLISIS
│   ├── ActividadFuente.py           # Cálculo de actividad de fuentes
│   ├── Analisis_PlacaRC.py          # Análisis de películas (líneas, campos)
│   ├── Analisis_PlacaCuadrada.py    # Análisis de campos cuadrados
│   └── Analisis_Catphan_TAC.py      # ⭐ Análisis completo CatPhan
│
├── data/                            # 💾 GESTIÓN DE DATOS
│   ├── ManejoDatos/
│   │   ├── conection.py             # ⭐ Conexión BD y creación de tablas
│   │   ├── load.py                  # ⭐ Guardado y carga de datos
│   │   ├── lectorWidgets.py         # Lectura de configuración widgets
│   │   ├── user.py                  # Gestión de usuarios
│   │   ├── usuariosManager.py       # Manager de usuarios
│   │   ├── encriptarInfo.py         # Encriptación de datos sensibles
│   │   ├── obtenerDatosHalcyon.py   # Extracción de datos Halcyon
│   │   └── catphan_TAC/
│   │       ├── leer_dicom.py        # ⭐ Lectura y procesamiento DICOM
│   │       └── catphan_db.py        # ⭐ Guardado de resultados CatPhan
│   │   ├── Tablas_Anuales/
│   │       ├── tablas_anuales.py    # ⭐ Muestra la tablas de BD en la interfaz 
│   └── GraficasyTablas/
│       ├── tablas.py                # Configuración de tablas
│       └── unovsuno.py              # Gráficos personalizados
│
├── models/                          # 📊 MODELOS Y REPORTES
│   ├── images/
│   │   └── imagenes.py              # Gestión de imágenes
│   ├── PDF/
│   │   ├── reportes.py              # ⭐ Generación de reportes PDF
│   │   ├── PDFWindow.py             # Visor de PDFs
│   │   └── Mensuales/
│   │       └── reportes_mensuales.py
│   │   └── Anuales/
│   │       └── reportes_anuales.py
│   │   └── Imagenes/
│   │       └── reportes_control_sistema_imagenes.py
│
└── resources/                       # 🎨 RECURSOS
    ├── estilo.qss                   # Estilos Qt
    ├── archivos_json/               # Configuración de equipos
    │   ├── dosimetria.json
    │   ├── equipos.json
    │   └── poder_frenado_materiales.json
    ├── icons/                       # Iconos
    └── images/                      # Imágenes de la aplicación
```

---

## 🔄 Flujo de la Aplicación

### 1. Inicio y Autenticación
```
main.py → MainWindow (ui/mainpages.py) → Login (ui/paginasEntrReg/Login.py)
```

### 2. Selección de Prueba
```
selection_page.py → Tipo de control (Diario/Mensual/Anual)
                 → equipos.py → Selección de equipo específico
```

### 3. Realización de Prueba
```
Página específica (ej: PruebaMensualTAC)
    ↓
Carga de datos/imágenes
    ↓
Análisis (analisisImagenes/)
    ↓
Visualización de resultados
    ↓
Guardado en BD (data/ManejoDatos/load.py)
    ↓
Generación de reporte PDF (models/PDF/reportes.py)
```

---

## 👨‍💻 Guía para Desarrolladores

### Archivos Clave que Debes Conocer

#### 🔑 **Archivo Maestro para pruebas diarias u otras utilidades: `ui/paginasControles/PruebasDiarias/PruebasDiarias.py`**

**Clase: `PruebaBasico`** - Clase base para las pruebas diarias y mensual de braquiterapia

**¿Qué hace?**
- Define la estructura común de todas las páginas de pruebas
- Maneja tablas, gráficos, botones, y widgets compartidos
- Gestiona el guardado de datos y generación de reportes de las pruebas diarias
pero contiene funciones que pueden ser usadas en todas las pruebas

**Métodos importantes:**
```python
setupBox()              # Crea la estructura de la interfaz desde el excel 
crear_labels()          # Crea campos de entrada
agregar_tabla()         # Agrega tablas editables
agregar_graficos()      # Agrega visualizaciones
guardar_datos()         # Guarda en base de datos
generar_pdf()           # Crea reporte PDF
```

Funcionan particularmente para las pruebas diarias

**Para crear una nueva prueba:**
1. Hereda de `PruebaBasico`
2. Sobrescribe `setupBox()` para tu interfaz específica
3. Implementa métodos de análisis específicos
4. Define `guardar_datos()` para tu lógica de guardado


#### 🔑 **Archivo Maestro para pruebas mensuales y anuales: `ui/paginasControles/PruebasMensuales/seiscientos_mensual.py`**

**Clase: `PruebaMensual600`** - Clase base para las pruebas mensuales y anuales de los aceleradores lineales

**¿Qué hace?**
- Define la estructura común de todas las páginas de pruebas
- Maneja tablas, gráficos, botones, y widgets compartidos
- Gestiona el guardado de datos y generación de reportes de las pruebas diarias
pero contiene funciones que pueden ser usadas en todas las pruebas
- Para Halcyon e iX se redefinen algunos métodos para que tengan su propio comportamiento.


---

#### 🔬 **Análisis de Imágenes**

**Archivo: `MLCs_calibration_service`** En el archivo de servicios se guarda un conjunto de funciones que permiten hacer el analisis matemático y de imagenes del MLC, con esto se obtienen datos importantes, por el momento es un teaser entonces está muy verde, y da pie a mejores correcciones

**¿Qué hace?**
- Adquiere imagenes DICOM de MLCs, invoca la librería PyLinac de tal forma que usa los outputs de esta librería para obtener los datos. Literal solo se obtienen los datos del diccionario y se procesan, eso facilita mucho las cosas, aparte también maneja la base de datos para el analisis de MLC, de tal forma que se hace siempre automaticamente y se sobreescribe si se detecta que ya hay datos.


##### **`analisisImagenes/Analisis_Catphan_TAC.py`** - Análisis CatPhan

**Funciones principales:**

|                 Función                 |                      Qué analiza                |            Retorna                 |
|-----------------------------------------|-------------------------------------------------|------------------------------------|
| `espesor_corte(imagen, geometria, ...)` | Espesor de corte usando 4 rampas de alambre     | Dict con FWHM por dirección        |
| `tamano_pixel(imagen, geometria, ...)`  | Dimensiones físicas de píxeles                  | Dict con tamaños X e Y             |
| `resolucion_contraste(imagen, geometria, ...)` | Visibilidad de 6 ROIs de bajo contraste  | Dict con CNR, SNR, visibilidad     |
| `resolucion_espacial(imagen, geometria, ...)`  | MTF con patrones de barras               | Dict con MTF por región            |
| `valor_numero_ct(imagen, geometria)`           | Números CT de 7 materiales               | Dict con HU por material           |
| `linealidad_ct(valores_ct, ...)`               | Linealidad HU vs densidad                | Dict con R², pendiente, intercepto |
| `uniformidad(imagen, geometria)`               | Uniformidad en 5 ROIs                    | Dict con UI e INU                  |

**Parámetros comunes:**
- `imagen`: Array NumPy (corte 2D)
- `geometria`: Objeto `GeometriaCatphan` con centro y radio
- `visualizar`: Boolean para mostrar imágenes de debug

---

##### **`analisisImagenes/Analisis_PlacaRC.py`** - Análisis de Películas

**Funciones principales:**

|             Función               |                   Uso                           |               Retorna             |
|-----------------------------------|-------------------------------------------------|-----------------------------------|
| `analizar_lineas(imagen, ...)`    | Detecta líneas en películas, calcula distancias | HTML con tabla de resultados      |
| `analizar_cuadrado(imagen, ...)`  | Analiza campos cuadrados (simetría, penumbra) | Diccionario con perfiles y métricas |
| `detectar_contornos(imagen, ...)` | Encuentra cruces y esquinas en películas | Imagen procesada y contornos |

---

#### 💾 **Base de Datos**

##### **`data/ManejoDatos/conection.py`** - Gestión de BD

**Clase: `Conexion`**

```python
# Crear instancia
conexion = Conexion()

# Crear todas las tablas
conexion.createTable()

# Ejecutar query
conexion.executeQuery("SELECT * FROM usuarios")

# Insertar datos
conexion.executeQuery("INSERT INTO tabla VALUES (?, ?)", (val1, val2))
```

**Tablas principales:**
- `usuarios` - Información de usuarios
- `equipos` - Configuración de equipos
- `braqui`, `braqui_mensual` - Datos de braquiterapia
- `halcyon_diaria`, `halcyon_mensual` - Datos Halcyon
- `ix_diaria`, `ix_mensual` - Datos IX
- `seiscientos_diaria`, `seiscientos_mensual` - Datos 600
- `tac_mensual` - Datos generales de TAC
- 12 tablas específicas de CatPhan (ver abajo)

---

##### **`data/ManejoDatos/load.py`** - Guardado de Datos

**Función: `add_info()`** - Guarda datos de pruebas

```python
add_info(
    datos=datos_dict,           # Dict con todos los valores
    columnas=lista_columnas,    # Nombres de columnas
    nombreTabla='tabla',        # Nombre de tabla en BD
    imagen=imagen_bytes,        # Imagen como bytes (opcional)
    distancias=dict_distancias, # Dict de distancias (opcional)
    desplazamientos=dict_desp   # Dict de desplazamientos (opcional)
)
```

**Función: `guardarEdicion()`** - Actualiza registros existentes

---

##### **Tablas CatPhan** - `data/ManejoDatos/conection.py:crearTablasCatphan()`

Las 12 tablas especializadas para CatPhan:

1. **`catphan_espesor_corte`** - Resultados de espesor
2. **`catphan_tamano_pixel`** - Dimensiones de píxeles
3. **`catphan_resolucion_contraste_general`** - Resumen de resolución
4. **`catphan_resolucion_contraste_detalles`** - Detalles por ROI
5. **`catphan_resolucion_espacial_general`** - Resumen MTF
6. **`catphan_resolucion_espacial_detalles`** - MTF por región
7. **`catphan_valores_ct_general`** - Resumen números CT
8. **`catphan_valores_ct_materiales`** - HU por material
9. **`catphan_linealidad_ct`** - Regresión lineal
10. **`catphan_uniformidad_ruido_general`** - Resumen uniformidad
11. **`catphan_uniformidad_ruido_detalles`** - Datos por ROI
12. **`catphan_imagen_analizada`** - Imagen DICOM como BLOB

---

##### **`data/ManejoDatos/catphan_TAC/catphan_db.py`** - Sistema CatPhan

**Flujo completo:**

```python
# 1. Usuario ejecuta análisis → Resultados en dict
resultados_espesor = espesor_corte(imagen, geometria, ...)

# 2. Mapear resultados a formato BD
datos_bd = mapear_espesor_corte(resultados_espesor, id_tac, usuario)

# 3. Guardar en BD
guardar_espesor_corte(datos_bd)

# 4. Crear widget para mostrar
tabla_widget = tabla_resultados_espesor(datos_bd)
```

**Funciones de mapeo:** Convierten resultados de análisis a diccionarios BD
- `mapear_espesor_corte()`, `mapear_resolucion_contraste()`, etc.

**Funciones de guardado:** Insertan datos en tablas específicas
- `guardar_espesor_corte()`, `guardar_valores_ct()`, etc.

**Función maestra:**
```python
guardar_prueba_completa_catphan(
    id_tac_mensual,              # ID de la prueba principal
    resultados_espesor,          # Dict de resultados
    resultados_tamano_pixel,
    resultados_resolucion_contraste,
    # ... todos los resultados ...
    corte_dicom,                 # Array NumPy del corte
    nombre_usuario
)
```

---

#### 🖼️ **Interfaz de Usuario**

##### **`ui/paginasControles/PruebasMensuales/tac_mensual.py`** - Ejemplo Completo

**Clase: `PruebaMensualTAC`** - Prueba mensual de tomografía

**Estructura:**

```python
class PruebaMensualTAC(QWidget):
    def __init__(self):
        # 7 botones para categorías CatPhan
        self.categorias = {
            'Espesor': self.categoria_espesor,
            'Tamaño Píxel': self.categoria_tamano_pixel,
            # ... etc ...
        }
        
    def cargar_dicom(self):
        """Carga carpeta DICOM y muestra visualizador"""
        self.dicom_volume = DicomVolume(carpeta_dicom)
        self.visualizador = VisualizadorDicom(self.dicom_volume)
        
    def categoria_espesor(self):
        """Ejecuta análisis de espesor de corte"""
        # 1. Obtener corte actual
        corte = self.visualizador.obtener_corte_actual()
        
        # 2. Ejecutar análisis
        self.resultados_espesor = espesor_corte(
            corte, 
            self.geometria,
            visualizar=True
        )
        
        # 3. Mostrar resultados en tabla
        tabla = tabla_resultados_espesor(self.resultados_espesor)
        self.layout_resultados.addWidget(tabla)
        
    def guardar_todo(self):
        """Guarda todos los resultados en BD"""
        # 1. Guardar prueba general TAC
        id_tac = add_info(
            datos=self.datos_generales,
            columnas=['fecha', 'usuario', 'equipo'],
            nombreTabla='tac_mensual'
        )
        
        # 2. Guardar análisis CatPhan completo
        guardar_prueba_completa_catphan(
            id_tac,
            self.resultados_espesor,
            self.resultados_tamano_pixel,
            # ... todos los resultados ...
            self.corte_dicom_array,
            self.usuario
        )
        
        # 3. Generar PDF
        self.generar_pdf()
```

---

##### **`data/ManejoDatos/catphan_TAC/leer_dicom.py`** - Manejo DICOM

**Clase: `DicomVolume`** - Carga y procesa volúmenes DICOM

```python
# Crear volumen
volumen = DicomVolume(carpeta_dicom)

# Acceder a cortes
corte = volumen.get_slice(indice)  # Array 2D en unidades Hounsfield

# Propiedades
volumen.num_slices          # Número de cortes
volumen.pixel_spacing       # Espaciado de píxeles [x, y]
volumen.slice_thickness     # Espesor de corte
```

**Clase: `GeometriaCatphan`** - Detecta geometría del phantom

```python
# Detectar automáticamente
geometria = GeometriaCatphan.desde_imagen(corte)

# Acceder a propiedades
geometria.centro            # (x, y) del centro
geometria.radio             # Radio del phantom
```

**Clase: `VisualizadorDicom`** - Widget Qt para visualización

```python
# Crear visualizador
visualizador = VisualizadorDicom(dicom_volume)

# Conectar señales
visualizador.slice_changed.connect(self.on_slice_change)

# Obtener corte actual
corte_actual = visualizador.obtener_corte_actual()
```

---

#### 📄 **Generación de Reportes**

##### **`models/PDF/reportes.py`** - Función `reporte()`

```python
reporte(
    datos=datos_dict,           # Dict con todos los datos
    nombreTabla='tabla',        # Nombre de tabla
    imagenes=[img1, img2],      # Lista de imágenes (opcional)
    graficos=[graf1, graf2],    # Lista de gráficos (opcional)
    titulo='Mi Reporte',        # Título del reporte
    usuario='nombre_usuario'    # Usuario que genera
)
```

**Personalizar reportes:**
1. Edita las funciones `_crear_encabezado()`, `_crear_tabla()`, `_agregar_imagenes()`
2. Modifica estilos en `getSampleStyleSheet()`
3. Cambia formato de tabla en `TableStyle`

---

## 🔧 Cómo Agregar Nuevas Funcionalidades

### 1️⃣ Agregar un Nuevo Tipo de Prueba

**Paso 1: Crear la clase de interfaz**

Crea archivo en `ui/paginasControles/PruebasDiarias/mi_nueva_prueba.py`:

```python
from ui.paginasControles.PruebasDiarias.PruebasDiarias import PruebaBasico

class MiNuevaPrueba(PruebaBasico):
    def __init__(self, info_widget, usuario):
        super().__init__(info_widget, usuario)
        self.nombreTabla = "mi_tabla"  # Nombre de tabla en BD
        self.setupBox()
        
    def setupBox(self):
        """Define la interfaz específica"""
        # Agregar campos
        self.crear_labels(['Campo1', 'Campo2', 'Campo3'])
        
        # Agregar tabla
        self.agregar_tabla(num_columnas=5)
        
        # Agregar botones personalizados
        btn_analizar = QPushButton("Analizar")
        btn_analizar.clicked.connect(self.analizar)
        self.layout.addWidget(btn_analizar)
        
    def analizar(self):
        """Lógica de análisis específica"""
        # Tu código aquí
        pass
        
    def guardar_datos(self):
        """Guardado personalizado"""
        datos = {
            'campo1': self.labels['Campo1'].text(),
            'campo2': self.labels['Campo2'].text()
        }
        add_info(datos, columnas, self.nombreTabla)
```

**Paso 2: Crear tabla en BD**

En `data/ManejoDatos/conection.py`, agrega en `createTable()`:

```python
def createTable(self):
    # ... código existente ...
    
    # Tu nueva tabla
    self.executeQuery('''
        CREATE TABLE IF NOT EXISTS mi_tabla (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha DATE,
            usuario TEXT,
            equipo TEXT,
            campo1 REAL,
            campo2 REAL,
            campo3 TEXT
        )
    ''')
```

**Paso 3: Integrar en navegación**

En `ui/paginasGuia/equipos.py`, agrega tu página:

```python
from ui.paginasControles.PruebasDiarias.mi_nueva_prueba import MiNuevaPrueba

class Config:
    def configurar_mi_equipo(self):
        self.prueba_diaria = MiNuevaPrueba(info_widget, usuario)
        self.stack.addWidget(self.prueba_diaria)
```

---

### 2️⃣ Agregar Nuevo Análisis de Imagen

**Paso 1: Crear función de análisis**

En `analisisImagenes/mi_analisis.py`:

```python
import cv2
import numpy as np

def mi_analisis(imagen, parametro1, parametro2, visualizar=False):
    """
    Descripción detallada del análisis.
    
    Args:
        imagen: Array NumPy (H, W) o (H, W, C)
        parametro1: Descripción
        parametro2: Descripción
        visualizar: Si True, muestra imágenes de debug
        
    Returns:
        dict: {
            'resultado1': valor1,
            'resultado2': valor2,
            'imagen_procesada': array
        }
    """
    # 1. Preprocesamiento
    if len(imagen.shape) == 3:
        imagen_gray = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
    else:
        imagen_gray = imagen
        
    # 2. Tu algoritmo aquí
    resultado1 = np.mean(imagen_gray)
    resultado2 = np.std(imagen_gray)
    
    # 3. Visualización (opcional)
    if visualizar:
        import matplotlib.pyplot as plt
        plt.figure(figsize=(10, 5))
        plt.subplot(1, 2, 1)
        plt.imshow(imagen_gray, cmap='gray')
        plt.title('Original')
        plt.subplot(1, 2, 2)
        plt.imshow(imagen_procesada, cmap='gray')
        plt.title('Procesada')
        plt.show()
        
    # 4. Retornar resultados
    return {
        'resultado1': resultado1,
        'resultado2': resultado2,
        'imagen_procesada': imagen_procesada
    }
```

**Paso 2: Integrar en interfaz**

En tu clase de prueba:

```python
from analisisImagenes.mi_analisis import mi_analisis

def ejecutar_mi_analisis(self):
    # Cargar imagen
    imagen = cv2.imread(self.ruta_imagen)
    
    # Ejecutar análisis
    resultados = mi_analisis(
        imagen,
        parametro1=10,
        parametro2='opcion',
        visualizar=True
    )
    
    # Mostrar resultados
    self.labels['Resultado1'].setText(str(resultados['resultado1']))
    self.labels['Resultado2'].setText(str(resultados['resultado2']))
```

---

### 3️⃣ Agregar Nuevo Equipo

**Paso 1: Registrar en BD**

Inserta manualmente en tabla `equipos` o usa interfaz de administración.

**Paso 2: Crear archivos de configuración**

En `resources/archivos_json/`, agrega configuración:

```json
{
  "mi_equipo": {
    "nombre": "Mi Nuevo Equipo",
    "tipo": "acelerador",
    "parametros": {
      "energia": [6, 10, 15],
      "tasas_dosis": [100, 200, 400]
    }
  }
}
```

**Paso 3: Crear clases de prueba**

Crea clases heredadas de `PruebaBasico` para cada tipo de control (diario/mensual/anual).

**Paso 4: Integrar en `equipos.py`**

```python
def configurar_mi_equipo(self):
    self.prueba_diaria = PruebaDiariaMiEquipo(...)
    self.prueba_mensual = PruebaMensualMiEquipo(...)
    # ...
```

---

### 4️⃣ Personalizar Reportes PDF

**Opción 1: Modificar `models/PDF/reportes.py`**

```python
def reporte(datos, nombreTabla, ...):
    # Personalizar por tipo de tabla
    if nombreTabla == 'mi_tabla':
        # Formato especial
        _crear_seccion_personalizada(datos)
    else:
        # Formato estándar
        _crear_tabla_estandar(datos)
```

**Opción 2: Crear función de reporte específica**

```python
def reporte_mi_equipo(datos, imagenes):
    """Reporte personalizado para mi equipo"""
    doc = SimpleDocTemplate(filename, pagesize=letter)
    story = []
    
    # Encabezado personalizado
    story.append(Paragraph("Mi Equipo - Reporte", estilos['Title']))
    
    # Contenido específico
    # ...
    
    doc.build(story)
    return filename
```

---

## 🧪 Testing

### Ejecutar Tests Existentes

```bash
# Tests de análisis CatPhan
python models/tests/test_catphan_TAC.py

# Comparación con pylinac
python models/tests/comparar_mio_pylinac.py

# Pruebas pylinac
python models/tests/prueba_pylinac.py
```

### Crear Nuevos Tests

```python
# tests/test_mi_funcionalidad.py

import unittest
from analisisImagenes.mi_analisis import mi_analisis

class TestMiAnalisis(unittest.TestCase):
    def setUp(self):
        # Preparar datos de prueba
        self.imagen_test = np.random.rand(512, 512)
        
    def test_resultado_valido(self):
        resultado = mi_analisis(self.imagen_test, param1=10)
        self.assertIsNotNone(resultado)
        self.assertIn('resultado1', resultado)
        
    def test_parametros_invalidos(self):
        with self.assertRaises(ValueError):
            mi_analisis(None, param1=10)
            
if __name__ == '__main__':
    unittest.main()
```

---

## 🐛 Troubleshooting

### Problema: Error al cargar DICOM

**Causa:** Archivos DICOM corruptos o formato incorrecto

**Solución:**
```python
# En leer_dicom.py, agregar validación
try:
    ds = pydicom.dcmread(archivo)
    if not hasattr(ds, 'PixelData'):
        raise ValueError("DICOM sin PixelData")
except Exception as e:
    print(f"Error al leer {archivo}: {e}")
```

---

### Problema: Tabla no se crea en BD

**Causa:** Sintaxis SQL incorrecta o tipo de dato no soportado

**Solución:**
1. Verifica sintaxis en `conection.py:createTable()`
2. Ejecuta manualmente la query en un visor SQLite
3. Revisa tipos de datos: INTEGER, REAL, TEXT, BLOB, DATE

---

### Problema: Análisis CatPhan falla al detectar geometría

**Causa:** Imagen de bajo contraste o ruido excesivo

**Solución:**
```python
# En leer_dicom.py:GeometriaCatphan.desde_imagen()
# Ajustar parámetros de detección
_, imagen_bin = cv2.threshold(
    imagen_norm, 
    umbral_ajustado,  # Probar diferentes valores (100-150)
    255, 
    cv2.THRESH_BINARY
)
```

---

### Problema: Memoria insuficiente con volúmenes DICOM grandes

**Causa:** Carga de todo el volumen en RAM

**Solución:**
```python
# Ya implementado en DicomVolume
# Usa lazy loading y cache limitado
volumen = DicomVolume(carpeta, cache_size=50)  # Limitar cache
```

---

### Problema: PDF no se genera

**Causa:** Rutas incorrectas o permisos de escritura

**Solución:**
```python
# Verificar rutas absolutas
import os
pdf_dir = os.path.join(os.getcwd(), 'reportes')
os.makedirs(pdf_dir, exist_ok=True)
pdf_path = os.path.join(pdf_dir, 'reporte.pdf')
```

---

## 📚 Recursos Adicionales

### Documentación de Librerías
- [PyQt5 Documentation](https://www.riverbankcomputing.com/static/Docs/PyQt5/)
- [OpenCV Python](https://docs.opencv.org/master/d6/d00/tutorial_py_root.html)
- [pydicom User Guide](https://pydicom.github.io/pydicom/stable/tutorials/index.html)
- [ReportLab User Guide](https://www.reportlab.com/docs/reportlab-userguide.pdf)
- [pylinac Documentation](https://pylinac.readthedocs.io/)

### Referencias de Física Médica
- AAPM TG Reports para protocolos de control de calidad
- Documentación del phantom CatPhan (Phantom Laboratory)

---

## 🤝 Contribuir

### Estándares de Código

1. **Docstrings:** Todas las funciones deben tener docstrings en formato Google
```python
def mi_funcion(parametro1, parametro2):
    """
    Descripción breve.
    
    Descripción detallada si es necesario.
    
    Args:
        parametro1 (tipo): Descripción
        parametro2 (tipo): Descripción
        
    Returns:
        tipo: Descripción del retorno
        
    Raises:
        ErrorType: Cuándo se lanza
    """
```

2. **Nombres:** PEP 8
   - Variables y funciones: `snake_case`
   - Clases: `PascalCase`
   - Constantes: `UPPER_CASE`

3. **Imports:** Organizados
```python
# Estándar
import os
import sys

# Terceros
import numpy as np
import cv2
from PyQt5.QtWidgets import QWidget

# Locales
from data.ManejoDatos.conection import Conexion
```

4. **Comentarios:** Claros y concisos
   - Explica el "por qué", no el "qué"
   - Actualiza comentarios al cambiar código

---

## 📞 Contacto y Soporte

Para preguntas o reportar bugs:
- **Repositorio:** AngieNavarroyh/Controles
- **Rama:** main

---

## 📝 Changelog

### Versión Actual
- ✅ Sistema completo de análisis CatPhan
- ✅ Controles diarios/mensuales/anuales para todos los equipos
- ✅ Generación automática de reportes PDF
- ✅ Gestión de usuarios y equipos
- ✅ Visualizador DICOM interactivo
- ✅ Base de datos SQLite con 30+ tablas

### Próximas Características
- 🔄 Análisis estadístico avanzado
- 🔄 Dashboard de tendencias históricas
- 🔄 Exportación a Excel
- 🔄 Notificaciones automáticas

---

## 📄 Licencia

[Especificar licencia]

---

**Última actualización:** Octubre 2025
**Mantenedor:** [Tu nombre/equipo]

---

## 🎓 Conceptos Clave para Nuevos Desarrolladores

### Patrón de Herencia
```
PruebaBasico (clase base)
    ↓
PruebaDiariaBraq, PruebaMensualTAC, etc. (clases específicas)
```
- Maximiza reutilización de código
- Mantiene consistencia en la interfaz
- Facilita mantenimiento

### Flujo de Datos
```
Usuario → Interfaz (Qt) → Análisis (OpenCV/NumPy) → BD (SQLite) → Reporte (PDF)
```

### OJO:
```
Es muy facil no encontrar los widgets de la interfaz, estos viven en ManejoDatos/widgets.xslx, ahí es muy importante definir el tipo de elemento QLineEdit/QComboBox/QLabel, etc, esta referencia es importante para cuando añadas nuevas funciones.
```

### Señales y Slots (PyQt)
```python
# Emisor
self.mi_senal.emit(datos)

# Receptor
self.mi_senal.connect(self.mi_funcion)
```

### Gestión de Memoria
- Usa `gc.collect()` después de análisis pesados
- Libera recursos con `del` cuando ya no se necesiten
- Implementa lazy loading para grandes volúmenes

---

**¡Bienvenido al proyecto! Happy coding! 🚀**
