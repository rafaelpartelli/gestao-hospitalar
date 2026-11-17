#!/usr/bin/env bash
# Tenta criar a instancia Arm (VM.Standard.A1.Flex) Always Free na Oracle, repetindo ate haver vaga.
# Roda no SEU computador, com a CLI da Oracle ja configurada (oci setup config). Nenhuma credencial entra neste arquivo.
# Variaveis obrigatorias (OCIDs do console da Oracle):
#   COMPARTMENT_OCID   compartimento da VM atual
#   SUBNET_OCID        sub-rede da VM atual (Instancia, VNIC primaria, Sub-rede)
# Opcionais: SSH_PUB_KEY_FILE (padrao ~/.ssh/id_ed25519.pub), NOME, OCPUS (max 2), MEM_GB (max 12), BOOT_GB (max 100),
#            INTERVALO (segundos, padrao 300), MAX_TENTATIVAS (padrao 0 = sem limite), FORCAR=1 (ignora a trava de A1 existente)
set -uo pipefail
: "${COMPARTMENT_OCID:?defina COMPARTMENT_OCID}"
: "${SUBNET_OCID:?defina SUBNET_OCID}"
SSH_PUB_KEY_FILE="${SSH_PUB_KEY_FILE:-$HOME/.ssh/id_ed25519.pub}"
NOME="${NOME:-partelli-arm}"; OCPUS="${OCPUS:-2}"; MEM_GB="${MEM_GB:-12}"; BOOT_GB="${BOOT_GB:-50}"
INTERVALO="${INTERVALO:-300}"; MAX_TENTATIVAS="${MAX_TENTATIVAS:-0}"
LOG="${LOG:-$HOME/criar_arm_oracle.log}"
log() { printf '%s %s\n' "$(date -Is)" "$*" | tee -a "$LOG"; }

# Trava do plano gratuito: Arm Always Free = ate 2 OCPUs e 12 GB no total, disco total de 200 GB
[ "$OCPUS" -le 2 ] && [ "$MEM_GB" -le 12 ] || { log "ERRO: limite gratuito e 2 OCPUs e 12 GB."; exit 2; }
[ "$BOOT_GB" -ge 47 ] && [ "$BOOT_GB" -le 100 ] || { log "ERRO: disco de boot entre 47 e 100 GB."; exit 2; }
[ -f "$SSH_PUB_KEY_FILE" ] || { log "ERRO: chave publica nao encontrada em $SSH_PUB_KEY_FILE"; exit 2; }
command -v oci >/dev/null || { log "ERRO: CLI da Oracle (oci) nao instalada."; exit 2; }

if [ "${FORCAR:-0}" != "1" ]; then
  EXISTE="$(oci compute instance list --compartment-id "$COMPARTMENT_OCID" --all --query "data[?shape=='VM.Standard.A1.Flex' && \"lifecycle-state\"!='TERMINATED'].\"display-name\"" 2>/dev/null || echo '[]')"
  case "$EXISTE" in *'"'*) log "PARADO: ja existe instancia A1 ($EXISTE). Use FORCAR=1 se tiver certeza de que cabe na cota."; exit 3 ;; esac
fi

ADS="$(oci iam availability-domain list --compartment-id "$COMPARTMENT_OCID" --query 'data[].name' 2>>"$LOG")" || { log "ERRO ao listar dominios de disponibilidade"; exit 4; }
IMG="$(oci compute image list --compartment-id "$COMPARTMENT_OCID" --operating-system 'Canonical Ubuntu' --operating-system-version '24.04' --shape VM.Standard.A1.Flex --sort-by TIMECREATED --sort-order DESC --query 'data[0].id' --raw-output 2>>"$LOG")" || { log "ERRO ao buscar a imagem Ubuntu 24.04 Arm"; exit 4; }
[ -n "$IMG" ] || { log "ERRO: imagem nao encontrada"; exit 4; }
mapfile -t ADLIST < <(python3 -c 'import json,sys; [print(a) for a in json.loads(sys.argv[1])]' "$ADS")
log "Imagem: $IMG | dominios: ${#ADLIST[@]} | alvo: ${OCPUS} OCPUs, ${MEM_GB} GB, disco ${BOOT_GB} GB"

N=0
while :; do
  for AD in "${ADLIST[@]}"; do
    N=$((N+1))
    SAIDA="$(oci compute instance launch --availability-domain "$AD" --compartment-id "$COMPARTMENT_OCID" \
      --shape VM.Standard.A1.Flex --shape-config "{\"ocpus\":$OCPUS,\"memoryInGBs\":$MEM_GB}" \
      --image-id "$IMG" --subnet-id "$SUBNET_OCID" --assign-public-ip true --display-name "$NOME" \
      --ssh-authorized-keys-file "$SSH_PUB_KEY_FILE" --boot-volume-size-in-gbs "$BOOT_GB" 2>&1)"
    COD=$?
    if [ $COD -eq 0 ]; then
      log "SUCESSO na tentativa $N ($AD). Instancia criada: $NOME"; echo "$SAIDA" | head -40 >> "$LOG"; exit 0
    fi
    if echo "$SAIDA" | grep -qiE 'out of (host )?capacity|OutOfHostCapacity|Out of host capacity'; then
      log "tentativa $N ($AD): sem capacidade, tentando de novo"
    elif echo "$SAIDA" | grep -qiE 'TooManyRequests|429'; then
      log "tentativa $N: limite de requisicoes, aguardando mais"; sleep 120
    else
      log "PARADO na tentativa $N: erro diferente de falta de capacidade:"; echo "$SAIDA" | tail -8 | tee -a "$LOG"; exit 5
    fi
    [ "$MAX_TENTATIVAS" -gt 0 ] && [ "$N" -ge "$MAX_TENTATIVAS" ] && { log "Limite de tentativas atingido."; exit 6; }
  done
  sleep $((INTERVALO + RANDOM % 60))
done
