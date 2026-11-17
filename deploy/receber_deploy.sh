#!/usr/bin/env bash
# Recebe o pacote do GitHub Actions (tar.gz pela entrada padrao) e instala o modulo.
# Roda na VM como comando forcado da chave de deploy: a chave nao abre shell, so executa este script.
# Instalacao: sudo install -m 755 -o root deploy/receber_deploy.sh /usr/local/bin/partelli-receber-deploy
set -euo pipefail
DESTINO="${DESTINO:-$HOME/gestao-hospitalar-release}"
WEB_ROOT="${WEB_ROOT:-/var/www/html}"
LOG="${LOG:-$HOME/deploy.log}"
TMP="$(mktemp -d /tmp/partelli-deploy.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT
exec > >(tee -a "$LOG") 2>&1
echo "== $(date -Is) deploy recebido"
head -c 30000000 | tar xz --no-same-owner -C "$TMP"
[ -f "$TMP/deploy/instalar_oracle.sh" ] || { echo "ERRO: pacote invalido (sem deploy/instalar_oracle.sh)"; exit 1; }
[ -f "$TMP/hospital/fragmento.html" ] || { echo "ERRO: pacote invalido (sem hospital/fragmento.html)"; exit 1; }
rm -rf "$DESTINO.nova"; mv "$TMP" "$DESTINO.nova"; trap - EXIT
rm -rf "$DESTINO"; mv "$DESTINO.nova" "$DESTINO"
chmod +x "$DESTINO"/deploy/*.sh "$DESTINO"/deploy/*.py 2>/dev/null || true
if [ -n "${INSTALADOR:-}" ]; then bash "$INSTALADOR" "$DESTINO"; else sudo WEB_ROOT="$WEB_ROOT" bash "$DESTINO/deploy/instalar_oracle.sh"; fi
echo "== $(date -Is) deploy concluido"
