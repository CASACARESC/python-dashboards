@echo off
cd /d "%~dp0"
"%~dp0venv\Scripts\python.exe" "%~dp0atualizar_dados.py" >> "%~dp0sincronizar.log" 2>&1
