#!/usr/bin/env bash
# Conector Partelli para a VM Oracle: recebe um pacote tar.gz pela entrada padrao e publica no site.
# Roda como comando forcado da chave de deploy (a chave nao abre shell nem tunel).
# Modos, escolhidos pelo comando SSH enviado pelo GitHub:
#   site   publica a secao Gestao Hospitalar (CSS, JS, configuracao) e a embute no index.html, com backup
#   dados  publica somente os JSON de dados coletados pelos robos (pasta hospital/dados)
set -euo pipefail
WEB_ROOT="${WEB_ROOT:-/var/www/html}"
LOG="${LOG:-$HOME/deploy.log}"
SUDO="${SUDO-sudo}"
MODO="${SSH_ORIGINAL_COMMAND:-}"
exec > >(tee -a "$LOG") 2>&1
case "$MODO" in site|dados) ;; *) echo "ERRO: modo invalido '$MODO' (use site ou dados)"; exit 2 ;; esac
TMP="$(mktemp -d /tmp/partelli-deploy.XXXXXX)"; trap 'rm -rf "$TMP"' EXIT
echo "== $(date -Is) modo=$MODO"
head -c 30000000 | tar xz --no-same-owner -C "$TMP"
H="$WEB_ROOT/hospital"
if [ "$MODO" = "site" ]; then
  [ -f "$TMP/hospital/fragmento.html" ] && [ -f "$TMP/deploy/montar_plataforma.py" ] || { echo "ERRO: pacote do site incompleto"; exit 1; }
  $SUDO install -d -m 755 "$H" "$H/dados" "$H/css" "$H/js" "$H/config"
  for f in css/hospital.css js/hospital.js js/hospital_calc.js js/util.js js/rede.js config/remessas_datasus.json; do
    [ -f "$TMP/hospital/$f" ] || { echo "ERRO: falta hospital/$f"; exit 1; }
    $SUDO install -m 644 "$TMP/hospital/$f" "$H/$f"
  done
  for f in indice.json status_fontes.json; do [ -e "$H/dados/$f" ] || $SUDO install -m 644 "$TMP/hospital/dados/$f" "$H/dados/$f"; done
  $SUDO rm -f "$H/index.html" "$H/fragmento.html"
  if [ -f "$WEB_ROOT/index.html" ]; then
    $SUDO cp -p "$WEB_ROOT/index.html" "$WEB_ROOT/index.html.bak.$(date +%Y%m%d%H%M%S)"
    cp "$WEB_ROOT/index.html" "$TMP/index.html"
    python3 "$TMP/deploy/montar_plataforma.py" "$TMP/index.html" "$TMP/hospital/fragmento.html"
    $SUDO install -m 644 "$TMP/index.html" "$WEB_ROOT/index.html"
    ls -1t "$WEB_ROOT"/index.html.bak.* 2>/dev/null | tail -n +8 | while read -r b; do $SUDO rm -f "$b"; done
  else
    echo "AVISO: $WEB_ROOT/index.html nao existe; secao nao embutida."
  fi
else
  $SUDO install -d -m 755 "$H/dados"
  N=0
  for f in "$TMP"/*.json; do
    [ -e "$f" ] || { echo "ERRO: nenhum JSON no pacote"; exit 1; }
    b="$(basename "$f")"
    [[ "$b" =~ ^[A-Za-z0-9_.-]+\.json$ ]] || { echo "ERRO: nome recusado: $b"; exit 1; }
    python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$f" || { echo "ERRO: JSON invalido: $b"; exit 1; }
    $SUDO install -m 644 "$f" "$H/dados/.$b.novo" && $SUDO mv -f "$H/dados/.$b.novo" "$H/dados/$b"
    N=$((N+1))
  done
  echo "dados publicados: $N arquivos"
fi
[ -z "$SUDO" ] || $SUDO nginx -t >/dev/null 2>&1 || true
echo "== $(date -Is) concluido"
