import sys
import json
import traceback
import io
import os
import time
import threading
import queue
import base64

from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- Importación de Servicios ---
# Asumimos que estos servicios están disponibles:
import sgs_service
from reportes_inscritos import Reportes_Module
from ocr_service import OCR_Module
from convocar_aspirantes_service import Convocar_Module

# --- Configuración Inicial ---
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
load_dotenv()

# --- Rutas y Constantes ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
DOWNLOAD_DIR = os.path.join(BASE_DIR, 'descargas_reportes')
OUTPUT_DIR = os.path.join(BASE_DIR, 'Output_Informes')
TEMP_IMAGE_FOLDER = os.path.join(BASE_DIR, 'temp_ocr_images')
# Asegúrate de que esta ruta sea la correcta para tu entorno:
CHROMEDRIVER_PATH = r"D:\Users\Lenovo\Documents\chrome-win\chromedriver.exe" 

class AutoService:
    def __init__(self, ficha, pdf_path):
        self.ficha = ficha
        self.pdf_path = pdf_path
        self.driver = None
        self.wait = None
        self.total_steps = 7 

        self.inscritos_report_path = None
        self.ocr_report_path = None

        self.sgs_service = None
        self.reportes_inscritos_service = None
        self.ocr_service = None
        self.convocar_aspirantes_service = None

        # ✅ NUEVO: Cola para manejar respuestas de stdin en un thread separado
        self.response_queue = queue.Queue()
        self.stdin_reader_active = True
        self._start_stdin_reader()

        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        os.makedirs(TEMP_IMAGE_FOLDER, exist_ok=True)

    # --- ✅ NUEVO: Thread para leer stdin de forma no bloqueante ---
    def _start_stdin_reader(self):
        """Inicia un thread en background que lee stdin continuamente."""
        def read_stdin_loop():
            self._send_log("🔄 Thread de lectura de stdin iniciado", "debug")
            while self.stdin_reader_active:
                try:
                    line = sys.stdin.readline()
                    
                    if not line:  # EOF
                        self._send_log("⚠️ EOF detectado en stdin - Canal cerrado", "warn")
                        self.response_queue.put({"_eof": True})
                        break
                    
                    if line.strip():
                        self._send_log(f"📥 Línea recibida de stdin: {line.strip()}", "debug")
                        try:
                            data = json.loads(line)
                            self.response_queue.put(data)
                        except json.JSONDecodeError as e:
                            self._send_log(f"❌ Error parseando JSON de stdin: {e}", "error")
                            
                except Exception as e:
                    self._send_log(f"❌ Error crítico en stdin reader: {e}", "error")
                    self.response_queue.put({"_error": str(e)})
                    break
                    
            self._send_log("🛑 Thread de lectura de stdin finalizado", "debug")
        
        reader_thread = threading.Thread(target=read_stdin_loop, daemon=True)
        reader_thread.start()
        self._send_log("✅ Thread de stdin reader iniciado correctamente", "debug")

    # --- Métodos de Comunicación con el Frontend (CORREGIDO) ---

    def _send_log(self, message, level="info"):
        """Envía mensajes de log al frontend."""
        print(json.dumps({"type": "log", "message": message, "level": level}), flush=True)

    def _send_progress(self, step, message):
        """Envía el progreso al frontend."""
        progress = (step / self.total_steps) * 100
        print(json.dumps({"type": "progress", "step": step, "total_steps": self.total_steps, "progress": progress, "message": message}), flush=True)

    def _request_user_interaction(self, interaction_type, data, timeout=300):
        """
        ✅ CORREGIDO: Solicita interacción al usuario con TIMEOUT y manejo robusto.
        
        Args:
            interaction_type: Tipo de interacción ('ocr_image_selection', etc.)
            data: Datos a enviar al frontend
            timeout: Tiempo máximo de espera en segundos (default: 5 minutos)
        
        Returns:
            dict: Respuesta del usuario o {} si timeout/error
        """
        self._send_log(f"🟡 Solicitando interacción del usuario: {interaction_type}")
        # Se ha truncado el log de datos para evitar URLs de datos muy largas
        data_to_log = data.copy()
        if "image_data_urls" in data_to_log:
            data_to_log["image_data_urls"] = f"[{len(data_to_log['image_data_urls'])} URLs]"
        
        self._send_log(f"📤 Datos enviados: {json.dumps(data_to_log)}", "debug")
        
        # Enviar solicitud al frontend
        print(json.dumps({
            "type": "user_interaction_required", 
            "interaction": interaction_type, 
            "data": data
        }), flush=True)
        
        start_time = time.time()
        iteration = 0
        
        # ✅ Limpiar cola antes de esperar nueva respuesta
        while not self.response_queue.empty():
            try:
                self.response_queue.get_nowait()
            except queue.Empty:
                break
        
        while True:
            iteration += 1
            elapsed = time.time() - start_time
            
            # ⏱️ Verificar timeout
            if elapsed > timeout:
                self._send_log(f"⏱️ TIMEOUT ({timeout}s) esperando respuesta para '{interaction_type}'", "error")
                return {}
            
            # 📊 Log cada 10 segundos para mostrar que está esperando
            if iteration % 100 == 0:  # Cada 10 segundos (con sleep de 0.1)
                self._send_log(f"⏳ Esperando respuesta del usuario... ({elapsed:.1f}s / {timeout}s)", "info")
            
            # 📥 Intentar obtener respuesta de la cola (timeout de 0.5s para no bloquear)
            try:
                response = self.response_queue.get(timeout=0.5)
                
                # Verificar si es un mensaje especial de error/EOF
                if isinstance(response, dict):
                    if response.get("_eof"):
                        self._send_log("⚠️ Canal de comunicación cerrado (EOF)", "warn")
                        return {}
                    
                    if response.get("_error"):
                        self._send_log(f"❌ Error en comunicación: {response['_error']}", "error")
                        return {}
                    
                    # ✅ Respuesta válida recibida
                    self._send_log(f"✅ Respuesta recibida para '{interaction_type}': {json.dumps(response)[:200]}...", "debug")
                    return response
                
            except queue.Empty:
                # No hay respuesta aún, continuar esperando
                continue
            except Exception as e:
                self._send_log(f"❌ Error obteniendo respuesta de la cola: {e}", "error")
                return {}
            
            time.sleep(0.1)

    # --- Métodos de Automatización (Setup y Login) ---
    def _init_driver(self):
        self._send_log("Configurando el navegador Chrome...")
        chrome_options = Options()
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--disable-notifications")
        prefs = {
            "download.default_directory": DOWNLOAD_DIR,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        chrome_options.add_experimental_option("prefs", prefs)
        try:
            service = Service(CHROMEDRIVER_PATH)
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.wait = WebDriverWait(self.driver, 20)
            self._send_log("✅ Navegador iniciado correctamente.")
        except Exception as e:
            raise RuntimeError(f"No se pudo iniciar ChromeDriver. Asegúrate de que la ruta es correcta. Error: {e}")

    def _login_sofia_plus(self):
        self._send_log("🌐 Navegando a SOFIA Plus...")
        self.driver.get("http://senasofiaplus.edu.co/sofia-public/")
        time.sleep(3)
        try:
            self.driver.find_element(By.XPATH, "//a[contains(text(), 'Ingresar')]").click()
            time.sleep(2)
        except Exception:
            self._send_log("🟡 No se encontró el botón 'Ingresar', puede que ya estemos en el formulario.")

        self._send_log("🔐 Realizando inicio de sesión...")
        self.wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'registradoBox1')))
        self.wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/form/div/div/div/div[2]/input"))).send_keys("1050962935")
        self.wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/form/div/div/div/div[3]/input"))).send_keys("PapaJose92805331050*")
        self.wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/form/div/div/div/div[7]/input"))).click()
        time.sleep(5)
        
        if "para ingresar a la aplicaci" in self.driver.page_source.lower():
            raise RuntimeError("Fallo en el inicio de sesión. Verifica las credenciales.")
        
        self._send_log("✅ Inicio de sesión completado.")
        self.driver.switch_to.default_content()
        self._send_log("Seleccionando rol 'Apoyo Administrativo'...")
        self.wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="seleccionRol:roles"]/option[4]'))).click()
        time.sleep(1)
        self._send_log("✅ Rol seleccionado.")
        self.wait.until(EC.invisibility_of_element_located((By.CLASS_NAME, "blockUI")))
        self._send_log("✅ Página cargada.")

    def _init_services(self):
        self.reportes_inscritos_service = Reportes_Module(self.driver, self.wait, self._send_log, self.ficha)
        self.ocr_service = OCR_Module(self._send_log, self.ficha, self.pdf_path)
        self.convocar_aspirantes_service = Convocar_Module(self.driver, self.wait, self._send_log)
        self._send_log("Servicios especializados inicializados.")

    # --- Lógica de los Pasos del Proceso ---

    def step_1_sgs_report(self):
        self._send_progress(1, "Iniciando consulta de estado SGS...")
        sgs_service.navegacion_principal(self.driver)
        sgs_service.consultar_ficha(self.driver, self.ficha)
        self._send_log("✅ Consulta SGS completada.")

    def step_2_inscritos_report(self):
        self._send_progress(2, "Generando reporte de inscritos...")
        self.inscritos_report_path = self.reportes_inscritos_service.generar_y_descargar_reporte()
        if not self.inscritos_report_path or not os.path.exists(self.inscritos_report_path):
            raise FileNotFoundError("El servicio de reportes no devolvió una ruta de archivo válida.")
        self._send_log(f"✅ Reporte de inscritos generado en: {self.inscritos_report_path}")

    def step_3_ocr_preprocessing(self):
        """✅ CORREGIDO: Envía imágenes como Data URLs para el frontend."""
        self._send_progress(3, "Extrayendo imágenes del PDF para OCR...")
        
        try:
            image_paths = self.ocr_service.preparar_imagenes_pdf()
            self._send_log(f"📸 {len(image_paths)} imágenes extraídas del PDF", "debug")
            
            if not image_paths:
                self._send_log("⚠️ No se extrajeron imágenes del PDF", "warn")
                return []

            # Convertir imágenes a Data URLs para el frontend
            image_data_urls = []
            for img_path in image_paths:
                with open(img_path, "rb") as image_file:
                    encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                    image_data_urls.append(f"data:image/jpeg;base64,{encoded_string}")
            
            # Solicitar selección al usuario enviando las Data URLs
            self._send_log("📤 Enviando imágenes al frontend para selección...")
            response = self._request_user_interaction(
                "ocr_image_selection", 
                {
                    "image_data_urls": image_data_urls,
                    "original_paths": image_paths  # Enviar también las rutas originales
                },
                timeout=300
            )
            
            self._send_log(f"📦 Respuesta recibida: {response}", "debug")
            
            # El frontend debe devolver las *rutas originales* de las imágenes seleccionadas
            selected_paths = response.get("selected_images", [])
            
            if not selected_paths:
                self._send_log("⚠️ El usuario no seleccionó ninguna imagen. Se omitirán los pasos de OCR.", "warn")
                # Limpiar todas las imágenes si no se seleccionó ninguna
                self.ocr_service.limpiar_imagenes_no_seleccionadas(image_paths, [])
                return []
            
            self._send_log(f"✅ Usuario seleccionó {len(selected_paths)} imágenes para OCR.")
            # Limpiar solo las imágenes no seleccionadas
            self.ocr_service.limpiar_imagenes_no_seleccionadas(image_paths, selected_paths)
            return selected_paths
            
        except Exception as e:
            self._send_log(f"❌ Error en step_3_ocr_preprocessing: {e}", "error")
            self._send_log(traceback.format_exc(), "debug")
            return []

    def step_4_ocr_processing(self, selected_image_paths):
        self._send_progress(4, "Procesando imágenes con IA y comparando...")
        self.ocr_service.set_inscritos_report_path(self.inscritos_report_path)
        coincidentes, self.ocr_report_path = self.ocr_service.procesar_imagenes_y_comparar(selected_image_paths)
        
        self._send_log(f"✅ Informe de comparación OCR guardado en: {self.ocr_report_path}")
        
        return coincidentes

    def step_4_5_confirm_convocatoria(self, comparison_data):
        """
        Nuevo paso intermedio: Esperar confirmación del usuario después de ver
        la vista previa de comparación.
        
        Returns:
            list: Lista de aspirantes confirmados para convocar
        """
        self._send_progress(4.5, "Esperando confirmación de convocatoria...")
        
        if comparison_data['total_matches'] == 0:
            self._send_log("No hay aspirantes con coincidencia para convocar.", "warn")
            return []
        
        # Solicitar confirmación al usuario
        response = self._request_user_interaction(
            "comparison_preview",
            comparison_data,
            timeout=300
        )
        
        confirmed_aspirants_raw = response.get("confirmed_aspirants", [])
        
        if not confirmed_aspirants_raw:
            self._send_log("Usuario no confirmó ningún aspirante.", "warn")
            return []
        
        self._send_log(f"✅ Usuario confirmó {len(confirmed_aspirants_raw)} aspirantes.")
        return confirmed_aspirants_raw

    def step_5_convocar_aspirantes(self, aspirantes):
        """
        NOTA: Este paso ya NO solicita confirmación aquí.
        La confirmación se hace en el nuevo paso intermedio.
        """
        self._send_progress(5, "Convocando aspirantes confirmados...")
        
        if not aspirantes:
            self._send_log("No hay aspirantes para convocar.", "warn")
            return []
        
        self._send_log(f"Convocando {len(aspirantes)} aspirantes...")
        self.convocar_aspirantes_service.navegar_y_convocar(aspirantes)
        self._send_log("✅ Convocatoria de aspirantes completada.")
        return aspirantes

    def step_6_fin_matricula_confirmation(self):
        self._send_progress(6, "Esperando confirmación para finalizar matrícula...")
        response = self._request_user_interaction(
            "fin_matricula_confirmation", 
            {},
            timeout=300
        )
        return response.get("confirm", False)

    def step_7_fin_matricula(self):
        self._send_progress(7, "Iniciando proceso de fin de matrícula...")
        self._send_log("Navegando a la sección de fin de matrícula (simulado)...")
        time.sleep(3)
        self._send_log("Confirmando y finalizando la matrícula (simulado)...")
        time.sleep(5)
        self._send_log("✅ Proceso de Fin de Matrícula completado (simulado).")

    def execute(self):
        """✅ Orquesta la ejecución con el nuevo paso de vista previa."""
        try:
            self._send_progress(0, "Iniciando automatización...")
            self._init_driver()
            self._login_sofia_plus()
            self._init_services() 

            self.step_1_sgs_report()
            self.step_2_inscritos_report()
            
            self._send_log("🔄 Iniciando paso 3: Preprocesamiento OCR...")
            selected_images = self.step_3_ocr_preprocessing()
            self._send_log(f"📊 Resultado step_3: {len(selected_images) if selected_images else 0} imágenes seleccionadas")

            if selected_images:
                self._send_log(f"✅ Continuando con OCR de {len(selected_images)} imágenes...")
                
                # Paso 4: Procesar OCR y obtener coincidencias
                coincidentes = self.step_4_ocr_processing(selected_images)
                
                # ✅ NUEVO: Paso 4.5: Mostrar vista previa y esperar confirmación
                comparison_data = self._prepare_comparison_preview(coincidentes)
                confirmed_aspirants = self.step_4_5_confirm_convocatoria(comparison_data)
                
                # Paso 5: Convocar aspirantes (YA confirmados)
                if confirmed_aspirants:
                    convocados = self.step_5_convocar_aspirantes(confirmed_aspirants)
                    
                    # Paso 6 y 7: Fin de matrícula
                    if convocados:
                        if self.step_6_fin_matricula_confirmation():
                            self.step_7_fin_matricula()
                        else:
                            self._send_log("⏩ Proceso de Fin de Matrícula omitido por decisión del usuario.")
                else:
                    self._send_log("No hubo aspirantes confirmados, omitiendo convocatoria.", "info")
            else:
                self._send_log("⏭️ Omitiendo OCR y convocatoria (no se seleccionaron imágenes).", "info")

            self._send_progress(self.total_steps, "🎉 ¡Automatización completada con éxito!")
            print(json.dumps({"success": True, "message": "Proceso finalizado."}), flush=True)

        except Exception as e:
            error_message = f"❌ Error crítico: {e}\n{traceback.format_exc()}"
            self._send_log(error_message, level="error")
            print(json.dumps({"success": False, "error": str(e)}), flush=True)
        finally:
            self.stdin_reader_active = False
            if self.driver:
                self._send_log("Cerrando el navegador...")
                self.driver.quit()

    def _prepare_comparison_preview(self, coincidentes):
        """
        Prepara los datos de comparación para enviar al frontend.
        
        Args:
            coincidentes: Lista de diccionarios con los aspirantes coincidentes
            
        Returns:
            dict: Datos estructurados para el frontend
        """
        if not coincidentes:
            return {
                "total_images_processed": 0,
                "total_matches": 0,
                "matches": [],
                "report_path": self.ocr_report_path
            }
        
        # Calcular estadísticas
        matches_with_scores = []
        for asp in coincidentes:
            # Calcular un score de confianza basado en los datos disponibles
            confidence = 100  # Por defecto alta confianza
            
            # Reducir confianza si faltan datos
            if not asp.get('Identificacion_Ext'):
                confidence -= 20
            if not asp.get('Nombre_Ext'):
                confidence -= 20
            if not asp.get('Nombre_Ref'):
                confidence -= 10
                
            matches_with_scores.append({
                "nombre_extraido": asp.get('Nombre_Ext', 'N/A'),
                "identificacion_extraida": asp.get('Identificacion_Ext', 'N/A'),
                "nombre_referencia": asp.get('Nombre_Ref', 'N/A'),
                "identificacion_referencia": asp.get('Identificacion_Ref', 'N/A'),
                "confidence": confidence,
                "raw_data": asp  # Mantener datos originales para convocatoria
            })
        
        return {
            "total_images_processed": len(self.ocr_service.resultados_ocr) if hasattr(self.ocr_service, 'resultados_ocr') else 0,
            "total_matches": len(matches_with_scores),
            "matches": matches_with_scores,
            "report_path": self.ocr_report_path
        }

    def _send_comparison_preview(self, comparison_data):
        """Envía los datos de comparación al frontend para vista previa."""
        self._send_log(f"📊 Enviando vista previa de comparación: {comparison_data['total_matches']} coincidencias encontradas")
        
        print(json.dumps({
            "type": "comparison_preview",
            "data": comparison_data
        }), flush=True)

if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1].lower() == 'execute':
        ficha_arg = sys.argv[2]
        pdf_path_arg = sys.argv[3] if len(sys.argv) > 3 else None
        
        service = AutoService(ficha_arg, pdf_path_arg)
        service.execute()
    else:
        print(json.dumps({"success": False, "error": "Argumentos insuficientes."}), flush=True)