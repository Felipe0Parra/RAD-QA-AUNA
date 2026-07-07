import sys
import os


def _configurar_registro_errores():
    """
    Escribe toda excepción no capturada (incluidas las de slots de PyQt5, que
    el runtime imprime y traga sin cerrar la app) en error_log.txt junto al
    ejecutable (o en la raíz del proyecto en desarrollo). El exe se distribuye
    con --noconsole: sin este registro, los errores en producción son invisibles.
    """
    import traceback
    from datetime import datetime

    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    ruta_log = os.path.join(base_dir, 'error_log.txt')

    hook_previo = sys.excepthook

    def _hook(tipo, valor, tb):
        try:
            with open(ruta_log, 'a', encoding='utf-8') as f:
                f.write(f"\n[{datetime.now():%Y-%m-%d %H:%M:%S}] Excepción no capturada:\n")
                f.write(''.join(traceback.format_exception(tipo, valor, tb)))
        except OSError:
            pass  # el registro de errores jamás debe producir otro error
        hook_previo(tipo, valor, tb)

    sys.excepthook = _hook


_configurar_registro_errores()

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QCoreApplication
QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
from ui.paginasEntrReg.Login import LoginPage





class AppController:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.login_window = LoginPage()
        self.login_window.login_successful.connect(self.show_selection_page)  # señal de entrada de usuario
        self.login_window.show()

    def show_selection_page(self, user_id):
        from ui.paginasGuia.selection_page import SelectionPage
        self.selection_window = SelectionPage(user_id)
        self.selection_window.Start_QA.connect(self.show_QA) 
        self.selection_window.show()
        self.login_window.close()  

    def show_QA(self, user_id):
        from ui.mainpages import MainWindow
        self.Main = MainWindow(user_id)
        self.Main.reRun_signal.connect(self.reRun)  # Conectar la señal ida a inicio
        self.Main.show()
        self.selection_window.close()
        
    def reRun(self):
        self.login_window = LoginPage()
        self.login_window.login_successful.connect(self.show_selection_page)
        self.login_window.show()   
    
    def run(self):
        sys.exit(self.app.exec_())

if __name__ == '__main__':
    controller = AppController()
    controller.run()
