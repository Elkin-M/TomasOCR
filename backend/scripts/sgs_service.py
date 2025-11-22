from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException, WebDriverException
from selenium.webdriver.common.keys import Keys
import time
import json
import sys
import traceback
import io

# IMPORTANTE: Configurar encoding UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# --- Constantes y Selectores ---
OVERLAY_SELECTOR = (By.CLASS_NAME, "blockUI")
WAIT_TIME = 10 

def log_message(message, level="info"):
    """Envía mensajes de log al frontend en formato JSON."""
    print(json.dumps({"type": "log", "message": message, "level": level}), flush=True)

def inicializar_driver():
    """Inicializa el driver de Chrome"""
    try:
        chrome_options = Options()
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_experimental_option("detach", True) 
        
        log_message("Iniciando ChromeDriver...")
        service = Service(r"D:\\Users\\Lenovo\\Documents\\chrome-win\\chromedriver.exe")
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        log_message("Navegando a SOFIA Plus...")
        driver.get("http://senasofiaplus.edu.co/sofia-public/")
        time.sleep(3)
        
        log_message("[OK] Driver inicializado correctamente")
        return driver
    except Exception as e:
        log_message(f"[ERROR] Error al inicializar el driver: {e}", "error")
        log_message(traceback.format_exc(), "debug_trace")
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
        log_message(f"[WARN] No se encontro el boton Ingresar (continuando): {e}", "warn")
        return False

def iniciar_sesion(driver):
    """Inicia sesión en el sistema Sofia Plus"""
    usuario = "1050962935"
    contrasena = "PapaJose92805331050*"
    wait = WebDriverWait(driver, WAIT_TIME)
    
    try:
        driver.switch_to.default_content()
        wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "registradoBox1")))

        log_message("Ingresando credenciales...")
        
        wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/form/div/div/div/div[2]/input"))).send_keys(usuario)
        wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/form/div/div/div/div[3]/input"))).send_keys(contrasena)
        
        boton_login = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/form/div/div/div/div[7]/input")))
        boton_login.click()
        
        time.sleep(5)
        
        # Verificar fallo de inicio de sesión
        if "para ingresar a la aplicaci" in driver.page_source.lower():
            raise Exception("Fallo en el inicio de sesión. Verifica las credenciales.")
            
        log_message("[OK] Inicio de sesion exitoso")
        return True
    except Exception as e:
        log_message(f"[ERROR] Error al iniciar sesion: {e}", "error")
        log_message(traceback.format_exc(), "debug_trace")
        return False
    finally:
        driver.switch_to.default_content()

def navegacion_principal(driver):
    """Realiza la navegación principal del menú"""
    wait = WebDriverWait(driver, WAIT_TIME)
    
    try:
        driver.switch_to.default_content()
        
        log_message("Seleccionando Rol 'Apoyo Administrativo'...")
        wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="seleccionRol:roles"]/option[4]'))).click()
        time.sleep(2) 
        log_message("[OK] Rol seleccionado")

        log_message("Esperando a que la página cargue (desaparezca el overlay inicial)...")
        try:
            WebDriverWait(driver, 30).until(
                EC.invisibility_of_element_located(OVERLAY_SELECTOR)
            )
            log_message("[OK] Overlay 'blockUI' inicial ha desaparecido.")
        except TimeoutException:
            log_message("[WARN] El overlay inicial no desapareció en 30s. Continuando de todas formas.", "warn")
        
        time.sleep(3)
        driver.switch_to.default_content()
        
        def click_and_wait(xpath, name):
            log_message(f"Navegando a '{name}'...")
            
            try:
                wait.until(EC.invisibility_of_element_located(OVERLAY_SELECTOR))
                log_message(f"DEBUG: Overlay no visible antes de hacer clic en '{name}'.")
            except TimeoutException:
                log_message(f"[WARN] El overlay no desapareció antes de '{name}'. Intentando clic de todas formas.", "warn")

            elemento = wait.until(
                EC.presence_of_element_located((By.XPATH, xpath)) 
            )
            
            driver.execute_script("arguments[0].scrollIntoView(true);", elemento) 
            driver.execute_script("arguments[0].click();", elemento) 
            
            log_message(f"[OK] Clic en '{name}' (FORZADO con JS)")
            time.sleep(2) 

        click_and_wait('//*[@id="side-menu"]/li[9]/a', 'Gestión de Desarrollo Curricular')
        click_and_wait('//*[@id="side-menu"]/li[9]/ul/li/a', 'Desarrollo de la Formación')
        click_and_wait('//*[@id="327229Opcion"]', 'Consultar Fichas de Caracterización')
        
        log_message("[OK] Navegacion completada")
        time.sleep(3)
        return True
        
    except (TimeoutException, ElementClickInterceptedException, WebDriverException) as e:
        log_message(f"[ERROR] Fallo en la navegación por Timeout o Intercepción: {e}", "error")
        log_message(traceback.format_exc(), "debug_trace")
        return False
    except Exception as e:
        log_message(f"[ERROR] Error inesperado en navegacion principal: {e}", "error")
        log_message(traceback.format_exc(), "debug_trace")
        return False


def consultar_ficha(driver, ficha):
    """Consulta una ficha en Sofia Plus y obtiene su estado"""
    datos_ficha = {
        "ficha": ficha,
        "estado": None,
        "resultado_tabla": {},
        "modal_detalle": {}
    }
    
    try:
        wait = WebDriverWait(driver, WAIT_TIME)
        driver.switch_to.default_content()
        wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "contenido")))
        
        log_message(f"Buscando campo de ficha con ID 'formConsultar:numeroFicha'...")
        input_element = wait.until(
            EC.presence_of_element_located((By.ID, "formConsultar:numeroFicha"))
        )
        input_element.clear()
        log_message(f"DEBUG: Enviando la siguiente ficha al campo de texto: {ficha}")
        input_element.send_keys(ficha)
        
        consultar_btn_xpath = '//*[@id="formConsultar:consultarfichasCMD"]'
        wait.until(
            EC.element_to_be_clickable((By.XPATH, consultar_btn_xpath))
        ).click()
        
        log_message(f"Consultando ficha {ficha}...")
        time.sleep(3)
        
        # Verificar si existe un mensaje de error específico
        try:
            error_element = driver.find_element(By.XPATH, '//*[@id="formConsultar:messages1"]')
            error_message = error_element.text.strip()
            if error_message:
                log_message(f"[INFO] Mensaje de error encontrado: {error_message}")
                datos_ficha["estado"] = error_message
                return datos_ficha
        except:
            pass
        
        # Detectar dinámicamente las tablas en la página
        try:
            log_message("[INFO] Escaneando la pagina para detectar elementos...")
            
            tablas = driver.find_elements(By.TAG_NAME, "table")
            log_message(f"[INFO] Encontradas {len(tablas)} tablas en la pagina")
            
            tabla_resultados = None
            for idx, tabla in enumerate(tablas):
                tabla_id = tabla.get_attribute("id")
                tabla_class = tabla.get_attribute("class")
                es_visible = tabla.is_displayed()
                
                log_message(f"[INFO] Tabla {idx+1}: id='{tabla_id}', class='{tabla_class}', visible={es_visible}")
                
                if es_visible and tabla_id:
                    try:
                        filas = tabla.find_elements(By.XPATH, ".//tbody/tr")
                        if len(filas) > 0:
                            log_message(f"[INFO] Tabla '{tabla_id}' tiene {len(filas)} filas - CANDIDATA")
                            tabla_resultados = tabla
                            break
                    except:
                        pass
            
            if not tabla_resultados:
                log_message("[WARN] No se encontro tabla de resultados")
                datos_ficha["estado"] = "Sin resultados"
                return datos_ficha
            
            tabla_id = tabla_resultados.get_attribute("id")
            log_message(f"[OK] Tabla de resultados identificada: '{tabla_id}'")
            
            # Extraer información de la primera fila
            try:
                primera_fila = tabla_resultados.find_element(By.XPATH, ".//tbody/tr[1]")
                celdas = primera_fila.find_elements(By.TAG_NAME, "td")
                
                log_message(f"[INFO] Primera fila tiene {len(celdas)} columnas")
                
                headers = []
                try:
                    thead = tabla_resultados.find_element(By.TAG_NAME, "thead")
                    th_elements = thead.find_elements(By.TAG_NAME, "th")
                    headers = [th.text.strip() for th in th_elements if th.text.strip()]
                    log_message(f"[INFO] Headers encontrados: {headers}")
                except:
                    log_message("[INFO] No se encontraron headers en la tabla")
                
                for i, celda in enumerate(celdas):
                    texto = celda.text.strip()
                    if texto:
                        key = headers[i] if i < len(headers) and headers[i] else f"columna_{i+1}"
                        datos_ficha["resultado_tabla"][key] = texto
                        log_message(f"[INFO] {key}: {texto}")
                
                log_message(f"[OK] Datos de la tabla extraidos: {len(datos_ficha['resultado_tabla'])} campos")
                
            except Exception as e:
                log_message(f"[WARN] Error al extraer datos de la tabla: {e}", "warn")
            
            # Extraer el estado
            try:
                spans = driver.find_elements(By.TAG_NAME, "span")
                for span in spans:
                    texto = span.text.strip()
                    
                    if texto and any(keyword in texto for keyword in ["Ejecución", "Finalizada", "Suspendida", "Cancelada", "Activa"]):
                        estado = texto
                        datos_ficha["estado"] = estado
                        log_message(f"[OK] Estado extraido: {estado}")
                        break
            except Exception as e:
                log_message(f"[WARN] No se encontro el elemento de estado: {e}", "warn")
            
            # Buscar dinámicamente el icono de detalle
            try:
                log_message("[INFO] Buscando icono de detalle...")
                
                imagenes = primera_fila.find_elements(By.TAG_NAME, "img")
                log_message(f"[INFO] Encontradas {len(imagenes)} imagenes en la primera fila")
                
                icono_detalle = None
                for idx, img in enumerate(imagenes):
                    img_id = img.get_attribute("id") or ""
                    img_src = img.get_attribute("src") or ""
                    img_title = img.get_attribute("title") or ""
                    
                    log_message(f"[INFO] Imagen {idx+1}: id='{img_id}', src='{img_src[-30:]}', title='{img_title}'")
                    
                    if any(keyword in img_id.lower() for keyword in ["det", "detalle", "detail", "info"]) or \
                        any(keyword in img_src.lower() for keyword in ["det", "detalle", "detail", "info", "eye", "view"]) or \
                        any(keyword in img_title.lower() for keyword in ["det", "detalle", "detail", "ver"]):
                        icono_detalle = img
                        log_message(f"[OK] Icono de detalle identificado: {img_id}")
                        break
                
                if not icono_detalle and len(imagenes) > 0:
                    icono_detalle = imagenes[0]
                    log_message(f"[WARN] Usando primera imagen como icono de detalle", "warn")
                
                if not icono_detalle:
                    log_message("[WARN] No se encontro icono de detalle", "warn")
                else:
                    driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", icono_detalle)
                    time.sleep(1)
                    driver.execute_script("arguments[0].click();", icono_detalle)
                    log_message("[OK] Clic en icono de detalle exitoso (vía JS)")
                    time.sleep(4)
                    
                    # Buscar el modal dinámicamente
                    try:
                        log_message("[INFO] Buscando modal...")
                        
                        divs = driver.find_elements(By.TAG_NAME, "div")
                        
                        modal = None
                        for div in divs:
                            div_class = div.get_attribute("class") or ""
                            div_role = div.get_attribute("role") or ""
                            div_style = div.get_attribute("style") or ""
                            
                            if (("dialog" in div_class.lower() or div_role == "dialog") and 
                                "display: none" not in div_style and 
                                div.is_displayed()):
                                
                                if len(div.text.strip()) > 50:
                                    modal = div
                                    log_message(f"[OK] Modal encontrado: class='{div_class[:50]}'")
                                    break
                        
                        if not modal:
                            log_message("[WARN] No se encontro el modal", "warn")
                        else:
                            modal_text = modal.text
                            datos_ficha["modal_detalle"]["texto_completo"] = modal_text
                            log_message("[OK] Texto completo del modal extraido")
                            log_message(f"[INFO] Contenido del modal ({len(modal_text)} chars): {modal_text[:200]}...")
                            
                            # Extraer campos estructurados
                            try:
                                campos = {}
                                
                                elementos = modal.find_elements(By.XPATH, ".//*[string-length(text()) > 0]")
                                
                                for elemento in elementos:
                                    tag = elemento.tag_name
                                    elem_id = elemento.get_attribute("id") or ""
                                    elem_class = elemento.get_attribute("class") or ""
                                    texto = elemento.text.strip()
                                    
                                    if tag in ["label", "span", "input", "p", "div"]:
                                        if tag == "input":
                                            valor = elemento.get_attribute("value") or ""
                                            if valor:
                                                key = elem_id if elem_id else f"input_{len(campos)}"
                                                campos[key] = valor
                                        elif texto and len(texto) > 0 and len(texto) < 200:
                                            if elem_id:
                                                campos[elem_id] = texto
                                            elif "label" in elem_class.lower() or tag == "label":
                                                try:
                                                    parent = elemento.find_element(By.XPATH, "..")
                                                    siguiente = parent.find_element(By.XPATH, ".//*[not(self::label)]")
                                                    valor = siguiente.text.strip() or siguiente.get_attribute("value") or ""
                                                    if valor:
                                                        campos[texto] = valor
                                                except Exception:
                                                    pass
                                            
                                datos_ficha["modal_detalle"]["campos"] = campos
                                log_message(f"[OK] Campos del modal extraidos: {len(campos)} campos")
                                
                            except Exception as e:
                                log_message(f"[WARN] Error al extraer campos del modal: {e}", "warn")
                            
                            # Cerrar el modal
                            try:
                                botones_cerrar = modal.find_elements(By.XPATH, ".//*[contains(@class, 'close') or contains(@title, 'Close') or contains(@title, 'Cerrar') or contains(text(), 'Cerrar')]")
                                if botones_cerrar:
                                    driver.execute_script("arguments[0].click();", botones_cerrar[0])
                                    time.sleep(1)
                                    log_message("[OK] Modal cerrado")
                                else:
                                    raise Exception("No se encontro boton de cerrar")
                            except:
                                try:
                                    driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                                    time.sleep(1)
                                    log_message("[OK] Modal cerrado con ESC")
                                except:
                                    log_message("[WARN] No se pudo cerrar el modal", "warn")
                            
                    except Exception as e:
                        log_message(f"[WARN] Error al procesar modal: {e}", "warn")
                        log_message(traceback.format_exc(), "debug_trace")
                        
            except Exception as e:
                log_message(f"[WARN] Error al buscar icono de detalle: {e}", "warn")
                log_message(traceback.format_exc(), "debug_trace")
                        
        except Exception as e:
            log_message(f"[WARN] No se encontraron resultados para la ficha {ficha}: {e}", "warn")
            datos_ficha["estado"] = "Sin resultados"
        
        return datos_ficha
        
    except Exception as e:
        log_message(f"[WARN] Ocurrio un error en consultar_ficha: {e}", "error")
        log_message(traceback.format_exc(), "debug_trace")
        datos_ficha["estado"] = f"Error: {str(e)}"
        return datos_ficha
    finally:
        driver.switch_to.default_content()

def run_sgs(ficha):
    """Función principal que ejecuta el proceso SGS"""
    driver = None
    try:
        log_message(f"Iniciando proceso para ficha {ficha}...")
        
        driver = inicializar_driver()
        if not driver:
            raise Exception("No se pudo inicializar el driver")
        
        hacer_clic_ingresar(driver)
        
        if not iniciar_sesion(driver):
            raise Exception("Fallo al iniciar sesión.")
        
        if not navegacion_principal(driver):
            raise Exception("Fallo en la navegación principal del menú.")
        
        log_message(f"Consultando ficha {ficha}...")
        datos = consultar_ficha(driver, ficha)
        
        result = {
            "success": True,
            "estado": datos.get("estado", "Proceso iniciado - Navegador abierto"),
            "ficha": ficha,
            "datos_completos": datos,
            "mensaje": "El navegador permanecera abierto para intervencion manual si es necesario"
        }
        
        log_message(f"[OK] Proceso completado - Navegador permanece abierto")
        if datos.get("estado"):
            log_message(f"Estado de la ficha: {datos['estado']}")
        
        print(json.dumps(result, ensure_ascii=False), flush=True)
        return result
        
    except Exception as e:
        log_message(f"[ERROR] Error en el proceso: {e}", "error")
        log_message(traceback.format_exc(), "debug_trace")
        
        error_result = {
            "success": True, 
            "estado": "Error - Navegador abierto para intervencion manual",
            "error": str(e),
            "ficha": ficha,
            "mensaje": "Ocurrio un error pero el navegador permanece abierto. Revise los logs."
        }
        print(json.dumps(error_result, ensure_ascii=False), flush=True)
        return error_result
    
    finally:
        log_message("[INFO] Navegador permanece abierto - Cierre manual requerido")
        pass 

if __name__ == "__main__":
    if len(sys.argv) > 2:
        action = sys.argv[1]
        ficha = sys.argv[2]
        if action.lower() == 'execute':
            run_sgs(ficha)
        else:
            print(json.dumps({"success": False, "error": f"Acción desconocida: {action}"}, ensure_ascii=False), flush=True)
    else:
        print(json.dumps({"success": False, "error": "Argumentos insuficientes. Se requiere una acción y un número de ficha."}, ensure_ascii=False), flush=True)