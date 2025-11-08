from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import json
import sys
import traceback
import os
import shutil
import pandas as pd

def log_message(message):
    print(json.dumps({"type": "log", "message": message}), flush=True)

def read_excel_data(file_path):
    try:
        df = pd.read_excel(file_path)
        data = df.to_dict('records')
        return data
    except Exception as e:
        log_message(f"Error leyendo Excel: {e}")
        return []

def ensure_dir_exists(path):
    if not os.path.exists(path):
        os.makedirs(path)
        log_message(f"Directorio creado: {path}")
    return path

def get_download_dir():
    project_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    downloads_dir = os.path.join(project_path, 'descargas_reportes')
    ensure_dir_exists(downloads_dir)
    return downloads_dir

def wait_for_file(downloads_dir, timeout=30):
    start_time = time.time()
    while time.time() - start_time < timeout:
        for file in os.listdir(downloads_dir):
            if file.endswith('.xlsx'):
                file_path = os.path.join(downloads_dir, file)
                if os.path.exists(file_path):
                    log_message(f"✅ Archivo encontrado: {file_path}")
                    return file_path
        time.sleep(1)
    return None

def wait_for_and_rename_file(downloads_dir, ficha, timeout=30):
    start_time = time.time()
    new_name_xlsx = f"Reporte de inscritos {ficha}.xlsx"
    new_name_xls = f"Reporte de inscritos {ficha}.xls"
    new_path_xlsx = os.path.join(downloads_dir, new_name_xlsx)
    new_path_xls = os.path.join(downloads_dir, new_name_xls)
    while time.time() - start_time < timeout:
        for file in os.listdir(downloads_dir):
            if file.endswith('.xlsx') or file.endswith('.xls'):
                original_path = os.path.join(downloads_dir, file)
                try:
                    # Si ya tiene el nombre correcto, solo retorna
                    if file == new_name_xlsx or file == new_name_xls:
                        log_message(f"✅ Archivo ya tiene el nombre esperado: {file}")
                        return original_path
                    # Renombrar según extensión
                    if file.endswith('.xlsx'):
                        os.rename(original_path, new_path_xlsx)
                        log_message(f"✅ Archivo renombrado a: {new_name_xlsx}")
                        return new_path_xlsx
                    else:
                        os.rename(original_path, new_path_xls)
                        log_message(f"✅ Archivo renombrado a: {new_name_xls}")
                        return new_path_xls
                except Exception as e:
                    log_message(f"Error renombrando archivo: {e}")
        time.sleep(1)
    return None

def main(ficha):
    driver = None
    try:
        if not ficha:
            log_message("No se recibió número de ficha. Abortando.")
            result = {"success": False, "error": "Ficha vacía"}
            print(json.dumps(result), flush=True)
            return 1

        log_message(f"Iniciando proceso para ficha: {ficha}")
        downloads_dir = get_download_dir()
        log_message(f"Directorio de descargas configurado: {downloads_dir}")

        chrome_options = Options()
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        prefs = {
            "download.default_directory": downloads_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        chrome_options.add_experimental_option("prefs", prefs)

        service = Service(r"D:\Users\Lenovo\Documents\chrome-win\chromedriver.exe")
        driver = webdriver.Chrome(service=service, options=chrome_options)
        wait = WebDriverWait(driver, 15)

        # --- Configuraciones Iniciales ---
        url = "http://senasofiaplus.edu.co/sofia-public/"
        driver.get(url)
        time.sleep(3)

        # Buscar y hacer clic en el botón de "Ingresar"
        try:
            boton_ingresar = driver.find_element(By.XPATH, "//a[contains(text(), 'Ingresar')]")
            boton_ingresar.click()
            time.sleep(2)
        except Exception as e:
            log_message(f"Error al encontrar el botón de Ingresar: {e}")

        # Ingreso de credenciales
        usuario = "1050962935"
        contrasena = "PapaJose92805331050*"

        def iniciar():
            """Función para el login."""
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
                log_message("✅ Inicio de sesión exitoso.")
            except Exception as e:
                log_message(f"❌ Error al iniciar sesión: {e}")

        # Intentar iniciar sesión
        iniciar()

        # --- NAVEGACIÓN ---

        # 1. Seleccionar Rol (Option 4)
        driver.switch_to.default_content() 
        try:
            log_message("⏳ Seleccionando rol...")
            rol_xpath = '//*[@id="seleccionRol:roles"]/option[4]'
            WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, rol_xpath))).click()
            time.sleep(4)
            log_message("✅ Rol seleccionado.")
        except Exception as e:
            log_message(f"❌ Error al seleccionar el rol: {e}")

        # 2. Navegación al menú "Inscripción" y submenús
        driver.switch_to.default_content()
        try:
            log_message("⏳ Navegando al menú...")
            
            # Inscripción
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="side-menu"]/li[4]/a'))
            ).click()
            time.sleep(1)

            # Consultas
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="side-menu"]/li[4]/ul/li[1]/a'))
            ).click()
            time.sleep(1)

            # Generar reporte de inscripción
            elemento_reporte = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="3230Opcion"]'))
            )
            driver.execute_script("arguments[0].click();", elemento_reporte)
            time.sleep(3)
            log_message("✅ Llegada a 'Generar reporte de inscripción'.")

        except Exception as e:
            log_message(f"❌ Error durante la navegación del menú: {e}")


        # 3. Cambiar al iframe "contenido"
        try:
            driver.switch_to.default_content()
            WebDriverWait(driver, 10).until(
                EC.frame_to_be_available_and_switch_to_it((By.ID, "contenido"))
            )
            log_message("✅ Cambiado al iframe 'contenido'.")
            time.sleep(2)
        except Exception as e:
            log_message(f"❌ Error al cambiar al iframe 'contenido': {e}")


        # 4. CLIC EN EL ICONO DE FILTROS (Múltiples estrategias)
        def click_icono_filtros():
            """Intenta hacer clic en el icono de filtros usando múltiples métodos."""
            
            # Estrategia 1: Buscar por imagen (la lupa)
            try:
                log_message("⏳ Método 1: Buscando icono por imagen src...")
                icono = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//img[contains(@src, 'buscar') or contains(@src, 'search')]"))
                )
                driver.execute_script("arguments[0].click();", icono)
                log_message("✅ Clic en icono de filtros (Método 1: imagen).")
                return True
            except TimeoutException:
                log_message("⚠️  Método 1 falló, intentando Método 2...")
            
            # Estrategia 2: Buscar por el enlace padre de la imagen
            try:
                log_message("⏳ Método 2: Buscando enlace padre...")
                enlace = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//a[.//img[contains(@src, 'buscar') or contains(@src, 'search')]]"))
                )
                driver.execute_script("arguments[0].click();", enlace)
                log_message("✅ Clic en icono de filtros (Método 2: enlace).")
                return True
            except TimeoutException:
                log_message("⚠️  Método 2 falló, intentando Método 3...")
            
            # Estrategia 3: Buscar por cualquier ID que contenga el patrón
            try:
                log_message("⏳ Método 3: Buscando por patrón de ID...")
                icono = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, "//*[contains(@id, 'j_id_jsp_') and contains(@id, '_38')]"))
                )
                driver.execute_script("arguments[0].click();", icono)
                log_message("✅ Clic en icono de filtros (Método 3: patrón ID).")
                return True
            except TimeoutException:
                log_message("⚠️  Método 3 falló, intentando Método 4...")
            
            # Estrategia 4: Buscar por posición en la tabla
            try:
                log_message("⏳ Método 4: Buscando por posición en tabla...")
                icono = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//fieldset//table//tr[1]//td[2]//a[1]"))
                )
                driver.execute_script("arguments[0].click();", icono)
                log_message("✅ Clic en icono de filtros (Método 4: tabla).")
                return True
            except TimeoutException:
                log_message("❌ Todos los métodos fallaron para el icono de filtros.")
                return False

        # Ejecutar la función de clic
        click_icono_filtros()
        time.sleep(2)


        # 5. Escribir la ficha en el input dentro del modal
        input_ficha_xpath = '//*[@id="form:codigoFichaITX"]'
        IFRAME_MODAL_ID = 'modalDialogContentviewDialog2'

        try:
            log_message("⏳ Esperando iframe del modal...")
            iframe_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, IFRAME_MODAL_ID))
            )
            driver.switch_to.frame(iframe_element)
            log_message("✅ Iframe del modal activado.")

            log_message(f"⏳ Escribiendo la ficha {ficha} en el input...")
            input_ficha = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, input_ficha_xpath))
            )
            input_ficha.clear()
            input_ficha.send_keys(ficha)
            log_message("✅ Ficha ingresada con éxito.")
            
            # Buscar y presionar el botón de búsqueda/consultar
            try:
                boton_buscar = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//input[@type='submit' or @type='button'][@value='Buscar' or @value='Consultar']"))
                )
                boton_buscar.click()
                log_message("✅ Botón de búsqueda presionado.")
                time.sleep(3)
            except Exception as e:
                log_message(f"⚠️  No se encontró botón de búsqueda automático: {e}")

        except Exception as e:
            log_message(f"❌ Error al interactuar con el modal o el input de la ficha: {e}")

        # 1) Seleccionar el resultado (si existe) - xpath exacto proporcionado
        try:
            log_message("Buscando resultado de ficha...")
            resultado_xpath = '//*[@id="form:dtFichas:0:imgSelec"]'
            elem_result = wait.until(EC.element_to_be_clickable((By.XPATH, resultado_xpath)))
            driver.execute_script("arguments[0].click();", elem_result)
            log_message("Resultado seleccionado. Modal debería cerrarse.")
            time.sleep(2)
        except Exception as e:
            log_message(f"No se encontró resultado para la ficha (puede no existir): {e}")
            # continuar: si no hay resultado, devolver sin error pero vacío
            result = {"success": True, "data": []}
            print(json.dumps(result), flush=True)
            return 0

        # 2) Volver al contexto principal / iframe 'contenido' (si el modal cerró)
        try:
            driver.switch_to.default_content()
            wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "contenido")))
            log_message("Regresado al iframe 'contenido' tras cerrar modal.")
            time.sleep(1)
        except Exception as e:
            log_message(f"Advertencia al volver al iframe 'contenido': {e}")

        # 3) Seleccionar tipo de inscritos: //*[@id="opcionesInscritos"]/option[2]
        try:
            log_message("Seleccionando tipo de inscritos (opción 2)...")
            select_xpath = '//*[@id="opcionesInscritos"]'
            select_elem = wait.until(EC.presence_of_element_located((By.XPATH, select_xpath)))
            # obtener valor de la segunda option y asignarlo
            js_set_option = """
                const sel = arguments[0];
                if (sel && sel.options && sel.options.length > 1) {
                    sel.value = sel.options[1].value;
                    sel.dispatchEvent(new Event('change', { bubbles: true }));
                    return sel.options[1].value;
                }
                return null;
            """
            selected_value = driver.execute_script(js_set_option, select_elem)
            if selected_value:
                log_message(f"Tipo de inscritos seleccionado (value={selected_value}).")
            else:
                log_message("No se pudo seleccionar option[2] en opcionesInscritos.")
            time.sleep(1)
        except Exception as e:
            log_message(f"Error seleccionando tipo de inscritos: {e}")

        # 4) Presionar consulta //*[@id="frmPrincipal:cmdlnkSearch"]
        try:
            log_message("Presionando consulta...")
            consulta_xpath = '//*[@id="frmPrincipal:cmdlnkSearch"]'
            consulta_btn = wait.until(EC.element_to_be_clickable((By.XPATH, consulta_xpath)))
            driver.execute_script("arguments[0].click();", consulta_btn)
            log_message("Consulta ejecutada.")
            time.sleep(2)
        except Exception as e:
            log_message(f"Error al presionar consulta: {e}")

        # 5) Generar reporte //*[@id="frmPrincipal:btnGenerar"]
        try:
            log_message("Generando reporte...")
            generar_xpath = '//*[@id="frmPrincipal:btnGenerar"]'
            generar_btn = wait.until(EC.element_to_be_clickable((By.XPATH, generar_xpath)))
            driver.execute_script("arguments[0].click();", generar_btn)
            log_message("Botón de generar presionado. Esperando proceso...")
            time.sleep(3)
        except Exception as e:
            log_message(f"Error al generar reporte: {e}")
            result = {"success": False, "error": "Error al generar reporte" }
            print(json.dumps(result), flush=True)
            return 1

        # Esperar que el archivo aparezca en la carpeta de descargas
        log_message(f"Esperando archivo .xlsx en: {downloads_dir}")
        file_path = wait_for_and_rename_file(downloads_dir, ficha)

        if file_path and os.path.exists(file_path):
            log_message("Leyendo datos del archivo...")
            excel_data = read_excel_data(file_path)
            result = {"success": True, "data": excel_data}
        else:
            log_message("❌ No se pudo encontrar o renombrar el archivo descargado")
            result = {"success": False, "error": "Archivo no encontrado"}

        print(json.dumps(result), flush=True)
        return 0

    except Exception as e:
        log_message(f"Error crítico en flujo: {e}\n{traceback.format_exc()}")
        result = {"success": False, "error": str(e)}
        print(json.dumps(result), flush=True)
        return 1

    finally:
        if driver:
            try:
                driver.quit()
                log_message("Navegador cerrado.")
            except Exception as e:
                log_message(f"Error cerrando navegador: {e}")

if __name__ == "__main__":
    ficha_arg = sys.argv[1] if len(sys.argv) > 1 else ""
    sys.exit(main(ficha_arg))
