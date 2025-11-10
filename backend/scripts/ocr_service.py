import sys
import os
import json
import traceback
from dotenv import load_dotenv
import shutil
import subprocess
from mistralai import Mistral
import base64
import pandas as pd  # Se añade pandas para la comparación con Excel
import re
from datetime import datetime
import fitz  # For PDF processing: pip install PyMuPDF

# Cargar variables de entorno desde .env
load_dotenv()

# --- Constantes y Configuración ---
TEMP_IMAGE_FOLDER = os.path.join(os.path.dirname(__file__), '..', '..', 'temp_ocr_images')
ALLOWED_EXTENSIONS = ('.jpg', '.jpeg', '.png')

# Ajustar las rutas relativas
COMPARISON_EXCEL_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'datos_a_comparar.xlsx')
OUTPUT_FOLDER = os.path.join(os.path.dirname(__file__), '..', '..', 'Output_Informes')


def send_log(message):
    """Envía un mensaje de log al proceso de Node.js."""
    print(json.dumps({"type": "log", "message": str(message)}), flush=True)


def send_result(data):
    """Envía un resultado JSON al proceso de Node.js."""
    print(json.dumps(data), flush=True)

# --- PDF Conversion ---
def convert_pdf_to_images(archivo_pdf, ruta_salida, dpi=300):
    """
    Convierte PDF a imágenes JPG, limpia el directorio de salida primero.
    Retorna (True/False, lista_rutas_iniciales, conteo)
    """
    send_log(f"Iniciando conversión PDF: {os.path.basename(archivo_pdf)} a {ruta_salida}")
    try:
        if os.path.exists(ruta_salida): # Clean directory before new images
            send_log(f"Limpiando directorio de imágenes temporales: {ruta_salida}")
            for item in os.listdir(ruta_salida):
                item_path = os.path.join(ruta_salida, item)
                try:
                    if os.path.isfile(item_path) or os.path.islink(item_path): os.unlink(item_path)
                    elif os.path.isdir(item_path): shutil.rmtree(item_path)
                except Exception as e_clean: send_log(f"Error limpiando {item_path}: {e_clean}")
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
            send_log(f"  - Guardada: {os.path.basename(nombre_archivo_salida)}")
        pdf_documento.close()
        send_log(f"{num_paginas_generadas} imágenes JPG generadas en '{ruta_salida}'.")
        image_paths = [os.path.join(ruta_salida, f"imagen{i + 1}.jpg") for i in range(num_paginas_generadas)]  # Create image_paths list
        
        return True, image_paths, num_paginas_generadas # RETURN EXPLÍCITO EN ÉXITO

    except Exception as e:
        error_msg = f"Error durante la conversión de PDF: {e}\nDetalle: {traceback.format_exc()}"
        send_log(error_msg)
        send_result({"success": False, "action": "convert", "error": error_msg})
        return False, [], 0 # RETURN EXPLÍCITO EN FALLO

# --- 2. Abrir Carpeta ---
def open_folder(folder_path):
    send_log(f"Abriendo carpeta: {folder_path}")
    try:
        if not os.path.exists(folder_path):
            raise FileNotFoundError(f"La carpeta no existe: {folder_path}")
        
        # Use os.path.realpath to get the absolute path and handle symbolic links
        real_path = os.path.realpath(folder_path)

        if sys.platform == 'win32':
            os.startfile(real_path)
        elif sys.platform == 'darwin':
            subprocess.run(['open', real_path], check=True)
        else: # Linux and other Unix-like systems
            subprocess.run(['xdg-open', real_path], check=True)
            
        send_result({"success": True, "action": "open_folder"})
    except FileNotFoundError as fnf_error:
        error_msg = str(fnf_error)
        send_log(error_msg)
        send_result({"success": False, "action": "open_folder", "error": error_msg})
    except Exception as e:
        # Catch other potential errors during subprocess execution
        error_msg = f"No se pudo abrir la carpeta: {e}"
        send_log(error_msg)
        send_result({"success": False, "action": "open_folder", "error": error_msg})

# Resequence Images
def _resequence_images_in_temp_folder(folder_path):
    send_log(f"Resecuenciando imágenes en: {folder_path}")
    try:
        image_files = []
        for entry in os.listdir(folder_path):
            entry_path = os.path.join(folder_path, entry)
            if os.path.isfile(entry_path) and entry.lower().endswith(ALLOWED_EXTENSIONS) and entry.lower().startswith("imagen"):
                image_files.append(entry_path)
        if not image_files: send_log("No archivos 'imagenX.jpg' para resecuenciar."); return True, 0
        def get_num(fpath):
            try: return int(re.findall(r'\d+', os.path.basename(fpath))[0])
            except: return float('inf')
        image_files.sort(key=get_num)
        renamed_count, temp_renames = 0, []
        for i, old_path in enumerate(image_files):
            _, ext = os.path.splitext(old_path); very_temp_name = f"__reseq_temp_{i+1}{ext}"; very_temp_path = os.path.join(folder_path, very_temp_name)
            try: os.rename(old_path, very_temp_path); temp_renames.append((very_temp_path, f"procesar_{i+1}{ext}"))
            except Exception as e_r1: send_log(f"Error 1er renombrado {os.path.basename(old_path)}: {e_r1}"); return False, renamed_count
        for very_temp_path, final_name_only in temp_renames:
            final_new_path = os.path.join(folder_path, final_name_only)
            try: os.rename(very_temp_path, final_new_path); send_log(f"  - Resecuenciado a: {final_name_only}"); renamed_count += 1
            except Exception as e_r2: send_log(f"Error 2do renombrado {os.path.basename(very_temp_path)}: {e_r2}"); return False, renamed_count
        send_log(f"Resecuenciación completada. {renamed_count} archivos renombrados a 'procesar_X.jpg'.")
        for entry in os.listdir(folder_path):
            if entry.lower().startswith("imagen") and entry.lower().endswith(ALLOWED_EXTENSIONS):
                try: os.unlink(os.path.join(folder_path, entry)); send_log(f"  - Limpiado original restante: {entry}")
                except Exception as e_c: send_log(f"  - Error limpiando original {entry}: {e_c}")
        return True, renamed_count
    except Exception as e: send_log(f"Error mayor resecuenciación: {e}\n{traceback.format_exc()}"); return False, 0


# NUEVA FUNCIÓN AÑADIDA PARA MANEJAR LA ELIMINACIÓN DE IMÁGENES
def delete_images(image_paths_to_delete):
    """Elimina una lista de archivos de imágenes del disco."""
    send_log("Iniciando eliminación de imágenes seleccionadas...")
    deleted_count = 0
    try:
        for image_path in image_paths_to_delete:
            try:
                if os.path.exists(image_path) and image_path.startswith(TEMP_IMAGE_FOLDER): # Seguridad: sólo elimina de la carpeta temp
                    os.unlink(image_path)
                    send_log(f"  - Eliminada: {os.path.basename(image_path)}")
                    deleted_count += 1
            except Exception as e:
                send_log(f"Error al eliminar {os.path.basename(image_path)}: {e}")
                
        send_log(f"Eliminación completada. {deleted_count} archivos eliminados.")
        send_result({
            "success": True, 
            "action": "delete_selected_images",
            "message": f"Paso 2 completado: {deleted_count} imágenes no deseadas eliminadas de la selección."
        })
    except Exception as e:
        error_msg = f"Error general durante la eliminación de imágenes: {e}\n{traceback.format_exc()}"
        send_log(error_msg)
        send_result({"success": False, "action": "delete_selected_images", "error": error_msg})
# --- 3. Procesamiento con Mistral ---
# NUEVA FUNCIÓN AÑADIDA PARA MANEJAR LA ELIMINACIÓN DE IMÁGENES
        
# --- 3. Procesamiento con Mistral ---
def encode_image_to_base64(image_path):
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        send_log(f"Error codificando la imagen {os.path.basename(image_path)}: {e}")
        return None

def process_with_mistral(selected_image_paths):
    send_log("--- Iniciando procesamiento con Mistral API ---")
    try:
        api_key = os.getenv("MISTRAL_API_KEY")
        # Check if the API key is missing or is the placeholder value
        if not api_key or api_key == 'TU_API_KEY':
            raise ValueError("La clave de API de Mistral no está configurada en el archivo .env o es el valor por defecto.")

        if not os.path.exists(TEMP_IMAGE_FOLDER):
            raise FileNotFoundError("La carpeta de imágenes temporales no existe. Realice el Paso 1 (convert) primero.")

        # Dynamically get allowed extensions from the constant
        image_files = sorted([
            os.path.join(TEMP_IMAGE_FOLDER, f)
            for f in os.listdir(TEMP_IMAGE_FOLDER)
            if f.lower().endswith(ALLOWED_EXTENSIONS) and os.path.join(TEMP_IMAGE_FOLDER, f) in selected_image_paths
        ])
        
        if not image_files:
            raise FileNotFoundError("No se encontraron imágenes válidas en la carpeta temporal para procesar.")

        client = Mistral(api_key=api_key)
        # Use a default model if not specified in environment variables
        model = os.getenv("MISTRAL_MODEL", "mistral-small-latest")
        
        # Define the prompt for the AI model
        text_prompt = (
            "Extrae la información del documento de identidad en formato JSON. "
            "Los campos principales son: 'nombre_completo', 'numero_identificacion'. "
            "Identifica el 'tipo_documento'. Los valores posibles para 'tipo_documento' son estrictamente: "
            "'Cedula de Ciudadania', 'Cedula de Extranjeria', o 'Tarjeta de Identidad'. "
            "El 'numero_identificacion' debe ser un número sin puntos ni separadores. "
            "Asegúrate que el JSON sea válido y solo contenga los campos solicitados."
        )

        results = []
        for image_path in image_files:
            send_log(f"Procesando imagen: {os.path.basename(image_path)}")
            base64_image = encode_image_to_base64(image_path)
            if not base64_image:
                results.append({"file": os.path.basename(image_path), "success": False, "error": "Error de codificación Base64"})
                continue

            # Construct the messages payload for the Mistral API
            messages = [
                {"role": "user", "content": [
                    {"type": "text", "text": text_prompt},
                    {"type": "image_url", "image_url": f"data:image/jpeg;base64,{base64_image}"}
                ]}
            ]

            try:
                chat_response = client.chat.complete(model=model, messages=messages)
                response_content = chat_response.choices[0].message.content
                send_log(f"Respuesta de la API recibida para {os.path.basename(image_path)}.")
                
                # Attempt to parse the JSON response, handling potential malformed JSON
                try:
                    # Find the start and end of the JSON object within the response string
                    json_start = response_content.find('{')
                    json_end = response_content.rfind('}')
                    if json_start != -1 and json_end != -1 and json_start < json_end:
                        json_match = response_content[json_start:json_end + 1]
                        parsed_json = json.loads(json_match)
                        results.append({"file": os.path.basename(image_path), "success": True, "data": parsed_json})
                    else:
                        raise ValueError("No se encontró un objeto JSON válido en la respuesta.")
                except json.JSONDecodeError as json_err:
                    send_log(f"Error decodificando JSON para {os.path.basename(image_path)}: {json_err}")
                    results.append({"file": os.path.basename(image_path), "success": False, "error": f"Respuesta JSON inválida: {json_err}"})
                except ValueError as val_err:
                    send_log(f"Error en el formato de respuesta para {os.path.basename(image_path)}: {val_err}")
                    results.append({"file": os.path.basename(image_path), "success": False, "error": str(val_err)})

            except Exception as api_err:
                send_log(f"Error de API de Mistral para {os.path.basename(image_path)}: {api_err}")
                results.append({"file": os.path.basename(image_path), "success": False, "error": str(api_err)})

        send_log("Procesamiento con Mistral finalizado.")
        send_result({"success": True, "action": "process", "data": results})

    except ValueError as ve:
        error_msg = f"Configuración inválida: {ve}"
        send_log(error_msg)
        send_result({"success": False, "action": "process", "error": error_msg})
    except FileNotFoundError as fnf_error:
        error_msg = f"Archivo o directorio no encontrado: {fnf_error}"
        send_log(error_msg)
        send_result({"success": False, "action": "process", "error": error_msg})
    except Exception as e:
        error_msg = f"Error general durante el procesamiento con Mistral: {e}\n{traceback.format_exc()}"
        send_log(error_msg)
        send_result({"success": False, "action": "process", "error": error_msg})


# Lógica de comparación con Excel - Implementación de la funcionalidad faltante de app_gui.py
def process_data_and_compare_excel(extracted_data_json_path, comparison_excel_path):
    send_log("Iniciando Paso 4: Comparación de datos con archivo Excel de referencia.")
    try:
        # 1. Cargar datos extraídos
        with open(extracted_data_json_path, 'r', encoding='utf-8') as f:
            extracted_data = json.load(f)
        
        # Filtrar solo los datos exitosos
        clean_data = [item['data'] for item in extracted_data if item.get('success') and item.get('data')]
        if not clean_data:
            send_log("Error: No se encontraron datos JSON extraídos exitosamente para comparar.")
            return False

        temp_data = []
        for item in clean_data:
            temp_data.append({
                'nombre_completo': item.get('nombre_completo'),
                'numero_identificacion': item.get('numero_identificacion'),
                'tipo_documento': item.get('tipo_documento')
            })
        
        df_extraido = pd.DataFrame(temp_data)
        
        # Renombrar para el reporte final
        df_extraido.rename(columns={
            'nombre_completo': 'Nombre_Ext', 
            'numero_identificacion': 'Identificacion_Ext'
        }, inplace=True)
        
        # 2. Cargar datos de referencia del Excel
        if not os.path.exists(comparison_excel_path):
            send_log(f"Error: Archivo de comparación no encontrado en {comparison_excel_path}")
            return False

        # Leer encabezado desde la fila 6 (header=5)
        df_referencia = pd.read_excel(comparison_excel_path, header=5)
        df_referencia.columns = df_referencia.columns.str.strip()
        
        # 3. Preparar DataFrames para la comparación
        
        # Renombrar columnas clave del Excel de referencia
        # CORRECCIÓN APLICADA: Usamos 'Nombre' y 'Identificación' según la imagen del reporte.
        df_referencia.rename(columns={'Nombre': 'Nombre_Ref', 'Identificación': 'Identificacion_Ref'}, inplace=True)
        
        # Estandarización de columnas clave para unión (Merge)
        df_extraido['Identificacion_Str'] = df_extraido['Identificacion_Ext'].astype(str).str.replace(r'\D', '', regex=True).str.strip() # Limpiar caracteres no numéricos
        
        df_referencia['Identificacion_Str'] = df_referencia['Identificacion_Ref'].astype(str).str.replace(r'\D', '', regex=True).str.strip()
        
        # 4. Realizar la comparación (LEFT JOIN en los datos extraídos)
        df_final = pd.merge(
            df_extraido,
            df_referencia[['Identificacion_Str', 'Nombre_Ref', 'Identificacion_Ref']],
            on='Identificacion_Str',
            how='left',
        ) # Eliminamos suffixes ya que los nombres ya están con '_Ext' y '_Ref'

        # 5. Generar columna de ESTADO
        df_final['Estado_Comparacion'] = 'NO COINCIDE (ID)'
        df_final.loc[df_final['Identificacion_Ref'].notna(), 'Estado_Comparacion'] = 'COINCIDE (ID)'
        
        # 6. Crear informe y guardarlo
        if not os.path.exists(OUTPUT_FOLDER):
            os.makedirs(OUTPUT_FOLDER)
            
        # Extraer el número de ficha del nombre del archivo de comparación
        ficha_match = re.search(r'Ficha-(\d+)', comparison_excel_path)
        ficha_number = ficha_match.group(1) if ficha_match else "DESCONOCIDA"
        
        output_filename = os.path.join(OUTPUT_FOLDER, f"informe_final_({ficha_number}).xlsx")

        # Seleccionar columnas para el informe
        columns_to_report = ['Identificacion_Ext', 'Nombre_Ext', 'Identificacion_Ref', 'Nombre_Ref', 'Estado_Comparacion']
        df_reporte = df_final[columns_to_report].rename(columns={
            'Identificacion_Ext': 'ID_Extraída',
            'Nombre_Ext': 'Nombre_Extraído',
            'Identificacion_Ref': 'ID_Referencia',
            'Nombre_Ref': 'Nombre_Referencia'
        })
        
        df_reporte.to_excel(output_filename, index=False)
        send_log(f"Informe de comparación generado exitosamente en: {output_filename}")
        return True

    except Exception as e:
        error_msg = f"Error durante la comparación de datos con Excel: {e}\n{traceback.format_exc()}"
        send_log(error_msg)
        return False

def get_most_recent_report():
    """Encuentra el archivo 'Reporte de inscritos' más reciente en la carpeta de descargas."""
    send_log("Buscando el reporte de inscritos más reciente...")
    try:
        reports_folder = os.path.join(os.path.dirname(__file__), '..', '..', 'descargas_reportes')
        if not os.path.exists(reports_folder):
            raise FileNotFoundError("La carpeta 'descargas_reportes' no existe.")

        report_files = [f for f in os.listdir(reports_folder) if f.startswith("Reporte-Ficha-") and f.endswith(".xls")]
        if not report_files:
            raise FileNotFoundError("No se encontraron archivos de 'Reporte-Ficha-' en la carpeta.")

        latest_report = max(report_files, key=lambda f: os.path.getmtime(os.path.join(reports_folder, f)))
        latest_report_path = os.path.join(reports_folder, latest_report)

        send_log(f"Reporte más reciente encontrado: {latest_report}")
        send_result({"success": True, "action": "get_most_recent_report", "report_path": latest_report_path})

    except FileNotFoundError as fnf_error:
        error_msg = str(fnf_error)
        send_log(error_msg)
        send_result({"success": False, "action": "get_most_recent_report", "error": error_msg})
    except Exception as e:
        error_msg = f"Error al buscar el reporte más reciente: {e}\n{traceback.format_exc()}"
        send_log(error_msg)
        send_result({"success": False, "action": "get_most_recent_report", "error": error_msg})

def get_most_recent_informe():
    """Encuentra el informe más reciente en la carpeta 'Output_Informes'."""
    send_log("Buscando el informe más reciente...")
    try:
        informes_folder = os.path.join(os.path.dirname(__file__), '..', '..', 'Output_Informes')
        if not os.path.exists(informes_folder):
            raise FileNotFoundError("La carpeta 'Output_Informes' no existe.")

        informe_files = [f for f in os.listdir(informes_folder) if f.startswith("informe_final_(") and f.endswith(").xlsx")]
        if not informe_files:
            raise FileNotFoundError("No se encontraron archivos de 'informe_final_(' en la carpeta.")

        latest_informe = max(informe_files, key=lambda f: os.path.getmtime(os.path.join(informes_folder, f)))
        latest_informe_path = os.path.join(informes_folder, latest_informe)

        send_log(f"Informe más reciente encontrado: {latest_informe}")
        send_result({"success": True, "action": "get_most_recent_informe", "informe_path": latest_informe_path})

    except FileNotFoundError as fnf_error:
        error_msg = str(fnf_error)
        send_log(error_msg)
        send_result({"success": False, "action": "get_most_recent_informe", "error": error_msg})
    except Exception as e:
        error_msg = f"Error al buscar el informe más reciente: {e}\n{traceback.format_exc()}"
        send_log(error_msg)
        send_result({"success": False, "action": "get_most_recent_informe", "error": error_msg})

if __name__ == "__main__":
    if len(sys.argv) < 2:
        send_result({"success": False, "error": "No se especificó ninguna acción. Uso: python script.py <action> [args...]"})
        sys.exit(1)

    action = sys.argv[1].lower()

    if action == "convert":
        if len(sys.argv) > 2:
            pdf_path = sys.argv[2]
            temp_images_path = TEMP_IMAGE_FOLDER
            send_log("Iniciando la conversión del PDF a imágenes...")
            convert_ok, _, num_images = convert_pdf_to_images(pdf_path, temp_images_path)
            if not convert_ok:
                sys.exit(1)
            
            send_log("Resecuenciando las imágenes...")
            resequence_ok, num_resequenced = _resequence_images_in_temp_folder(temp_images_path)
            
            if not resequence_ok:
                send_result({"success": False, "action": "convert", "error": "Error al resecuenciar las imágenes."})
            else:
                final_image_paths = [os.path.join(temp_images_path, f"procesar_{i + 1}.jpg") for i in range(num_resequenced)]
                send_result({
                    "success": True,
                    "action": "convert",
                    "image_folder": temp_images_path,
                    "message": f"{num_resequenced} imágenes generadas y resecuenciadas.",
                    "image_count": num_resequenced,
                    "image_paths": final_image_paths
                })
        else:
            send_result({"success": False, "action": "convert", "error": "No se proporcionó la ruta del PDF para la conversión."})

    elif action == "open_folder":
        if len(sys.argv) > 2:
            open_folder(sys.argv[2])
        else:
            send_result({"success": False, "action": "open_folder", "error": "No se proporcionó la ruta de la carpeta para abrir."})

    elif action == "delete_selected_images":
        if len(sys.argv) > 2:
            image_paths_to_delete = json.loads(sys.argv[2])
            delete_images(image_paths_to_delete)
        else:
            send_result({"success": False, "action": "delete_selected_images", "error": "No se proporcionaron las rutas de las imágenes a eliminar."})

    elif action == "process":
        if len(sys.argv) > 2:
            selected_image_paths = json.loads(sys.argv[2])
            process_with_mistral(selected_image_paths)
        else:
            send_result({"success": False, "action": "process", "error": "No se proporcionaron las rutas de las imágenes seleccionadas."})

    elif action == "compare":
        if len(sys.argv) > 3:
            extracted_data_json_path = sys.argv[2]
            comparison_excel_path = sys.argv[3]
            success = process_data_and_compare_excel(extracted_data_json_path, comparison_excel_path)
            send_result({"success": success, "action": "compare", "message": "Proceso de comparación finalizado."})
        else:
            send_result({"success": False, "action": "compare", "error": "Argumentos incompletos. Se requiere ruta del JSON extraído y ruta del Excel de comparación."})

    elif action == "get_most_recent_report":
        get_most_recent_report()

    elif action == "get_most_recent_informe":
        get_most_recent_informe()

    else:
        send_result({"success": False, "error": f"Acción desconocida: {action}"})
        sys.exit(1)