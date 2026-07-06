import sys
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
