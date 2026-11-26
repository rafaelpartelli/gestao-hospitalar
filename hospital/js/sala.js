// Tela unica "Gestao hospitalar", nos moldes da Sala de Gestao do partelli.pro: escolha de Estado, Municipio e Estabelecimento
// sempre visivel no topo e, abaixo, Ambulatorio (SIA), Internacoes (SIH), CIHA e Profissionais (CNES) na mesma tela, sem abas.
// Le /dados/rede_<cod>_estab.json e rede_nomes_cnes.json. Textos externos entram so como texto (el). Sem estilo embutido (CSP).
import {el, limpar, carregar, tabela, inteiro, decimal} from './util.js';
import {arr, kpi, cartao, aviso, brl, brlc, num, pct, pend, icone, detalhesTabela, barrasMes, painelEstado, painelFontes} from './rede.js';

const DS = new URL('../', import.meta.url).href + 'dados/';
const IBGE = 'https://servicodados.ibge.gov.br/api/v1/localidades';
const soma = (l, f) => arr(l).reduce((s, x) => s + (num(f(x)) ? f(x) : 0), 0);
const TIPOS = {'05': 'Hospital', '07': 'Hospital', '62': 'Hospital', '01': 'Unidade básica', '02': 'Unidade básica', '73': 'UPA', '70': 'CAPS', '04': 'Policlínica ou ambulatório', '36': 'Policlínica ou ambulatório', '50': 'Vigilância em saúde', '64': 'Vigilância em saúde', '68': 'Vigilância em saúde', '76': 'Vigilância em saúde', '81': 'Vigilância em saúde'};
const tipoTxt = t => { const c = String(t == null ? '' : t).trim().padStart(2, '0'); return t == null || t === '' ? 'tipo sem dado' : (TIPOS[c] || 'Outro tipo (' + c + ')'); };
const ate = (a, b) => { const l = arr(a).map(x => x.competencia || x.mes_processamento).filter(Boolean); return l.length ? (l.length > 1 ? l[0] + ' a ' + l[l.length - 1] : l[0]) : 'sem competência'; };
const dtBr = iso => { const m = String(iso || '').match(/^(\d{4})-(\d{2})-(\d{2})/); return m ? `${m[3]}/${m[2]}/${m[1]}` : ''; };
const media = (a, b) => num(a) && num(b) && b > 0 ? a / b : null;

async function ibge(caminho) {
  try { const r = await fetch(IBGE + caminho); return r.ok ? await r.json() : null; } catch (e) { return null; }
}
function lembrado() {
  try { const s = JSON.parse(localStorage.getItem('partelli_v1') || '{}'); return s && s.mun && /^\d{7}$/.test(String(s.mun.id)) ? {id: String(s.mun.id), uf: s.mun.uf || s.uf || ''} : null; } catch (e) { return null; }
}

export function abaSala() {
  const raiz = el('div', {class: 'rede sala'});
  const E = {rede: null, indice: null, nomes: {}, uf: '', mun: null, estab: '', dados: null, ufs: null, muns: {}};
  const selUF = el('select', {id: 'slUF', 'aria-label': 'Estado'}, el('option', {value: ''}, 'Escolha o estado'));
  const selMun = el('select', {id: 'slMun', 'aria-label': 'Município', disabled: true}, el('option', {value: ''}, 'Escolha o município'));
  const selEst = el('select', {id: 'slEst', 'aria-label': 'Estabelecimento', disabled: true}, el('option', {value: ''}, 'Todos os estabelecimentos'));
  const selo = el('p', {class: 'sl-selo', role: 'status', 'aria-live': 'polite'}, 'Escolha um estado e um município para ver a produção por estabelecimento.');
  const corpo = el('div', {class: 'sl-corpo'});
  const rot = (t, no) => el('label', null, t, no);

  const hero = el('header', {class: 'sl-topo'});
  raiz.append(hero,
    el('div', {class: 'sl-filtros', role: 'group', 'aria-label': 'Escolha do território'},
      rot('Estado', selUF), rot('Município', selMun), rot('Estabelecimento', selEst), selo),
    corpo);
  function pintarHero() {
    limpar(hero);
    const m = E.mun ? E.mun.nome.replace(/ \(dados do robô\)$/, '') : '', ger = E.dados ? dtBr(E.dados.gerado_em) : '';
    hero.append(
      el('p', {class: 'sl-marca'}, 'Gestão hospitalar · Sala do Gestor', ger ? el('span', {class: 'sl-atual'}, ' · Atualizado em ' + ger) : null),
      el('h2', null, m ? m + '/' + (E.uf || '') + ': painel hospitalar 2026' : 'Painel hospitalar do município'),
      el('p', {class: 'sl-lead'}, 'Escolha um estado e um município e a tela reúne, em uma só página, internações, ambulatório, CIHA, profissionais, críticas e habilitações de cada estabelecimento, para saber onde olhar e o que perguntar. Cada bloco mostra a fonte e a data da última coleta.'),
      el('p', {class: 'sl-atalhos'}, [['#sl-h-res', 'Situação em números'], ['#sl-internacoes', 'Internações'], ['#sl-ambulatorio', 'Ambulatório'], ['#sl-profissionais', 'Profissionais'], ['#sl-fontes', 'Fontes oficiais']].map(([h, t]) => el('a', {class: 'sl-atalho', href: h, onclick: ev => { ev.preventDefault(); const a = document.querySelector(h); if (a) a.scrollIntoView({behavior: 'smooth', block: 'start'}); }}, t))),
      el('p', {class: 'sl-lead sl-peq'}, 'Fontes: SIH/SUS, SIA/SUS, CIHA e CNES (DATASUS), coletadas pelo robô Partelli.'));
  }
  pintarHero();

  const nomeEst = c => E.nomes[c] || null;
  const rotuloEst = f => (nomeEst(f.cnes) || 'Sem nome público') + ' (CNES ' + f.cnes + ')';

  async function carregarUF() {
    const l = await ibge('/estados?orderBy=nome');
    E.ufs = arr(l).length ? l.map(u => [u.sigla, u.nome]) : [['ES', 'Espírito Santo']];
    E.ufs.forEach(([s, n]) => selUF.append(el('option', {value: s}, n + ' (' + s + ')')));
  }
  async function carregarMuns(uf) {
    if (!E.muns[uf]) {
      const l = await ibge('/estados/' + uf + '/municipios?orderBy=nome');
      E.muns[uf] = arr(l).length ? l.map(m => [String(m.id), m.nome]) : arr(E.indice && E.indice.municipios).map(m => [String(m.cod), m.nome]);
    }
    limpar(selMun); selMun.append(el('option', {value: ''}, 'Escolha o município'));
    const tem = new Set(arr(E.indice && E.indice.municipios).map(m => String(m.cod).slice(0, 6)));
    E.muns[uf].forEach(([id, nome]) => selMun.append(el('option', {value: id}, nome + (tem.has(id.slice(0, 6)) ? ' (dados do robô)' : ''))));
    selMun.disabled = false;
  }
  function aviso0(txt) { limpar(corpo); corpo.append(aviso(txt)); }

  async function aoMunicipio(id) {
    E.estab = ''; E.dados = null; E.rede = null; limpar(selEst); selEst.append(el('option', {value: ''}, 'Todos os estabelecimentos')); selEst.disabled = true;
    if (!id) { E.mun = null; selo.textContent = 'Escolha um município.'; limpar(corpo); return; }
    E.mun = {id, nome: (selMun.selectedOptions[0] || {}).textContent || ''}; pintarHero();
    selo.textContent = 'Carregando dados...';
    const item = arr(E.indice && E.indice.municipios).find(m => String(m.cod).slice(0, 6) === id.slice(0, 6));
    const arq = item ? await carregar(DS + 'rede_' + item.cod + '_estab.json') : null;
    if (!arq) { selo.textContent = 'Município fora da lista do robô.'; aviso0('Este município ainda não está na lista do robô (hoje: municípios piloto do ES). Os dados abaixo ficam em branco até a coleta cobrir o território. Você pode preencher as etapas da trilha manualmente, com fonte e data.'); return; }
    E.dados = arq; E.rede = await carregar(DS + 'rede_' + item.cod + '.json');
    const sec = arq.secao || {};
    const lista = arr(sec.estabelecimentos).slice().sort((a, b) => (nomeEst(a.cnes) || 'zzz' + a.cnes).localeCompare(nomeEst(b.cnes) || 'zzz' + b.cnes, 'pt-BR'));
    lista.forEach(f => selEst.append(el('option', {value: f.cnes}, rotuloEst(f))));
    selEst.disabled = !lista.length;
    selo.textContent = lista.length ? `${inteiro(lista.length)} estabelecimento(s) com produção ou profissionais. Dados gerados em ${dtBr(arq.gerado_em) || 'data sem registro'}.` : 'Sem estabelecimentos na base.';
    pintar();
  }

  const FONTES = [
    ['CNES (Cadastro Nacional de Estabelecimentos)', 'Caracterização, leitos, serviços, habilitações e profissionais de cada estabelecimento.', 'https://cnes.datasus.gov.br/'],
    ['TabNet DATASUS', 'Conferência de AIH, produção ambulatorial e CNES em agregados.', 'https://datasus.saude.gov.br/informacoes-de-saude-tabnet/'],
    ['SIGTAP', 'Tabela unificada de procedimentos, valores SH e SP, regras e habilitações por competência.', 'https://sigtap.datasus.gov.br/'],
    ['SIOPS', 'Aplicação mínima em saúde (LC 141/2012): 15% nos municípios e 12% nos estados.', 'https://siops.datasus.saude.gov.br/'],
    ['Fundo Nacional de Saúde', 'Repasses fundo a fundo, propostas e emendas.', 'https://consultafns.saude.gov.br/'],
    ['Diário Oficial da União', 'Portarias de habilitação e de incentivos do Ministério da Saúde.', 'https://www.in.gov.br/']
  ];
  const PERGUNTAS = [
    ['Produção e faturamento', 'Quanto cada estabelecimento fatura por mês e como isso se compara à média por AIH dos demais hospitais do SUS?', 'Internações (SIH) e benchmark'],
    ['Rejeição de AIH', 'Qual a proporção de AIH rejeitadas e quais códigos de erro mais aparecem? O que foi reapresentado e aprovado depois?', 'Arquivo ER e manual do SIH'],
    ['Habilitações', 'Os serviços produzidos têm portaria de habilitação vigente? O que está produzido sem habilitação?', 'CNES e Diário Oficial da União'],
    ['Profissionais e carga horária', 'O número de vínculos e as horas semanais são compatíveis com a produção e com os leitos cadastrados?', 'CNES, profissionais (PF)'],
    ['Ambulatório e CIHA', 'Há produção ambulatorial e CIHA que não aparece no faturamento? Quais procedimentos concentram o valor aprovado?', 'SIA/SUS e CIHA'],
    ['Cadastro atualizado', 'Os dados do CNES (leitos, serviços, equipamentos) estão atualizados na competência em análise?', 'CNES']
  ];
  const ordem = c => { const m = String(c || '').match(/^(\d{1,2})\/(\d{4})$/); return m ? Number(m[2]) * 100 + Number(m[1]) : 0; };

  function pintar() {
    limpar(corpo); pintarHero();
    const arq = E.dados; if (!arq) return;
    const sec = arq.secao || {};
    const todos = arr(sec.estabelecimentos);
    if (!todos.length) { corpo.append(aviso(sec.situacao || 'A confirmar: sem produção por estabelecimento na base.')); return; }
    const sel = E.estab ? todos.filter(f => f.cnes === E.estab) : todos;
    const um = sel.length === 1 && !!E.estab ? sel[0] : null;
    const gerado = dtBr(arq.gerado_em) || 'data sem registro';
    const fonte = txt => el('p', {class: 'sl-fonte'}, 'Fonte: ' + txt + ' Coleta: ' + gerado + '.');
    const nome = f => el('div', null, el('strong', null, nomeEst(f.cnes) || 'Sem nome público'), el('div', {class: 'rd-peq'}, 'CNES ' + f.cnes + ' · ' + tipoTxt(f.tipo_unidade)));
    const bloco = (id, ...f) => { const c = cartao(...f); c.id = id; return c; };

    // 1. situacao em seis numeros
    const aih = soma(sel, f => soma(f.sih, x => x.aih)), vsih = soma(sel, f => soma(f.sih, x => x.valor_total)), rej = soma(sel, f => soma(f.sih, x => x.rejeitadas));
    const temRej = sel.some(f => arr(f.sih).some(x => num(x.rejeitadas)));
    const qsia = soma(sel, f => soma((f.sia || {}).por_mes, x => x.quantidade_aprovada)), vsia = soma(sel, f => soma((f.sia || {}).por_mes, x => x.valor_aprovado));
    const vinc = soma(sel, f => (f.profissionais || {}).vinculos);
    const lk = (href, no) => el('a', {class: 'sl-kpi', href, onclick: ev => { ev.preventDefault(); const a = document.querySelector(href); if (a) a.scrollIntoView({behavior: 'smooth', block: 'start'}); }}, no);
    corpo.append(el('section', {class: 'sl-sec', id: 'sl-h-res', 'aria-labelledby': 'sl-t-res'}, el('h3', {id: 'sl-t-res'}, um ? (nomeEst(um.cnes) || 'Estabelecimento sem nome público') + ' (CNES ' + um.cnes + '): situação em seis números' : 'Situação do município em seis números'),
      el('div', {class: 'rd-kpis'},
        lk('#sl-ranking', kpi('hospital', 'azul', 'Estabelecimentos', inteiro(sel.length), um ? tipoTxt(um.tipo_unidade) : 'com produção ou profissionais na base')),
        lk('#sl-internacoes', kpi('doc', 'azul', 'AIH aprovadas', aih ? inteiro(aih) : 'sem dado', vsih ? brlc(vsih) + ' em valor total SIH' : 'sem valor na base')),
        lk('#sl-internacoes', kpi('moeda', 'verde', 'Média por AIH', media(vsih, aih) == null ? 'sem dado' : brlc(media(vsih, aih)), 'valor total ÷ AIH aprovadas')),
        lk('#sl-internacoes', kpi('alerta', 'verm', 'Rejeição de AIH', temRej && aih + rej > 0 ? pct(rej / (aih + rej) * 100) : 'sem dado', temRej ? inteiro(rej) + ' AIH rejeitadas (arquivo ER)' : 'sem arquivo ER para o período')),
        lk('#sl-ambulatorio', kpi('grafico', 'verde', 'Ambulatório aprovado', qsia ? inteiro(qsia) : 'sem dado', vsia ? brlc(vsia) + ' em valor aprovado SIA' : 'sem valor na base')),
        lk('#sl-profissionais', kpi('pessoas', 'azul', 'Vínculos profissionais', vinc ? inteiro(vinc) : 'sem dado', 'contagem de vínculos, não de pessoas')))),
      el('p', {class: 'rd-peq'}, 'Como ler os valores: "mi" é milhão e "mil" é milhar. Os números somam as competências disponíveis na base e vêm sempre com a fonte do bloco.'));

    // 2. ranking com busca
    const peso = f => soma(f.sih, x => x.valor_total) + soma((f.sia || {}).por_mes, x => x.valor_aprovado);
    const rk = todos.slice().sort((a, b) => peso(b) - peso(a)), totalPeso = rk.reduce((t, f) => t + peso(f), 0);
    const busca = el('input', {type: 'search', class: 'rd-busca', placeholder: 'Buscar estabelecimento ou CNES', 'aria-label': 'Buscar estabelecimento ou CNES'});
    const tbRk = el('div'); let todosRk = false;
    const pintaRk = () => {
      limpar(tbRk);
      const q = busca.value.trim().toLowerCase();
      let l = rk.map((f, i) => [i + 1, f]).filter(([, f]) => !q || (nomeEst(f.cnes) || '').toLowerCase().includes(q) || f.cnes.includes(q));
      const total = l.length; if (!todosRk && !q) l = l.slice(0, 10);
      tbRk.append(tabela(['#', 'Estabelecimento', 'Valor aprovado (SIH + SIA)', 'Participação'], l.map(([i, f]) => [String(i), nome(f), brl(peso(f)), totalPeso ? pct(peso(f) / totalPeso * 100) : 'sem dado']), [0, 2, 3]));
      if (!todosRk && !q && total > 10) tbRk.append(el('button', {type: 'button', class: 'rd-btn', onclick: () => { todosRk = true; pintaRk(); }}, 'Mostrar todos os ' + inteiro(total) + ' estabelecimentos'));
    };
    busca.addEventListener('input', pintaRk); pintaRk();
    corpo.append(bloco('sl-ranking', 'Estabelecimentos: ranking por valor aprovado', 'Soma do valor aprovado no SIH (internações) e no SIA (ambulatório). Os dez primeiros aparecem por padrão. Use a busca para localizar um estabelecimento.', busca, tbRk, fonte('SIH/SUS e SIA/SUS via DATASUS.')));

    // 3. internacoes: mes a mes + tabela
    const mm = {};
    sel.forEach(f => arr(f.sih).forEach(x => { const o = mm[x.competencia] || (mm[x.competencia] = {competencia: x.competencia, aih: 0, valor_total: 0}); o.aih += x.aih || 0; o.valor_total += x.valor_total || 0; }));
    const meses = Object.values(mm).sort((a, b) => ordem(a.competencia) - ordem(b.competencia));
    const linhaI = f => { if (!arr(f.sih).length) return [nome(f), 'sem dado', 'sem dado', 'sem dado', 'sem dado', 'sem dado', 'sem dado', 'sem dado']; const s = f.sih, a = soma(s, x => x.aih), v = soma(s, x => x.valor_total), r = soma(s, x => x.rejeitadas), tem = arr(s).some(x => num(x.rejeitadas)); return [nome(f), inteiro(a), brl(v), media(v, a) == null ? 'sem dado' : brl(media(v, a)), inteiro(soma(s, x => x.obitos)), media(soma(s, x => x.dias_permanencia), a) == null ? 'sem dado' : decimal(media(soma(s, x => x.dias_permanencia), a), 1), tem ? inteiro(r) : 'sem dado', tem && a + r > 0 ? pct(r / (a + r) * 100) : 'sem dado']; };
    const secI = bloco('sl-internacoes', 'Internações (SIH): mês a mês e por estabelecimento', 'A rejeição vem do arquivo ER, em quantidade de AIH (base: AIH rejeitadas ÷ AIH aprovadas e rejeitadas). Valor rejeitado e não processadas ficam em branco, porque a fonte não traz R$.');
    if (meses.length) {
      const si = el('select', {'aria-label': 'Indicador mensal'}, el('option', {value: 'aih'}, 'AIH aprovadas'), el('option', {value: 'valor_total'}, 'Valor total')), fig = el('div', {class: 'sl-graf'}), pf = () => { limpar(fig); fig.append(barrasMes(meses, si.value, 'Internações por mês')); };
      si.addEventListener('change', pf); pf();
      secI.append(el('label', {class: 'rd-rot-sel'}, 'Indicador ', si), fig);
    }
    secI.append(tabela(['Estabelecimento', 'AIH aprovadas', 'Valor total', 'Média por AIH', 'Óbitos', 'Permanência média (dias)', 'AIH rejeitadas', '% de rejeição'], sel.map(linhaI), [1, 2, 3, 4, 5, 6, 7]));
    if (um && arr(um.sih).length) secI.append(detalhesTabela('Ver por mês', tabela(['Competência', 'AIH aprovadas', 'Valor total', 'Óbitos', 'Dias de permanência', 'AIH rejeitadas'], um.sih.map(x => [x.competencia, inteiro(x.aih), brl(x.valor_total), inteiro(x.obitos), inteiro(x.dias_permanencia), num(x.rejeitadas) ? inteiro(x.rejeitadas) : 'sem dado']), [1, 2, 3, 4, 5])));
    secI.append(fonte('SIH/SUS (arquivos RD e ER) via DATASUS.'));
    corpo.append(secI);

    // 4. ambulatorio
    const rowsA = sel.map(f => { const sa = (f.sia || {}).por_mes; if (!arr(sa).length) return [nome(f), 'sem dado', 'sem dado', 'sem competência']; return [nome(f), inteiro(soma(sa, x => x.quantidade_aprovada)), brl(soma(sa, x => x.valor_aprovado)), ate(sa)]; });
    const secA = bloco('sl-ambulatorio', 'Ambulatório (SIA)', 'Produção ambulatorial aprovada por estabelecimento, soma das competências disponíveis.', tabela(['Estabelecimento', 'Quantidade aprovada', 'Valor aprovado', 'Competências'], rowsA, [1, 2]));
    if (um && arr((um.sia || {}).por_mes).length) secA.append(detalhesTabela('Ver por mês', tabela(['Mês de processamento', 'Quantidade aprovada', 'Valor aprovado'], um.sia.por_mes.map(x => [x.mes_processamento, inteiro(x.quantidade_aprovada), brl(x.valor_aprovado)]), [1, 2])));
    if (um && arr((um.sia || {}).principais_procedimentos).length) secA.append(detalhesTabela('Principais procedimentos (código SIGTAP)', tabela(['Procedimento', 'Quantidade aprovada', 'Valor aprovado'], um.sia.principais_procedimentos.map(x => [x.procedimento, inteiro(x.quantidade_aprovada), brl(x.valor_aprovado)]), [1, 2])));
    secA.append(fonte('SIA/SUS (arquivo PA), valores aprovados, via DATASUS.'));
    corpo.append(secA);

    // 5. CIHA
    const secC = bloco('sl-ciha', 'CIHA (Comunicação de Internação Hospitalar e Ambulatorial)', 'Registros de estabelecimentos que não faturam pelo SIH, por estabelecimento.', tabela(['Estabelecimento', 'Registros', 'Procedimentos', 'Dias de permanência', 'Óbitos', 'Competências'],
      sel.map(f => !arr(f.ciha).length ? [nome(f), 'sem dado', 'sem dado', 'sem dado', 'sem dado', 'sem competência'] : [nome(f), inteiro(soma(f.ciha, x => x.registros)), inteiro(soma(f.ciha, x => x.quantidade_procedimentos)), inteiro(soma(f.ciha, x => x.dias_permanencia)), inteiro(soma(f.ciha, x => x.obitos)), ate(f.ciha)]), [1, 2, 3, 4]));
    if (um && arr(um.ciha).length) secC.append(detalhesTabela('Ver por mês', tabela(['Competência', 'Registros', 'Procedimentos', 'Dias de permanência', 'Óbitos'], um.ciha.map(x => [x.competencia, inteiro(x.registros), inteiro(x.quantidade_procedimentos), inteiro(x.dias_permanencia), inteiro(x.obitos)]), [1, 2, 3, 4])));
    secC.append(fonte('CIHA, via DATASUS.'));
    corpo.append(secC);

    // 6. profissionais
    const secP = bloco('sl-profissionais', 'Profissionais (CNES)', 'Vínculos e carga horária semanal por estabelecimento. Conta vínculos (quem atua em dois estabelecimentos aparece duas vezes). Nenhum nome de profissional é coletado ou exibido.', tabela(['Estabelecimento', 'Vínculos', 'Horas ambulatoriais', 'Horas hospitalares', 'Outras horas', 'Competência'],
      sel.map(f => { const q = f.profissionais; return [nome(f), q ? inteiro(q.vinculos) : 'sem dado', q ? inteiro(q.horas_ambulatoriais) : 'sem dado', q ? inteiro(q.horas_hospitalares) : 'sem dado', q ? inteiro(q.horas_outras) : 'sem dado', q ? String(q.competencia || '').replace(/^(\d{4})(\d{2})$/, '$2/$1') : 'sem dado']; }), [1, 2, 3, 4]));
    if (um && um.profissionais && arr(um.profissionais.principais_cbo).length) secP.append(detalhesTabela('Principais CBO (ocupações), em vínculos', tabela(['CBO', 'Vínculos', 'Horas ambulatoriais', 'Horas hospitalares', 'Outras horas'], um.profissionais.principais_cbo.map(x => [x.cbo, inteiro(x.vinculos), inteiro(x.horas_ambulatoriais), inteiro(x.horas_hospitalares), inteiro(x.horas_outras)]), [1, 2, 3, 4])));
    secP.append(fonte('CNES, profissionais (arquivo PF), via DATASUS.'));
    corpo.append(secP);
    if (sec.truncado) corpo.append(aviso('Lista limitada aos estabelecimentos de maior produção.'));

    // 7. painel estrategico: criticas e habilitacoes (arquivo do robo por hospital)
    const h = E.rede && E.rede.hospitais, hi = arr(h && h.itens).filter(i => !E.estab || String(i.cnes) === E.estab);
    const secE = bloco('sl-estrategico', 'Painel estratégico: críticas e habilitações', 'Verificações automáticas do robô sobre os hospitais do município. Habilitação só aparece como "Habilitado" com portaria registrada.');
    if (hi.length) {
      secE.append(tabela(['Estabelecimento', 'Críticas altas', 'Críticas médias', 'Críticas baixas', 'Habilitações (status)', '% de rejeição'], hi.map(i => {
        const c = {}; arr(i.criticas).forEach(x => { const k = x.severidade === 'Média' ? 'Media' : x.severidade; c[k] = (c[k] || 0) + 1; });
        const hb = i.checklist_habilitacao || {}, rs = Object.entries(hb.resumo || {}).filter(([, n]) => n > 0).map(([k, n]) => k + ' ' + n).join(' · ');
        return [el('div', null, el('strong', null, nomeEst(String(i.cnes)) || 'Sem nome público'), el('div', {class: 'rd-peq'}, 'CNES ' + i.cnes)), inteiro(c.Alta || 0), inteiro(c.Media || 0), inteiro(c.Baixa || 0), rs || 'sem habilitação na base', pct((i.rejeicao_sih || {}).pct_rejeicao_periodo)];
      }), [1, 2, 3]));
    } else secE.append(aviso((h && (h.situacao || h.obs)) || 'A confirmar: sem críticas nem habilitações do robô para este município.'));
    secE.append(fonte('CNES, SIH/SUS e portarias; críticas e checklist calculados pelo robô.'));
    corpo.append(secE);

    // 8. guia: o que perguntar
    corpo.append(bloco('sl-guia', 'Guia de gestão: o que perguntar', 'Pontos de partida para a reunião de diretoria ou para o pedido de informação, sem juízo prévio sobre o que será encontrado.',
      el('ul', {class: 'sl-ask'}, PERGUNTAS.map(([t, q, f]) => el('li', null, el('strong', null, t), el('p', null, q), el('span', {class: 'rd-peq'}, 'Onde conferir: ' + f))))));

    // 9. fontes e consultas oficiais
    corpo.append(bloco('sl-fontes', 'Fontes e consultas oficiais', 'Cada cartão leva à consulta na fonte oficial. Confira sempre o dado na origem antes de decidir.',
      el('div', {class: 'sl-links'}, FONTES.map(([t, d, u]) => el('a', {class: 'sl-link', href: u, target: '_blank', rel: 'noopener noreferrer'}, el('strong', null, t), el('span', null, d))))));
    corpo.append(el('p', {class: 'rd-peq'}, (sec.obs || '') + ' Conteúdo técnico e informativo, sem posicionamento partidário.'));
    corpo.append(complementos());
  }

  function complementos() {
    // visoes extras do robo, recolhidas para nao competir com os quatro blocos
    const w = el('section', {class: 'sl-sec'});
    const painel = (tit, corpoFn) => {
      const alvo = el('div', {class: 'rd-lazy'}); let feito = false;
      const d = el('details', {class: 'rd-det sl-mais'}, el('summary', null, tit), alvo);
      d.addEventListener('toggle', async () => { if (!d.open || feito) return; feito = true; alvo.append(el('p', {class: 'rd-carregando'}, 'Carregando...')); const x = await corpoFn(); limpar(alvo); alvo.append(x); if (x.carregar) x.carregar(); });
      return d;
    };
    w.append(
      painel('Rejeições de AIH no estado (arquivo ER): concentração, recuperação e motivos', async () => {
        const est = await carregar(DS + 'rede_rejeicao_es.json'), nomes = {};
        arr(E.indice && E.indice.municipios).forEach(m => { nomes[String(m.cod).slice(0, 6)] = m.nome; });
        return est ? painelEstado(est, c => nomes[String(c)] || (c ? 'município ' + c : 'município sem dado')) : aviso('A confirmar: sem dados de rejeição do estado.');
      }),
      painel('Status das conexões e fontes oficiais', async () => painelFontes()));
    return w;
  }

  selUF.addEventListener('change', async () => { E.uf = selUF.value; E.dados = null; E.mun = null; pintarHero(); limpar(corpo); selEst.disabled = true; limpar(selMun); selMun.append(el('option', {value: ''}, 'Escolha o município')); selMun.disabled = true; if (!E.uf) { selo.textContent = 'Escolha um estado.'; return; } selo.textContent = 'Carregando municípios...'; await carregarMuns(E.uf); selo.textContent = 'Escolha o município.'; });
  selMun.addEventListener('change', () => aoMunicipio(selMun.value));
  selEst.addEventListener('change', () => { E.estab = selEst.value; pintar(); });

  (async () => {
    const [indice, nomes] = await Promise.all([carregar(DS + 'rede_indice.json'), carregar(DS + 'rede_nomes_cnes.json')]);
    E.indice = indice; E.nomes = (nomes && nomes.nomes) || {};
    await carregarUF();
    const lem = lembrado(), uf0 = (lem && lem.uf) || '';
    if (lem && uf0) { selUF.value = uf0; E.uf = uf0; await carregarMuns(uf0); selMun.value = lem.id; if (selMun.value === lem.id) await aoMunicipio(lem.id); }
  })();
  return raiz;
}
