import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class Convocar_Module:
    """
    Servicio para navegar a la sección de 'Convocar Aspirantes' y procesarlos.
    """
    def __init__(self, driver, wait, log_callback):
        self.driver = driver
        self.wait = wait
        self.log = log_callback

    def navegar_y_convocar(self, aspirantes_confirmados):
        """
        Navega a la sección 'Convocar Aspirantes' y realiza el proceso
        para los aspirantes confirmados.
        """
        try:
            self.log("Navegando a 'Ejecución de la Formación'...")
            self.driver.switch_to.default_content()
            self.wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="side-menu"]/li[5]/a'))).click()
            
            self.log("Navegando a 'Gestionar Novedades'...")
            self.wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="side-menu"]/li[5]/ul/li[2]/a'))).click()
            
            self.log("Navegando a 'Convocar a Matrícula'...")
            elemento_convocar = self.wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="185Opcion"]')))
            self.driver.execute_script("arguments[0].click();", elemento_convocar)
            time.sleep(3)
            self.log("✅ Navegación a 'Convocar a Matrícula' completada.")

            self.wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, 'contenido')))
            
            # La lógica real para buscar la ficha y seleccionar cada aspirante es compleja
            # y depende de la interfaz de SOFIA Plus. Por ahora, se simula el proceso.
            self.log(f"Simulando la selección y convocatoria de {len(aspirantes_confirmados)} aspirantes...")
            for aspirante in aspirantes_confirmados:
                nombre = aspirante.get('Nombre_Ext', 'N/A')
                self.log(f"  - Procesando (simulado): {nombre}")
                time.sleep(0.5) # Pequeña pausa por cada aspirante

            self.log("✅ Convocatoria de aspirantes (simulada) completada.")

        except Exception as e:
            self.log(f"Error durante la convocatoria de aspirantes: {e}", "error")
            raise
