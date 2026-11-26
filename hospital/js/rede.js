// Aba "Rede e rejeicoes (ES)": le os JSON gerados pelo super robo (rede_indice, rede_<cod>, rede_rejeicao_es).
// Visual com cards e graficos SVG. Textos externos nunca entram como HTML (el/sv). Sem estilo embutido (compativel com CSP style-src 'self').
import {el, limpar, carregar, tabela, inteiro, decimal} from './util.js';

const D = new URL('../', import.meta.url).href + 'dados/';
const NS = 'http://www.w3.org/2000/svg';
const sv = (tag, attrs, ...filhos) => {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs || {})) { if (v == null || v === false) continue; e.setAttribute(k, v === true ? '' : v); }
  for (const f of filhos.flat()) if (f != null) e.append(f.nodeType ? f : document.createTextNode(String(f)));
  return e;
};
export const brl = v => new Intl.NumberFormat('pt-BR', {style: 'currency', currency: 'BRL'}).format(v);
export const brlc = v => v >= 1e6 ? 'R$ ' + decimal(v / 1e6, 1) + ' mi' : v >= 1e3 ? 'R$ ' + decimal(v / 1e3, 0) + ' mil' : brl(v);
export const num = v => typeof v === 'number' && Number.isFinite(v);
export const pct = v => num(v) ? decimal(v, 1) + '%' : (typeof v === 'string' ? v : 'sem dado');
export const arr = x => Array.isArray(x) ? x : [];
export const pend = txt => el('span', {class: 'pendente'}, `[PREENCHER: ${txt}]`);
export const aviso = txt => el('p', {class: 'aviso'}, txt);
const motivo = m => m ? `${m.texto_manual} (manual do SIH, p. ${m.pagina_manual}; ${String(m.status || '').toLowerCase()})` : 'sem descrição localizada';
const CORES = ['#1351b4', '#168821', '#e0a100', '#0c326f', '#7a3fb5', '#c2185b', '#00838f'];

const ICONES = {
  doc: 'M6 2h9l5 5v15H6z M14 2v6h6', alerta: 'M12 3l10 18H2z M12 10v5 M12 18v.5', hospital: 'M4 21V4h10v17 M14 9h6v12 M8 8v4 M6 10h4 M7 21v-4h2v4 M17 13h1 M17 17h1',
  ok: 'M5 12l4 4L19 7', agenda: 'M4 6h16v14H4z M4 10h16 M8 3v4 M16 3v4', moeda: 'M12 3v18 M16 7c-1-1-2.5-1.5-4-1.5-2.5 0-4 1.2-4 3s1.5 2.5 4 3 4 1.2 4 3-1.5 3-4 3c-1.7 0-3.2-.6-4.2-1.7',
  grafico: 'M4 20V4 M4 20h16 M8 16v-5 M12 16V8 M16 16v-8', pessoas: 'M9 11a3 3 0 100-6 3 3 0 000 6 M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6 M17 11a2.5 2.5 0 100-5 M16 14c3 0 5 2.2 5 5', busca: 'M11 4a7 7 0 100 14 7 7 0 000-14 M20 20l-4-4',
  imprimir: 'M7 8V3h10v5 M6 17H4v-7h16v7h-2 M7 14h10v7H7z', info: 'M12 3a9 9 0 100 18 9 9 0 000-18 M12 11v5 M12 8v.5'
};
export const icone = (n, cls) => sv('svg', {viewBox: '0 0 24 24', class: 'rd-ico ' + (cls || ''), 'aria-hidden': 'true', focusable: 'false', fill: 'none', stroke: 'currentColor', 'stroke-width': '1.8', 'stroke-linecap': 'round', 'stroke-linejoin': 'round'}, sv('path', {d: ICONES[n]}));

export const kpi = (ic, tom, rot, val, nota) => el('div', {class: 'rd-kpi rd-' + tom},
  el('div', {class: 'rd-kpi-ic'}, icone(ic)),
  el('div', {class: 'rd-kpi-tx'}, el('div', {class: 'rd-rot'}, rot), el('div', {class: 'rd-val'}, val), nota ? el('div', {class: 'rd-nota'}, nota) : null));
export const cartao = (titulo, sub, ...filhos) => el('section', {class: 'rd-card'}, el('h3', null, titulo), sub ? el('p', {class: 'rd-sub'}, sub) : null, ...filhos);
export const detalhesTabela = (rotulo, tab) => el('details', {class: 'rd-det'}, el('summary', null, rotulo), tab);
const SEV = {Alta: ['rd-sev-alta', '▲'], Media: ['rd-sev-media', '◆'], 'Média': ['rd-sev-media', '◆'], Baixa: ['rd-sev-baixa', '●']};
const chipSev = (sev, n) => { const [c, s] = SEV[sev] || ['rd-sev-baixa', '●']; return el('span', {class: 'rd-chip ' + c}, `${s} ${sev === 'Media' ? 'Média' : sev}${n != null ? ': ' + inteiro(n) : ''}`); };

// ---------- graficos ----------
function leitura() { const r = el('p', {class: 'rd-leitura', 'aria-live': 'polite'}, 'Passe o mouse ou use o Tab sobre uma barra para ver o detalhe.'); return r; }
function ligar(no, texto, r) { no.setAttribute('tabindex', '0'); const f = () => { r.textContent = texto; }; no.addEventListener('mouseenter', f); no.addEventListener('focus', f); no.setAttribute('aria-label', texto); }

function pareto(itens, nomeMun) {
  const W = 720, H = 300, m = {t: 16, r: 44, b: 64, l: 52}, iw = W - m.l - m.r, ih = H - m.t - m.b;
  const max = Math.max(...itens.map(i => i.rejeitadas || 0), 1);
  const passo = niceStep(max / 4); const topo = Math.ceil(max / passo) * passo;
  const bw = iw / itens.length, rd = leitura();
  const g = sv('svg', {viewBox: `0 0 ${W} ${H}`, class: 'rd-svg', role: 'group', 'aria-label': 'Gráfico de Pareto: AIH rejeitadas por CNES e percentual acumulado'});
  for (let v = 0; v <= topo; v += passo) {
    const y = m.t + ih - (v / topo) * ih;
    g.append(sv('line', {x1: m.l, x2: W - m.r, y1: y, y2: y, class: 'rd-grade'}), sv('text', {x: m.l - 8, y: y + 4, class: 'rd-eixo', 'text-anchor': 'end'}, inteiro(v)));
  }
  [0, 50, 100].forEach(p => g.append(sv('text', {x: W - m.r + 8, y: m.t + ih - (p / 100) * ih + 4, class: 'rd-eixo rd-eixo-d'}, p + '%')));
  const pts = [];
  itens.forEach((i, k) => {
    const h = ((i.rejeitadas || 0) / topo) * ih, x = m.l + k * bw + bw * 0.18, y = m.t + ih - h;
    const r = sv('rect', {x, y, width: bw * 0.64, height: h, rx: 3, class: 'rd-barra'});
    ligar(r, `CNES ${i.cnes} (${nomeMun(i.municipio_movimento)}): ${inteiro(i.rejeitadas)} AIH rejeitadas, ${pct(i.pct_do_total)} do total, ${pct(i.pct_acumulado)} acumulado`, rd);
    g.append(r);
    const cx = m.l + k * bw + bw / 2, cy = m.t + ih - ((i.pct_acumulado || 0) / 100) * ih;
    pts.push([cx, cy]);
    const t = sv('text', {x: cx, y: m.t + ih + 14, class: 'rd-eixo', 'text-anchor': 'end', transform: `rotate(-40 ${cx} ${m.t + ih + 14})`}, i.cnes);
    g.append(t);
  });
  g.append(sv('polyline', {points: pts.map(p => p.join(',')).join(' '), class: 'rd-linha', fill: 'none'}));
  pts.forEach(p => g.append(sv('circle', {cx: p[0], cy: p[1], r: 3.5, class: 'rd-ponto'})));
  g.append(sv('text', {x: m.l, y: 11, class: 'rd-eixo-tit'}, 'AIH rejeitadas'), sv('text', {x: W - m.r, y: 11, class: 'rd-eixo-tit', 'text-anchor': 'end'}, '% acumulado'));
  return el('figure', {class: 'rd-fig'}, g, rd, el('figcaption', {class: 'rd-legenda'}, el('span', {class: 'rd-leg rd-leg-barra'}, 'AIH rejeitadas'), el('span', {class: 'rd-leg rd-leg-linha'}, '% acumulado do total do ES')));
}
function niceStep(x) { const e = Math.pow(10, Math.floor(Math.log10(x || 1))), f = x / e; return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * e; }

function barrasRecuperacao(itens, nomeMun) {
  const melhor = itens.reduce((a, i) => num(i.pct_recuperadas) && (!a || i.pct_recuperadas > a.pct_recuperadas) ? i : a, null);
  const w = el('div', {class: 'rd-rank'});
  itens.forEach(i => {
    const v = num(i.pct_recuperadas) ? i.pct_recuperadas : null;
    const barra = el('span', {class: 'rd-fill'});
    requestAnimationFrame(() => { barra.style.width = (v == null ? 0 : Math.max(Math.min(v, 100), v > 0 ? 1.5 : 0)) + '%'; });
    w.append(el('div', {class: 'rd-rank-l'},
      el('div', {class: 'rd-rank-n'}, el('strong', null, 'CNES ' + i.cnes), el('span', null, nomeMun(i.municipio_movimento)), melhor && i === melhor ? el('em', {class: 'rd-ref'}, 'referência interna') : null),
      el('div', {class: 'rd-trilho', role: 'img', 'aria-label': `CNES ${i.cnes}: ${pct(v)} recuperadas`}, barra),
      el('div', {class: 'rd-rank-v'}, pct(v))));
  });
  return w;
}

function rosca(itens) {
  const soma = {}; let total = 0;
  itens.forEach(i => arr(i.principais_codigos_erro).forEach(c => { soma[c.codigo_erro] = soma[c.codigo_erro] || {aih: 0, motivo: c.motivo_provavel}; soma[c.codigo_erro].aih += c.aih || 0; total += c.aih || 0; }));
  const lista = Object.entries(soma).sort((a, b) => b[1].aih - a[1].aih).slice(0, 6);
  if (!lista.length || !total) return aviso('A confirmar: sem códigos de erro na base.');
  const R = 62, C = 2 * Math.PI * R; let off = 0;
  const g = sv('svg', {viewBox: '0 0 160 160', class: 'rd-rosca', role: 'img', 'aria-label': 'Distribuição das AIH rejeitadas por código de erro'}, sv('circle', {cx: 80, cy: 80, r: R, fill: 'none', class: 'rd-rosca-fundo', 'stroke-width': 22}));
  lista.forEach(([c, v], k) => {
    const frac = v.aih / total;
    g.append(sv('circle', {cx: 80, cy: 80, r: R, fill: 'none', stroke: CORES[k % CORES.length], 'stroke-width': 22, 'stroke-dasharray': `${frac * C} ${C}`, 'stroke-dashoffset': -off, transform: 'rotate(-90 80 80)'}, sv('title', null, `${c}: ${inteiro(v.aih)} AIH`)));
    off += frac * C;
  });
  g.append(sv('text', {x: 80, y: 78, 'text-anchor': 'middle', class: 'rd-rosca-n'}, inteiro(total)), sv('text', {x: 80, y: 96, 'text-anchor': 'middle', class: 'rd-rosca-t'}, 'AIH nos 5 principais'));
  const leg = el('ul', {class: 'rd-rosca-leg'}, lista.map(([c, v], k) => el('li', null, el('span', {class: 'rd-amostra', 'data-c': String(k % CORES.length)}), el('div', null, el('strong', null, `${c} `, el('span', {class: 'rd-peq'}, `${inteiro(v.aih)} AIH (${pct(v.aih / total * 100)})`)), el('div', {class: 'rd-peq'}, motivo(v.motivo))))));
  return el('div', {class: 'rd-rosca-w'}, g, leg);
}

function gauge(v, rot) {
  const ok = num(v), f = ok ? Math.max(0, Math.min(v, 100)) / 100 : 0, R = 46, L = Math.PI * R;
  const arco = `M ${50 - R} 56 A ${R} ${R} 0 0 1 ${50 + R} 56`;
  return el('div', {class: 'rd-gauge'}, sv('svg', {viewBox: '0 0 100 64', role: 'img', 'aria-label': `${rot}: ${pct(v)}`},
    sv('path', {d: arco, fill: 'none', class: 'rd-g-fundo', 'stroke-width': 9, 'stroke-linecap': 'round'}),
    ok ? sv('path', {d: arco, fill: 'none', class: 'rd-g-valor', 'stroke-width': 9, 'stroke-linecap': 'round', 'stroke-dasharray': `${f * L} ${L}`}) : null,
    sv('text', {x: 50, y: 52, 'text-anchor': 'middle', class: 'rd-g-n'}, ok ? decimal(v, 0) + '%' : '—')), el('div', {class: 'rd-peq'}, rot));
}

const STATUS = {Habilitado: 'rd-st-ok', 'Em habilitação': 'rd-st-em', 'A verificar': 'rd-st-av', 'Não habilitado': 'rd-st-no'};
function pilha(resumo, total) {
  const ent = Object.entries(resumo || {}).filter(([, n]) => n > 0);
  if (!ent.length || !total) return el('div', {class: 'rd-peq'}, 'sem habilitações na base');
  const barra = el('div', {class: 'rd-pilha', role: 'img', 'aria-label': ent.map(([k, n]) => `${k}: ${n}`).join(', ')});
  ent.forEach(([k, n]) => { const s = el('span', {class: STATUS[k] || 'rd-st-av'}); s.style.flexGrow = String(n); barra.append(s); });
  return el('div', null, barra, el('div', {class: 'rd-peq'}, ent.map(([k, n]) => `${k} ${n}`).join(' · ')));
}

export function barrasMes(meses, campo, rotulo = 'Produção SIH por mês') {
  const W = 640, H = 220, m = {t: 14, r: 12, b: 34, l: 54}, iw = W - m.l - m.r, ih = H - m.t - m.b, rd = leitura();
  const val = x => num(x[campo]) ? x[campo] : 0, max = Math.max(...meses.map(val), 1), passo = niceStep(max / 4), topo = Math.ceil(max / passo) * passo, bw = iw / meses.length;
  const g = sv('svg', {viewBox: `0 0 ${W} ${H}`, class: 'rd-svg', role: 'group', 'aria-label': rotulo});
  for (let v = 0; v <= topo; v += passo) { const y = m.t + ih - (v / topo) * ih; g.append(sv('line', {x1: m.l, x2: W - m.r, y1: y, y2: y, class: 'rd-grade'}), sv('text', {x: m.l - 6, y: y + 4, class: 'rd-eixo', 'text-anchor': 'end'}, /valor/.test(campo) ? brlc(v) : inteiro(v))); }
  meses.forEach((x, k) => {
    const h = (val(x) / topo) * ih, bx = m.l + k * bw + bw * 0.2, r = sv('rect', {x: bx, y: m.t + ih - h, width: bw * 0.6, height: h, rx: 3, class: 'rd-barra'});
    const rot = x.competencia || x.mes_processamento || '';
    ligar(r, x.aih !== undefined ? `${rot}: ${inteiro(x.aih)} AIH, ${num(x.valor_total) ? brl(x.valor_total) : 'sem valor'}, ocupação estimada ${pct(x.ocupacao_estimada_pct)}` : `${rot}: ${/valor/.test(campo) ? brl(x[campo]) : inteiro(x[campo])}`, rd); g.append(r);
    g.append(sv('text', {x: bx + bw * 0.3, y: H - 12, class: 'rd-eixo', 'text-anchor': 'middle'}, rot));
  });
  return el('figure', {class: 'rd-fig'}, g, rd);
}

// ---------- pagina ----------
export function abaRede() {
  const raiz = el('div', {class: 'rede'});
  raiz.append(el('p', {class: 'rd-carregando'}, 'Carregando dados da rede hospitalar...'));
  montar(raiz);
  return raiz;
}

async function montar(raiz) {
  const [indice, estado] = await Promise.all([carregar(D + 'rede_indice.json'), carregar(D + 'rede_rejeicao_es.json')]);
  limpar(raiz);
  if (!indice && !estado) { raiz.append(aviso('[PREENCHER: dados do super robô ainda não publicados nesta página. Rode partelli-coleta publicar no notebook.]')); return; }
  const muns = arr(indice && indice.municipios), nomes = {};
  muns.forEach(m => { nomes[String(m.cod).slice(0, 6)] = m.nome; });
  const nomeMun = c => nomes[String(c)] || (c ? 'município ' + c : 'município sem dado');
  raiz.append(cabecalho(indice, estado));
  const painelE = estado ? painelEstado(estado, nomeMun) : aviso('A confirmar: sem dados de rejeição do estado.');
  const painelM = painelMunicipios(muns);
  raiz.append(abas([['Panorama do ES', painelE], ['Por município', painelM], ['Fontes e conexões', painelFontes()]]));
  raiz.append(rodapeFonte());
}

function cabecalho(indice, estado) {
  const quando = (indice && indice.gerado_em) || (estado && estado.gerado_em);
  return el('header', {class: 'rd-topo'},
    el('div', null, el('h2', null, 'Gestão hospitalar'), el('p', {class: 'rd-sub'}, 'Tudo que o robô colhe e valida: rejeição de AIH, produção SIH, SIA e CIHA, rede CNES, financeiro, recursos, território, críticas e plano de avanço do faturamento.')),
    el('div', {class: 'rd-topo-acoes'}, el('span', {class: 'rd-pilula'}, icone('agenda'), quando ? 'Dados gerados em ' + quando : pend('data de geração')),
      el('button', {type: 'button', class: 'rd-btn', onclick: () => window.print()}, icone('imprimir'), 'Imprimir')));
}

function rodapeFonte() {
  return el('p', {class: 'rd-fonte'}, icone('info'), 'Fonte: SIH/SUS, SIA/SUS, CIHA e CNES (arquivos do DATASUS) e fontes oficiais de financiamento, lidos e validados pelo super robô do notebook. Somente dados agregados, identificados por código CNES e código do município. Campo sem dado aparece como [PREENCHER] e vai para a lista de pendências. Percentual de recuperação, ocupação e perda são estimativas de apoio à gestão e não substituem o censo hospitalar nem o relatório oficial de críticas.');
}

function abas(lista) {
  const barra = el('div', {class: 'rd-abas', role: 'tablist'}), corpo = el('div'), btns = [], pn = [];
  const ir = k => { btns.forEach((b, j) => { const on = j === k; b.setAttribute('aria-selected', on ? 'true' : 'false'); b.tabIndex = on ? 0 : -1; pn[j].hidden = !on; }); pn[k].querySelectorAll('.rd-lazy').forEach(a => a.carregar && a.carregar()); };
  lista.forEach(([rot, no], k) => {
    const b = el('button', {type: 'button', role: 'tab', class: 'rd-aba', onclick: () => ir(k)}, rot);
    b.addEventListener('keydown', ev => { if (ev.key === 'ArrowRight' || ev.key === 'ArrowLeft') { const n = (k + (ev.key === 'ArrowRight' ? 1 : lista.length - 1)) % lista.length; ir(n); btns[n].focus(); } });
    const p = el('div', {role: 'tabpanel', class: 'rd-painel'}, no); btns.push(b); pn.push(p); barra.append(b); corpo.append(p);
  });
  ir(0);
  return el('div', null, barra, corpo);
}

export function painelEstado(e, nomeMun) {
  const itens = arr(e.itens);
  if (!itens.length) return aviso(e.situacao || 'A confirmar: sem dados de rejeição.');
  const fech = itens.reduce((s, i) => s + (i.rejeitadas_fechadas || 0), 0), rec = itens.reduce((s, i) => s + (i.recuperadas || 0), 0);
  const w = el('div');
  w.append(el('div', {class: 'rd-kpis'},
    kpi('alerta', 'verm', 'AIH rejeitadas no ES', inteiro(e.total_rejeitadas_es), 'arquivo ER, 2026'),
    kpi('hospital', 'azul', 'CNES listados', inteiro(e.cnes_listados), `${pct(e.pct_acumulado_listados)} do total de rejeições`),
    kpi('ok', 'verde', 'Recuperadas depois', fech > 0 ? pct(rec / fech * 100) : 'sem dado', 'mesma AIH aprovada em competência posterior (CNES listados)'),
    kpi('agenda', 'amar', 'Competência em aberto', e.competencia_em_aberto || 'sem dado', 'fica fora da conta de recuperação')));
  w.append(el('div', {class: 'rd-duas'},
    cartao('Concentração das rejeições', 'Poucos CNES concentram a maior parte das AIH rejeitadas. A linha mostra o acumulado.', pareto(itens, nomeMun),
      detalhesTabela('Ver em tabela', tabela(['CNES', 'Município', 'Rejeitadas', '% do total', '% acumulado'], itens.map(i => [i.cnes, nomeMun(i.municipio_movimento), inteiro(i.rejeitadas), pct(i.pct_do_total), pct(i.pct_acumulado)]), [2, 3, 4]))),
    cartao('Quanto volta a ser aprovado', 'Percentual das AIH rejeitadas que reaparecem aprovadas com o mesmo número e CNES em competência posterior.', barrasRecuperacao(itens, nomeMun),
      el('p', {class: 'rd-peq'}, 'A referência interna é o melhor CNES da própria lista, e não uma meta oficial.'))));
  w.append(cartao('Motivos mais frequentes (código de erro)', 'Descrição retirada do manual do SIH pelos 3 últimos dígitos do código. Correspondência provável, a confirmar na tela SIHD2 de uma AIH.', rosca(itens)));
  w.append(cartao('Detalhe por CNES', null, detalhesTabela('Abrir tabela completa com os principais códigos', tabela(['CNES', 'Município', 'Rejeitadas', '% recuperadas', 'Principais códigos de erro'],
    itens.map(i => [i.cnes, nomeMun(i.municipio_movimento), inteiro(i.rejeitadas), pct(i.pct_recuperadas), el('div', null, arr(i.principais_codigos_erro).map(c => el('div', null, `${inteiro(c.aih)} AIH, ${c.codigo_erro}: `, motivo(c.motivo_provavel))))]), [2, 3])),
    el('p', {class: 'rd-peq'}, `${e.regra || ''} ${e.obs || ''}`)));
  return w;
}

function painelMunicipios(muns) {
  const w = el('div');
  if (!muns.length) { w.append(aviso('A confirmar: nenhum município exportado.')); return w; }
  const grade = el('div', {class: 'rd-muns', role: 'list'}), det = el('div', {class: 'rd-det-mun', 'aria-live': 'polite'}), dados = {};
  const busca = el('input', {type: 'search', class: 'rd-busca', placeholder: 'Buscar município', 'aria-label': 'Buscar município'});
  const cartoes = muns.map(m => {
    const b = el('button', {type: 'button', class: 'rd-mun', role: 'listitem'}, el('strong', null, m.nome), el('span', {class: 'rd-peq'}, `${inteiro(m.hospitais)} hospital(is)`), el('span', {class: 'rd-mun-res rd-peq'}, 'Carregando...'));
    b.addEventListener('click', () => { cartoes.forEach(c => c[1].classList.remove('rd-sel')); b.classList.add('rd-sel'); abrir(m); });
    return [m, b];
  });
  cartoes.forEach(c => grade.append(c[1]));
  busca.addEventListener('input', () => { const q = busca.value.trim().toLowerCase(); cartoes.forEach(([m, b]) => { b.hidden = q !== '' && !m.nome.toLowerCase().includes(q); }); });
  async function abrir(m) {
    limpar(det); det.append(el('p', null, 'Carregando...'));
    const d = dados[m.cod] || (dados[m.cod] = await carregar(D + `rede_${m.cod}.json`));
    limpar(det); det.append(d ? municipioPainel(m, d) : aviso('A confirmar: arquivo do município não encontrado.'));
    det.scrollIntoView && det.scrollIntoView({behavior: 'smooth', block: 'start'});
  }
  // resumo nos cartoes: carrega todos em paralelo (poucos arquivos pequenos)
  muns.forEach(async (m, k) => {
    const d = dados[m.cod] = await carregar(D + `rede_${m.cod}.json`), r = cartoes[k][1].querySelector('.rd-mun-res'), h = d && d.hospitais;
    limpar(r);
    if (!h || !arr(h.itens).length) { r.append('sem hospital na base'); return; }
    const sev = h.criticas_por_severidade || {}, aih = h.itens.reduce((s, i) => s + ((i.indicadores || {}).aih || 0), 0);
    r.append(`${inteiro(aih)} AIH em 2026 · `, sev.Alta ? chipSev('Alta', sev.Alta) : 'sem crítica alta');
  });
  w.append(el('div', {class: 'rd-filtros'}, busca), grade, det);
  return w;
}

function municipio(d) {
  const h = d.hospitais, w = el('div');
  if (!h || !arr(h.itens).length) { w.append(aviso((h && (h.situacao || h.obs)) || 'A confirmar: sem hospital na base.')); return w; }
  const sev = h.criticas_por_severidade || {}, itens = h.itens;
  const aih = itens.reduce((s, i) => s + ((i.indicadores || {}).aih || 0), 0), valor = itens.reduce((s, i) => s + ((i.indicadores || {}).valor_total || 0), 0);
  w.append(el('div', {class: 'rd-kpis'},
    kpi('hospital', 'azul', 'Hospitais', inteiro(h.total)), kpi('doc', 'azul', 'AIH aprovadas (2026)', inteiro(aih), 'soma dos hospitais'), kpi('moeda', 'verde', 'Valor total', valor ? brlc(valor) : 'sem dado', 'SH + SP + complemento federal'),
    el('div', {class: 'rd-kpi rd-amar'}, el('div', {class: 'rd-kpi-ic'}, icone('alerta')), el('div', {class: 'rd-kpi-tx'}, el('div', {class: 'rd-rot'}, 'Críticas abertas'), el('div', {class: 'rd-chips'}, chipSev('Alta', sev.Alta || 0), chipSev('Media', sev.Media || 0), chipSev('Baixa', sev.Baixa || 0))))));
  // comparativo
  const metr = {aih: ['AIH aprovadas', i => (i.indicadores || {}).aih], valor: ['Valor total', i => (i.indicadores || {}).valor_total], media: ['Média por AIH', i => (i.indicadores || {}).media_por_aih], rej: ['% de rejeição no período', i => (i.rejeicao_sih || {}).pct_rejeicao_periodo]};
  const sel = el('select', {'aria-label': 'Indicador do comparativo', class: 'rd-sel-ind'}, Object.entries(metr).map(([k, v]) => el('option', {value: k}, v[0])));
  const comp = el('div'), pintar = () => { const [rot, f] = metr[sel.value], f2 = sel.value === 'valor' || sel.value === 'media' ? brl : sel.value === 'rej' ? pct : inteiro; limpar(comp); comp.append(barrasHosp(itens, f, f2, rot)); };
  sel.addEventListener('change', pintar); pintar();
  w.append(cartao('Comparativo entre hospitais', null, el('label', {class: 'rd-rot-sel'}, 'Indicador ', sel), comp));
  // cartoes dos hospitais
  const det = el('div', {class: 'rd-hdet', 'aria-live': 'polite'}), grade = el('div', {class: 'rd-hosps'});
  itens.forEach(i => {
    const ind = i.indicadores || {}, rj = i.rejeicao_sih || {}, hb = i.checklist_habilitacao || {}, s = {}; arr(i.criticas).forEach(c => { s[c.severidade] = (s[c.severidade] || 0) + 1; });
    const c = el('article', {class: 'rd-hosp'},
      el('header', null, el('h4', null, 'CNES ' + i.cnes), num(rj.pct_rejeicao_periodo) ? el('span', {class: 'rd-chip rd-sev-media'}, 'rejeição ' + pct(rj.pct_rejeicao_periodo)) : null),
      el('dl', {class: 'rd-dl'}, el('div', null, el('dt', null, 'AIH (2026)'), el('dd', null, inteiro(ind.aih))), el('div', null, el('dt', null, 'Valor total'), el('dd', null, num(ind.valor_total) ? brlc(ind.valor_total) : 'sem dado')),
        el('div', null, el('dt', null, 'Média por AIH'), el('dd', null, num(ind.media_por_aih) ? brl(ind.media_por_aih) : 'sem dado'))),
      gauge(ind.ocupacao_estimada_pct, 'ocupação estimada'),
      el('div', {class: 'rd-sub-t'}, 'Habilitações'), pilha(hb.resumo, hb.total),
      el('div', {class: 'rd-chips'}, chipSev('Alta', s.Alta || 0), chipSev('Media', (s.Media || 0) + (s['Média'] || 0)), chipSev('Baixa', s.Baixa || 0)),
      el('button', {type: 'button', class: 'rd-btn rd-btn-p', onclick: () => { grade.querySelectorAll('.rd-hosp').forEach(x => x.classList.remove('rd-sel')); c.classList.add('rd-sel'); limpar(det); det.append(hospital(i)); det.scrollIntoView && det.scrollIntoView({behavior: 'smooth', block: 'start'}); }}, 'Ver detalhes'));
    grade.append(c);
  });
  w.append(el('h3', {class: 'rd-h3'}, 'Hospitais'), grade, det, el('p', {class: 'rd-peq'}, h.obs || ''));
  return w;
}

function barrasHosp(itens, f, fmt, rot) {
  const vals = itens.map(f), max = Math.max(...vals.filter(num), 0) || 1, w = el('div', {class: 'rd-rank'});
  itens.forEach((i, k) => {
    const v = vals[k], barra = el('span', {class: 'rd-fill'});
    requestAnimationFrame(() => { barra.style.width = (num(v) ? Math.max(v / max * 100, v > 0 ? 1.5 : 0) : 0) + '%'; });
    w.append(el('div', {class: 'rd-rank-l'}, el('div', {class: 'rd-rank-n'}, el('strong', null, 'CNES ' + i.cnes)), el('div', {class: 'rd-trilho', role: 'img', 'aria-label': `CNES ${i.cnes}, ${rot}: ${num(v) ? fmt(v) : 'sem dado'}`}, barra), el('div', {class: 'rd-rank-v'}, num(v) ? fmt(v) : 'sem dado')));
  });
  return w;
}

function hospital(i) {
  const w = el('section', {class: 'rd-hdet-in'}, el('h3', null, `CNES ${i.cnes}: detalhe`));
  const ind = i.indicadores || {};
  w.append(el('div', {class: 'rd-kpis'},
    kpi('doc', 'azul', 'AIH aprovadas', inteiro(ind.aih), `${inteiro(ind.meses_com_producao)} mês(es) com produção`),
    kpi('moeda', 'verde', 'Valor total', num(ind.valor_total) ? brlc(ind.valor_total) : 'sem dado', num(ind.valor_total) ? brl(ind.valor_total) : 'SH + SP + complemento federal'),
    kpi('grafico', 'azul', 'Média por AIH', num(ind.media_por_aih) ? brlc(ind.media_por_aih) : 'sem dado', num(ind.media_por_aih) ? brl(ind.media_por_aih) + ' (valor total ÷ AIH)' : 'valor total ÷ AIH'),
    kpi('agenda', 'azul', 'Permanência média', num(ind.permanencia_media_dias) ? decimal(ind.permanencia_media_dias, 1) + ' dias' : 'sem dado', 'dias ÷ AIH'),
    kpi('hospital', 'amar', 'Ocupação estimada', pct(ind.ocupacao_estimada_pct), 'ESTIMATIVA, não substitui o censo'),
    kpi('pessoas', 'verm', 'Mortalidade hospitalar', pct(ind.mortalidade_hospitalar_pct), 'óbitos ÷ AIH')));
  const prod = arr((i.producao || {}).sih_por_mes);
  const sec = cartao('Produção SIH por mês', null);
  if (prod.length) {
    const sel = el('select', {'aria-label': 'Indicador mensal'}, el('option', {value: 'aih'}, 'AIH aprovadas'), el('option', {value: 'valor_total'}, 'Valor total')), fig = el('div'), p = () => { limpar(fig); fig.append(barrasMes(prod, sel.value)); };
    sel.addEventListener('change', p); p();
    sec.append(el('label', {class: 'rd-rot-sel'}, 'Indicador ', sel), fig, detalhesTabela('Ver em tabela', tabela(['Competência', 'AIH', 'Valor total', 'SH', 'SP', 'Complemento federal', 'Ocupação estimada'],
      prod.map(x => [x.competencia, inteiro(x.aih), brl(x.valor_total), brl(x.sh), brl(x.sp), brl((x.sh_fed || 0) + (x.sp_fed || 0)), pct(x.ocupacao_estimada_pct)]), [1, 2, 3, 4, 5, 6])));
  } else sec.append(aviso('A confirmar: sem produção SIH na base.'));
  w.append(sec);
  const rj = i.rejeicao_sih, sr = cartao('Rejeição (arquivo ER)', null);
  if (!rj || rj.situacao) sr.append(aviso((rj && rj.situacao) || 'A confirmar: sem dado de rejeição.'));
  else {
    const rec = rj.reapresentacao || {};
    sr.append(el('div', {class: 'rd-kpis'}, kpi('alerta', 'verm', 'AIH rejeitadas', inteiro(rj.total_rejeitadas), `${pct(rj.pct_rejeicao_periodo)} sobre aprovadas e rejeitadas`), kpi('ok', 'verde', 'Recuperadas depois', rec.pct_recuperadas != null ? pct(rec.pct_recuperadas) : 'sem dado', 'mesma AIH aprovada em competência posterior'),
      num(rec.perda_liquida_estimada_rs) ? kpi('moeda', 'amar', 'Perda estimada', brl(rec.perda_liquida_estimada_rs), 'ESTIMATIVA: AIH não recuperadas × média por AIH') : null));
    const cod = arr(rec.por_codigo_erro);
    if (cod.length) {
      const l = el('div', {class: 'rd-cods'});
      cod.forEach(c => {
        const tot = c.rejeitadas || 0, r = c.recuperadas || 0, barra = el('div', {class: 'rd-duplo', role: 'img', 'aria-label': `${c.codigo_erro}: ${inteiro(r)} recuperadas e ${inteiro(c.nao_recuperadas)} não recuperadas`}), a = el('span', {class: 'rd-st-ok'}), b = el('span', {class: 'rd-st-no'});
        a.style.flexGrow = String(r); b.style.flexGrow = String(Math.max(tot - r, 0)); barra.append(a, b);
        l.append(el('div', {class: 'rd-cod'}, el('div', {class: 'rd-cod-t'}, el('strong', null, c.codigo_erro), el('span', {class: 'rd-peq'}, `${inteiro(tot)} rejeitadas · ${pct(c.pct_recuperadas)} recuperadas`)), barra, el('div', {class: 'rd-peq'}, motivo(c.motivo_provavel))));
      });
      sr.append(el('p', {class: 'rd-leg-linha2'}, el('span', {class: 'rd-amostra rd-a-ok'}), ' recuperadas ', el('span', {class: 'rd-amostra rd-a-no'}), ' não recuperadas'), l);
    }
    sr.append(el('p', {class: 'rd-peq'}, rj.obs || ''));
  }
  w.append(sr);
  const hb = i.checklist_habilitacao || {}, sh = cartao('Habilitações (CNES)', null);
  if (arr(hb.itens).length) {
    sh.append(pilha(hb.resumo, hb.total), el('div', {class: 'rd-lista'}, hb.itens.map(x => el('div', {class: 'rd-item'}, el('div', {class: 'rd-item-t'}, el('strong', null, `${x.codigo} ${x.descricao || ''}`), el('span', {class: 'rd-chip ' + (STATUS[x.status] || 'rd-st-av')}, x.status)),
      el('div', {class: 'rd-peq'}, 'Portaria: ', x.portaria || pend('portaria'), ` · ${x.data_portaria || ''} · vigência ${x.vigencia_inicio || ''} a ${x.vigencia_fim || ''}`), el('div', {class: 'rd-peq'}, x.motivo || '')))));
  } else sh.append(aviso(hb.situacao || 'A confirmar: sem habilitação na base.'));
  w.append(sh);
  const sc = cartao('Críticas', null);
  sc.append(arr(i.criticas).length ? el('div', {class: 'rd-lista'}, i.criticas.map(c => el('div', {class: 'rd-item'}, el('div', {class: 'rd-item-t'}, el('strong', null, c.codigo), chipSev(c.severidade), el('span', {class: 'rd-chip rd-st-av'}, c.status || '')), el('div', null, c.descricao), el('div', {class: 'rd-peq'}, 'Ação recomendada: ', c.acao_recomendada || pend('ação'))))) : el('p', null, 'Nenhuma crítica aberta.'));
  w.append(sc);
  const pl = i.plano_avanco || {}, sp = cartao('Plano de avanço do faturamento', null);
  if (arr(pl.itens).length) {
    sp.append(el('div', {class: 'rd-lista'}, pl.itens.map(x => el('div', {class: 'rd-item'}, el('div', {class: 'rd-item-t'}, el('strong', null, x.acao), chipSev(x.prioridade), el('span', {class: 'rd-chip rd-st-av'}, x.status)),
      el('div', {class: 'rd-peq'}, `Crítica: ${x.critica_vinculada} · Prazo: ${x.prazo || ''} · Responsável: ${x.responsavel || ''}`),
      el('div', {class: 'rd-peq'}, 'Perda: ', num(x.perda_por_rejeicao_rs) ? brl(x.perda_por_rejeicao_rs) + ' (estimativa)' : 'sem dado', ' · Ganho estimado: ', num(x.ganho_estimado_rs) ? brl(x.ganho_estimado_rs) : pend('ganho, lançado pelo gestor'))))));
    if (pl.pendencia_ganho) sp.append(el('p', {class: 'rd-peq'}, pl.pendencia_ganho));
  } else sp.append(el('p', null, 'Sem ações no plano.'));
  w.append(sp);
  return w;
}

// ---------- Gestão hospitalar: demais seções do dossiê (produção, CNES, financeiro, recursos, território, pendências) ----------
const ehPend = v => typeof v === 'string' && v.startsWith('[PREENCHER');
const rotulo = k => { const t = String(k).replace(/_/g, ' ').trim(); return t.charAt(0).toUpperCase() + t.slice(1); };
const PLANO = /(^|_)(ano|exercicio|se|bimestre|competencia|cod|cnes|codigo|tipo|classe|procedimento|cbo|servico|classificacao|mes_processamento|valores)$/;
const META = ['fonte', 'status_fonte', 'competencia', 'exercicio', 'bimestre', 'periodo', 'ano', 'ano_da_proposta', 'se', 'meses', 'coletado_em', 'convertido_em', 'gerado_em', 'extracao_investsus', 'defasagem_dias'];
const NOTAS = ['obs', 'situacao', 'regra'];
const g = (o, ...c) => c.reduce((a, k) => (a && typeof a === 'object' ? a[k] : undefined), o);

function fmtVal(k, v) {
  if (v == null || v === '') return 'sem dado';
  if (ehPend(v)) return el('span', {class: 'pendente'}, v);
  if (typeof v === 'boolean') return v ? 'sim' : 'não';
  if (typeof v === 'number') {
    const c = String(k).toLowerCase();
    if (PLANO.test(c)) return String(v);
    if (/(_rs$|^valor|valor_|^val_|^sh$|^sp$|^sh_|^sp_)/.test(c)) return brl(v);
    if (/pct|percent/.test(c)) return pct(v);
    return Number.isInteger(v) ? inteiro(v) : decimal(v, 2);
  }
  return String(v);
}
const celula = (c, v) => v == null || v === '' ? '' : typeof v === 'object' ? (Array.isArray(v) ? `${inteiro(v.length)} item(ns)` : Object.entries(v).map(([a, b]) => `${rotulo(a)}: ${b && typeof b === 'object' ? '...' : b}`).join('; ')) : fmtVal(c, v);

function meta(o) {
  const w = el('div'), selos = [];
  META.forEach(k => { const v = o[k]; if (v == null || v === '' || typeof v === 'object') return; selos.push(el('span', {class: 'rd-selo' + (k === 'defasagem_dias' && v > 30 ? ' rd-selo-av' : '')}, el('b', null, rotulo(k) + ': '), k === 'defasagem_dias' ? `${v} dia(s)` : ehPend(v) ? v : String(v))); });
  if (selos.length) w.append(el('div', {class: 'rd-selos'}, selos));
  NOTAS.forEach(k => { if (typeof o[k] === 'string' && o[k]) w.append(k === 'situacao' ? aviso(o[k]) : el('p', {class: 'rd-peq'}, o[k])); });
  return w;
}

function lista(a, k) {
  if (!a.length) return el('span', {class: 'rd-peq'}, 'sem registro');
  if (a.every(x => x && typeof x === 'object' && !Array.isArray(x))) {
    const cols = [...new Set(a.flatMap(x => Object.keys(x)))].slice(0, 12), N = 60, sub = a.slice(0, N);
    const t = tabela(cols.map(rotulo), sub.map(x => cols.map(c => celula(c, x[c]))), cols.map((c, i) => i).filter(i => sub.some(x => typeof x[cols[i]] === 'number' && !PLANO.test(cols[i]))));
    return el('div', null, t, a.length > N ? el('p', {class: 'rd-peq'}, `Mostrando ${N} de ${inteiro(a.length)} linhas.`) : null);
  }
  return el('div', {class: 'rd-fichas'}, a.slice(0, 80).map(x => el('span', {class: 'rd-ficha'}, x && typeof x === 'object' ? JSON.stringify(x) : fmtVal(k, x))), a.length > 80 ? el('span', {class: 'rd-peq'}, `+ ${inteiro(a.length - 80)}`) : null);
}

function bloco(v, k = '', d = 0) {
  if (v == null || v === '') return el('span', {class: 'rd-peq'}, 'sem dado');
  if (typeof v !== 'object') return fmtVal(k, v);
  if (Array.isArray(v)) return lista(v, k);
  const w = el('div', {class: 'rd-bloco'}), simples = [], filhos = [];
  w.append(meta(v));
  Object.entries(v).forEach(([c, x]) => { if (META.includes(c) || NOTAS.includes(c)) return; (x && typeof x === 'object' ? filhos : simples).push([c, x]); });
  if (simples.length) w.append(el('dl', {class: 'rd-kv'}, simples.map(([c, x]) => el('div', null, el('dt', null, rotulo(c)), el('dd', null, fmtVal(c, x))))));
  filhos.forEach(([c, x]) => w.append(el('div', {class: 'rd-sub-b'}, el('h5', null, rotulo(c)), d >= 3 ? el('pre', {class: 'rd-peq'}, JSON.stringify(x).slice(0, 400)) : bloco(x, c, d + 1))));
  return w;
}

const grupo = (titulo, sub, ...filhos) => el('section', {class: 'rd-grupo'}, el('h3', null, titulo), sub ? el('p', {class: 'rd-sub'}, sub) : null, ...filhos);
const semDado = (x, txt) => ehPend(x) ? aviso(x) : (x && typeof x === 'object' && !Array.isArray(x) ? bloco(x) : aviso(txt));
const somar = (a, c) => arr(a).reduce((s, x) => s + (num(x[c]) ? x[c] : 0), 0);
const nomeItem = x => x.descricao || [x.tipo, x.codigo, x.servico, x.classificacao, x.tipo_equipe, x.cbo, x.tipo_unidade, x.procedimento, x.cnes && 'CNES ' + x.cnes].filter(v => v != null && v !== '').join(' / ') || 'item';

function rankSimples(linhas, fnome, fval, fmt, rot, max = 12) {
  const l = linhas.slice(0, max), vals = l.map(fval), mx = Math.max(...vals.filter(num), 0) || 1, w = el('div', {class: 'rd-rank'});
  l.forEach((x, k) => {
    const v = vals[k], barra = el('span', {class: 'rd-fill'});
    requestAnimationFrame(() => { barra.style.width = (num(v) ? Math.max(v / mx * 100, v > 0 ? 1.5 : 0) : 0) + '%'; });
    w.append(el('div', {class: 'rd-rank-l'}, el('div', {class: 'rd-rank-n'}, el('strong', null, fnome(x))), el('div', {class: 'rd-trilho', role: 'img', 'aria-label': `${fnome(x)}, ${rot}: ${num(v) ? fmt(v) : 'sem dado'}`}, barra), el('div', {class: 'rd-rank-v'}, num(v) ? fmt(v) : 'sem dado')));
  });
  return w;
}

function cartaoLista(titulo, o, chaveLista, fval, fmt, rot, sub) {
  const l = o && arr(o[chaveLista]);
  if (!l || !l.length) return cartao(titulo, null, semDado(o, 'A confirmar: sem registro na base.'));
  return cartao(titulo, sub || null, meta(o), rankSimples(l, nomeItem, fval, fmt, rot), detalhesTabela('Ver tabela completa', lista(l, chaveLista)));
}

// ---- Produção
function cartaoSih(x) {
  const m = arr(x && x.aih_por_mes);
  if (!m.length) return grupo('SIH/SUS: internações aprovadas', null, semDado(x, 'A confirmar: sem AIH do município na base.'));
  const aih = somar(m, 'aih'), valor = somar(m, 'valor_total'), ob = somar(m, 'obitos'), dias = somar(m, 'dias_permanencia');
  const comp = [['SH (serviço hospitalar)', somar(m, 'sh')], ['SP (serviço profissional)', somar(m, 'sp')], ['SH complemento federal', somar(m, 'sh_fed')], ['SP complemento federal', somar(m, 'sp_fed')]].filter(c => c[1] > 0);
  const w = el('div');
  w.append(meta(x), el('div', {class: 'rd-kpis'},
    kpi('doc', 'azul', 'AIH aprovadas', inteiro(aih), `${inteiro(m.length)} mês(es)`), kpi('moeda', 'verde', 'Valor total', brlc(valor), brl(valor)),
    kpi('grafico', 'azul', 'Média por AIH', aih ? brl(valor / aih) : 'sem dado', 'valor total ÷ AIH'), kpi('agenda', 'azul', 'Permanência média', aih ? decimal(dias / aih, 1) + ' dias' : 'sem dado', 'dias ÷ AIH'),
    kpi('pessoas', 'verm', 'Óbitos hospitalares', pct(aih ? ob / aih * 100 : null), `${inteiro(ob)} óbito(s) ÷ AIH`)));
  w.append(el('div', {class: 'rd-duas'}, cartao('AIH por mês', null, barrasMes(m, 'aih', 'AIH aprovadas por mês no município')), cartao('Valor por mês', null, barrasMes(m, 'valor_total', 'Valor aprovado por mês no município'))));
  w.append(el('div', {class: 'rd-duas'},
    cartao('Composição do valor', 'SH + SP + complemento federal (a partir de 03/2026).', comp.length ? rankSimples(comp, c => c[0], c => c[1], brlc, 'valor') : aviso('A confirmar: sem valor.')),
    cartaoLista('Procedimentos de maior valor', {principais_procedimentos: x.principais_procedimentos}, 'principais_procedimentos', p => p.valor_total, brlc, 'valor total', 'Código SIGTAP do procedimento realizado.')));
  w.append(detalhesTabela('Ver produção mensal completa', lista(m, 'aih_por_mes')));
  if (arr(x.servicos_profissionais_por_mes).length) w.append(cartao('Serviços profissionais por mês (SP)', null, lista(x.servicos_profissionais_por_mes, 'sp')));
  if (arr(x.cnes_com_aih).length) w.append(cartao('CNES com AIH no município', 'Conferir com o CNES antes de usar.', lista(x.cnes_com_aih, 'cnes')));
  return grupo('SIH/SUS: internações aprovadas', 'Produção hospitalar aprovada, por mês de processamento.', w);
}

function cartaoSia(x) {
  const m = arr(x && x.por_mes);
  if (!m.length) return grupo('SIA/SUS: produção ambulatorial aprovada', null, semDado(x, 'A confirmar: sem produção ambulatorial do município na base.'));
  const w = el('div');
  w.append(meta(x), el('div', {class: 'rd-kpis'}, kpi('doc', 'azul', 'Quantidade aprovada', inteiro(somar(m, 'quantidade_aprovada')), `${inteiro(m.length)} mês(es)`), kpi('moeda', 'verde', 'Valor aprovado', brlc(somar(m, 'valor_aprovado')), brl(somar(m, 'valor_aprovado')))));
  w.append(el('div', {class: 'rd-duas'}, cartao('Valor aprovado por mês', null, barrasMes(m, 'valor_aprovado', 'Valor ambulatorial aprovado por mês')), cartao('Quantidade por mês', null, barrasMes(m, 'quantidade_aprovada', 'Quantidade ambulatorial aprovada por mês'))));
  w.append(el('div', {class: 'rd-duas'}, cartaoLista('Procedimentos de maior valor', x, 'principais_procedimentos', p => p.valor_aprovado, brlc, 'valor aprovado'), cartaoLista('Estabelecimentos de maior valor', x, 'principais_estabelecimentos', p => p.valor_aprovado, brlc, 'valor aprovado')));
  w.append(detalhesTabela('Ver produção mensal completa', lista(m, 'por_mes')));
  return grupo('SIA/SUS: produção ambulatorial aprovada', 'Somente produção aprovada.', w);
}

function cartaoCiha(x) {
  const m = arr(x && x.por_mes);
  if (!m.length) return grupo('CIHA: internação e atendimento fora do SIH', null, semDado(x, 'A confirmar: sem registro de CIHA do município.'));
  const w = el('div');
  w.append(meta(x), el('div', {class: 'rd-kpis'}, kpi('doc', 'azul', 'Registros', inteiro(somar(m, 'registros')), `${inteiro(m.length)} mês(es)`), kpi('grafico', 'azul', 'Procedimentos', inteiro(somar(m, 'quantidade_procedimentos'))),
    kpi('agenda', 'azul', 'Dias de permanência', inteiro(somar(m, 'dias_permanencia'))), kpi('pessoas', 'verm', 'Óbitos', inteiro(somar(m, 'obitos')))));
  w.append(el('div', {class: 'rd-duas'}, cartao('Registros por mês', null, barrasMes(m, 'registros', 'Registros de CIHA por mês')), cartaoLista('Procedimentos mais frequentes', x, 'principais_procedimentos', p => p.quantidade, inteiro, 'quantidade')));
  w.append(detalhesTabela('Ver mês a mês', lista(m, 'por_mes')));
  if (arr(x.cnes_com_ciha).length) w.append(cartao('CNES com CIHA', null, lista(x.cnes_com_ciha, 'cnes')));
  return grupo('CIHA: internação e atendimento fora do SIH', 'Sem valor financeiro. Não somar com AIH sem conferir duplicidade por CNES.', w);
}

const secProducao = s => s && typeof s === 'object' && !ehPend(s) ? el('div', null, cartaoSih(s.sih), cartaoSia(s.sia_aprovado), cartaoCiha(s.ciha)) : semDado(s, 'A confirmar: sem produção.');

// ---- Rede CNES
function secCnes(s) {
  if (!s || typeof s !== 'object' || ehPend(s)) return semDado(s, 'A confirmar: sem seção CNES.');
  const w = el('div'), kp = [];
  const lt = g(s, 'leitos_por_tipo', 'totais'), eq = g(s, 'equipamentos_cadastro', 'totais'), pf = s.profissionais_cadastro, es = s.estabelecimentos;
  if (lt && num(lt.existentes)) kp.push(kpi('hospital', 'azul', 'Leitos existentes', inteiro(lt.existentes), `${inteiro(lt.sus)} SUS · ${inteiro(lt.nao_sus)} não SUS`));
  if (es && num(es.total)) kp.push(kpi('hospital', 'azul', 'Estabelecimentos', inteiro(es.total), `${inteiro(arr(es.com_leito_cadastrado).length)} com leito cadastrado`));
  if (eq && num(eq.existentes)) kp.push(kpi('grafico', 'verde', 'Equipamentos', inteiro(eq.existentes), `${pct(eq.existentes ? eq.em_uso / eq.existentes * 100 : null)} em uso`));
  if (pf && num(pf.vinculos)) kp.push(kpi('pessoas', 'azul', 'Vínculos profissionais', inteiro(pf.vinculos), 'contagem de vínculos, não de pessoas'));
  if (g(s, 'equipes_cadastro', 'total_equipes') != null) kp.push(kpi('pessoas', 'azul', 'Equipes', inteiro(s.equipes_cadastro.total_equipes)));
  if (g(s, 'habilitacoes', 'total') != null) kp.push(kpi('ok', 'verde', 'Habilitações', inteiro(s.habilitacoes.total), 'cadastro CNES'));
  if (g(s, 'servicos_especializados', 'total_servicos_classificacoes') != null) kp.push(kpi('doc', 'azul', 'Serviços especializados', inteiro(s.servicos_especializados.total_servicos_classificacoes)));
  if (kp.length) w.append(el('div', {class: 'rd-kpis'}, kp));
  w.append(el('div', {class: 'rd-duas'}, cartaoLista('Leitos por tipo', s.leitos_por_tipo, 'itens', x => x.existentes, inteiro, 'leitos existentes'), cartaoLista('Equipamentos', s.equipamentos_cadastro, 'itens', x => x.existentes, inteiro, 'existentes')));
  w.append(el('div', {class: 'rd-duas'}, cartaoLista('Equipes', s.equipes_cadastro, 'itens', x => x.equipes, inteiro, 'equipes'), cartaoLista('Serviços especializados', s.servicos_especializados, 'itens', x => x.estabelecimentos, inteiro, 'estabelecimentos')));
  if (pf && arr(pf.principais_cbo).length) w.append(el('div', {class: 'rd-duas'}, cartaoLista('Profissionais por CBO', pf, 'principais_cbo', x => x.vinculos, inteiro, 'vínculos', 'Sem nome, CPF, CNS ou registro.'), cartaoLista('Vínculos por estabelecimento', pf, 'principais_estabelecimentos', x => x.vinculos, inteiro, 'vínculos')));
  else w.append(cartao('Profissionais', null, semDado(pf, 'A confirmar: sem profissionais na base.')));
  w.append(cartaoLista('Estabelecimentos por tipo de unidade', es, 'por_tipo_unidade', x => x.estabelecimentos, inteiro, 'estabelecimentos'));
  if (es && arr(es.com_leito_cadastrado).length) w.append(cartao('Estabelecimentos com leito cadastrado', 'Natureza, gestão, urgência, centro cirúrgico, acreditação e instalações, em código do CNES.', detalhesTabela('Abrir tabela', lista(es.com_leito_cadastrado, 'com_leito_cadastrado'))));
  [['habilitacoes', 'Habilitações'], ['incentivos', 'Incentivos'], ['regras_contratuais', 'Regras contratuais'], ['entidade_filantropica', 'Entidade filantrópica']].forEach(([k, t]) => w.append(cartao(t, 'Portaria, data e vigência por CNES.', ...(s[k] && arr(s[k].itens).length ? [meta(s[k]), detalhesTabela('Abrir tabela', lista(s[k].itens, k))] : [semDado(s[k], 'A confirmar: sem registro na base.')]))));
  [['leitos', 'Resumo de leitos (Sala de Gestão)'], ['equipes', 'Resumo de equipes (Sala de Gestão)'], ['equipamentos', 'Resumo de equipamentos (Sala de Gestão)'], ['profissionais', 'Resumo de profissionais (Sala de Gestão)'], ['rede', 'Rede de serviços (Sala de Gestão)'], ['tabelas_codigos', 'Tabelas oficiais de descrição de códigos']].forEach(([k, t]) => { if (k in s) w.append(cartao(t, null, detalhesTabela('Abrir', bloco(s[k])))); });
  return w;
}

// ---- Financeiro, recursos, território
function secFinanceiro(s) {
  if (!s || typeof s !== 'object' || ehPend(s)) return semDado(s, 'A confirmar: sem seção financeira.');
  const w = el('div');
  [['despesa_saude', 'Despesa em saúde'], ['receita', 'Receita'], ['pessoal', 'Despesa com pessoal'], ['siops', 'SIOPS: aplicação em saúde']].forEach(([k, t]) => { if (k in s) w.append(cartao(t, null, bloco(s[k]))); });
  return w;
}

function secRecursos(s) {
  if (!s || typeof s !== 'object' || ehPend(s)) return semDado(s, 'A confirmar: sem seção de recursos.');
  const w = el('div'), e = s.emendas;
  if (e && typeof e === 'object' && num(e.proposto_rs)) {
    w.append(cartao('Emendas parlamentares (Radar de Recursos)', 'Execução financeira, não meta. Ano da proposta indicado abaixo.', meta(e), el('div', {class: 'rd-kpis'},
      kpi('doc', 'azul', 'Propostas', inteiro(e.propostas)), kpi('moeda', 'azul', 'Proposto', brlc(e.proposto_rs), brl(e.proposto_rs)), kpi('moeda', 'amar', 'Empenhado', brlc(e.empenhado_rs), `${pct(e.pct_empenhado_sobre_proposto)} do proposto`),
      kpi('ok', 'verde', 'Pago', brlc(e.pago_rs), `${pct(e.pct_pago_sobre_empenhado)} do empenhado`), kpi('alerta', 'verm', 'Saldo a pagar', brlc(e.saldo_a_pagar_rs), brl(e.saldo_a_pagar_rs))),
      rankSimples([['Proposto', e.proposto_rs], ['Empenhado', e.empenhado_rs], ['Pago', e.pago_rs]], x => x[0], x => x[1], brlc, 'valor')));
  } else if (e) w.append(cartao('Emendas parlamentares (Radar de Recursos)', null, semDado(e, 'A confirmar: sem emendas.')));
  [['fns_investsus', 'Repasses FNS e InvestSUS'], ['transferencias_uniao_saude', 'Transferências da União para a saúde']].forEach(([k, t]) => { if (k in s) w.append(cartao(t, null, bloco(s[k]))); });
  return w;
}

function secTerritorio(s) {
  if (!s || typeof s !== 'object' || ehPend(s)) return semDado(s, 'A confirmar: sem seção de território.');
  const w = el('div');
  [['dengue', 'Dengue (Sala de Gestão)'], ['cobertura_planos_ans', 'Cobertura de planos de saúde (ANS)']].forEach(([k, t]) => { if (k in s) w.append(cartao(t, null, bloco(s[k]))); });
  return w;
}

// ---- Pendências e validação
function secResumo(r) {
  const p = arr(r && r.pendencias), w = el('div');
  const pop = g(r, 'municipio', 'populacao');
  w.append(el('div', {class: 'rd-kpis'}, kpi('alerta', p.length ? 'amar' : 'verde', 'Pendências do robô', inteiro(p.length), 'campos que ainda dependem de dado oficial'), kpi('pessoas', 'azul', 'População', pop && num(pop.valor) ? inteiro(pop.valor) : 'sem dado', pop && pop.fonte ? String(pop.fonte) : 'denominador IBGE')));
  if (!p.length) { w.append(aviso('Nenhuma pendência registrada pelo robô nesta geração.')); return w; }
  const grupos = {};
  p.forEach(t => { const [c, ...resto] = String(t).split(': '); const topo = c.split(/[.[]/)[0] || 'outros'; (grupos[topo] = grupos[topo] || []).push([c, resto.join(': ')]); });
  Object.entries(grupos).sort((a, b) => b[1].length - a[1].length).forEach(([k, l]) => w.append(cartao(`${({cnes: 'Rede CNES', territorio_saude: 'Território', producao: 'Produção', recursos: 'Recursos', financeiro: 'Financeiro', populacao: 'População'})[k] || rotulo(k)}: ${inteiro(l.length)} pendência(s)`, null, tabela(['Campo', 'O que falta'], l.map(([c, t]) => [c, ehPend(t) ? el('span', {class: 'pendente'}, t) : t])))));
  return w;
}

// ---- painel do município com abas e carga sob demanda
const SECOES = [['producao', 'Produção SIH, SIA e CIHA', secProducao, 'secao'], ['cnes', 'Rede CNES', secCnes, 'secao'], ['financeiro', 'Financeiro', secFinanceiro, 'secao'], ['recursos', 'Recursos e emendas', secRecursos, 'secao'], ['territorio', 'Território', secTerritorio, 'secao'], ['resumo', 'Pendências', secResumo, null]];

function municipioPainel(m, d) {
  const w = el('div'), h = d.hospitais;
  w.append(el('h3', {class: 'rd-tit-mun'}, d.municipio && d.municipio.nome ? d.municipio.nome : m.nome), el('p', {class: 'rd-fonte-peq'}, `Gerado em: ${d.gerado_em || '[PREENCHER: data]'} · ${h && h.fonte ? h.fonte : ''}`));
  const painel = [['Hospitais e rejeição', municipio(d)]];
  SECOES.forEach(([k, rot, fn, campo]) => {
    const alvo = el('div', {class: 'rd-lazy'});
    let feito = false;
    alvo.carregar = async () => {
      if (feito) return; feito = true; alvo.append(el('p', {class: 'rd-carregando'}, 'Carregando...'));
      const x = await carregar(D + `rede_${m.cod}_${k}.json`);
      limpar(alvo);
      alvo.append(x ? (campo ? fn(x[campo]) : fn(x)) : aviso('A confirmar: seção ainda não publicada. Rode a coleta do robô e a publicação.'));
    };
    painel.push([rot, alvo]);
  });
  w.append(abas(painel));
  return w;
}

// ---------- Fontes e conexões: status calculado pelo robô (rede_fontes.json) ----------
const ST = {Ativa: ['rd-st-ativa', '✔'], 'Em teste': ['rd-st-teste', '◌'], Manual: ['rd-st-manual', '✎'], Bloqueada: ['rd-st-bloq', '■'], 'A confirmar': ['rd-st-conf', '?'], Descartada: ['rd-st-desc', '✕']};
const chipSt = st => { const [c, s] = ST[st] || ['rd-st-conf', '?']; return el('span', {class: 'rd-chip ' + c}, `${s} ${st}`); };
const dataBr = iso => { const t = new Date(iso); return iso && !isNaN(t) ? t.toLocaleDateString('pt-BR') : 'sem teste'; };

export function painelFontes() {
  const alvo = el('div', {class: 'rd-lazy'});
  let feito = false;
  alvo.carregar = async () => {
    if (feito) return; feito = true; alvo.append(el('p', {class: 'rd-carregando'}, 'Carregando...'));
    const d = await carregar(D + 'rede_fontes.json');
    limpar(alvo);
    if (!d || !arr(d.fontes).length) { alvo.append(aviso('A confirmar: o robô ainda não gerou o status das fontes. Rode "partelli-coleta fontes" no Serverrobo e publique.')); return; }
    const res = d.resumo || {}, tot = arr(d.fontes).length, tom = {Ativa: 'verde', 'A confirmar': 'amar', Manual: 'azul', Bloqueada: 'verm', Descartada: 'azul', 'Em teste': 'azul'};
    const ic = {Ativa: 'ok', 'A confirmar': 'agenda', Manual: 'doc', Bloqueada: 'alerta', Descartada: 'doc', 'Em teste': 'agenda'};
    alvo.append(el('p', {class: 'rd-fonte-peq'}, `Gerado em ${dataBr(d.gerado_em)}. ${d.regra || ''}`),
      el('div', {class: 'rd-kpis'}, Object.keys(ST).filter(k => res[k]).map(k => kpi(ic[k], tom[k], k, inteiro(res[k]), `${pct(res[k] / tot * 100)} das ${inteiro(tot)} fontes`))));
    const sel = el('select', {'aria-label': 'Filtrar por status', class: 'rd-sel-ind'}, [el('option', {value: ''}, 'Todos os status'), ...Object.keys(ST).filter(k => res[k]).map(k => el('option', {value: k}, k))]);
    const corpo = el('div'), pintar = () => {
      limpar(corpo);
      const l = arr(d.fontes).filter(x => !sel.value || x.status === sel.value);
      corpo.append(tabela(['Sistema', 'Acesso', 'Status', 'Último teste', 'Resultado e limite'], l.map(x => [el('div', null, el('strong', null, x.sistema), x.uso ? el('div', {class: 'rd-peq'}, x.uso) : null), x.acesso || '', chipSt(x.status), el('span', {class: 'rd-nw'}, dataBr(x.ultimo_teste)), el('div', null, x.resultado || '', x.limite ? el('div', {class: 'rd-peq'}, x.limite) : null)])));
    };
    sel.addEventListener('change', pintar); pintar();
    alvo.append(cartao('Todas as fontes oficiais', 'O status é calculado pelo robô a cada rodada. Ativa só com coleta registrada dentro do prazo. Bloqueio declarado não é contornado.', el('label', {class: 'rd-rot-sel'}, 'Status ', sel), corpo));
  };
  return alvo;
}
