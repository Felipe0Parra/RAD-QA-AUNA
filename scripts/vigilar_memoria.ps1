<#
.SYNOPSIS
    Registra cuanta memoria usa el programa, segundo a segundo, en un CSV.

.DESCRIPTION
    Sirve para contestar una pregunta concreta: cuando la aplicacion se cierra
    sola al cargar una carpeta DICOM, se cerro por falta de memoria o por otra
    cosa. Si fue memoria, el CSV termina con la curva subiendo; si no, termina
    con la curva plana.

    No toca el programa ni la base de datos: solo mira desde afuera.
    No necesita instalar nada.

.EXAMPLE
    Abra DOS ventanas de PowerShell.

    En la primera, ANTES de abrir el programa:
        cd C:\Users\parra\Documents\AUNA_Codigos_2026\Codigo_radqa_2026-09-21
        .\scripts\vigilar_memoria.ps1

    En la segunda, el programa de siempre:
        .venv\Scripts\python main.py

    Trabaje normal. Cuando termine (o cuando se caiga), vuelva a la primera
    ventana y pulse Ctrl+C. El archivo memoria_radqa.csv queda en la carpeta.

.NOTES
    Si PowerShell se niega a ejecutarlo ("no se puede cargar porque la
    ejecucion de scripts esta deshabilitada"), corralo asi:
        powershell -ExecutionPolicy Bypass -File .\scripts\vigilar_memoria.ps1
#>

param(
    [string]$Proceso   = "python",
    [string]$Salida    = "memoria_radqa.csv",
    [int]   $Intervalo = 1
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "  Vigilando procesos llamados '$Proceso'" -ForegroundColor Cyan
Write-Host "  Escribiendo en: $Salida"
Write-Host "  Intervalo: $Intervalo segundo(s)"
Write-Host ""
Write-Host "  Deje esta ventana abierta. Pulse Ctrl+C para terminar." -ForegroundColor Yellow
Write-Host ""

"hora,pid,memoria_MB,memoria_privada_MB,ram_libre_MB,handles,hilos" |
    Out-File -FilePath $Salida -Encoding UTF8

$pico       = 0
$vistoAlguno = $false

try {
    while ($true) {
        $hora = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

        # RAM libre del sistema, en MB
        $ramLibre = [math]::Round(
            (Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory / 1024, 0
        )

        $procs = @(Get-Process -Name $Proceso -ErrorAction SilentlyContinue)

        if ($procs.Count -eq 0) {
            if ($vistoAlguno) {
                # Estaba y ya no esta: esto es el momento de la caida.
                "$hora,,,,$ramLibre,," | Out-File -FilePath $Salida -Append -Encoding UTF8
                Write-Host "  [$hora] EL PROCESO DESAPARECIO. Pico registrado: $pico MB. RAM libre ahora: $ramLibre MB" -ForegroundColor Red
                Write-Host "  Revise las ultimas lineas de $Salida" -ForegroundColor Red
                $vistoAlguno = $false
            }
        }
        else {
            $vistoAlguno = $true
            foreach ($p in $procs) {
                $mb  = [math]::Round($p.WorkingSet64    / 1MB, 1)
                $mbp = [math]::Round($p.PrivateMemorySize64 / 1MB, 1)
                if ($mb -gt $pico) { $pico = $mb }

                "$hora,$($p.Id),$mb,$mbp,$ramLibre,$($p.HandleCount),$($p.Threads.Count)" |
                    Out-File -FilePath $Salida -Append -Encoding UTF8

                Write-Host ("  [{0}] pid {1,-6}  {2,8:N1} MB   (pico {3:N1} MB)   RAM libre {4:N0} MB" -f `
                            $hora, $p.Id, $mb, $pico, $ramLibre)
            }
        }

        Start-Sleep -Seconds $Intervalo
    }
}
finally {
    Write-Host ""
    Write-Host "  Terminado. Pico de memoria observado: $pico MB" -ForegroundColor Cyan
    Write-Host "  Archivo: $Salida"
    Write-Host ""
}
