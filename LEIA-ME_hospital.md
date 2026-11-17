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

## Deploy automatico (GitHub Actions para a VM)
A cada push na branch `main`, o GitHub roda os testes e, se passarem, envia o pacote por SSH para a VM, que reinstala o modulo (`deploy/receber_deploy.sh`). A chave de deploy so executa esse recebedor: nao abre shell nem tunel. A VM nao precisa de token do GitHub.
Configuracao unica, na VM: `./deploy/configurar_deploy_automatico.sh`, e cadastrar os segredos `VM_HOST`, `VM_USER`, `VM_HOST_KEY` e `VM_SSH_KEY` no GitHub (Settings, Secrets and variables, Actions). Nunca versionar chaves.
Para reverter um deploy: restaurar o `index.html.bak.*` mais recente em `/var/www/html` e reexecutar o deploy de um commit anterior.
