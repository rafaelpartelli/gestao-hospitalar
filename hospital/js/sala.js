// Tela unica "Gestao hospitalar", nos moldes da Sala de Gestao do partelli.pro: escolha de Estado, Municipio e Estabelecimento
// sempre visivel no topo e, abaixo, Ambulatorio (SIA), Internacoes (SIH), CIHA e Profissionais (CNES) na mesma tela, sem abas.
// Le /dados/rede_<cod>_estab.json e rede_nomes_cnes.json. Textos externos entram so como texto (el). Sem estilo embutido (CSP).
import {el, limpar, carregar, tabela, inteiro, decimal} from './util.js';
import {sv, CORES, arr, kpi, cartao, aviso, brl, brlc, num, pct, pend, icone, detalhesTabela, barrasMes, painelEstado, painelFontes} from './rede.js';

const DS = new URL('../', import.meta.url).href + 'dados/';
const IBGE = 'https://servicodados.ibge.gov.br/api/v1/localidades';
const soma = (l, f) => arr(l).reduce((s, x) => s + (num(f(x)) ? f(x) : 0), 0);
const TIPOS = {'05': 'Hospital', '07': 'Hospital', '62': 'Hospital', '01': 'Unidade básica', '02': 'Unidade básica', '73': 'UPA', '70': 'CAPS', '04': 'Policlínica ou ambulatório', '36': 'Policlínica ou ambulatório', '50': 'Vigilância em saúde', '64': 'Vigilância em saúde', '68': 'Vigilância em saúde', '76': 'Vigilância em saúde', '81': 'Vigilância em saúde'};
const tipoTxt = t => { const c = String(t == null ? '' : t).trim().padStart(2, '0'); return t == null || t === '' ? 'tipo sem dado' : (TIPOS[c] || 'Outro tipo (' + c + ')'); };
const ate = (a, b) => { const l = arr(a).map(x => x.competencia || x.mes_processamento).filter(Boolean); return l.length ? (l.length > 1 ? l[0] + ' a ' + l[l.length - 1] : l[0]) : 'sem competência'; };
const dtBr = iso => { const m = String(iso || '').match(/^(\d{4})-(\d{2})-(\d{2})/); return m ? `${m[3]}/${m[2]}/${m[1]}` : ''; };
const listaPub = arq => { const b = arr(arq && arq.secao && arq.secao.estabelecimentos), tem = b.some(f => f.gestao_publica != null); return {brutos: b, tem, lista: tem ? b.filter(f => f.gestao_publica === true) : b}; };
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
    const lp = listaPub(arq), lista = lp.lista.slice().sort((a, b) => (nomeEst(a.cnes) || 'zzz' + a.cnes).localeCompare(nomeEst(b.cnes) || 'zzz' + b.cnes, 'pt-BR'));
    lista.forEach(f => selEst.append(el('option', {value: f.cnes}, rotuloEst(f))));
    selEst.disabled = !lista.length;
    selo.textContent = lista.length ? `${inteiro(lista.length)} estabelecimento(s) de gestão pública${lp.tem ? ' (de ' + inteiro(lp.brutos.length) + ' com produção ou profissionais no CNES)' : ''}. Dados gerados em ${dtBr(arq.gerado_em) || 'data sem registro'}.` : 'Sem estabelecimentos de gestão pública na base.';
    pintar();
  }

  // ---------- graficos ----------
  const barrasH = (itens, fmt) => {
    const max = Math.max(...itens.map(i => i.v), 0) || 1, w = el('div', {class: 'rd-rank'});
    itens.forEach(i => {
      const barra = el('span', {class: 'rd-fill'});
      requestAnimationFrame(() => { barra.style.width = Math.max(i.v / max * 100, i.v > 0 ? 1.5 : 0) + '%'; });
      w.append(el('div', {class: 'rd-rank-l'}, el('div', {class: 'rd-rank-n'}, el('strong', null, i.nome), i.sub ? el('span', null, i.sub) : null), el('div', {class: 'rd-trilho', role: 'img', 'aria-label': `${i.nome}: ${fmt(i.v)}`}, barra), el('div', {class: 'rd-rank-v'}, fmt(i.v))));
    });
    return w;
  };
  const topOutros = (itens, n) => { const o = itens.filter(i => i.v > 0).sort((a, b) => b.v - a.v); if (o.length <= n) return o; const r = o.slice(0, n - 1), resto = o.slice(n - 1).reduce((t, i) => t + i.v, 0); return r.concat([{rot: 'Demais estabelecimentos', v: resto}]); };
  const donut = (fatias, centroN, centroT, fmt, rotulo) => {
    const total = fatias.reduce((t, f) => t + f.v, 0);
    if (!total) return el('p', {class: 'rd-peq'}, 'Sem valores na base para este gráfico.');
    const R = 62, C = 2 * Math.PI * R; let off = 0;
    const g = sv('svg', {viewBox: '0 0 160 160', class: 'rd-rosca', role: 'img', 'aria-label': rotulo}, sv('circle', {cx: 80, cy: 80, r: R, fill: 'none', class: 'rd-rosca-fundo', 'stroke-width': 22}));
    fatias.forEach((f, k) => { const fr = f.v / total; g.append(sv('circle', {cx: 80, cy: 80, r: R, fill: 'none', stroke: CORES[k % CORES.length], 'stroke-width': 22, 'stroke-dasharray': `${fr * C} ${C}`, 'stroke-dashoffset': -off, transform: 'rotate(-90 80 80)'}, sv('title', null, `${f.rot}: ${fmt(f.v)}`))); off += fr * C; });
    g.append(sv('text', {x: 80, y: 80, 'text-anchor': 'middle', class: 'rd-rosca-n'}, centroN), sv('text', {x: 80, y: 96, 'text-anchor': 'middle', class: 'rd-rosca-t'}, centroT));
    return el('div', {class: 'rd-rosca-w'}, g, el('ul', {class: 'rd-rosca-leg'}, fatias.map((f, k) => el('li', null, el('span', {class: 'rd-amostra', 'data-c': String(k % CORES.length)}), el('div', null, el('strong', null, f.rot), el('div', {class: 'rd-peq'}, fmt(f.v) + ' (' + pct(f.v / total * 100) + ')'))))));
  };
  const painel2 = (...f) => el('div', {class: 'rd-duas'}, ...f);
  const subt = (t, ...f) => el('div', {class: 'sl-sub'}, el('h4', null, t), ...f);

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
  const agrupaMes = (sel, ler, chave, campos) => { const mm = {}; sel.forEach(f => arr(ler(f)).forEach(x => { const k = x[chave], o = mm[k] || (mm[k] = {[chave]: k}); campos.forEach(c => { o[c] = (o[c] || 0) + (num(x[c]) ? x[c] : 0); }); })); return Object.values(mm).sort((a, b) => ordem(a[chave]) - ordem(b[chave])); };
  const comSeletor = (meses, opcoes, rotulo) => {
    const si = el('select', {'aria-label': 'Indicador mensal'}, opcoes.map(([v, t]) => el('option', {value: v}, t))), fig = el('div', {class: 'sl-graf'}), pf = () => { limpar(fig); fig.append(barrasMes(meses, si.value, rotulo)); };
    si.addEventListener('change', pf); pf();
    return el('div', null, el('label', {class: 'rd-rot-sel'}, 'Indicador ', si), fig);
  };

  function pintar() {
    limpar(corpo); pintarHero();
    const arq = E.dados; if (!arq) return;
    const sec = arq.secao || {};
    const lp = listaPub(arq), todos = lp.lista;
    if (!lp.brutos.length) { corpo.append(aviso(sec.situacao || 'A confirmar: sem produção por estabelecimento na base.')); return; }
    if (!lp.tem) corpo.append(aviso('O arquivo do robô ainda não traz a natureza jurídica do CNES, por isso todos os estabelecimentos aparecem. Rode a consolidação e a publicação no Serverrobo para filtrar somente a gestão pública.'));
    if (!todos.length) { corpo.append(aviso('Nenhum estabelecimento de gestão pública com produção ou profissionais na base deste município.')); return; }
    const sel = E.estab ? todos.filter(f => f.cnes === E.estab) : todos;
    const um = sel.length === 1 && !!E.estab ? sel[0] : null;
    const gerado = dtBr(arq.gerado_em) || 'data sem registro';
    const fonte = txt => el('p', {class: 'sl-fonte'}, 'Fonte: ' + txt + ' Coleta: ' + gerado + '. Somente estabelecimentos de gestão pública (natureza jurídica do CNES).');
    const rotu = f => nomeEst(f.cnes) || 'Sem nome público (CNES ' + f.cnes + ')';
    const nome = f => el('div', null, el('strong', null, nomeEst(f.cnes) || 'Sem nome público'), el('div', {class: 'rd-peq'}, 'CNES ' + f.cnes + ' · ' + tipoTxt(f.tipo_unidade)));
    const bloco = (id, ...f) => { const c = cartao(...f); c.id = id; return c; };
    const tab = (rot, t) => detalhesTabela(rot, t);

    // totais
    const aih = soma(sel, f => soma(f.sih, x => x.aih)), vsih = soma(sel, f => soma(f.sih, x => x.valor_total)), rej = soma(sel, f => soma(f.sih, x => x.rejeitadas));
    const obi = soma(sel, f => soma(f.sih, x => x.obitos)), dias = soma(sel, f => soma(f.sih, x => x.dias_permanencia));
    const temRej = sel.some(f => arr(f.sih).some(x => num(x.rejeitadas)));
    const qsia = soma(sel, f => soma((f.sia || {}).por_mes, x => x.quantidade_aprovada)), vsia = soma(sel, f => soma((f.sia || {}).por_mes, x => x.valor_aprovado));
    const reg = soma(sel, f => soma(f.ciha, x => x.registros)), vinc = soma(sel, f => (f.profissionais || {}).vinculos);
    const horas = soma(sel, f => (f.profissionais || {}).horas_ambulatoriais) + soma(sel, f => (f.profissionais || {}).horas_hospitalares) + soma(sel, f => (f.profissionais || {}).horas_outras);
    const mesesSih = agrupaMes(sel, f => f.sih, 'competencia', ['aih', 'valor_total']);
    const lk = (href, no) => el('a', {class: 'sl-kpi', href, onclick: ev => { ev.preventDefault(); const a = document.querySelector(href); if (a) a.scrollIntoView({behavior: 'smooth', block: 'start'}); }}, no);

    // 1. situacao em numeros: so cartoes com informacao
    const C = {
      est: [true, 'hospital', 'azul', 'Estabelecimentos públicos', inteiro(sel.length), um ? tipoTxt(um.tipo_unidade) : (lp.tem ? 'de ' + inteiro(lp.brutos.length) + ' com produção ou profissionais no CNES' : 'com produção ou profissionais na base'), '#sl-ranking'],
      aih: [aih > 0, 'doc', 'azul', 'AIH aprovadas', inteiro(aih), 'internações em ' + ate(mesesSih), '#sl-internacoes'],
      med: [aih > 0 && vsih > 0, 'grafico', 'verde', 'Média por AIH', brlc(vsih / (aih || 1)), 'valor total ÷ AIH aprovadas', '#sl-internacoes'],
      rej: [temRej && aih + rej > 0, 'alerta', 'verm', 'Rejeição de AIH', pct(rej / ((aih + rej) || 1) * 100), inteiro(rej) + ' AIH rejeitadas (arquivo ER)', '#sl-internacoes'],
      amb: [qsia > 0, 'grafico', 'verde', 'Ambulatório aprovado', inteiro(qsia), brlc(vsia) + ' em valor aprovado (SIA)', '#sl-ambulatorio'],
      vin: [vinc > 0, 'pessoas', 'azul', 'Vínculos profissionais', inteiro(vinc), 'contagem de vínculos, não de pessoas', '#sl-profissionais'],
      vsih: [vsih > 0, 'moeda', 'verde', 'Valor aprovado em internações', brlc(vsih), brl(vsih), '#sl-internacoes'],
      per: [aih > 0 && dias > 0, 'agenda', 'azul', 'Permanência média', decimal(dias / (aih || 1), 1) + ' dias', 'dias de permanência ÷ AIH', '#sl-internacoes'],
      mor: [aih > 0, 'pessoas', 'verm', 'Mortalidade hospitalar', pct(obi / (aih || 1) * 100), inteiro(obi) + ' óbitos ÷ AIH aprovadas', '#sl-internacoes'],
      vsia: [vsia > 0, 'moeda', 'azul', 'Valor aprovado no ambulatório', brlc(vsia), brl(vsia), '#sl-ambulatorio'],
      ciha: [reg > 0, 'doc', 'azul', 'Registros de CIHA', inteiro(reg), 'estabelecimentos que não faturam pelo SIH', '#sl-ciha'],
      hor: [horas > 0, 'agenda', 'azul', 'Horas semanais cadastradas', inteiro(horas), 'ambulatoriais, hospitalares e outras', '#sl-profissionais']
    };
    const ativos = k => C[k][0];
    let ks = ['est', 'aih', 'med', 'rej', 'amb', 'vin'].filter(ativos);
    ['vsih', 'per', 'mor', 'vsia', 'ciha', 'hor'].forEach(k => { if (ks.length < 6 && ativos(k)) ks.push(k); });
    corpo.append(el('section', {class: 'sl-sec', id: 'sl-h-res', 'aria-labelledby': 'sl-t-res'}, el('h3', {id: 'sl-t-res'}, um ? rotu(um) + ': situação em números' : 'Situação do município em números (gestão pública)'),
      el('div', {class: 'rd-kpis'}, ks.map(k => { const [, ic, tom, rot, val, nota, href] = C[k]; return lk(href, kpi(ic, tom, rot, val, nota)); })),
      el('p', {class: 'rd-peq'}, 'Como ler os valores: "mi" é milhão e "mil" é milhar. Os números somam as competências disponíveis na base. Só aparecem cartões com informação.')));

    // 2. ranking e composicao
    const peso = f => soma(f.sih, x => x.valor_total) + soma((f.sia || {}).por_mes, x => x.valor_aprovado);
    const rk = todos.slice().sort((a, b) => peso(b) - peso(a)).filter(f => peso(f) > 0);
    const busca = el('input', {type: 'search', class: 'rd-busca', placeholder: 'Buscar estabelecimento ou CNES', 'aria-label': 'Buscar estabelecimento ou CNES'}), tbRk = el('div');
    const pintaRk = () => { limpar(tbRk); const q = busca.value.trim().toLowerCase(); tbRk.append(tabela(['#', 'Estabelecimento', 'Valor aprovado (SIH + SIA)'], rk.map((f, i) => [i + 1, f]).filter(([, f]) => !q || (nomeEst(f.cnes) || '').toLowerCase().includes(q) || f.cnes.includes(q)).map(([i, f]) => [String(i), nome(f), brl(peso(f))]), [0, 2])); };
    busca.addEventListener('input', pintaRk); pintaRk();
    corpo.append(bloco('sl-ranking', 'Estabelecimentos públicos: valor aprovado', 'Soma do valor aprovado no SIH (internações) e no SIA (ambulatório). O gráfico de barras mostra os dez maiores e a rosca mostra de onde vem o valor.',
      rk.length ? painel2(subt('Dez maiores por valor aprovado', barrasH(rk.slice(0, 10).map(f => ({nome: nomeEst(f.cnes) || 'Sem nome público', sub: 'CNES ' + f.cnes + ' · ' + tipoTxt(f.tipo_unidade), v: peso(f)})), brlc)),
        subt('Composição do valor aprovado', donut([{rot: 'Internações (SIH)', v: soma(sel, f => soma(f.sih, x => x.valor_total))}, {rot: 'Ambulatório (SIA)', v: soma(sel, f => soma((f.sia || {}).por_mes, x => x.valor_aprovado))}].filter(f => f.v > 0), brlc(soma(sel, peso)), 'valor aprovado', brlc, 'Composição do valor aprovado entre internações e ambulatório')))
        : el('p', {class: 'rd-peq'}, 'Sem valor aprovado na base para os estabelecimentos de gestão pública.'),
      tab('Ver todos em tabela, com busca', el('div', null, busca, tbRk)), fonte('SIH/SUS e SIA/SUS via DATASUS.')));

    // 3. internacoes
    const hosp = sel.filter(f => arr(f.sih).length);
    const secI = bloco('sl-internacoes', 'Internações (SIH)', 'AIH aprovadas por mês e por estabelecimento. A rejeição vem do arquivo ER, em quantidade de AIH (base: AIH rejeitadas ÷ AIH aprovadas e rejeitadas). Valor rejeitado e não processadas ficam em branco, porque a fonte não traz R$.');
    if (hosp.length) {
      secI.append(painel2(subt('AIH aprovadas e valor, mês a mês', comSeletor(mesesSih, [['aih', 'AIH aprovadas'], ['valor_total', 'Valor total']], 'Internações por mês')),
        temRej && aih + rej > 0 ? subt('AIH aprovadas e rejeitadas', donut([{rot: 'Aprovadas', v: aih}, {rot: 'Rejeitadas', v: rej}].filter(f => f.v > 0), pct(rej / (aih + rej) * 100), 'de rejeição', inteiro, 'AIH aprovadas e rejeitadas'))
          : subt('Valor das internações por estabelecimento', donut(topOutros(hosp.map(f => ({rot: nomeEst(f.cnes) || 'CNES ' + f.cnes, v: soma(f.sih, x => x.valor_total)})), 5), brlc(vsih), 'valor total SIH', brlc, 'Valor das internações por estabelecimento'))));
      if (hosp.length > 1) secI.append(subt('Média por AIH por estabelecimento', barrasH(hosp.filter(f => soma(f.sih, x => x.aih) > 0).map(f => ({nome: nomeEst(f.cnes) || 'Sem nome público', sub: 'CNES ' + f.cnes, v: soma(f.sih, x => x.valor_total) / soma(f.sih, x => x.aih)})).sort((a, b) => b.v - a.v), brl)));
      secI.append(tab('Ver em tabela', tabela(['Estabelecimento', 'AIH aprovadas', 'Valor total', 'Média por AIH', 'Óbitos', 'Permanência média (dias)', 'AIH rejeitadas', '% de rejeição'], hosp.map(f => { const s = f.sih, a = soma(s, x => x.aih), v = soma(s, x => x.valor_total), r = soma(s, x => x.rejeitadas), tem = arr(s).some(x => num(x.rejeitadas)); return [nome(f), inteiro(a), brl(v), media(v, a) == null ? 'sem dado' : brl(media(v, a)), inteiro(soma(s, x => x.obitos)), media(soma(s, x => x.dias_permanencia), a) == null ? 'sem dado' : decimal(media(soma(s, x => x.dias_permanencia), a), 1), tem ? inteiro(r) : 'sem dado', tem && a + r > 0 ? pct(r / (a + r) * 100) : 'sem dado']; }), [1, 2, 3, 4, 5, 6, 7])));
    } else secI.append(el('p', {class: 'rd-peq'}, 'Nenhum estabelecimento de gestão pública com internação (SIH) na base.'));
    secI.append(fonte('SIH/SUS (arquivos RD e ER) via DATASUS.'));
    corpo.append(secI);

    // 4. ambulatorio
    const amb = sel.filter(f => arr((f.sia || {}).por_mes).length), mesesSia = agrupaMes(sel, f => (f.sia || {}).por_mes, 'mes_processamento', ['quantidade_aprovada', 'valor_aprovado']);
    const secA = bloco('sl-ambulatorio', 'Ambulatório (SIA)', 'Produção ambulatorial aprovada por mês e por estabelecimento.');
    if (amb.length) {
      secA.append(painel2(subt('Produção aprovada, mês a mês', comSeletor(mesesSia, [['valor_aprovado', 'Valor aprovado'], ['quantidade_aprovada', 'Quantidade aprovada']], 'Produção ambulatorial por mês')),
        subt('Valor aprovado por estabelecimento', donut(topOutros(amb.map(f => ({rot: nomeEst(f.cnes) || 'CNES ' + f.cnes, v: soma(f.sia.por_mes, x => x.valor_aprovado)})), 5), brlc(vsia), 'valor aprovado SIA', brlc, 'Valor ambulatorial por estabelecimento'))));
      if (um && arr(um.sia.principais_procedimentos).length) secA.append(subt('Principais procedimentos (código SIGTAP), por valor aprovado', barrasH(um.sia.principais_procedimentos.map(x => ({nome: String(x.procedimento), sub: inteiro(x.quantidade_aprovada) + ' aprovados', v: x.valor_aprovado})), brlc)));
      secA.append(tab('Ver em tabela', tabela(['Estabelecimento', 'Quantidade aprovada', 'Valor aprovado', 'Competências'], amb.map(f => [nome(f), inteiro(soma(f.sia.por_mes, x => x.quantidade_aprovada)), brl(soma(f.sia.por_mes, x => x.valor_aprovado)), ate(f.sia.por_mes)]), [1, 2])));
    } else secA.append(el('p', {class: 'rd-peq'}, 'Nenhum estabelecimento de gestão pública com produção ambulatorial (SIA) na base.'));
    secA.append(fonte('SIA/SUS (arquivo PA), valores aprovados, via DATASUS.'));
    corpo.append(secA);

    // 5. CIHA
    const ci = sel.filter(f => arr(f.ciha).length), mesesCi = agrupaMes(sel, f => f.ciha, 'competencia', ['registros', 'quantidade_procedimentos']);
    const secC = bloco('sl-ciha', 'CIHA (Comunicação de Internação Hospitalar e Ambulatorial)', 'Registros de estabelecimentos que não faturam pelo SIH.');
    if (ci.length) {
      secC.append(painel2(subt('Registros por mês', comSeletor(mesesCi, [['registros', 'Registros'], ['quantidade_procedimentos', 'Procedimentos']], 'CIHA por mês')),
        subt('Registros por estabelecimento', barrasH(ci.map(f => ({nome: nomeEst(f.cnes) || 'Sem nome público', sub: 'CNES ' + f.cnes, v: soma(f.ciha, x => x.registros)})).sort((a, b) => b.v - a.v), inteiro))));
      secC.append(tab('Ver em tabela', tabela(['Estabelecimento', 'Registros', 'Procedimentos', 'Dias de permanência', 'Óbitos', 'Competências'], ci.map(f => [nome(f), inteiro(soma(f.ciha, x => x.registros)), inteiro(soma(f.ciha, x => x.quantidade_procedimentos)), inteiro(soma(f.ciha, x => x.dias_permanencia)), inteiro(soma(f.ciha, x => x.obitos)), ate(f.ciha)]), [1, 2, 3, 4])));
    } else secC.append(el('p', {class: 'rd-peq'}, 'Nenhum estabelecimento de gestão pública com CIHA na base. Isso é esperado quando todos faturam pelo SIH.'));
    secC.append(fonte('CIHA, via DATASUS.'));
    corpo.append(secC);

    // 6. profissionais
    const pr = sel.filter(f => f.profissionais);
    const secP = bloco('sl-profissionais', 'Profissionais (CNES)', 'Vínculos e carga horária semanal. Conta vínculos (quem atua em dois estabelecimentos aparece duas vezes). Nenhum nome de profissional é coletado ou exibido.');
    if (pr.length) {
      const ha = soma(pr, f => f.profissionais.horas_ambulatoriais), hh = soma(pr, f => f.profissionais.horas_hospitalares), ho = soma(pr, f => f.profissionais.horas_outras);
      secP.append(painel2(um && arr(um.profissionais.principais_cbo).length ? subt('Principais CBO (ocupações), em vínculos', barrasH(um.profissionais.principais_cbo.map(x => ({nome: 'CBO ' + x.cbo, v: x.vinculos})), inteiro))
        : subt('Vínculos por estabelecimento', barrasH(pr.map(f => ({nome: nomeEst(f.cnes) || 'Sem nome público', sub: 'CNES ' + f.cnes, v: f.profissionais.vinculos || 0})).sort((a, b) => b.v - a.v).slice(0, 10), inteiro)),
        subt('Carga horária semanal', donut([{rot: 'Ambulatoriais', v: ha}, {rot: 'Hospitalares', v: hh}, {rot: 'Outras', v: ho}].filter(f => f.v > 0), inteiro(ha + hh + ho), 'horas por semana', inteiro, 'Carga horária semanal por tipo'))));
      secP.append(tab('Ver em tabela', tabela(['Estabelecimento', 'Vínculos', 'Horas ambulatoriais', 'Horas hospitalares', 'Outras horas', 'Competência'], pr.map(f => { const q = f.profissionais; return [nome(f), inteiro(q.vinculos), inteiro(q.horas_ambulatoriais), inteiro(q.horas_hospitalares), inteiro(q.horas_outras), String(q.competencia || '').replace(/^(\d{4})(\d{2})$/, '$2/$1')]; }), [1, 2, 3, 4])));
    } else secP.append(el('p', {class: 'rd-peq'}, 'Nenhum estabelecimento de gestão pública com profissionais na base.'));
    secP.append(fonte('CNES, profissionais (arquivo PF), via DATASUS.'));
    corpo.append(secP);

    // 7. painel estrategico
    const pubSet = new Set(todos.map(f => f.cnes));
    const h = E.rede && E.rede.hospitais, hi = arr(h && h.itens).filter(i => pubSet.has(String(i.cnes)) && (!E.estab || String(i.cnes) === E.estab));
    const secE = bloco('sl-estrategico', 'Painel estratégico: críticas e habilitações', 'Verificações automáticas do robô nos hospitais de gestão pública. Habilitação só aparece como "Habilitado" com portaria registrada.');
    if (hi.length) {
      const cr = {Alta: 0, Media: 0, Baixa: 0}, hb = {};
      hi.forEach(i => { arr(i.criticas).forEach(x => { const k = x.severidade === 'Média' ? 'Media' : x.severidade; cr[k] = (cr[k] || 0) + 1; }); Object.entries((i.checklist_habilitacao || {}).resumo || {}).forEach(([k, n]) => { hb[k] = (hb[k] || 0) + n; }); });
      secE.append(painel2(subt('Críticas abertas por severidade', barrasH([{nome: 'Alta', v: cr.Alta}, {nome: 'Média', v: cr.Media}, {nome: 'Baixa', v: cr.Baixa}], inteiro)),
        subt('Habilitações por status', donut(Object.entries(hb).filter(([, n]) => n > 0).map(([k, n]) => ({rot: k, v: n})), inteiro(Object.values(hb).reduce((t, n) => t + n, 0)), 'habilitações', inteiro, 'Habilitações por status'))));
      secE.append(tab('Ver em tabela', tabela(['Estabelecimento', 'Críticas altas', 'Críticas médias', 'Críticas baixas', 'Habilitações (status)', '% de rejeição'], hi.map(i => { const c = {}; arr(i.criticas).forEach(x => { const k = x.severidade === 'Média' ? 'Media' : x.severidade; c[k] = (c[k] || 0) + 1; }); const rs = Object.entries((i.checklist_habilitacao || {}).resumo || {}).filter(([, n]) => n > 0).map(([k, n]) => k + ' ' + n).join(' · '); return [el('div', null, el('strong', null, nomeEst(String(i.cnes)) || 'Sem nome público'), el('div', {class: 'rd-peq'}, 'CNES ' + i.cnes)), inteiro(c.Alta || 0), inteiro(c.Media || 0), inteiro(c.Baixa || 0), rs || 'sem habilitação na base', pct((i.rejeicao_sih || {}).pct_rejeicao_periodo)]; }), [1, 2, 3])));
    } else secE.append(el('p', {class: 'rd-peq'}, (h && (h.situacao || h.obs)) || 'Sem críticas nem habilitações do robô para os hospitais de gestão pública deste município.'));
    secE.append(fonte('CNES, SIH/SUS e portarias; críticas e checklist calculados pelo robô.'));
    corpo.append(secE);

    // 8. guia e 9. fontes
    corpo.append(bloco('sl-guia', 'Guia de gestão: o que perguntar', 'Pontos de partida para a reunião de diretoria ou para o pedido de informação, sem juízo prévio sobre o que será encontrado.',
      el('ul', {class: 'sl-ask'}, PERGUNTAS.map(([t, q, f]) => el('li', null, el('strong', null, t), el('p', null, q), el('span', {class: 'rd-peq'}, 'Onde conferir: ' + f))))));
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
