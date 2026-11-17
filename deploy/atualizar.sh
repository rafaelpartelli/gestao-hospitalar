#!/usr/bin/env bash
# Atualiza o modulo a partir do git e reaplica a instalacao (nao apaga dados nem hospitais.json).
# Uso na VM:  cd ~/partelli-hospital && ./deploy/atualizar.sh
set -euo pipefail
cd "$(dirname "$0")/.."
git pull --ff-only
chmod +x deploy/*.sh
sudo WEB_ROOT="${WEB_ROOT:-/var/www/html}" bash ./deploy/instalar_oracle.sh
