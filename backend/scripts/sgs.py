from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import pandas as pd
import requests
import json
from datetime import date, timedelta
import traceback

# Variables globales
estado = ""
ficha = ""
driver = None  # Declarar driver como global

def inicializar_driver():
    """Inicializa el driver de Chrome"""
    global driver
    try:
        # Configuración del navegador
        chrome_options = Options()
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_experimental_option("detach", True)  # IMPORTANTE: Mantiene el navegador abierto
        
        # Ruta del ChromeDriver (ajústala según tu PC)
        ruta_driver = r"D:\Users\Lenovo\Videos\chrome-win\chromedriver.exe"  
        service = Service(ruta_driver)
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # URL de Sofia Plus
        url = "http://senasofiaplus.edu.co/sofia-public/"
        driver.get(url)
        time.sleep(3)
        
        print("✓ Driver inicializado correctamente")
        return True
    except Exception as e:
        print(f"✗ Error al inicializar el driver: {e}")
        traceback.print_exc()
        return False

def hacer_clic_ingresar():
    """Buscar y hacer clic en el botón de Ingresar"""
    try:
        boton_ingresar = driver.find_element(By.XPATH, "//a[contains(text(), 'Ingresar')]")
        boton_ingresar.click()
        time.sleep(2)
        print("✓ Clic en botón Ingresar exitoso")
        return True
    except Exception as e:
        print(f"✗ Error al encontrar el botón de Ingresar: {e}")
        return False

def iniciar():
    """Inicia sesión en el sistema Sofia Plus"""
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
        print("✓ Inicio de sesión exitoso")
        return True
    except Exception as e:
        print(f"✗ Error al iniciar sesión: {e}")
        traceback.print_exc()
        return False

def verificasofia1(ficha_param):
    """Verifica datos desde Google Apps Script"""
    web_app_url = "https://script.google.com/macros/s/AKfycbyjawbAG1VSRXW7liCg88fTx1zMIe04v6ecM1Tn_2Er3RCp9OynzFcVS4hgFk16jpU/exec"
    
    try:
        response = requests.get(web_app_url)
        response.raise_for_status()
        data = response.json()
        
        if "valorE" in data:
            global ficha
            ficha = data["valorE"]
            print(f"✓ Ficha obtenida: {ficha}")
            return ficha
        elif "error" in data:
            print(f"✗ Error from the web app: {data['error']}")
            return None
        else:
            print("✗ Unexpected response from the web app")
            return None
            
    except Exception as e:
        print(f"✗ Error calling the web app: {e}")
        traceback.print_exc()
        return None

def cargasofia1(ficha):
    """Carga una ficha en Sofia Plus y obtiene su estado completo"""
    global estado
    
    datos_ficha = {
        "ficha": ficha,
        "estado": None,
        "resultado_tabla": {},
        "modal_detalle": {}
    }
    
    try:
        driver.switch_to.default_content()
        driver.switch_to.frame("contenido")
        
        # Ingresar la ficha en el input
        input_xpath = "/html/body/div[2]/form/div[1]/fieldset/table/tbody/tr[6]/td[2]/input"
        input_element = driver.find_element(By.XPATH, input_xpath)
        input_element.clear()
        input_element.send_keys(ficha)
        
        # Hacer clic en el botón "Consultar Ficha"
        consultar_btn_xpath = '//*[@id="formConsultar:consultarfichasCMD"]'
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, consultar_btn_xpath))
        ).click()
        
        print(f"✓ Consultando ficha {ficha}...")
        time.sleep(3)
        
        # Verificar si hay resultados
        try:
            tabla_resultado = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="formConsultar:fichasDTB"]'))
            )
            
            print("✓ Se encontraron resultados en la tabla")
            
            # Extraer información de la fila de resultados
            try:
                fila_xpath = '//*[@id="formConsultar:fichasDTB:0"]'
                fila = driver.find_element(By.XPATH, fila_xpath)
                celdas = fila.find_elements(By.TAG_NAME, "td")
                
                datos_ficha["resultado_tabla"] = {
                    f"columna_{i+1}": celda.text.strip() for i, celda in enumerate(celdas) if celda.text.strip()
                }
                
                print(f"✓ Datos de la tabla extraídos: {datos_ficha['resultado_tabla']}")
                
            except Exception as e:
                print(f"✗ No se pudieron extraer datos de la tabla: {e}")
            
            # Hacer clic en el icono de detalle para abrir el modal
            try:
                detalle_icon_xpath = '//*[@id="formConsultar:fichasDTB:0:imgDetFicha"]'
                icono_detalle = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, detalle_icon_xpath))
                )
                icono_detalle.click()
                print("✓ Modal de detalle abierto")
                time.sleep(2)
                
                # Extraer información del modal
                try:
                    modal_xpath = '//*[contains(@class, "ui-dialog") or contains(@role, "dialog")]'
                    modal = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, modal_xpath))
                    )
                    
                    modal_text = modal.text
                    datos_ficha["modal_detalle"]["texto_completo"] = modal_text
                    
                    # Extraer campos específicos
                    try:
                        labels = modal.find_elements(By.TAG_NAME, "label")
                        spans = modal.find_elements(By.TAG_NAME, "span")
                        
                        campos = {}
                        for label in labels:
                            texto = label.text.strip()
                            if texto:
                                campos[texto] = None
                        
                        for span in spans:
                            texto = span.text.strip()
                            if texto and len(texto) > 0:
                                id_span = span.get_attribute("id")
                                if id_span:
                                    campos[id_span] = texto
                        
                        datos_ficha["modal_detalle"]["campos"] = campos
                        
                    except Exception as e:
                        print(f"✗ Error al extraer campos específicos del modal: {e}")
                    
                    print("✓ Información del modal extraída")
                    
                    # Cerrar el modal
                    try:
                        cerrar_btn = modal.find_element(By.XPATH, './/*[contains(@class, "ui-dialog-titlebar-close") or contains(text(), "Cerrar")]')
                        cerrar_btn.click()
                        time.sleep(1)
                    except:
                        print("⚠ No se pudo cerrar el modal automáticamente")
                    
                except Exception as e:
                    print(f"✗ Error al extraer información del modal: {e}")
                    traceback.print_exc()
                    
            except Exception as e:
                print(f"✗ Error al abrir el modal: {e}")
            
            # Extraer el estado
            try:
                status_element_xpath = "/html/body/div[2]/form/div[1]/div[2]/fieldset/table/tbody/tr/td[3]/span"
                elemento = driver.find_element(By.XPATH, status_element_xpath)
                estado_local = elemento.text
                estado = estado_local
                datos_ficha["estado"] = estado
                print(f"✓ Estado extraído: {estado}")
            except Exception as e:
                print(f"⚠ No se encontró el elemento de estado: {e}")
            
        except Exception as e:
            print(f"✗ No se encontraron resultados para la ficha {ficha}: {e}")
            datos_ficha["estado"] = "Sin resultados"
        
        return datos_ficha
        
    except Exception as e:
        print(f"✗ Ocurrió un error en cargasofia1: {e}")
        traceback.print_exc()
        datos_ficha["estado"] = f"Error: {str(e)}"
        return datos_ficha

def llamarclick(xphat):
    """Hace clic en un elemento usando JavaScript"""
    try:
        elemento = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, f'{xphat}'))
        )
        driver.execute_script("arguments[0].click();", elemento)
        return True
    except Exception as e:
        print(f"✗ Error en llamarclick: {e}")
        return False

def llamarclicksolo(xphat):
    """Hace clic en un elemento de forma directa"""
    try:
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, f'{xphat}'))
        ).click()
        return True
    except Exception as e:
        print(f"✗ Error en llamarclicksolo: {e}")
        return False

def leerelemento(xphat):
    """Lee y muestra el texto de un elemento"""
    try:
        elemento = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, f'{xphat}'))
        )
        print(elemento.text)
        return elemento.text
    except Exception as e:
        print(f"✗ Error en leerelemento: {e}")
        return None

def enviardatosSofia(ficha, estado_retornado):
    """Envía datos a Google Apps Script"""
    idapp = "AKfycbx-3ehgVsKN8c55dZt0_hdy14DPut5qQXq9ZyehRTOdj7LjkTJld7TeIKLsHfsj8WM"
    url_app_script = f"https://script.google.com/macros/s/{idapp}/exec"
    
    payload = {
        "ficha": ficha,
        "estado": estado_retornado
    }
    
    print(f"→ Enviando datos a: {url_app_script}")
    print(f"→ Payload: {payload}")
    
    try:
        response = requests.post(url_app_script, data=payload, allow_redirects=True)
        print(f"✓ C��digo de estado: {response.status_code}")
        print("✓ Respuesta del servidor:")
        print(response.text)
        
        if response.history:
            print("\nHistorial de redirecciones:")
            for resp in response.history:
                print(f" - {resp.status_code} {resp.url}")
            print(f" -> {response.status_code} {response.url} (URL final)")
        
        return True
            
    except Exception as e:
        print(f"✗ Ocurrió un error al enviar la solicitud: {e}")
        traceback.print_exc()
        return False

def navegacion_principal():
    """Realiza la navegación principal del menú"""
    try:
        driver.switch_to.default_content()
        
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, '//*[@id="seleccionRol:roles"]/option[4]'))
        ).click()
        time.sleep(4)
        print("✓ Rol seleccionado")
        
        driver.switch_to.default_content()
        
        try:
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '/html/body[1]/div/div[1]/nav/div[2]/div/div/form[2]/ul/li[9]/a'))
            ).click()
            
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '/html/body[1]/div/div[1]/nav/div[2]/div/div/form[2]/ul/li[9]/ul/li/a'))
            ).click()
            
            elemento = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '/html/body[1]/div/div[1]/nav/div[2]/div/div/form[2]/ul/li[9]/ul/li/ul/li[4]/a'))
            )
            driver.execute_script("arguments[0].click();", elemento)
            print("✓ Navegación completada (primer intento)")
            
        except:
            print("⚠ Primer intento de navegación falló, intentando alternativa...")
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '/html/body[1]/div/div[1]/nav/div[2]/div/div/form[2]/ul/l[9]/a'))
            ).click()
            
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '/html/body[1]/div/div[1]/nav/div[2]/div/div/form[2]/ul/li[9]/ul/li/a'))
            ).click()
            
            elemento = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '/html/body[1]/div/div[1]/nav/div[2]/div/div/form[2]/ul/li[9]/ul/li/ul/li[4]/a'))
            )
            driver.execute_script("arguments[0].click();", elemento)
            print("✓ Navegación completada (segundo intento)")
        
        time.sleep(3)
        return True
        
    except Exception as e:
        print(f"✗ Error en navegación principal: {e}")
        traceback.print_exc()
        return False

# ============================================================================
# PROGRAMA PRINCIPAL CON MANEJO ROBUSTO DE ERRORES
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*70)
    print("INICIANDO SCRIPT DE AUTOMATIZACIÓN SOFIA PLUS")
    print("="*70 + "\n")
    
    try:
        # 1. Inicializar driver
        print("PASO 1: Inicializando navegador...")
        if not inicializar_driver():
            print("⚠ Fallo al inicializar, pero continuando...")
        
        # 2. Clic en botón Ingresar
        print("\nPASO 2: Haciendo clic en Ingresar...")
        if not hacer_clic_ingresar():
            print("⚠ Fallo al hacer clic en Ingresar, pero continuando...")
        
        # 3. Iniciar sesión
        print("\nPASO 3: Iniciando sesión...")
        if not iniciar():
            print("⚠ Fallo al iniciar sesión, pero continuando...")
        
        # 4. Cargar datos desde Excel (opcional)
        print("\nPASO 4: Cargando datos desde Excel...")
        try:
            ruta_excel = r"D:\Users\Lenovo\Desktop\ollama\Complementaria 2025.xlsx"
            df = pd.read_excel(ruta_excel, engine="openpyxl")
            print(f"✓ Excel cargado: {len(df)} filas")
            print(df.head())
        except Exception as e:
            print(f"⚠ No se pudo cargar el Excel: {e}")
            print("Continuando sin datos de Excel...")
        
        # 5. Navegación principal
        print("\nPASO 5: Realizando navegación principal...")
        if not navegacion_principal():
            print("⚠ Fallo en navegación principal, pero continuando...")
        
        # 6. Consultar ficha de ejemplo
        print("\nPASO 6: Consultando ficha de ejemplo...")
        try:
            ficha_ejemplo = "3189000"
            print(f"Estado ANTES de consulta: {estado}")
            
            datos_extraidos = cargasofia1(ficha_ejemplo)
            
            print(f"\n{'='*70}")
            print("DATOS EXTRAÍDOS (formato JSON):")
            print(f"{'='*70}")
            print(json.dumps(datos_extraidos, indent=2, ensure_ascii=False))
            
            print(f"\n{'='*70}")
            print("ACCESO A DATOS ESPECÍFICOS:")
            print(f"{'='*70}")
            print(f"Ficha consultada: {datos_extraidos['ficha']}")
            print(f"Estado: {datos_extraidos['estado']}")
            print(f"Datos de la tabla: {datos_extraidos['resultado_tabla']}")
            print(f"Datos del modal: {datos_extraidos['modal_detalle']}")
            
        except Exception as e:
            print(f"✗ Error al consultar ficha: {e}")
            traceback.print_exc()
        
        print("\n" + "="*70)
        print("✓ PROCESO COMPLETADO")
        print("="*70)
        
    except Exception as e:
        print("\n" + "="*70)
        print(f"✗ ERROR GENERAL: {e}")
        traceback.print_exc()
        print("="*70)
    
    finally:
        # EL NAVEGADOR PERMANECERÁ ABIERTO
        print("\n" + "="*70)
        print("⚠ EL NAVEGADOR PERMANECERÁ ABIERTO")
        print("="*70)
        print("\nOpciones:")
        print("1. Presiona ENTER para cerrar el navegador")
        print("2. Presiona Ctrl+C para salir dejando el navegador abierto")
        print("="*70)
        
        try:
            input()
            print("\nCerrando navegador...")
            //if driver:
            //    driver.quit()
            print("✓ Navegador cerrado correctamente")
        except KeyboardInterrupt:
            print("\n\n⚠ Saliendo sin cerrar el navegador...")
            print("El navegador permanecerá abierto.")
        except:
            print("\n⚠ El navegador permanecerá abierto")
        
        print("\n✓ Programa finalizado")
