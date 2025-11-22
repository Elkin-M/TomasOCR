import os
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class Reportes_Module:
    """
    Servicio para generar y descargar el reporte de inscritos de una ficha.
    """
    def __init__(self, driver, wait, log_callback, ficha):
        self.driver = driver
        self.wait = wait
        self.log = log_callback
        self.ficha = ficha
        self.download_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'descargas_reportes')

    def generar_y_descargar_reporte(self):
        """
        Navega a la sección de reportes, genera y descarga el de inscritos.
        Renombra el archivo y devuelve la ruta completa.
        """
        try:
            self.log("Navegando a 'Gestión de Reportes'...")
            self.driver.switch_to.default_content()
            self.wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="side-menu"]/li[4]/a'))).click()
            self.wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="side-menu"]/li[4]/ul/li[1]/a'))).click()
            
            self.log("Navegando a 'Reportes de Inscripción'...")
            elemento = self.wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="3230Opcion"]')))
            self.driver.execute_script("arguments[0].click();", elemento)
            time.sleep(3)
            self.log("✅ Llegada a 'Generar reporte de inscripción'.")

            self.wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "contenido")))
            
            self.log("Abriendo modal de búsqueda de ficha...")
            icono_filtros = self.wait.until(EC.presence_of_element_located((By.XPATH, '/html/body[1]/div[2]/form/div[1]/fieldset/table/tbody/tr[1]/td[2]/table/tbody/tr/td[2]/a/img')))
            self.driver.execute_script("arguments[0].click();", icono_filtros)
            time.sleep(2)

            self.log(f"Buscando ficha {self.ficha} en el modal...")
            self.wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'modalDialogContentviewDialog2')))
            input_ficha = self.wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="form:codigoFichaITX"]')))
            input_ficha.clear()
            input_ficha.send_keys(self.ficha)
            buscar_button = self.wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="form:buscarCBT"]')))
            self.driver.execute_script("arguments[0].click();", buscar_button)
            time.sleep(3)
            
            self.log("Seleccionando ficha de los resultados...")
            first_result = self.wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="form:dtFichas:0:imgSelec"]')))
            self.driver.execute_script("arguments[0].click();", first_result)
            time.sleep(3)

            self.log("Iniciando descarga del reporte...")
            self.driver.switch_to.default_content()
            self.driver.switch_to.frame("contenido")
            self.wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="opcionesInscritos"]/option[2]'))).click()
            self.wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="frmPrincipal:cmdlnkSearch"]'))).click()
            time.sleep(5)
            self.wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="frmPrincipal:btnGenerar"]'))).click()
            
            self.log("Descarga iniciada. Esperando 15 segundos para que el archivo se complete...")
            time.sleep(15)

            return self._renombrar_reporte_descargado()

        except Exception as e:
            self.log(f"Error al generar el reporte de inscritos: {e}", "error")
            raise

    def _renombrar_reporte_descargado(self):
        """
        Encuentra el último archivo descargado, lo renombra y devuelve la nueva ruta.
        """
        self.log("Buscando y renombrando el archivo descargado...")
        list_of_files = [os.path.join(self.download_dir, f) for f in os.listdir(self.download_dir)]
        if not list_of_files:
            raise FileNotFoundError("No se encontró ningún archivo en el directorio de descargas.")
        
        latest_file = max(list_of_files, key=os.path.getctime)
        _, file_extension = os.path.splitext(latest_file)
        
        new_file_name = f"Reporte-Ficha-{self.ficha}{file_extension}"
        new_file_path = os.path.join(self.download_dir, new_file_name)
        
        if os.path.exists(new_file_path):
            os.remove(new_file_path)
            self.log(f"Archivo existente '{new_file_name}' eliminado.")
            
        os.rename(latest_file, new_file_path)
        
        self.log(f"✅ Reporte de inscritos guardado como: {new_file_name}")
        return new_file_path
