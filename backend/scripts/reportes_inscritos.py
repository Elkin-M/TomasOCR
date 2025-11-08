from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import json
import sys

def log_message(message):
    print(json.dumps({"type": "log", "message": message}))

def generar_reporte_inscritos(ficha):
    
    try:
        log_message(f"Iniciando proceso para ficha {ficha}...")
        chrome_options = Options()
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--disable-notifications")
        
        service = Service(r"D:\Users\Lenovo\Videos\chrome-win\chromedriver.exe")
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        log_message("Navegando a SOFIA Plus...")
        driver.get("http://senasofiaplus.edu.co/sofia-public/")
        
        # ... resto del código de navegación y extracción ...
        
        # Simulación de datos para prueba
        data = {
            "success": True,
            "data": [
                {
                    "nombre": "Juan Pérez",
                    "documento": "1234567890",
                    "estado": "Inscrito",
                    "correo": "juan@email.com"
                }
            ]
        }
        
        driver.quit()
        return data
        
    except Exception as e:
        log_message(f"Error: {str(e)}")
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    if len(sys.argv) > 1:
        ficha = sys.argv[1]
        result = generar_reporte_inscritos(ficha)
        print(json.dumps(result))
