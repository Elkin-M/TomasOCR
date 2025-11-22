import os
import json
import traceback
from dotenv import load_dotenv
import shutil
import base64
import pandas as pd
import re
import fitz  # PyMuPDF
from mistralai import Mistral

load_dotenv()

class OCR_Module:
    """
    Servicio para procesar documentos PDF, extraer texto de imágenes con IA
    y comparar los resultados con un reporte de referencia.
    """
    def __init__(self, log_callback, ficha, pdf_path):
        self.log = log_callback
        self.ficha = ficha
        self.pdf_path = pdf_path
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        self.temp_image_folder = os.path.join(self.base_dir, 'temp_ocr_images')
        self.output_dir = os.path.join(self.base_dir, 'Output_Informes')
        self.inscritos_report_path = None
        os.makedirs(self.temp_image_folder, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)

    def set_inscritos_report_path(self, path):
        """Establece la ruta del reporte de inscritos para la comparación."""
        self.inscritos_report_path = path

    def preparar_imagenes_pdf(self):
        """Convierte el PDF a imágenes JPG y las guarda en la carpeta temporal."""
        self.log("Extrayendo imágenes del PDF...")
        if not self.pdf_path or not os.path.exists(self.pdf_path):
            raise FileNotFoundError(f"El archivo PDF no fue proporcionado o no existe: {self.pdf_path}")

        # Limpiar directorio temporal
        for item in os.listdir(self.temp_image_folder):
            os.remove(os.path.join(self.temp_image_folder, item))

        image_paths = []
        try:
            pdf_documento = fitz.open(self.pdf_path)
            for i, page in enumerate(pdf_documento):
                pix = page.get_pixmap(dpi=300)
                image_path = os.path.join(self.temp_image_folder, f"procesar_{i+1}.jpg")
                pix.save(image_path, "JPEG")
                image_paths.append(image_path)
            pdf_documento.close()
            self.log(f"Se extrajeron {len(image_paths)} imágenes del PDF.")
            return image_paths
        except Exception as e:
            self.log(f"Error al convertir PDF a imágenes: {e}", "error")
            raise

    def limpiar_imagenes_no_seleccionadas(self, all_image_paths, selected_paths):
        """Elimina las imágenes que no fueron seleccionadas por el usuario."""
        self.log("Limpiando imágenes no seleccionadas...")
        images_to_delete = set(all_image_paths) - set(selected_paths)
        for path in images_to_delete:
            try:
                os.remove(path)
            except OSError:
                self.log(f"No se pudo eliminar la imagen: {path}", "warn")
        self.log(f"Limpieza completada. Se mantienen {len(selected_paths)} imágenes.")

    def procesar_imagenes_y_comparar(self, selected_image_paths):
        """
        Procesa las imágenes seleccionadas con Mistral, compara los resultados
        con el reporte de inscritos y genera un informe final.
        """
        self.log("Iniciando procesamiento OCR y comparación...")
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key or api_key == 'TU_API_KEY':
            raise ValueError("La clave de API de Mistral no está configurada en el archivo .env.")
        if not self.inscritos_report_path or not os.path.exists(self.inscritos_report_path):
            raise FileNotFoundError("La ruta al reporte de inscritos no ha sido establecida o el archivo no existe.")

        # 1. Procesamiento con Mistral
        client = Mistral(api_key=api_key)
        model = os.getenv("MISTRAL_MODEL", "mistral-small-latest")
        text_prompt = (
            "Extrae la información del documento de identidad en formato JSON. "
            "Los campos son: 'nombre_completo', 'numero_identificacion', 'tipo_documento'. "
            "Valores para 'tipo_documento': 'Cedula de Ciudadania', 'Cedula de Extranjeria', 'Tarjeta de Identidad'. "
            "'numero_identificacion' debe ser un número sin puntos. El JSON debe ser válido."
        )

        ocr_results = []
        for image_path in selected_image_paths:
            self.log(f"Procesando imagen: {os.path.basename(image_path)}")
            with open(image_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
            
            messages = [{"role": "user", "content": [{"type": "text", "text": text_prompt}, {"type": "image_url", "image_url": f"data:image/jpeg;base64,{base64_image}"}]}]
            
            try:
                chat_response = client.chat.complete(model=model, messages=messages)
                content = chat_response.choices[0].message.content
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    parsed_json = json.loads(json_match.group(0))
                    ocr_results.append(parsed_json)
                else:
                    self.log(f"Respuesta no JSON para {os.path.basename(image_path)}", "warn")
            except Exception as e:
                self.log(f"Error de API para {os.path.basename(image_path)}: {e}", "error")

        if not ocr_results:
            raise ValueError("El procesamiento OCR no arrojó ningún resultado válido.")

        # 2. Comparación con el reporte de inscritos
        self.log("Comparando resultados de OCR con el reporte de inscritos...")
        df_extraido = pd.DataFrame(ocr_results)
        df_extraido.rename(columns={'nombre_completo': 'Nombre_Ext', 'numero_identificacion': 'Identificacion_Ext'}, inplace=True)
        df_extraido['Identificacion_Str'] = df_extraido['Identificacion_Ext'].astype(str).str.replace(r'\D', '', regex=True).str.strip()

        df_referencia = pd.read_excel(self.inscritos_report_path, header=5)
        df_referencia.columns = df_referencia.columns.str.strip()
        df_referencia.rename(columns={'Nombre': 'Nombre_Ref', 'Identificación': 'Identificacion_Ref'}, inplace=True)
        df_referencia['Identificacion_Str'] = df_referencia['Identificacion_Ref'].astype(str).str.replace(r'\D', '', regex=True).str.strip()

        df_final = pd.merge(df_extraido, df_referencia[['Identificacion_Str', 'Nombre_Ref', 'Identificacion_Ref']], on='Identificacion_Str', how='left')
        df_final['Estado_Comparacion'] = 'NO COINCIDE'
        df_final.loc[df_final['Identificacion_Ref'].notna(), 'Estado_Comparacion'] = 'COINCIDE'

        # 3. Guardar informe final
        output_filename = f"informe_final_({self.ficha}).xlsx"
        ocr_report_path = os.path.join(self.output_dir, output_filename)
        df_final.to_excel(ocr_report_path, index=False)
        self.log(f"Informe de comparación OCR guardado en: {output_filename}")

        aspirantes_coincidentes = df_final[df_final['Estado_Comparacion'] == 'COINCIDE'].to_dict('records')
        return aspirantes_coincidentes, ocr_report_path