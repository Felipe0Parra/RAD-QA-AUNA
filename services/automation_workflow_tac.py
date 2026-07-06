"""
Módulo de Automatización de Workflow para Análisis DICOM CatPhan
Automatiza la selección de cortes y ejecución de análisis con auditoría del usuario.
"""
 
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                              QPushButton, QDialogButtonBox, QTextEdit, QProgressBar)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt5.QtGui import QFont, QColor
import traceback
 
 
class DialogoAprobacionCorte(Dialog):
    # muestra un pop up para que el user confirme si acepta ese corte
    def __init__(self, parent, categoria, indice_corte, total_cortes, imagen_preview = None):
        self.categoria = categoria
        self.indice_corte = indice_corte
        self.total_cortes = total_cortes
        self.corte_aprobado = None 
        
        self.setWindowTitle(f"Aprobar corte {categoria}")
        self.setModal(True)
        self.setMinimumWidth(400)
        self.setMaximumHeight(400)
        
        self._setup_ui()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        titulo = QLabel(f"Revision de corte automatico")
        titulo.setFont(QFont("Segoe UI", 14, QFont.Bold))
        titulo.setAlignment(Qt.AlignmentCenter)
        titulo.setStyleSheet("color: #2c3e50; padding: 10px;")
        layout.addWidget(titulo)
        
        info_categoria = QLabel(f"Categoria: {self.categoria}")
        info_categoria.setFont(QFont("Segoe UI", 11))
        info_categoria.setStyleSheet("color:#34495e; padding: 5px;")
        layout.addWidget(info_categoria)
        
        info_corte = QLabel(f"corte detectado: {self.indice_corte+1} de {self.total_cortes}")
        info_corte.setFont(QFont("Segoe UI", 11))
        info_corte.setStyleSheet("color: #34495e; padding: 5px;")
        layout.addWidget(info_corte)

        preview_label = QLabel("Revisa el corte en la ventana principal")
        preview_label.setAlignment(Qt.Alignment)
        preview_label.setStyleSheet("""
            QLabel {
                background-color: #ecf0f1;
                border: 2px dashed #95a5a6;
                border-radius: 8px;
                padding: 30px;
                color: #7f8c8d;
                font-size: 12px;
            }
        """)
        layout.addWidget(preview_label)
        instrucciones = QTextEdit()
        instrucciones.setReadOnly(True)
        instrucciones.setMaximumHeight(100)
        instrucciones.setHtml("""
            <div style='font-family: Segoe UI; font-size: 11px; color: #2c3e50;'>
                <b>Instrucciones:</b>
                <ul style='margin: 5px 0;'>
                    <li>✅ <b>Aprobar</b>: El corte es correcto, continuar con el análisis</li>
                    <li>🔄 <b>Ajustar</b>: Cerrar diálogo y seleccionar manualmente otro corte</li>
                    <li>⏭️ <b>Omitir</b>: Saltar esta categoría por ahora</li>
                </ul>
            </div>
        """)
        instrucciones.setStyleSheet("""
            QTextEdit {
                background-color: #e8f4f8;
                border: 1px solid #bdc3c7;
                border-radius: 6px;
            }
        """)
        layout.addWidget(instrucciones)
        botones_layout = QHBoxLayout()
        btn_rechazar = QPushButton(" Omitir categoria ")
        btn_rechazar.clicked.connect(self.reject)
        btn_ajustar = QPushButton("Ajuste manual")
        btn_ajustar.clicked.connect(self._ajustar_manual)
        btn_aprobar = QPushButton("Aprobar")
        btn_aprobar.clicked.connect(self._aprobar_corte)
        btn_aprobar.setDefault(True)
        
        botones_layout.addWidget(btn_rechazar)
        botones_layout.addStretch()
        botones_layout.addWidget(btn_ajustar)
        botones_layout.addWidget(btn_aprobar)
        layout.addLayout(botones_layout)
    
    def _aprobar_corte(self):
        self.corte_aprobado = self.indice_corte
        self.accept()
    def _ajustar_manual(self):
        self.corte_aprobado = -1
        self.reject()
        
class GestorWorkflowAutomatico(QObject):
    workflow_iniciado = pyqtSignal()
    workflow_completado = pyqtSignal(dict)
    categoria_procesada = pyqtSignal(str, bool)
    
    def __init__(self, instancia_tac):
        super().__init__()
        self.tac = instancia_tac
        self.en_progreso = False
        self.categorias_pendientes = []
        self.categorias_completadas = []
        self.categorias_omitidas = []
        self.indice_actual = 0
        
        self.mapeo_modulos = {
            'espesor': 'CTP404',
            'resolucion_contraste': 'CTP515',
            'resolucion_espacial': 'CTP528',
            'uniformidad_ruido': 'CTP486'
        }
        
        self.categorias_especiales = {
            'tamaño_pixel': self._procesar_tamano_pixel,
            'valores_numero_ct': self._procesar_valores_ct,
            'linealidad_numero_ct': self._procesar_linealidad_ct
        }
    
    def iniciar_workflow_automatico(self):
        try:
            if not self._validar_precondiciones():
                return False
            self._preparar_categorias()
            if not self.categorias_pendientes:
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.warning(self.tac,"Sin categorías",
                    "No hay categorías disponibles para procesar.\n"
                    "Asegúrate de que los cortes hayan sido detectados correctamente.")
                return False 
            self.en_progreso = True
            self.indice_actual = 0 
            self.workflow_iniciado.emit()
            print(f"iniciando workflow {self.categorias_pendientes}")
            QTimer.singleShot(500, self._procesar_siguiente_categoria)
            return True
        except Exception as e:
            print(f"Error {e}")
            traceback.print_exc()
            return False
    def _validar_precondiciones(self):
        if not hasattr(self.tac, 'visualizador_principal') or not self.tac.visualizador_principal:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(
                self.tac,
                "Error de inicialización",
                "No se encontró el visualizador principal.\n"
                "Carga una carpeta DICOM primero."
            )
            return False
        # Verificar volumen cargado
        if not self.tac.visualizador_principal.vol or not self.tac.visualizador_principal.vol.volumen_hu:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(
                self.tac,
                "Sin volumen DICOM",
                "No hay un volumen DICOM cargado.\n"
                "Carga una carpeta DICOM antes de iniciar el análisis automático."
            )
            return False
        
        # Verificar cortes detectados
        if not hasattr(self.tac.visualizador_principal, 'cortes') or not self.tac.visualizador_principal.cortes:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(
                self.tac,
                "Cortes no detectados",
                "No se detectaron los cortes automáticamente.\n"
                "Verifica que la imagen DICOM sea un CatPhan válido."
            )
            return False
        
        return True
    
    def _preparar_categorias(self):
        self.categorias_pendientes = []
        cortes_detectados = self.tac.visualizador_principal.cortes
        for categoria, modulo in self.mapeo_modulos.items():
            if modulo in cortes_detectados:
                indice_corte = corteS_detectados[modulo]
                self.categorias_pendientes.append({
                    'categoria': categoria,
                    'modulo': modulo,
                    'indice_corte': indice_corte,
                    'tipo': 'automatico'
                })  
        for categoria_especial in ['tamaño_pixel', 'valores_numero_ct', 'linealidad_numero_ct']:
            if 'CTP404' in cortes_detectados:
                self.categorias_pendientes.append({
                    'categoria': categoria_especial,
                    'modulo': 'CTP404',
                    'indice_corte': cortes_detectados['CTP404'],
                    'tipo': 'especial'
                })
    def _procesar_siguiente_categoria(self):
        if self.indice_actual >= len(self.categorias_pendientes):
            self._finalizar_workflow()
            return
        categoria_info = self.categorias_pendientes[self.indice_actual]
        categoria = categoria_info['categoria']
        indice_corte = categoria_info['indice_corte']
        
        try: 
            self._navegar_a_categoria(categoria)
            self._mostrar_corte_preview(indice_corte)
            QTimer.singleShot(300, lambda: self._solicitar_aprobacion_corte(categoria, indice_corte))
        except Exception as e:
            print(f"Error de categoria {e}")
    
    def _navegar_a_categoria(self, categoria):
        mapeo_pestanas = {
            'espesor': 'Espesor de corte',
            'tamaño_pixel': 'Tamaño de Pixel',
            'resolucion_contraste': 'Resolución de Contraste',
            'resolucion_espacial': 'Resolución Espacial',
            'valores_numero_ct': 'Valores CT',
            'linealidad_numero_ct': 'Linealidad del CT',
            'uniformidad_ruido': 'Uniformidad y Ruido'
        }
        
        nombre_pestana = mapeo_pestanas.get(categoria)
        if nombre_pestana and hasattr(self.tac, 'graficar'):
            self.tac.graficar.setCurrentText(nombre_pestana)
            print(f" Navegando a {nombre_pestana}")
    
    def _mostrar_corte_preview(self, indice_corte):
        try: 
            visualizador = self.tac.visualizador_principal
            
            if hasattr(visualizador, 'idx_actual'):
                visualizador.idx_actual = indice_corte
            if hasattr(visualizador, 'actualizar_ventana'):
                visualizador.actualizar_ventana()
            
            print(f" mostrando preview de corte {indice_corte+1} ")
        
        except Exception as e:
            print(f" error al mostrar preview {e}")
            
    def _solicitar_aprobacion_corte(self, categoria, indice_corte):
        try:
            total_cortes = len(self.tac.visualizador_principal.vol.volumen_hu)
            
            # Crear y mostrar diálogo
            dialogo = DialogoAprobacionCorte(
                self.tac,
                categoria,
                indice_corte,
                total_cortes
            )
            
            resultado = dialogo.exec_()
            
            if resultado == QDialog.Accepted and dialogo.corte_aprobado is not None:
                # Usuario aprobó el corte
                print(f"✅ Corte aprobado por usuario: {dialogo.corte_aprobado + 1}")
                self._ejecutar_analisis(categoria, dialogo.corte_aprobado)
            elif dialogo.corte_aprobado == -1:
                # Usuario quiere ajustar manualmente
                print(f"🔄 Usuario solicitó ajuste manual para {categoria}")
                self._modo_ajuste_manual(categoria)
            else:
                # Usuario omitió la categoría
                print(f"⏭️ Categoría omitida por usuario: {categoria}")
                self.categorias_omitidas.append(categoria)
                self.indice_actual += 1
                QTimer.singleShot(500, self._procesar_siguiente_categoria)
                
        except Exception as e:
            print(f"❌ Error en aprobación de corte: {e}")
            traceback.print_exc()
            self.categorias_omitidas.append(categoria)
            self.indice_actual += 1
            QTimer.singleShot(500, self._procesar_siguiente_categoria)
    
    def _ejecutar_analisis(self, categoria, indice_corte):
        try:
            resultado = self.tac.visualizador_principal.corte_seleccionado.emit(indice_corte)
            
            QTimer.singleShot(1400, lambda: self._post_analisis(categoria))
        
        except Exception as e:
            print(f"Error en analisis {e}")
            traceback.print_exc()
            self.categorias_omitidas.append(categoria)
            self.indice_actual += 1
            QTimer.singleShot(500, self._procesar_siguiente_categoria)

    def _post_analisis(self, categoria):
        try:
            # Verificar si el análisis generó resultados
            resultado_attr = self._obtener_atributo_resultado(categoria)
            resultado = getattr(self.tac, resultado_attr, None)
            
            if resultado:
                print(f"✅ Análisis completado para {categoria}")
                self.categorias_completadas.append(categoria)
                
                # Guardar automáticamente si está configurado
                if hasattr(self, 'auto_guardar') and self.auto_guardar:
                    self._guardar_resultado(categoria)
                
                self.categoria_procesada.emit(categoria, True)
            else:
                print(f"⚠️ No se generaron resultados para {categoria}")
                self.categorias_omitidas.append(categoria)
                self.categoria_procesada.emit(categoria, False)
            
            # Continuar con siguiente categoría
            self.indice_actual += 1
            QTimer.singleShot(800, self._procesar_siguiente_categoria)
            
        except Exception as e:
            print(f"❌ Error en post-análisis de {categoria}: {e}")
            traceback.print_exc()
            self.categorias_omitidas.append(categoria)
            self.indice_actual += 1
            QTimer.singleShot(500, self._procesar_siguiente_categoria)
    
    def _modo_ajuste_manual(self, categoria):
        """Permite al usuario ajustar manualmente el corte"""
        from PyQt5.QtWidgets import QMessageBox
        
        QMessageBox.information(
            self.tac,
            "Ajuste Manual",
            f"Ajusta el corte manualmente usando el slider.\n\n"
            f"Cuando hayas encontrado el corte correcto:\n"
            f"1. Presiona 'Elegir Corte'\n"
            f"2. El análisis se ejecutará automáticamente\n"
            f"3. Presiona 'Continuar Workflow' para seguir"
        )
        
        # Pausar el workflow hasta que el usuario continúe manualmente
        self.en_progreso = False
        print(f"⏸️ Workflow pausado para ajuste manual de {categoria}")
    
    def continuar_despues_ajuste_manual(self):
        """Continúa el workflow después de un ajuste manual"""
        if not self.en_progreso:
            self.en_progreso = True
            self.indice_actual += 1
            print(f"▶️ Reanudando workflow...")
            QTimer.singleShot(500, self._procesar_siguiente_categoria)
    
    def _obtener_atributo_resultado(self, categoria):
        """Obtiene el nombre del atributo de resultado para una categoría"""
        mapeo = {
            'espesor': 'resultados_espesor',
            'tamaño_pixel': 'resultados_tamano_pixel',
            'resolucion_contraste': 'resultados_resolucion_contraste',
            'resolucion_espacial': 'resultados_resolucion_espacial',
            'valores_numero_ct': 'resultados_ct',
            'linealidad_numero_ct': 'resultados_linealidad_ct',
            'uniformidad_ruido': 'resultados_uniformidad'
        }
        return mapeo.get(categoria, f'resultados_{categoria}')
    
    def _guardar_resultado(self, categoria):
        """Guarda automáticamente el resultado de una categoría"""
        try:
            # Mapeo de categorías a funciones de guardado
            mapeo_guardado = {
                'espesor': 'guardar_espesor_corte',
                'tamaño_pixel': 'guardar_tamano_pixel',
                'resolucion_contraste': 'guardar_resolucion_contraste',
                'resolucion_espacial': 'guardar_resolucion_espacial',
                'valores_numero_ct': 'guardar_valores_ct',
                'linealidad_numero_ct': 'guardar_linealidad_ct',
                'uniformidad_ruido': 'guardar_uniformidad'
            }
            
            funcion_guardado = mapeo_guardado.get(categoria)
            if funcion_guardado and hasattr(self.tac, funcion_guardado):
                metodo = getattr(self.tac, funcion_guardado)
                exito = metodo()
                if exito:
                    print(f"💾 Resultado de {categoria} guardado automáticamente")
                else:
                    print(f"⚠️ No se pudo guardar resultado de {categoria}")
        except Exception as e:
            print(f"❌ Error al guardar resultado de {categoria}: {e}")
    
    def _procesar_tamano_pixel(self, indice_corte):
        """Procesamiento especial para tamaño de pixel"""
        # Usa el mismo corte que CTP404
        return indice_corte
    
    def _procesar_valores_ct(self, indice_corte):
        """Procesamiento especial para valores CT"""
        # Usa el mismo corte que CTP404
        return indice_corte
    
    def _procesar_linealidad_ct(self, indice_corte):
        """Procesamiento especial para linealidad CT"""
        # Requiere configuración adicional de energía
        if hasattr(self.tac, 'energia_select'):
            # Configurar energía por defecto (0.12 MeV)
            self.tac.energia_select.setCurrentText("0.12 MeV")
            print(f"⚡ Energía configurada automáticamente: 0.12 MeV")
        return indice_corte
    
    def _finalizar_workflow(self):
        """Finaliza el workflow y muestra estadísticas"""
        self.en_progreso = False
        
        estadisticas = {
            'completadas': self.categorias_completadas,
            'omitidas': self.categorias_omitidas,
            'total': len(self.categorias_pendientes)
        }
        
        print(f"\n{'='*60}")
        print(f"🏁 Workflow Completado")
        print(f"✅ Categorías completadas: {len(self.categorias_completadas)}/{len(self.categorias_pendientes)}")
        print(f"⏭️ Categorías omitidas: {len(self.categorias_omitidas)}")
        print(f"{'='*60}\n")
        
        self.workflow_completado.emit(estadisticas)
        
        # Mostrar diálogo de resumen
        self._mostrar_resumen(estadisticas)
    
    def _mostrar_resumen(self, estadisticas):
        """Muestra un diálogo con el resumen del workflow"""
        from PyQt5.QtWidgets import QMessageBox
        
        mensaje = f"""
        <h3>🏁 Workflow Automatizado Completado</h3>
        
        <p><b>Estadísticas:</b></p>
        <ul>
            <li>✅ Completadas: {len(estadisticas['completadas'])}</li>
            <li>⏭️ Omitidas: {len(estadisticas['omitidas'])}</li>
            <li>📊 Total: {estadisticas['total']}</li>
        </ul>
        
        <p><b>Categorías completadas:</b></p>
        <ul>
            {''.join(f'<li>{cat}</li>' for cat in estadisticas['completadas'])}
        </ul>
        """
        
        if estadisticas['omitidas']:
            mensaje += f"""
            <p><b>Categorías omitidas:</b></p>
            <ul>
                {''.join(f'<li>{cat}</li>' for cat in estadisticas['omitidas'])}
            </ul>
            """
        
        msg_box = QMessageBox(self.tac)
        msg_box.setWindowTitle("Resumen del Workflow")
        msg_box.setTextFormat(Qt.RichText)
        msg_box.setText(mensaje)
        msg_box.setIcon(QMessageBox.Information)
        msg_box.exec_()
 
 
class WidgetControlWorkflow(QWidget):
    """
    Widget de control para el workflow automatizado.
    Muestra progreso y permite controlar la ejecución.
    """
    
    def __init__(self, gestor_workflow, parent=None):
        super().__init__(parent)
        self.gestor = gestor_workflow
        self._setup_ui()
        self._conectar_senales()
    
    def _setup_ui(self):
        """Configura la interfaz del widget de control"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Título
        titulo = QLabel("🤖 Análisis Automático")
        titulo.setFont(QFont("Segoe UI", 12, QFont.Bold))
        titulo.setStyleSheet("color: #2c3e50;")
        layout.addWidget(titulo)
        
        # Barra de progreso
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #bdc3c7;
                border-radius: 5px;
                text-align: center;
                background-color: #ecf0f1;
            }
            QProgressBar::chunk {
                background-color: #3498db;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        # Label de estado
        self.estado_label = QLabel("Esperando inicio...")
        self.estado_label.setAlignment(Qt.AlignCenter)
        self.estado_label.setStyleSheet("color: #7f8c8d; font-size: 10px;")
        layout.addWidget(self.estado_label)
        
        # Botones de control
        botones_layout = QHBoxLayout()
        
        self.btn_iniciar = QPushButton("🚀 Iniciar Análisis Automático")
        self.btn_iniciar.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #229954;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        self.btn_iniciar.clicked.connect(self._iniciar_workflow)
        
        self.btn_continuar = QPushButton("▶️ Continuar")
        self.btn_continuar.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        self.btn_continuar.clicked.connect(self.gestor.continuar_despues_ajuste_manual)
        self.btn_continuar.setEnabled(False)
        self.btn_continuar.hide()
        
        botones_layout.addWidget(self.btn_iniciar)
        botones_layout.addWidget(self.btn_continuar)
        
        layout.addLayout(botones_layout)
    
    def _conectar_senales(self):
        """Conecta las señales del gestor"""
        self.gestor.workflow_iniciado.connect(self._on_workflow_iniciado)
        self.gestor.workflow_completado.connect(self._on_workflow_completado)
        self.gestor.categoria_procesada.connect(self._on_categoria_procesada)
    
    def _iniciar_workflow(self):
        """Inicia el workflow"""
        exito = self.gestor.iniciar_workflow_automatico()
        if not exito:
            self.estado_label.setText("❌ Error al iniciar")
    
    def _on_workflow_iniciado(self):
        """Maneja el inicio del workflow"""
        self.btn_iniciar.setEnabled(False)
        self.estado_label.setText("🔄 Procesando...")
        self.progress_bar.setValue(0)
    
    def _on_categoria_procesada(self, categoria, exito):
        """Actualiza el progreso al procesar una categoría"""
        total = len(self.gestor.categorias_pendientes)
        procesadas = self.gestor.indice_actual
        porcentaje = int((procesadas / total) * 100)
        
        self.progress_bar.setValue(porcentaje)
        
        simbolo = "✅" if exito else "⏭️"
        self.estado_label.setText(f"{simbolo} {categoria} ({procesadas}/{total})")
    
    def _on_workflow_completado(self, estadisticas):
        """Maneja la finalización del workflow"""
        self.btn_iniciar.setEnabled(True)
        self.progress_bar.setValue(100)
        self.estado_label.setText(
            f"🏁 Completado: {len(estadisticas['completadas'])}/{estadisticas['total']}"
        )
 
 
# Función de integración para agregar al PruebaMensualTAC
def integrar_workflow_automatico(instancia_tac):
    """
    Integra el sistema de workflow automatizado en una instancia de PruebaMensualTAC.
    
    Args:
        instancia_tac: Instancia de PruebaMensualTAC donde integrar el workflow
        
    Returns:
        tuple: (gestor_workflow, widget_control)
    """
    # Crear gestor de workflow
    gestor = GestorWorkflowAutomatico(instancia_tac)
    
    # Crear widget de control
    widget_control = WidgetControlWorkflow(gestor, parent=instancia_tac)
    
    return gestor, widget_control
                    
        
        
        

           