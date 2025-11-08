const { PythonShell } = require('python-shell');
const path = require('path');

class NotebookService {
    constructor() {
        this.notebooksPath = path.join(__dirname, '../../notebooks');
    }

    async executeSGSNotebook(ficha) {
        return new Promise((resolve, reject) => {
            let options = {
                mode: 'text',
                pythonPath: 'python',
                pythonOptions: ['-u'],
                scriptPath: this.notebooksPath,
                args: [ficha]
            };

            PythonShell.run('00-DeterminarEstado-SGS-.ipynb', options, function (err, results) {
                if (err) reject(err);
                resolve(results);
            });
        });
    }

    async executeOCRNotebook(files) {
        // Implementar lógica OCR
    }
}

module.exports = new NotebookService();
