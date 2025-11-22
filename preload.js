const { contextBridge, ipcRenderer } = require('electron')

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

    // Auto (Proceso Automatizado Completo)
    autoExecute: (ficha, pdfPath) => ipcRenderer.invoke('auto:execute', ficha, pdfPath),
    onAutoLog: (callback) => ipcRenderer.on('auto:log', (_event, value) => callback(value)),
    onAutoProgress: (callback) => ipcRenderer.on('auto:progress', (_event, value) => callback(value)),
    
    // --- Nuevas funciones para interactividad ---
    onRequireInteraction: (callback) => ipcRenderer.on('auto:require-interaction', (_event, value) => callback(value)),
    sendInteractionResponse: (data) => ipcRenderer.send('auto:interaction-response', data)
});

