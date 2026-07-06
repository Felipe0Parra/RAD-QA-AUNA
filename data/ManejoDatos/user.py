class Usuario():
    def __init__(self, username="",  password="",  fullname="", active=0, identificacion="", role="", firma = ""):
        self._usuario = username
        self._clave = password
        self._nombre = fullname
        self._activo = active
        self._ident = identificacion
        self._rol = role
        self._firma = firma

class Equipo():
    def __init__(self, equipo="",  model="",  serie="", fact_calibr =0, fecha=""):
        self._equipo = equipo
        self._model = model
        self._serie = serie
        self._fact = fact_calibr
        self._fecha = fecha