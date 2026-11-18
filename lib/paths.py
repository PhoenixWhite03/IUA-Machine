import hashlib
import secrets
import os
import sys
import json
from pathlib import Path
from platformdirs import user_data_dir

def resource_path(relative_path):
    """Obtiene la ruta absoluta al recurso, compatible con desarrollo y PyInstaller."""
    try:
        # PyInstaller crea una carpeta temporal en _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)

# --- RUTAS PRINCIPALES ---
APP_NAME = "IUAMachine"
APP_AUTHOR = "AIRE"

carpeta_datos = Path(user_data_dir(APP_NAME, APP_AUTHOR))
carpeta_datos.mkdir(parents=True, exist_ok=True)

DATA_PATH = carpeta_datos / "iua_records.parquet"
ICON_PATH = resource_path(os.path.join("src/assets", "IUA-Machine-LOGO-remove-bg-io.ico"))

# --- NUEVO: GESTIÓN DE CONFIGURACIÓN Y SEGURIDAD ---
SETTINGS_PATH = carpeta_datos / "settings.json"

def hash_password(password: str, salt: str = None) -> str:
    """Genera un hash seguro usando PBKDF2-HMAC-SHA256 con salt."""
    if not salt:
        salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100_000 # 100,000 iteraciones
    )
    return f"{salt}${key.hex()}"

def verify_password(stored_hash_string: str, provided_password: str) -> bool:
    """Verifica si la contraseña ingresada coincide con el hash guardado."""
    try:
        salt, stored_hash = stored_hash_string.split("$")
        check_hash = hash_password(provided_password, salt=salt).split("$")[1]
        return secrets.compare_digest(stored_hash, check_hash)
    except Exception:
        return False

def get_admin_password_hash() -> str:
    """Retorna el hash almacenado o inicializa uno por defecto ('admin123')."""
    data = {}
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if "admin_hash" in data:
                    return data["admin_hash"]
        except Exception:
            pass

    # Hash por defecto si es la primera vez
    default_hash = hash_password("admin123")
    save_admin_password_hash(default_hash)
    return default_hash

def save_admin_password_hash(hash_string: str):
    """Guarda el hash en settings.json manteniendo las otras configuraciones."""
    data = {}
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            pass
            
    data["admin_hash"] = hash_string
    # Eliminamos cualquier contraseña en texto plano previa
    data.pop("admin_password", None)

    with open(SETTINGS_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

def get_saved_theme():
    """Lee el último tema guardado desde el archivo JSON, o devuelve el tema por defecto."""
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Si existe la clave 'theme', la devuelve, si no, devuelve "Light Theme"
                return data.get("theme", "Light Theme")
        except Exception:
            return "Light Theme"
    return "Light Theme"

def save_theme(theme_name):
    """Guarda el nombre del tema seleccionado en el archivo JSON."""
    data = {}
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            pass
            
    data["theme"] = theme_name
    
    with open(SETTINGS_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
