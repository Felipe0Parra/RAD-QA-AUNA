import os
import pandas as pd
from reportlab.platypus import Image
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle, Paragraph
from PyQt5.QtCore import QByteArray
import io

def generar_reporte_pdf(df, fecha, user, tipo_reporte=" " , maquina=" ", 
                id_maquina = " ", nombre_pdf="lab_report.pdf",
                logo_path="logo.png", firma = None, role = "", temp = False):    
    from reportlab.lib.styles import getSampleStyleSheet
    styles = getSampleStyleSheet()
    c = canvas.Canvas(nombre_pdf, pagesize=letter)
    
    if temp:
        pdf_bytes = io.BytesIO()
        c = canvas.Canvas(pdf_bytes, pagesize=letter)
    else:
        c = canvas.Canvas(nombre_pdf, pagesize=letter)

    
    width, height = letter  

    # 🔹 Agregar un LOGO en la esquina superior izquierda
    if logo_path:
        try:
            c.drawImage(logo_path, 40, height - 80, width=120, height=50, mask='auto')  
        except:
            print("No se pudo cargar el logo, revisa la ruta.")

    # 🔹 Texto en la parte superior derecha (Nombre del programa)
    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(width - 40, height - 50, "Instituto de Cancerología Las Américas")
    c.setFont("Helvetica", 10)
    c.drawRightString(width - 40, height - 65, f"Control de calidad {tipo_reporte} {id_maquina}")

    # 🔹 Crear un rectángulo para el título
    c.setStrokeColor(colors.black)
    c.setFillColor(colors.lightgrey)
    c.rect(81, height - 150, 450, 60, fill=1)
    

    # 🔹 Agregar el título dentro del recuadro
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(300, height - 110, f"Control de calidad {tipo_reporte}" )

    c.setFont("Helvetica", 12)
    c.drawCentredString(300, height - 125, "Clínica Las Américas AUNA")
    c.setFont("Helvetica-Oblique", 10)
    c.drawCentredString(300, height - 140, "Instituto de Cancerología Las Américas")
    #c.setFont("Helvetica", 9)
    #c.drawCentredString(300, height - 152, "Formato unificado para informe de laboratorio")

    
    # 🔹 FECHA del reporte
    c.setFont("Helvetica-Bold", 12)
    c.drawString(81, height - 180, "Información general")
    
    # 🔹 maquina
    c.setFont("Helvetica", 10)
    c.drawString(81, height - 195, f"Máquina: {maquina}") 
    
    # 🔹
    c.setFont("Helvetica", 10)
    c.drawString(81, height - 210, f"Fecha: {fecha}")  
    
    # 🔹 
    c.setFont("Helvetica", 10)
    c.drawString(81, height - 225, f"Usuario: {user}")  
    

    # 🔹 Eliminar date, id y user_id del DataFrame
    #print(f'El df es como:\n{df}')
    df.drop(df[df[df.columns[0]]=='date'].index, inplace=True)
    df.drop(df[df[df.columns[0]]=='id'].index, inplace=True)
    df.drop(df[df[df.columns[0]]=='user_id'].index, inplace=True)
    obs_rows = df[df[df.columns[0]] == 'Observaciones']
    if not obs_rows.empty:
        # Toma solo la columna de valores (ajusta el índice según tu estructura)
        obs_text = obs_rows.iloc[0, 2]  # Suponiendo que la columna 2 es la de valores
        obs = [Paragraph(str(obs_text), styles["Normal"])]
    else:
        obs = []
    
    #obs.pop(-1)
    #nea = df[df[df.columns[0]]=='Observaciones']
    df.drop(df[df[df.columns[0]]=='Observaciones'].index, inplace=True)
    df.drop(df[df[df.columns[0]]=='pelicula'].index, inplace=True)
    #print(f'objetivos:\n{obs} \nsin objetivos: \n{df}')
    # 🔹 Ajuste de texto
    
    styles = getSampleStyleSheet()
    df["Valores"] = df["Valores"].apply(lambda text: Paragraph(str(text), styles["Normal"]))
    if not obs_rows.empty:
        obs_text = obs_rows.iloc[0, 2]
        obs = [obs_text]   # keep as raw text
    else:
        obs = [""]

    # Later convert ONLY once:
    obs = [Paragraph(str(text), styles["Normal"]) for text in obs]
    
    # 🔹 Convertir DataFrame a lista de listas para la tabla
    data = [df.columns.tolist()] + df.values.tolist()  + [obs]
    #print(f'Data es: \n{data}')
    # 🔹 Calcular el ancho de las columnas
    #ancho = 450 / len(df.columns)
    ancho = [None] * len(df.columns)
    from reportlab.pdfbase.pdfmetrics import stringWidth
    
    for i in range(len(df.columns)):
        if i == 0:
            n = 450*0.33
            ancho[i] = n
        else:
            n = 450*0.67/(len(df.columns)-1)
            ancho[i] = n

    # 🔹 Crear la tabla
    table = Table(data, colWidths= ancho)
    table.setStyle(TableStyle([
        ("SPAN", (1, -1), (-1, -1)), 
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#01b0ca")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 7.5),
    ]))

    # 🔹 Manejo de paginación de la tabla
    x_start, y_start = 81, height - 245  # Posición inicial
    available_height = y_start - 80  # Espacio disponible en la primera página

    parts = table.split(width, available_height)  # Divide la tabla en partes

    for i, part in enumerate(parts):
        if i > 0:  # Si no es la primera página, agrega una nueva
            c.showPage()
            y_start = height - 50  # Reinicia la posición en la nueva página

        part.wrapOn(c, width, height)
        part.drawOn(c, x_start, y_start - part._height)  # Dibuja la parte de la tabla

    #linea de firma
    c.setStrokeColor(colors.black)
    c.setLineWidth(1)
    c.line(100,80-40, 300, 80-40)

    if firma:
        try:
            c.drawImage(firma, 100, 95-30, width=150, height=50, mask='auto')  
        except:
            print("No se pudo cargar la firma, revisa la ruta.")
            
    # 🔹 Agregar texto de firma
    c.setFont("Helvetica", 12)
    c.drawString(100, 65-40, user)
    
    c.setFont("Helvetica", 12)
    c.drawString(100,  50, role)
    
    c.save()
    #print(f"PDF guardado como {nombre_pdf}")

    if temp:
        pdf_bytes.seek(0)
        pdf_data = pdf_bytes.read()
        qbyte_array = QByteArray(pdf_data)
        
        
        return qbyte_array

def generar_reporte_pdf_multitabla_mensual(tablas, fecha, user, tipo_reporte=" ", maquina=" ", id_maquina=" ", nombre_pdf="reporte_multitabla.pdf",
                                    logo_path="logo.png", firma=None, role="", user2=None, firma2=None, role2=None, temp=False, sistema_imagenes=False):
    
    """Genera un PDF con múltiples tablas separadas
    
    Args:
        user2: Nombre del segundo usuario (físico 2), opcional
        firma2: Ruta de la firma del segundo usuario, opcional
        role2: Rol del segundo usuario, opcional
    """
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Spacer
    from reportlab.lib.units import inch
    
    styles = getSampleStyleSheet()
    if temp:
        pdf_bytes = io.BytesIO()
        doc = SimpleDocTemplate(pdf_bytes, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=245, bottomMargin=100)
    else:
        doc = SimpleDocTemplate(nombre_pdf, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=245, bottomMargin=100)
    
    # Función para agregar encabezado y pie de página
    def add_header_footer(canvas, doc):
        width, height = letter
        
        # Agregar logo
        if logo_path:
            try:
                canvas.drawImage(logo_path, 40, height - 80, width=120, height=50, mask='auto')
            except:
                print("No se pudo cargar el logo, revisa la ruta.")
        
        # Texto superior derecho
        canvas.setFont("Helvetica-Bold", 10)
        canvas.drawRightString(width - 40, height - 50, "Instituto de Cancerología Las Américas")
        canvas.setFont("Helvetica", 10)
        canvas.drawRightString(width - 40, height - 65, f"Control de calidad {tipo_reporte} {id_maquina}")
        
        # Rectángulo del título
        canvas.setStrokeColor(colors.black)
        canvas.setFillColor(colors.lightgrey)
        canvas.rect(40, height - 150, width - 80, 60, fill=1)
        
        # Título dentro del rectángulo
        canvas.setFillColor(colors.black)
        canvas.setFont("Helvetica-Bold", 14)
        canvas.drawCentredString(width/2, height - 110, f"Control de calidad {tipo_reporte}")
        canvas.setFont("Helvetica", 12)
        canvas.drawCentredString(width/2, height - 125, "Clínica Las Américas AUNA")
        canvas.setFont("Helvetica-Oblique", 10)
        canvas.drawCentredString(width/2, height - 140, "Instituto de Cancerología Las Américas")
        
        # Información general
        canvas.setFont("Helvetica-Bold", 12)
        canvas.drawString(40, height - 180, "Información general")
        canvas.setFont("Helvetica", 10)
        canvas.drawString(40, height - 195, f"Máquina: {'GammaMedPlus iX' if maquina == 'Braquiterapia' else maquina}")
        canvas.drawString(40, height - 210, f"Fecha: {fecha}")
        canvas.drawString(40, height - 225, f"Físico Médico: {user}")
        canvas.drawString(40, height - 240, f"Físico Médico 2: {user2}" if user2 else "")
        
        # Líneas de firma en pie de página
        canvas.setStrokeColor(colors.black)
        canvas.setLineWidth(1)
        
        # Si hay segundo usuario, dividir el espacio para dos firmas
        if user2:
            # Línea de firma 1 (izquierda)
            canvas.line(80, 50, 260, 50) 
            
            # Firma 1 si existe
            if firma:
                try:
                    canvas.drawImage(firma, 90, 55, width=140, height=50, mask='auto')
                except:
                    print("No se pudo cargar la firma 1, revisa la ruta.")
            
            # Texto de firma 1
            canvas.setFont("Helvetica", 10)
            canvas.drawString(80, 40, user)
            canvas.drawString(80, 20, role)
            
            # Línea de firma 2 (derecha)
            canvas.line(340, 50, 520, 50)
            
            # Firma 2 si existe
            if firma2:
                try:
                    canvas.drawImage(firma2, 350, 55, width=140, height=50, mask='auto')
                except:
                    print("No se pudo cargar la firma 2, revisa la ruta.")
            
            # Texto de firma 2
            canvas.setFont("Helvetica", 10)
            canvas.drawString(340, 40, user2)
            canvas.drawString(340, 20, role2 if role2 else "")
        else:
            # Solo una firma (centrada)
            canvas.line(100, 50, 300, 50)
            
            # Firma si existe
            if firma:
                try:
                    canvas.drawImage(firma, 110, 55, width=150, height=50, mask='auto')
                except:
                    print("No se pudo cargar la firma, revisa la ruta.")
            
            # Texto de firma
            canvas.setFont("Helvetica", 12)
            canvas.drawString(100, 40, user)
            canvas.drawString(100, 20, role)
    
    # Crear elementos del documento
    elements = []
    
    # Agregar espaciador inicial
    elements.append(Spacer(1, 0.5*inch))
    
    # Procesar cada tabla
    if maquina == 'Halcyon' and not sistema_imagenes:
        print('Generando reporte de Halcyon sin sistema de imágenes...')
        orden_tablas = ['equipos', 'aspectos_mecanicos_gantry', 'aspectos_mecanicos_colimador', 'indicadores_laser', 'indicadores_camilla',
                        'desplazamiento_isocentro', 'tamanos_campo', 'dosimetricos']
        
    elif (maquina ==  'Tomógrafo' and sistema_imagenes) or (maquina == 'Halcyon' and sistema_imagenes) or (maquina == 'Clinac ix' and sistema_imagenes):
        print('Generando reporte de sistema de imágenes...')
        orden_tablas = ['espesor', 'parametros_espesor','imagen_espesor', 'tamano_pixel', 'parametros_tamano_pixel', 'imagen_tamano_pixel', 
                        'parametros_resolucion_contraste', 'resolucion_contraste', 'imagen_resolucion_contraste', 'resolucion_espacial', 
                        'parametros_resolucion_espacial', 'imagen_resolucion_espacial', 'valores_ct', 'parametros_valores_ct', 'imagen_valores_ct',
                        'linealidad_ct', 'parametros_linealidad_ct', 'imagen_linealidad_ct','uniformidad', 'parametros_uniformidad', 'imagen_uniformidad']
    
    elif maquina == 'Braquiterapia':
        print('Generando reporte de Braquiterapia...')
        # Detectar si es Linealidad o Control Mensual/Cambio de Fuente
        if 'sistema_medicion_linealidad' in tablas:
            # Reporte de Linealidad
            orden_tablas = ['sistema_medicion_linealidad', 'carga_colectada', 'medidas_linealidad', 
                          'resultados_linealidad', 'grafico_linealidad']
        else:
            # Reporte de Control Mensual/Cambio de Fuente
            orden_tablas = ['tipo_calibracion', 'sistema_medicion', 'condiciones_medicion', 
                          'maximos_camaras', 'grafico_maximos', 'lecturas_maximos', 
                          'grafico_lecturas', 'resultados_actividad']
    
    else:
        orden_tablas = ['equipos', 'seguridad', 'aspectos_mecanicos_gantry', 'aspectos_mecanicos_colimador', 'preguntas',
                        'tamanos_campo', 'imagen','analisis_imagen', 'dosimetricos']

    for i, nombre_tabla in enumerate(orden_tablas):
        if nombre_tabla in tablas:
            df_tabla = tablas[nombre_tabla]
            
            if not df_tabla.empty:
                # Convertir DataFrame a datos de tabla
                data = [df_tabla.columns.tolist()] + df_tabla.values.tolist()

                # Crear estilo centrado para celdas
                from reportlab.lib.enums import TA_CENTER
                centered_style = styles["Normal"]
                centered_style.alignment = TA_CENTER

                # Reemplazar rutas de imagen por objetos Image y convertir todo a Flowables
                for row_idx, row in enumerate(data):
                    for col_idx, cell in enumerate(row):
                        # Si ya es un Flowable (Paragraph, Image, etc.), no lo toques
                        if isinstance(cell, (Paragraph, Image)):
                            continue
                        # Si es una imagen en base64 (de los gráficos de braquiterapia)
                        elif isinstance(cell, str) and cell.startswith('iVBORw0KGgo'):  # Base64 de PNG
                            import base64
                            img_data = base64.b64decode(cell)
                            img_buffer = io.BytesIO(img_data)
                            data[row_idx][col_idx] = Image(img_buffer, width=5*inch, height=3*inch)
                        # Si es una ruta de imagen válida
                        elif isinstance(cell, str) and os.path.isfile(cell) and cell.lower().endswith(('.png', '.jpg', '.jpeg')):
                            data[row_idx][col_idx] = Image(cell, width=2.5*inch, height=2.5*inch)
                        # Si es string, conviértelo a Paragraph centrado
                        elif isinstance(cell, str):
                            data[row_idx][col_idx] = Paragraph(cell, centered_style)
                        # Si es None, ponlo como string vacío
                        elif cell is None:
                            data[row_idx][col_idx] = Paragraph("", centered_style)
                        # Si es un número, conviértelo a string y luego a Paragraph
                        elif isinstance(cell, (int, float)):
                            data[row_idx][col_idx] = Paragraph(str(cell), centered_style)
                        # Cualquier otro tipo, convertir a string y luego a Paragraph
                        else:
                            data[row_idx][col_idx] = Paragraph(str(cell), centered_style)
                # Crear tabla
                if nombre_tabla == 'equipos':
                    # Tabla de equipos de una sola columna
                    tabla = Table(data, colWidths=[1.5*inch])

                elif nombre_tabla == 'tamanos_campo' and maquina.lower() != 'halcyon':
                    # Tabla de tamaños de campo con columnas específicas
                    col_widths = [1*inch, 0.6*inch, 0.6*inch, 0.6*inch, 0.6*inch, 
                                    0.6*inch, 0.6*inch, 0.6*inch, 0.6*inch]
                    tabla = Table(data, colWidths=col_widths)
                
                elif nombre_tabla == 'tamanos_campo' and maquina.lower() == 'halcyon':
                    # Tabla de tamaños de campo específica para Halcyon
                    col_widths = [1.5*inch, 1.5*inch, 1.5*inch, 1.5*inch]
                    tabla = Table(data, colWidths=col_widths)
                    
                elif nombre_tabla == 'analisis_imagen':
                    # Tabla de análisis de imagen con columnas dinámicas
                    num_cols = len(df_tabla.columns)
                    col_width = 5.5*inch / num_cols
                    tabla = Table(data, colWidths=[col_width] * num_cols)
                
                elif nombre_tabla == 'dosimetricos':
                    # Tabla dosimétrica de una columna
                    tabla = Table(data, colWidths=[7*inch])
                
                # Tablas de Braquiterapia
                elif nombre_tabla in ['tipo_calibracion', 'sistema_medicion', 'condiciones_medicion', 
                                    'sistema_medicion_linealidad', 'carga_colectada', 'resultados_linealidad', 
                                    'resultados_actividad']:
                    # Tablas de 2 columnas: Campo | Valor
                    tabla = Table(data, colWidths=[3*inch, 3*inch])
                
                elif nombre_tabla in ['maximos_camaras', 'lecturas_maximos']:
                    # Tablas con múltiples columnas de medidas
                    num_cols = len(df_tabla.columns)
                    col_width = 6*inch / num_cols
                    tabla = Table(data, colWidths=[col_width] * num_cols)
                
                elif nombre_tabla == 'medidas_linealidad':
                    # Tabla de medidas de linealidad: 5 columnas
                    col_widths = [1.2*inch, 1.2*inch, 1.2*inch, 1.2*inch, 1.2*inch]
                    tabla = Table(data, colWidths=col_widths)
                
                elif nombre_tabla in ['grafico_maximos', 'grafico_lecturas', 'grafico_linealidad']:
                    # Tablas de gráficos (una sola columna con imagen)
                    tabla = Table(data, colWidths=[6*inch])
                
                else:
                    # Tablas con ancho automático
                    num_cols = len(df_tabla.columns)
                    col_width = 5.5*inch / num_cols
                    tabla = Table(data, colWidths=[col_width] * num_cols)
                
                # Estilo de tabla
                style = [
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#01b0ca")),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('FONTSIZE', (0, 1), (-1, -1), 8),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ]

                # Estilos específicos por tabla
                if nombre_tabla == 'tamanos_campo' and maquina.lower() != 'halcyon':
                    # Fusionar celdas para encabezados agrupados
                    style.extend([
                        ('SPAN', (0, 0), (8, 0)),  # Encabezado
                        ('SPAN', (0, 1), (0, 3)),  # Campo nominal
                        ('SPAN', (1, 1), (4, 1)),  # Indicador del equipo, los paréntesis indican (columna_inicio, fila_inicio), (columna_fin, fila_fin)
                        ('SPAN', (5, 1), (8, 1)),  # Indicador de la consola
                        ('SPAN', (1, 2), (2, 2)),  # Largo equipo
                        ('SPAN', (3, 2), (4, 2)),  # Ancho equipo
                        ('SPAN', (5, 2), (6, 2)),  # Largo consola
                        ('SPAN', (7, 2), (8, 2)),  # Ancho consola
                    ])
                elif nombre_tabla == 'tamanos_campo' and maquina.lower() == 'halcyon':
                    # Estilos específicos para Halcyon
                    style.extend([
                        ('SPAN', (0, 0), (-1, 0)),  # Encabezado
                        ('SPAN', (0, 1), (1, 1)),  # (columna_inicio, fila_inicio), (columna_fin, fila_fin)
                        ('SPAN', (2, 1), (3, 1)),  # (columna_inicio, fila_inicio), (columna_fin, fila_fin)
                    ])

                elif nombre_tabla in ['equipos', 'aspectos_mecanicos_gantry', 'aspectos_mecanicos_colimador', 
                                    'preguntas', 'seguridad', 'analisis_imagen', 'indicadores_laser', 'desplazamiento_isocentro',
                                    'parametros', 'espesor', 'tamano_pixel', 'resolucion_espacial',  
                                    'valores_ct', 'linealidad_ct', 'uniformidad', 'parametros_espesor', 'parametros_tamano_pixel', 
                                    'parametros_resolucion_contraste', 'parametros_resolucion_espacial', 'parametros_valores_ct',
                                    'parametros_linealidad_ct', 'parametros_uniformidad']:
                    style.extend([
                        ('SPAN', (0, 0), (-1, 0)),
                        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#bfeff6")),
                        ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
                    ])

                # Estilos para tablas de Braquiterapia
                elif nombre_tabla in ['tipo_calibracion', 'sistema_medicion', 'condiciones_medicion',
                                    'sistema_medicion_linealidad', 'carga_colectada', 'resultados_linealidad',
                                    'resultados_actividad']:
                    # Tablas de 2 columnas con encabezado
                    style.extend([
                        ('SPAN', (0, 0), (-1, 0)),
                        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#bfeff6")),
                        ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
                        ('ALIGN', (0, 1), (0, -1), 'LEFT'),  # Alinear campo a la izquierda
                        ('ALIGN', (1, 1), (1, -1), 'CENTER'),  # Alinear valor al centro
                    ])

                elif nombre_tabla in ['maximos_camaras', 'lecturas_maximos', 'medidas_linealidad']:
                    # Tablas de medidas con encabezado
                    style.extend([
                        ('SPAN', (0, 0), (-1, 0)),
                        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#bfeff6")),
                        ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
                    ])

                elif nombre_tabla in ['grafico_maximos', 'grafico_lecturas', 'grafico_linealidad']:
                    # Tablas de gráficos - solo título y imagen
                    style.extend([
                        ('SPAN', (0, 0), (-1, 0)),
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#01b0ca")),
                        ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
                        ('VALIGN', (0, 1), (-1, -1), 'MIDDLE'),
                    ])

                elif nombre_tabla == 'indicadores_camilla':
                    # Resaltar la primera fila de encabezados
                    style.extend([
                                    ('SPAN', (0, 0), (-1, 0)),
                                    ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#bfeff6")),
                                    ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
                                    ('SPAN', (0, 2), (0, 4)),  # Campo nominal (columna_inicio, fila_inicio), (columna_fin, fila_fin)
                                    ('SPAN', (0, 5), (0, 7)),  # Dosis medida
                                    ('SPAN', (0, 8), (0, 10)),
                                ])

                elif nombre_tabla == 'dosimetricos':
                    # Resaltar secciones principales
                    for row_idx, row in enumerate(data):
                        if row and any('ASPECTOS DOSIMÉTRICOS' in str(cell) or 'HACES DE' in str(cell) for cell in row):
                            style.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor("#01b0ca")))
                            style.append(('FONTNAME', (0, row_idx), (-1, row_idx), 'Helvetica-Bold'))
                        elif row and any('Nominal' in str(cell) for cell in row):
                            style.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.lightgrey))
                            style.append(('FONTNAME', (0, row_idx), (-1, row_idx), 'Helvetica-Bold'))

                elif nombre_tabla in ['imagen_espesor', 'imagen_tamano_pixel', 'imagen_resolucion_contraste', 'imagen_resolucion_espacial',
                                    'imagen_valores_ct', 'imagen_linealidad_ct', 'imagen_uniformidad']:
                    style.extend([
                        ('SPAN', (0, 1), (-1, 1)),
                    ])

                elif nombre_tabla == 'resolucion_contraste':
                    
                    style.extend([
                        ('SPAN', (0, 0), (-1, 0)),
                        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#bfeff6")),
                        ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
                    ])

                    for row_idx, row in enumerate(data):
                        if row and any('RESUMEN' in str(cell) for cell in row):
                            style.append(('SPAN', (0, row_idx), (-1, row_idx)))
                            style.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor("#c8fcf6")))
                            style.append(('FONTNAME', (0, row_idx), (-1, row_idx), 'Helvetica-Bold'))

                        # Aplicar estilo a la tabla
                            style.append(('SPAN', (1, row_idx + 1), (-1, row_idx + 1)))
                            style.append(('SPAN', (1, row_idx + 2), (-1, row_idx + 2)))


                tabla.setStyle(TableStyle(style))
                from reportlab.platypus import KeepTogether
                elements.append(KeepTogether(tabla))  # <-- Envuelve la tabla
                
                # Agregar espaciador entre tablas (excepto la última)
                if i < len(orden_tablas) - 1:
                        elements.append(Spacer(1, 0.3*inch))
        # ════════════════════════════════════════════════════════════════
    #  SECCIÓN 7 — Interpretación de métricas
    # ════════════════════════════════════════════════════════════════

    metricas_data = [
        [P("Definiciones de métricas", bold=True, size=10), ""],

        [P("Métrica", bold=True),
        P("Descripción", bold=True)],

        [
            Pl("Radio de convergencia"),
            Pl(
                "Radio mínimo que contiene todos los rayos detectados. "
                "Es el criterio principal de aceptación del ensayo Starshot."
            )
        ],

        [
            Pl("RMS residuos"),
            Pl(
                "Mide la dispersión global de las intersecciones respecto "
                "al centroide. Valores menores indican mejor consistencia "
                "geométrica."
            )
        ],

        [
            Pl("Máximo residuo"),
            Pl(
                "Mayor desviación observada entre las intersecciones "
                "detectadas. Representa el peor caso encontrado."
            )
        ],

        [
            Pl("STD residuos"),
            Pl(
                "Desviación estándar de las distancias al centroide. "
                "Describe la variabilidad de la nube de intersecciones."
            )
        ],

        [
            Pl("Desviación angular"),
            Pl(
                "Diferencia entre el ángulo nominal esperado y el ángulo "
                "real detectado para cada spoke."
            )
        ],

        [
            Pl("Error de separación angular"),
            Pl(
                "Diferencia entre la separación angular ideal y la "
                "separación observada entre spokes consecutivos."
            )
        ],
    ]

    metricas_table = Table(
        metricas_data,
        colWidths=[1.8 * inch, 4.7 * inch]
    )

    metricas_table.setStyle(TableStyle([
        ("SPAN",       (0, 0), (1, 0)),
        ("BACKGROUND", (0, 0), (1, 0), _CYAN),
        ("TEXTCOLOR",  (0, 0), (1, 0), _WHITE),

        ("BACKGROUND", (0, 1), (1, 1), _CYAN_LITE),
        ("FONTNAME",   (0, 1), (1, 1), "Helvetica-Bold"),

        ("GRID",       (0, 0), (-1, -1), 0.5, _BLACK),
        ("VALIGN",     (0, 0), (-1, -1), "TOP"),

        ("ROWBACKGROUNDS",
        (0, 2), (-1, -1),
        [_WHITE, colors.HexColor("#f9f9f9")]),
    ]))

    elements.append(KeepTogether(metricas_table))
    elements.append(Spacer(1, 0.3 * inch))
    # Construir el documento
    doc.build(elements, onFirstPage=add_header_footer, onLaterPages=add_header_footer)
    
    if temp:
        pdf_bytes.seek(0)
        pdf_data = pdf_bytes.read()
        qbyte_array = QByteArray(pdf_data)
        return qbyte_array

def generar_reporte_pdf_multitabla_anual(tablas_dict, fecha, user, tipo_reporte=" ", maquina=" ", 
                                    id_maquina=" ", nombre_pdf="reporte_anual_multitabla.pdf",
                                    logo_path="logo.png", firma=None, role="", 
                                    user2=None, firma2=None, role2=None, temp=False, sistema_imagenes=False):
    """Genera un PDF con múltiples tablas para reportes anuales
    
    Args:
        tablas_dict: Diccionario con las tablas organizadas por categoría
                    Ejemplo: {
                        'equipos': DataFrame,
                        'factores_campo': [{'titulo': str, 'dataframe': DataFrame}, ...],
                        'factores_transmision': [...],
                        'factores_sobre_eje': [...],
                        'control_camaras': [...]
                    }
        user2: Nombre del segundo usuario (físico 2), opcional
        firma2: Ruta de la firma del segundo usuario, opcional
        role2: Rol del segundo usuario, opcional
    """
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Spacer, PageBreak, Paragraph, KeepTogether
    from reportlab.lib.units import inch
    
    styles = getSampleStyleSheet()
    
    if temp:
        pdf_bytes = io.BytesIO()
        doc = SimpleDocTemplate(pdf_bytes, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=245, bottomMargin=100)
    else:
        doc = SimpleDocTemplate(nombre_pdf, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=245, bottomMargin=100)
    
    # Función para agregar encabezado y pie de página
    def add_header_footer(canvas, doc):
        width, height = letter
        
        # Agregar logo
        if logo_path:
            try:
                canvas.drawImage(logo_path, 40, height - 80, width=120, height=50, mask='auto')
            except:
                print("No se pudo cargar el logo, revisa la ruta.")
        
        # Texto superior derecho
        canvas.setFont("Helvetica-Bold", 10)
        canvas.drawRightString(width - 40, height - 50, "Instituto de Cancerología Las Américas")
        canvas.setFont("Helvetica", 10)
        canvas.drawRightString(width - 40, height - 65, f"Control de calidad {tipo_reporte} {id_maquina}")
        
        # Rectángulo del título
        canvas.setStrokeColor(colors.black)
        canvas.setFillColor(colors.lightgrey)
        canvas.rect(40, height - 150, width - 80, 60, fill=1)
        
        # Título dentro del rectángulo
        canvas.setFillColor(colors.black)
        canvas.setFont("Helvetica-Bold", 14)
        canvas.drawCentredString(width/2, height - 110, f"Control de calidad {tipo_reporte}")
        canvas.setFont("Helvetica", 12)
        canvas.drawCentredString(width/2, height - 125, "Clínica Las Américas AUNA")
        canvas.setFont("Helvetica-Oblique", 10)
        canvas.drawCentredString(width/2, height - 140, "Instituto de Cancerología Las Américas")
        
        # Información general
        canvas.setFont("Helvetica-Bold", 12)
        canvas.drawString(40, height - 180, "Información general")
        canvas.setFont("Helvetica", 10)
        canvas.drawString(40, height - 195, f"Máquina: {maquina}")
        canvas.drawString(40, height - 210, f"Fecha: {fecha}")
        canvas.drawString(40, height - 225, f"Físico Médico: {user}")
        canvas.drawString(40, height - 240, f"Físico Médico 2: {user2}" if user2 else "")
        
        # Líneas de firma en pie de página
        canvas.setStrokeColor(colors.black)
        canvas.setLineWidth(1)
        
        # Si hay segundo usuario, dividir el espacio para dos firmas
        if user2:
            # Línea de firma 1 (izquierda)
            canvas.line(80, 70, 260, 70)
            
            # Firma 1 si existe
            if firma and os.path.isfile(firma):
                try:
                    canvas.drawImage(firma, 90, 85, width=80, height=30, mask='auto')
                except Exception as e:
                    print("No se pudo cargar la firma 1:", e)
            
            # Texto de firma 1
            canvas.setFont("Helvetica", 10)
            canvas.drawString(80, 55, user)
            canvas.drawString(80, 40, role)
            
            # Línea de firma 2 (derecha)
            canvas.line(340, 70, 520, 70)
            
            # Firma 2 si existe
            if firma2 and os.path.isfile(firma2):
                try:
                    canvas.drawImage(firma2, 350, 85, width=80, height=30, mask='auto')
                except Exception as e:
                    print("No se pudo cargar la firma 2:", e)
            
            # Texto de firma 2
            canvas.setFont("Helvetica", 10)
            canvas.drawString(340, 55, user2)
            canvas.drawString(340, 40, role2 if role2 else "")
        else:
            # Solo una firma (centrada)
            canvas.line(100, 70, 300, 70)
            
            # Firma si existe
            if firma and os.path.isfile(firma):
                try:
                    canvas.drawImage(firma, 110, 85, width=80, height=30, mask='auto')
                except Exception as e:
                    print("No se pudo cargar la firma:", e)
            else:
                print("Firma no encontrada o ruta inválida:", firma)
            
            # Texto de firma
            canvas.setFont("Helvetica", 12)
            canvas.drawString(100, 55, user)
            canvas.drawString(100, 40, role)
    
    # Crear elementos del documento
    elements = []
    
    # Agregar espaciador inicial
    elements.append(Spacer(1, 0.5*inch))
    
    # Orden de procesamiento de tablas para reportes anuales
    if maquina == 'Clinac ix':
        orden_categorias = [
            'equipos', 'factores_campo', 'factores_transmision', 
            'factores_sobre_eje', 'control_camaras'
        ]
        # Agregar tablas del sistema de imágenes si existen
        orden_categorias_img = [
            'espesor', 'parametros_espesor', 'imagen_espesor', 
            'tamano_pixel', 'parametros_tamano_pixel', 'imagen_tamano_pixel',
            'parametros_resolucion_contraste', 'resolucion_contraste', 'imagen_resolucion_contraste',
            'resolucion_espacial', 'parametros_resolucion_espacial', 'imagen_resolucion_espacial',
            'valores_ct', 'parametros_valores_ct', 'imagen_valores_ct',
            'linealidad_ct', 'parametros_linealidad_ct', 'imagen_linealidad_ct',
            'uniformidad', 'parametros_uniformidad', 'imagen_uniformidad'
        ]
        # Agregar al final las tablas de imágenes si existen
        for cat_img in orden_categorias_img:
            if cat_img in tablas_dict:
                orden_categorias.append(cat_img)
                
    elif maquina == 'Halcyon':
        orden_categorias = [
            'equipos', 'indicadores_angulares_gantry', 'indicadores_angulares_colimador',
            'indicadores_laser', 'indicadores_camilla', 'velocidad_multilaminas',
            'precision_posicion_multilaminas', 'imagen_perfil_mlc', 'dosimetria', 'linealidad_unidades_monitor',
            'tamanos_campo_dosis'
        ]
        # Agregar tablas del sistema de imágenes si existen
        orden_categorias_img = [
            'espesor', 'parametros_espesor', 'imagen_espesor', 
            'tamano_pixel', 'parametros_tamano_pixel', 'imagen_tamano_pixel',
            'parametros_resolucion_contraste', 'resolucion_contraste', 'imagen_resolucion_contraste',
            'resolucion_espacial', 'parametros_resolucion_espacial', 'imagen_resolucion_espacial',
            'valores_ct', 'parametros_valores_ct', 'imagen_valores_ct',
            'linealidad_ct', 'parametros_linealidad_ct', 'imagen_linealidad_ct',
            'uniformidad', 'parametros_uniformidad', 'imagen_uniformidad'
        ]
        # Agregar al final las tablas de imágenes si existen
        for cat_img in orden_categorias_img:
            if cat_img in tablas_dict:
                orden_categorias.append(cat_img)
                
    else:
        orden_categorias = [
            'equipos', 'factores_campo', 'factores_transmision', 
            'factores_sobre_eje', 'control_camaras'
        ]

    # Procesar cada categoría de tablas
    for categoria in orden_categorias:
        if categoria not in tablas_dict:
            continue
            
        contenido = tablas_dict[categoria]
        
        # Si es la tabla de equipos o una tabla del sistema de imágenes (DataFrame simple)
        # Mostrar texto antes de las tablas del sistema de imágenes
        if categoria == 'titulo_sistema_imagenes':
            from reportlab.platypus import Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet
            styles = getSampleStyleSheet()
            elements.append(Spacer(1, 0.2*inch))
            elements.append(Paragraph(tablas_dict[categoria], styles['Heading2']))
            elements.append(Spacer(1, 0.2*inch))
            continue

        contenido = tablas_dict[categoria]

        if categoria in ['equipos', 'espesor', 'tamano_pixel', 'resolucion_contraste', 'resolucion_espacial',
                        'valores_ct', 'linealidad_ct', 'uniformidad', 
                        'parametros_espesor', 'parametros_tamano_pixel', 'parametros_resolucion_contraste',
                        'parametros_resolucion_espacial', 'parametros_valores_ct', 'parametros_linealidad_ct',
                        'parametros_uniformidad', 'imagen_espesor', 'imagen_tamano_pixel', 'imagen_resolucion_contraste',
                        'imagen_resolucion_espacial', 'imagen_valores_ct', 'imagen_linealidad_ct', 'imagen_uniformidad']:
            if isinstance(contenido, type(pd.DataFrame())) and not contenido.empty:        
                # Crear y agregar la tabla
                tabla_pdf = _crear_tabla_pdf_anual(contenido, categoria, maquina)
                if tabla_pdf:
                    elements.append(KeepTogether(tabla_pdf))
                    elements.append(Spacer(1, 0.3*inch))
        
        # Si es una lista de tablas con títulos (factores de campo, transmisión, etc.)
        elif isinstance(contenido, list):
            for i, tabla_info in enumerate(contenido):
                if not isinstance(tabla_info, dict) or 'dataframe' not in tabla_info:
                    continue
                
                df_tabla = tabla_info['dataframe']
                titulo_tabla = tabla_info.get('titulo', f'{categoria.replace("_", " ").title()}')
                
                if df_tabla.empty:
                    continue
                
                # Agregar título de la tabla
                if maquina == 'Clinac ix':
                    titulo_elemento = Paragraph(
                        f'<b>{titulo_tabla}</b>',
                        styles['Normal']
                    )
                    elements.append(titulo_elemento)
                    elements.append(Spacer(1, 0.08*inch)) 
                else:
                    pass
                
                # Crear y agregar la tabla
                tabla_pdf = _crear_tabla_pdf_anual(df_tabla, categoria, maquina)
                if tabla_pdf:
                    elements.append(KeepTogether(tabla_pdf))
                    elements.append(Spacer(1, 0.3*inch))
                
                # Agregar salto de página después de cada 3 tablas para mejor legibilidad
                if (i + 1) % 3 == 0 and i < len(contenido) - 1:
                    elements.append(PageBreak())

    # Construir el documento
    doc.build(elements, onFirstPage=add_header_footer, onLaterPages=add_header_footer)
    
    if temp:
        pdf_bytes.seek(0)
        pdf_data = pdf_bytes.read()
        qbyte_array = QByteArray(pdf_data)
        return qbyte_array

def _crear_tabla_pdf_anual(df_tabla, tipo_tabla, maquina):
    """Crea una tabla PDF con el estilo apropiado para reportes anuales
    
    Args:
        df_tabla: DataFrame con los datos
        tipo_tabla: Tipo de tabla ('equipos', 'factores_campo', etc.)
        maquina: Nombre de la máquina
        
    Returns:
        Objeto Table de reportlab con estilos aplicados
    """
    from reportlab.lib.units import inch
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.enums import TA_CENTER
    
    styles = getSampleStyleSheet()
    
    # Crear estilo centrado para celdas
    centered_style = styles["Normal"]
    centered_style.alignment = TA_CENTER
    
    # Convertir DataFrame a datos de tabla
    data = [df_tabla.columns.tolist()] + df_tabla.values.tolist()
    
    # Convertir todas las celdas a Flowables (Paragraph o Image)
    for row_idx, row in enumerate(data):
        for col_idx, cell in enumerate(row):
            # Si ya es un Flowable (Paragraph, Image, etc.), no lo toques
            if isinstance(cell, (Paragraph, Image)):
                continue
            # Si es una ruta de imagen válida
            elif isinstance(cell, str) and os.path.isfile(cell) and cell.lower().endswith(('.png', '.jpg', '.jpeg')):
                if tipo_tabla == 'imagen_perfil_mlc':
                    data[row_idx][col_idx] = Image(cell, width=5.5*inch, height=3*inch)
                elif tipo_tabla in ['imagen_espesor', 'imagen_tamano_pixel', 'imagen_resolucion_contraste',
                                    'imagen_resolucion_espacial', 'imagen_valores_ct', 'imagen_linealidad_ct',
                                    'imagen_uniformidad']:
                    # Imágenes del sistema de imágenes - tamaño ajustado para caber en la tabla
                    data[row_idx][col_idx] = Image(cell, width=3.8*inch, height=3.8*inch)
                else:
                    data[row_idx][col_idx] = Image(cell, width=3*inch, height=2.5*inch)
            # Si es string, conviértelo a Paragraph centrado
            elif isinstance(cell, str):
                data[row_idx][col_idx] = Paragraph(cell, centered_style)
            # Si es None, ponlo como string vacío
            elif cell is None:
                data[row_idx][col_idx] = Paragraph("", centered_style)
            # Si es un número, conviértelo a string y luego a Paragraph
            elif isinstance(cell, (int, float)):
                data[row_idx][col_idx] = Paragraph(str(cell), centered_style)
            # Cualquier otro tipo, convertir a string y luego a Paragraph
            else:
                data[row_idx][col_idx] = Paragraph(str(cell), centered_style)
    
    # Determinar anchos de columna según el tipo de tabla
    num_cols = len(df_tabla.columns)
    
    if tipo_tabla == 'equipos':
        # Tabla de equipos: 4 columnas
        col_widths = [1.5*inch, 1.3*inch, 1.2*inch, 1.5*inch]
    elif tipo_tabla in ['factores_campo', 'factores_transmision', 'factores_sobre_eje']:
        # Tablas de factores: 4 columnas generalmente
        col_width = 5.5*inch / num_cols
        col_widths = [col_width] * num_cols
    elif tipo_tabla == 'control_camaras':
        # Tabla de control de cámaras: 2 columnas
        col_widths = [3*inch, 2.5*inch]
    elif tipo_tabla == 'indicadores_angulares_gantry':
        col_widths = [2*inch, 1.5*inch, 1.5*inch]
    elif tipo_tabla == 'indicadores_angulares_colimador':
        col_widths = [2*inch, 1.5*inch, 1.5*inch]
    elif tipo_tabla == 'indicadores_laser':
        col_widths = [2*inch, 1.5*inch, 1.5*inch]
    elif tipo_tabla == 'indicadores_camilla':
        col_widths = [2*inch, 1.5*inch, 1.5*inch]
    elif tipo_tabla == 'velocidad_multilaminas':
        col_widths = [1.5*inch]
    elif tipo_tabla == 'precision_posicion_multilaminas':
        col_widths = [2*inch, 1.5*inch, 1.5*inch]
    elif tipo_tabla == 'imagen_perfil_mlc':
        col_widths = [5.5*inch]
    elif tipo_tabla in ['imagen_espesor', 'imagen_tamano_pixel', 'imagen_resolucion_contraste',
                       'imagen_resolucion_espacial', 'imagen_valores_ct', 'imagen_linealidad_ct',
                       'imagen_uniformidad']:
        # Tablas de imágenes del sistema de imágenes - ancho ajustado
        col_widths = [4*inch]
    elif tipo_tabla == 'dosimetria':
        col_widths = [5.5*inch]
    elif tipo_tabla == 'tamanos_campo_dosis':
        col_widths = [2*inch, 1.5*inch, 1.5*inch]

    else:
        # Tabla genérica
        col_width = 6*inch / num_cols
        col_widths = [col_width] * num_cols
    
    # Crear la tabla
    tabla = Table(data, colWidths=col_widths)
    
    # Estilo base de la tabla
    style = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#01b0ca")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]
    
    # Estilos específicos por tipo de tabla
    if tipo_tabla in ('equipos', 'indicadores_angulares_gantry', 'indicadores_angulares_colimador',
            'indicadores_laser', 'velocidad_multilaminas',
            'precision_posicion_multilaminas', 'dosimetria', 'linealidad_unidades_monitor',
            'parametros_espesor', 'parametros_tamano_pixel', 'parametros_resolucion_contraste',
            'parametros_resolucion_espacial', 'parametros_valores_ct', 'parametros_linealidad_ct',
            'parametros_uniformidad', 'espesor', 'tamano_pixel', 'resolucion_espacial',
            'valores_ct', 'linealidad_ct', 'uniformidad'):
        # Resaltar la primera fila de encabezados
        style.extend([
                        ('SPAN', (0, 0), (-1, 0)),
                        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#bfeff6")),
                        ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
                    ])
    elif tipo_tabla in ['imagen_espesor', 'imagen_tamano_pixel', 'imagen_resolucion_contraste',
                       'imagen_resolucion_espacial', 'imagen_valores_ct', 'imagen_linealidad_ct',
                       'imagen_uniformidad', 'resolucion_contraste']:
        # Tablas de imágenes o de resolución de contraste - solo encabezado principal
        style.extend([
                        ('SPAN', (0, 0), (-1, 0)),
                    ])
    elif tipo_tabla == 'tamanos_campo_dosis':
        # Resaltar la primera fila de encabezados
        style.extend([
                        ('SPAN', (0, 0), (-1, 0)),
                        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#bfeff6")),
                        ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
                        ('SPAN', (0, 1), (1, 1)),  # Campo nominal (columna_inicio, fila_inicio), (columna_fin, fila_fin)
                        ('SPAN', (2, 1), (3, 1)),  # Dosis medida
                    ])
        
    elif tipo_tabla == 'indicadores_camilla':
        # Resaltar la primera fila de encabezados
        style.extend([
                        ('SPAN', (0, 0), (-1, 0)),
                        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#bfeff6")),
                        ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
                        ('SPAN', (0, 2), (0, 4)),  # Campo nominal (columna_inicio, fila_inicio), (columna_fin, fila_fin)
                        ('SPAN', (0, 5), (0, 7)),  # Dosis medida
                        ('SPAN', (0, 8), (0, 10)),
                    ])
    
    elif tipo_tabla in ['factores_campo', 'factores_transmision', 'factores_sobre_eje']:
        # Estilo estándar para tablas de factores
        pass
    
    elif tipo_tabla == 'control_camaras':
        # Alternar colores de fondo para mejor lectura
        for row_idx in range(1, len(data)):
            if row_idx % 2 == 0:
                style.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor("#f0f0f0")))
    
    tabla.setStyle(TableStyle(style))
    return tabla


#### REPORTE MLCS

# ─────────────────────────────────────────────────────────────────
#  REPORTE PDF — PICKET FENCE MLC
#  Lee desde la DB y genera un PDF con estilo institucional
# ─────────────────────────────────────────────────────────────────
import io
from data.ManejoDatos.load import *
import numpy as np
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                 Paragraph, Spacer, KeepTogether, Image)
from reportlab.pdfgen import canvas as rl_canvas
from PyQt5.QtCore import QByteArray
from PyQt5.QtWidgets import QPushButton


# ── Colores institucionales ───────────────────────────────────────
_CYAN      = colors.HexColor("#01b0ca")
_CYAN_LITE = colors.HexColor("#bfeff6")
_PASS      = colors.HexColor("#4CAF82")
_WARN      = colors.HexColor("#E8A838")
_FAIL      = colors.HexColor("#E05252")
_GRAY_HDR  = colors.HexColor("#f0f0f0")
_WHITE     = colors.white
_BLACK     = colors.black


# ── Helpers de celda a nivel de módulo ────────────────────────────
# La sección "Interpretación de métricas" de generar_reporte_pdf_multitabla_mensual
# usa P()/Pl(), que solo existían como funciones anidadas dentro de
# generar_reporte_mlc_pdf y generar_reporte_starshot_pdf (fuera de alcance allí:
# NameError determinista al generar ese reporte). Las copias anidadas se conservan
# intactas: dentro de sus funciones tienen prioridad de alcance, así que el
# renderizado de los reportes MLC y Starshot no cambia.
def P(text, bold=False, size=8):
    s = getSampleStyleSheet()["Normal"].clone("tmp_c")
    s.alignment = TA_CENTER
    s.fontSize  = size
    if bold:
        return Paragraph(f"<b>{text}</b>", s)
    return Paragraph(str(text), s)


def Pl(text, bold=False, size=8):
    s = getSampleStyleSheet()["Normal"].clone("tmp_l")
    s.alignment = TA_LEFT
    s.fontSize  = size
    if bold:
        return Paragraph(f"<b>{text}</b>", s)
    return Paragraph(str(text), s)


def _pass_color(value, tol, action):
    """Color semáforo para una celda de error."""
    if value > tol:
        return _FAIL
    if value > action:
        return _WARN
    return _PASS


def _leer_datos_mlc_db(ref):
    """
    Lee todas las tablas MLC desde la DB para un ref dado.
    Devuelve un dict con DataFrames y metadatos.
    """
    from data.ManejoDatos.conection import Conexion
    conn = Conexion().conectar()
    cursor = conn.cursor()

    # ── configuracion_picketfence ─────────────────────────────────
    cursor.execute("""
        SELECT fecha, equipo, fisico_1, fisico_2,
               tolerancia, action_tolerance, imagen_mlc
        FROM configuracion_picketfence
        WHERE ref = ?
        ORDER BY id DESC LIMIT 1
    """, (ref,))
    row = cursor.fetchone()
    if not row:
        raise ValueError(f"No hay datos MLC para ref={ref}")

    fecha, equipo, fisico_1, fisico_2, tol, action, imagen_blob = row
    cfg_ref_id = cursor.lastrowid  # id de configuracion para FK

    
    

    imagen_blob = dicom_to_png_blob(imagen_blob)
    # Obtener el id real de configuracion_picketfence
    cursor.execute("""
        SELECT id FROM configuracion_picketfence
        WHERE ref = ? ORDER BY id DESC LIMIT 1
    """, (ref,))
    cfg_id = cursor.fetchone()[0]

    # ── error_picket ──────────────────────────────────────────────
    cursor.execute("""
        SELECT picket, picket_mean_error, picket_max_error
        FROM error_picket
        WHERE ref = ?
        ORDER BY picket
    """, (ref,))
    picket_rows = cursor.fetchall()

    # ── leaf_error ────────────────────────────────────────────────
    cursor.execute("""
        SELECT leaf, error
        FROM leaf_error
        WHERE ref = ?
        ORDER BY leaf
    """, (ref,))
    leaf_rows = cursor.fetchall()

    # ── highest_leaf_errors ───────────────────────────────────────
    cursor.execute("""
        SELECT leaf_out, picket_asociado, desviacion
        FROM highest_leaf_errors
        WHERE ref = ?
        ORDER BY desviacion DESC
    """, (ref,))
    worst_rows = cursor.fetchall()

    return {
        "fecha":       fecha,
        "equipo":      equipo,
        "fisico_1":    fisico_1,
        "fisico_2":    fisico_2,
        "tol":         tol,
        "action":      action,
        "imagen_blob": imagen_blob,
        "picket_rows": picket_rows,   # [(picket, mean, max), ...]
        "leaf_rows":   leaf_rows,     # [(leaf, std), ...]
        "worst_rows":  worst_rows,    # [(leaf, picket, desv), ...]
    }


def _header_footer_mlc(c, doc, datos, logo_path):
    """Encabezado y pie de página institucional."""
    width, height = letter

    if logo_path:
        try:
            c.drawImage(logo_path, 40, height - 80,
                        width=120, height=50, mask='auto')
        except Exception:
            pass

    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(width - 40, height - 50,
                      "Instituto de Cancerología Las Américas")
    c.setFont("Helvetica", 10)
    c.drawRightString(width - 40, height - 65,
                      f"QA Colimador Multilámiinas — {datos['equipo']}")

    # Rectángulo título
    c.setStrokeColor(_BLACK)
    c.setFillColor(colors.lightgrey)
    c.rect(40, height - 150, width - 80, 60, fill=1)

    c.setFillColor(_BLACK)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width / 2, height - 110,
                        "Control de Calidad — Colimador Multiláminas (MLC)")
    c.setFont("Helvetica", 12)
    c.drawCentredString(width / 2, height - 125, "Clínica Las Américas AUNA")
    c.setFont("Helvetica-Oblique", 10)
    c.drawCentredString(width / 2, height - 140,
                        "Instituto de Cancerología Las Américas")

    # Info general
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, height - 170, "Información general")
    c.setFont("Helvetica", 10)
    c.drawString(40, height - 185, f"Máquina: {datos['equipo']}")
    c.drawString(40, height - 200, f"Fecha: {datos['fecha']}")
    c.drawString(40, height - 215, f"Físico Médico: {datos['fisico_1']}")
    if datos.get("fisico_2"):
        c.drawString(40, height - 230,
                     f"Físico Médico 2: {datos['fisico_2']}")

    # Pie
    c.setStrokeColor(_BLACK)
    c.setLineWidth(1)
    c.line(80, 50, 280, 50)
    c.setFont("Helvetica", 10)
    c.drawString(80, 38, datos["fisico_1"] or "")


def generar_reporte_mlc_pdf(ref, logo_path="logo.png",
                             nombre_pdf="reporte_mlc.pdf",
                             temp=False):
    """
    Genera el PDF de QA de MLC leyendo desde la DB.

    Args:
        ref:        id del control (self.ref)
        logo_path:  ruta al logo institucional
        nombre_pdf: nombre del archivo si temp=False
        temp:       si True devuelve QByteArray para previsualización

    Returns:
        QByteArray si temp=True, None si temp=False
    """
    datos = _leer_datos_mlc_db(ref)
    styles = getSampleStyleSheet()

    tol    = datos["tol"]
    action = datos["action"]

    # Estilo de celda centrada
    cell_style = styles["Normal"]
    cell_style.alignment = TA_CENTER
    cell_style.fontSize  = 8

    def P(text, bold=False, color=_BLACK, size=8):
        tag = f'<font color="#{color.hexval()[2:] if hasattr(color,"hexval") else "000000"}">'
        s = styles["Normal"].clone("tmp")
        s.alignment = TA_CENTER
        s.fontSize  = size
        if bold:
            return Paragraph(f"<b>{text}</b>", s)
        return Paragraph(str(text), s)

    def Pl(text, bold=False, size=8):
        s = styles["Normal"].clone("tmpl")
        s.alignment = TA_LEFT
        s.fontSize  = size
        if bold:
            return Paragraph(f"<b>{text}</b>", s)
        return Paragraph(str(text), s)

    elements = []
    elements.append(Spacer(1, 0.3 * inch))

    # ════════════════════════════════════════════════════════════════
    #  SECCIÓN 1 — Parámetros del estudio
    # ════════════════════════════════════════════════════════════════
    param_data = [
        [P("Parámetros del estudio", bold=True, size=10), "", "", ""],
        [Pl("Parámetro", bold=True), Pl("Valor", bold=True),
         Pl("Parámetro", bold=True), Pl("Valor", bold=True)],
        [Pl("Equipo"),          P(datos["equipo"]),
         Pl("Tolerancia"),      P(f"{tol} mm")],
        [Pl("Fecha"),           P(datos["fecha"]),
         Pl("Action tolerance"), P(f"{action} mm")],
        [Pl("Físico 1"),        P(datos["fisico_1"] or "—"),
         Pl("N° pickets"),      P(str(len(datos["picket_rows"])))],
        [Pl("Físico 2"),        P(datos["fisico_2"] or "—"),
         Pl("N° láminas"),      P(str(len(datos["leaf_rows"])))],
    ]
    param_table = Table(param_data,
                        colWidths=[1.8*inch, 1.7*inch, 1.8*inch, 1.7*inch])
    param_table.setStyle(TableStyle([
        ("SPAN",       (0, 0), (3, 0)),
        ("BACKGROUND", (0, 0), (3, 0), _CYAN),
        ("TEXTCOLOR",  (0, 0), (3, 0), _WHITE),
        ("BACKGROUND", (0, 1), (3, 1), _CYAN_LITE),
        ("FONTNAME",   (0, 1), (3, 1), "Helvetica-Bold"),
        ("BACKGROUND", (0, 2), (1, -1), _GRAY_HDR),
        ("BACKGROUND", (2, 2), (3, -1), _GRAY_HDR),
        ("GRID",       (0, 0), (-1, -1), 0.5, _BLACK),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 2), (-1, -1),
         [_WHITE, colors.HexColor("#f9f9f9")]),
    ]))
    elements.append(KeepTogether(param_table))
    elements.append(Spacer(1, 0.3 * inch))

    # ════════════════════════════════════════════════════════════════
    #  SECCIÓN 2 — Error por picket (mean + max)
    # ════════════════════════════════════════════════════════════════
    picket_header = [
        [P("Error por Picket", bold=True, size=10), "", "", ""],
        [P("Picket", bold=True), P("Error medio (mm)", bold=True),
         P("Error máx (mm)", bold=True), P("Estado", bold=True)],
    ]
    picket_rows_pdf = []
    for picket, mean_e, max_e in datos["picket_rows"]:
        if max_e > tol:
            estado = P("FUERA TOL")
            bg_estado = _FAIL
        elif max_e > action:
            estado = P("ACCIÓN")
            bg_estado = _WARN
        else:
            estado = P("OK")
            bg_estado = _PASS
        picket_rows_pdf.append([
            P(f"P{picket}"),
            P(f"{mean_e:.4f}"),
            P(f"{max_e:.4f}"),
            estado,
        ])

    picket_data  = picket_header + picket_rows_pdf
    picket_table = Table(picket_data,
                         colWidths=[1.1*inch, 1.8*inch, 1.8*inch, 1.3*inch])

    picket_style = [
        ("SPAN",       (0, 0), (3, 0)),
        ("BACKGROUND", (0, 0), (3, 0), _CYAN),
        ("TEXTCOLOR",  (0, 0), (3, 0), _WHITE),
        ("BACKGROUND", (0, 1), (3, 1), _CYAN_LITE),
        ("FONTNAME",   (0, 1), (3, 1), "Helvetica-Bold"),
        ("GRID",       (0, 0), (-1, -1), 0.5, _BLACK),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 2), (-1, -1),
         [_WHITE, colors.HexColor("#f9f9f9")]),
    ]
    # Colorear columna Estado por fila
    for i, (_, _, max_e) in enumerate(datos["picket_rows"]):
        row_idx = i + 2
        if max_e > tol:
            picket_style.append(("BACKGROUND", (3, row_idx), (3, row_idx), _FAIL))
            picket_style.append(("TEXTCOLOR",  (3, row_idx), (3, row_idx), _WHITE))
        elif max_e > action:
            picket_style.append(("BACKGROUND", (3, row_idx), (3, row_idx), _WARN))
        else:
            picket_style.append(("BACKGROUND", (3, row_idx), (3, row_idx), _PASS))
            picket_style.append(("TEXTCOLOR",  (3, row_idx), (3, row_idx), _WHITE))

    picket_table.setStyle(TableStyle(picket_style))
    elements.append(KeepTogether(picket_table))
    elements.append(Spacer(1, 0.3 * inch))

    # ════════════════════════════════════════════════════════════════
    #  SECCIÓN 3 — Desviación estándar por lámina (heatmap textual)
    # ════════════════════════════════════════════════════════════════
    std_threshold = tol * 0.3
    leaf_data_all = datos["leaf_rows"]   # [(leaf, std), ...]

    # Dividir en dos columnas para compactar
    half = (len(leaf_data_all) + 1) // 2
    left_half  = leaf_data_all[:half]
    right_half = leaf_data_all[half:]

    leaf_header = [
        [P("Desviación estándar inter-picket por lámina", bold=True, size=10),
         "", "", ""],
        [P("Lámina", bold=True), P("Std (mm)", bold=True),
         P("Lámina", bold=True), P("Std (mm)", bold=True)],
    ]
    leaf_rows_pdf = []
    for i in range(half):
        l_leaf, l_std = left_half[i]
        r_leaf, r_std = right_half[i] if i < len(right_half) else ("", "")
        leaf_rows_pdf.append([
            P(str(l_leaf)), P(f"{l_std:.4f}" if l_std != "" else ""),
            P(str(r_leaf)), P(f"{r_std:.4f}" if r_std != "" else ""),
        ])

    leaf_table_data = leaf_header + leaf_rows_pdf
    leaf_table = Table(leaf_table_data,
                       colWidths=[1.1*inch, 1.4*inch, 1.1*inch, 1.4*inch])

    leaf_style = [
        ("SPAN",       (0, 0), (3, 0)),
        ("BACKGROUND", (0, 0), (3, 0), _CYAN),
        ("TEXTCOLOR",  (0, 0), (3, 0), _WHITE),
        ("BACKGROUND", (0, 1), (3, 1), _CYAN_LITE),
        ("FONTNAME",   (0, 1), (3, 1), "Helvetica-Bold"),
        ("GRID",       (0, 0), (-1, -1), 0.5, _BLACK),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 2), (-1, -1),
         [_WHITE, colors.HexColor("#f9f9f9")]),
    ]
    # Colorear celdas de std según umbral
    for i, (_, std) in enumerate(left_half):
        row_idx = i + 2
        if std > std_threshold:
            leaf_style.append(("BACKGROUND", (1, row_idx), (1, row_idx), _FAIL))
            leaf_style.append(("TEXTCOLOR",  (1, row_idx), (1, row_idx), _WHITE))
        elif std > std_threshold * 0.7:
            leaf_style.append(("BACKGROUND", (1, row_idx), (1, row_idx), _WARN))
    for i, (_, std) in enumerate(right_half):
        row_idx = i + 2
        if std > std_threshold:
            leaf_style.append(("BACKGROUND", (3, row_idx), (3, row_idx), _FAIL))
            leaf_style.append(("TEXTCOLOR",  (3, row_idx), (3, row_idx), _WHITE))
        elif std > std_threshold * 0.7:
            leaf_style.append(("BACKGROUND", (3, row_idx), (3, row_idx), _WARN))

    leaf_table.setStyle(TableStyle(leaf_style))
    elements.append(KeepTogether(leaf_table))
    elements.append(Spacer(1, 0.3 * inch))

    # ════════════════════════════════════════════════════════════════
    #  SECCIÓN 4 — Peores láminas (highest_leaf_errors)
    # ════════════════════════════════════════════════════════════════
    worst_header = [
        [P("Láminas con mayor error (highest_leaf_errors)",
           bold=True, size=10), "", "", "", ""],
        [P("#", bold=True), P("Lámina", bold=True),
         P("Picket asociado", bold=True),
         P("Desviación (mm)", bold=True), P("Estado", bold=True)],
    ]
    worst_rows_pdf = []
    for rank, (leaf, picket, desv) in enumerate(datos["worst_rows"], 1):
        if desv > tol:
            estado_txt, bg = "FUERA TOL", _FAIL
            tc = _WHITE
        elif desv > action:
            estado_txt, bg = "ACCIÓN", _WARN
            tc = _BLACK
        else:
            estado_txt, bg = "OK", _PASS
            tc = _WHITE
        worst_rows_pdf.append([
            P(str(rank)), P(str(leaf)), P(str(picket)),
            P(f"{desv:.4f}"), P(estado_txt),
        ])

    worst_data  = worst_header + worst_rows_pdf
    worst_table = Table(worst_data,
                        colWidths=[0.5*inch, 1.0*inch, 1.5*inch,
                                   1.5*inch, 1.5*inch])
    worst_style = [
        ("SPAN",       (0, 0), (4, 0)),
        ("BACKGROUND", (0, 0), (4, 0), _CYAN),
        ("TEXTCOLOR",  (0, 0), (4, 0), _WHITE),
        ("BACKGROUND", (0, 1), (4, 1), _CYAN_LITE),
        ("FONTNAME",   (0, 1), (4, 1), "Helvetica-Bold"),
        ("GRID",       (0, 0), (-1, -1), 0.5, _BLACK),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 2), (-1, -1),
         [_WHITE, colors.HexColor("#f9f9f9")]),
    ]
    for i, (_, _, desv) in enumerate(datos["worst_rows"]):
        row_idx = i + 2
        if desv > tol:
            worst_style.append(("BACKGROUND", (4, row_idx), (4, row_idx), _FAIL))
            worst_style.append(("TEXTCOLOR",  (4, row_idx), (4, row_idx), _WHITE))
        elif desv > action:
            worst_style.append(("BACKGROUND", (4, row_idx), (4, row_idx), _WARN))
        else:
            worst_style.append(("BACKGROUND", (4, row_idx), (4, row_idx), _PASS))
            worst_style.append(("TEXTCOLOR",  (4, row_idx), (4, row_idx), _WHITE))

    worst_table.setStyle(TableStyle(worst_style))
    elements.append(KeepTogether(worst_table))
    elements.append(Spacer(1, 0.3 * inch))

    # ════════════════════════════════════════════════════════════════
    #  SECCIÓN 5 — Imagen del peine (BLOB → Image)
    # ════════════════════════════════════════════════════════════════
    if datos["imagen_blob"]:
        img_buffer = io.BytesIO(bytes(datos["imagen_blob"]))
        img_rl     = Image(img_buffer, width=6.5*inch, height=4.5*inch)

        img_header = Table(
            [[P("Visualización Picket Fence — Vista de Peine",
                bold=True, size=10)]],
            colWidths=[6.5*inch]
        )
        img_header.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), _CYAN),
            ("TEXTCOLOR",  (0, 0), (0, 0), _WHITE),
            ("GRID",       (0, 0), (-1, -1), 0.5, _BLACK),
            ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ]))

        img_wrapper = Table([[img_rl]], colWidths=[6.5*inch])
        img_wrapper.setStyle(TableStyle([
            ("GRID",   (0, 0), (-1, -1), 0.5, _BLACK),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN",  (0, 0), (-1, -1), "CENTER"),
        ]))

        elements.append(KeepTogether([img_header,
                                       Spacer(1, 0.05*inch),
                                       img_wrapper]))
        elements.append(Spacer(1, 0.3 * inch))

    # ════════════════════════════════════════════════════════════════
    #  SECCIÓN 6 — Leyenda de criterios
    # ════════════════════════════════════════════════════════════════
    leyenda_data = [
        [P("Criterios de evaluación", bold=True, size=10), "", ""],
        [P("Color", bold=True), P("Criterio", bold=True),
         P("Umbral", bold=True)],
        [P("APROBADO"), P("Error ≤ action tolerance"), P(f"≤ {action} mm")],
        [P("ACCIÓN"),   P("Action tol < error ≤ tolerancia"),
         P(f"{action} – {tol} mm")],
        [P("FUERA"),    P("Error > tolerancia"), P(f"> {tol} mm")],
    ]
    leyenda_table = Table(leyenda_data,
                          colWidths=[1.5*inch, 3.5*inch, 2.0*inch])
    leyenda_style = [
        ("SPAN",       (0, 0), (2, 0)),
        ("BACKGROUND", (0, 0), (2, 0), _CYAN),
        ("TEXTCOLOR",  (0, 0), (2, 0), _WHITE),
        ("BACKGROUND", (0, 1), (2, 1), _CYAN_LITE),
        ("FONTNAME",   (0, 1), (2, 1), "Helvetica-Bold"),
        ("BACKGROUND", (0, 2), (2, 2), _PASS),
        ("TEXTCOLOR",  (0, 2), (2, 2), _WHITE),
        ("BACKGROUND", (0, 3), (2, 3), _WARN),
        ("BACKGROUND", (0, 4), (2, 4), _FAIL),
        ("TEXTCOLOR",  (0, 4), (2, 4), _WHITE),
        ("GRID",       (0, 0), (-1, -1), 0.5, _BLACK),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
    ]
    leyenda_table.setStyle(TableStyle(leyenda_style))
    elements.append(KeepTogether(leyenda_table))

    # ════════════════════════════════════════════════════════════════
    #  BUILD
    # ════════════════════════════════════════════════════════════════
    if temp:
        pdf_bytes = io.BytesIO()
        doc = SimpleDocTemplate(pdf_bytes, pagesize=letter,
                                rightMargin=40, leftMargin=40,
                                topMargin=250, bottomMargin=80)
    else:
        doc = SimpleDocTemplate(nombre_pdf, pagesize=letter,
                                rightMargin=40, leftMargin=40,
                                topMargin=250, bottomMargin=80)

    doc.build(
        elements,
        onFirstPage=lambda c, d: _header_footer_mlc(c, d, datos, logo_path),
        onLaterPages=lambda c, d: _header_footer_mlc(c, d, datos, logo_path),
    )

    if temp:
        pdf_bytes.seek(0)
        return QByteArray(pdf_bytes.read())
    
    

# REPORTE STARSHOT 

 
# ── Colores institucionales (idénticos al reporte MLC) ───────────
_CYAN      = colors.HexColor("#01b0ca")
_CYAN_LITE = colors.HexColor("#bfeff6")
_PASS      = colors.HexColor("#4CAF82")
_WARN      = colors.HexColor("#E8A838")
_FAIL      = colors.HexColor("#E05252")
_GRAY_HDR  = colors.HexColor("#f0f0f0")
_WHITE     = colors.white
_BLACK     = colors.black
 
 
# ════════════════════════════════════════════════════════════════
#  HELPERS
# ════════════════════════════════════════════════════════════════
 
def _pass_color_starshot(value, tolerance):
    """Semáforo binario PASS/FAIL para radio de convergencia."""
    return _PASS if value <= tolerance else _FAIL
 
 
def _leer_datos_starshot_db(ref):
    """
    Lee todas las tablas Starshot desde la DB para un ref dado.
    Devuelve un dict con los datos necesarios para el PDF.
 
    Tablas leídas:
        configuracion_starshot
        estadisticas_starshot
        angulo_starshot
        uniformidad_angular_starshot
    """
    from data.ManejoDatos.conection import Conexion
 
    conn   = Conexion().conectar()
    cursor = conn.cursor()
 
    # ── configuracion_starshot ────────────────────────────────────
    cursor.execute("""
        SELECT fecha, equipo, fisico_1, fisico_2,
               tolerancia, sid, imagen_mlc_spoke
        FROM configuracion_starshot
        WHERE ref = ?
        ORDER BY id DESC LIMIT 1
    """, (ref,))
    row = cursor.fetchone()
    if not row:
        raise ValueError(f"No hay datos Starshot para ref={ref}")
 
    fecha, equipo, fisico_1, fisico_2, tolerancia, sid, imagen_blob = row
 
    # Convertir blob DICOM a PNG si viene como bytes raw
    try:
        from data.ManejoDatos.load import dicom_to_png_blob
        imagen_blob = dicom_to_png_blob(imagen_blob)
    except Exception:
        pass  # Si falla la conversión, simplemente no se incluye la imagen
 
    # ── estadisticas_starshot ─────────────────────────────────────
    cursor.execute("""
        SELECT std_mm, rms_mm, pm_95
        FROM estadisticas_starshot
        WHERE ref = ?
        ORDER BY id DESC LIMIT 1
    """, (ref,))
    stats_row = cursor.fetchone()
    if stats_row:
        std_mm, rms_mm, p95_mm = stats_row
    else:
        std_mm = rms_mm = p95_mm = None
 
    # ── angulo_starshot ───────────────────────────────────────────
    cursor.execute("""
        SELECT spoke_index, angulo_nominal_deg,
               angulo_real_deg, desviacion_deg
        FROM angulo_starshot
        WHERE ref = ?
        ORDER BY spoke_index
    """, (ref,))
    spoke_rows = cursor.fetchall()   # [(idx, nominal, real, desv), ...]
 
    # ── uniformidad_angular_starshot ──────────────────────────────
    cursor.execute("""
        SELECT gap_index, spoke_inicial, spoke_final,
               separacion_deg, separacion_ideal_deg, error_deg
        FROM uniformidad_angular_starshot
        WHERE ref = ?
        ORDER BY gap_index
    """, (ref,))
    uniformidad_rows = cursor.fetchall()   # [(gap_idx, ini, fin, sep, ideal, err), ...]
 
    conn.close()
 
    return {
        "fecha":            fecha,
        "equipo":           equipo,
        "fisico_1":         fisico_1,
        "fisico_2":         fisico_2,
        "tolerancia":       tolerancia,
        "sid":              sid,
        "imagen_blob":      imagen_blob,
        "std_mm":           std_mm,
        "rms_mm":           rms_mm,
        "p95_mm":           p95_mm,
        "spoke_rows":       spoke_rows,
        "uniformidad_rows": uniformidad_rows,
    }
 
 
# ════════════════════════════════════════════════════════════════
#  ENCABEZADO / PIE DE PÁGINA
# ════════════════════════════════════════════════════════════════
 
def _header_footer_starshot(c, doc, datos, logo_path):
    """Encabezado y pie de página institucional para Starshot."""
    width, height = letter
 
    if logo_path:
        try:
            c.drawImage(logo_path, 40, height - 80,
                        width=120, height=50, mask='auto')
        except Exception:
            pass
 
    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(width - 40, height - 50,
                      "Instituto de Cancerología Las Américas")
    c.setFont("Helvetica", 10)
    c.drawRightString(width - 40, height - 65,
                      f"QA Starshot — {datos['equipo']}")
 
    # Rectángulo título
    c.setStrokeColor(_BLACK)
    c.setFillColor(colors.lightgrey)
    c.rect(40, height - 150, width - 80, 60, fill=1)
 
    c.setFillColor(_BLACK)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(width / 2, height - 110,
                        "Control de Calidad — Starshot (Spoke Shot)")
    c.setFont("Helvetica", 12)
    c.drawCentredString(width / 2, height - 125, "Clínica Las Américas AUNA")
    c.setFont("Helvetica-Oblique", 10)
    c.drawCentredString(width / 2, height - 140,
                        "Instituto de Cancerología Las Américas")
 
    # Info general
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, height - 170, "Información general")
    c.setFont("Helvetica", 10)
    c.drawString(40, height - 185, f"Máquina: {datos['equipo']}")
    c.drawString(40, height - 200, f"Fecha: {datos['fecha']}")
    c.drawString(40, height - 215, f"Físico Médico: {datos['fisico_1']}")
    if datos.get("fisico_2"):
        c.drawString(40, height - 230,
                     f"Físico Médico 2: {datos['fisico_2']}")
 
    # Pie de página — firma
    c.setStrokeColor(_BLACK)
    c.setLineWidth(1)
    c.line(80, 50, 280, 50)
    c.setFont("Helvetica", 10)
    c.drawString(80, 38, datos["fisico_1"] or "")
 
 
# ════════════════════════════════════════════════════════════════
#  FUNCIÓN PRINCIPAL
# ════════════════════════════════════════════════════════════════
 
def generar_reporte_starshot_pdf(ref,
                                  radius_mm: float,
                                  max_residuo_mm: float,
                                  n_intersecciones: int,
                                  center_x_mm: float,
                                  center_y_mm: float,
                                  n_spokes: int,
                                  logo_path: str = "logo.png",
                                  nombre_pdf: str = "reporte_starshot.pdf",
                                  temp: bool = False):
    """
    Genera el PDF de QA de Starshot leyendo la mayor parte de los datos
    desde la DB, y recibiendo las métricas de convergencia directamente
    (porque no se almacenan en DB pero sí se calculan en memoria).
 
    Args:
        ref               – id del control (self.ref)
        radius_mm         – radio de convergencia calculado por pylinac
        max_residuo_mm    – máximo residuo de intersecciones
        n_intersecciones  – cantidad de intersecciones usadas
        center_x_mm       – coordenada X del centro (mm)
        center_y_mm       – coordenada Y del centro (mm)
        n_spokes          – número de rayos detectados
        logo_path         – ruta al logo institucional
        nombre_pdf        – nombre del archivo si temp=False
        temp              – si True devuelve QByteArray para previsualización
 
    Returns:
        QByteArray si temp=True, None si temp=False
    """
    datos = _leer_datos_starshot_db(ref)
    tol   = datos["tolerancia"]
 
    styles = getSampleStyleSheet()
 
    # ── Helpers de celda ─────────────────────────────────────────
    def P(text, bold=False, size=8):
        s = styles["Normal"].clone("tmp_c")
        s.alignment = TA_CENTER
        s.fontSize  = size
        if bold:
            return Paragraph(f"<b>{text}</b>", s)
        return Paragraph(str(text), s)
 
    def Pl(text, bold=False, size=8):
        s = styles["Normal"].clone("tmp_l")
        s.alignment = TA_LEFT
        s.fontSize  = size
        if bold:
            return Paragraph(f"<b>{text}</b>", s)
        return Paragraph(str(text), s)
 
    elements = []
    elements.append(Spacer(1, 0.3 * inch))
 
    # ════════════════════════════════════════════════════════════════
    #  SECCIÓN 1 — Parámetros del estudio
    # ════════════════════════════════════════════════════════════════
    sid_str = f"{datos['sid']} mm" if datos['sid'] else "—"
    param_data = [
        [P("Parámetros del estudio", bold=True, size=10), "", "", ""],
        [Pl("Parámetro", bold=True), Pl("Valor", bold=True),
         Pl("Parámetro", bold=True), Pl("Valor", bold=True)],
        [Pl("Equipo"),     P(datos["equipo"]),
         Pl("Tolerancia"), P(f"{tol} mm")],
        [Pl("Fecha"),      P(datos["fecha"]),
         Pl("SID"),        P(sid_str)],
        [Pl("Físico 1"),   P(datos["fisico_1"] or "—"),
         Pl("N° rayos"),   P(str(n_spokes))],
        [Pl("Físico 2"),   P(datos["fisico_2"] or "—"),
         Pl("Intersecciones"), P(str(n_intersecciones))],
    ]
    param_table = Table(param_data,
                        colWidths=[1.8*inch, 1.7*inch, 1.8*inch, 1.7*inch])
    param_table.setStyle(TableStyle([
        ("SPAN",       (0, 0), (3, 0)),
        ("BACKGROUND", (0, 0), (3, 0), _CYAN),
        ("TEXTCOLOR",  (0, 0), (3, 0), _WHITE),
        ("BACKGROUND", (0, 1), (3, 1), _CYAN_LITE),
        ("FONTNAME",   (0, 1), (3, 1), "Helvetica-Bold"),
        ("BACKGROUND", (0, 2), (1, -1), _GRAY_HDR),
        ("BACKGROUND", (2, 2), (3, -1), _GRAY_HDR),
        ("GRID",       (0, 0), (-1, -1), 0.5, _BLACK),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 2), (-1, -1),
         [_WHITE, colors.HexColor("#f9f9f9")]),
    ]))
    elements.append(KeepTogether(param_table))
    elements.append(Spacer(1, 0.3 * inch))
 
    # ════════════════════════════════════════════════════════════════
    #  SECCIÓN 2 — Métricas de convergencia (las que realmente importan)
    #
    #  Jerarquía clínica:
    #    1. Radio de convergencia  → criterio TG-142 PASS/FAIL
    #    2. RMS residuos           → compacidad de la nube
    #    3. Máximo residuo         → peor caso
    #    4. STD                    → dispersión (apartado avanzado)
    #    5. P95                    → solo para trending; NO se destaca
    # ════════════════════════════════════════════════════════════════
    passed      = radius_mm <= tol
    pass_color  = _PASS if passed else _FAIL
    pass_text   = "APROBADO" if passed else "REPROBADO"
    pass_tc     = _WHITE
 
    conv_data = [
        [P("Métricas de convergencia", bold=True, size=10), "", "", ""],
        [Pl("Métrica", bold=True), Pl("Valor", bold=True),
         Pl("Tolerancia", bold=True), Pl("Estado", bold=True)],
        # Radio — métrica reina
        [Pl("Radio de convergencia (circle_radius)"),
         P(f"{radius_mm:.4f} mm"),
         P(f"{tol:.2f} mm"),
         P(pass_text, bold=True)],
        # RMS residuos
        [Pl("RMS residuos"),
         P(f"{datos['rms_mm']:.4f} mm" if datos['rms_mm'] is not None else "—"),
         P("—"), P("—")],
        # Máximo residuo
        [Pl("Máximo residuo"),
         P(f"{max_residuo_mm:.4f} mm"),
         P("—"), P("—")],
        # STD — apartado avanzado
        [Pl("Desviación estándar (STD)"),
         P(f"{datos['std_mm']:.4f} mm" if datos['std_mm'] is not None else "—"),
         P("—"), P("—")],
    ]
    conv_table = Table(conv_data,
                       colWidths=[2.5*inch, 1.5*inch, 1.3*inch, 1.2*inch])
    conv_style = [
        ("SPAN",       (0, 0), (3, 0)),
        ("BACKGROUND", (0, 0), (3, 0), _CYAN),
        ("TEXTCOLOR",  (0, 0), (3, 0), _WHITE),
        ("BACKGROUND", (0, 1), (3, 1), _CYAN_LITE),
        ("FONTNAME",   (0, 1), (3, 1), "Helvetica-Bold"),
        ("GRID",       (0, 0), (-1, -1), 0.5, _BLACK),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 2), (-1, -1),
         [_WHITE, colors.HexColor("#f9f9f9")]),
        # Colorear fila del radio según PASS/FAIL
        ("BACKGROUND", (3, 2), (3, 2), pass_color),
        ("TEXTCOLOR",  (3, 2), (3, 2), pass_tc),
        # Centro resaltado para radio
        ("FONTNAME",   (0, 2), (3, 2), "Helvetica-Bold"),
    ]
    conv_table.setStyle(TableStyle(conv_style))
    elements.append(KeepTogether(conv_table))
    elements.append(Spacer(1, 0.3 * inch))
 
    # ════════════════════════════════════════════════════════════════
    #  SECCIÓN 3 — Centro y geometría
    # ════════════════════════════════════════════════════════════════
    geo_data = [
        [P("Geometría del isocentro", bold=True, size=10), "", "", ""],
        [Pl("Parámetro", bold=True), Pl("Valor", bold=True),
         Pl("Parámetro", bold=True), Pl("Valor", bold=True)],
        [Pl("Centro X"),   P(f"{center_x_mm:+.4f} mm"),
         Pl("Centro Y"),   P(f"{center_y_mm:+.4f} mm")],
        [Pl("N° spokes"),  P(str(n_spokes)),
         Pl("Intersecciones"), P(str(n_intersecciones))],
    ]
    geo_table = Table(geo_data,
                      colWidths=[1.8*inch, 1.7*inch, 1.8*inch, 1.7*inch])
    geo_table.setStyle(TableStyle([
        ("SPAN",       (0, 0), (3, 0)),
        ("BACKGROUND", (0, 0), (3, 0), _CYAN),
        ("TEXTCOLOR",  (0, 0), (3, 0), _WHITE),
        ("BACKGROUND", (0, 1), (3, 1), _CYAN_LITE),
        ("FONTNAME",   (0, 1), (3, 1), "Helvetica-Bold"),
        ("BACKGROUND", (0, 2), (1, -1), _GRAY_HDR),
        ("BACKGROUND", (2, 2), (3, -1), _GRAY_HDR),
        ("GRID",       (0, 0), (-1, -1), 0.5, _BLACK),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 2), (-1, -1),
         [_WHITE, colors.HexColor("#f9f9f9")]),
    ]))
    elements.append(KeepTogether(geo_table))
    elements.append(Spacer(1, 0.3 * inch))
 
    # ════════════════════════════════════════════════════════════════
    #  SECCIÓN 4 — Tabla de spokes (ángulo nominal, real, desviación)
    # ════════════════════════════════════════════════════════════════
    if datos["spoke_rows"]:
        spoke_header = [
            [P("Rayos detectados — Error angular por spoke", bold=True, size=10),
             "", "", ""],
            [P("Índice", bold=True), P("Ángulo nominal (°)", bold=True),
             P("Ángulo real (°)", bold=True), P("Desviación (°)", bold=True)],
        ]
        spoke_pdf_rows = []
        for idx, nom, real, desv in datos["spoke_rows"]:
            spoke_pdf_rows.append([
                P(str(idx)),
                P(f"{nom:.2f}"),
                P(f"{real:.4f}"),
                P(f"{desv:+.4f}"),
            ])
 
        spoke_data  = spoke_header + spoke_pdf_rows
        spoke_table = Table(spoke_data,
                            colWidths=[1.0*inch, 2.0*inch, 2.0*inch, 2.0*inch])
        spoke_style = [
            ("SPAN",       (0, 0), (3, 0)),
            ("BACKGROUND", (0, 0), (3, 0), _CYAN),
            ("TEXTCOLOR",  (0, 0), (3, 0), _WHITE),
            ("BACKGROUND", (0, 1), (3, 1), _CYAN_LITE),
            ("FONTNAME",   (0, 1), (3, 1), "Helvetica-Bold"),
            ("GRID",       (0, 0), (-1, -1), 0.5, _BLACK),
            ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 2), (-1, -1),
             [_WHITE, colors.HexColor("#f9f9f9")]),
        ]
        # Resaltar desviaciones grandes (>1° advertencia visual)
        for i, (_, _, _, desv) in enumerate(datos["spoke_rows"]):
            row_idx = i + 2
            if abs(desv) > 2.0:
                spoke_style.append(("BACKGROUND", (3, row_idx), (3, row_idx), _FAIL))
                spoke_style.append(("TEXTCOLOR",  (3, row_idx), (3, row_idx), _WHITE))
            elif abs(desv) > 1.0:
                spoke_style.append(("BACKGROUND", (3, row_idx), (3, row_idx), _WARN))
 
        spoke_table.setStyle(TableStyle(spoke_style))
        elements.append(KeepTogether(spoke_table))
        elements.append(Spacer(1, 0.3 * inch))
 
    # ════════════════════════════════════════════════════════════════
    #  SECCIÓN 5 — Uniformidad angular (max_error_sep_deg es lo clave)
    # ════════════════════════════════════════════════════════════════
    if datos["uniformidad_rows"]:
        # Calcular max_error_sep para resaltarlo
        errores_sep = [abs(r[5]) for r in datos["uniformidad_rows"]]
        max_err_sep = max(errores_sep) if errores_sep else 0.0
        ideal_sep   = datos["uniformidad_rows"][0][4]  # separacion_ideal_deg
 
        uni_header = [
            [P("Uniformidad angular entre spokes", bold=True, size=10),
             "", "", "", "", ""],
            [P("Gap", bold=True), P("Spoke ini", bold=True),
             P("Spoke fin", bold=True), P("Sep. real (°)", bold=True),
             P("Sep. ideal (°)", bold=True), P("Error (°)", bold=True)],
        ]
        uni_pdf_rows = []
        for gap_idx, ini, fin, sep, ideal, err in datos["uniformidad_rows"]:
            uni_pdf_rows.append([
                P(str(gap_idx)),
                P(str(ini)),
                P(str(fin)),
                P(f"{sep:.3f}"),
                P(f"{ideal:.3f}"),
                P(f"{err:+.3f}"),
            ])
 
        uni_data  = uni_header + uni_pdf_rows
        uni_table = Table(uni_data,
                          colWidths=[0.7*inch, 0.9*inch, 0.9*inch,
                                     1.3*inch, 1.3*inch, 1.4*inch])
        uni_style = [
            ("SPAN",       (0, 0), (5, 0)),
            ("BACKGROUND", (0, 0), (5, 0), _CYAN),
            ("TEXTCOLOR",  (0, 0), (5, 0), _WHITE),
            ("BACKGROUND", (0, 1), (5, 1), _CYAN_LITE),
            ("FONTNAME",   (0, 1), (5, 1), "Helvetica-Bold"),
            ("GRID",       (0, 0), (-1, -1), 0.5, _BLACK),
            ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 2), (-1, -1),
             [_WHITE, colors.HexColor("#f9f9f9")]),
        ]
        # Resaltar errores de separación angular
        for i, (_, _, _, _, _, err) in enumerate(datos["uniformidad_rows"]):
            row_idx = i + 2
            if abs(err) > 2.0:
                uni_style.append(("BACKGROUND", (5, row_idx), (5, row_idx), _FAIL))
                uni_style.append(("TEXTCOLOR",  (5, row_idx), (5, row_idx), _WHITE))
            elif abs(err) > 1.0:
                uni_style.append(("BACKGROUND", (5, row_idx), (5, row_idx), _WARN))
 
        uni_table.setStyle(TableStyle(uni_style))
        elements.append(KeepTogether(uni_table))
 
        # Resumen de uniformidad angular (max_error_sep_deg — métrica clave)
        elements.append(Spacer(1, 0.15 * inch))
        max_err_color = _FAIL if max_err_sep > 2.0 else (_WARN if max_err_sep > 1.0 else _PASS)
        resumen_uni_data = [
            [P("Resumen uniformidad angular", bold=True, size=9), "", ""],
            [Pl("Separación ideal", bold=True),
             Pl("Max error separación (max_error_sep_deg)", bold=True),
             Pl("Evaluación", bold=True)],
            [P(f"{ideal_sep:.3f}°"),
             P(f"{max_err_sep:.4f}°"),
             P("OK" if max_err_sep <= 1.0 else "REVISAR", bold=True)],
        ]
        resumen_uni = Table(resumen_uni_data,
                            colWidths=[1.5*inch, 3.5*inch, 2.0*inch])
        resumen_uni_style = [
            ("SPAN",       (0, 0), (2, 0)),
            ("BACKGROUND", (0, 0), (2, 0), _CYAN),
            ("TEXTCOLOR",  (0, 0), (2, 0), _WHITE),
            ("BACKGROUND", (0, 1), (2, 1), _CYAN_LITE),
            ("FONTNAME",   (0, 1), (2, 1), "Helvetica-Bold"),
            ("BACKGROUND", (2, 2), (2, 2), max_err_color),
            ("TEXTCOLOR",  (2, 2), (2, 2), _WHITE),
            ("GRID",       (0, 0), (-1, -1), 0.5, _BLACK),
            ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ]
        resumen_uni = Table(resumen_uni_data,
                            colWidths=[1.5*inch, 3.5*inch, 2.0*inch])
        resumen_uni.setStyle(TableStyle(resumen_uni_style))
        elements.append(KeepTogether(resumen_uni))
        elements.append(Spacer(1, 0.3 * inch))
 
    # ════════════════════════════════════════════════════════════════
    #  SECCIÓN 6 — Imagen del starshot (blob PNG)
    # ════════════════════════════════════════════════════════════════
    if datos["imagen_blob"]:
        try:
            img_buffer = io.BytesIO(bytes(datos["imagen_blob"]))
            img_rl     = Image(img_buffer, width=5.5*inch, height=5.5*inch)
 
            img_header = Table(
                [[P("Visualización Starshot — Rueda de rayos",
                    bold=True, size=10)]],
                colWidths=[6.5*inch]
            )
            img_header.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (0, 0), _CYAN),
                ("TEXTCOLOR",  (0, 0), (0, 0), _WHITE),
                ("GRID",       (0, 0), (-1, -1), 0.5, _BLACK),
                ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
            ]))
 
            img_wrapper = Table([[img_rl]], colWidths=[6.5*inch])
            img_wrapper.setStyle(TableStyle([
                ("GRID",   (0, 0), (-1, -1), 0.5, _BLACK),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN",  (0, 0), (-1, -1), "CENTER"),
            ]))
 
            elements.append(KeepTogether([img_header,
                                           Spacer(1, 0.05*inch),
                                           img_wrapper]))
            elements.append(Spacer(1, 0.3 * inch))
        except Exception:
            pass  # Si la imagen falla, continúa sin ella
 
    # ════════════════════════════════════════════════════════════════
    #  SECCIÓN 7 — Leyenda de criterios
    # ════════════════════════════════════════════════════════════════
    leyenda_data = [
        [P("Criterios de evaluación", bold=True, size=10), "", ""],
        [P("Color", bold=True), P("Criterio", bold=True),
         P("Referencia", bold=True)],
        [P("APROBADO"),
         P("Radio de convergencia <= tolerancia TG-142"),
         P(f"<= {tol} mm")],
        [P("REPROBADO"),
         P("Radio de convergencia > tolerancia"),
         P(f"> {tol} mm")],
        [P("ADVERTENCIA"),
         P("Desviación angular > 1° (no criterio principal)"),
         P("> 1°")],
    ]
    leyenda_table = Table(leyenda_data,
                          colWidths=[1.5*inch, 3.5*inch, 2.0*inch])
    leyenda_style = [
        ("SPAN",       (0, 0), (2, 0)),
        ("BACKGROUND", (0, 0), (2, 0), _CYAN),
        ("TEXTCOLOR",  (0, 0), (2, 0), _WHITE),
        ("BACKGROUND", (0, 1), (2, 1), _CYAN_LITE),
        ("FONTNAME",   (0, 1), (2, 1), "Helvetica-Bold"),
        ("BACKGROUND", (0, 2), (2, 2), _PASS),
        ("TEXTCOLOR",  (0, 2), (2, 2), _WHITE),
        ("BACKGROUND", (0, 3), (2, 3), _FAIL),
        ("TEXTCOLOR",  (0, 3), (2, 3), _WHITE),
        ("BACKGROUND", (0, 4), (2, 4), _WARN),
        ("GRID",       (0, 0), (-1, -1), 0.5, _BLACK),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
    ]
    leyenda_table.setStyle(TableStyle(leyenda_style))
    elements.append(KeepTogether(leyenda_table))
 
    # ════════════════════════════════════════════════════════════════
    #  BUILD
    # ════════════════════════════════════════════════════════════════
    if temp:
        pdf_bytes = io.BytesIO()
        doc = SimpleDocTemplate(pdf_bytes, pagesize=letter,
                                rightMargin=40, leftMargin=40,
                                topMargin=250, bottomMargin=80)
    else:
        doc = SimpleDocTemplate(nombre_pdf, pagesize=letter,
                                rightMargin=40, leftMargin=40,
                                topMargin=250, bottomMargin=80)
 
    doc.build(
        elements,
        onFirstPage=lambda c, d: _header_footer_starshot(c, d, datos, logo_path),
        onLaterPages=lambda c, d: _header_footer_starshot(c, d, datos, logo_path),
    )
 
    if temp:
        pdf_bytes.seek(0)
        return QByteArray(pdf_bytes.read())