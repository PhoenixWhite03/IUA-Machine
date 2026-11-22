import pandas as pd
from lib.paths import carpeta_datos # Usando tu propia ruta segura

csv_path = carpeta_datos / "iua_records.csv"
parquet_path = carpeta_datos / "iua_records.parquet"

print(f"Leyendo CSV gigante desde: {csv_path} ... esto puede tardar un poco.")
# Forzamos texto igual que hacías antes para no perder ceros
df = pd.read_csv(csv_path, dtype=str).fillna("")

print("Convirtiendo a Parquet de alta velocidad...")
df.to_parquet(parquet_path, engine='pyarrow', index=False)

print(f"¡Migración exitosa! El nuevo archivo está en: {parquet_path}")

# # Leer el archivo Parquet
# df = pd.read_parquet(parquet_path)

# # Guardar como CSV
# df.to_csv('archivo_prueba.csv', index=False)