# Single File Application: FichaProcessor_V5_1_Full_Comparison_Fix

import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox, ttk
import os
import threading
import queue
from dotenv import load_dotenv
import datetime
import subprocess
import sys
import shutil
import fitz       # For PDF processing: pip install PyMuPDF
from mistralai import Mistral # For Mistral API: pip install mistralai
import pandas as pd # For DataFrame operations: pip install pandas openpyxl xlrd
import json       # For handling JSON data
import re         # For regular expressions (e.g., in JSON parsing)
import traceback  # For detailed error logging

# --- Configuration Constants ---
DEFAULT_SOURCE_IMAGE_FOLDER = "./imagenes_jpg_temp" # Images from PDF go here first
ALLOWED_EXTENSIONS = ('.jpg', '.jpeg', '.png')      # Valid image types
DEFAULT_PROCESSED_IMAGES_BASE_FOLDER = "."          # Base for output folders
DEFAULT_INPUT_FILES_FOLDER = "fichasatrascribir"    # Default location for user's PDF/Excel
load_dotenv() # Load MISTRAL_API_KEY from .env file

# --- Helper for logging ---
def log_message_to_gui(message, logger_func=None):
    """Logs a message. If logger_func (GUI logger) is provided, uses it."""
    if logger_func:
        logger_func(message)
    else:
        # Fallback if GUI logger isn't passed (should not happen when called from app)
        print(f"LOG (no GUI): {datetime.datetime.now().strftime('%H:%M:%S')} - {message}")

# --- PDF Conversion ---
def convertir_pdf_a_imagenes_consecutivas_jpg(archivo_pdf, ruta_salida, dpi=300, logger_func=None):
    """Converts PDF to JPG images, cleans output dir first, names images imagen1.jpg, etc."""
    log_message_to_gui(f"Iniciando conversión PDF: {os.path.basename(archivo_pdf)} a {ruta_salida}", logger_func)
    try:
        if os.path.exists(ruta_salida): # Clean directory before new images
            log_message_to_gui(f"Limpiando directorio de imágenes temporales: {ruta_salida}", logger_func)
            for item in os.listdir(ruta_salida):
                item_path = os.path.join(ruta_salida, item)
                try:
                    if os.path.isfile(item_path) or os.path.islink(item_path): os.unlink(item_path)
                    elif os.path.isdir(item_path): shutil.rmtree(item_path)
                except Exception as e_clean: log_message_to_gui(f"Error limpiando {item_path}: {e_clean}", logger_func)
        else:
            os.makedirs(ruta_salida, exist_ok=True)

        pdf_documento = fitz.open(archivo_pdf)
        num_paginas_generadas = 0
        for num_pagina in range(len(pdf_documento)):
            pagina = pdf_documento.load_page(num_pagina)
            pix = pagina.get_pixmap(matrix=fitz.Matrix(dpi/72, dpi/72))
            nombre_archivo_salida = os.path.join(ruta_salida, f"imagen{num_pagina + 1}.jpg") # Original naming
            pix.save(nombre_archivo_salida, "JPEG")
            num_paginas_generadas += 1
            log_message_to_gui(f"  - Guardada: {os.path.basename(nombre_archivo_salida)}", logger_func)
        pdf_documento.close()
        log_message_to_gui(f"{num_paginas_generadas} imágenes JPG generadas en '{ruta_salida}'.", logger_func)
        return True, num_paginas_generadas
    except Exception as e:
        log_message_to_gui(f"Error durante la conversión de PDF: {e}\nDetalle: {traceback.format_exc()}", logger_func)
        return False, 0

# --- Image Encoding ---
def encode_image(image_path, logger_func=None):
    """Encodes an image file to a base64 string."""
    import base64 # Local import is fine here
    try:
        with open(image_path, "rb") as image_file:
            image_bytes = image_file.read()
        return base64.b64encode(image_bytes).decode('utf-8')
    except FileNotFoundError:
        log_message_to_gui(f"Error: No se encontró el archivo de imagen {image_path}", logger_func)
        return None
    except Exception as e:
        log_message_to_gui(f"Error al codificar la imagen '{image_path}': {e}", logger_func)
        return None

# --- Date Parsing Helper for Expiry Check ---
def parse_expiry_date(date_str, logger_func=None):
    """Tries to parse a date string into a date object using common formats."""
    if not date_str or not isinstance(date_str, str):
        return None
    formats_to_try = ["%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%Y-%m-%d", "%d %b %Y", "%d %B %Y", "%Y%m%d"] # Added YYYYMMDD
    for fmt in formats_to_try:
        try:
            return datetime.datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    log_message_to_gui(f"Advertencia: No se pudo parsear la fecha de vencimiento '{date_str}' con los formatos conocidos.", logger_func)
    return None

# --- Mistral API Processing ---
def process_images_with_mistral(image_folder_path, ficha_id, logger_func=None):
    """Processes images in the folder using Mistral API, includes expiry check."""
    import time # json, re are global

    log_message_to_gui(f"\n--- Iniciando escaneo en: '{image_folder_path}' para Mistral ---", logger_func)
    files_to_process = []
    try: # Scan for images (should be re-sequenced "procesar_X.jpg" files)
        all_entries = os.listdir(image_folder_path)
        for entry in all_entries:
            entry_path = os.path.join(image_folder_path, entry)
            if os.path.isfile(entry_path) and entry.lower().endswith(ALLOWED_EXTENSIONS) and entry.startswith("procesar_"):
                files_to_process.append(entry_path)
        def get_seq_num(filepath): # Helper for natural sort of "procesar_X.jpg"
            try: return int(os.path.basename(filepath).split('_')[1].split('.')[0])
            except: return float('inf')
        files_to_process.sort(key=get_seq_num) # Sort "procesar_X.jpg" numerically
        log_message_to_gui(f"Se procesarán {len(files_to_process)} imágenes (re-secuenciadas).", logger_func)
    except Exception as e_scan:
        log_message_to_gui(f"¡ERROR! Escaneando '{image_folder_path}': {e_scan}\n{traceback.format_exc()}", logger_func); return [], [], [], None
    if not files_to_process:
        log_message_to_gui("No hay imágenes 'procesar_X.jpg' para enviar a Mistral.", logger_func); return [], [], [], None

    lista_de_datos, lista_errores_primarios, lista_errores_reintento_fallido = [], [], []
    now_dt = datetime.datetime.now() # For expiry check and timestamp
    timestamp_str = now_dt.strftime("%Y-%m-%d_%H-%M-%S")
    destination_folder_name = f"{ficha_id}_{timestamp_str}_procesados_api" # Images successfully processed by API
    destination_dir_path = os.path.join(DEFAULT_PROCESSED_IMAGES_BASE_FOLDER, destination_folder_name)
    try: os.makedirs(destination_dir_path, exist_ok=True); log_message_to_gui(f"Imágenes procesadas por API se guardarán en: '{destination_dir_path}'", logger_func)
    except OSError as e: log_message_to_gui(f"Error creando destino API: {e}", logger_func); destination_dir_path = None

    log_message_to_gui("\n--- Iniciando Procesamiento de Imágenes con Mistral (una por una en orden) ---", logger_func)
    for local_image_path in files_to_process: # These are the "procesar_X.jpg" files
        time.sleep(0.5) # Adjustable pause
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key: log_message_to_gui("Error Fatal: MISTRAL_API_KEY no configurada.", logger_func); break
        
        model = os.getenv("MISTRAL_MODEL", "mistral-small-latest")
        text_prompt = ( # Your detailed prompt
            "Extrae la información del documento de identidad en formato JSON. "
            "Los campos principales son: 'nombre_completo', 'numero_identificacion'. "
            "Identifica el 'tipo_documento'. Los valores posibles para 'tipo_documento' son estrictamente: "
            "'Cedula de Ciudadania', 'Cedula de Extranjeria', o 'Tarjeta de Identidad'. "
            "Si el 'tipo_documento' es 'Tarjeta de Identidad', también extrae la 'fecha_vencimiento' si está presente. "
            "El 'numero_identificacion' debe ser un número sin puntos ni separadores. "
            "Asegúrate que el JSON sea válido." )
        log_message_to_gui(f"\nProcesando con API: {os.path.basename(local_image_path)}", logger_func)
        base64_image_data_str = encode_image(local_image_path, logger_func=logger_func)
        if base64_image_data_str is None: lista_errores_primarios.append({"imagen": os.path.basename(local_image_path), "razon": "Error Codificación"}); continue
        
        _, img_ext = os.path.splitext(local_image_path); image_type = img_ext.lower().replace('.', '')
        if image_type == 'jpg': image_type = 'jpeg'
        if image_type not in ['jpeg', 'png', 'gif', 'webp']: image_type = 'jpeg'
        
        image_input_for_api = f"data:image/{image_type};base64,{base64_image_data_str}"
        messages = [{"role": "user", "content": [{"type": "text", "text": text_prompt}, {"type": "image_url", "image_url": image_input_for_api}]}] # Your working format
        
        max_attempts, attempt, interpretation_result, api_call_successful, last_api_error = 2, 0, None, False, None
        while attempt < max_attempts: # API call loop with retries
            attempt += 1
            try:
                client = Mistral(api_key=api_key)
                log_message_to_gui(f"Intento {attempt}/{max_attempts} API para '{os.path.basename(local_image_path)}'", logger_func)
                chat_response = client.chat.complete(model=model, messages=messages) # YOUR WORKING API CALL
                if not chat_response.choices: raise ValueError("Respuesta API inválida (sin 'choices')")
                interpretation_result = chat_response.choices[0].message.content
                api_call_successful = True; log_message_to_gui("API Éxito.", logger_func); break
            except Exception as e_api:
                last_api_error = e_api; log_message_to_gui(f"Error intento {attempt} API: {e_api}\nDetalle: {traceback.format_exc()}", logger_func)
                retry_sleep = 2 * attempt # Your retry sleep
                if attempt < max_attempts: time.sleep(retry_sleep); log_message_to_gui(f"Reintentando en {retry_sleep}s...", logger_func)
                else: lista_errores_reintento_fallido.append({"imagen": os.path.basename(local_image_path),"razon": f"Error API {max_attempts} intentos","detalle": f"{type(last_api_error).__name__}: {last_api_error}"})
        if not api_call_successful: continue
        
        log_message_to_gui(f"Respuesta Modelo (parcial):\n{interpretation_result[:200]}...", logger_func)
        json_string = "" # Initialize for robust error logging
        try: # JSON parsing and data processing
            try: json_string = interpretation_result.split('```json')[1].split('```')[0].strip()
            except IndexError: json_string = interpretation_result.strip(); log_message_to_gui("Advertencia: No se encontró bloque ```json```, usando toda la respuesta.", logger_func)
            
            datos = json.loads(json_string)
            datos['fuente_imagen_original'] = os.path.basename(local_image_path) # Store the "procesar_X.jpg" name
            
            # Expiry Date Check
            doc_type = datos.get('tipo_documento', '').strip().lower()
            expiry_date_str = datos.get('fecha_vencimiento', None)
            datos['estado_vencimiento'] = "No Aplica" # Default
            if "tarjeta de identidad" in doc_type and expiry_date_str:
                parsed_date = parse_expiry_date(expiry_date_str, logger_func)
                if parsed_date:
                    if parsed_date < now_dt.date(): datos['estado_vencimiento'] = "Vencida"; log_message_to_gui(f"¡ALERTA! TI '{datos.get('numero_identificacion', 'N/A')}' VENCIDA ({expiry_date_str})", logger_func)
                    else: datos['estado_vencimiento'] = "Vigente"
                else: datos['estado_vencimiento'] = "Fecha Vencimiento No Parseable"
            elif "tarjeta de identidad" in doc_type and not expiry_date_str: datos['estado_vencimiento'] = "Fecha Vencimiento No Encontrada"

            lista_de_datos.append(datos); log_message_to_gui("Datos extraídos y procesados de la imagen.", logger_func)
            if destination_dir_path and os.path.exists(local_image_path): # Move the "procesar_X.jpg" file
                try: shutil.move(local_image_path, os.path.join(destination_dir_path, os.path.basename(local_image_path)))
                except Exception as e_move: lista_errores_primarios.append({"imagen": os.path.basename(local_image_path),"razon": "Error Moviendo Img Post-API","detalle": str(e_move)})
        except Exception as e_json_proc: # Catch errors from json.loads or subsequent data processing
            lista_errores_primarios.append({"imagen": os.path.basename(local_image_path),"razon": "Error JSON o Procesamiento de Datos Post-API","detalle": str(e_json_proc)}); log_message_to_gui(f"Error procesando JSON/Datos: {e_json_proc}\nString Intento Parse: {json_string[:100]}...\n{traceback.format_exc()}", logger_func)

    log_message_to_gui(f"\nPROCESO MISTRAL TERMINADO. Imágenes procesadas: {len(lista_de_datos)}. Errores Primarios: {len(lista_errores_primarios)}. Errores API (reintentos fallidos): {len(lista_errores_reintento_fallido)}.", logger_func)
    return lista_de_datos, lista_errores_primarios, lista_errores_reintento_fallido, destination_dir_path

# --- DataFrame Processing and Excel Comparison (REVISED with fixes from V4.1) ---
def process_data_and_compare_excel(lista_de_datos_api, ficha_id, excel_file_path, logger_func=None):
    log_message_to_gui("Iniciando procesamiento de datos y comparación Excel...", logger_func)

    api_cols_base = ['nombre_completo', 'numero_identificacion', 'tipo_documento', 'fecha_vencimiento', 'estado_vencimiento', 'fuente_imagen_original']
    api_cols_derived = ['nombre_norm']
    api_cols_expected_internal = api_cols_base + api_cols_derived
    
    if not lista_de_datos_api:
        log_message_to_gui("No hay datos de API para procesar.", logger_func)
        df_api = pd.DataFrame(columns=api_cols_expected_internal)
    else:
        try:
            df_api = pd.DataFrame(lista_de_datos_api)
            log_message_to_gui(f"DataFrame API creado con {len(df_api)} registros.", logger_func)
            for col in api_cols_expected_internal: # Ensure all expected columns exist (base + derived like nombre_norm if added before this loop)
                if col not in df_api.columns: df_api[col] = pd.NA
            
            df_api['nombre_completo'] = df_api['nombre_completo'].fillna('').astype(str).str.strip()
            df_api['numero_identificacion'] = df_api['numero_identificacion'].fillna('').astype(str).str.strip()
            df_api['tipo_documento'] = df_api['tipo_documento'].fillna('Desconocido').astype(str).str.strip()
            df_api['fecha_vencimiento'] = df_api['fecha_vencimiento'].fillna('').astype(str).str.strip()
            df_api['estado_vencimiento'] = df_api['estado_vencimiento'].fillna('No Aplica').astype(str).str.strip()
            df_api['fuente_imagen_original'] = df_api['fuente_imagen_original'].fillna('').astype(str).str.strip()
            df_api['nombre_norm'] = df_api['nombre_completo'].str.lower().str.strip()
            log_message_to_gui(f"Datos de API preparados: {len(df_api)} registros.", logger_func)
        except Exception as e:
            log_message_to_gui(f"Error GRAVE procesando DataFrame API: {e}\n{traceback.format_exc()}", logger_func)
            df_api = pd.DataFrame(columns=api_cols_expected_internal)
    
    intermediate_filename = f"datos_extraidos_api_{ficha_id}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
    intermediate_filepath = os.path.join(DEFAULT_PROCESSED_IMAGES_BASE_FOLDER, intermediate_filename)
    try:
        if not df_api.empty:
            cols_to_save_intermediate = ['numero_identificacion', 'nombre_completo', 'tipo_documento', 'fecha_vencimiento', 'estado_vencimiento', 'fuente_imagen_original']
            existing_cols_for_save = [col for col in cols_to_save_intermediate if col in df_api.columns]
            if existing_cols_for_save:
                 df_api[existing_cols_for_save].to_excel(intermediate_filepath, sheet_name="Datos_API_Extraidos_Detalle", index=False) # Changed sheet name slightly
                 log_message_to_gui(f"Datos API detallados guardados en: {intermediate_filepath}", logger_func)
            else: log_message_to_gui("No hay columnas para guardado intermedio detallado.", logger_func)
        else: log_message_to_gui("No hay datos de API para guardado intermedio.", logger_func)
    except Exception as e_inter:
        log_message_to_gui(f"Error guardando archivo API intermedio: {e_inter}\n{traceback.format_exc()}", logger_func)

    excel_cols_expected_after_load = ['identificacion_excel', 'nombre_excel_raw', 'nombre_norm_excel']
    df_excel = pd.DataFrame(columns=excel_cols_expected_after_load)
    if not excel_file_path or not os.path.exists(excel_file_path):
        log_message_to_gui(f"Archivo Excel para comparación no proporcionado/encontrado.", logger_func)
    else:
        try:
            temp_df_excel = pd.read_excel(excel_file_path, header=5, usecols="A,B", engine='xlrd')
            temp_df_excel.columns = ['identificacion_excel', 'nombre_excel_raw']
            temp_df_excel.dropna(subset=['identificacion_excel'], inplace=True)
            temp_df_excel['identificacion_excel'] = temp_df_excel['identificacion_excel'].astype(str).apply(
                lambda x: x.split(' - ')[-1] if pd.notna(x) and ' - ' in x else x
            ).str.replace(r'\.0$', '', regex=True).str.strip()
            temp_df_excel['nombre_excel_raw'] = temp_df_excel['nombre_excel_raw'].fillna('').astype(str).str.strip()
            temp_df_excel['nombre_norm_excel'] = temp_df_excel['nombre_excel_raw'].str.lower().str.strip()
            df_excel = temp_df_excel[temp_df_excel['identificacion_excel'] != ''].copy()
            log_message_to_gui(f"Datos Excel para comparación cargados: {len(df_excel)} registros.", logger_func)
        except Exception as e:
            log_message_to_gui(f"Error crítico al leer/procesar Excel: {e}\n{traceback.format_exc()}", logger_func)

    final_report_filename = f"informe_final_comparacion_{ficha_id}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
    final_report_path = os.path.join(DEFAULT_PROCESSED_IMAGES_BASE_FOLDER, final_report_filename)
    
    try:
        with pd.ExcelWriter(final_report_path, engine='openpyxl') as writer:
            sheet_written_count = 0
            # Sheet 1: All detailed extracted API data
            if not df_api.empty:
                cols_api_report = ['numero_identificacion', 'nombre_completo', 'tipo_documento', 'fecha_vencimiento', 'estado_vencimiento', 'fuente_imagen_original']
                existing_cols_api_report = [col for col in cols_api_report if col in df_api.columns]
                if existing_cols_api_report:
                    df_api[existing_cols_api_report].to_excel(writer, sheet_name="API_Datos_Detallados", index=False); sheet_written_count +=1
            
            if sheet_written_count == 0 and df_api.empty:
                 pd.DataFrame([{"info":"No se extrajeron datos de API válidos."}]).to_excel(writer, sheet_name="API_Datos_Detallados", index=False); sheet_written_count +=1 # Ensure this sheet always exists

            # Comparison Logic
            if not df_api.empty and not df_excel.empty and \
               all(col in df_api.columns for col in ['numero_identificacion', 'nombre_norm']) and \
               all(col in df_excel.columns for col in ['identificacion_excel', 'nombre_norm_excel']):
                
                log_message_to_gui("Realizando merge para comparación (estilo original)...", logger_func)
                
                # Prepare df_api for simple merge (identificacion, nombre, nombre_norm)
                df_api_simple = df_api[['numero_identificacion', 'nombre_completo', 'nombre_norm']].copy()
                df_api_simple.rename(columns={'numero_identificacion': 'identificacion', 'nombre_completo': 'nombre'}, inplace=True)

                # Prepare df_excel for simple merge (identificacion, nombre, nombre_norm)
                df_excel_simple = df_excel[['identificacion_excel', 'nombre_excel_raw', 'nombre_norm_excel']].copy()
                df_excel_simple.rename(columns={'identificacion_excel': 'identificacion', 'nombre_excel_raw': 'nombre', 'nombre_norm_excel':'nombre_norm'}, inplace=True)

                df_merged = pd.merge(
                    df_api_simple, df_excel_simple, on='identificacion',
                    how='outer', suffixes=('_lista', '_excel'), indicator=True )
                log_message_to_gui(f"Merge (estilo original simple) completado, {len(df_merged)} filas.", logger_func)

                # Paridad (Your original logic)
                matches_condition = (df_merged['_merge'] == 'both') & (df_merged['nombre_norm_lista'] == df_merged['nombre_norm_excel'])
                df_matches = df_merged.loc[matches_condition, ['identificacion', 'nombre_lista']].copy()
                df_matches.rename(columns={'nombre_lista': 'nombre_coincidente'}, inplace=True)
                if not df_matches.empty: df_matches.drop_duplicates(subset=['identificacion'], keep='first', inplace=True)
                df_matches.to_excel(writer, sheet_name='Comparacion_Paridad', index=False); sheet_written_count +=1
                log_message_to_gui(f"Coincidencias (Paridad): {len(df_matches)}", logger_func)

                # Discrepancias (Your original logic)
                df_discrepancies_list_for_concat = []
                name_mismatch_cond = (df_merged['_merge'] == 'both') & (df_merged['nombre_norm_lista'] != df_merged['nombre_norm_excel'])
                if name_mismatch_cond.any():
                    df_nm = df_merged.loc[name_mismatch_cond, ['identificacion', 'nombre_lista', 'nombre_excel']].copy()
                    df_nm['tipo_discrepancia'] = 'Diferencia de Nombre (Misma ID)'
                    df_nm.rename(columns={'nombre_lista': 'nombre_en_api', 'nombre_excel': 'nombre_en_plataforma'}, inplace=True)
                    df_nm.drop_duplicates(subset=['identificacion'], keep='first', inplace=True)
                    df_discrepancies_list_for_concat.append(df_nm)
                
                only_list_cond = df_merged['_merge'] == 'left_only'
                if only_list_cond.any():
                    df_ol = df_merged.loc[only_list_cond, ['identificacion', 'nombre_lista']].copy()
                    df_ol['tipo_discrepancia'] = 'Solo en API (No en Plataforma)'
                    df_ol.rename(columns={'nombre_lista': 'nombre_en_api'}, inplace=True)
                    df_ol['nombre_en_plataforma'] = pd.NA
                    df_ol.drop_duplicates(subset=['identificacion'], keep='first', inplace=True)
                    df_discrepancies_list_for_concat.append(df_ol)

                only_excel_cond = df_merged['_merge'] == 'right_only'
                if only_excel_cond.any():
                    df_oe = df_merged.loc[only_excel_cond, ['identificacion', 'nombre_excel']].copy()
                    df_oe['tipo_discrepancia'] = 'Solo en Plataforma (No en API)'
                    df_oe['nombre_en_api'] = pd.NA
                    df_oe.rename(columns={'nombre_excel': 'nombre_en_plataforma'}, inplace=True)
                    df_oe.drop_duplicates(subset=['identificacion'], keep='first', inplace=True)
                    df_discrepancies_list_for_concat.append(df_oe)

                if df_discrepancies_list_for_concat:
                    df_discrepancies = pd.concat(df_discrepancies_list_for_concat, ignore_index=True)
                    final_disc_cols_orig_style = ['identificacion', 'tipo_discrepancia', 'nombre_en_api', 'nombre_en_plataforma']
                    for col in final_disc_cols_orig_style:
                        if col not in df_discrepancies.columns: df_discrepancies[col] = pd.NA
                    df_discrepancies[final_disc_cols_orig_style].to_excel(writer, sheet_name='Comparacion_Discrepancias', index=False); sheet_written_count +=1
                    log_message_to_gui(f"Discrepancias (Estilo Original): {len(df_discrepancies)}", logger_func)
                elif sheet_written_count > 0 :
                     pd.DataFrame([{"info":"No se encontraron discrepancias."}]).to_excel(writer, sheet_name='Comparacion_Discrepancias', index=False)
            
            elif not df_excel.empty: # Only Excel data for comparison part
                 df_excel.rename(columns={'identificacion_excel':'identificacion', 'nombre_excel_raw':'nombre_de_plataforma'}).to_excel(writer, sheet_name='Solo_Datos_Plataforma', index=False)
            
            if sheet_written_count == 0: # Ultimate fallback if no sheets were written
                pd.DataFrame([{"info":"No hay datos suficientes para generar informe."}]).to_excel(writer, sheet_name='Resumen_General', index=False)

        abs_path = os.path.abspath(final_report_path)
        log_message_to_gui(f"¡Éxito! Informe final (comparación estilo original) generado en:\n{abs_path}", logger_func)
        return abs_path
    except Exception as e_write_excel:
        log_message_to_gui(f"Error CRÍTICO al escribir el archivo Excel final: {e_write_excel}\n{traceback.format_exc()}", logger_func)
        return None


# --- Tkinter Application Class (FichaProcessorApp) ---
class FichaProcessorApp:
    # ... (__init__ and all GUI methods are identical to V5)
    # The changes are in the data processing functions called by the GUI.
    # Make sure the FichaProcessorApp part is the one from the previous (V5) complete response.
    # I will paste it here for absolute completeness.

    def __init__(self, root_window):
        self.root = root_window
        self.root.title("Procesador de Fichas PDF v5.1 (Comparación Clave)")
        self.root.geometry("950x850")

        self.ficha_id = None
        self.current_temp_images_path = None
        self.pdf_to_images_step_done = False

        self.pdf_path_var = tk.StringVar()
        self.excel_path_var = tk.StringVar()
        self.ficha_id_display_var = tk.StringVar(value="Ficha ID: (se derivará del PDF)")
        self.output_dir_var = tk.StringVar(value=os.path.abspath(DEFAULT_PROCESSED_IMAGES_BASE_FOLDER))
        self.temp_images_dir_var = tk.StringVar(value=os.path.abspath(DEFAULT_SOURCE_IMAGE_FOLDER))

        top_frame = ttk.Frame(self.root, padding=(10,5)); top_frame.pack(fill="x", padx=10, pady=5)
        pdf_frame = ttk.LabelFrame(top_frame, text="Entrada Principal", padding=(10,5)); pdf_frame.pack(side=tk.LEFT, fill="x", expand=True, padx=(0,5))
        ttk.Label(pdf_frame, text="Archivo PDF:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.pdf_entry = ttk.Entry(pdf_frame, textvariable=self.pdf_path_var, width=40, state="readonly"); self.pdf_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.pdf_button = ttk.Button(pdf_frame, text="Seleccionar PDF", command=self.select_pdf); self.pdf_button.grid(row=0, column=2, padx=5, pady=5)
        self.ficha_id_label = ttk.Label(pdf_frame, textvariable=self.ficha_id_display_var); self.ficha_id_label.grid(row=1, column=0, columnspan=3, padx=5, pady=2, sticky="w")
        pdf_frame.grid_columnconfigure(1, weight=1)
        excel_frame = ttk.LabelFrame(top_frame, text="Opcional: Archivo Excel (Plataforma)", padding=(10,5)); excel_frame.pack(side=tk.LEFT, fill="x", expand=True, padx=(5,0))
        ttk.Label(excel_frame, text="Archivo Excel:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.excel_entry = ttk.Entry(excel_frame, textvariable=self.excel_path_var, width=40, state="readonly"); self.excel_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.excel_button = ttk.Button(excel_frame, text="Seleccionar Excel", command=self.select_excel); self.excel_button.grid(row=0, column=2, padx=5, pady=5)
        excel_frame.grid_columnconfigure(1, weight=1)

        control_frame = ttk.Frame(self.root, padding=(10,10)); control_frame.pack(fill="x", padx=10)
        self.step1_pdf_to_images_button = ttk.Button(control_frame, text="Paso 1: PDF a Imágenes", command=self.start_pdf_to_images_thread)
        self.step1_pdf_to_images_button.pack(side=tk.LEFT, padx=2)
        self.open_image_folder_button = ttk.Button(control_frame, text="Abrir Carpeta Limpieza", command=self.open_temp_image_folder, state=tk.DISABLED)
        self.open_image_folder_button.pack(side=tk.LEFT, padx=2)
        self.clear_images_button = ttk.Button(control_frame, text="Limpiar Carpeta", command=self.clear_temp_image_folder, state=tk.DISABLED)
        self.clear_images_button.pack(side=tk.LEFT, padx=2)
        self.step2_mistral_and_excel_button = ttk.Button(control_frame, text="Paso 2: Procesar y Comparar", command=self.start_mistral_and_comparison_thread, state=tk.DISABLED)
        self.step2_mistral_and_excel_button.pack(side=tk.LEFT, padx=2)
        self.test_api_button = ttk.Button(control_frame, text="Probar API", command=self.test_api_connection_thread)
        self.test_api_button.pack(side=tk.RIGHT, padx=10)

        config_dirs_frame = ttk.LabelFrame(self.root, text="Configuración Directorios", padding=(10, 5)); config_dirs_frame.pack(padx=10, pady=5, fill="x", expand=False)
        ttk.Label(config_dirs_frame, text="Dir. Base Salida:").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        self.output_dir_entry = ttk.Entry(config_dirs_frame, textvariable=self.output_dir_var, width=60); self.output_dir_entry.grid(row=0, column=1, padx=5, pady=2, sticky="ew")
        self.output_dir_button = ttk.Button(config_dirs_frame, text="Cambiar", command=self.select_output_dir); self.output_dir_button.grid(row=0, column=2, padx=5, pady=2)
        config_dirs_frame.grid_columnconfigure(1, weight=1)
        ttk.Label(config_dirs_frame, text="Dir. Imágenes Temp PDF:").grid(row=1, column=0, padx=5, pady=2, sticky="w")
        self.temp_images_dir_entry = ttk.Entry(config_dirs_frame, textvariable=self.temp_images_dir_var, width=60); self.temp_images_dir_entry.grid(row=1, column=1, padx=5, pady=2, sticky="ew")
        self.temp_images_dir_button = ttk.Button(config_dirs_frame, text="Cambiar", command=self.select_temp_images_dir); self.temp_images_dir_button.grid(row=1, column=2, padx=5, pady=2)
        status_frame = ttk.Frame(self.root); status_frame.pack(fill="x", padx=10, pady=5)
        self.progress_var = tk.DoubleVar(); self.progress_bar = ttk.Progressbar(status_frame, orient="horizontal", variable=self.progress_var); self.progress_bar.pack(side=tk.LEFT, fill="x", expand=True, padx=(0,5))
        self.status_label_var = tk.StringVar(value="Listo."); self.status_label = ttk.Label(status_frame, textvariable=self.status_label_var, width=50, anchor="w"); self.status_label.pack(side=tk.LEFT)
        log_frame = ttk.LabelFrame(self.root, text="Registro de Actividad", padding=(10,5)); log_frame.pack(padx=10, pady=10, fill="both", expand=True)
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=15); self.log_text.pack(fill="both", expand=True, padx=5, pady=5); self.log_text.configure(state='disabled')

        self.log_queue = queue.Queue(); self.root.after(100, self.process_log_queue)
        if not os.getenv("MISTRAL_API_KEY"): self.gui_log_direct("ADVERTENCIA: MISTRAL_API_KEY no configurada."); messagebox.showwarning("Config API", "MISTRAL_API_KEY no encontrada.")
        else: self.gui_log_direct("MISTRAL_API_KEY encontrada.")
        self.gui_log_direct("Bienvenido. Seleccione PDF para iniciar el Paso 1.")
        self._update_button_states()

    def gui_log_direct(self, message): self.log_text.configure(state='normal'); self.log_text.insert(tk.END, f"{datetime.datetime.now().strftime('%H:%M:%S')} - {message}\n"); self.log_text.see(tk.END); self.log_text.configure(state='disabled'); self.root.update_idletasks()
    def gui_log_from_thread(self, message): self.log_queue.put(message)
    def process_log_queue(self):
        try:
            while True: message = self.log_queue.get_nowait(); self.gui_log_direct(message)
        except queue.Empty: pass
        finally: self.root.after(100, self.process_log_queue)

    def select_pdf(self):
        initial_dir = DEFAULT_INPUT_FILES_FOLDER if os.path.exists(DEFAULT_INPUT_FILES_FOLDER) else os.getcwd()
        file_path = filedialog.askopenfilename(title="Seleccionar PDF", initialdir=initial_dir, filetypes=(("Archivos PDF", "*.pdf"), ("Todos", "*.*")))
        if file_path:
            self.pdf_path_var.set(file_path); self.ficha_id = os.path.splitext(os.path.basename(file_path))[0]
            self.ficha_id_display_var.set(f"Ficha ID: {self.ficha_id}"); self.gui_log_direct(f"PDF: {file_path}, ID: {self.ficha_id}")
            self.pdf_to_images_step_done = False; self._update_button_states()
    def select_excel(self):
        initial_dir = DEFAULT_INPUT_FILES_FOLDER if os.path.exists(DEFAULT_INPUT_FILES_FOLDER) else os.getcwd()
        file_path = filedialog.askopenfilename(title="Seleccionar Excel", initialdir=initial_dir, filetypes=(("Archivos Excel", "*.xls *.xlsx"), ("Todos", "*.*")))
        if file_path: self.excel_path_var.set(file_path); self.gui_log_direct(f"Excel: {file_path}")
    def select_output_dir(self):
        global DEFAULT_PROCESSED_IMAGES_BASE_FOLDER; dir_path = filedialog.askdirectory(title="Seleccionar Dir. Base Salida", initialdir=self.output_dir_var.get())
        if dir_path: self.output_dir_var.set(dir_path); DEFAULT_PROCESSED_IMAGES_BASE_FOLDER = dir_path; self.gui_log_direct(f"Dir. base salida: {dir_path}")
    def select_temp_images_dir(self):
        global DEFAULT_SOURCE_IMAGE_FOLDER; dir_path = filedialog.askdirectory(title="Seleccionar Dir. Imágenes Temp.", initialdir=self.temp_images_dir_var.get())
        if dir_path: self.temp_images_dir_var.set(dir_path); DEFAULT_SOURCE_IMAGE_FOLDER = dir_path; self.gui_log_direct(f"Dir. imágenes temp.: {dir_path}")
    def _update_progress(self, value, status_text=""):
        self.progress_var.set(value);
        if status_text: self.status_label_var.set(status_text[:70] + "..." if len(status_text) > 70 else status_text)
        self.root.update_idletasks()

    def _update_button_states(self, is_processing_any_step=False):
        pdf_selected = bool(self.pdf_path_var.get())
        self.pdf_button.config(state=tk.NORMAL if not is_processing_any_step else tk.DISABLED)
        self.excel_button.config(state=tk.NORMAL if not is_processing_any_step else tk.DISABLED)
        self.test_api_button.config(state=tk.NORMAL if not is_processing_any_step else tk.DISABLED)
        self.output_dir_button.config(state=tk.NORMAL if not is_processing_any_step else tk.DISABLED)
        self.temp_images_dir_button.config(state=tk.NORMAL if not is_processing_any_step else tk.DISABLED)
        if is_processing_any_step:
            self.step1_pdf_to_images_button.config(state=tk.DISABLED)
            self.open_image_folder_button.config(state=tk.DISABLED)
            self.clear_images_button.config(state=tk.DISABLED)
            self.step2_mistral_and_excel_button.config(state=tk.DISABLED)
        else:
            self.step1_pdf_to_images_button.config(state=tk.NORMAL if pdf_selected else tk.DISABLED)
            self.open_image_folder_button.config(state=tk.NORMAL if self.pdf_to_images_step_done else tk.DISABLED)
            self.clear_images_button.config(state=tk.NORMAL if self.pdf_to_images_step_done else tk.DISABLED)
            self.step2_mistral_and_excel_button.config(state=tk.NORMAL if self.pdf_to_images_step_done else tk.DISABLED)

    def open_temp_image_folder(self):
        if self.current_temp_images_path and os.path.exists(self.current_temp_images_path):
            try:
                if os.name == 'nt': os.startfile(self.current_temp_images_path)
                elif os.name == 'posix': subprocess.call(['open' if sys.platform == "darwin" else 'xdg-open', self.current_temp_images_path])
            except Exception as e: self.gui_log_direct(f"No se pudo abrir carpeta: {e}")
        else: messagebox.showwarning("Carpeta no encontrada", "Dir. imágenes temp. no existe o no ha sido creado.")

    def clear_temp_image_folder(self):
        if not self.current_temp_images_path or not os.path.exists(self.current_temp_images_path):
            messagebox.showinfo("Información", "Carpeta de imágenes temporales no existe o no definida para esta sesión.")
            return
        if messagebox.askyesno("Confirmar Limpieza", f"¿Eliminar TODOS los archivos en:\n{self.current_temp_images_path}?"):
            self.gui_log_direct(f"Iniciando limpieza de: {self.current_temp_images_path}")
            count_deleted = 0
            try:
                for item in os.listdir(self.current_temp_images_path):
                    item_path = os.path.join(self.current_temp_images_path, item)
                    if os.path.isfile(item_path): os.unlink(item_path); count_deleted +=1
                self.gui_log_direct(f"Limpieza completada. {count_deleted} archivos eliminados.")
                messagebox.showinfo("Limpieza Exitosa", f"{count_deleted} archivos eliminados.")
            except Exception as e: self.gui_log_direct(f"Error durante limpieza: {e}"); messagebox.showerror("Error Limpieza", f"Error: {e}")

    def start_pdf_to_images_thread(self):
        pdf_file = self.pdf_path_var.get();
        if not pdf_file: messagebox.showerror("Error Entrada", "Seleccione PDF."); return
        if not self.ficha_id: messagebox.showerror("Error Interno", "Ficha ID no definida."); return
        global DEFAULT_SOURCE_IMAGE_FOLDER; DEFAULT_SOURCE_IMAGE_FOLDER = self.temp_images_dir_var.get()
        self.current_temp_images_path = DEFAULT_SOURCE_IMAGE_FOLDER
        self._update_button_states(True); self.log_text.configure(state='normal'); self.log_text.delete('1.0', tk.END); self.log_text.configure(state='disabled')
        self._update_progress(0, "Iniciando conversión PDF..."); threading.Thread(target=self._run_pdf_conversion, args=(pdf_file, self.current_temp_images_path), daemon=True).start()

    def _run_pdf_conversion(self, pdf_file, temp_images_path):
        self.pdf_to_images_step_done = False
        try:
            self.gui_log_from_thread(f"Convirtiendo PDF '{os.path.basename(pdf_file)}'..."); self._update_progress(10, "Convirtiendo...")
            converted_ok, num_images = convertir_pdf_a_imagenes_consecutivas_jpg(pdf_file, temp_images_path, logger_func=self.gui_log_from_thread)
            if converted_ok and num_images > 0:
                self._update_progress(100, f"{num_images} imágenes generadas. Limpieza manual."); self.pdf_to_images_step_done = True
                messagebox.showinfo("Limpieza Manual Requerida", f"Se generaron {num_images} imágenes en:\n'{temp_images_path}'\n\n1. Use 'Abrir Carpeta' o 'Limpiar Carpeta'.\n2. Elimine imágenes innecesarias.\n3. Presione 'Paso 2: Procesar y Comparar'.")
            elif converted_ok and num_images == 0: self._update_progress(0, "PDF procesado, 0 imágenes."); messagebox.showwarning("Sin Imágenes", "PDF procesado pero no se generaron imágenes.")
            else: self._update_progress(0, "Error conversión PDF."); messagebox.showerror("Error Proceso", "Falló conversión PDF.")
        except Exception as e: self.gui_log_from_thread(f"Error conversión PDF: {e}\n{traceback.format_exc()}"); messagebox.showerror("Error Crítico", f"Error conversión: {e}"); self._update_progress(0, "Error crítico PDF.")
        finally: self._update_button_states(False)

    def start_mistral_and_comparison_thread(self):
        if not self.pdf_to_images_step_done or not self.current_temp_images_path: messagebox.showerror("Error de Flujo", "Debe completar el 'Paso 1: PDF a Imágenes' primero."); return
        if not self.ficha_id: messagebox.showerror("Error Interno", "Ficha ID no está definida. Reintente el Paso 1."); return
        self._update_button_states(is_processing_any_step=True); self._update_progress(0, "Iniciando Paso 2..."); self.gui_log_direct("Iniciando Paso 2...")
        threading.Thread(target=self._run_resequence_mistral_and_comparison, daemon=True).start()

    def _run_resequence_mistral_and_comparison(self):
        try:
            self.gui_log_from_thread("Paso 2.0: Resecuenciando imágenes..."); self._update_progress(5, "Resecuenciando...")
            resequence_success, num_resequenced = self._resequence_images_in_temp_folder(self.current_temp_images_path)
            if not resequence_success: messagebox.showerror("Error Resecuenciación", "No se pudieron resecuenciar. Revise log."); self._update_progress(0, "Error resecuenciando."); return
            if num_resequenced == 0: messagebox.showinfo("Sin Imágenes", "No quedaron imágenes tras limpieza/resecuenciación."); self._update_progress(0, "No hay imágenes."); return
            self.gui_log_from_thread(f"{num_resequenced} imágenes listas para Mistral.")
            
            excel_file = self.excel_path_var.get(); global DEFAULT_PROCESSED_IMAGES_BASE_FOLDER; DEFAULT_PROCESSED_IMAGES_BASE_FOLDER = self.output_dir_var.get()
            self.gui_log_from_thread("Paso 2.1: Procesando con Mistral..."); self._update_progress(10, "Enviando a Mistral...")
            api_data, err_p, err_r, processed_api_img_dir = process_images_with_mistral(self.current_temp_images_path, self.ficha_id, logger_func=self.gui_log_from_thread)
            if err_p: self.gui_log_from_thread(f"Errores primarios Mistral: {len(err_p)}")
            if err_r: self.gui_log_from_thread(f"Errores API (reintento): {len(err_r)}")
            if not api_data and not processed_api_img_dir: messagebox.showwarning("Proceso Mistral", "No se extrajeron datos o falló Mistral.")
            
            self.gui_log_from_thread("Paso 2.2: Generando informe Excel..."); self._update_progress(60, "Generando informe...")
            report_path = process_data_and_compare_excel(api_data, self.ficha_id, excel_file if excel_file else None, logger_func=self.gui_log_from_thread)
            if report_path:
                messagebox.showinfo("Proceso Completado", f"Proceso finalizado.\nInforme: {report_path}")
                try:
                    report_dir = os.path.dirname(report_path)
                    if os.path.exists(report_dir):
                        if os.name == 'nt': os.startfile(report_dir)
                        elif os.name == 'posix': subprocess.call(['open' if sys.platform == "darwin" else 'xdg-open', report_dir])
                except Exception as e_open: self.gui_log_from_thread(f"No se pudo abrir dir. informe: {e_open}")
            else: messagebox.showinfo("Proceso Completado (parcial)", "Finalizado. Informe Excel no generado/falló.")
            self._update_progress(100, "Todo el proceso completado.")
        except Exception as e_major: self.gui_log_from_thread(f"Error MAYOR en flujo Paso 2: {e_major}\n{traceback.format_exc()}"); messagebox.showerror("Error Crítico", f"Error: {e_major}"); self._update_progress(0, "Error crítico en Paso 2.")
        finally: self.pdf_to_images_step_done = False; self._update_button_states(False)

    def _resequence_images_in_temp_folder(self, folder_path):
        self.gui_log_from_thread(f"Resecuenciando imágenes en: {folder_path}")
        try:
            image_files = []
            for entry in os.listdir(folder_path):
                entry_path = os.path.join(folder_path, entry)
                if os.path.isfile(entry_path) and entry.lower().endswith(ALLOWED_EXTENSIONS) and entry.lower().startswith("imagen"):
                    image_files.append(entry_path)
            if not image_files: self.gui_log_from_thread("No archivos 'imagenX.jpg' para resecuenciar."); return True, 0
            def get_num(fpath):
                try: return int(re.findall(r'\d+', os.path.basename(fpath))[0])
                except: return float('inf')
            image_files.sort(key=get_num)
            renamed_count, temp_renames = 0, []
            for i, old_path in enumerate(image_files):
                _, ext = os.path.splitext(old_path); very_temp_name = f"__reseq_temp_{i+1}{ext}"; very_temp_path = os.path.join(folder_path, very_temp_name)
                try: os.rename(old_path, very_temp_path); temp_renames.append((very_temp_path, f"procesar_{i+1}{ext}"))
                except Exception as e_r1: self.gui_log_from_thread(f"Error 1er renombrado {os.path.basename(old_path)}: {e_r1}"); return False, renamed_count
            for very_temp_path, final_name_only in temp_renames:
                final_new_path = os.path.join(folder_path, final_name_only)
                try: os.rename(very_temp_path, final_new_path); self.gui_log_from_thread(f"  - Resecuenciado a: {final_name_only}"); renamed_count += 1
                except Exception as e_r2: self.gui_log_from_thread(f"Error 2do renombrado {os.path.basename(very_temp_path)}: {e_r2}"); return False, renamed_count
            self.gui_log_from_thread(f"Resecuenciación completada. {renamed_count} archivos renombrados a 'procesar_X.jpg'.")
            for entry in os.listdir(folder_path): # Safeguard cleanup
                if entry.lower().startswith("imagen") and entry.lower().endswith(ALLOWED_EXTENSIONS):
                    try: os.unlink(os.path.join(folder_path, entry)); self.gui_log_from_thread(f"  - Limpiado original restante: {entry}")
                    except Exception as e_c: self.gui_log_from_thread(f"  - Error limpiando original {entry}: {e_c}")
            return True, renamed_count
        except Exception as e: self.gui_log_from_thread(f"Error mayor resecuenciación: {e}\n{traceback.format_exc()}"); return False, 0

    def test_api_connection_thread(self):
        self.gui_log_direct("Iniciando prueba API..."); self._update_button_states(True); self._update_progress(0, "Probando API...")
        threading.Thread(target=self._run_api_test, daemon=True).start()
    def _run_api_test(self):
        api_key_value = os.getenv("MISTRAL_API_KEY")
        if not api_key_value: self.gui_log_from_thread("Prueba API Fallida: MISTRAL_API_KEY no configurada/vacía."); messagebox.showerror("Error API", "MISTRAL_API_KEY no configurada/vacía."); self._update_progress(0, "API Key no encontrada."); self._update_button_states(False); return
        self.gui_log_from_thread(f"Intentando conectar con Mistral API...");
        try:
            client = Mistral(api_key=api_key_value); models = client.models.list()
            if models and hasattr(models, 'data') and models.data: self.gui_log_from_thread(f"Conexión API Exitosa. {len(models.data)} modelos."); messagebox.showinfo("Prueba API Exitosa", f"Conexión API OK.\n{len(models.data)} modelos encontrados."); self._update_progress(100, "API OK.")
            else: self.gui_log_from_thread("Prueba API: Respuesta inesperada (no datos modelos)."); messagebox.showwarning("Prueba API", "Respuesta API inesperada."); self._update_progress(50, "API respuesta extraña.")
        except Exception as e: self.gui_log_from_thread(f"Prueba API Fallida: {type(e).__name__} - {e}\n{traceback.format_exc()}"); messagebox.showerror("Prueba API Fallida", f"Error: {e}"); self._update_progress(0, "Error API.")
        finally: self._update_button_states(False)

# --- Main execution block ---
if __name__ == "__main__":
    themed_tkinter_available = False
    try: from ttkthemes import ThemedTk; themed_tkinter_available = True
    except ImportError: print("ttkthemes no instalado (opcional). Para mejor apariencia: pip install ttkthemes")
    if themed_tkinter_available: main_window = ThemedTk(theme="arc") # Example: "arc", "plastik", "clearlooks"
    else: main_window = tk.Tk()
    app = FichaProcessorApp(main_window); main_window.mainloop()