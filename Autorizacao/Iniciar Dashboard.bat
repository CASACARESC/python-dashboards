@echo off
title Dashboard Autorizacoes
echo Iniciando servidor...

:: Fecha processo Python anterior na porta 3002
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":3002 "') do (
    taskkill /f /pid %%a >nul 2>&1
)
timeout /t 1 >nul

cd /d "%~dp0"

:: Abre o browser em background apos 4s
start "" cmd /c "timeout /t 4 >nul && start http://localhost:3002"

:: Inicia o servidor em foreground — fechar esta janela encerra tudo automaticamente
echo Servidor em http://localhost:3002
echo Feche esta janela para encerrar.
echo.
python app.py
