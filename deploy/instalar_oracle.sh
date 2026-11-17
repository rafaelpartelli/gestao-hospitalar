#!/usr/bin/env bash
# Instala o modulo Gestao Hospitalar (Partelli) na VM Oracle Cloud Always Free.
# Uso:  sudo ./deploy/instalar_oracle.sh
# Variaveis opcionais:
#   WEB_ROOT      raiz publicada do site (se vazio, tenta descobrir pelo nginx para partelli.tec.br)
#   SALA_ROBO     pasta robo/ da Sala de Gestao (precisa de comum.py e dbc.py). Se vazio, procura e, se preciso, clona o repositorio publico.
#   APP_DIR       destino dos robos e do estado (padrao /opt/partelli/hospital)
#   SERVICE_USER  usuario que roda os robos (padrao: quem chamou o sudo)
# Nada aqui cria recurso pago: so copia arquivos, cria 2 timers do systemd e usa a propria VM.
set -euo pipefail

PKG="$(cd "$(dirname "$0")/.." && pwd)"
APP_DIR="${APP_DIR:-/opt/partelli/hospital}"
SERVICE_USER="${SERVICE_USER:-${SUDO_USER:-$(id -un)}}"
ORCAMENTO_GB="${ORCAMENTO_TRAFEGO_GB:-6}"
DISCO_MIN_GB="${DISCO_MINIMO_GB:-3}"

say() { printf '\n== %s\n' "$*"; }
die() { printf '\nERRO: %s\n' "$*" >&2; exit 1; }
[ "$(id -u)" -eq 0 ] || die "rode com sudo (precisa criar os timers do systemd)."
id "$SERVICE_USER" >/dev/null 2>&1 || die "usuario $SERVICE_USER nao existe."

say "1/7 Conferindo a VM (limites do plano gratuito)"
command -v python3 >/dev/null || die "python3 nao encontrado."
python3 - <<'PY' || die "python3 3.9 ou superior e necessario."
import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)
PY
MEM_MB=$(awk '/MemTotal/ {printf "%d", $2/1024}' /proc/meminfo)
LIVRE_GB=$(df -BG --output=avail / | tail -1 | tr -dc '0-9')
echo "Memoria: ${MEM_MB} MB. Disco livre em /: ${LIVRE_GB} GB."
[ "$LIVRE_GB" -ge 5 ] || die "menos de 5 GB livres em disco. Libere espaco antes de instalar."
[ "$MEM_MB" -ge 700 ] || echo "AVISO: pouca memoria. Os robos leem os arquivos por mmap e rodam um de cada vez, mas confira com 'free -m'."
echo "Always Free: 2 VMs Micro (1/8 OCPU, 1 GB) e 200 GB de disco no total, mais 10 TB/mes de saida de dados. Este modulo so baixa dados (entrada) e serve paginas estaticas."

say "2/7 Descobrindo a raiz do site"
if [ -z "${WEB_ROOT:-}" ]; then
  WEB_ROOT="$(python3 - <<'PY'
import re, subprocess
try:
    out = subprocess.run(["nginx", "-T"], capture_output=True, text=True, timeout=20).stdout
except Exception:
    out = ""
atual = None
for linha in out.splitlines():
    l = linha.strip()
    if l.startswith("server_name") and "partelli.tec.br" in l:
        atual = True
    elif atual and l.startswith("root "):
        print(l.split()[1].rstrip(";")); break
    elif l.startswith("server {"):
        atual = None
PY
)"
fi
[ -n "${WEB_ROOT:-}" ] && [ -d "$WEB_ROOT" ] || die "nao achei a raiz do site. Rode: sudo WEB_ROOT=/caminho/do/site $0"
echo "Raiz do site: $WEB_ROOT"

say "3/7 Localizando comum.py e dbc.py da Sala de Gestao"
if [ -z "${SALA_ROBO:-}" ]; then
  for c in /opt/partelli/sala-gestao/robo "/home/$SERVICE_USER/sala-gestao/robo" "/home/$SERVICE_USER/sala_gestao/robo" /opt/partelli/sala_gestao/robo; do
    [ -f "$c/comum.py" ] && { SALA_ROBO="$c"; break; }
  done
fi
if [ -z "${SALA_ROBO:-}" ]; then
  command -v git >/dev/null || die "git nao encontrado e SALA_ROBO nao informado."
  mkdir -p /opt/partelli && chown "$SERVICE_USER" /opt/partelli
  sudo -u "$SERVICE_USER" git clone --depth 1 https://github.com/rafaelpartelli/sala-gestao /opt/partelli/sala-gestao
  SALA_ROBO=/opt/partelli/sala-gestao/robo
fi
[ -f "$SALA_ROBO/comum.py" ] || die "falta $SALA_ROBO/comum.py"
[ -f "$SALA_ROBO/dbc.py" ] || die "falta $SALA_ROBO/dbc.py (leitor de .dbc da v2 da Sala de Gestao). Copie a pasta robo/ do computador do Rafael (Documentos/Site_partelli/sala_gestao/robo) e rode com SALA_ROBO=<pasta>."
echo "Robos da Sala de Gestao: $SALA_ROBO"

say "4/7 Copiando os arquivos"
install -d -o "$SERVICE_USER" "$APP_DIR" "$APP_DIR/robo" "$APP_DIR/config" "$APP_DIR/deploy" "$APP_DIR/estado" "$APP_DIR/tmp" "$APP_DIR/tests"
cp -a "$PKG/robo/." "$APP_DIR/robo/"
cp -a "$PKG/tests/." "$APP_DIR/tests/"
cp -a "$PKG/deploy/rodar_coleta.sh" "$APP_DIR/deploy/" && chmod 755 "$APP_DIR/deploy/rodar_coleta.sh"
[ -f "$APP_DIR/config/hospitais.json" ] || cp "$PKG/config/hospitais.json" "$APP_DIR/config/hospitais.json"
install -d "$WEB_ROOT/hospital"
# A pagina e os JSON de configuracao sao sobrescritos. A pasta dados/ so recebe arquivos iniciais se estiver vazia.
(cd "$PKG/hospital" && find . -path ./dados -prune -o -type f ! -name fragmento.html -print) | while read -r f; do install -D -m 644 "$PKG/hospital/$f" "$WEB_ROOT/hospital/$f"; done
# fragmento.html nao e pagina: so alimenta a montagem da plataforma
rm -f "$WEB_ROOT/hospital/fragmento.html" "$WEB_ROOT/hospital/index.html"
install -d -o "$SERVICE_USER" "$WEB_ROOT/hospital/dados"
if [ -f "$WEB_ROOT/index.html" ]; then
  cp -p "$WEB_ROOT/index.html" "$WEB_ROOT/index.html.bak.$(date +%Y%m%d%H%M%S)"
  python3 "$PKG/deploy/montar_plataforma.py" "$WEB_ROOT/index.html" "$PKG/hospital/fragmento.html" || die "nao consegui embutir o modulo no index.html (backup .bak mantido)."
else
  echo "AVISO: $WEB_ROOT/index.html nao existe; modulo nao embutido."
fi
for f in "$PKG"/hospital/dados/*.json; do [ -e "$WEB_ROOT/hospital/dados/$(basename "$f")" ] || install -m 644 -o "$SERVICE_USER" "$f" "$WEB_ROOT/hospital/dados/"; done
chown -R "$SERVICE_USER" "$APP_DIR"

say "5/7 Rodando os testes (sem internet)"
sudo -u "$SERVICE_USER" env ROBO_EXTRA="$SALA_ROBO" python3 -I -m unittest discover -s "$APP_DIR/tests" -p "test_hospital.py" || die "testes falharam. Nada foi agendado."

say "6/7 Criando os agendamentos (systemd, horario de Brasilia)"
ENVS="Environment=PARTELLI_DADOS=$WEB_ROOT/hospital/dados
Environment=PARTELLI_CONFIG=$APP_DIR/config
Environment=PARTELLI_ESTADO=$APP_DIR/estado
Environment=PARTELLI_REMESSAS=$WEB_ROOT/hospital/config/remessas_datasus.json
Environment=PYTHONPATH=$APP_DIR/robo:$SALA_ROBO
Environment=TMPDIR=$APP_DIR/tmp
Environment=ORCAMENTO_TRAFEGO_GB=$ORCAMENTO_GB
Environment=DISCO_MINIMO_GB=$DISCO_MIN_GB"
for modo in diaria semanal; do
cat > "/etc/systemd/system/partelli-hospital-$modo.service" <<EOF
[Unit]
Description=Partelli Gestao Hospitalar, coleta $modo
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=$SERVICE_USER
WorkingDirectory=$APP_DIR
$ENVS
ExecStart=$APP_DIR/deploy/rodar_coleta.sh $modo
Nice=15
IOSchedulingClass=idle
MemoryMax=700M
TimeoutStartSec=6h
EOF
done
cat > /etc/systemd/system/partelli-hospital-diaria.timer <<EOF
[Unit]
Description=Coleta diaria SIH e SIA (02:30, Brasilia)
[Timer]
OnCalendar=*-*-* 02:30:00 America/Sao_Paulo
RandomizedDelaySec=10min
Persistent=true
[Install]
WantedBy=timers.target
EOF
cat > /etc/systemd/system/partelli-hospital-semanal.timer <<EOF
[Unit]
Description=Coleta semanal CNES e sondagem das paginas de remessa (segunda, 04:30, Brasilia)
[Timer]
OnCalendar=Mon *-*-* 04:30:00 America/Sao_Paulo
RandomizedDelaySec=10min
Persistent=true
[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now partelli-hospital-diaria.timer partelli-hospital-semanal.timer

say "7/7 Pronto"
systemctl list-timers 'partelli-hospital-*' --no-pager || true
cat <<FIM

Modulo embutido na plataforma: https://partelli.tec.br/#gestao-hospitalar  (arquivos em $WEB_ROOT/hospital)
Proximos passos:
  1. Edite $APP_DIR/config/hospitais.json com o CNES autorizado, a UF e (se autorizado) o nome.
  2. Confirme os layouts dos arquivos do DATASUS antes da primeira coleta:
       sudo -u $SERVICE_USER env PYTHONPATH=$APP_DIR/robo:$SALA_ROBO PARTELLI_ESTADO=$APP_DIR/estado TMPDIR=$APP_DIR/tmp python3 $APP_DIR/robo/coletar_hospital_sih.py --sondar
     (repita com coletar_hospital_sia.py e coletar_hospital_cnes.py) e envie a saida para ajuste dos campos.
  3. Coleta de teste agora:  sudo systemctl start partelli-hospital-diaria.service ; journalctl -u partelli-hospital-diaria -n 50
  4. O item Gestao Hospitalar ja entra no menu lateral (montar_plataforma.py).
Guardas ativas: orcamento mensal de ${ORCAMENTO_GB} GB de download, parada com menos de ${DISCO_MIN_GB} GB livres, um robo por vez, limite de 700 MB de memoria.
FIM
