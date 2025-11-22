// ipcHandlers.js
// Ubicación: backend/ipc/ipcHandlers.js o dentro de tu main.js

const { ipcMain } = require('electron');
const { getPythonAutomationService } = require('../services/pythonAutomationService');

/**
 * Configura todos los manejadores IPC para la automatización
 */
function setupAutomationIpcHandlers(mainWindow) {
  const automationService = getPythonAutomationService();

  // ========== INICIAR AUTOMATIZACIÓN ==========
  ipcMain.on('start-automation', (event, { ficha, pdfPath }) => {
    console.log('\n🎬 ========================================');
    console.log('🎬 INICIANDO AUTOMATIZACIÓN');
    console.log(`🎬 Ficha: ${ficha}`);
    console.log(`🎬 PDF: ${pdfPath}`);
    console.log('🎬 ========================================\n');

    const success = automationService.startAutomation(ficha, pdfPath, {
      
      // Callback para logs
      onLog: (message, level) => {
        mainWindow.webContents.send('automation-log', { message, level });
      },

      // Callback para progreso
      onProgress: (step, totalSteps, progress, message) => {
        mainWindow.webContents.send('automation-progress', { 
          step, 
          totalSteps, 
          progress, 
          message 
        });
      },

      // Callback para interacción del usuario
      onUserInteraction: (interactionType, data) => {
        console.log(`\n🔔 ========================================`);
        console.log(`🔔 INTERACCIÓN REQUERIDA: ${interactionType}`);
        console.log(`🔔 Datos:`, data);
        console.log(`🔔 ========================================\n`);
        
        mainWindow.webContents.send('automation-user-interaction', { 
          interactionType, 
          data 
        });
      },

      // Callback para errores
      onError: (error) => {
        console.error('💥 Error en automatización:', error);
        mainWindow.webContents.send('automation-error', { success: false, error });
      },

      // Callback para completar
      onComplete: (exitCode) => {
        console.log(`\n🏁 ========================================`);
        console.log(`🏁 AUTOMATIZACIÓN COMPLETADA`);
        console.log(`🏁 Código de salida: ${exitCode}`);
        console.log(`🏁 ========================================\n`);
        
        mainWindow.webContents.send('automation-complete', { success: exitCode === 0, exitCode });
      }
    });

    if (!success) {
      event.reply('automation-error', { 
        error: 'No se pudo iniciar el proceso de automatización' 
      });
    }
  });

  // ========== SELECCIÓN DE IMÁGENES OCR ==========
  ipcMain.on('ocr-images-selected', (event, { selectedImages }) => {
    console.log(`\n📸 ========================================`);
    console.log(`📸 IMÁGENES SELECCIONADAS POR EL USUARIO`);
    console.log(`📸 Cantidad: ${selectedImages ? selectedImages.length : 0}`);
    console.log(`📸 ========================================\n`);

    if (!automationService.isActive()) {
      console.error('❌ No hay proceso activo para enviar la selección');
      event.reply('automation-error', { 
        error: 'El proceso de automatización no está activo' 
      });
      return;
    }

    const success = automationService.sendResponseToPython('ocr_image_selection', {
      selected_images: selectedImages || []
    });

    if (success) {
      console.log('✅ Selección de imágenes enviada correctamente');
      event.reply('ocr-images-response-sent', { success: true });
    } else {
      console.error('❌ Error enviando selección de imágenes');
      event.reply('automation-error', { 
        error: 'No se pudo enviar la selección de imágenes' 
      });
    }
  });

  // ========== CONFIRMACIÓN DE ASPIRANTES ==========
  ipcMain.on('confirm-aspirantes', (event, { confirmedAspirants }) => {
    console.log(`\n👥 ========================================`);
    console.log(`👥 ASPIRANTES CONFIRMADOS`);
    console.log(`👥 Cantidad: ${confirmedAspirants ? confirmedAspirants.length : 0}`);
    console.log(`👥 ========================================\n`);

    if (!automationService.isActive()) {
      console.error('❌ No hay proceso activo');
      event.reply('automation-error', { 
        error: 'El proceso de automatización no está activo' 
      });
      return;
    }

    const success = automationService.sendResponseToPython('convocar_aspirantes_confirmation', {
      confirmed_aspirants: confirmedAspirants || []
    });

    if (success) {
      console.log('✅ Confirmación de aspirantes enviada');
      event.reply('aspirantes-response-sent', { success: true });
    } else {
      console.error('❌ Error enviando confirmación');
      event.reply('automation-error', { 
        error: 'No se pudo enviar la confirmación' 
      });
    }
  });

  // ========== CONFIRMACIÓN FIN DE MATRÍCULA ==========
  ipcMain.on('confirm-fin-matricula', (event, { confirm }) => {
    console.log(`\n🎓 ========================================`);
    console.log(`🎓 FIN DE MATRÍCULA: ${confirm ? 'CONFIRMADO' : 'CANCELADO'}`);
    console.log(`🎓 ========================================\n`);

    if (!automationService.isActive()) {
      console.error('❌ No hay proceso activo');
      event.reply('automation-error', { 
        error: 'El proceso de automatización no está activo' 
      });
      return;
    }

    const success = automationService.sendResponseToPython('fin_matricula_confirmation', {
      confirm: confirm === true
    });

    if (success) {
      console.log('✅ Confirmación de fin de matrícula enviada');
      event.reply('fin-matricula-response-sent', { success: true });
    } else {
      console.error('❌ Error enviando confirmación');
      event.reply('automation-error', { 
        error: 'No se pudo enviar la confirmación' 
      });
    }
  });

  // ========== RESPUESTA GENÉRICA DE USUARIO ==========
  ipcMain.on('user-interaction-response', (event, { interactionType, responseData }) => {
    console.log(`\n💬 ========================================`);
    console.log(`💬 RESPUESTA GENÉRICA DEL USUARIO`);
    console.log(`💬 Tipo: ${interactionType}`);
    console.log(`💬 Datos:`, responseData);
    console.log(`💬 ========================================\n`);

    if (!automationService.isActive()) {
      console.error('❌ No hay proceso activo');
      event.reply('automation-error', { 
        error: 'El proceso de automatización no está activo' 
      });
      return;
    }

    const success = automationService.sendResponseToPython(interactionType, responseData);

    if (!success) {
      console.error('❌ Error enviando respuesta');
      event.reply('automation-error', { 
        error: 'No se pudo enviar la respuesta al proceso Python' 
      });
    }
  });

  // ========== CANCELAR AUTOMATIZACIÓN ==========
  ipcMain.on('cancel-automation', (event) => {
    console.log('\n🛑 Cancelando automatización...');
    automationService.terminate();
    event.reply('automation-cancelled', { success: true });
  });

  // ========== VERIFICAR ESTADO ==========
  ipcMain.on('check-automation-status', (event) => {
    const isActive = automationService.isActive();
    event.reply('automation-status', { isActive });
  });

  console.log('✅ Manejadores IPC de automatización configurados');
}

module.exports = { setupAutomationIpcHandlers };