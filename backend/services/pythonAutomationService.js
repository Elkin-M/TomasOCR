// pythonAutomationService.js
// Ubicación: backend/services/pythonAutomationService.js

const { spawn } = require('child_process');
const path = require('path');

class PythonAutomationService {
  constructor() {
    this.pythonProcess = null;
    this.isProcessRunning = false;
  }

  /**
   * Inicia el proceso de automatización Python con stdin habilitado
   */
  startAutomation(ficha, pdfPath, callbacks) {
    if (this.isProcessRunning) {
      console.warn('⚠️ Ya hay un proceso de automatización en ejecución');
      return false;
    }

    const scriptPath = path.join(__dirname, '..', 'scripts', 'auto_service.py');
    const pythonExe = 'python'; // Cambia a 'python3' si es necesario
    
    console.log(`🚀 Iniciando automatización para ficha: ${ficha}`);
    console.log(`📄 PDF: ${pdfPath}`);
    console.log(`📂 Script: ${scriptPath}`);

    // 🔥 CONFIGURACIÓN CRÍTICA: stdio como pipes
    this.pythonProcess = spawn(
      pythonExe, 
      [scriptPath, 'execute', ficha, pdfPath || ''],
      {
        stdio: ['pipe', 'pipe', 'pipe'], // ← CRÍTICO: stdin, stdout, stderr como pipes
        shell: false,
        windowsHide: true,
        env: { ...process.env, PYTHONUNBUFFERED: '1' } // Desactivar buffering
      }
    );

    this.isProcessRunning = true;

    // Configurar stdin
    if (this.pythonProcess.stdin) {
      this.pythonProcess.stdin.setDefaultEncoding('utf8');
      console.log('✅ stdin configurado correctamente');
    } else {
      console.error('❌ stdin no está disponible');
      if (callbacks.onError) {
        callbacks.onError('No se pudo configurar la comunicación con Python');
      }
      return false;
    }

    // ========== MANEJAR STDOUT (Mensajes de Python) ==========
    this.pythonProcess.stdout.on('data', (data) => {
      const lines = data.toString().split('\n').filter(line => line.trim());
      
      lines.forEach(line => {
        try {
          const message = JSON.parse(line);
          this.handlePythonMessage(message, callbacks);
        } catch (error) {
          // Si no es JSON, es un mensaje de texto plano
          console.log('[Python]:', line);
        }
      });
    });

    // ========== MANEJAR STDERR (Errores de Python) ==========
    this.pythonProcess.stderr.on('data', (data) => {
      const errorMsg = data.toString();
      // Solo tratar como error si es un traceback real
      if (errorMsg.includes('Traceback (most recent call last):')) {
        console.error('[Python Error]:', errorMsg);
        if (callbacks.onError) {
          callbacks.onError(errorMsg);
        }
      } else {
        // De lo contrario, tratarlo como un log de depuración
        console.log('[Python Debug]:', errorMsg);
        if (callbacks.onLog) {
          callbacks.onLog(errorMsg, 'debug');
        }
      }
    });

    // ========== MANEJAR CIERRE DEL PROCESO ==========
    this.pythonProcess.on('close', (code) => {
      console.log(`🏁 Proceso Python finalizado con código: ${code}`);
      this.isProcessRunning = false;
      
      if (callbacks.onComplete) {
        callbacks.onComplete(code);
      }
    });

    // ========== MANEJAR ERRORES DEL PROCESO ==========
    this.pythonProcess.on('error', (error) => {
      console.error('💥 Error ejecutando Python:', error);
      this.isProcessRunning = false;
      
      if (callbacks.onError) {
        callbacks.onError(`Error al iniciar Python: ${error.message}`);
      }
    });

    return true;
  }

  /**
   * Procesa mensajes recibidos desde Python
   */
  handlePythonMessage(message, callbacks) {
    console.log(`📨 Mensaje recibido de Python:`, message.type);

    switch (message.type) {
      case 'log':
        if (callbacks.onLog) {
          callbacks.onLog(message.message, message.level || 'info');
        }
        break;

      case 'progress':
        if (callbacks.onProgress) {
          callbacks.onProgress(
            message.step, 
            message.total_steps, 
            message.progress, 
            message.message
          );
        }
        break;

      case 'user_interaction_required':
        console.log(`🔔 Interacción requerida: ${message.interaction}`);
        
        if (callbacks.onUserInteraction) {
          callbacks.onUserInteraction(message.interaction, message.data);
        }
        break;

      default:
        console.log('⚠️ Tipo de mensaje no reconocido:', message.type);
    }
  }

  /**
   * Envía respuesta al proceso Python (MÉTODO CRÍTICO)
   */
  sendResponseToPython(interactionType, responseData) {
    console.log(`\n📤 ==========================================`);
    console.log(`📤 Enviando respuesta a Python`);
    console.log(`📤 Tipo: ${interactionType}`);
    console.log(`📤 Datos:`, JSON.stringify(responseData).substring(0, 200));
    console.log(`📤 ==========================================\n`);

    // Verificar que el proceso existe y stdin está disponible
    if (!this.pythonProcess) {
      console.error('❌ No hay proceso Python activo');
      return false;
    }

    if (!this.pythonProcess.stdin) {
      console.error('❌ stdin no está disponible en el proceso Python');
      return false;
    }

    if (!this.pythonProcess.stdin.writable) {
      console.error('❌ stdin no es escribible');
      return false;
    }

    try {
      // Construir el objeto de respuesta
      const response = {
        interaction_type: interactionType,
        ...responseData
      };

      // Convertir a JSON con salto de línea
      const jsonResponse = JSON.stringify(response) + '\n';
      
      console.log(`📝 JSON a enviar (primeros 200 chars):`, jsonResponse.substring(0, 200));

      // Escribir a stdin
      const written = this.pythonProcess.stdin.write(jsonResponse, 'utf8', (error) => {
        if (error) {
          console.error('❌ Error en callback de write:', error);
        } else {
          console.log('✅ Write callback completado');
        }
      });

      if (written) {
        console.log('✅ Datos escritos inmediatamente a stdin');
      } else {
        console.warn('⚠️ Buffer lleno, esperando drain event...');
        
        this.pythonProcess.stdin.once('drain', () => {
          console.log('✅ Buffer drenado, datos enviados');
        });
      }

      // Importante: NO cerrar stdin aquí
      // this.pythonProcess.stdin.end(); // ❌ NO HACER ESTO

      return true;

    } catch (error) {
      console.error('❌ Excepción al enviar respuesta:', error);
      return false;
    }
  }

  /**
   * Verifica si el proceso está activo
   */
  isActive() {
    return this.isProcessRunning && this.pythonProcess !== null;
  }

  /**
   * Finaliza el proceso Python de forma segura
   */
  terminate() {
    if (!this.pythonProcess) {
      console.log('ℹ️ No hay proceso Python para terminar');
      return;
    }

    console.log('🛑 Terminando proceso Python...');

    try {
      // Cerrar stdin de forma controlada
      if (this.pythonProcess.stdin && this.pythonProcess.stdin.writable) {
        this.pythonProcess.stdin.end();
        console.log('✅ stdin cerrado');
      }

      // Enviar SIGTERM
      this.pythonProcess.kill('SIGTERM');
      console.log('✅ SIGTERM enviado');

      // Si no responde en 5 segundos, forzar con SIGKILL
      setTimeout(() => {
        if (this.pythonProcess && !this.pythonProcess.killed) {
          console.warn('⚠️ Proceso no respondió, enviando SIGKILL...');
          this.pythonProcess.kill('SIGKILL');
        }
      }, 5000);

    } catch (error) {
      console.error('❌ Error terminando proceso:', error);
    } finally {
      this.isProcessRunning = false;
      this.pythonProcess = null;
    }
  }
}

// Exportar instancia única (Singleton)
let serviceInstance = null;

function getPythonAutomationService() {
  if (!serviceInstance) {
    serviceInstance = new PythonAutomationService();
  }
  return serviceInstance;
}

module.exports = { 
  PythonAutomationService,
  getPythonAutomationService 
};