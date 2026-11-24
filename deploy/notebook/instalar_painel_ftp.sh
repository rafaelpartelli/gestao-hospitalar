#!/usr/bin/env bash
# Instala o Painel FTP no Serverrobo. Rodar como root:  sudo bash deploy/notebook/instalar_painel_ftp.sh
# Variaveis: PARTELLI_USER (padrao rafael), PAINEL_HOST (padrao 127.0.0.1), PAINEL_PORT (padrao 8765).
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "Rode com sudo."; exit 1; }
USUARIO="${PARTELLI_USER:-rafael}"
HOME_U="$(getent passwd "$USUARIO" | cut -d: -f6)"
APP="$HOME_U/partelli/repo/notebook_app/servidor_ftp.py"
[ -f "$APP" ] || { echo "Nao achei $APP. Atualize o repositorio: su $USUARIO -c 'cd ~/partelli/repo && git pull'"; exit 1; }
install -d -m 750 -o root -g "$USUARIO" /etc/partelli
ENV=/etc/partelli/ftp.env
if [ ! -f "$ENV" ]; then
  umask 077
  {
    echo "PAINEL_HOST=${PAINEL_HOST:-127.0.0.1}"
    echo "PAINEL_PORT=${PAINEL_PORT:-8765}"
    echo "PAINEL_TOKEN=$(python3 -c 'import secrets;print(secrets.token_urlsafe(24))')"
    echo "PAINEL_SEGREDO=$(python3 -c 'import secrets;print(secrets.token_hex(32))')"
  } > "$ENV"
  chown root:"$USUARIO" "$ENV"; chmod 640 "$ENV"
  echo "Token criado em $ENV (nao exibido)."
fi
cat > /etc/systemd/system/partelli-ftp.service <<UNIT
[Unit]
Description=Painel FTP do Serverrobo (Partelli)
After=network-online.target
Wants=network-online.target

[Service]
User=$USUARIO
Environment=PARTELLI_BASE=$HOME_U/partelli
EnvironmentFile=$ENV
ExecStart=/usr/bin/python3 $APP
Restart=on-failure
RestartSec=5
MemoryMax=200M
Nice=10
NoNewPrivileges=true
ProtectSystem=full
PrivateTmp=true

[Install]
WantedBy=multi-user.target
UNIT
# Download automatico ES 2026 (RDES, SPES, PAES), todos os dias 03:40, depois da coleta diaria das 02:30
cat > /etc/systemd/system/partelli-ftp-es.service <<UNIT
[Unit]
Description=Download automatico FTP DATASUS, ES (Partelli)
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=$USUARIO
Environment=PARTELLI_BASE=$HOME_U/partelli
ExecStart=/usr/bin/python3 $HOME_U/partelli/repo/notebook_app/rodar_automacao.py
StandardOutput=append:$HOME_U/partelli/log/automacao_ftp.log
StandardError=append:$HOME_U/partelli/log/automacao_ftp.log
MemoryMax=600M
Nice=10
TimeoutStartSec=6h
UNIT
cat > /etc/systemd/system/partelli-ftp-es.timer <<UNIT
[Unit]
Description=Agenda do download automatico FTP, ES

[Timer]
OnCalendar=*-*-* 03:40:00
Persistent=true
RandomizedDelaySec=120

[Install]
WantedBy=timers.target
UNIT
install -d -o "$USUARIO" -g "$USUARIO" "$HOME_U/partelli/log"
systemctl daemon-reload
systemctl enable --now partelli-ftp-es.timer
systemctl enable --now partelli-ftp.service
systemctl restart partelli-ftp.service
sleep 2
systemctl --no-pager --lines=5 status partelli-ftp.service || true
PORTA="$(grep ^PAINEL_PORT= "$ENV" | cut -d= -f2)"
echo
echo "Painel em http://127.0.0.1:$PORTA (no proprio notebook)."
echo "Ver o token:  sudo grep PAINEL_TOKEN $ENV"
echo "Acesso de outro computador, sem abrir a rede:  ssh -L 8765:127.0.0.1:$PORTA $USUARIO@<ip-do-notebook>"
