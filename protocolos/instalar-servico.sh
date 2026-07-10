#!/usr/bin/env bash
# Instala/atualiza o Dashboard Python de Protocolos como serviço systemd no servidor Linux.
# Uso: cd nesta pasta e rode: bash instalar-servico.sh
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="dashboard-protocolos-python"
USER_NAME="$(whoami)"

echo "== Diretório do dashboard: $DIR"

if [ ! -d "$DIR/venv" ]; then
    echo "== Criando venv..."
    python3 -m venv "$DIR/venv"
fi

echo "== Instalando/atualizando dependências..."
"$DIR/venv/bin/pip" install -r "$DIR/requirements.txt"

if [ ! -f "$DIR/.env" ]; then
    echo "AVISO: não existe .env em $DIR."
    echo "Copie o .env.example para .env e preencha DB_USER, DB_PASS e DB_DSN do Oracle antes de continuar."
fi

echo "== Gerando unit do systemd..."
sudo tee "/etc/systemd/system/${SERVICE_NAME}.service" > /dev/null <<EOF
[Unit]
Description=Dashboard Python de Protocolos (Flask/gunicorn)
After=network.target

[Service]
Type=simple
User=${USER_NAME}
WorkingDirectory=${DIR}
ExecStart=${DIR}/venv/bin/gunicorn -w 4 -b 0.0.0.0:3001 app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

echo "== Ativando serviço (inicia com o servidor + reinicia sozinho se cair)..."
sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}"
sudo systemctl restart "${SERVICE_NAME}"

echo
echo "== Status do serviço:"
sudo systemctl status "${SERVICE_NAME}" --no-pager
