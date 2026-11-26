#!/usr/bin/env bash
# Executa no notebook, no usuario configurado no servico (padrao: rafael). Uso: partelli-coleta diaria|semanal|tudo|espelho
# Funciona 100% no notebook: codigo e dados ficam em ~/partelli, a pagina e servida pelo painel local.
# GitHub, Oracle e Codeberg sao opcionais e ficam desligados por padrao (PUBLICAR_GITHUB=0, ATUALIZAR_CODIGO=0, VM_HOST vazio).
# A unica conexao obrigatoria e com o FTP publico do DATASUS.
# Nenhuma credencial neste arquivo: chaves SSH ficam em ~/.ssh e ajustes em /etc/partelli/coleta.env.
set -euo pipefail

MODO="${1:-}"
case "$MODO" in diaria|semanal|tudo|fontes|espelho|site|publicar) ;; *) echo "uso: $0 diaria|semanal|tudo|fontes|espelho|site|publicar" >&2; exit 2 ;; esac

ENV_FILE="${PARTELLI_ENV:-/etc/partelli/coleta.env}"
[ -r "$ENV_FILE" ] && . "$ENV_FILE"

BASE="${PARTELLI_BASE:-$HOME/partelli}"
REPO_URL="${REPO_URL:-git@github.com:rafaelpartelli/gestao-hospitalar.git}"
SALA_URL="${SALA_URL:-https://github.com/rafaelpartelli/sala-gestao.git}"
PUBLICAR_GITHUB="${PUBLICAR_GITHUB:-0}"   # 1 = envia os dados a branch dados do GitHub
ATUALIZAR_CODIGO="${ATUALIZAR_CODIGO:-0}" # 1 = atualiza o codigo pelo GitHub antes de coletar (falha nao interrompe)
CODEBERG_URL="${CODEBERG_URL:-}"          # [PREENCHER: ex. git@codeberg.org:USUARIO/gestao-hospitalar.git]
VM_HOST="${VM_HOST:-}"                    # IP ou dominio da Oracle (vazio = nao envia)
VM_USER="${VM_USER:-ubuntu}"
ORACLE_KEY="${ORACLE_KEY:-$HOME/.ssh/oracle_key}"
GCS_BUCKET="${GCS_BUCKET:-}"              # bucket do Google Cloud lido pelo site (vazio = nao envia)
GCS_KEY="${GCS_KEY:-$BASE/.chave_gcs.json}"   # arquivo da conta de servico, so neste notebook, nunca em codigo
GCS_PY="${GCS_PY:-$BASE/venv_gcs/bin/python}"
SSH_OPTS="-o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new -o BatchMode=yes"
# Chaves proprias dos robos: nao dependem nem alteram o ~/.ssh/config do usuario.
GH_KEY="${GH_KEY:-$HOME/.ssh/partelli_github_key}"
CB_KEY="${CB_KEY:-$HOME/.ssh/partelli_codeberg_key}"
export GIT_SSH_COMMAND="ssh -i $GH_KEY $SSH_OPTS"

mkdir -p "$BASE"/{log,estado,tmp}
LOG="$BASE/log/coleta.log"
exec 9>"$BASE/.lock"
flock -n 9 || { echo "$(date -Is) outra execucao em andamento, saindo" >> "$LOG"; exit 0; }
log() { echo "$(date -Is) [$MODO] $*" | tee -a "$LOG"; }

atualizar_repo() { # $1 = url, $2 = pasta. Com a copia local presente, so atualiza se ATUALIZAR_CODIGO=1 e nunca falha por rede.
  if [ -d "$2/.git" ]; then
    [ "$ATUALIZAR_CODIGO" = "1" ] || return 0
    { git -C "$2" fetch -q origin && git -C "$2" reset -q --hard origin/main; } || log "sem rede para atualizar $2, usando a copia local"
  else git clone -q "$1" "$2" || { log "ERRO: sem copia local de $2 e sem acesso a $1"; exit 1; }; fi
}

# ---------- espelho no Codeberg ----------
if [ "$MODO" = "espelho" ]; then
  [ -n "$CODEBERG_URL" ] || { log "CODEBERG_URL nao definido em $ENV_FILE"; exit 1; }
  ESP="$BASE/espelho.git"
  if [ -d "$ESP" ]; then git -C "$ESP" fetch -q --prune origin '+refs/heads/*:refs/heads/*' '+refs/tags/*:refs/tags/*'
  else git clone -q --bare "$REPO_URL" "$ESP"; git -C "$ESP" fetch -q origin '+refs/heads/*:refs/heads/*'; fi
  GIT_SSH_COMMAND="ssh -i $CB_KEY $SSH_OPTS" git -C "$ESP" push -q --prune "$CODEBERG_URL" 'refs/heads/*:refs/heads/*' 'refs/tags/*:refs/tags/*'
  log "espelho Codeberg atualizado"
  exit 0
fi

# ---------- envio para a Oracle (conector Partelli: so executa partelli-receber-deploy, sem shell) ----------
enviar_oracle() { # $1 = site|dados
  [ -n "$VM_HOST" ] || { log "VM_HOST vazio em $ENV_FILE: envio para a Oracle desligado"; return 2; }
  [ -r "$ORACLE_KEY" ] || { log "chave do conector nao encontrada em $ORACLE_KEY"; return 2; }
  if [ "$1" = "site" ]; then
    tar czf - -C "$REPO" hospital deploy/montar_plataforma.py | ssh -i "$ORACLE_KEY" $SSH_OPTS "$VM_USER@$VM_HOST" site
  else
    ( cd "$DADOS" && ls ./*.json >/dev/null 2>&1 && tar czf - ./*.json | ssh -i "$ORACLE_KEY" $SSH_OPTS "$VM_USER@$VM_HOST" dados )
  fi
}

# ---------- envio ao Google Cloud (site partelli.tec.br le /dados/ deste bucket) ----------
enviar_gcs() {
  [ -n "$GCS_BUCKET" ] || { log "GCS_BUCKET vazio em $ENV_FILE: envio ao Google Cloud desligado"; return 2; }
  [ -r "$GCS_KEY" ] || { log "arquivo da conta de servico nao encontrado em $GCS_KEY"; return 2; }
  [ -x "$GCS_PY" ] || { log "python do venv nao encontrado em $GCS_PY"; return 2; }
  GOOGLE_APPLICATION_CREDENTIALS="$GCS_KEY" "$GCS_PY" "$REPO/deploy/notebook/publicar_gcs.py" "$DADOS" "$GCS_BUCKET" >> "$LOG" 2>&1
}

# ---------- coleta ----------
export ORCAMENTO_TRAFEGO_GB="${ORCAMENTO_TRAFEGO_GB:-6}"
export DISCO_MINIMO_GB="${DISCO_MINIMO_GB:-3}"
REPO="$BASE/repo"; SALA="$BASE/sala-gestao"; DADOS="$BASE/dados_repo"

atualizar_repo "$REPO_URL" "$REPO"
atualizar_repo "$SALA_URL" "$SALA"
# modo fontes: traz sempre os dados mais novos da Sala de Gestao (coletados pelas rotinas automaticas dela no GitHub)
if [ "$MODO" = "fontes" ] && [ -d "$SALA/.git" ]; then
  { git -C "$SALA" fetch -q origin && git -C "$SALA" reset -q --hard origin/main && log "dados da Sala de Gestao atualizados"; } || log "AVISO: sem rede para atualizar a Sala de Gestao, usando a copia local"
fi

if [ "$MODO" = "publicar" ] && [ -n "$GCS_BUCKET" ]; then
  # site novo (Cloud Run): a pagina vai pelo deploy do Cloud Run, aqui seguem so os dados agregados
  enviar_gcs && { log "dados enviados ao Google Cloud ($GCS_BUCKET)"; date -Is > "$BASE/ultima_execucao_${MODO}.txt"; exit 0; } || { log "ERRO no envio ao Google Cloud"; exit 1; }
fi
if [ "$MODO" = "site" ] || [ "$MODO" = "publicar" ]; then
  RES=0
  log "publicando a pagina Gestao Hospitalar em $VM_HOST"
  enviar_oracle site && log "pagina enviada para a Oracle" || { log "ERRO no envio da pagina"; RES=1; }
  if [ "$MODO" = "publicar" ]; then
    enviar_oracle dados && log "dados enviados para a Oracle" || { log "ERRO no envio dos dados"; RES=1; }
  fi
  [ "$RES" -eq 0 ] && date -Is > "$BASE/ultima_execucao_${MODO}.txt"
  exit "$RES"
fi

if [ -d "$DADOS/.git" ]; then
  if [ "$PUBLICAR_GITHUB" = "1" ]; then git -C "$DADOS" fetch -q origin dados 2>/dev/null && git -C "$DADOS" reset -q --hard origin/dados || true; fi
else
  mkdir -p "$DADOS"; git -C "$DADOS" init -q -b dados
  git -C "$DADOS" remote add origin "$REPO_URL" 2>/dev/null || true
  cp "$REPO"/hospital/dados/*.json "$DADOS"/ 2>/dev/null || true
fi

FONTES_LOCAIS="${FONTES_LOCAIS:-}"
export SALA_DADOS="$SALA/dados" PARTELLI_BASE="$BASE"
export PARTELLI_DADOS="$DADOS" PARTELLI_CONFIG="$REPO/config" \
       PARTELLI_REMESSAS="$REPO/hospital/config/remessas_datasus.json" \
       PARTELLI_ESTADO="$BASE/estado" TMPDIR="$BASE/tmp" \
       PYTHONPATH="$REPO/robo:$SALA/robo"

case "$MODO" in
  diaria)  JOBS="coletar_hospital_sih coletar_hospital_sia status_fontes" ;;
  semanal) JOBS="coletar_hospital_cnes coletar_cnes_tabelas sondar_remessas status_fontes" ;;
  fontes)  JOBS="$FONTES_LOCAIS status_fontes" ;;   # FONTES_LOCAIS (opcional, em coleta.env): coletores da Sala rodados aqui, ex.: "sala:coletar_recursos sala:coletar_emendas"
  *)       JOBS="coletar_hospital_sih coletar_hospital_sia coletar_hospital_cnes coletar_cnes_tabelas sondar_remessas status_fontes" ;;
esac
JOBS="${JOBS_OVERRIDE:-$JOBS}"   # uso em testes

FALHAS=0
for J in $JOBS; do
  log "inicio $J"
  if [ "${J#sala:}" != "$J" ]; then   # coletor da Sala de Gestao, executado na pasta dela com o proprio PYTHONPATH
    N="${J#sala:}"
    if [ -f "$SALA/robo/$N.py" ]; then ( cd "$SALA" && PYTHONPATH="$SALA/robo" python3 "robo/$N.py" ) >> "$LOG" 2>&1 || { log "ERRO em $J"; FALHAS=$((FALHAS+1)); }
    else log "coletor $N nao existe na Sala de Gestao"; FALHAS=$((FALHAS+1)); fi
  elif [ -f "$REPO/robo/$J.py" ]; then python3 "$REPO/robo/$J.py" >> "$LOG" 2>&1 || { log "ERRO em $J"; FALHAS=$((FALHAS+1)); }
  else "$J" >> "$LOG" 2>&1 || { log "ERRO em $J"; FALHAS=$((FALHAS+1)); }; fi
done

cd "$DADOS"
git config user.name "robo-partelli"; git config user.email "noreply@partelli.pro"
git add -A
if git diff --cached --quiet; then log "sem mudanca nos dados"
else
  git commit -q -m "Dados $MODO $(date -u +%F) (notebook)"; log "dados gravados no notebook ($DADOS)"
  if [ "$PUBLICAR_GITHUB" = "1" ]; then
    git push -q origin dados && log "dados enviados ao GitHub (branch dados)" || log "AVISO: envio ao GitHub falhou, dados seguem salvos no notebook"
  else log "envio ao GitHub desligado (PUBLICAR_GITHUB=0)"; fi
fi

if [ -n "$VM_HOST" ]; then
  enviar_oracle dados && log "dados enviados para a Oracle" || { log "ERRO no envio para a Oracle"; FALHAS=$((FALHAS+1)); }
else log "envio para a Oracle desligado (VM_HOST vazio)"; fi

if [ -n "$GCS_BUCKET" ] && [ -s "$GCS_KEY" ]; then
  enviar_gcs && log "dados enviados ao Google Cloud ($GCS_BUCKET)" || { log "ERRO no envio ao Google Cloud"; FALHAS=$((FALHAS+1)); }
elif [ -n "$GCS_BUCKET" ]; then
  log "sem chave de conta de servico: o envio ao bucket e feito pela acao do GitHub (Publicar dados), sem chave"
fi

log "fim, robos com erro: $FALHAS"
date -Is > "$BASE/ultima_execucao_${MODO}.txt"
[ "$FALHAS" -eq 0 ]
