import datetime

from services.anulacion import filtro_activo

def graficarvstiempo(self, query, ax, maquina, selected_column2, selected_chart, start_date, end_date, scatter = False, limite = None):
    # LR3 (DA-47/DA-48): `maquina` es siempre una de las 4 diarias y la
    # lectura es por RANGO DE FECHAS (bloque). Filtra sobre la MISMA
    # variable dinámica -> protegida por construcción, sin lista blanca.
    # H6 (PLAN_BRAQUI_DIARIO_HORA_IMAGEN_28-08.md): `braqui.date` puede
    # ahora traer hora -- `DATE(...)` en el SELECT (si no, el `strptime`
    # de abajo revienta con la hora pegada) y en el BETWEEN (si no, un
    # registro justo en `end_date` con hora queda excluido por
    # comparación de texto). Función compartida por las 4 diarias: para
    # las otras 3 (`date` siempre sin hora) `DATE(...)` es un no-op.
    query.prepare(f"""
        SELECT DATE(date) AS date, {selected_column2} FROM {maquina}
        WHERE DATE(date) BETWEEN :start_date AND :end_date{filtro_activo(maquina)}
        ORDER BY date ASC
    """)
    query.bindValue(":start_date", start_date)
    query.bindValue(":end_date", end_date)
    query.exec()
    
    x_data = []
    y_data = []
    while query.next():
        val = query.value(1)
        if val is None or val == '':
            continue
        x_data.append(query.value(0))       # la fecha
        y_data.append(float(query.value(1))) # valor de la columna elegida
    
    date = [datetime.datetime.strptime(date, '%Y-%m-%d').date() for date in x_data]
    
    if scatter is True:
        # Separar los datos según el valor
        green_dates = [d for d, val in zip(date, y_data) if val == 1.0]
        green_y = [val for val in y_data if val == 1.0]
        red_dates   = [d for d, val in zip(date, y_data) if val != 1.0]
        red_y   = [val for val in y_data if val != 1.0]
        
        ax.scatter(green_dates, green_y, c='green', marker='o', edgecolors='black', label='Paso')
        ax.scatter(red_dates, red_y, c='red', marker='o', edgecolors='black', label='No Paso')
        ax.legend()
    else:
        ax.plot(date, y_data, marker='o')
        
    self.figure.autofmt_xdate()
    ax.set_xlabel('Fecha')
    ax.set_ylabel(selected_chart)
    ax.set_title(f'{selected_chart} vs tiempo')
    ax.grid(True)
    
    if limite is not None:
        ax.axhline(y=limite, color='r', linestyle='dashed', label=f'Límite (±{limite})')
        ax.axhline(y=-limite, color='r', linestyle='dashed')
        ax.legend()
