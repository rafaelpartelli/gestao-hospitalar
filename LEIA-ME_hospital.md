# Gestão Hospitalar (perfil do diretor), Plataforma Partelli

Módulo para diretores e gestores de unidade hospitalar entenderem o faturamento SUS e os demais serviços da unidade. Página estática em `hospital/`, robôs de coleta em Python (somente biblioteca padrão) e instalador para a VM Oracle Always Free.

Marca: somente Partelli. Rodapé: Rafael Partelli, CRA/ES 15721, partelli.pro, aviso LGPD, 2026.

## O que o diretor encontra na página

| Aba | Conteúdo | Origem dos dados |
|---|---|---|
| Resumo executivo | AIHs aprovadas, valor aprovado, média por AIH, rejeição, perda por rejeição, não processadas, composição SH e SP, permanência média, ambulatório (aprovado e diferença), críticas abertas, leitura para a direção, comparativo entre competências (delta B menos A), meta lançada pelo gestor, sugestões e próximo passo | Cálculo da plataforma sobre os valores coletados ou lançados |
| Faturamento hospitalar (SIH) | Lançamento do resumo mensal, procedimentos de maior valor, causas por capítulo do CID-10, especialidade, motivos de rejeição (código), oportunidade frente a benchmark lançado | Robô SIH (RD, RJ, ER) ou lançamento |
| Produção ambulatorial (SIA) | Valor apresentado, aprovado e diferença, por grupo, procedimento e financiamento | Robô SIA (PA) |
| Remessas e prazos | Os 4 portais (SIHD, SIASUS, CIHA, Transmissor) com todos os relatórios, para que servem, link oficial e status. Lançamento da situação da remessa e do prazo final, com contagem de dias | Consulta manual no portal e lançamento |
| Estabelecimento (CNES) | Tipo de unidade, leitos, serviços especializados, habilitações, profissionais por grupo de CBO, comparação de similaridade entre dois CNES, card do ElastiCNES | Robô CNES (ST, LT, SR, HB, PF) |
| Críticas e plano | Críticas automáticas por severidade, críticas não avaliadas por falta de dado, plano de avanço (ganho estimado lançado, nunca calculado), exportação CSV, backup dos lançamentos | Regras da seção 6 do documento de orientação |
| Fontes e status | Cada fonte com status (Ativa, Em teste, Manual, Bloqueada, A confirmar) e pendências | Configuração e sondagem |

Fórmulas: as 15 da seção 4.1 do documento de orientação, em `hospital/js/hospital_calc.js` (cobertas por 16 testes em `tests/test_hospital_calc.mjs`). Sem valor lançado, o campo mostra `[PREENCHER: ...]`.

## Robôs

| Robô | Fonte | Agenda (Brasília) | Status |
|---|---|---|---|
| `coletar_hospital_sih.py` | FTP DATASUS, SIH: RD (aprovadas), RJ (rejeitadas), ER (erros) | diária, 02:30 | Em teste |
| `coletar_hospital_sia.py` | FTP DATASUS, SIA: PA (apresentado e aprovado) | diária, 02:30 | Em teste |
| `coletar_hospital_cnes.py` | FTP DATASUS, CNES: ST, LT, SR, HB, PF | segunda, 04:30 | Em teste |
| `sondar_remessas.py` | robots.txt e resposta das 4 páginas de remessa e do ElastiCNES | segunda, 04:30 | Em teste |

Cada coletor tem o modo `--sondar`, que baixa o menor arquivo (UF do Amapá) e imprime só os nomes dos campos. Rode antes da primeira coleta: os layouts dos arquivos RJ, ER, PA, HB e SR vieram de conhecimento prévio e não foram confirmados em campo. O coletor para com mensagem clara se faltar um campo obrigatório e registra no JSON os campos opcionais ausentes.

Os coletores reaproveitam `comum.py` e `dbc.py` da Sala de Gestão. O instalador procura essas peças e, se preciso, clona o repositório público.

## Proteções do plano gratuito

Limites do Always Free conferidos na documentação da Oracle: 2 VMs AMD Micro (1/8 OCPU e 1 GB cada), 200 GB de disco somente no total (boot mais blocos) e 10 TB por mês de saída de dados. Este módulo serve páginas estáticas e só baixa arquivos (entrada).

- Download para disco temporário e leitura por mmap (memória baixa na VM de 1 GB), com remoção do arquivo ao terminar.
- Orçamento mensal de download (padrão 6 GB, `ORCAMENTO_TRAFEGO_GB`), registrado em `estado/`. Estourou, o robô para.
- Para com menos de 3 GB livres em disco (`DISCO_MINIMO_GB`).
- Não baixa de novo arquivo já processado (mesmo nome e tamanho).
- Um robô por vez (trava `flock`), `Nice=15`, E/S ociosa e `MemoryMax=700M` no systemd.
- Nenhum recurso pago é criado. Não troque a forma da VM nem aumente o disco acima da cota.

## Instalação

1. Copie a pasta para a VM e rode: `sudo ./deploy/instalar_oracle.sh`
2. Se o instalador não achar a raiz do site: `sudo WEB_ROOT=/caminho ./deploy/instalar_oracle.sh`
3. Edite `/opt/partelli/hospital/config/hospitais.json` com o CNES autorizado.
4. Rode `--sondar` em cada coletor e confirme os campos.
5. Coleta de teste: `sudo systemctl start partelli-hospital-diaria.service`
6. Inclua o link `/hospital/` no menu lateral da plataforma.

O instalador roda os 13 testes antes de agendar e não agenda nada se falharem.

## Regras respeitadas

- Sem dado inventado. Os arquivos entregues não têm hospital, valor ou resultado de exemplo.
- Sem dado pessoal: o número da AIH é usado só em memória para ligar RJ e ER e nunca é gravado. Nome, CPF, CNS, CNPJ, endereço, telefone e e-mail estão em lista de campos proibidos.
- Sem credencial em código ou em tela.
- Nome de hospital só aparece no índice se `autorizado` for verdadeiro.
- Os lançamentos manuais ficam no navegador de quem lança (armazenamento local), com exportação e importação em JSON. Não vão para o servidor.
- Páginas de remessa do DATASUS: status Manual. A leitura automática do SIHD foi negada pelo robots.txt em 16/11/2026 e a plataforma não contorna bloqueio.
- ElastiCNES: consta como fonte descartada nas regras do projeto (a rota de relatórios do Kibana expõe tarefas de outros usuários). A plataforma só oferece o link e os passos do filtro `tipo_estabelecimento`. O CNES da unidade vem do FTP oficial.

## Pendências

- [PREENCHER: CNES autorizado, UF e nome autorizado da unidade]
- [PREENCHER: competência inicial para teste]
- [PREENCHER: tabela SIGTAP da competência (descrição e valores oficiais)]
- [PREENCHER: lista oficial de internações sensíveis à atenção primária]
- [PREENCHER: descrição dos códigos de erro de rejeição do SIH]
- [PREENCHER: tabelas oficiais de tipo de unidade e de financiamento, para conferir os rótulos]
- [PREENCHER: portarias de habilitação de cada serviço]
- [PREENCHER: onde estão as saídas dos robôs de produção SIA e SIH já existentes (roboms e robo_producao_es), para integrar em vez de coletar de novo]

## O que não foi testado

O ambiente de desenvolvimento não alcança o FTP do DATASUS. Foram testados: fórmulas, agregações, gravação, guardas de orçamento e disco, trava de execução, interface em 1280 e 390 px sem erro de console e sem rolagem horizontal. Não foram testados: download real, leitura de .dbc real pelo caminho mmap e os nomes de campos dos arquivos RJ, ER, PA, SR e HB. Por isso todas as fontes saem como Em teste.

## Atualizacao via git
Na VM: `cd ~/partelli-hospital && ./deploy/atualizar.sh`. O script faz `git pull`, roda os testes e reaplica os arquivos sem apagar dados coletados nem `/opt/partelli/hospital/config/hospitais.json`.
Nunca versionar chave SSH, `.env`, dados coletados ou o `hospitais.json` real da VM.

## Integracao na plataforma
O modulo nao e uma pagina separada: vira a secao `#gestao-hospitalar` do index.html da plataforma (menu lateral, CSS escopado e JS). `deploy/montar_plataforma.py` faz a montagem, com backup `.bak` do index, e e idempotente. A pasta `/hospital/` do servidor guarda apenas dados, configuracao, CSS e JS.

## Arquitetura: robos no GitHub, site na Oracle
- **Robos e automacoes rodam no GitHub Actions** (`.github/workflows/coleta.yml`): SIH e SIA todo dia 02:30, CNES e remessas toda segunda 04:30 (Brasilia). Os JSON agregados ficam na branch `dados` (historico) e sao enviados a Oracle.
- **O site fica na Oracle** (nginx). A VM so serve arquivos estaticos.
- **Conector Oracle** = `deploy/receber_deploy.sh` com chave SSH de comando forcado (modos `site` e `dados`). A chave nao abre shell nem tunel.
- `.github/workflows/site.yml`: testes e publicacao da secao Gestao Hospitalar a cada alteracao em `hospital/`.

Configuracao unica na VM: `./deploy/conectar_oracle.sh`. Depois, cadastrar `VM_HOST`, `VM_USER`, `VM_HOST_KEY` e `VM_SSH_KEY` em Settings, Secrets and variables, Actions, e criar o ambiente `producao` (com aprovacao opcional).
Reverter o site: restaurar o `index.html.bak.*` mais recente em `/var/www/html` (os 7 ultimos ficam guardados).
Observacao: se o FTP do DATASUS recusar conexoes vindas do GitHub, registrar o bloqueio e manter o lancamento manual. Nao contornar.

## Criar a instancia Arm gratuita na Oracle
`deploy/criar_arm_oracle.sh` repete a criacao de uma VM.Standard.A1.Flex (Ubuntu 24.04, ate 2 OCPUs e 12 GB, o limite Always Free) ate haver vaga na regiao principal. Roda no computador do gestor, com a CLI da Oracle configurada (`oci setup config`). Nao guarda credenciais. Trava limites acima da cota gratuita e para sozinho em qualquer erro que nao seja falta de capacidade.

## Executor no notebook e copia no Codeberg

Motivo: o agendamento do GitHub Actions teve atrasos e descarta execucoes com mais de 30 minutos de atraso. Os robos passam a rodar em um notebook (Ubuntu Server 24.04 ou Lubuntu 24.04) com timers systemd. O GitHub continua como repositorio, o site continua na Oracle e o Codeberg recebe uma copia diaria.

Arquivos: `deploy/notebook/instalar_notebook.sh` (instalador, roda com sudo) e `deploy/notebook/coletar_local.sh` (executor, instalado como `/usr/local/bin/partelli-coleta`).

Horarios (America/Sao_Paulo): diaria 02:30 (SIH e SIA), semanal segunda 04:30 (CNES e remessas), espelho 06:30. `Persistent=true`: se o notebook estiver desligado no horario, a coleta roda ao ligar.

Instalacao no notebook:
1. `git clone` do repositorio (ou copiar a pasta `deploy/notebook`) e `sudo bash deploy/notebook/instalar_notebook.sh`.
2. Cadastrar as duas chaves PUBLICAS impressas: Deploy key com escrita no GitHub e no Codeberg.
3. Editar `/etc/partelli/coleta.env`: `CODEBERG_URL` e `VM_HOST` (IP da Oracle).
4. Copiar para o notebook a chave do conector da Oracle (gerada por `conectar_oracle.sh`) em `/home/rafael/.ssh/oracle_key`, dono rafael, permissao 600.
5. Testar: `sudo -u rafael partelli-coleta espelho`, depois `sudo systemctl start partelli-coleta@semanal.service` e `tail -f /home/rafael/partelli/log/coleta.log`.

Usuario: tudo roda no usuario `rafael` (padrao do instalador; outro usuario: `PARTELLI_USER=nome`). Chaves proprias `partelli_github_key` e `partelli_codeberg_key`, sem alterar o `~/.ssh/config`.

Credenciais: somente chaves SSH em `~rafael/.ssh` (nunca no repositorio). Primeira conexao com GitHub, Codeberg e Oracle aceita a impressao digital (accept-new): conferir uma vez.
O workflow `coleta.yml` ficou apenas como reserva manual (sem cron).

## Painel FTP do Serverrobo (notebook)

Pagina local para explorar o FTP publico do DATASUS (somente `/dissemin/publicos/`), baixar arquivos com as protecoes dos robos (limite de 6 GB/mes de trafego, disco minimo de 3 GB, um download por vez, confirmacao acima de 200 MB), ver status e disparar coletas.

Instalacao (no notebook): `cd ~/partelli/repo && git pull && sudo bash deploy/notebook/instalar_painel_ftp.sh`.
Acesso: `http://127.0.0.1:8765` no proprio notebook, ou de outro computador por `ssh -L 8765:127.0.0.1:8765 rafael@<ip>`. Token em `/etc/partelli/ftp.env` (nao fica no codigo). Por padrao nao abre a rede; para abrir na rede local, definir `PAINEL_HOST=0.0.0.0` no arquivo e reiniciar (sem HTTPS, usar so em rede confiavel).
O painel nunca le valores de arquivo: o botao Campos mostra apenas nomes de campos e contagem de registros.

### Operacao 100% no notebook

- Coleta: os timers rodam `partelli-coleta`, que usa o codigo ja presente em `~/partelli/repo` e grava os JSON em `~/partelli/dados_repo` (com historico git local). A unica conexao obrigatoria e com o FTP publico do DATASUS.
- Visualizacao: o painel serve a pagina Gestao Hospitalar em `http://127.0.0.1:8765/hospital/` (mesmo token), lendo os JSON direto do notebook.
- GitHub, Oracle e Codeberg sao opcionais e vem desligados: `PUBLICAR_GITHUB=1` (envia os dados), `ATUALIZAR_CODIGO=1` (atualiza o codigo; sem rede, segue com a copia local), `VM_HOST` (envia ao site) e `CODEBERG_URL` (espelho).
- Para atualizar o codigo manualmente: `cd ~/partelli/repo && git pull`.

### Download automatico de arquivos (ES, 2026)

`notebook_app/coleta_ftp.py` baixa do FTP do DATASUS os arquivos `RDES`, `SPES` e `PAES` de 2026 (config em `notebook_app/automacao.json`: ano, UF e pastas) para `~/partelli/ftp_downloads`. Timer `partelli-ftp-es.timer` todos os dias as 03:40. Pula arquivo ja baixado (mesmo tamanho), respeita orcamento de trafego e disco minimo, usa a mesma trava dos robos (nunca dois ao mesmo tempo) e grava `_estado_automacao.json`. Manual: `python3 notebook_app/coleta_ftp.py --listar` (so lista) ou o botao "Baixar agora" do painel. Para mudar ano ou UF, editar `automacao.json`.

### Conversao para SQLite (base agregada)

`notebook_app/converter_sqlite.py` converte os DBC baixados (RDES, SPES, PAES) em `~/partelli/base/producao_es.sqlite`, somando por hospital (CNES), competencia e procedimento. So le colunas de uma lista fixa, conferida contra `PROIBIDOS`: nao grava numero da AIH, nascimento, CEP, municipio de residencia, sexo, idade, raca, CPF, CNS, autorizacao, nota fiscal nem documento de profissional. Tabelas: `rd` (AIH reduzida), `sp` (servicos profissionais), `pa` (ambulatorial), mais `arquivos` (controle de linhas e valor por arquivo). Cada arquivo e conferido (linhas e valor somados na base = lidos do DBC) antes de gravar; reprocessar substitui o arquivo, sem duplicar.
O timer das 03:40 roda `rodar_automacao.py`: baixa o que falta e converte. Manual: `python3 notebook_app/converter_sqlite.py` (converte pendentes), `--resumo` (linhas e valor por arquivo, para conferir com fonte oficial), `--limpar-dias N` (apaga DBC bruto ja convertido ha mais de N dias; desligado por padrao).
`python3 notebook_app/campos_dbc.py` mostra so os nomes de campos de um arquivo de cada tipo.

### Publicar no site (partelli.tec.br, VM Oracle)

O notebook publica direto na VM pelo conector Partelli (`partelli-receber-deploy`, chave sem shell, so aceita os modos `site` e `dados`):
- `partelli-coleta site`: envia a pagina Gestao Hospitalar (HTML embutido, CSS, JS, configuracao).
- `partelli-coleta publicar`: pagina e dados (todos os JSON de `~/partelli/dados_repo`).
- Depois de cada coleta, os dados seguem sozinhos para a Oracle quando `VM_HOST` estiver definido em `/etc/partelli/coleta.env`.
Pre-requisitos no notebook: `VM_HOST=partelli.tec.br`, `VM_USER=<usuario da VM>` em `/etc/partelli/coleta.env` e a chave do conector em `~rafael/.ssh/oracle_key` (permissao 600; copiar do terminal da VM, nunca por chat). A base SQLite agregada e os arquivos DBC nao sobem para o site.
Aviso: a descricao dos codigos do CNES agora vive em `hospital/js/util.js` (o conector da VM so instala arquivos conhecidos; um arquivo novo nao seria publicado).

### Super robo, camada 1: dossie por municipio (ES)

`super_robo/consolidar.py` gera, para Itapemirim, Marataizes, Montanha, Nova Venecia e Sao Mateus (`super_robo/municipios.json`, codigos IBGE conferidos na base SICONFI), um JSON por municipio em `~/partelli/dossie/` com: populacao (IBGE/SICONFI), despesa, receita e pessoal (SICONFI), SIOPS, FNS/InvestSUS, transferencias da Uniao, leitos, equipes, equipamentos, profissionais e rede (CNES), dengue, cobertura de planos (ANS) e a producao SIH e SIA **aprovado** vinda da base SQLite. Cada secao traz fonte, data de coleta e defasagem em dias; sem dado vira `[PREENCHER: ...]` e entra em `pendencias`. Os dados nacionais vem de `SALA_DADOS` (padrao `~/partelli/sala-gestao/dados`). Timer diario as 05:30: `deploy/notebook/instalar_super_robo.sh`.

## Habilitações (CNES HB) e CIHA

- Download automático (ES, 2026): `HBES` (CNES, habilitações) e `CIHAES` (internação e atendimento hospitalar), junto de RD, SP e PA.
- Conversão para a base SQLite, tabelas `hb` e `ciha`. Não são gravados: CNPJ do hospital e do consórcio, CNPJ/CPF do mantenedor, CEP, nascimento, sexo, idade, município de residência, datas de atendimento e saída.
- `hb`: uma linha por habilitação do estabelecimento na competência (código, vigência, portaria, leitos). O código (SGRUPHAB) aparece sem descrição até a tabela de habilitações do SIGTAP ser carregada: pendência registrada no dossiê.
- `ciha`: quantidades, dias de permanência e óbitos. Não tem valor financeiro e não deve ser somado ao SIH sem conferir duplicidade por CNES.
- Dossiê por município: `cnes.habilitacoes` (competência mais recente do HB) e `producao.ciha`.

## Demais grupos do CNES (ST, LT, EQ, PF, SR, EP, IN, RC, EF)

- Download automático (ES, 2026, últimos 3 meses de cada grupo cadastral) em `/dissemin/publicos/CNES/200508_/Dados/<grupo>`.
- Conversão para tabelas agregadas `st`, `lt`, `eq`, `pf`, `sr`, `ep`, `inc`, `rc`, `ef`. Nunca gravados: CNPJ, CEP, conta bancária, contrato, alvará, CPF, CNS, nome e registro de profissional, município de residência do profissional, nomes de equipe e de área.
- Profissionais (`pf`): contagem de vínculos e horas por CNES e CBO. Um profissional com mais de um vínculo conta mais de uma vez.
- Dossiê por município, em `cnes`: `estabelecimentos`, `leitos_por_tipo`, `equipamentos_cadastro`, `profissionais_cadastro`, `servicos_especializados`, `equipes_cadastro`, `habilitacoes`, `incentivos`, `regras_contratuais`, `entidade_filantropica`.
- Descrição de códigos: vem de `tabelas_cnes.json` (gerado por `robo/coletar_cnes_tabelas.py`, status Em teste). Sem esse arquivo o dossiê traz só o código e uma pendência única em `cnes.tabelas_codigos`. Variável opcional `TABELAS_CNES` aponta o caminho.
- Cada seção usa a competência mais recente do próprio grupo e a informa.
