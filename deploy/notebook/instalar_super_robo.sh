#!/usr/bin/env bash
# Instala o timer do super robo (dossie por municipio) no Serverrobo. Rodar como root:
#   bash /home/rafael/partelli/repo/deploy/notebook/instalar_super_robo.sh
# Roda todo dia as 21:50, 30 minutos depois da busca das fontes (21:20), para consolidar e exportar os dados do painel.
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "Rode como root."; exit 1; }
USUARIO="${PARTELLI_USER:-rafael}"
HOME_U="$(getent passwd "$USUARIO" | cut -d: -f6)"
APP="$HOME_U/partelli/repo/super_robo/consolidar.py"
[ -f "$APP" ] || { echo "Nao achei $APP. Rode antes: su $USUARIO -c 'cd ~/partelli/repo && git pull'"; exit 1; }
install -d -o "$USUARIO" -g "$USUARIO" "$HOME_U/partelli/log" "$HOME_U/partelli/dossie"
cat > /etc/systemd/system/partelli-super.service <<UNIT
[Unit]
Description=Super robo Partelli, dossie por municipio (ES)

[Service]
Type=oneshot
User=$USUARIO
Environment=PARTELLI_BASE=$HOME_U/partelli
ExecStart=/usr/bin/python3 $APP
StandardOutput=append:$HOME_U/partelli/log/super_robo.log
StandardError=append:$HOME_U/partelli/log/super_robo.log
MemoryMax=300M
Nice=10
UNIT
cat > /etc/systemd/system/partelli-super.timer <<UNIT
[Unit]
Description=Agenda do super robo

[Timer]
OnCalendar=*-*-* 21:50:00
Persistent=true
RandomizedDelaySec=120

[Install]
WantedBy=timers.target
UNIT
systemctl daemon-reload
systemctl enable --now partelli-super.timer
systemctl start partelli-super.service || true
sleep 2
tail -n 8 "$HOME_U/partelli/log/super_robo.log" || true
echo "Dossies em $HOME_U/partelli/dossie (um JSON por municipio, mais indice.json)."
