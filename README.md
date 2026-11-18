# IUA Machine 2.0

## Instalación rápida (Windows)

1. Asegúrate de tener **Python 3** instalado (con la opción *Add Python to PATH* marcada).
2. Haz doble clic en **`instalar_dependencias.bat`**.
   Esto creará un entorno virtual (`.venv`) e instalará automáticamente todas las dependencias listadas en `requirements.txt`.

## Ejecución

- Haz doble clic en **`IUA_Machine.bat`** (o **`IUA Machine Launcher.vbs`** para abrirlo sin consola).

## Instalación manual (opcional)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```
