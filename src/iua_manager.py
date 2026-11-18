# © 2026 David Ali Caballero Pérez. All rights reserved.
import pandas as pd
import numpy as np
import threading
import json
import re
import ast
from pathlib import Path
from utils.b36 import Base36
from lib.enums import Formats, GlobalRegistryTableColumn, IUARegistryState, IUAType

class IUAManager:
    def __init__(self, data_file_path):
        self.data_file_path = data_file_path
        self.df_iua = self._load_data()

        self.undo_stack = []
        self.redo_stack = []
        self.max_history = 5 # Guardamos los últimos 5 cambios

    def _load_data(self):
        """Carga el archivo de datos directamente a un DataFrame de Pandas y asegura las columnas."""
        expected_columns = [
            GlobalRegistryTableColumn.IUA.value,
            GlobalRegistryTableColumn.IUX.value,
            GlobalRegistryTableColumn.STATE.value,
            GlobalRegistryTableColumn.REPORT_YEAR.value,
            GlobalRegistryTableColumn.BDI_CODES.value,
            GlobalRegistryTableColumn.ASSET_TYPE.value,
            GlobalRegistryTableColumn.UC.value,
            GlobalRegistryTableColumn.FORMAT.value,
            GlobalRegistryTableColumn.OPERATION.value
        ]

        try:
            df = pd.read_parquet(self.data_file_path, engine='pyarrow')
            
            # Migración: Asegurar que todas las columnas esperadas existan en el DataFrame
            for col in expected_columns:
                if col not in df.columns:
                    if col == GlobalRegistryTableColumn.IUX.value and GlobalRegistryTableColumn.IUA.value in df.columns:
                        df[col] = df.apply(lambda row: self.extract_iux(row.get(GlobalRegistryTableColumn.IUA.value, ''), row.to_dict()), axis=1)
                    else:
                        df[col] = ""
                        
            return df.fillna("")
        except FileNotFoundError:
            # Si el archivo no existe, arranca de cero con las columnas completas
            return pd.DataFrame(columns=expected_columns)

    def save_data(self):
        """Guarda el archivo de datos en un hilo secundario para no congelar la interfaz."""
        def background_save(df_to_save, path):
            try:
                df_to_save.to_parquet(path, engine='pyarrow', index=False)
            except Exception as e:
                print(f"Error guardando archivo de datos en segundo plano: {e}")
        
        # Hacemos un .copy() para que el hilo guarde la versión exacta de este milisegundo,
        # permitiendo que el usuario siga trabajando (modificando df_iua) sin romper el guardado.
        thread = threading.Thread(target=background_save, args=(self.df_iua.copy(), self.data_file_path))
        thread.start()

    def save_state(self):
        """Toma una foto de la base de datos ANTES de un cambio."""
        if len(self.undo_stack) >= self.max_history:
            self.undo_stack.pop(0) # Borramos el más antiguo si llegamos al límite
            
        # Guardamos una copia exacta e independiente del DataFrame actual
        self.undo_stack.append(self.df_iua.copy())
        self.redo_stack.clear() # Si hay un cambio nuevo, el futuro (redo) se borra

    def undo(self):
        """Deshace el último cambio."""
        if self.undo_stack:
            # Guardamos el estado actual en rehacer
            self.redo_stack.append(self.df_iua.copy())
            # Restauramos el estado anterior
            self.df_iua = self.undo_stack.pop()
            self.save_data() # Sobrescribimos el archivo con la versión restaurada
            return True
        return False

    def redo(self):
        """Rehace un cambio deshecho."""
        if self.redo_stack:
            self.undo_stack.append(self.df_iua.copy())
            self.df_iua = self.redo_stack.pop()
            self.save_data()
            return True
        return False

    @staticmethod
    def extract_iux(iua_str: str, row_data: dict = None) -> str:
        """
        Extrae el IUL o IUS (código de 4 caracteres).
        - Formato 10 y 12: Tiene longitud 10. Toma el valor de la columna 'IUL'.
        - Otros formatos: Extrae los 4 caracteres correspondientes dentro del IUA.
        """
        if not iua_str or pd.isna(iua_str):
            return ""
        
        iua_clean = str(iua_str).strip().upper()
        row_data = row_data or {}

        if len(iua_clean) == 10:
            iul_val = row_data.get('IUL', '')
            if pd.isna(iul_val):
                return ""
            return f"{iul_val:0>4}".strip().upper() if iul_val else ""

        if len(iua_clean) >= 12:
            return iua_clean[1:5]

        return ""

    @staticmethod
    def extract_bdi_codes(row_data: dict) -> str:
        """Busca dinámicamente columnas de códigos (solo códigos) y las empaqueta en JSON."""
        codes_dict = {}
        for key, value in row_data.items():
            key_lower = str(key).lower()
            
            if ('código ' in key_lower or 'codigo' in key_lower or 'código bdi' in key_lower) and not 'proyecto' in key_lower:
                val_str = str(value).strip()
                if val_str and val_str.lower() != 'nan':
                    codes_dict[key] = val_str
                    
        return json.dumps(codes_dict, ensure_ascii=False) if codes_dict else ""

    @staticmethod
    def clean_bdi_code(code) -> str:
        """Limpia y normaliza un código BDI:
        - Descarta valores nulos, vacíos, 'nan' o '-'
        - Elimina el decimal '.0' residual generado por conversiones numéricas
        - Normaliza espacios y mayúsculas
        """
        if code is None or pd.isna(code):
            return ""
        
        val_str = str(code).strip()
        if not val_str or val_str.lower() in ('nan', 'none', 'null', '-', '--'):
            return ""
        
        # Eliminar decimal residual .0 o .00 al final (suciedad de conversión numérica)
        if re.search(r'\.0+$', val_str):
            val_str = re.sub(r'\.0+$', '', val_str).strip()
            
        if not val_str or val_str.lower() in ('nan', 'none', 'null', '-', '--'):
            return ""
            
        return val_str.upper()

    @staticmethod
    def extract_clean_codes_from_json(raw_val) -> set:
        """Extrae el conjunto de códigos BDI limpios y únicos de un campo JSON o texto."""
        if raw_val is None or pd.isna(raw_val):
            return set()
            
        val_str = str(raw_val).strip()
        if not val_str or val_str.lower() in ('nan', 'none', 'null', '-', '--'):
            return set()
            
        codes = set()
        
        # Si tiene estructura JSON (diccionario o lista)
        if "{" in val_str or "[" in val_str:
            parsed = None
            try:
                parsed = json.loads(val_str)
            except Exception:
                try:
                    parsed = ast.literal_eval(val_str)
                except Exception:
                    parsed = None
            
            if parsed is not None:
                if isinstance(parsed, dict):
                    candidates = parsed.values()
                elif isinstance(parsed, (list, tuple, set)):
                    candidates = parsed
                else:
                    candidates = [parsed]
                    
                for c in candidates:
                    cleaned = IUAManager.clean_bdi_code(c)
                    if cleaned:
                        codes.add(cleaned)
                return codes

        # Si no tiene llaves/corchetes, procesar como valor único
        cleaned = IUAManager.clean_bdi_code(val_str)
        if cleaned:
            codes.add(cleaned)
        return codes

    @staticmethod
    def _parse_year_safe(val) -> int:
        """Convierte de forma segura un año de reporte a entero para comparaciones numéricas."""
        if val is None or pd.isna(val):
            return -1
        val_str = str(val).strip()
        if val_str.endswith('.0'):
            val_str = val_str[:-2].strip()
        try:
            return int(val_str)
        except (ValueError, TypeError):
            return -1

    @staticmethod
    def extract_static_field(row_data: dict, possible_keys: list) -> str:
        """Busca un campo específico en el diccionario usando posibles nombres."""
        for key, value in row_data.items():
            if str(key).strip().lower() in possible_keys:
                val_str = str(value).strip()
                return val_str if val_str.lower() != 'nan' else ""
        return ""

    def get_available_iuas(self, tipo_iua, base_code="", cantidad=1):
        """Busca IUAs libres rellenando huecos desde cero (0) hacia arriba."""
        
        # 1. Configurar reglas según el tipo
        if tipo_iua == IUAType.SUBSTATION.value:
            prefix = "1" + f"{base_code:0>4}"
            target_len = 12
            suffix = "000"
            b36_pad = 4
        elif tipo_iua == IUAType.LINE.value:
            prefix = "2" + f"{base_code:0>4}"
            target_len = 12
            suffix = "000"
            b36_pad = 4
        elif tipo_iua == IUAType.TRAFO.value:
            prefix = "1"
            target_len = 10
            suffix = "0000"
            b36_pad = 5
        elif tipo_iua == IUAType.BT_NETWORK.value:
            prefix = "2"
            target_len = 10
            suffix = "0000"
            b36_pad = 5
        else:
            return []

        # 2. Filtrar los que coinciden con la regla actual
        mask = self.df_iua[
            (self.df_iua[GlobalRegistryTableColumn.IUA.value].str.startswith(prefix)) & 
            (self.df_iua[GlobalRegistryTableColumn.IUA.value].str.len() == target_len)
        ]
        
        # 3. LÓGICA CORREGIDA: Extraer TODOS los números usados a un Set (búsqueda instantánea)
        used_integers = set()
        
        if not mask.empty:
            if tipo_iua in [IUAType.TRAFO.value, IUAType.BT_NETWORK.value]:
                # Extraemos los 9 caracteres del incremento
                used_codes = mask[GlobalRegistryTableColumn.IUA.value].str.slice(1, 6)
            else:
                # Extraemos los 4 caracteres del incremento
                used_codes = mask[GlobalRegistryTableColumn.IUA.value].str.slice(5, 9)
            
            for code in used_codes:
                try:
                    # Convertimos a entero base 10 y lo metemos al set
                    used_integers.add(int(code, 36))
                except ValueError:
                    continue

        # 4. Generar los consecutivos rellenando los huecos vacíos
        iuas_libres = []
        curr_idx = 0 
        limite_maximo = (36 ** b36_pad) - 1 # El máximo posible (ej. ZZZZ)
        
        while len(iuas_libres) < cantidad:
            # Si el número actual NO está en el set de ocupados, es un hueco libre
            if curr_idx not in used_integers:
                b36 = Base36(curr_idx) 
                b36_padded = f"{b36:0>{b36_pad}}"
                iua = prefix + b36_padded + suffix
                iuas_libres.append(iua)

            # Evitar un bucle infinito si se acaban los códigos Base 36
            if curr_idx >= limite_maximo:
                break

            curr_idx += 1
            
        return iuas_libres

    def reserve_iuas(self, iuas_list, year):
        """Agrega una lista entera de IUAs con estado RESERVADO y extrae su IUX."""
        self.save_state()

        iux_list = [self.extract_iux(iua) for iua in iuas_list]
        
        nuevos_registros = pd.DataFrame({
            GlobalRegistryTableColumn.IUA.value: iuas_list,
            GlobalRegistryTableColumn.IUX.value: iux_list,
            GlobalRegistryTableColumn.STATE.value: [IUARegistryState.RESERVED.value] * len(iuas_list), 
            GlobalRegistryTableColumn.REPORT_YEAR.value: [str(year)] * len(iuas_list),
            GlobalRegistryTableColumn.BDI_CODES.value: [""] * len(iuas_list),
            GlobalRegistryTableColumn.ASSET_TYPE.value: [""] * len(iuas_list),
            GlobalRegistryTableColumn.UC.value: [""] * len(iuas_list),
            GlobalRegistryTableColumn.FORMAT.value: [""] * len(iuas_list),
            GlobalRegistryTableColumn.OPERATION.value: [""] * len(iuas_list)
        })
        
        if not nuevos_registros.empty:
            self.df_iua = pd.concat([self.df_iua, nuevos_registros], ignore_index=True)
            self.save_data()

    def reserve_from_excel_batch(
        self, file_path, code_column, quantity_column, year_default, tipo_iua_default, 
        do_reserve=True, progress_callback=None, check_cancel_callback=None,
        type_column="", year_column=""
    ):
        """Lee un Excel, reserva lotes y respeta el año dinámico y el IUX."""
        try:
            # --- 1. SOLUCIÓN RAÍZ: Forzamos a Pandas a leer todo como texto ---
            df_batch = pd.read_excel(file_path, dtype=str)
            
            if code_column not in df_batch.columns or quantity_column not in df_batch.columns:
                raise ValueError(f"Las columnas '{code_column}' o '{quantity_column}' no se encontraron en el archivo.")
            
            reporte_resultados = []
            total_rows = len(df_batch)
            
            valid_types_map = {
                "SUBESTACIÓN": IUAType.SUBSTATION.value,
                "SUBESTACION": IUAType.SUBSTATION.value,
                "LÍNEA": IUAType.LINE.value,
                "LINEA": IUAType.LINE.value,
                "RED BT": IUAType.BT_NETWORK.value,
                "TRANSFORMADOR": IUAType.TRAFO.value
            }
            
            for index, row in df_batch.iterrows():
                if check_cancel_callback and check_cancel_callback():
                    raise InterruptedError("Generación de lotes cancelada por el usuario.")

                if progress_callback and index % max(1, total_rows // 100) == 0:
                    progreso = int((index / total_rows) * 100)
                    progress_callback(progreso)

                # --- 1. Determinar el Tipo de IUA ---
                current_tipo_iua = tipo_iua_default
                if type_column and type_column in df_batch.columns:
                    val_tipo = str(row[type_column]).strip().upper()
                    if val_tipo in valid_types_map:
                        current_tipo_iua = valid_types_map[val_tipo]

                # --- 2. Determinar el Año de Reporte ---
                current_year = str(year_default)
                if year_column and year_column in df_batch.columns:
                    val_year = str(row[year_column]).strip()
                    if val_year and val_year.lower() != 'nan':
                        # Blindaje extra por si el año también se lee como "2025.0"
                        if val_year.endswith('.0'):
                            val_year = val_year[:-2]
                        current_year = val_year

                # --- 3. Regla de Negocio: IUX ---
                is_high_level = current_tipo_iua in [IUAType.SUBSTATION.value, IUAType.LINE.value]
                if is_high_level:
                    # --- 2. BLINDAJE EXTRA: Limpieza del string base ---
                    codigo_base = str(row[code_column]).strip().upper()
                    
                    # Si Pandas nos entregó "11.0", le quitamos el ".0"
                    if codigo_base.endswith('.0'):
                        codigo_base = codigo_base[:-2]
                        
                    # Y finalmente lo forzamos a tener 4 caracteres rellenando con ceros
                    codigo_base = f"{codigo_base:0>4}" 
                    
                    iux_format = f'="{codigo_base}"' 
                else:
                    codigo_base = "" 
                    iux_format = "" 

                try:
                    # int() ignorará sin problemas si lee "10" o "10.0" (previamente pasado a float)
                    cantidad = int(float(row[quantity_column]))
                except (ValueError, TypeError):
                    continue
                
                if cantidad <= 0: continue
                
                iuas_libres = self.get_available_iuas(current_tipo_iua, codigo_base, cantidad)
                
                if iuas_libres and len(iuas_libres) == cantidad:
                    if do_reserve:
                        self.reserve_iuas(iuas_libres, current_year)
                    
                    for iua in iuas_libres:
                        reporte_resultados.append({
                            'IUA_LIBRE': iua,
                            'IUL/IUS': iux_format, 
                            'TIPO_GENERADO': current_tipo_iua,
                            'AÑO_DE_REPORTE': current_year 
                        })
                else:
                    print(f"No se pudieron generar {cantidad} IUAs para el tipo {current_tipo_iua}.")

            if progress_callback: progress_callback(100)
            return pd.DataFrame(reporte_resultados)
            
        except Exception as e:
            raise Exception(f"Error procesando el lote: {str(e)}")

    def free_reserved_iuas(self, iuas_list):
        """Elimina de la base de datos los IUAs especificados si están en estado RESERVADO."""
        self.save_state()

        mask_to_drop = (
            self.df_iua[GlobalRegistryTableColumn.IUA.value].isin(iuas_list)
        ) & (
            self.df_iua[GlobalRegistryTableColumn.STATE.value] == IUARegistryState.RESERVED.value
        )
        
        cantidad_liberada = mask_to_drop.sum()

        if cantidad_liberada > 0:
            self.df_iua = self.df_iua[~mask_to_drop].reset_index(drop=True)
            self.save_data()
            
        return cantidad_liberada

    def sync_all_formats_from_inva(
        self, files_config, possible_iua_columns=['IUA', 'IUA ajustado', 'IUA provisional'],
        clear_unmatched_reserved=True, progress_callback=None, check_cancel_callback=None
    ):
        """Procesa archivos INVA y extrae todas las columnas estáticas (Formato, Activo, UC)."""
        print(f"Iniciando procesamiento masivo de {len(files_config)} archivos.")

        inva_data_dict = {}
        total_files = len(files_config)
        processed_years_taken = set()

        # --- NUEVO: Diccionario para almacenar las estadísticas ---
        stats = {
            'already_taken': 0,
            'reserved_to_taken': 0,
            'new_reserved': 0,
            'new_taken': 0,
            'freed_reserved': 0
        }

        for file_idx, config in enumerate(files_config):
            if check_cancel_callback and check_cancel_callback():
                raise InterruptedError("Sincronización cancelada por el usuario.")
            
            file_path = config['path']
            global_year = config['year']
            year_col = config.get('year_col', '')
            file_state = config.get('state', IUARegistryState.TAKEN.value)

            try:
                xls = pd.ExcelFile(file_path)
            except Exception as e:
                print(f"Omitiendo {file_path} por error: {e}")
                continue

            formatos_validos = [f for f in Formats if f.name in xls.sheet_names]
            total_hojas = len(formatos_validos)

            for idx, formato in enumerate(formatos_validos):
                if check_cancel_callback and check_cancel_callback():
                    raise InterruptedError("Sincronización cancelada por el usuario.")

                df_hoja = pd.read_excel(xls, sheet_name=formato.name)
                columna_encontrada = next((c for c in possible_iua_columns if c in df_hoja.columns), None)

                if columna_encontrada:
                    df_hoja = df_hoja.fillna('')
                    for _, row in df_hoja.iterrows():
                        row_dict = row.to_dict()
                        iua_val = str(row_dict.get(columna_encontrada, '')).strip()
                        
                        if iua_val:
                            final_year = global_year
                            if year_col and year_col in row_dict:
                                extracted_year = str(row_dict[year_col]).strip()
                                if extracted_year:
                                    final_year = extracted_year
                                    
                            # LÓGICA CORREGIDA: Solo agregar al set si es TAKEN
                            if file_state == IUARegistryState.TAKEN.value:
                                processed_years_taken.add(final_year)
                            
                            # Extraemos los datos para las nuevas columnas nativas
                            asset_type = self.extract_static_field(row_dict, ['activo'])
                            uc = self.extract_static_field(row_dict, ['unidad constructiva', 'uc'])
                            
                            inva_data_dict[iua_val] = {
                                'row_data': row_dict,
                                'year': final_year,
                                'format_name': formato.name,
                                'asset_type': asset_type,
                                'uc': uc,
                                'state': file_state
                            }

                if progress_callback:
                    base_progress = (file_idx / max(1, total_files)) * 70
                    hoja_progress = ((idx + 1) / max(1, total_hojas)) * (70 / max(1, total_files))
                    progress_callback(int(base_progress + hoja_progress))

        inva_iuas_globales = set(inva_data_dict.keys())
        if not inva_iuas_globales:
            if progress_callback: progress_callback(100)
            return stats # Retornamos stats vacíos

        db_iuas = set(self.df_iua[GlobalRegistryTableColumn.IUA.value].astype(str))
        if progress_callback: progress_callback(75)

        # 2. ACTUALIZACIÓN A BASE DE DATOS
        iuas_in_both = inva_iuas_globales.intersection(db_iuas)
        if iuas_in_both:
            # Contar los que ya estaban ocupados
            mask_already_taken = (
                self.df_iua[GlobalRegistryTableColumn.IUA.value].isin(iuas_in_both)
            ) & (
                self.df_iua[GlobalRegistryTableColumn.STATE.value] == IUARegistryState.TAKEN.value
            )
            stats['already_taken'] = int(mask_already_taken.sum())

            mask_update = (
                self.df_iua[GlobalRegistryTableColumn.IUA.value].isin(iuas_in_both)
            ) & (
                self.df_iua[GlobalRegistryTableColumn.STATE.value] == IUARegistryState.RESERVED.value
            )
             
            if mask_update.any():
                # Eliminamos la línea estática que forzaba a .TAKEN.value aquí arriba

                for iua in iuas_in_both:
                    if check_cancel_callback and check_cancel_callback():
                        raise InterruptedError("Sincronización cancelada por el usuario.")

                    idx_mask = (self.df_iua[GlobalRegistryTableColumn.IUA.value] == iua) & mask_update
                    if idx_mask.any():
                        data = inva_data_dict[iua]
                        row_data = data['row_data']

                        # --- Sumar a las estadísticas de Reservado a Ocupado ---
                        if data['state'] == IUARegistryState.TAKEN.value:
                            stats['reserved_to_taken'] += 1

                        self.df_iua.loc[idx_mask, GlobalRegistryTableColumn.STATE.value] = data['state']
                        self.df_iua.loc[idx_mask, GlobalRegistryTableColumn.REPORT_YEAR.value] = data['year']
                        self.df_iua.loc[idx_mask, GlobalRegistryTableColumn.IUX.value] = self.extract_iux(iua, row_data)
                        self.df_iua.loc[idx_mask, GlobalRegistryTableColumn.BDI_CODES.value] = self.extract_bdi_codes(row_data)
                        self.df_iua.loc[idx_mask, GlobalRegistryTableColumn.ASSET_TYPE.value] = data['asset_type']
                        self.df_iua.loc[idx_mask, GlobalRegistryTableColumn.UC.value] = data['uc']
                        self.df_iua.loc[idx_mask, GlobalRegistryTableColumn.FORMAT.value] = data['format_name']
                        self.df_iua.log[idx_mask, GlobalRegistryTableColumn.OPERATION.value] = row_data.get('Operación', '')

        if progress_callback: progress_callback(85)

        # 3. CREACIÓN DE NUEVOS REGISTROS
        new_iuas = inva_iuas_globales - db_iuas
        if new_iuas:
            new_rows = []
            for iua in new_iuas:
                if check_cancel_callback and check_cancel_callback():
                    raise InterruptedError("Sincronización cancelada por el usuario.")

                data = inva_data_dict[iua]
                row_data = data['row_data']

                # --- Sumar a las estadísticas de nuevos registros ---
                if data['state'] == IUARegistryState.TAKEN.value:
                    stats['new_taken'] += 1
                elif data['state'] == IUARegistryState.RESERVED.value:
                    stats['new_reserved'] += 1
                
                new_rows.append({
                    GlobalRegistryTableColumn.IUA.value: iua,
                    GlobalRegistryTableColumn.IUX.value: self.extract_iux(iua, row_data),
                    GlobalRegistryTableColumn.STATE.value: data['state'],
                    GlobalRegistryTableColumn.REPORT_YEAR.value: data['year'],
                    GlobalRegistryTableColumn.BDI_CODES.value: self.extract_bdi_codes(row_data),
                    GlobalRegistryTableColumn.ASSET_TYPE.value: data['asset_type'],
                    GlobalRegistryTableColumn.UC.value: data['uc'],
                    GlobalRegistryTableColumn.FORMAT.value: data['format_name'],
                    GlobalRegistryTableColumn.FORMAT.value: row_data.get('Operación', ''),
                })

            if new_rows:
                self.df_iua = pd.concat([self.df_iua, pd.DataFrame(new_rows)], ignore_index=True)

        if progress_callback: progress_callback(95)

        # 4. LIMPIEZA DE RESERVADOS
        # Ahora solo se ejecuta si hubo al menos un archivo TAKEN en el lote
        if clear_unmatched_reserved and processed_years_taken:
            mask_target_reserved = (
                (self.df_iua[GlobalRegistryTableColumn.STATE.value] == IUARegistryState.RESERVED.value) &
                (self.df_iua[GlobalRegistryTableColumn.REPORT_YEAR.value].astype(str).isin(processed_years_taken))
            )
            
            db_reserved_targets = set(self.df_iua[mask_target_reserved][GlobalRegistryTableColumn.IUA.value].astype(str))
            
            # Comparamos contra todos los IUAs del INVA procesado en este lote
            reserved_to_free = db_reserved_targets - inva_iuas_globales
            
            if reserved_to_free:
                mask_to_drop = self.df_iua[GlobalRegistryTableColumn.IUA.value].isin(reserved_to_free)
                self.df_iua = self.df_iua[~mask_to_drop].reset_index(drop=True)
                # --- Sumar a las estadísticas de liberados ---
                stats['freed_reserved'] = len(reserved_to_free)

                self.df_iua.fillna("", inplace=True)

        self.save_data()
        if progress_callback: progress_callback(100)

        # --- NUEVO: Retornamos las estadísticas al final del proceso ---
        return stats

    def wipe_all_data(self):
        """Borra absolutamente todos los registros y deja el archivo de datos en blanco (con las 8 columnas)."""
        self.df_iua = pd.DataFrame(
            columns=[
                GlobalRegistryTableColumn.IUA.value,
                GlobalRegistryTableColumn.IUX.value,
                GlobalRegistryTableColumn.STATE.value,
                GlobalRegistryTableColumn.REPORT_YEAR.value,
                GlobalRegistryTableColumn.BDI_CODES.value,
                GlobalRegistryTableColumn.ASSET_TYPE.value,
                GlobalRegistryTableColumn.UC.value,
                GlobalRegistryTableColumn.FORMAT.value,
                GlobalRegistryTableColumn.OPERATION.value
            ]
        )
        self.save_data()

    def match_bdi_codes_from_excel(self, file_path, code_column, progress_callback=None, check_cancel_callback=None):
        """Lee un Excel con códigos BDI, busca asociaciones exactas contra los códigos en JSON y devuelve reporte."""
        try:
            df_batch = pd.read_excel(file_path, dtype=str)
            
            if code_column not in df_batch.columns:
                raise ValueError(f"La columna '{code_column}' no se encontró en el archivo.")
            
            col_bdi = GlobalRegistryTableColumn.BDI_CODES.value
            col_iua = GlobalRegistryTableColumn.IUA.value
            col_year = GlobalRegistryTableColumn.REPORT_YEAR.value
            col_asset = GlobalRegistryTableColumn.ASSET_TYPE.value
            
            # 1. Construir índice invertido sobre df_iua para búsquedas exactas O(1)
            bdi_index = {}
            
            if col_bdi in self.df_iua.columns and not self.df_iua.empty:
                bdi_series = self.df_iua[col_bdi]
                mask_has_codes = bdi_series.notna() & (bdi_series != "")
                df_with_codes = self.df_iua[mask_has_codes]
                
                total_iua_rows = len(df_with_codes)
                step_iua = max(1, total_iua_rows // 50)
                
                bdi_vals = df_with_codes[col_bdi].values
                iua_vals = df_with_codes[col_iua].values if col_iua in df_with_codes.columns else [""] * total_iua_rows
                year_vals = df_with_codes[col_year].values if col_year in df_with_codes.columns else [""] * total_iua_rows
                asset_vals = df_with_codes[col_asset].values if col_asset in df_with_codes.columns else [""] * total_iua_rows
                
                for idx, (bdi_val, iua_val, year_val, asset_val) in enumerate(zip(bdi_vals, iua_vals, year_vals, asset_vals)):
                    if check_cancel_callback and check_cancel_callback():
                        raise InterruptedError("Consulta cancelada por el usuario.")
                        
                    if progress_callback and idx % step_iua == 0:
                        progreso = int((idx / total_iua_rows) * 50)
                        progress_callback(progreso)
                        
                    codes = self.extract_clean_codes_from_json(bdi_val)
                    if codes:
                        year_clean = str(year_val).strip() if pd.notna(year_val) else ""
                        if year_clean.endswith(".0"):
                            year_clean = year_clean[:-2]
                            
                        record = {
                            'IUA Asociado': str(iua_val) if pd.notna(iua_val) else "",
                            'Año de Reporte': year_clean,
                            'Tipo de Activo': str(asset_val) if pd.notna(asset_val) else ""
                        }
                        for code in codes:
                            if code not in bdi_index:
                                bdi_index[code] = []
                            bdi_index[code].append(record)
                            
            if progress_callback:
                progress_callback(50)
                
            # 2. Consultar los códigos del archivo batch
            reporte_resultados = []
            total_batch = len(df_batch)
            step_batch = max(1, total_batch // 50)
            
            cache_coincidencias = {}

            for index, raw_codigo in enumerate(df_batch[code_column]):
                if check_cancel_callback and check_cancel_callback():
                    raise InterruptedError("Consulta cancelada por el usuario.")

                if progress_callback and index % step_batch == 0:
                    progreso = 50 + int((index / total_batch) * 50)
                    progress_callback(progreso)

                codigo_limpio = self.clean_bdi_code(raw_codigo)
                
                if not codigo_limpio:
                    continue

                if codigo_limpio not in cache_coincidencias:
                    coincidencias = bdi_index.get(codigo_limpio)
                    if not coincidencias:
                        cache_coincidencias[codigo_limpio] = [{
                            'IUA Asociado': 'NO ENCONTRADO',
                            'Año de Reporte': 'N/A',
                            'Tipo de Activo': 'N/A'
                        }]
                    else:
                        if len(coincidencias) > 1:
                            # Ante repeticiones, conservar únicamente la(s) coincidencia(s) del REPORT_YEAR más reciente
                            max_year = max(self._parse_year_safe(item['Año de Reporte']) for item in coincidencias)
                            coincidencias = [
                                item for item in coincidencias 
                                if self._parse_year_safe(item['Año de Reporte']) == max_year
                            ]

                        seen = set()
                        unique_matches = []
                        for item in coincidencias:
                            key_tup = (item['IUA Asociado'], item['Año de Reporte'], item['Tipo de Activo'])
                            if key_tup not in seen:
                                seen.add(key_tup)
                                unique_matches.append(item)

                        cache_coincidencias[codigo_limpio] = unique_matches

                for item in cache_coincidencias[codigo_limpio]:
                    reporte_resultados.append({
                        'Código BDI Consultado': codigo_limpio,
                        'IUA Asociado': item['IUA Asociado'],
                        'Año de Reporte': item['Año de Reporte'],
                        'Tipo de Activo': item['Tipo de Activo']
                    })
            
            if progress_callback:
                progress_callback(100)
                
            if not reporte_resultados:
                return pd.DataFrame(columns=['Código BDI Consultado', 'IUA Asociado', 'Año de Reporte', 'Tipo de Activo'])
                
            return pd.DataFrame(reporte_resultados)
            
        except InterruptedError:
            raise
        except Exception as e:
            raise Exception(f"Error procesando la consulta masiva: {str(e)}")

    def match_iuas_from_excel(self, file_path, code_column, progress_callback=None):
        """Cruza una lista de IUAs desde un Excel contra la BD y devuelve todas las columnas."""
        try:
            df_batch = pd.read_excel(file_path, dtype=str)
            if code_column not in df_batch.columns:
                raise ValueError(f"La columna '{code_column}' no se encontró en el archivo.")
                
            lista_codigos = df_batch[code_column].dropna().tolist()
            
            # Simulamos el progreso inicial
            if progress_callback: progress_callback(20)
            
            # 1. Limpiamos la lista (evadiendo nulos)
            iua_list_clean = [str(iua).strip().upper() for iua in lista_codigos if str(iua).strip() and str(iua).lower() != 'nan']
            
            if progress_callback: progress_callback(40)
            
            # 2. Filtramos los que SÍ existen
            mask_exist = self.df_iua[GlobalRegistryTableColumn.IUA.value].isin(iua_list_clean)
            df_found = self.df_iua[mask_exist].copy()
            
            if progress_callback: progress_callback(60)
            
            # 3. Identificamos los que NO existen
            found_iuas = set(df_found[GlobalRegistryTableColumn.IUA.value])
            missing_iuas = set(iua_list_clean) - found_iuas
            
            if progress_callback: progress_callback(80)
            
            # 4. Creamos filas ficticias para los no encontrados
            if missing_iuas:
                missing_data = []
                for missing_iua in missing_iuas:
                    row = {col.value: "" for col in GlobalRegistryTableColumn}
                    row[GlobalRegistryTableColumn.IUA.value] = missing_iua
                    row[GlobalRegistryTableColumn.STATE.value] = "NO ENCONTRADO"
                    missing_data.append(row)
                
                df_missing = pd.DataFrame(missing_data)
                df_result = pd.concat([df_found, df_missing], ignore_index=True)
            else:
                df_result = df_found
                
            if progress_callback: progress_callback(100)
            
            return df_result
            
        except Exception as e:
            raise Exception(f"Error procesando la consulta masiva: {str(e)}")

    @staticmethod
    def _vectorized_extract_iux(df, iua_col):
        """Extrae el IUX (IUL o IUS) de todo el DataFrame simultáneamente usando Numpy."""
        if df.empty: return pd.Series(dtype=str)
            
        iua_series = df[iua_col].astype(str).str.strip().str.upper()
        iux_series = pd.Series("", index=df.index)
        
        # Regla: Longitud >= 12. Extrae los 4 caracteres correspondientes (índice 1:5).
        mask_12 = iua_series.str.len() >= 12
        iux_series = np.where(mask_12, iua_series.str.slice(1, 5), iux_series)
        
        # Regla: Longitud == 10. Toma el valor de la columna 'IUL'.
        mask_10 = iua_series.str.len() == 10
        if mask_10.any():
            iul_col = next((c for c in df.columns if str(c).strip().upper() == 'IUL'), None)
            if iul_col:
                iul_vals = df[iul_col].astype(str).str.strip().str.upper()
                iul_vals = iul_vals.replace('NAN', '').apply(lambda x: f"{x:0>4}" if x else "")
                iux_series = np.where(mask_10, iul_vals, iux_series)
                
        return iux_series

    @staticmethod
    def _vectorized_extract_bdi_codes(df):
        """Identifica columnas BDI según tu lógica y empaqueta a JSON toda la matriz."""
        bdi_cols = []
        for c in df.columns:
            c_lower = str(c).lower()
            if ('código' in c_lower or 'codigo' in c_lower or 'código bdi' in c_lower) and 'proyecto' not in c_lower and 'transformador' not in c_lower:
                bdi_cols.append(c)

        if not bdi_cols or df.empty:
            return pd.Series("", index=df.index)
            
        def row_to_json(row):
            d = {str(k): str(v).strip() for k, v in row.items() if pd.notna(v) and str(v).strip() and str(v).strip().lower() != 'nan'}
            return json.dumps(d, ensure_ascii=False) if d else ""
            
        return df[bdi_cols].apply(row_to_json, axis=1)

    @staticmethod
    def _vectorized_extract_static(df, possible_keys):
        """Extrae el valor de columnas estáticas para todos los registros de golpe."""
        col = next((c for c in df.columns if str(c).strip().lower() in possible_keys), None)
        if col and not df.empty:
            return df[col].astype(str).str.strip().replace(r'(?i)^nan$', '', regex=True)
        return pd.Series("", index=df.index)

    def vectorized_sync_all_formats_from_inva(
            self, files_config, possible_iua_columns=['IUA ajustado', 'IUA'],
            clear_unmatched_reserved=True, progress_callback=None, check_cancel_callback=None
        ):
            """Procesa archivos INVA vectorizadamente extrayendo estadísticas y columnas estáticas."""
            self.save_state()
            print(f"Iniciando procesamiento masivo de {len(files_config)} archivos.")

            total_files = len(files_config)
            processed_years_taken = set()

            stats = {
                'already_taken': 0,
                'reserved_to_taken': 0,
                'new_reserved': 0,
                'new_taken': 0,
                'freed_reserved': 0,
                'n_to_s_upgraded': 0
            }

            all_inva_dfs = []

            for file_idx, config in enumerate(files_config):
                if check_cancel_callback and check_cancel_callback():
                    raise InterruptedError("Sincronización cancelada por el usuario.")
                
                file_path = config['path']
                global_year = config['year']
                year_col = config.get('year_col', '')
                file_state = config.get('state', IUARegistryState.TAKEN.value)

                is_bra0_file = 'BRA0' in Path(file_path).stem.upper()

                try:
                    xls = pd.ExcelFile(file_path)
                except Exception as e:
                    print(f"Omitiendo {file_path} por error: {e}")
                    continue

                formatos_validos = [f for f in Formats if f.name in xls.sheet_names]
                total_hojas = len(formatos_validos)

                for idx, formato in enumerate(formatos_validos):
                    if check_cancel_callback and check_cancel_callback():
                        raise InterruptedError("Sincronización cancelada por el usuario.")

                    df_hoja = pd.read_excel(xls, sheet_name=formato.name)
                    columna_encontrada = next((c for c in possible_iua_columns if c in df_hoja.columns), None)

                    if columna_encontrada:
                        # Filtramos filas vacías de IUA usando operaciones de matriz
                        df_hoja = df_hoja[df_hoja[columna_encontrada].notna()].copy()
                        df_hoja['IUA_CLEAN'] = df_hoja[columna_encontrada].astype(str).str.strip()
                        df_hoja = df_hoja[df_hoja['IUA_CLEAN'] != '']
                        
                        if not df_hoja.empty:
                            # Vectorización del AÑO
                            if year_col and year_col in df_hoja.columns:
                                df_hoja['FINAL_YEAR'] = df_hoja[year_col].astype(str).str.strip().replace(r'(?i)^nan$', '', regex=True)
                                df_hoja['FINAL_YEAR'] = np.where(df_hoja['FINAL_YEAR'] == '', str(global_year), df_hoja['FINAL_YEAR'])
                            else:
                                df_hoja['FINAL_YEAR'] = str(global_year)
                            
                            if file_state == IUARegistryState.TAKEN.value:
                                processed_years_taken.update(df_hoja['FINAL_YEAR'].unique())

                            # Ensamblaje masivo del DataFrame estandarizado
                            df_processed = pd.DataFrame({
                                GlobalRegistryTableColumn.IUA.value: df_hoja['IUA_CLEAN'],
                                GlobalRegistryTableColumn.STATE.value: file_state,
                                GlobalRegistryTableColumn.REPORT_YEAR.value: df_hoja['FINAL_YEAR'],
                                GlobalRegistryTableColumn.FORMAT.value: formato.name
                            })
                            
                            # Extraemos los campos mediante los helpers vectorizados
                            df_processed[GlobalRegistryTableColumn.IUX.value] = self._vectorized_extract_iux(df_hoja, 'IUA_CLEAN')
                            df_processed[GlobalRegistryTableColumn.ASSET_TYPE.value] = self._vectorized_extract_static(df_hoja, ['activo'])
                            df_processed[GlobalRegistryTableColumn.UC.value] = self._vectorized_extract_static(df_hoja, ['unidad constructiva', 'uc'])
                            df_processed[GlobalRegistryTableColumn.BDI_CODES.value] = self._vectorized_extract_bdi_codes(df_hoja)
                            df_processed[GlobalRegistryTableColumn.OPERATION.value] = self._vectorized_extract_static(df_hoja, ['operación', 'operacion'])

                            # --- CORRECCIÓN DEFINITIVA: EXCEPCIÓN BRA0 (LÓGICA INVERSA) ---
                            if is_bra0_file:
                                # Estandarizamos a texto, sin espacios y en mayúsculas
                                col_op = df_processed[GlobalRegistryTableColumn.OPERATION.value].astype(str).str.strip().str.upper()
                                
                                # Tu idea: La máscara será Verdadera para todo lo que NO (~) sea 'S' o 'N'
                                mask_bra0 = ~col_op.isin(['S', 'N'])
                                
                                # Inyectamos la 'S' a todo lo que cayó en la máscara
                                df_processed[GlobalRegistryTableColumn.OPERATION.value] = np.where(
                                    mask_bra0,
                                    'S',
                                    col_op  # Guardamos la versión ya limpia en mayúsculas para los que sí eran S o N
                                )
                            # -------------------------------------------------------------

                            all_inva_dfs.append(df_processed)

                    if progress_callback:
                        base_progress = (file_idx / max(1, total_files)) * 70
                        hoja_progress = ((idx + 1) / max(1, total_hojas)) * (70 / max(1, total_files))
                        progress_callback(int(base_progress + hoja_progress))

            if not all_inva_dfs:
                if progress_callback: progress_callback(100)
                return stats

            # Unimos todas las hojas y deduplicamos (el último archivo manda)
            df_inva_total = pd.concat(all_inva_dfs, ignore_index=True)
            df_inva_total.drop_duplicates(subset=[GlobalRegistryTableColumn.IUA.value], keep='last', inplace=True)
            
            inva_iuas_globales = set(df_inva_total[GlobalRegistryTableColumn.IUA.value])
            db_iuas = set(self.df_iua[GlobalRegistryTableColumn.IUA.value].astype(str))
            
            if progress_callback: progress_callback(75)

            # 2. ACTUALIZACIÓN A BASE DE DATOS (Cruce instantáneo por índices)
            df_db = self.df_iua.set_index(GlobalRegistryTableColumn.IUA.value)
            df_in = df_inva_total.set_index(GlobalRegistryTableColumn.IUA.value)

            iuas_in_both = list(inva_iuas_globales.intersection(db_iuas))
            
            if iuas_in_both:
                # Estadísticas base
                mask_already_taken = df_db.loc[iuas_in_both, GlobalRegistryTableColumn.STATE.value] == IUARegistryState.TAKEN.value
                stats['already_taken'] = int(mask_already_taken.sum())

                # 1. Identificamos los que están puramente RESERVADOS
                mask_reserved = df_db.loc[iuas_in_both, GlobalRegistryTableColumn.STATE.value] == IUARegistryState.RESERVED.value
                
                # --- NUEVO: Blindaje matemático de años ---
                # Convertimos las columnas de años a enteros para poder usar el operador Mayor Que (>)
                db_years = pd.to_numeric(df_db.loc[iuas_in_both, GlobalRegistryTableColumn.REPORT_YEAR.value], errors='coerce').fillna(0)
                in_years = pd.to_numeric(df_in.loc[iuas_in_both, GlobalRegistryTableColumn.REPORT_YEAR.value], errors='coerce').fillna(0)

                # 2. Identificamos la mejora de Operación: 
                # Local es 'N', Nuevo es 'S', Y el año nuevo es estrictamente MAYOR al año local
                mask_upgrade = (
                    (df_db.loc[iuas_in_both, GlobalRegistryTableColumn.STATE.value] == IUARegistryState.TAKEN.value) &
                    (df_db.loc[iuas_in_both, GlobalRegistryTableColumn.OPERATION.value] == 'N') &
                    (df_in.loc[iuas_in_both, GlobalRegistryTableColumn.OPERATION.value] == 'S') &
                    (in_years > db_years)
                )

                # Unimos ambas condiciones: se actualiza si es reservado O si cumple la mejora de operación
                mask_final = mask_reserved | mask_upgrade
                iuas_to_update = mask_final[mask_final].index

                if not iuas_to_update.empty:
                    # Actualizamos las estadísticas
                    stats['reserved_to_taken'] = int((df_in.loc[mask_reserved[mask_reserved].index, GlobalRegistryTableColumn.STATE.value] == IUARegistryState.TAKEN.value).sum())
                    stats['n_to_s_upgraded'] = int(mask_upgrade.sum()) # Nueva estadística
                    
                    # LA MAGIA VECTORIZADA: Reemplaza todas las columnas a la vez
                    df_db.update(df_in.loc[iuas_to_update])

            if progress_callback: progress_callback(85)

            # 3. CREACIÓN DE NUEVOS REGISTROS
            new_iuas = list(inva_iuas_globales - db_iuas)
            if new_iuas:
                df_new = df_in.loc[new_iuas].reset_index()
                
                stats['new_taken'] = int((df_new[GlobalRegistryTableColumn.STATE.value] == IUARegistryState.TAKEN.value).sum())
                stats['new_reserved'] = int((df_new[GlobalRegistryTableColumn.STATE.value] == IUARegistryState.RESERVED.value).sum())
                
                self.df_iua = pd.concat([df_db.reset_index(), df_new], ignore_index=True)
            else:
                self.df_iua = df_db.reset_index()

            if progress_callback: progress_callback(95)

            # 4. LIMPIEZA DE RESERVADOS
            if clear_unmatched_reserved and processed_years_taken:
                mask_target_reserved = (
                    (self.df_iua[GlobalRegistryTableColumn.STATE.value] == IUARegistryState.RESERVED.value) &
                    (self.df_iua[GlobalRegistryTableColumn.REPORT_YEAR.value].astype(str).isin(processed_years_taken))
                )
                
                db_reserved_targets = set(self.df_iua[mask_target_reserved][GlobalRegistryTableColumn.IUA.value].astype(str))
                reserved_to_free = db_reserved_targets - inva_iuas_globales
                
                if reserved_to_free:
                    mask_to_drop = self.df_iua[GlobalRegistryTableColumn.IUA.value].isin(reserved_to_free)
                    self.df_iua = self.df_iua[~mask_to_drop].reset_index(drop=True)
                    stats['freed_reserved'] = len(reserved_to_free)

                    self.df_iua.fillna("", inplace=True)

            if check_cancel_callback and check_cancel_callback():
                raise InterruptedError("Sincronización cancelada por el usuario.")

            self.save_data()
            if progress_callback: progress_callback(100)
            
            return stats
