from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import json
import sys
import traceback
import io

# Configuración de encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def log_message(message):
    """Envía mensajes de log al frontend en formato JSON."""
    print(json.dumps({"type": "log", "message": message}), flush=True)

def main(ficha):
    driver = None
    try:
        if not ficha:
            raise ValueError("No se proporcionó un número de ficha.")

        log_message(f"🚀 Iniciando proceso para convocar aspirantes de la ficha: {ficha}")

        # --- Configuración de Selenium ---
        chrome_options = Options()
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--disable-notifications")
        
        # NOTA: Asegúrate de que esta ruta al chromedriver sea correcta
        service = Service(r"D:\Users\Lenovo\Documents\chrome-win\chromedriver.exe")
        driver = webdriver.Chrome(service=service, options=chrome_options)
        wait = WebDriverWait(driver, 15)

        # --- 1. Inicio de Sesión ---
        log_message("🌐 Navegando a SOFIA Plus...")
        driver.get("http://senasofiaplus.edu.co/sofia-public/")
        time.sleep(3)

        try:
            driver.find_element(By.XPATH, "//a[contains(text(), 'Ingresar')]" ).click()
            time.sleep(2)
        except Exception:
            log_message("🟡 No se encontró el botón 'Ingresar', puede que ya estemos en el formulario.")

        log_message("🔐 Realizando inicio de sesión...")
        driver.switch_to.frame('registradoBox1')
        wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/form/div/div/div/div[2]/input"))).send_keys("1050962935")
        wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/form/div/div/div/div[3]/input"))).send_keys("PapaJose92805331050*")
        wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/form/div/div/div/div[7]/input"))).click()
        time.sleep(5)
        log_message("✅ Inicio de sesión completado.")

        # --- 2. Navegación al Menú ---
        driver.switch_to.default_content()
        log_message("🧭 Navegando a 'Convocar Aspirantes'...")
        
        wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="seleccionRol:roles"]/option[4]'))).click()
        time.sleep(4)
        log_message("✅ Rol seleccionado.")

        driver.switch_to.default_content()
        wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="side-menu"]/li[5]/a'))).click()
        time.sleep(1)
        wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="side-menu"]/li[5]/ul/li[2]/a'))).click()
        time.sleep(1)
        
        elemento_convocar = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="185Opcion"]')))
        driver.execute_script("arguments[0].click();", elemento_convocar)
        time.sleep(3)
        log_message("✅ Navegación a la página de 'Convocar Aspirantes' finalizada.")

        # --- 3. Búsqueda de la Ficha ---
        log_message("🔍 Buscando la ficha en el formulario...")
        wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'contenido')))
        
        icono_filtros = wait.until(EC.presence_of_element_located((By.XPATH, '/html/body[1]/div[2]/div[1]/fieldset/form/table/tbody/tr/td[3]/a/img')))
        driver.execute_script("arguments[0].click();", icono_filtros)
        log_message("✅ Modal de filtros abierto.")
        time.sleep(5) # Espera estática para que el modal cargue completamente

        wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'modalDialogContentviewDialog')))
        log_message("✅ Foco en el modal.")

        input_ficha = wait.until(EC.presence_of_element_located((By.XPATH, '/html/body/div[2]/form/fieldset/div/table/tbody/tr[1]/td[2]/input')))
        input_ficha.clear()
        input_ficha.send_keys(ficha)
        log_message(f"✅ Ficha {ficha} ingresada en el campo de búsqueda.")

        wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="form:buscarCBT"]'))).click()
        log_message("✅ Búsqueda de ficha ejecutada.")
        time.sleep(3)

        # --- 4. Procesamiento (Simulado, ya que la acción final no está clara en el notebook) ---
        # El notebook no muestra qué hacer después de buscar. Asumimos que el proceso termina aquí.
        # Si se necesitara hacer clic en un resultado, se añadiría aquí.
        
        log_message("🎉 Proceso de búsqueda de ficha para convocatoria finalizado con éxito.")
        result = {"success": True, "message": "Búsqueda de ficha completada."}
        print(json.dumps(result), flush=True)

    except Exception as e:
        error_message = f"❌ Error crítico: {e}\n{traceback.format_exc()}"
        log_message(error_message)
        result = {"success": False, "error": str(e)}
        print(json.dumps(result), flush=True)

    finally:
        if driver:
            log_message("🔚 Cerrando navegador...")
            driver.quit()
            log_message("✅ Navegador cerrado.")

if __name__ == "__main__":
    ficha_arg = sys.argv[1] if len(sys.argv) > 1 else ""
    main(ficha_arg)
