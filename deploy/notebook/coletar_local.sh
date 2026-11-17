#!/usr/bin/env bash
# Executa no notebook (usuario partelli). Uso: partelli-coleta diaria|semanal|tudo|espelho
# Robos rodam aqui, os dados vao para a branch "dados" no GitHub, para a Oracle (modo dados)
# e o codigo e os dados ganham copia no Codeberg (modo espelho).
# Nenhuma credencial neste arquivo: chaves SSH ficam em ~/.ssh e ajustes em /etc/partelli/coleta.env.
set -euo pipefail

MODO="${1:-}"
case "$MODO" in diaria|semanal|tudo|espelho) ;; *) echo "uso: $0 diaria|semanal|tudo|espelho" >&2; exit 2 ;; esac

ENV_FILE="${PARTELLI_ENV:-/etc/partelli/coleta.env}"
[ -r "$ENV_FILE" ] && . "$ENV_FILE"

BASE="${PARTELLI_BASE:-$HOME/partelli}"
REPO_URL="${REPO_URL:-git@github.com:rafaelpartelli/gestao-hospitalar.git}"
SALA_URL="${SALA_URL:-https://github.com/rafaelpartelli/sala-gestao.git}"
CODEBERG_URL="${CODEBERG_URL:-}"          # [PREENCHER: ex. git@codeberg.org:USUARIO/gestao-hospitalar.git]
VM_HOST="${VM_HOST:-}"                    # IP ou dominio da Oracle (vazio = nao envia)
VM_USER="${VM_USER:-ubuntu}"
ORACLE_KEY="${ORACLE_KEY:-$HOME/.ssh/oracle_key}"
SSH_OPTS="-o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new -o BatchMode=yes"

mkdir -p "$BASE"/{log,estado,tmp}
LOG="$BASE/log/coleta.log"
exec 9>"$BASE/.lock"
flock -n 9 || { echo "$(date -Is) outra execucao em andamento, saindo" >> "$LOG"; exit 0; }
log() { echo "$(date -Is) [$MODO] $*" | tee -a "$LOG"; }

atualizar_repo() { # $1 = url, $2 = pasta
  if [ -d "$2/.git" ]; then git -C "$2" fetch -q origin && git -C "$2" reset -q --hard origin/main
  else git clone -q "$1" "$2"; fi
}

# ---------- espelho no Codeberg ----------
if [ "$MODO" = "espelho" ]; then
  [ -n "$CODEBERG_URL" ] || { log "CODEBERG_URL nao definido em $ENV_FILE"; exit 1; }
  ESP="$BASE/espelho.git"
  if [ -d "$ESP" ]; then git -C "$ESP" fetch -q --prune origin '+refs/heads/*:refs/heads/*' '+refs/tags/*:refs/tags/*'
  else git clone -q --bare "$REPO_URL" "$ESP"; git -C "$ESP" fetch -q origin '+refs/heads/*:refs/heads/*'; fi
  git -C "$ESP" push -q --prune "$CODEBERG_URL" 'refs/heads/*:refs/heads/*' 'refs/tags/*:refs/tags/*'
  log "espelho Codeberg atualizado"
  exit 0
fi

# ---------- coleta ----------
export ORCAMENTO_TRAFEGO_GB="${ORCAMENTO_TRAFEGO_GB:-6}"
export DISCO_MINIMO_GB="${DISCO_MINIMO_GB:-3}"
REPO="$BASE/repo"; SALA="$BASE/sala-gestao"; DADOS="$BASE/dados_repo"

atualizar_repo "$REPO_URL" "$REPO"
atualizar_repo "$SALA_URL" "$SALA"

if [ -d "$DADOS/.git" ]; then
  git -C "$DADOS" fetch -q origin dados 2>/dev/null && git -C "$DADOS" reset -q --hard origin/dados || true
elif git ls-remote --exit-code --heads "$REPO_URL" dados >/dev/null 2>&1; then
  git clone -q --branch dados "$REPO_URL" "$DADOS"
else
  mkdir -p "$DADOS"; git -C "$DADOS" init -q -b dados; git -C "$DADOS" remote add origin "$REPO_URL"
  cp "$REPO"/hospital/dados/*.json "$DADOS"/ 2>/dev/null || true
fi

export PARTELLI_DADOS="$DADOS" PARTELLI_CONFIG="$REPO/config" \
       PARTELLI_REMESSAS="$REPO/hospital/config/remessas_datasus.json" \
       PARTELLI_ESTADO="$BASE/estado" TMPDIR="$BASE/tmp" \
       PYTHONPATH="$REPO/robo:$SALA/robo"

case "$MODO" in
  diaria)  JOBS="coletar_hospital_sih coletar_hospital_sia" ;;
  semanal) JOBS="coletar_hospital_cnes sondar_remessas" ;;
  *)       JOBS="coletar_hospital_sih coletar_hospital_sia coletar_hospital_cnes sondar_remessas" ;;
esac
JOBS="${JOBS_OVERRIDE:-$JOBS}"   # uso em testes

FALHAS=0
for J in $JOBS; do
  log "inicio $J"
  if [ -f "$REPO/robo/$J.py" ]; then python3 "$REPO/robo/$J.py" >> "$LOG" 2>&1 || { log "ERRO em $J"; FALHAS=$((FALHAS+1)); }
  else "$J" >> "$LOG" 2>&1 || { log "ERRO em $J"; FALHAS=$((FALHAS+1)); }; fi
done

cd "$DADOS"
git config user.name "robo-partelli"; git config user.email "noreply@partelli.pro"
git add -A
if git diff --cached --quiet; then log "sem mudanca nos dados"
else git commit -q -m "Dados $MODO $(date -u +%F) (notebook)"; git push -q origin dados; log "dados enviados ao GitHub (branch dados)"; fi

if [ -n "$VM_HOST" ] && ls ./*.json >/dev/null 2>&1; then
  tar czf - ./*.json | ssh -i "$ORACLE_KEY" $SSH_OPTS "$VM_USER@$VM_HOST" dados \
    && log "dados enviados para a Oracle" || { log "ERRO no envio para a Oracle"; FALHAS=$((FALHAS+1)); }
else log "envio para a Oracle desligado (VM_HOST vazio)"; fi

log "fim, robos com erro: $FALHAS"
date -Is > "$BASE/ultima_execucao_${MODO}.txt"
[ "$FALHAS" -eq 0 ]
