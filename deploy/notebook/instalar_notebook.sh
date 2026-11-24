#!/usr/bin/env bash
# Instala o executor dos robos no notebook (Ubuntu Server 24.04 ou Lubuntu 24.04). Rodar com sudo ou como root.
# Roda no usuario indicado em PARTELLI_USER (padrao: rafael; criado so se nao existir). Nao altera o ~/.ssh/config dele.
# Timers systemd (diaria, semanal, espelho), desliga suspensao e gera chaves SSH proprias (partelli_github_key, partelli_codeberg_key).
# Nao grava nenhuma credencial: imprime apenas as chaves PUBLICAS para cadastro no GitHub e no Codeberg.
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "Rode com sudo."; exit 1; }
AQUI="$(cd "$(dirname "$0")" && pwd)"

apt-get update -qq
apt-get install -y -qq git python3 openssh-client util-linux ca-certificates
timedatectl set-timezone America/Sao_Paulo

# usuario que executa os robos
USUARIO="${PARTELLI_USER:-rafael}"
id "$USUARIO" >/dev/null 2>&1 || useradd -m -s /bin/bash "$USUARIO"
CASA="$(getent passwd "$USUARIO" | cut -d: -f6)"
install -d -m 700 -o "$USUARIO" -g "$USUARIO" "$CASA/.ssh"
for K in partelli_github_key partelli_codeberg_key; do
  [ -f "$CASA/.ssh/$K" ] || sudo -u "$USUARIO" ssh-keygen -q -t ed25519 -N "" -C "partelli-notebook-${K%_key}" -f "$CASA/.ssh/$K"
done

# script e configuracao
install -m 755 "$AQUI/coletar_local.sh" /usr/local/bin/partelli-coleta
install -d -m 750 -o root -g "$USUARIO" /etc/partelli
if [ ! -f /etc/partelli/coleta.env ]; then
  cat > /etc/partelli/coleta.env <<'ENV'
# Sem senha aqui. Preencha somente enderecos.
REPO_URL=git@github.com:rafaelpartelli/gestao-hospitalar.git
# [PREENCHER: URL SSH do repositorio no Codeberg, ex. git@codeberg.org:USUARIO/gestao-hospitalar.git]
CODEBERG_URL=
# [PREENCHER: IP ou dominio da VM Oracle, para enviar os dados ao site (deixe vazio para desligar)]
VM_HOST=
VM_USER=ubuntu
ENV
fi
chown root:"$USUARIO" /etc/partelli/coleta.env; chmod 640 /etc/partelli/coleta.env

# unidades systemd
cat > /etc/systemd/system/partelli-coleta@.service <<UNIT
[Unit]
Description=Partelli coleta (%i)
After=network-online.target
Wants=network-online.target
[Service]
Type=oneshot
User=$USUARIO
ExecStart=/usr/local/bin/partelli-coleta %i
Nice=10
IOSchedulingClass=idle
MemoryMax=700M
TimeoutStartSec=5h
UNIT
mk_timer() { # nome, agenda, instancia
cat > /etc/systemd/system/partelli-$1.timer <<UNIT
[Unit]
Description=Partelli $1
[Timer]
OnCalendar=$2
Persistent=true
RandomizedDelaySec=120
Unit=partelli-coleta@$3.service
[Install]
WantedBy=timers.target
UNIT
}
mk_timer diaria  "*-*-* 02:30:00" diaria      # SIH e SIA
mk_timer semanal "Mon *-*-* 04:30:00" semanal  # CNES e remessas
mk_timer espelho "*-*-* 06:30:00" espelho      # copia no Codeberg

# o notebook nao pode suspender
systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target >/dev/null
mkdir -p /etc/systemd/logind.conf.d
printf '[Login]\nHandleLidSwitch=ignore\nHandleLidSwitchExternalPower=ignore\nHandleLidSwitchDocked=ignore\nIdleAction=ignore\n' > /etc/systemd/logind.conf.d/partelli.conf
systemctl restart systemd-logind || true

systemctl daemon-reload
systemctl enable --now partelli-diaria.timer partelli-semanal.timer partelli-espelho.timer

echo
echo "Instalado. Agora cadastre as chaves PUBLICAS (nunca a privada):"
echo "--- GitHub: Settings do repositorio gestao-hospitalar > Deploy keys > Add (marcar Allow write access)"
cat "$CASA/.ssh/partelli_github_key.pub"
echo "--- Codeberg: Settings do repositorio > Deploy keys > Add (marcar acesso de escrita)"
cat "$CASA/.ssh/partelli_codeberg_key.pub"
echo
echo "Opcional, em /etc/partelli/coleta.env: PUBLICAR_GITHUB=1, ATUALIZAR_CODIGO=1, CODEBERG_URL e VM_HOST. Por padrao tudo roda so no notebook."
echo "Usuario dos robos: $USUARIO (pasta de trabalho: $CASA/partelli, log: $CASA/partelli/log/coleta.log)"
echo "Teste: sudo -u $USUARIO /usr/local/bin/partelli-coleta espelho"
echo "Proximas execucoes: systemctl list-timers 'partelli-*'"
