// Gestao Hospitalar (perfil do diretor). Sem framework. Textos externos nunca entram como HTML (usa el() do util.js).
import {el, limpar, carregar, tabela, inteiro, decimal} from './util.js';
import * as C from './hospital_calc.js';

const BASE = new URL('../', import.meta.url).href;   // pasta hospital/ (dados e config), independente da pagina que embute o modulo
const D = BASE + 'dados/';
const CHAVE_LOCAL = 'partelli_hospital_v1';
const brl = v => new Intl.NumberFormat('pt-BR', {style: 'currency', currency: 'BRL'}).format(v);
const pctf = (v, d = 1) => decimal(v * 100, d) + '%';
const pend = txt => el('span', {class: 'pendente'}, `[PREENCHER: ${txt}]`);
const mostra = (v, fmt, txt) => (v === null || v === undefined || Number.isNaN(v)) ? pend(txt) : fmt(v);
const parseNum = s => { const t = String(s ?? '').trim(); if (!t) return null; const n = Number(t.includes(',') ? t.replace(/\./g, '').replace(',', '.') : t); return Number.isFinite(n) ? n : null; };
const compParaChave = c => /^\d{2}\/\d{4}$/.test(c || '') ? c.slice(3) + c.slice(0, 2) : null;
const chaveParaComp = k => k.slice(4) + '/' + k.slice(0, 4);
const TIPOS_HOSP = {'05': 'Hospital geral', '07': 'Hospital especializado', '62': 'Hospital/dia isolado'};

// ---------------------------------------------------------------- estado e armazenamento local (so no navegador)
const memoria = {};
const guardar = {
  ler() { try { return JSON.parse(localStorage.getItem(CHAVE_LOCAL) || '{}'); } catch (e) { return memoria.dados || {}; } },
  gravar(o) { try { localStorage.setItem(CHAVE_LOCAL, JSON.stringify(o)); } catch (e) { memoria.dados = o; } }
};
const S = {indice: null, cnes: '', comp: '', auto: null, local: guardar.ler(), aba: 'resumo', remessas: null, status: null};

const registro = () => ((S.local[S.cnes || '_'] ||= {})[S.comp || '_'] ||= {sih: {}, remessas: [], plano: [], meta: {}});
const salvar = () => guardar.gravar(S.local);

function dadosComp() {
  const k = compParaChave(S.comp);
  const auto = (S.auto && S.auto.competencias && S.auto.competencias[k]) || {};
  const man = registro();
  const sih = {...(auto.sih || {})};
  for (const [c, v] of Object.entries(man.sih || {})) if (v !== null && v !== undefined && v !== '') sih[c] = v;
  const ano = k ? k.slice(0, 4) : '';
  return {sih, sia: auto.sia || null, procedimentos: sih.procedimentos || [], fonte: sih.fonte, ano: sih.fonte ? ano : '', man, auto};
}

// ---------------------------------------------------------------- interface geral
const ABAS = [['resumo', 'Resumo executivo'], ['sih', 'Faturamento hospitalar (SIH)'], ['sia', 'Produção ambulatorial (SIA)'],
  ['remessas', 'Remessas e prazos'], ['cnes', 'Estabelecimento (CNES)'], ['criticas', 'Críticas e plano'], ['fontes', 'Fontes e status']];

function montarAbas() {
  const nav = limpar(document.getElementById('abas'));
  ABAS.forEach(([id, rot]) => nav.append(el('button', {class: 'aba', role: 'tab', id: 'aba-' + id, 'aria-selected': String(S.aba === id), onclick: () => { S.aba = id; desenhar(); }}, rot)));
}

function desenhar() {
  montarAbas();
  const p = limpar(document.getElementById('painel'));
  p.setAttribute('aria-labelledby', 'aba-' + S.aba);
  const f = {resumo: abaResumo, sih: abaSIH, sia: abaSIA, remessas: abaRemessas, cnes: abaCNES, criticas: abaCriticas, fontes: abaFontes}[S.aba];
  p.append(f());
  const selo = document.getElementById('selo');
  selo.textContent = S.cnes ? `CNES ${S.cnes}${S.comp ? ', competência ' + S.comp : ', sem competência escolhida'}` : 'Informe o CNES de uma unidade autorizada para começar.';
}

function kpi(rot, valor, nota) {
  return el('div', {class: 'kpi'}, el('div', {class: 'rot'}, rot), el('div', {class: 'val'}, valor), nota ? el('div', {class: 'nota'}, nota) : null);
}

function cabecalhoLancamento(texto) {
  return el('p', {class: 'fonte'}, texto);
}

// ---------------------------------------------------------------- calculos centrais
function avaliar(d) {
  const hab = (S.auto && S.auto.cnes && S.auto.cnes.habilitacoes && S.auto.cnes.habilitacoes.itens) || [];
  const r = C.criticas(d, {habilitacoes: hab});
  if (!S.comp) r.criticas = [];  // sem competencia escolhida nao ha o que criticar
  return r;
}

function indicadores(d) {
  const s = d.sih;
  const rj = C.rejeicao(s);
  const apr = C.mediaAIH(s.valor_aprovado, s.aprovadas);
  const sia = d.sia;
  const glosaVal = sia ? sia.valor_apresentado - sia.valor_aprovado : null;
  return {
    s, rj, rjVal: C.rejeicaoValor(s), media: apr, np: C.pctNaoProcessadas(s), compSH: C.compSH(s), compSP: C.compSP(s), confere: C.shSpConfere(s),
    perda: C.perdaRejeicao(s), perm: C.div(s.dias_perm, s.aprovadas), obito: C.div(s.obitos, s.aprovadas),
    glosa: glosaVal, glosaPct: sia ? C.div(glosaVal, sia.valor_apresentado) : null, sia
  };
}

function textoExecutivo(i, d) {
  const out = [];
  if (i.s.aprovadas != null && i.s.valor_aprovado != null) {
    out.push(`Em ${S.comp}, a unidade teve ${inteiro(i.s.aprovadas)} AIHs aprovadas, no valor de ${brl(i.s.valor_aprovado)}, com média de ${i.media === null ? 'sem dado' : brl(i.media)} por AIH.`);
  }
  if (i.rj.valor !== null) {
    out.push(`A rejeição ficou em ${pctf(i.rj.valor)} (base: ${i.rj.base})${i.perda != null ? `, com perda de ${brl(i.perda)} por rejeição` : ''}.`);
  }
  if (i.sia && i.sia.valor_apresentado > 0) {
    out.push(`No ambulatório, foram apresentados ${brl(i.sia.valor_apresentado)} e aprovados ${brl(i.sia.valor_aprovado)}${i.glosaPct !== null ? ` (diferença de ${pctf(i.glosaPct)})` : ''}.`);
  }
  return out;
}

function sugestoes(i, d, crit) {
  const l = [];
  if (i.rj.valor !== null && i.rj.valor > 0) l.push('Alcançar a meta: levantar os motivos de rejeição por código, corrigir na origem e reapresentar as AIHs dentro do prazo da competência.');
  if (i.glosa !== null && i.glosa > 0) l.push('Alcançar a meta: abrir os procedimentos ambulatoriais com maior diferença entre valor apresentado e aprovado e conferir regra, CBO e habilitação.');
  if (i.confere === false) l.push('Alcançar a meta: conferir os componentes de valor das AIHs (SH mais SP deve fechar com o total).');
  if (i.s.aprovadas != null) l.push('Superar a meta: comparar a média por AIH dos principais procedimentos com um benchmark lançado na aba Faturamento (SIH) e priorizar onde a média da unidade está abaixo.');
  l.push('Ampliar: cruzar leitos, serviços e habilitações do CNES com a produção, para identificar serviço que a unidade já executa e ainda não tem habilitado.');
  if (crit.criticas.some(c => c.severidade === 'Alta')) l.push('Tratar primeiro as críticas de severidade Alta, que afetam o valor faturado.');
  return l;
}

function proximoPasso(i, d, crit) {
  if (!S.cnes) return 'Informe o CNES da unidade (com autorização do responsável) no filtro acima.';
  if (!S.comp) return 'Escolha ou cadastre a competência (MM/AAAA) que será analisada.';
  if (i.s.aprovadas == null && i.s.valor_aprovado == null) return 'Lance o resumo mensal na aba Faturamento hospitalar (SIH), com fonte, data de coleta e responsável, ou rode os robôs de coleta para a unidade.';
  const alta = crit.criticas.find(c => c.severidade === 'Alta');
  if (alta) return `Resolver a crítica ${alta.codigo}: ${alta.acao}`;
  if (!registro().remessas.length) return 'Lance, na aba Remessas e prazos, a situação das remessas da competência e o prazo final do Transmissor.';
  return 'Registrar no plano de avanço a ação de maior ganho estimado, com responsável e prazo.';
}

// ---------------------------------------------------------------- aba resumo
function abaResumo() {
  const d = dadosComp(), i = indicadores(d), crit = avaliar(d);
  const w = el('div', null, el('h2', null, 'Resumo executivo'));
  w.append(cabecalhoLancamento(`Fonte: ${d.sih.fonte || '[PREENCHER: fonte oficial]'} · Competência: ${S.comp || '[PREENCHER: MM/AAAA]'} · Coleta: ${d.sih.coletado_em || d.sih.coleta || '[PREENCHER: data de coleta]'}`));
  const k = el('div', {class: 'kpis'});
  k.append(
    kpi('AIHs aprovadas', mostra(i.s.aprovadas, inteiro, 'lançamento necessário'), 'SIH, arquivo RD ou lançamento'),
    kpi('Valor aprovado', mostra(i.s.valor_aprovado, brl, 'R$'), 'soma do valor total das AIHs'),
    kpi('Média por AIH', mostra(i.media, brl, 'aprovadas e valor'), 'valor aprovado ÷ AIHs aprovadas'),
    kpi('Rejeição', mostra(i.rj.valor, v => pctf(v), 'rejeitadas e enviadas'), i.rj.base ? 'base: ' + i.rj.base : 'rejeitadas ÷ enviadas'),
    kpi('Perda por rejeição', mostra(i.perda, brl, 'valor rejeitado'), 'valor rejeitado na competência'),
    kpi('Não processadas', mostra(i.np, v => pctf(v), 'não processadas e enviadas'), 'não processadas ÷ enviadas'),
    kpi('SH e SP', i.compSH === null ? pend('SH e SP') : `${pctf(i.compSH)} / ${pctf(i.compSP)}`, i.confere === false ? 'SH + SP não fecha com o total' : 'composição do valor total'),
    kpi('Permanência média', mostra(i.perm, v => decimal(v, 1) + ' dias', 'dias de permanência'), 'dias de permanência ÷ AIHs aprovadas'),
    kpi('Ambulatório: aprovado', mostra(i.sia && i.sia.valor_aprovado, brl, 'produção SIA'), i.sia ? 'SIA, arquivo PA' : 'sem coleta do SIA'),
    kpi('Ambulatório: diferença', mostra(i.glosa, brl, 'valor apresentado'), i.glosaPct !== null ? `${pctf(i.glosaPct)} do apresentado` : 'apresentado − aprovado'),
    kpi('Críticas abertas', String(crit.criticas.length), `${crit.criticas.filter(c => c.severidade === 'Alta').length} de severidade Alta`)
  );
  w.append(k);
  const lt = textoExecutivo(i, d);
  const lei = el('div', {class: 'leitura'}, el('h3', null, 'Leitura para a direção'));
  if (lt.length) lt.forEach(t => lei.append(el('p', null, t))); else lei.append(el('p', null, 'Sem dado lançado para esta competência. Os indicadores aparecem quando houver lançamento ou coleta.'));
  w.append(lei);
  const meta = registro().meta;
  w.append(el('h3', null, 'Meta de rejeição (lançada pelo gestor)'),
    el('p', {class: 'nota-pequena'}, 'Meta e percentual precisam de fonte e ano. Sem fonte, não são publicados. Meta não é resultado.'),
    formulario([['meta_pct', 'Meta de rejeição (%)', meta.meta_pct], ['meta_fonte', 'Fonte da meta', meta.meta_fonte], ['meta_ano', 'Ano da meta', meta.meta_ano]], v => { Object.assign(registro().meta, v); salvar(); desenhar(); }, 'Salvar meta'));
  const mp = parseNum(meta.meta_pct);
  if (mp !== null && meta.meta_fonte && meta.meta_ano && i.rj.valor !== null) {
    const dif = i.rj.valor * 100 - mp;
    w.append(el('p', null, `Rejeição atual ${pctf(i.rj.valor)} contra meta de ${decimal(mp, 1)}% (${meta.meta_fonte}, ${meta.meta_ano}): ${dif > 0 ? 'acima da meta em ' + decimal(dif, 1) + ' pontos percentuais.' : 'dentro da meta.'}`));
  } else w.append(el('p', {class: 'nota-pequena'}, 'Meta não informada com fonte e ano.'));
  w.append(comparador(d));
  w.append(el('h3', null, 'Sugestões para alcance, superação e ampliação'), el('ul', {class: 'metodo'}, sugestoes(i, d, crit).map(t => el('li', null, t))));
  w.append(el('div', {class: 'aviso'}, el('strong', null, 'Próximo passo: '), proximoPasso(i, d, crit)));
  return w;
}

function comparador(dA) {
  const ks = Object.keys(((S.auto && S.auto.competencias) || {})).map(chaveParaComp), locais = Object.keys(S.local[S.cnes || '_'] || {}).filter(x => x !== '_');
  const todas = [...new Set([...ks, ...locais])].filter(c => c !== S.comp).sort();
  const w = el('div', null, el('h3', null, 'Comparar com outra competência'));
  if (!todas.length) { w.append(el('p', {class: 'nota-pequena'}, 'Cadastre ou colete outra competência para ver o comparativo (delta = B menos A).')); return w; }
  const sel = el('select', {id: 'selB'}, todas.map(c => el('option', {value: c}, c)));
  const out = el('div');
  const calc = () => {
    const bk = compParaChave(sel.value), baseAuto = (S.auto && S.auto.competencias && S.auto.competencias[bk]) || {};
    const manB = ((S.local[S.cnes || '_'] || {})[sel.value] || {}).sih || {};
    const b = {...(baseAuto.sih || {})}; for (const [c, v] of Object.entries(manB)) if (v !== '' && v != null) b[c] = v;
    const a = dA.sih;
    const linhas = [['AIHs aprovadas', 'aprovadas', inteiro], ['Valor aprovado', 'valor_aprovado', brl], ['AIHs rejeitadas', 'rejeitadas', inteiro], ['Valor rejeitado', 'valor_rejeitado', brl]].map(([r, c, f]) => {
      const dl = C.delta(a[c], b[c]), dp = C.deltaPct(a[c], b[c]);
      return [r, mostra(num(a[c]), f, 'valor A'), mostra(num(b[c]), f, 'valor B'), dl === null ? '' : (dl > 0 ? '+' : '') + (f === brl ? brl(dl) : inteiro(dl)), dp === null ? '' : (dp > 0 ? '+' : '') + pctf(dp)];
    });
    const mA = C.mediaAIH(a.valor_aprovado, a.aprovadas), mB = C.mediaAIH(b.valor_aprovado, b.aprovadas);
    linhas.push(['Média por AIH', mostra(mA, brl, 'média A'), mostra(mB, brl, 'média B'), C.delta(mA, mB) === null ? '' : brl(C.delta(mA, mB)), C.deltaPct(mA, mB) === null ? '' : pctf(C.deltaPct(mA, mB))]);
    limpar(out).append(tabela(['Indicador', `A (${S.comp || 'atual'})`, `B (${sel.value})`, 'Delta (B − A)', 'Delta %'], linhas, [1, 2, 3, 4]));
  };
  sel.addEventListener('change', calc);
  w.append(el('label', null, 'Competência B ', sel), out); calc();
  w.append(el('p', {class: 'nota-pequena'}, 'O insight sobre a variação é do gestor. A plataforma não gera interpretação automática.'));
  return w;
}
const num = v => (v === '' || v == null || isNaN(Number(v))) ? null : Number(v);

// ---------------------------------------------------------------- formulario generico
function formulario(campos, aoSalvar, rotulo) {
  const ins = campos.map(([id, rot, val]) => el('label', null, rot, el('input', {id: 'f_' + id, value: val ?? '', autocomplete: 'off'})));
  const bt = el('button', {class: 'botao cheio', type: 'button', onclick: () => { const v = {}; campos.forEach(([id]) => { v[id] = document.getElementById('f_' + id).value.trim(); }); aoSalvar(v); }}, rotulo || 'Salvar');
  return el('div', null, el('div', {class: 'form-grade'}, ins), el('div', {class: 'acoes'}, bt));
}

function baixar(nome, texto, tipo = 'text/csv;charset=utf-8') {
  const a = el('a', {href: URL.createObjectURL(new Blob(['﻿' + texto], {type: tipo})), download: nome});
  document.body.append(a); a.click(); a.remove();
}
const csv = linhas => linhas.map(l => l.map(c => `"${String(c ?? '').replace(/"/g, '""')}"`).join(';')).join('\n');

// ---------------------------------------------------------------- aba SIH
function abaSIH() {
  const d = dadosComp(), i = indicadores(d), s = d.sih;
  const w = el('div', null, el('h2', null, 'Faturamento hospitalar (SIH/SUS)'));
  w.append(cabecalhoLancamento('Valores das AIHs aprovadas (arquivo RD) e rejeitadas (RJ e ER) coletados pelo robô, ou lançados pelo gestor a partir do SIHD. Lançamento do gestor prevalece sobre a coleta.'));
  const man = registro().sih;
  w.append(el('h3', null, 'Lançar resumo mensal'),
    formulario([
      ['enviadas', 'AIHs enviadas', man.enviadas], ['aprovadas', 'AIHs aprovadas', man.aprovadas], ['rejeitadas', 'AIHs rejeitadas', man.rejeitadas], ['nao_processadas', 'AIHs não processadas', man.nao_processadas],
      ['valor_aprovado', 'Valor aprovado (R$)', man.valor_aprovado], ['valor_rejeitado', 'Valor rejeitado (R$)', man.valor_rejeitado], ['sh', 'SH (R$)', man.sh], ['sp', 'SP (R$)', man.sp],
      ['fonte', 'Fonte oficial (ex.: SIHD, TabNet SIH)', man.fonte], ['coleta', 'Data de coleta', man.coleta], ['responsavel', 'Responsável pelo lançamento', man.responsavel]
    ], v => {
      const o = registro().sih;
      for (const [c, x] of Object.entries(v)) o[c] = ['fonte', 'coleta', 'responsavel'].includes(c) ? x : (x === '' ? '' : parseNum(x));
      salvar(); desenhar();
    }, 'Salvar lançamento'));
  w.append(el('p', {class: 'nota-pequena'}, 'A média, os percentuais e as críticas são calculados pela plataforma. Não digite resultado calculado.'));
  const f = el('div', {class: 'kpis'}, kpi('Rejeição por valor', mostra(i.rjVal.valor, v => pctf(v), 'valor aprovado e rejeitado'), i.rjVal.base || ''),
    kpi('AIHs com óbito', mostra(i.obito, v => pctf(v), 'óbitos e aprovadas'), 'proporção das AIHs aprovadas'),
    kpi('AIH sem SH', mostra(num(s.aih_sem_sh), inteiro, 'coleta do RD'), 'valor SH zerado'), kpi('AIH sem SP', mostra(num(s.aih_sem_sp), inteiro, 'coleta do RD'), 'valor SP zerado'));
  w.append(f);
  const procs = d.procedimentos || [];
  w.append(el('h3', null, 'Procedimentos de maior valor'));
  if (!procs.length) w.append(el('p', {class: 'indisponivel'}, 'Sem coleta de procedimentos para esta competência. Rode o robô do SIH para a unidade ou lance manualmente.'));
  else {
    const busca = el('input', {placeholder: 'Filtrar por código', 'aria-label': 'Filtrar procedimentos por código'}), tb = el('div');
    const pinta = () => limpar(tb).append(tabela(['Código SIGTAP', 'Quantidade', 'Valor total', 'Média por AIH', 'SH', 'SP'], procs.filter(p => !busca.value || p.codigo.includes(busca.value)).map(p => [p.codigo, inteiro(p.qtd), brl(p.valor), brl(p.valor / p.qtd), brl(p.sh), brl(p.sp)]), [1, 2, 3, 4, 5]));
    busca.addEventListener('input', pinta); pinta(); w.append(busca, tb);
    w.append(el('p', {class: 'nota-pequena'}, 'A descrição do procedimento vem da tabela SIGTAP da competência (fonte oficial DATASUS). [PREENCHER: tabela SIGTAP da competência]'));
    w.append(benchmark(procs));
  }
  const caps = d.sih.capitulos || [];
  w.append(el('h3', null, 'Causas de internação por capítulo do CID-10'));
  if (caps.length) w.append(ranking(caps.map(c => [c.capitulo, c.qtd])), el('p', {class: 'nota-pequena'}, 'Capítulo do diagnóstico principal. A análise de internações sensíveis à atenção primária exige a lista oficial de condições. [PREENCHER: lista ICSAP oficial]'));
  else w.append(el('p', {class: 'indisponivel'}, 'Sem diagnóstico agregado nesta competência.'));
  const es = d.sih.especialidades || [];
  if (es.length) w.append(el('h3', null, 'Especialidade do leito (código)'), tabela(['Código', 'AIHs', 'Valor'], es.map(e => [e.codigo, inteiro(e.qtd), brl(e.valor)]), [1, 2]));
  const er = d.sih.erros_rejeicao;
  w.append(el('h3', null, 'Motivos de rejeição (código)'));
  if (er && er.length) w.append(tabela(['Código do erro', 'Ocorrências', 'Descrição'], er.map(e => [e.codigo, inteiro(e.qtd), pend('descrição do código no manual do SIH')]), [1]));
  else w.append(el('p', {class: 'indisponivel'}, 'Sem arquivo de erros para a competência. Consulte o relatório de acompanhamento no SIHD.'));
  w.append(avisosColeta(d.sih));
  return w;
}

function avisosColeta(b) {
  return (b && b.avisos && b.avisos.length) ? el('div', {class: 'aviso'}, el('strong', null, 'Avisos da coleta: '), b.avisos.join(' · ')) : el('span');
}

function ranking(pares) {
  const max = Math.max(...pares.map(p => p[1]), 1);
  return el('ul', {class: 'rank'}, pares.map(([n, v]) => el('li', null, el('span', {class: 'nome', title: n}, n), el('span', {class: 'trilho'}, el('span', {class: 'barra', style: `width:${Math.max(1, v / max * 100)}%`})), el('span', {class: 'num'}, inteiro(v)))));
}

function benchmark(procs) {
  const w = el('div', null, el('h3', null, 'Oportunidade frente a um benchmark lançado'));
  w.append(el('p', {class: 'nota-pequena'}, 'Cole uma linha por procedimento no formato código;média por AIH do benchmark (fonte oficial, ex.: TabNet SIH de outros hospitais). A oportunidade só é calculada com os dois valores lançados. Se a média da unidade for maior, a oportunidade é zero e o procedimento fica como acima do benchmark.'));
  const ta = el('textarea', {rows: '4', placeholder: '0407040064;3500,00', 'aria-label': 'Benchmark por procedimento', value: ''}), out = el('div');
  ta.value = registro().meta.benchmark || '';
  const calc = () => {
    registro().meta.benchmark = ta.value; salvar();
    const mapa = {}; ta.value.split('\n').forEach(l => { const [c, m] = l.split(';'); if (c && parseNum(m) !== null) mapa[c.trim()] = parseNum(m); });
    const linhas = procs.filter(p => mapa[p.codigo] != null).map(p => { const mh = C.mediaHospitalBench(p.valor, p.qtd), o = C.oportunidade(mapa[p.codigo], mh, p.qtd); return [p.codigo, inteiro(p.qtd), brl(mh), brl(mapa[p.codigo]), o.acima ? 'acima do benchmark' : brl(o.valor)]; });
    limpar(out).append(linhas.length ? tabela(['Código', 'Quantidade', 'Média da unidade', 'Média benchmark', 'Oportunidade'], linhas, [1, 2, 3, 4]) : el('p', {class: 'indisponivel'}, 'Nenhum procedimento com benchmark lançado.'));
  };
  w.append(ta, el('div', {class: 'acoes'}, el('button', {class: 'botao', type: 'button', onclick: calc}, 'Calcular oportunidade')), out); calc();
  return w;
}

// ---------------------------------------------------------------- aba SIA
function abaSIA() {
  const d = dadosComp(), a = d.sia, w = el('div', null, el('h2', null, 'Produção ambulatorial (SIA/SUS)'));
  w.append(cabecalhoLancamento('Fonte: arquivos PA do SIA/SUS (FTP do DATASUS). O valor apresentado menos o aprovado mostra o que foi glosado.'));
  if (!a) { w.append(el('p', {class: 'indisponivel'}, 'Sem coleta do SIA para esta unidade e competência. Rode o robô do SIA ou consulte o TabNet SIA e lance os valores.'), pend('valores do SIA da competência')); return w; }
  const gl = a.valor_apresentado - a.valor_aprovado;
  w.append(el('div', {class: 'kpis'}, kpi('Apresentado', brl(a.valor_apresentado)), kpi('Aprovado', brl(a.valor_aprovado)), kpi('Diferença', brl(gl), C.div(gl, a.valor_apresentado) === null ? '' : pctf(C.div(gl, a.valor_apresentado)) + ' do apresentado'),
    kpi('Quantidade aprovada', inteiro(a.qtd_aprovada), 'procedimentos')));
  w.append(el('h3', null, 'Por grupo de procedimento'), tabela(['Grupo', 'Quantidade', 'Apresentado', 'Aprovado'], a.grupos.map(g => [`${g.grupo} ${g.nome}`, inteiro(g.qtd), brl(g.valor_apresentado), brl(g.valor_aprovado)]), [1, 2, 3]));
  w.append(el('h3', null, 'Procedimentos de maior valor aprovado'), tabela(['Código', 'Qtd apresentada', 'Qtd aprovada', 'Apresentado', 'Aprovado', 'Diferença'], a.procedimentos.map(p => [p.codigo, inteiro(p.qtd_apresentada), inteiro(p.qtd_aprovada), brl(p.valor_apresentado), brl(p.valor_aprovado), brl(p.valor_apresentado - p.valor_aprovado)]), [1, 2, 3, 4, 5]));
  if (a.financiamento && a.financiamento.length) w.append(el('h3', null, 'Por tipo de financiamento (código)'), tabela(['Código', 'Quantidade', 'Valor aprovado'], a.financiamento.map(f => [f.codigo, inteiro(f.qtd), brl(f.valor_aprovado)]), [1, 2]), el('p', {class: 'nota-pequena'}, 'Significado dos códigos conforme tabela oficial do SIA. [PREENCHER: conferir tabela de financiamento]'));
  w.append(avisosColeta(a));
  return w;
}

// ---------------------------------------------------------------- aba remessas
function abaRemessas() {
  const w = el('div', null, el('h2', null, 'Remessas e prazos (SIHD, SIASUS, CIHA e Transmissor)'));
  const cfg = S.remessas;
  if (!cfg) { w.append(el('p', {class: 'indisponivel'}, 'Cadastro das páginas de remessa indisponível.')); return w; }
  w.append(el('div', {class: 'aviso'}, cfg.aviso));
  const cart = el('div', {class: 'cartoes'});
  for (const s of cfg.sistemas) {
    const st = (S.status && S.status.fontes && S.status.fontes[s.id]) || null, stt = (st && st.status) || s.status;
    const grupos = {}; s.relatorios.forEach(r => (grupos[r.grupo] ||= []).push(r));
    cart.append(el('div', {class: 'cartao'}, el('h3', null, s.nome), el('p', null, el('span', {class: 'status ' + stt.replace(' ', '-')}, stt), ' ', s.area),
      el('p', {class: 'nota-pequena'}, st && st.testado_em ? `Último teste: ${st.testado_em.slice(0, 10)}. ${st.resultado || ''}` : s.teste),
      el('p', null, el('a', {href: s.url, target: '_blank', rel: 'noopener noreferrer'}, 'Abrir no portal oficial')),
      el('details', null, el('summary', null, `Ver relatórios e para que servem (${s.relatorios.length})`),
        tabela(['Relatório', 'O que informa', 'Uso na gestão'], s.relatorios.map(r => [r.nome, r.informa, r.uso])))));
  }
  w.append(cart);
  const t = cfg.sistemas.find(s => s.id === 'transmissor');
  if (t) w.append(el('p', {class: 'nota-pequena'}, 'Sistemas com limite de competência no Transmissor: ' + t.sistemas_consulta.join(', ') + '.'));
  const r = registro();
  w.append(el('h3', null, 'Lançar situação da remessa e prazo'),
    el('div', {class: 'form-grade'},
      el('label', null, 'Sistema', el('select', {id: 'r_sis'}, ['SIHD', 'SIASUS', 'CIHA', 'CNES', 'Outro'].map(x => el('option', {value: x}, x)))),
      el('label', null, 'Data limite (Transmissor)', el('input', {id: 'r_lim', type: 'date'})),
      el('label', null, 'Data de envio', el('input', {id: 'r_env', type: 'date'})),
      el('label', null, 'Situação', el('select', {id: 'r_sit'}, ['Não enviada', 'Enviada', 'Processada', 'Com pendência', 'A verificar'].map(x => el('option', {value: x}, x)))),
      el('label', null, 'Observação', el('input', {id: 'r_obs', autocomplete: 'off'}))),
    el('div', {class: 'acoes'}, el('button', {class: 'botao cheio', type: 'button', onclick: () => {
      r.remessas.push({sistema: v('r_sis'), limite: v('r_lim'), envio: v('r_env'), situacao: v('r_sit'), obs: v('r_obs'), comp: S.comp}); salvar(); desenhar();
    }}, 'Adicionar')));
  if (!r.remessas.length) w.append(el('p', {class: 'indisponivel'}, 'Nenhuma remessa lançada para esta competência.'));
  else w.append(tabela(['Sistema', 'Data limite', 'Dias para o prazo', 'Envio', 'Situação', 'Observação', ''], r.remessas.map((x, n) => {
    const dias = C.diasParaPrazo(x.limite), fechada = ['Enviada', 'Processada'].includes(x.situacao);
    const cls = fechada ? 'prazo-ok' : dias === null ? '' : dias < 0 ? 'prazo-vencido' : dias <= 3 ? 'prazo-perto' : 'prazo-ok';
    const txt = dias === null ? pend('data limite') : fechada ? 'cumprido' : dias < 0 ? `vencido há ${-dias} dia(s)` : dias === 0 ? 'vence hoje' : `${dias} dia(s)`;
    return [x.sistema, x.limite || '', el('span', {class: cls}, txt), x.envio || '', x.situacao, x.obs || '', el('button', {class: 'botao', type: 'button', onclick: () => { r.remessas.splice(n, 1); salvar(); desenhar(); }}, 'Remover')];
  })));
  return w;
}
const v = id => document.getElementById(id).value;

// ---------------------------------------------------------------- aba CNES
function abaCNES() {
  const w = el('div', null, el('h2', null, 'Estabelecimento (CNES)'));
  const c = S.auto && S.auto.cnes;
  w.append(elasticnes());
  if (!c) { w.append(el('p', {class: 'indisponivel'}, 'Sem coleta do CNES para esta unidade. Rode o robô do CNES.'), pend('leitos, serviços e habilitações do CNES')); return w; }
  w.append(cabecalhoLancamento(`Fonte: ${c.fonte}. Competência do CNES: ${c.competencia_cnes}. Coleta: ${c.coletado_em}.`));
  const est = c.estabelecimento || {}, tp = est.TP_UNID;
  w.append(el('h3', null, 'Caracterização'), el('div', {class: 'kpis'}, kpi('Tipo de unidade', tp ? `${tp}${TIPOS_HOSP[tp] ? ' · ' + TIPOS_HOSP[tp] : ''}` : pend('tipo de unidade'), TIPOS_HOSP[tp] ? 'conferir com a tabela oficial do CNES' : 'código do campo TP_UNID, conferir na tabela oficial'),
    kpi('Leitos existentes', c.leitos ? inteiro(c.leitos.total_existentes) : pend('leitos'), c.leitos ? `${inteiro(c.leitos.total_sus)} SUS` : ''), kpi('Vínculos profissionais', c.profissionais ? inteiro(c.profissionais.total_vinculos) : pend('profissionais'), 'vínculos, não pessoas')));
  if (c.leitos && c.leitos.itens.length) w.append(el('h3', null, 'Leitos'), tabela(['Tipo', 'Código do leito', 'Existentes', 'SUS', 'Contratados'], c.leitos.itens.map(l => [l.tp_leito, l.cod_leito, inteiro(l.existentes), inteiro(l.sus), inteiro(l.contratados)]), [2, 3, 4]));
  if (c.servicos && c.servicos.itens.length) w.append(el('h3', null, 'Serviços especializados'), tabela(['Serviço', 'Classificação'], c.servicos.itens.map(x => [x.servico, x.classificacao])));
  w.append(el('h3', null, 'Habilitações'));
  if (c.habilitacoes && c.habilitacoes.itens.length) w.append(tabela(Object.keys(c.habilitacoes.itens[0]).map(k => k.toUpperCase()), c.habilitacoes.itens.map(h => Object.values(h))), el('p', {class: 'nota-pequena'}, 'Conforme o CNES. Para afirmar que um serviço está habilitado, confirme a portaria no DOU. [PREENCHER: portaria de habilitação, número, data e DOU]'));
  else w.append(el('p', {class: 'indisponivel'}, 'Sem habilitações no CNES coletado. Status: A verificar.'));
  if (c.profissionais) w.append(el('h3', null, 'Profissionais por grupo de CBO'), tabela(['Grupo', 'Vínculos', 'Vínculos SUS', 'Horas semanais'], c.profissionais.grupos.map(g => [g.grupo, inteiro(g.vinculos), inteiro(g.vinculos_sus), inteiro(g.horas_semanais)]), [1, 2, 3]), el('p', {class: 'nota-pequena'}, c.profissionais.unidade));
  if (c.instalacoes && c.instalacoes.itens.length) w.append(el('h3', null, 'Instalações físicas'), tabela(['Código', 'Quantidade'], c.instalacoes.itens.map(x => [x.codigo, inteiro(x.quantidade)]), [1]), el('p', {class: 'nota-pequena'}, `Total de ${inteiro(c.instalacoes.total)} instalações. [PREENCHER: descrição por código, após conferir a tabela auxiliar oficial do CNES]`));
  if (c.equipamentos && c.equipamentos.itens.length) w.append(el('h3', null, 'Equipamentos'), tabela(['Tipo', 'Código', 'Existentes', 'Em uso'], c.equipamentos.itens.map(x => [x.tipo, x.codigo, inteiro(x.existentes), inteiro(x.em_uso)]), [2, 3]), el('p', {class: 'nota-pequena'}, 'Códigos conforme tabela do CNES. [PREENCHER: descrição por código, após conferir a tabela auxiliar oficial]'));
  if (c.incentivos && c.incentivos.itens.length) w.append(el('h3', null, 'Incentivos'), tabela(Object.keys(c.incentivos.itens[0]).map(k => k.toUpperCase()), c.incentivos.itens.map(h => Object.values(h))));
  w.append(comparaCNES(c), avisosColeta(c));
  return w;
}

function elasticnes() {
  const e = S.remessas && S.remessas.elasticnes;
  if (!e) return el('span');
  return el('div', {class: 'cartao'}, el('h3', null, e.nome), el('p', null, el('span', {class: 'status A-confirmar'}, e.status)),
    el('p', null, e.uso), el('ol', {class: 'passos'}, el('li', null, 'Abra o ElastiCNES pelo link abaixo.'), el('li', null, 'Aplique o filtro tipo_estabelecimento (hospital geral ou especializado) e o município.'), el('li', null, 'Copie o código CNES da unidade e informe no filtro desta página.')),
    el('p', null, el('a', {href: e.url, target: '_blank', rel: 'noopener noreferrer'}, 'Abrir o ElastiCNES')), el('p', {class: 'nota-pequena'}, e.nota));
}

function comparaCNES(c) {
  const w = el('div', null, el('h3', null, 'Comparar com outro CNES (similaridade)'));
  const outros = ((S.indice && S.indice.hospitais) || []).filter(h => h.cnes !== S.cnes);
  if (!outros.length) { w.append(el('p', {class: 'nota-pequena'}, 'Configure ao menos dois CNES para comparar leitos, serviços e habilitações. Similaridade = itens em comum ÷ itens únicos nos dois.')); return w; }
  const sel = el('select', null, outros.map(h => el('option', {value: h.cnes}, h.nome || 'CNES ' + h.cnes))), out = el('div');
  const itens = x => ({Leitos: (x.leitos ? x.leitos.itens : []).map(l => l.tp_leito + '/' + l.cod_leito), Serviços: (x.servicos ? x.servicos.itens : []).map(s => s.servico + '|' + s.classificacao), Habilitações: (x.habilitacoes ? x.habilitacoes.itens : []).map(h => JSON.stringify(h)), Instalações: (x.instalacoes ? x.instalacoes.itens : []).map(q => q.codigo + '|' + q.quantidade), Equipamentos: (x.equipamentos ? x.equipamentos.itens : []).map(q => q.tipo + '/' + q.codigo), Incentivos: (x.incentivos ? x.incentivos.itens : []).map(h => JSON.stringify(h))});
  sel.addEventListener('change', async () => {
    const o = await carregar(D + sel.value + '.json'), b = o && o.cnes; if (!b) { limpar(out).append(el('p', {class: 'indisponivel'}, 'Sem CNES coletado para a unidade escolhida.')); return; }
    const A = itens(c), B = itens(b), linhas = Object.keys(A).map(k => { const s = C.similaridade(A[k], B[k]); return [k, s.valor === null ? pend('itens') : pctf(s.valor), inteiro(s.comuns), inteiro(s.total)]; });
    limpar(out).append(tabela(['Menu', 'Similaridade', 'Itens em comum', 'Total de itens únicos'], linhas, [1, 2, 3]));
  });
  w.append(el('label', null, 'Outro CNES ', sel), out); sel.dispatchEvent(new Event('change'));
  return w;
}

// ---------------------------------------------------------------- aba criticas e plano
function abaCriticas() {
  const d = dadosComp(), crit = avaliar(d);
  const w = el('div', null, el('h2', null, 'Críticas de dados e plano de avanço do faturamento'));
  const lista = [...crit.criticas].sort((a, b) => C.ORDEM_SEV[a.severidade] - C.ORDEM_SEV[b.severidade]);
  if (!lista.length) w.append(el('p', {class: 'indisponivel'}, 'Nenhuma crítica gerada com os dados lançados. Isso não significa ausência de problema: veja as críticas não avaliadas abaixo.'));
  else w.append(tabela(['Código', 'Severidade', 'Origem', 'Descrição', 'Ação recomendada', 'Status'], lista.map(c => [c.codigo, el('span', {class: 'sev ' + c.severidade}, c.severidade), c.origem, c.descricao, c.acao, c.status])));
  w.append(el('h3', null, 'Críticas não avaliadas por falta de dado'), el('ul', {class: 'metodo'}, crit.nao_avaliadas.map(t => el('li', null, t))));
  const p = registro().plano, i = indicadores(d);
  w.append(el('h3', null, 'Plano de avanço do faturamento'), el('p', null, 'Perda por rejeição na competência: ', mostra(i.perda, brl, 'valor rejeitado'), '. O ganho estimado é lançado pelo gestor e nunca calculado pela plataforma.'));
  w.append(el('div', {class: 'form-grade'},
    el('label', null, 'Ação', el('input', {id: 'p_acao', autocomplete: 'off'})), el('label', null, 'Crítica vinculada (código)', el('input', {id: 'p_crit', autocomplete: 'off'})),
    el('label', null, 'Prioridade', el('select', {id: 'p_pri'}, ['Alta', 'Média', 'Baixa'].map(x => el('option', {value: x}, x)))),
    el('label', null, 'Ganho estimado (R$)', el('input', {id: 'p_gan', autocomplete: 'off'})), el('label', null, 'Prazo', el('input', {id: 'p_prazo', type: 'date'})),
    el('label', null, 'Responsável', el('input', {id: 'p_resp', autocomplete: 'off'})),
    el('label', null, 'Status', el('select', {id: 'p_st'}, ['A iniciar', 'Em andamento', 'Concluída', 'Cancelada'].map(x => el('option', {value: x}, x))))),
    el('div', {class: 'acoes'}, el('button', {class: 'botao cheio', type: 'button', onclick: () => {
      if (!v('p_acao')) return;
      p.push({acao: v('p_acao'), critica: v('p_crit'), prioridade: v('p_pri'), ganho: parseNum(v('p_gan')), prazo: v('p_prazo'), responsavel: v('p_resp'), status: v('p_st')}); salvar(); desenhar();
    }}, 'Adicionar ação'), el('button', {class: 'botao', type: 'button', onclick: () => baixar('plano_avanco_' + (S.cnes || 'unidade') + '.csv', csv([['Ação', 'Crítica', 'Prioridade', 'Ganho estimado R$', 'Prazo', 'Responsável', 'Status'], ...p.map(x => [x.acao, x.critica, x.prioridade, x.ganho, x.prazo, x.responsavel, x.status])]))}, 'Exportar CSV')));
  if (!p.length) w.append(el('p', {class: 'indisponivel'}, 'Nenhuma ação registrada.'));
  else {
    w.append(tabela(['Ação', 'Crítica', 'Prioridade', 'Ganho estimado', 'Prazo', 'Responsável', 'Status', ''], p.map((x, n) => [x.acao, x.critica, x.prioridade, x.ganho == null ? pend('ganho em R$') : brl(x.ganho), x.prazo, x.responsavel || pend('responsável'), x.status, el('button', {class: 'botao', type: 'button', onclick: () => { p.splice(n, 1); salvar(); desenhar(); }}, 'Remover')]), [3]));
    const soma = p.filter(x => x.status !== 'Cancelada' && x.ganho != null).reduce((a, x) => a + x.ganho, 0);
    w.append(el('p', null, 'Ganho estimado total lançado (ações não canceladas): ', brl(soma)));
  }
  w.append(el('h3', null, 'Backup dos lançamentos'), el('div', {class: 'acoes'},
    el('button', {class: 'botao', type: 'button', onclick: () => baixar('lancamentos_hospital.json', JSON.stringify(S.local, null, 1), 'application/json')}, 'Exportar lançamentos (JSON)'),
    el('label', {class: 'botao'}, 'Importar JSON ', el('input', {type: 'file', accept: 'application/json', onchange: ev => { const f = ev.target.files[0]; if (!f) return; f.text().then(t => { try { S.local = JSON.parse(t); salvar(); desenhar(); } catch (e) { alert('Arquivo inválido.'); } }); }}))));
  return w;
}

// ---------------------------------------------------------------- aba fontes
function abaFontes() {
  const w = el('div', null, el('h2', null, 'Fontes e status das integrações'));
  w.append(el('p', null, 'Status usados: Ativa (testada), Em teste, Manual (lançamento pelo usuário), Bloqueada e A confirmar. Nenhuma integração é considerada ativa sem teste registrado.'));
  const L = [['SIH/SUS, arquivos RD, RJ e ER (FTP DATASUS)', 'Em teste', 'Robô coletar_hospital_sih.py. Layouts a confirmar na primeira execução (modo --sondar).'],
    ['SIA/SUS, arquivos PA (FTP DATASUS)', 'Em teste', 'Robô coletar_hospital_sia.py. Layout a confirmar (modo --sondar).'],
    ['CNES, arquivos ST, LT, SR, HB e PF (FTP DATASUS)', 'Em teste', 'Robô coletar_hospital_cnes.py. Substitui a coleta pelo ElastiCNES.'],
    ['SIHD, SIASUS, CIHA e Transmissor (remessas e prazos)', 'Manual', 'Consulta no portal oficial e lançamento pelo gestor.'],
    ['ElastiCNES', 'A confirmar', 'Somente link de consulta. Descartado para coleta automática nas regras do projeto.'],
    ['SIGTAP (descrição e valores oficiais por competência)', 'Manual', 'Lançamento pelo usuário. [PREENCHER: tabela SIGTAP da competência]']];
  w.append(tabela(['Fonte', 'Status', 'Observação'], L.map(([a, b, c]) => [a, el('span', {class: 'status ' + b.replace(' ', '-')}, b), c])));
  const st = S.status;
  w.append(el('p', {class: 'nota-pequena'}, st && st.gerado_em ? 'Última sondagem das páginas de remessa: ' + st.gerado_em.slice(0, 16).replace('T', ' ') : 'Sondagem das páginas de remessa ainda não executada.'));
  w.append(el('h3', null, 'Pendências desta entrega'), el('ul', {class: 'metodo'},
    ['[PREENCHER: CNES autorizado da unidade e nome autorizado, em config/hospitais.json]', '[PREENCHER: competência inicial para teste]', '[PREENCHER: tabela SIGTAP da competência, para descrição e valores oficiais]',
      '[PREENCHER: lista oficial de condições sensíveis à atenção primária (ICSAP)]', '[PREENCHER: descrição dos códigos de erro de rejeição do SIH]', '[PREENCHER: tabelas oficiais de tipo de unidade e de financiamento para conferência]', '[PREENCHER: portarias de habilitação de cada serviço]'].map(t => el('li', null, t))));
  return w;
}

// ---------------------------------------------------------------- inicializacao
async function carregarUnidade() {
  S.auto = S.cnes ? await carregar(D + S.cnes + '.json') : null;
  const sel = limpar(document.getElementById('selComp'));
  const ks = Object.keys((S.auto && S.auto.competencias) || {}).map(chaveParaComp), loc = Object.keys(S.local[S.cnes || '_'] || {}).filter(x => x !== '_');
  const todas = [...new Set([...ks, ...loc])].sort((a, b) => compParaChave(b).localeCompare(compParaChave(a)));
  sel.append(el('option', {value: ''}, todas.length ? 'Escolha a competência' : 'Sem competência'));
  todas.forEach(c => sel.append(el('option', {value: c}, c)));
  if (!todas.includes(S.comp)) S.comp = todas[0] || '';
  sel.value = S.comp;
  desenhar();
}

async function iniciar() {
  const [indice, remessas, status] = await Promise.all([carregar(D + 'indice.json'), carregar(BASE + 'config/remessas_datasus.json'), carregar(D + 'status_fontes.json')]);
  Object.assign(S, {indice, remessas, status});
  const sel = limpar(document.getElementById('selHosp'));
  const hs = (indice && indice.hospitais) || [];
  sel.append(el('option', {value: ''}, hs.length ? 'Escolha a unidade' : 'Nenhuma unidade configurada'));
  hs.forEach(h => sel.append(el('option', {value: h.cnes}, `${h.nome || 'CNES ' + h.cnes} (${h.uf})`)));
  sel.addEventListener('change', () => { S.cnes = sel.value; document.getElementById('inpCnes').value = ''; carregarUnidade(); });
  document.getElementById('inpCnes').addEventListener('input', ev => { const x = ev.target.value.replace(/\D/g, ''); ev.target.value = x; if (x.length === 7) { S.cnes = x; sel.value = ''; carregarUnidade(); } });
  document.getElementById('selComp').addEventListener('change', ev => { S.comp = ev.target.value; desenhar(); });
  document.getElementById('inpComp').addEventListener('keydown', ev => {
    if (ev.key !== 'Enter') return;
    const c = ev.target.value.trim();
    if (!compParaChave(c) || +c.slice(0, 2) < 1 || +c.slice(0, 2) > 12) { alert('Use o formato MM/AAAA.'); return; }
    (S.local[S.cnes || '_'] ||= {})[c] ||= {sih: {}, remessas: [], plano: [], meta: {}}; salvar(); S.comp = c; ev.target.value = ''; carregarUnidade();
  });
  desenhar();
}
iniciar();
