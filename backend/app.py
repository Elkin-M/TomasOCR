from flask import Flask, request, jsonify
from flask_cors import CORS
import threading
import queue
from datetime import datetime

app = Flask(__name__)
CORS(app)  # Habilitar CORS para que el frontend pueda comunicarse

# Cola para almacenar logs en tiempo real
log_queue = queue.Queue()

class LogCapture:
    """Clase para capturar logs y enviarlos al frontend"""
    def __init__(self):
        self.logs = []
    
    def add_log(self, message, level='INFO'):
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = {
            'timestamp': timestamp,
            'message': message,
            'level': level
        }
        self.logs.append(log_entry)
        log_queue.put(log_entry)
        print(f"[{timestamp}] [{level}] {message}")
    
    def get_logs(self):
        return self.logs

def ejecutar_proceso_selenium(ficha, usuario, contrasena, log_capture):
    """
    Función que ejecuta el proceso de Selenium del notebook
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        import time

        log_capture.add_log("Iniciando configuración del navegador...", "INFO")
        
        # Configuraciones Iniciales
        chrome_options = Options()
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--disable-notifications")
        
        # IMPORTANTE: Ajusta esta ruta a tu sistema
        ruta_driver = r"D:\Users\Lenovo\Documents\chrome-win\chromedriver.exe"
        service = Service(ruta_driver)
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        url = "http://senasofiaplus.edu.co/sofia-public/"
        log_capture.add_log(f"Navegando a {url}...", "INFO")
        driver.get(url)
        time.sleep(3)

        # Buscar y hacer clic en el botón de "Ingresar"
        try:
            log_capture.add_log("Buscando botón de ingreso...", "INFO")
            boton_ingresar = driver.find_element(By.XPATH, "//a[contains(text(), 'Ingresar')]")
            boton_ingresar.click()
            time.sleep(2)
        except Exception as e:
            log_capture.add_log(f"No se encontró el botón de Ingresar (puede ser normal): {str(e)[:100]}", "WARNING")

        # Función para el login
        def iniciar():
            try:
                log_capture.add_log("Iniciando sesión...", "INFO")
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
                log_capture.add_log("✅ Inicio de sesión exitoso", "SUCCESS")
            except Exception as e:
                log_capture.add_log(f"❌ Error al iniciar sesión: {str(e)[:150]}", "ERROR")
                raise

        iniciar()

        # NAVEGACIÓN
        driver.switch_to.default_content()
        
        # 1. Seleccionar Rol
        try:
            log_capture.add_log("Seleccionando rol...", "INFO")
            rol_xpath = '//*[@id="seleccionRol:roles"]/option[4]'
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, rol_xpath))
            ).click()
            time.sleep(4)
            log_capture.add_log("Rol seleccionado", "SUCCESS")
        except Exception as e:
            log_capture.add_log(f"Error al seleccionar el rol: {str(e)[:100]}", "ERROR")

        # 2. Navegación al menú
        driver.switch_to.default_content()
        try:
            log_capture.add_log("Navegando al menú de Inscripción...", "INFO")
            
            # Inscripción
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="side-menu"]/li[4]/a'))
            ).click()

            # Consultas
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="side-menu"]/li[4]/ul/li[1]/a'))
            ).click()

            # Generar reporte de inscripción
            elemento_reporte = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="3230Opcion"]'))
            )
            driver.execute_script("arguments[0].click();", elemento_reporte)
            time.sleep(3)
            log_capture.add_log("✅ Llegada a 'Generar reporte de inscripción'", "SUCCESS")

        except Exception as e:
            log_capture.add_log(f"❌ Error durante la navegación del menú: {str(e)[:150]}", "ERROR")

        # 3. Cambiar al iframe "contenido"
        try:
            driver.switch_to.default_content()
            WebDriverWait(driver, 10).until(
                EC.frame_to_be_available_and_switch_to_it((By.ID, "contenido"))
            )
            log_capture.add_log("Cambiado al iframe 'contenido'", "INFO")
            time.sleep(2)
        except Exception as e:
            log_capture.add_log(f"❌ Error al cambiar al iframe 'contenido': {str(e)[:100]}", "ERROR")

        # 4. Clic en el icono de filtros
        try:
            log_capture.add_log("Intentando hacer clic en el icono de filtros...", "INFO")
            icono_filtros_clase = '/html/body[1]/div[2]/form/div[1]/fieldset/table/tbody/tr[1]/td[2]/table/tbody/tr/td[2]/a/img'
            
            icono_filtros = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, icono_filtros_clase))
            )
            driver.execute_script("arguments[0].click();", icono_filtros)
            log_capture.add_log("✅ Clic en icono de filtros ejecutado", "SUCCESS")
            time.sleep(2)
        except Exception as e:
            log_capture.add_log(f"❌ Error al hacer clic en el icono de filtros: {str(e)[:150]}", "ERROR")

        # 5. Escribir la ficha en el input
        input_ficha_xpath = '//*[@id="form:codigoFichaITX"]'
        IFRAME_MODAL_ID = 'modalDialogContentviewDialog2'

        try:
            log_capture.add_log("⏳ Esperando iframe 'modal'...", "INFO")
            iframe_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, IFRAME_MODAL_ID))
            )
            driver.switch_to.frame(iframe_element)
            log_capture.add_log("✅ Iframe 'modal' activado", "SUCCESS")

            log_capture.add_log(f"Escribiendo la ficha {ficha} en el input...", "INFO")
            input_ficha = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, input_ficha_xpath))
            )
            input_ficha.clear()
            input_ficha.send_keys(ficha)
            log_capture.add_log("✅ Ficha ingresada con éxito", "SUCCESS")
            
            # Aquí continuaría el proceso de extracción de datos
            # Por ahora simulamos resultados
            time.sleep(2)
            
        except Exception as e:
            log_capture.add_log(f"❌ Error al interactuar con el modal: {str(e)[:150]}", "ERROR")
        
        finally:
            log_capture.add_log("Cerrando navegador...", "INFO")
            driver.quit()
            log_capture.add_log("🏁 Proceso finalizado", "SUCCESS")
        
        # Retornar datos simulados (aquí extraerías los datos reales)
        return [
            {
                'name': 'Juan Pérez García',
                'doc': '1234567890',
                'status': 'Inscrito',
                'email': 'juan.perez@ejemplo.com'
            },
            {
                'name': 'María López Rodríguez',
                'doc': '0987654321',
                'status': 'En Proceso',
                'email': 'maria.lopez@ejemplo.com'
            }
        ]

    except Exception as e:
        log_capture.add_log(f"🚨 Error crítico: {str(e)}", "ERROR")
        return []

@app.route('/api/reportes/generar', methods=['POST'])
def generar_reporte():
    """
    Endpoint principal que recibe la solicitud del frontend
    """
    try:
        data = request.get_json()
        ficha = data.get('ficha')
        
        # Credenciales configuradas en el backend
        usuario = "1050962935"
        contrasena = "PapaJose92805331050*"
        
        if not ficha:
            return jsonify({
                'success': False,
                'logs': [{'message': 'Falta el número de ficha', 'level': 'ERROR'}],
                'reporte': []
            }), 400
        
        # Crear capturador de logs
        log_capture = LogCapture()
        log_capture.add_log(f"📋 Recibida solicitud para ficha: {ficha}", "INFO")
        
        # Ejecutar el proceso de Selenium
        resultados = ejecutar_proceso_selenium(ficha, usuario, contrasena, log_capture)
        
        return jsonify({
            'success': True,
            'logs': log_capture.get_logs(),
            'reporte': resultados
        }), 200
        
    except Exception as e:
        return jsonify({
            'success': False,
            'logs': [{'message': f'Error en el servidor: {str(e)}', 'level': 'ERROR'}],
            'reporte': []
        }), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Endpoint para verificar que el servidor está funcionando"""
    return jsonify({'status': 'ok', 'message': 'Servidor activo'}), 200

if __name__ == '__main__':
    print("🚀 Servidor Flask iniciado en http://127.0.0.1:5000")
    print("📡 Endpoints disponibles:")
    print("   - POST /api/reportes/generar")
    print("   - GET  /api/health")
    app.run(debug=True, host='127.0.0.1', port=5000)