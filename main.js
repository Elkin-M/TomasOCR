// ============================================
// main.js - VERSIÓN CORREGIDA CON SPAWN
// ============================================

const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const readline = require('readline');

// ✅ Variables globales para el proceso interactivo
let interactivePythonProcess = null;
let interactivePythonStdin = null;

function createWindow() {
    const win = new BrowserWindow({
        width: 1200,
        height: 800,
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            preload: path.join(__dirname, 'preload.js')
        }
    });

    win.loadFile('./frontend/auto.html');
    
    // ✅ Abrir DevTools para debugging (comentar en producción)
    // win.webContents.openDevTools();
    
    return win;
}

// ============================================
// ✅ FUNCIÓN INTERACTIVA CORREGIDA (para auto_service.py)
// ============================================
function executeAutoScript(scriptName, action, args, event) {
    const pythonPath = 'C:\\Users\\Lenovo\\anaconda3\\envs\\IDAutoSENA\\python.exe';
    const scriptPath = path.join(__dirname, 'backend', 'scripts', scriptName);

    return new Promise((resolve) => {
        console.log('🚀 Iniciando proceso Python interactivo...');
        console.log(`   Script: ${scriptName}`);
        console.log(`   Action: ${action}`);
        console.log(`   Args:`, args);

        // ✅ CRÍTICO: Usar spawn con unbuffered mode
        interactivePythonProcess = spawn(pythonPath, [
            '-u',  // ✅ Unbuffered output - MUY IMPORTANTE
            scriptPath,
            action,
            ...args
        ], {
            stdio: ['pipe', 'pipe', 'pipe'],  // ✅ stdin, stdout, stderr
            cwd: path.join(__dirname, 'backend', 'scripts'),
            env: { 
                ...process.env, 
                PYTHONUNBUFFERED: '1',  // ✅ Force unbuffered
                PYTHONIOENCODING: 'utf-8'  // ✅ Encoding correcto
            }
        });

        // ✅ Guardar referencia de stdin
        interactivePythonStdin = interactivePythonProcess.stdin;

        // ✅ CRÍTICO: Establecer codificación UTF-8 para stdout y stderr
        interactivePythonProcess.stdout.setEncoding('utf8');
        interactivePythonProcess.stderr.setEncoding('utf8');

        console.log(`✅ Proceso iniciado (PID: ${interactivePythonProcess.pid})`);
        console.log(`   stdin writable: ${interactivePythonStdin.writable}`);

        let lastResult = null;

        // ✅ Configurar readline para leer línea por línea
        const rl = readline.createInterface({
            input: interactivePythonProcess.stdout,
            crlfDelay: Infinity
        });

        // ✅ Procesar cada línea de stdout
        rl.on('line', (line) => {
            try {
                const parsed = JSON.parse(line);
                const logChannel = scriptName.split('_')[0].toLowerCase();

                console.log(`📥 Python output (${parsed.type}):`, 
                    parsed.type === 'log' ? parsed.message.substring(0, 100) : parsed.type);

                if (parsed.type === 'log') {
                    event.sender.send(`${logChannel}:log`, parsed.message);
                } else if (parsed.type === 'progress') {
                    event.sender.send('auto:progress', parsed);
                } else if (parsed.type === 'user_interaction_required' || parsed.type === 'comparison_preview') {
                    // ✅ Unificar los dos tipos de eventos en uno solo.
                    const interactionType = parsed.type === 'comparison_preview' ? 'comparison_preview' : parsed.interaction;
                    const interactionData = parsed.data || {};

                    console.log(`🔔 Interacción requerida: ${interactionType}`);
                    console.log(`   Datos:`, JSON.stringify(interactionData).substring(0, 200));
                    event.sender.send('auto:require-interaction', {
                        interaction: interactionType,
                        data: interactionData
                    });
                } else {
                    lastResult = parsed;
                }
            } catch (err) {
                // No es JSON, es un mensaje raw
                const logChannel = scriptName.split('_')[0].toLowerCase();
                console.log(`📝 Python raw output:`, line.substring(0, 100));
                event.sender.send(`${logChannel}:log`, `[RAW] ${line}`);
            }
        });

        // ✅ Manejar stderr
        interactivePythonProcess.stderr.on('data', (message) => {
            console.error('🔴 Python stderr:', message);
            event.sender.send('auto:log', `[ERROR] ${message}`);
        });

        // ✅ Manejar cierre del proceso
        interactivePythonProcess.on('close', (code) => {
            console.log(`🏁 Proceso Python cerrado (código: ${code})`);
            
            // ✅ Limpiar referencias
            interactivePythonProcess = null;
            interactivePythonStdin = null;

            if (code !== 0 && code !== null) {
                const errorMsg = `Proceso terminó con código ${code}`;
                console.error(`❌ ${errorMsg}`);
                resolve({ 
                    success: false, 
                    action: action, 
                    error: errorMsg 
                });
            } else if (lastResult) {
                resolve(lastResult);
            } else {
                resolve({ 
                    success: true, 
                    action: action, 
                    message: "Proceso finalizado." 
                });
            }
        });

        // ✅ Manejar errores del proceso
        interactivePythonProcess.on('error', (err) => {
            console.error('❌ Error en proceso Python:', err);
            interactivePythonProcess = null;
            interactivePythonStdin = null;
            resolve({ 
                success: false, 
                action: action, 
                error: err.message || String(err) 
            });
        });
    });
}

// ============================================
// ✅ MANEJADOR CRÍTICO: ENVIAR RESPUESTA A PYTHON
// ============================================
ipcMain.on('auto:interaction-response', (event, responseData) => {
    console.log('📤 Recibida respuesta del frontend');
    console.log('   Tipo:', responseData.interactionType || 'unknown');
    console.log('   Datos:', JSON.stringify(responseData).substring(0, 200));

    if (!interactivePythonProcess || !interactivePythonStdin) {
        console.error('❌ ERROR: No hay proceso Python activo');
        console.error(`   Process: ${!!interactivePythonProcess}`);
        console.error(`   Stdin: ${!!interactivePythonStdin}`);
        event.sender.send('auto:log', '[ERROR] No hay proceso Python activo para recibir la respuesta');
        return;
    }

    if (!interactivePythonStdin.writable) {
        console.error('❌ ERROR: stdin no es escribible');
        event.sender.send('auto:log', '[ERROR] Canal stdin no disponible');
        return;
    }

    try {
        // ✅ CRÍTICO: Extraer solo responseData, NO enviar interactionType
        const dataToSend = responseData.responseData || responseData;
        
        // ✅ CRÍTICO: Agregar \n al final
        const jsonString = JSON.stringify(dataToSend) + '\n';
        
        console.log(`📝 Escribiendo a Python stdin (${jsonString.length} bytes):`);
        console.log(`   ${jsonString.substring(0, 300)}`);

        // ✅ Escribir al stdin
        const success = interactivePythonStdin.write(jsonString, 'utf8');

        if (success) {
            console.log('✅ Datos escritos exitosamente a Python');
            event.sender.send('auto:log', '[INFO] ✅ Respuesta enviada al backend Python');
        } else {
            console.warn('⚠️ Buffer lleno, esperando drain...');
            interactivePythonStdin.once('drain', () => {
                console.log('✅ Buffer drenado, datos enviados');
                event.sender.send('auto:log', '[INFO] ✅ Respuesta enviada (después de drain)');
            });
        }

        // ✅ IMPORTANTE: NO cerrar stdin aquí
        // interactivePythonStdin.end(); // ❌ NUNCA HACER ESTO

    } catch (error) {
        console.error('❌ Error escribiendo a stdin:', error);
        event.sender.send('auto:log', `[ERROR] Fallo al enviar respuesta: ${error.message}`);
    }
});

// ============================================
// CONFIGURACIÓN DE LA APP
// ============================================

app.whenReady().then(() => {
    createWindow();

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow();
        }
    });

    // ✅ Handler para automatización completa
    ipcMain.handle('auto:execute', async (event, ficha, pdfPath) => {
        const action = 'execute';
        const args = [ficha, pdfPath];
        return executeAutoScript('auto_service.py', action, args, event);
    });

    // ✅ Debugging: Verificar estado de Python
    ipcMain.handle('auto:check-status', () => {
        const status = {
            processExists: !!interactivePythonProcess,
            stdinExists: !!interactivePythonStdin,
            stdinWritable: interactivePythonStdin?.writable || false,
            pid: interactivePythonProcess?.pid || null
        };
        console.log('🔍 Estado de Python:', status);
        return status;
    });
    
    // ✅ NUEVO: Abrir archivos con la aplicación predeterminada
    ipcMain.handle('open-file', (event, filePath) => {
        console.log('📂 Abriendo archivo:', filePath);
        const { shell } = require('electron');
        return shell.openPath(filePath);
    });

    // --- Handlers existentes (sin cambios) ---
    // ... (mantener todos los handlers de reportes, sgs, aspirantes, ocr, etc.)
});

app.on('window-all-closed', () => {
    // ✅ Limpiar proceso Python al cerrar
    if (interactivePythonProcess) {
        console.log('🧹 Cerrando proceso Python...');
        if (interactivePythonStdin && interactivePythonStdin.writable) {
            interactivePythonStdin.end();
        }
        interactivePythonProcess.kill();
    }
    
    if (process.platform !== 'darwin') {
        app.quit();
    }
});