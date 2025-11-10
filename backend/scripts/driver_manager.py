import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException, NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- Constantes ---
DEBUGGING_PORT = "9222"
USER_DATA_DIR = os.path.join(os.path.expanduser("~"), ".selenium_chrome_session_gemini")
CHROMEDRIVER_PATH = r"D:\\Users\\Lenovo\\Documents\\chrome-win\\chromedriver.exe"
URL_SOFIA_POST_LOGIN = "rol.sofiaplus.edu.co/sofia-rol/"

def get_driver(download_dir=None):
    """
    Obtiene una instancia del driver de Chrome, reutilizando una sesión existente si es posible.
    Si no hay ninguna sesión, crea una nueva en modo de depuración.
    """
    try:
        # Intentar conectarse a un navegador existente
        options = Options()
        options.add_experimental_option("debuggerAddress", f"127.0.0.1:{DEBUGGING_PORT}")
        
        if download_dir:
            prefs = {
                "download.default_directory": download_dir,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": True
            }
            options.add_experimental_option("prefs", prefs)

        service = Service(CHROMEDRIVER_PATH)
        driver = webdriver.Chrome(service=service, options=options)
        
        _ = driver.current_url
        print("INFO: Conectado a la sesión de navegador existente.", flush=True)
        return driver
        
    except WebDriverException:
        # Si falla la conexión, crear una nueva instancia del navegador
        print("INFO: No se encontró sesión de navegador. Creando una nueva...", flush=True)
        options = Options()
        options.add_argument(f"--remote-debugging-port={DEBUGGING_PORT}")
        options.add_argument(f"--user-data-dir={USER_DATA_DIR}")
        options.add_argument("--start-maximized")
        options.add_argument("--disable-notifications")
        
        if download_dir:
            prefs = {
                "download.default_directory": download_dir,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": True
            }
            options.add_experimental_option("prefs", prefs)

        service = Service(CHROMEDRIVER_PATH)
        driver = webdriver.Chrome(service=service, options=options)
        return driver

def do_login(driver, wait):
    """Realiza el proceso de inicio de sesión en Sofia Plus."""
    print("INFO: Iniciando proceso de login...", flush=True)
    try:
        try:
            driver.find_element(By.XPATH, "//a[contains(text(), 'Ingresar')] ").click()
            time.sleep(2)
        except NoSuchElementException:
            print("INFO: Botón 'Ingresar' no encontrado, se asume que el formulario ya está visible.", flush=True)

        driver.switch_to.default_content()
        wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "registradoBox1")))
        
        usuario = "1050962935"
        contrasena = "PapaJose92805331050*"
        
        wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/form/div/div/div/div[2]/input"))).send_keys(usuario)
        wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/form/div/div/div/div[3]/input"))).send_keys(contrasena)
        wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/form/div/div/div/div[7]/input"))).click()
        
        wait.until(EC.url_contains(URL_SOFIA_POST_LOGIN))
        print("INFO: Login exitoso.", flush=True)
        return True
    except Exception as e:
        print(f"ERROR: Fallo durante el login: {e}", flush=True)
        return False