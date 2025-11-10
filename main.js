const { app, BrowserWindow, ipcMain, dialog } = require('electron')
const path = require('path')
const { PythonShell } = require('python-shell')

/**
 * Crea la ventana principal de la aplicación.
 */
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
    win.loadFile('./frontend/OCR.html') 
}

// Función auxiliar para ejecutar el script de Python
function executePythonScript(scriptName, action, args, event) {
    // RUTA PYTHON: AJUSTAR A SU INTÉRPRETE DE CONDA (IDAutoSENA)
    const pythonPath = 'C:\\Users\\Lenovo\\anaconda3\\envs\\IDAutoSENA\\python.exe'; 
    // RUTA SCRIPT: Ajustar si la estructura de carpetas es diferente (asumiendo que main.js está un nivel arriba de backend/scripts)
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
                    // Envía logs al frontend
                    event.sender.send(`${scriptName.split('_')[0]}:log`, parsed.message);
                } else {
                    // Guarda el último resultado JSON (el resultado final)
                    lastResult = parsed;
                }
            } catch (err) {
                event.sender.send(`${scriptName.split('_')[0]}:log`, `[RAW] ${message}`); 
            }
        });

        pyShell.on('error', (err) => {
            console.error(`${scriptName} error:`, err);
            // Asegurarse de que el objeto resuelto incluya 'action'
            resolve({ success: false, action: action, error: err.message || String(err) });
        });

        pyShell.end((err) => {
            if (err) {
                console.error(`${scriptName} end error:`, err);
                // Asegurarse de que el objeto resuelto incluya 'action'
                resolve({ success: false, action: action, error: err.message || String(err) });
                return;
            }
            if (lastResult) {
                resolve(lastResult);
            } else {
                // Asegurarse de que el objeto resuelto incluya 'action'
                resolve({ success: true, action: action, message: "Proceso Python finalizado sin resultados JSON explícitos." });
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

    // --- MANEJADOR IPC PARA OCR (Implementación de todos los pasos) ---
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
                // Lógica para abrir el diálogo de selección de archivo
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
            case 'delete_selected_images': // NUEVO: Maneja la acción de eliminar imágenes
                // data.imagePathsToDelete debe ser una lista de rutas de imágenes (JSON stringificado)
                args.push(JSON.stringify(data.imagePathsToDelete));
                break;
            case 'process':
                args.push(JSON.stringify(data.selectedImagePaths));
                break;
            default:
                return { success: false, error: `Acción OCR desconocida: ${action}` };
        }

        // Ejecutar el script de Python con la acción y argumentos
        const pythonResult = await executePythonScript('ocr_service.py', action, args, event);

        // Si la acción es 'process', guardar los datos extraídos en un archivo temporal y luego realizar la comparación
        if (action === 'process' && pythonResult.success && pythonResult.data) {
            const fs = require('fs');
            const os = require('os');
            const path = require('path');
            const tmpDir = os.tmpdir();
            const extractedDataJsonPath = path.join(tmpDir, `extracted_data_${Date.now()}.json`);

            // Guardar los datos extraídos en un archivo temporal
            fs.writeFileSync(extractedDataJsonPath, JSON.stringify(pythonResult.data));

            // Llamar a la acción 'compare' con la ruta del archivo temporal y la ruta del archivo Excel
            const comparisonExcelPath = data.comparisonExcelPath; // Asegúrate de que la ruta del Excel se pasa desde el frontend
            if (!comparisonExcelPath) {
                return { success: false, error: 'Ruta del archivo Excel no proporcionada para la comparación.' };
            }
            const compareArgs = [extractedDataJsonPath, comparisonExcelPath];
            const compareResult = await executePythonScript('ocr_service.py', 'compare', compareArgs, event);

            // Eliminar el archivo temporal después de la comparación
            fs.unlinkSync(extractedDataJsonPath);

            return compareResult;
        }

        return pythonResult;
    });

    ipcMain.handle('ocr:deleteImages', async (event, data) => {
        const action = 'delete_selected_images';
        const args = [JSON.stringify(data.imagePaths)]; // imagePaths should be an array of paths
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
