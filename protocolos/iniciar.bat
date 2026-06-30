@echo off
cd /d "%~dp0"
echo Iniciando Dashboard de Protocolos...
echo Buscando dados atualizados do banco...
python "%~dp0atualizar_dados.py"
echo Gerando versao estatica...
python "%~dp0gerar_estatico.py"
start "" "%~dp0dashboard.html"
python -m uvicorn main:app --host 0.0.0.0 --port 3001 --reload
pause
