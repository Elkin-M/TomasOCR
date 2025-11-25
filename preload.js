// ============================================
// preload.js - VERSIÓN CORREGIDA
// ============================================

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('api', {
    // Reportes
    reportesExecute: (ficha) => ipcRenderer.invoke('reportes:execute', ficha),
    onReportesLog: (callback) => ipcRenderer.on('reportes:log', (_event, value) => callback(value)),

    // SGS
    sgsExecute: (ficha) => ipcRenderer.invoke('sgs:execute', ficha),
    onSGSLog: (callback) => ipcRenderer.on('sgs:log', (_event, value) => callback(value)),

    // Aspirantes
    aspirantesExecute: (ficha) => ipcRenderer.invoke('aspirantes:execute', ficha),
    onAspirantesLog: (callback) => ipcRenderer.on('aspirantes:log', (_event, value) => callback(value)),
    
    // OCR
    ocrExecute: (data) => ipcRenderer.invoke('ocr:execute', data),
    onOcrLog: (callback) => ipcRenderer.on('ocr:log', (_event, value) => callback(value)),
    deleteOcrImages: (data) => ipcRenderer.invoke('ocr:deleteImages', data),
    getMostRecentReport: () => ipcRenderer.invoke('ocr:getMostRecentReport'),
    getMostRecentInforme: () => ipcRenderer.invoke('finMatricula:getMostRecentInforme'),

    // ============================================
    // ✅ AUTO (Proceso Automatizado - CORREGIDO)
    // ============================================
    
    autoExecute: (ficha, pdfPath) => {
        console.log('[PRELOAD] autoExecute llamado:', { ficha, pdfPath });
        return ipcRenderer.invoke('auto:execute', ficha, pdfPath);
    },
    
    onAutoLog: (callback) => {
        ipcRenderer.on('auto:log', (_event, value) => callback(value));
    },
    
    onAutoProgress: (callback) => {
        ipcRenderer.on('auto:progress', (_event, value) => callback(value));
    },
    
    // ✅ CRÍTICO: Escuchar interacciones requeridas
    onRequireInteraction: (callback) => {
        ipcRenderer.on('auto:require-interaction', (_event, value) => {
            console.log('[PRELOAD] Interacción requerida:', value.interaction);
            callback(value);
        });
    },
    
    // ✅ CRÍTICO: Enviar respuesta de interacción
    sendInteractionResponse: (data) => {
        console.log('[PRELOAD] Enviando respuesta de interacción:');
        console.log('   Tipo:', data.interactionType);
        console.log('   Datos:', JSON.stringify(data.responseData).substring(0, 200));
        
        // ✅ Log específico según el tipo
        if (data.interactionType === 'ocr_image_selection') {
            const count = data.responseData?.selected_images?.length || 0;
            console.log(`[PRELOAD] → ${count} imágenes seleccionadas`);
        } else if (data.interactionType === 'convocar_aspirantes_confirmation') {
            const count = data.responseData?.confirmed_aspirants?.length || 0;
            console.log(`[PRELOAD] → ${count} aspirantes confirmados`);
        } else if (data.interactionType === 'fin_matricula_confirmation') {
            console.log(`[PRELOAD] → Fin matrícula: ${data.responseData?.confirm}`);
        }
        
        ipcRenderer.send('auto:interaction-response', data);
    },
    
    // ✅ Debugging: Verificar estado de Python
    checkPythonStatus: () => {
        console.log('[PRELOAD] Verificando estado de Python...');
        return ipcRenderer.invoke('auto:check-status');
    },
    
    // ✅ NUEVO: Abrir archivo (para el botón de ver informe)
    openFile: (filePath) => {
        console.log('[PRELOAD] Abriendo archivo:', filePath);
        return ipcRenderer.invoke('open-file', filePath);
    }
});