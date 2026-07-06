import subprocess

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
    "services.calculadora_actividad_braqui",
    "services.MLCs_calibration_service",
    "services.auditorias",
    "services.decoradores_audit"
    
    # ANALISIS
    "analisisImagenes.Analisis_Catphan_TAC",
    "analisisImagenes.Analisis_PlacaCuadrada",
    "analisisImagenes.Analisis_PlacaRC",
    "analisisImagenes.ActividadFuente",
    "services.dosis_service",
    "services.equipos_service",
    

    # MODELOS
    "models.PDF.reportes",
]

cmd = [
    "pyinstaller",
    "--onedir",
    "--noconsole",
    "--clean",
    "--name", "RAD-QA",
    "--icon", "resources/capybara.ico"
]

# hidden imports
for h in hidden_imports:
    cmd += ["--hidden-import", h]

# data
cmd += [      
    "--add-data", "ui;ui",
    "--add-data", "data;data",
    "--add-data", "models;models",
    "--add-data", "resources;resources",
    "--add-data", "services;services",
    "--add-data", "mcc_PTW_read;mcc_PTW_read",
    "--add-data", "analisisImagenes;analisisImagenes",
    "--add-data", "BaseDatosQA.db;.",
    "--exclude-module", "torch",
    "--add-data", "analisisImagenes;espesor_corte.jpg",
    "--add-data", "analisisImagenes;resolucion_contraste.jpg",
    "--add-data", "analisisImagenes;resolucion_espacial.jpg",
    "--add-data", "analisisImagenes;valores_ct.jpg",
    "--add-data", "analisisImagenes;uniformidad_ruido.jpg",
]

cmd.append("main.py")

subprocess.run(cmd, check=True)
