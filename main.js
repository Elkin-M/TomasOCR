const { app, BrowserWindow, ipcMain, dialog } = require('electron')
const path = require('path')
const { PythonShell } = require('python-shell')
 
// Variable para mantener la referencia al proceso interactivo de Python
let interactivePyShell = null; 

function createWindow () {
    const win = new BrowserWindow({
     width: 1200,
     height: 800,
     webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            preload: path.join(__dirname, 'preload.js') 
     }
    })

    // Carga el archivo HTML de la interfaz
    win.loadFile('./frontend/auto.html') 
}

// --- Nueva función para Scripts Interactivos (auto_service.py) ---
function executeAutoScript(scriptName, action, args, event) {
    const pythonPath = 'C:\\Users\\Lenovo\\anaconda3\\envs\\IDAutoSENA\\python.exe';
    const scriptPath = path.join(__dirname, 'backend', 'scripts');

    return new Promise((resolve) => {
        const options = {
            mode: 'text',
            pythonPath: pythonPath,
            scriptPath: scriptPath,
            args: [action, ...args]
        };

        const pyShell = new PythonShell(scriptName, options);
        interactivePyShell = pyShell; // Guardar referencia para la respuesta

        let lastResult = null;

        pyShell.on('message', (message) => {
            try {
                const parsed = JSON.parse(message);
                const logChannel = scriptName.split('_')[0].toLowerCase();

                if (parsed.type === 'log') {
                    event.sender.send(`${logChannel}:log`, parsed.message);
                } else if (parsed.type === 'progress') {
                    event.sender.send('auto:progress', parsed);
                } else if (parsed.type === 'user_interaction_required') {
                    // ¡Clave! Reenviar solicitud de interacción al frontend y NO resolver la promesa.
                    event.sender.send('auto:require-interaction', parsed);
                } else {
                    lastResult = parsed;
                }
            } catch (err) {
                const logChannel = scriptName.split('_')[0].toLowerCase();
                event.sender.send(`${logChannel}:log`, `[RAW] ${message}`);
            }
   });
 
        pyShell.on('error', (err) => {
            console.error(`${scriptName} error:`, err);
            interactivePyShell = null;
            resolve({ success: false, action: action, error: err.message || String(err) });
        });
 
        pyShell.end((err) => {
            interactivePyShell = null; // Limpiar referencia
            if (err) {
                console.error(`${scriptName} end error:`, err);
                resolve({ success: false, action: action, error: err.message || String(err) });
                return;
            }
            if (lastResult) {
                resolve(lastResult);
            } else {
                resolve({ success: true, action: action, message: "Proceso Python finalizado." });
            }
        });
    });
}
 
 
// --- Función Antigua para Scripts No Interactivos ---
function executePythonScript(scriptName, action, args, event) {
    const pythonPath = 'C:\\Users\\Lenovo\\anaconda3\\envs\\IDAutoSENA\\python.exe'; 
    const scriptPath = path.join(__dirname, 'backend', 'scripts'); 

    return new Promise((resolve) => {
        const options = {
            mode: 'text',
            pythonPath: pythonPath,
            scriptPath: scriptPath,
            args: [action, ...args] 
        };

        let lastResult = null;
        const pyShell = new PythonShell(scriptName, options);

        pyShell.on('message', (message) => {
            try {
                const parsed = JSON.parse(message);
                if (parsed.type === 'log') {
                    event.sender.send(`${scriptName.split('_')[0]}:log`, parsed.message);
                } else {
                    lastResult = parsed;
                }
            } catch (err) {
                event.sender.send(`${scriptName.split('_')[0]}:log`, `[RAW] ${message}`); 
            }
        });
 
        pyShell.on('error', (err) => {
            console.error(`${scriptName} error:`, err);
            resolve({ success: false, action: action, error: err.message || String(err) });
        });

        pyShell.end((err) => {
            if (err) {
                console.error(`${scriptName} end error:`, err);
                resolve({ success: false, action: action, error: err.message || String(err) });
                return;
            }
            if (lastResult) {
                resolve(lastResult);
            } else {
                resolve({ success: true, action: action, message: "Proceso Python finalizado." });
            }
        });
    });
}


app.whenReady().then(() => {
    createWindow()

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow()
        }
    })

    // --- MANEJADORES IPC ---

    // Nuevo: Manejador para la respuesta de interacción del usuario
    ipcMain.on('auto:interaction-response', (event, responseData) => {
        if (interactivePyShell) {
            interactivePyShell.send(JSON.stringify(responseData));
        } else {
            console.error('Se recibió una respuesta de interacción, pero no hay ningún script de Python interactivo en ejecución.');
        }
    });

    // Actualizado: El manejador de 'auto:execute' ahora usa la nueva función interactiva
    ipcMain.handle('auto:execute', async (event, ficha, pdfPath) => {
        const action = 'execute';
        const args = [ficha, pdfPath];
        // Usar la nueva función que permite la interactividad
        return executeAutoScript('auto_service.py', action, args, event);
    });

    // --- Handlers antiguos para otros servicios (no interactivos) ---
    ipcMain.handle('reportes:execute', async (event, ficha) => {
        const action = 'execute';
        const args = [ficha];
        return executePythonScript('reportes_service.py', action, args, event);
    });

    ipcMain.handle('sgs:execute', async (event, ficha) => {
        const action = 'execute';
        const args = [ficha];
        return executePythonScript('sgs_service.py', action, args, event);
    });

    ipcMain.handle('aspirantes:execute', async (event, ficha, informePath) => {
        const action = 'execute';
        const args = [ficha, informePath];
        return executePythonScript('convocar_aspirantes_service.py', action, args, event);
    });

    ipcMain.handle('ocr:execute', async (event, data) => {
        const action = data.action; 
        let args = [];

        switch (action) {
            case 'select_excel':
                const result = await dialog.showOpenDialog({
                    properties: ['openFile'],
                    filters: [{ name: 'Archivos Excel', extensions: ['xlsx', 'xls'] }]
                });
                if (result.canceled || result.filePaths.length === 0) {
                    return { success: false, error: "Selección de archivo Excel cancelada." };
                }
                return { success: true, excelPath: result.filePaths[0] }; 

            case 'convert':
                args.push(data.pdfPath);
                break;
            case 'open_folder':
                args.push(data.folderPath);
                break;
            case 'delete_selected_images':
                args.push(JSON.stringify(data.imagePathsToDelete));
                break;
            case 'process':
                args.push(JSON.stringify(data.selectedImagePaths));
                break;
            default:
                return { success: false, error: `Acción OCR desconocida: ${action}` };
        }

        const pythonResult = await executePythonScript('ocr_service.py', action, args, event);

        if (action === 'process' && pythonResult.success && pythonResult.data) {
            const fs = require('fs');
            const os = require('os');
            const path = require('path');
            const tmpDir = os.tmpdir();
            const extractedDataJsonPath = path.join(tmpDir, `extracted_data_${Date.now()}.json`);
            fs.writeFileSync(extractedDataJsonPath, JSON.stringify(pythonResult.data));
            const comparisonExcelPath = data.comparisonExcelPath;
            if (!comparisonExcelPath) {
                return { success: false, error: 'Ruta del archivo Excel no proporcionada para la comparación.' };
            }
            const compareArgs = [extractedDataJsonPath, comparisonExcelPath];
            const compareResult = await executePythonScript('ocr_service.py', 'compare', compareArgs, event);
            fs.unlinkSync(extractedDataJsonPath);
            return compareResult;
        }
        return pythonResult;
    });

    ipcMain.handle('ocr:deleteImages', async (event, data) => {
        const action = 'delete_selected_images';
        const args = [JSON.stringify(data.imagePaths)];
        return executePythonScript('ocr_service.py', action, args, event);
    });

    ipcMain.handle('ocr:getMostRecentReport', async (event) => {
        const action = 'get_most_recent_report';
        const args = [];
        return executePythonScript('ocr_service.py', action, args, event);
    });

    ipcMain.handle('finMatricula:getMostRecentInforme', async (event) => {
        const action = 'get_most_recent_informe';
        const args = [];
        return executePythonScript('ocr_service.py', action, args, event);
    });
})

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit()
    }
})
