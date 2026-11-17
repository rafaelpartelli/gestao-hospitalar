#!/usr/bin/env bash
# Rodar UMA vez na VM, como usuario ubuntu: cria o conector Partelli para o GitHub publicar o site e os dados.
# A chave gerada so executa partelli-receber-deploy (sem shell, sem tunel). Os robos deixam de rodar na VM.
set -euo pipefail
cd "$(dirname "$0")/.."
sudo install -m 755 -o root -g root deploy/receber_deploy.sh /usr/local/bin/partelli-receber-deploy
CH="$HOME/.ssh/partelli_conector"
mkdir -p "$HOME/.ssh"; chmod 700 "$HOME/.ssh"
[ -f "$CH" ] || ssh-keygen -q -t ed25519 -N "" -C "github-actions-partelli" -f "$CH"
touch "$HOME/.ssh/authorized_keys"; chmod 600 "$HOME/.ssh/authorized_keys"
PUB="$(cat "$CH.pub")"
grep -qF "$PUB" "$HOME/.ssh/authorized_keys" || echo "command=\"/usr/local/bin/partelli-receber-deploy\",no-port-forwarding,no-agent-forwarding,no-X11-forwarding,no-pty $PUB" >> "$HOME/.ssh/authorized_keys"
# robos e timers antigos da VM: desativar (a coleta agora roda no GitHub)
for t in partelli-hospital-diaria.timer partelli-hospital-semanal.timer; do sudo systemctl disable --now "$t" 2>/dev/null || true; done
echo
echo "Conector pronto. Cadastre no GitHub (repositorio, Settings, Secrets and variables, Actions):"
echo "  VM_HOST     = $(curl -s -4 --max-time 5 ifconfig.me || echo '[IP publico da VM]')"
echo "  VM_USER     = $(id -un)"
echo "  VM_HOST_KEY = $(ssh-keyscan -t ed25519 localhost 2>/dev/null | sed 's/^localhost/[HOST]/' | head -1)"
echo "  VM_SSH_KEY  = a chave privada abaixo (copie do terminal, nunca em chat)"
echo "----- INICIO -----"; cat "$CH"; echo "----- FIM -----"
