# © 2026 David Ali Caballero Pérez. All rights reserved.
from PyQt5.QtCore import QThread, pyqtSignal
import pandas as pd

class SyncWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str)

    def __init__(self, manager, files_config):
        super().__init__()
        self.manager = manager
        self.files_config = files_config

    def run(self):
        try:
            # Capturamos el diccionario de estadísticas
            stats = self.manager.vectorized_sync_all_formats_from_inva(
                files_config=self.files_config, 
                progress_callback=self.progress.emit,
                check_cancel_callback=self.isInterruptionRequested
            )
            
            # Formateamos el mensaje de resumen
            mensaje_resumen = (
                f"La sincronización masiva se ha completado correctamente.\n\n"
                f"Resumen de la operación:\n"
                f"• IUAs ya ocupados en BD: {stats.get('already_taken', 0)}\n"
                f"• IUAs pasados de Reservado a Ocupado: {stats.get('reserved_to_taken', 0)}\n"
                f"• IUAs No Operando pasados a estado de Operación: {stats.get('n_to_s_upgraded', 0)}\n"
                f"• Nuevos IUAs Ocupados creados: {stats.get('new_taken', 0)}\n"
                f"• Nuevos IUAs Reservados creados: {stats.get('new_reserved', 0)}\n"
            )
            
            # Si se liberaron algunos, lo mostramos también
            if stats.get('freed_reserved', 0) > 0:
                mensaje_resumen += f"• IUAs Reservados liberados (por inactividad): {stats['freed_reserved']}\n"
                
            self.finished.emit(True, mensaje_resumen)
            
        except InterruptedError as e:
            self.finished.emit(False, str(e))
        except Exception as e:
            self.finished.emit(False, str(e))

class BatchWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str, bool, str) 

    def __init__(self, manager, file_path, col_code, col_qty, year, tipo_iua, do_reserve, save_path, col_type="", col_year=""):
        super().__init__()
        self.manager = manager
        self.file_path = file_path
        self.col_code = col_code
        self.col_qty = col_qty
        self.year = year
        self.tipo_iua = tipo_iua
        self.do_reserve = do_reserve
        self.save_path = save_path
        self.col_type = col_type 
        self.col_year = col_year

    def run(self):
        try:
            df_reporte = self.manager.reserve_from_excel_batch(
                self.file_path, self.col_code, self.col_qty, self.year, 
                self.tipo_iua, self.do_reserve, 
                progress_callback=self.progress.emit,
                check_cancel_callback=self.isInterruptionRequested,
                type_column=self.col_type,
                year_column=self.col_year
            )

            # --- NUEVA LÓGICA: División en múltiples hojas ---
            # Dejamos un margen de seguridad (Excel soporta 1,048,576 filas, incluyendo la cabecera)
            max_rows_per_sheet = 1000000 
            
            if len(df_reporte) <= max_rows_per_sheet:
                # Guardado normal si no supera el límite
                df_reporte.to_excel(self.save_path, index=False)
            else:
                # Usamos ExcelWriter para guardar múltiples pestañas en el mismo archivo
                with pd.ExcelWriter(self.save_path, engine='openpyxl') as writer:
                    for i in range(0, len(df_reporte), max_rows_per_sheet):
                        chunk = df_reporte.iloc[i:i + max_rows_per_sheet]
                        num_hoja = (i // max_rows_per_sheet) + 1
                        chunk.to_excel(writer, sheet_name=f'Reporte_P{num_hoja}', index=False)
            # -------------------------------------------------

            self.finished.emit(True, "Lote procesado y Excel generado correctamente.", self.do_reserve, self.save_path)
            
        except InterruptedError as e:
            self.finished.emit(False, str(e), self.do_reserve, "")
        except Exception as e:
            self.finished.emit(False, str(e), self.do_reserve, "")

class ConsultaWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str, str)

    def __init__(self, manager, file_path, col_code, save_path, mode="BDI", expand_func=None):
        super().__init__()
        self.manager = manager
        self.file_path = file_path
        self.col_code = col_code
        self.save_path = save_path
        self.mode = mode
        self.expand_func = expand_func # Guardamos la función

    def run(self):
        try:
            # Bifurcamos según el modo seleccionado
            if self.mode == "IUA":
                df_resultados = self.manager.match_iuas_from_excel(
                    self.file_path, self.col_code, progress_callback=self.progress.emit
                )
            else:
                df_resultados = self.manager.match_bdi_codes_from_excel(
                    self.file_path, self.col_code, progress_callback=self.progress.emit
                )

            if self.expand_func:
                df_resultados = self.expand_func(df_resultados)

            # --- NUEVA LÓGICA: División en múltiples hojas ---
            # Dejamos un margen de seguridad (Excel soporta 1,048,576 filas, incluyendo la cabecera)
            max_rows_per_sheet = 1000000 
            
            if len(df_resultados) <= max_rows_per_sheet:
                # Guardado normal si no supera el límite
                df_resultados.to_excel(self.save_path, index=False)
            else:
                # Usamos ExcelWriter para guardar múltiples pestañas en el mismo archivo
                with pd.ExcelWriter(self.save_path, engine='openpyxl') as writer:
                    for i in range(0, len(df_resultados), max_rows_per_sheet):
                        chunk = df_resultados.iloc[i:i + max_rows_per_sheet]
                        num_hoja = (i // max_rows_per_sheet) + 1
                        chunk.to_excel(writer, sheet_name=f'Reporte_P{num_hoja}', index=False)
            # -------------------------------------------------

            self.finished.emit(True, "Reporte generado y guardado correctamente.", self.save_path)
        except InterruptedError as e:
            self.finished.emit(False, str(e), "")
        except Exception as e:
            self.finished.emit(False, str(e), "")
