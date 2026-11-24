const nf = new Intl.NumberFormat('pt-BR');
export const inteiro = v => (v == null || isNaN(v)) ? 'sem dado' : nf.format(Math.round(v));
export const decimal = (v, d = 1) => (v == null || isNaN(v)) ? 'sem dado' : v.toLocaleString('pt-BR', {minimumFractionDigits: d, maximumFractionDigits: d});
export function el(tag, attrs, ...filhos) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === 'class') e.className = v;
    else if (k === 'texto') e.textContent = v;
    else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v === true ? '' : v);
  }
  for (const f of filhos.flat()) if (f != null) e.append(f.nodeType ? f : document.createTextNode(String(f)));
  return e;
}
export const limpar = no => { while (no.firstChild) no.removeChild(no.firstChild); return no; };
const cache = new Map();
export function carregar(caminho) {
  if (!cache.has(caminho)) cache.set(caminho, fetch(caminho, {cache: 'no-cache'}).then(r => r.ok ? r.json() : null).catch(() => null));
  return cache.get(caminho);
}
export function tabela(colunas, linhas, numericas = []) {
  const t = el('table', null,
    el('thead', null, el('tr', null, colunas.map((c, i) => el('th', {scope: 'col', class: numericas.includes(i) ? 'n' : ''}, c)))),
    el('tbody', null, linhas.map(l => el('tr', null, l.map((c, i) => el('td', {class: numericas.includes(i) ? 'n' : ''}, c))))));
  return el('div', {class: 'tabela-rolavel'}, t);
}

// ---- Descricao de codigos do CNES (antes em cnes_desc.js; unido aqui para a publicacao na Oracle instalar so os arquivos conhecidos)
const T = tab => (tab && tab.tabelas) || {};
const pad = (v, n) => String(v == null ? '' : v).trim().padStart(n, '0');
export const semPrefixo = t => String(t || '').replace(/^\d+\s*-\s*/, '').trim();

export function descServico(tab, servico, classificacao) {
  return T(tab).servico_classificacao_n?.[pad(servico, 3) + pad(classificacao, 3)] || '';
}
export function descLeito(tab, tipo, cod) {
  const a = semPrefixo(T(tab).tipo_leito?.[String(tipo || '').trim()]), b = T(tab).especialidade_leito?.[pad(cod, 2)] || '';
  return [a, b].filter(Boolean).join(' · ');
}
export const descHabilitacao = (tab, sg) => T(tab).habilitacao?.[String(sg || '').trim()] || '';
export const descIncentivo = (tab, sg) => semPrefixo(T(tab).incentivo?.[String(sg || '').trim()]);
export function descEquipamento(tab, tipo, cod) {
  const k = pad(tipo, 2) + pad(cod, 2);
  return semPrefixo(T(tab).equipamento?.[k] || T(tab).tipo_equipamento?.[k]);
}

const cacheInst = new WeakMap();
const cap = s => s.charAt(0).toUpperCase() + s.slice(1).toLowerCase();
export function mapaInstalacoes(tab) {
  if (!tab) return {};
  if (cacheInst.has(tab)) return cacheInst.get(tab);
  const out = {};
  let grupo = '';
  for (const ln of T(tab).instalacoes_def || []) {
    const h = ln.match(/^I\*\s*(.+?)\s*\*\s*\.?\s*,\s*\w+/);
    if (h) { grupo = cap(h[1].replace(/\s+/g, ' ')); continue; }
    const i = ln.match(/^IQt\.\s*(.+?)\s*,\s*QTINST(\d{2})\s*$/);
    if (i) out[i[2]] = (grupo ? grupo + ': ' : '') + i[1].replace(/\s+/g, ' ').trim();
  }
  cacheInst.set(tab, out);
  return out;
}
export const descInstalacao = (tab, cod) => mapaInstalacoes(tab)[pad(cod, 2)] || '';

// 'AAAAMM' vira 'MM/AAAA'; 999999 e a convencao do CNES para sem data final.
export function fmtCompCnes(v) {
  const s = String(v || '').trim();
  if (s === '999999') return 'sem data final';
  return /^\d{6}$/.test(s) ? s.slice(4) + '/' + s.slice(0, 4) : s;
}
