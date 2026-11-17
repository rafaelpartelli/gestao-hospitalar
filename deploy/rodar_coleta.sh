#!/usr/bin/env bash
# Executa a coleta do modulo hospitalar, um robo por vez (trava), e guarda o resultado em estado/ultima_execucao_<modo>.json.
# Modos: diaria (SIH e SIA) | semanal (CNES e sondagem das paginas de remessa) | tudo
set -u
MODO="${1:-diaria}"
BASE="$(cd "$(dirname "$0")/.." && pwd)"
ESTADO="${PARTELLI_ESTADO:-$BASE/estado}"
mkdir -p "$ESTADO"
exec 9>"$ESTADO/coleta.lock"
flock -n 9 || { echo "outra coleta em andamento, saindo"; exit 0; }

case "$MODO" in
  diaria) JOBS="coletar_hospital_sih coletar_hospital_sia" ;;
  semanal) JOBS="coletar_hospital_cnes sondar_remessas" ;;
  tudo) JOBS="coletar_hospital_sih coletar_hospital_sia coletar_hospital_cnes sondar_remessas" ;;
  *) echo "modo desconhecido: $MODO"; exit 2 ;;
esac

RES=""; FALHOU=0
for J in $JOBS; do
  INI=$(date +%s)
  timeout 5h python3 "$BASE/robo/$J.py" ; COD=$?
  FIM=$(date +%s)
  echo "$J: codigo $COD em $((FIM-INI)) s"
  RES="$RES\"$J\":{\"codigo\":$COD,\"segundos\":$((FIM-INI))},"
  [ "$COD" -eq 0 ] || FALHOU=1
done
printf '{"modo":"%s","em":"%s","resultados":{%s}}\n' "$MODO" "$(date -Iseconds)" "${RES%,}" > "$ESTADO/ultima_execucao_$MODO.json"
exit $FALHOU
