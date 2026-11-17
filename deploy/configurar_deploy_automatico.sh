#!/usr/bin/env bash
# Rodar UMA vez na VM, com o usuario ubuntu: prepara o deploy automatico pelo GitHub Actions.
# Cria uma chave exclusiva, que so executa o recebedor de deploy (sem shell, sem tunel).
set -euo pipefail
cd "$(dirname "$0")/.."
sudo install -m 755 -o root -g root deploy/receber_deploy.sh /usr/local/bin/partelli-receber-deploy
CH="$HOME/.ssh/partelli_deploy_ci"
if [ ! -f "$CH" ]; then ssh-keygen -q -t ed25519 -N "" -C "github-actions-partelli" -f "$CH"; fi
mkdir -p "$HOME/.ssh"; touch "$HOME/.ssh/authorized_keys"; chmod 600 "$HOME/.ssh/authorized_keys"
PUB="$(cat "$CH.pub")"
grep -qF "$PUB" "$HOME/.ssh/authorized_keys" || echo "command=\"/usr/local/bin/partelli-receber-deploy\",no-port-forwarding,no-agent-forwarding,no-X11-forwarding,no-pty $PUB" >> "$HOME/.ssh/authorized_keys"
echo
echo "Pronto na VM. Agora cadastre 3 segredos no GitHub (repositorio, Settings, Secrets and variables, Actions):"
echo "  VM_HOST      = $(curl -s -4 --max-time 5 ifconfig.me || echo '[IP publico da VM]')"
echo "  VM_USER      = $(id -un)"
echo "  VM_HOST_KEY  = (linha abaixo)"
ssh-keyscan -t ed25519 localhost 2>/dev/null | sed 's/^localhost/[HOST]/' | head -1
echo "  VM_SSH_KEY   = conteudo da chave privada exibida abaixo (copie ate a ultima linha END e nunca cole em chat)"
echo "----- INICIO DA CHAVE (copie) -----"
cat "$CH"
echo "----- FIM DA CHAVE -----"
