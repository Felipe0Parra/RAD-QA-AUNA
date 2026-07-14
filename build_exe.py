import subprocess
import sys

hidden_imports = [
    # PAGINAS
    
    "ui.paginasControles.PruebasDiarias.IX",
    "ui.paginasControles.PruebasDiarias.halcyon",
    "ui.paginasControles.PruebasMensuales.ix_mensual",
    "ui.paginasControles.PruebasMensuales.tac_mensual",
    "ui.paginasControles.PruebasAnuales.ix_anual",   
    "ui.paginasControles.PruebasDiarias.seiscientos",
    "ui.paginasControles.PruebasMensuales.seiscientos_mensual",
    "ui.paginasControles.PruebasDiarias.braquiterapia",
    "ui.paginasControles.PruebasMensuales.halcyon_mensual",
    "data.ManejoDatos.load",
    "data.ManejoDatos.conection",
    "data.ManejoDatos.Tablas_Anuales.tablas_anuales",
    "ui.paginasControles.PruebasDiarias.PruebasDiarias",
    "services.MLCs_calibration_service",
    "services.auditorias",
    "services.decoradores_audit",

    # ANALISIS
    "analisisImagenes.Analisis_Catphan_TAC",
    "analisisImagenes.Analisis_PlacaCuadrada",
    "analisisImagenes.Analisis_PlacaRC",
    "analisisImagenes.ActividadFuente",
    "services.dosis_service",
    "services.equipos_service",

    # D4 (.mcc -> mensual): lector + métricas de simetría/planicidad. Se
    # importan estáticamente desde seiscientos_mensual, pero se listan aquí
    # por defensa (software auditado -> cero sorpresas de empaquetado).
    "services.mcc_metrics",
    "mcc_PTW_read.mcc_read",

    # MODELOS
    "models.PDF.reportes",
]

cmd = [
    sys.executable, "-m", "PyInstaller",
    "--onedir",
    "--noconsole",
    "--clean",
    "--name", "RAD-QA",
    "--icon", "resources/capybara.ico"
]

# hidden imports
for h in hidden_imports:
    cmd += ["--hidden-import", h]

# pylinac: ya se ejecutaba en builds previos (PicketFence/Starshot en
# MLCs_calibration_service, CatPhan en el análisis de TAC), PERO D4 usa
# submódulos NUEVOS -- pylinac.core.profile y pylinac.metrics.profile
# (simetría/planicidad de perfiles .mcc). PicketFence/Starshot no
# necesariamente los arrastraban, así que podrían faltar en el .exe y fallar
# con ModuleNotFoundError SOLO en runtime en Windows (no en desarrollo).
# collect-submodules mete todo el árbol de pylinac de una vez -> elimina esa
# clase entera de fallo, a costa de un .exe un poco más grande (aceptable).
cmd += ["--collect-submodules", "pylinac"]

# data
cmd += [      
    "--add-data", "ui;ui",
    "--add-data", "data;data",
    "--add-data", "models;models",
    "--add-data", "resources;resources",
    "--add-data", "services;services",
    "--add-data", "mcc_PTW_read;mcc_PTW_read",
    "--add-data", "analisisImagenes;analisisImagenes",
    "--exclude-module", "torch",
]

cmd.append("main.py")

subprocess.run(cmd, check=True)
