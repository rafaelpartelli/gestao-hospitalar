// Descricao de codigos do CNES a partir de tabelas_cnes.json (TAB_CNES.zip, FTP DATASUS, pasta Auxiliar). Sem dado pessoal.
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
