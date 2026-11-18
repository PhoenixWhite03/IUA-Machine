@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo   Instalador de dependencias - IUA Machine
echo ============================================
echo.

:: Verificar que Python este instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no esta instalado o no se encuentra en el PATH.
    echo Descargalo desde: https://www.python.org/downloads/
    echo Asegurate de marcar "Add Python to PATH" durante la instalacion.
    echo.
    pause
    exit /b 1
)

:: Crear entorno virtual si no existe
if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Creando entorno virtual (.venv)...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
) else (
    echo [1/3] Entorno virtual (.venv) ya existe.
)

echo [2/3] Actualizando pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet

echo [3/3] Instalando dependencias desde requirements.txt...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERROR] Hubo un problema al instalar las dependencias.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Instalacion completada con exito!
echo   Ahora puedes ejecutar IUA_Machine.bat
echo ============================================
echo.
pause
