from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import time
import json
import sys
import traceback
import io
import os

# IMPORTANTE: Configurar encoding UTF-8 para Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def log_message(message):
    """Envía mensajes de log al frontend en formato JSON."""
    print(json.dumps({"type": "log", "message": message}), flush=True)

def inicializar_driver():
    """Inicializa el driver de Chrome"""
    # Esta función no se usa directamente en generar_reporte, pero se mantiene por contexto.
    try:
        chrome_options = Options()
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_experimental_option("detach", True)
        
        log_message("Iniciando ChromeDriver...")
        # NOTA: Asegúrate de que esta ruta sea la correcta en el entorno de ejecución
        service = Service(r"D:\\Users\\Lenovo\\Documents\\chrome-win\\chromedriver.exe")
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        log_message("Navegando a SOFIA Plus...")
        driver.get("http://senasofiaplus.edu.co/sofia-public/")
        time.sleep(3)
        
        log_message("[OK] Driver inicializado correctamente")
        return driver
    except Exception as e:
        log_message(f"[ERROR] Error al inicializar el driver: {e}")
        traceback.print_exc()
        return None

def hacer_clic_ingresar(driver):
    """Buscar y hacer clic en el botón de Ingresar"""
    try:
        boton_ingresar = driver.find_element(By.XPATH, "//a[contains(text(), 'Ingresar')]")
        boton_ingresar.click()
        time.sleep(2)
        log_message("[OK] Clic en boton Ingresar exitoso")
        return True
    except Exception as e:
        log_message(f"[WARN] No se encontro el boton Ingresar (continuando): {e}")
        return False

def iniciar_sesion(driver):
    """Inicia sesión en el sistema Sofia Plus"""
    # **REEMPLAZAR CON CREDENCIALES REALES O PARÁMETROS DE ENTRADA**
    usuario = "1050962935" 
    contrasena = "PapaJose92805331050*"
    
    try:
        driver.switch_to.default_content()
        driver.switch_to.frame("registradoBox1")
        
        input_usuario = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "/html/body/form/div/div/div/div[2]/input"))
        )
        input_usuario.send_keys(usuario)
        
        input_contrasena = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "/html/body/form/div/div/div/div[3]/input"))
        )
        input_contrasena.send_keys(contrasena)
        
        boton_login = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "/html/body/form/div/div/div/div[7]/input"))
        )
        boton_login.click()
        time.sleep(5)
        log_message("[OK] Inicio de sesion exitoso")
        return True
    except Exception as e:
        log_message(f"[WARN] Error al iniciar sesion (continuando): {e}")
        return False

def generar_reporte(ficha):
    driver = None
    aprendices = []
    try:
        log_message(f"Iniciando proceso para ficha: {ficha}")
        
        # Configurar opciones de Chrome para descarga automática
        chrome_options = Options()
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_experimental_option("detach", True)
        
        download_dir = os.path.abspath("descargas_reportes")
        os.makedirs(download_dir, exist_ok=True)
        prefs = {
            "download.default_directory": download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        # NOTA: Asegúrate de que esta ruta sea la correcta
        service = Service(r"D:\\Users\\Lenovo\\Documents\\chrome-win\\chromedriver.exe")
        driver = webdriver.Chrome(service=service, options=chrome_options)
        wait = WebDriverWait(driver, 15)

        # 1. Ir a la página de inicio de SOFIA Plus
        log_message("Navegando a SOFIA Plus...")
        driver.get("http://senasofiaplus.edu.co/sofia-public/")
        time.sleep(3)

        # 2. Click en "Ingresar"
        hacer_clic_ingresar(driver)

        # 3. Ingresar credenciales
        if not iniciar_sesion(driver):
            log_message("generar_reporte: login failed")
            return

        # 4. Seleccionar rol y navegar al módulo de reportes
        driver.switch_to.default_content()
        log_message("Seleccionando rol...")
        # Asumiendo que option[4] es 'Apoyo Administrativo'
        wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="seleccionRol:roles"]/option[4]'))).click()
        time.sleep(4)
        
        # Navegación al reporte
        driver.switch_to.default_content()
        log_message("Navegando al módulo de reportes...")
        # Gestión de Reportes
        wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="side-menu"]/li[4]/a'))).click()
        # Reportes de Inscripción
        wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="side-menu"]/li[4]/ul/li[1]/a'))).click()
        # Generar reporte de inscripción
        elemento = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="3230Opcion"]')))
        driver.execute_script("arguments[0].click();", elemento)
        time.sleep(3)
        log_message("Llegada a 'Generar reporte de inscripción'.")
        
        # **AÑADIDO**: Espera para asegurar que no hay overlays después de la navegación
        try:
            log_message("Esperando a que el contenedor principal sea visible...")
            wait.until(EC.visibility_of_element_located((By.ID, "frmPrincipal"))) 
        except:
            log_message("Advertencia: El contenedor principal tardó en cargar o no se encontró el ID 'frmPrincipal'.")
        time.sleep(2) # Pausa de seguridad extra

        # 5. Lógica robusta para buscar ficha y descargar reporte
        log_message("Iniciando lógica de búsqueda y descarga...")

        # 5.1. Cambiar al iframe 'contenido'
        try:
            log_message("Cambiando al iframe 'contenido'...")
            wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "contenido")))
            time.sleep(1)
            log_message("Cambio a iframe 'contenido' exitoso.")
        except Exception as e:
            log_message(f"Error al cambiar al iframe 'contenido': {e}")
            raise

        # 5.2. Hacer clic en el icono de filtro para abrir el modal
        try:
            log_message("Haciendo clic en el icono de filtros para abrir modal (Solución ElementClickIntercepted)...")
            icono_filtros_xpath = '/html/body[1]/div[2]/form/div[1]/fieldset/table/tbody/tr[1]/td[2]/table/tbody/tr/td[2]/a/img'
            
            # **MODIFICACIÓN CLAVE**: Usar element_to_be_clickable
            icono_filtros = wait.until(
                EC.element_to_be_clickable((By.XPATH, icono_filtros_xpath))
            )
            
            # Usar JavaScript para forzar el clic y evitar intercepciones
            driver.execute_script("arguments[0].click();", icono_filtros)
            
            log_message("Clic en icono de filtros ejecutado con JS.")
            time.sleep(2)
        except Exception as e:
            log_message(f"Error al hacer clic en el icono de filtros: {e}")
            raise

        # 5.3. Cambiar al iframe del modal
        try:
            log_message("Esperando y cambiando al iframe del modal...")
            modal_iframe_id = 'modalDialogContentviewDialog2'
            iframe_element = wait.until(EC.presence_of_element_located((By.ID, modal_iframe_id)))
            driver.switch_to.frame(iframe_element)
            log_message("Cambio a iframe del modal exitoso.")
        except Exception as e:
            log_message(f"Error al cambiar al iframe del modal: {e}")
            raise

        # 5.4. Ingresar ficha, buscar y seleccionar resultado en el modal
        try:
            log_message(f"Buscando campo para ingresar ficha: {ficha}")
            input_ficha_xpath = '//*[@id="form:codigoFichaITX"]'
            input_ficha = wait.until(EC.presence_of_element_located((By.XPATH, input_ficha_xpath)))
            input_ficha.clear()
            input_ficha.send_keys(ficha)
            log_message("Ficha ingresada en el campo.")

            log_message("Haciendo clic en el botón de búsqueda del modal...")
            search_button_modal_xpath = '//*[@id="form:buscarCBT"]'
            # También usamos element_to_be_clickable aquí para mayor seguridad
            search_button = wait.until(EC.element_to_be_clickable((By.XPATH, search_button_modal_xpath)))
            driver.execute_script("arguments[0].click();", search_button)
            log_message("Clic con JavaScript en búsqueda del modal ejecutado.")
            time.sleep(3)

            log_message("Seleccionando el primer resultado de la ficha...")
            first_result_xpath = '//*[@id="form:dtFichas:0:imgSelec"]'
            first_result = wait.until(EC.element_to_be_clickable((By.XPATH, first_result_xpath)))
            driver.execute_script("arguments[0].click();", first_result)
            log_message("Primer resultado seleccionado con JavaScript. El modal debería cerrarse.")
            time.sleep(3)
        except Exception as e:
            log_message(f"Error al buscar y seleccionar la ficha en el modal: {e}")
            raise

        # 5.5. Seleccionar tipo de reporte y descargar
        try:
            log_message("Regresando al iframe 'contenido' principal...")
            driver.switch_to.default_content()
            # Volvemos al iframe principal de la aplicación
            wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "contenido"))) 

            log_message("Seleccionando opción del desplegable de reportes...")
            # Opción: Inscritos por tipo de identificación
            dropdown_option_xpath = '//*[@id="opcionesInscritos"]/option[2]' 
            wait.until(EC.element_to_be_clickable((By.XPATH, dropdown_option_xpath))).click()
            time.sleep(1)

            log_message("Haciendo clic en el botón 'Consultar' principal...")
            main_consult_button_xpath = '//*[@id="frmPrincipal:cmdlnkSearch"]'
            wait.until(EC.element_to_be_clickable((By.XPATH, main_consult_button_xpath))).click()
            time.sleep(5)

            log_message("Haciendo clic en el botón 'Descargar'...")
            download_button_xpath = '//*[@id="frmPrincipal:btnGenerar"]'
            wait.until(EC.element_to_be_clickable((By.XPATH, download_button_xpath))).click()
            log_message("Descarga iniciada.")
            time.sleep(10)

            # Renombrar el archivo descargado
            log_message("Renombrando el archivo descargado...")
            try:
                list_of_files = [os.path.join(download_dir, f) for f in os.listdir(download_dir)]
                if not list_of_files:
                    raise FileNotFoundError("No se encontraron archivos en el directorio de descargas.")
                
                latest_file = max(list_of_files, key=os.path.getctime)
                log_message(f"Archivo más reciente encontrado: {os.path.basename(latest_file)}")

                _, file_extension = os.path.splitext(latest_file)
                new_file_name = f"Reporte-Ficha-{ficha}{file_extension}"
                new_file_path = os.path.join(download_dir, new_file_name)

                if os.path.exists(new_file_path):
                    os.remove(new_file_path)
                    
                os.rename(latest_file, new_file_path)
                log_message(f"Archivo renombrado a: {new_file_name}")
            except Exception as rename_error:
                log_message(f"Advertencia: No se pudo renombrar el archivo. Error: {rename_error}")

        except Exception as e:
            log_message(f"Error al generar o descargar el reporte final: {e}")
            raise
        
        log_message("Proceso de descarga de reporte finalizado.")

    except Exception as e:
        error_msg = f"""Error: {str(e)}
{traceback.format_exc()} """
        log_message(error_msg)

    finally:
        if driver:
            if __name__ == "__main__":
                print("Proceso finalizado. Presiona Enter para cerrar el navegador...")
                input()
                driver.quit()
            else:
                # La opción 'detach' mantiene la ventana abierta en la aplicación principal.
                pass

        result = {
            "success": True,
            "data": aprendices
        }
        if __name__ == "__main__":
            print(result)
        else:
            print(json.dumps(result), flush=True)

if len(sys.argv) > 2 and sys.argv[1] == 'execute':
    ficha = sys.argv[2]
    generar_reporte(ficha)
elif __name__ == "__main__":
    ficha = "2826917" # Valor predeterminado para pruebas
    if len(sys.argv) > 1:
        ficha = sys.argv[1]
    generar_reporte(ficha)