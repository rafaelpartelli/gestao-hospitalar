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
