import sys
import json
import traceback
import io
import os
import time

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
    # ... (El método __init__ es el mismo)
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

        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        os.makedirs(TEMP_IMAGE_FOLDER, exist_ok=True)


    # --- Métodos de Comunicación con el Frontend (CORRECCIÓN AQUÍ) ---

    def _send_log(self, message, level="info"):
        """Envía mensajes de log al frontend."""
        print(json.dumps({"type": "log", "message": message, "level": level}), flush=True)

    def _send_progress(self, step, message):
        """Envía el progreso al frontend."""
        progress = (step / self.total_steps) * 100
        print(json.dumps({"type": "progress", "step": step, "total_steps": self.total_steps, "progress": progress, "message": message}), flush=True)

    def _request_user_interaction(self, interaction_type, data):
        """
        Solicita interacción al usuario y espera respuesta. 
        Bloquea hasta recibir una respuesta válida o el cierre del canal.
        """
        self._send_log(f"🟡 Esperando acción del usuario para: {interaction_type}")
        print(json.dumps({"type": "user_interaction_required", "interaction": interaction_type, "data": data}), flush=True)
        
        while True:
            try:
                # Intenta leer una línea de sys.stdin
                response_line = sys.stdin.readline()
            except Exception as e:
                self._send_log(f"Error al leer de sys.stdin: {e}", "error")
                return {}

            # 🛑 PUNTO CRÍTICO CORREGIDO: Manejo de EOF (Canal Cerrado)
            if not response_line:  
                # Si readline() devuelve una cadena vacía, el canal de entrada se ha cerrado (EOF).
                self._send_log("El canal de comunicación con el frontend se cerró (EOF). Devolviendo respuesta vacía.", level="warn")
                # Devolvemos un diccionario vacío para que el proceso continúe asumiendo la cancelación.
                return {} 
            
            # Si la línea tiene contenido (no es solo un salto de línea)
            if response_line.strip():
                self._send_log(f"Respuesta recibida del frontend: {response_line.strip()}")
                try:
                    # Intenta decodificar el JSON de la línea recibida
                    return json.loads(response_line)
                except json.JSONDecodeError as e:
                    self._send_log(f"Error al decodificar la respuesta del frontend: {e}. Respuesta: '{response_line.strip()}'", "error")
                    # En caso de JSON inválido, ignoramos la línea y continuamos esperando.
                    continue
            
            # Añadir un pequeño sleep para evitar un bucle de alta carga si hay problemas de I/O
            time.sleep(0.1)


    # --- Métodos de Automatización (Setup y Login - Sin cambios) ---
    def _init_driver(self):
        # ... (código sin cambios)
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
        # ... (código sin cambios)
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
        # ... (código sin cambios)
        self.reportes_inscritos_service = Reportes_Module(self.driver, self.wait, self._send_log, self.ficha)
        self.ocr_service = OCR_Module(self._send_log, self.ficha, self.pdf_path)
        self.convocar_aspirantes_service = Convocar_Module(self.driver, self.wait, self._send_log)
        self._send_log("Servicios especializados inicializados.")

    # --- Lógica de los Pasos del Proceso (Delegación - Sin cambios) ---

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
        self._send_progress(3, "Extrayendo imágenes del PDF para OCR...")
        image_paths = self.ocr_service.preparar_imagenes_pdf()
        
        # Llama al método corregido
        response = self._request_user_interaction("ocr_image_selection", {"image_paths": image_paths})
        
        selected_paths = response.get("selected_images", [])
        if not selected_paths:
            self._send_log("El usuario no seleccionó ninguna imagen o la comunicación se cerró antes. Se omitirán los pasos de OCR.", "warn")
            selected_paths = [] 
        
        self.ocr_service.limpiar_imagenes_no_seleccionadas(image_paths, selected_paths)
        self._send_log(f"✅ Usuario seleccionó {len(selected_paths)} imágenes para OCR.")
        return selected_paths

    def step_4_ocr_processing(self, selected_image_paths):
        self._send_progress(4, "Procesando imágenes con IA y comparando...")
        self.ocr_service.set_inscritos_report_path(self.inscritos_report_path)
        coincidentes, self.ocr_report_path = self.ocr_service.procesar_imagenes_y_comparar(selected_image_paths)
        self._send_log(f"✅ Informe de comparación OCR guardado en: {self.ocr_report_path}")
        return coincidentes

    def step_5_convocar_aspirantes(self, aspirantes):
        self._send_progress(5, "Esperando confirmación de aspirantes a convocar...")
        if not aspirantes:
            self._send_log("No se encontraron aspirantes coincidentes para convocar.", "warn")
            return []

        response = self._request_user_interaction("convocar_aspirantes_confirmation", {"aspirantes": aspirantes})
        confirmed_aspirants = response.get("confirmed_aspirants", [])

        if not confirmed_aspirants:
            self._send_log("Usuario no confirmó ningún aspirante para la convocatoria.", "warn")
            return []
        
        self._send_log(f"Usuario confirmó {len(confirmed_aspirants)} aspirantes. Procediendo a convocar...")
        self.convocar_aspirantes_service.navegar_y_convocar(confirmed_aspirants)
        self._send_log("✅ Convocatoria de aspirantes completada.")
        return confirmed_aspirants

    def step_6_fin_matricula_confirmation(self):
        self._send_progress(6, "Esperando confirmación para finalizar matrícula...")
        response = self._request_user_interaction("fin_matricula_confirmation", {})
        return response.get("confirm", False)

    def step_7_fin_matricula(self):
        self._send_progress(7, "Iniciando proceso de fin de matrícula...")
        self._send_log("Navegando a la sección de fin de matrícula (simulado)...")
        time.sleep(3)
        self._send_log("Confirmando y finalizando la matrícula (simulado)...")
        time.sleep(5)
        self._send_log("✅ Proceso de Fin de Matrícula completado (simulado).")

    def execute(self):
        """Orquesta la ejecución de todos los pasos del proceso de automatización."""
        try:
            self._send_progress(0, "Iniciando automatización...")
            self._init_driver()
            self._login_sofia_plus()
            self._init_services() 

            self.step_1_sgs_report()
            self.step_2_inscritos_report()
            
            selected_images = self.step_3_ocr_preprocessing()

            if selected_images:
                coincidentes = self.step_4_ocr_processing(selected_images)
                convocados = self.step_5_convocar_aspirantes(coincidentes)

                if convocados:
                    if self.step_6_fin_matricula_confirmation():
                        self.step_7_fin_matricula()
                    else:
                        self._send_log("⏩ Proceso de Fin de Matrícula omitido por decisión del usuario.")
                else:
                    self._send_log("No hubo aspirantes convocados, omitiendo fin de matrícula.", "info")
            else:
                self._send_log("Omitiendo los pasos de OCR y convocatoria porque no se seleccionaron imágenes.", "info")

            self._send_progress(self.total_steps, "🎉 ¡Automatización completada con éxito!")
            print(json.dumps({"success": True, "message": "Proceso finalizado."}), flush=True)

        except Exception as e:
            error_message = f"❌ Error crítico en la automatización: {e}\n{traceback.format_exc()}"
            self._send_log(error_message, level="error")
            print(json.dumps({"success": False, "error": str(e)}), flush=True)
        finally:
            if self.driver:
                self._send_log("Cerrando el navegador...")
                self.driver.quit()

if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1].lower() == 'execute':
        ficha_arg = sys.argv[2]
        pdf_path_arg = sys.argv[3] if len(sys.argv) > 3 else None
        
        service = AutoService(ficha_arg, pdf_path_arg)
        service.execute()
    else:
        print(json.dumps({"success": False, "error": "Argumentos insuficientes."}, flush=True))