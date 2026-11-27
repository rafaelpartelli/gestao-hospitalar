/* Preenchimento automatico das etapas 1, 3, 4, 5, 6, 7 e 8 a partir dos JSON do robo (/dados/rede_<cod>_*.json).
   Regras: so dado oficial colhido pelo robo, com fonte e data; campo sem dado fica vazio (aparece como [PREENCHER]); nada de nome de pessoa.
   Lancamentos automaticos levam _auto e o codigo do municipio; a cada rodada os automaticos do municipio sao trocados, os manuais ficam. */
(function () {
'use strict';
const D = new URL('dados/', location.href).href;
const ROBO = 'Robô Partelli (automático)';
const get = async n => { try { const r = await fetch(D + n, { cache: 'no-cache' }); return r.ok ? await r.json() : null; } catch (e) { return null; } };
const arr = x => Array.isArray(x) ? x : [];
const num = v => (typeof v === 'number' && isFinite(v)) ? v : '';
const dia = g => { const m = /^(\d{4}-\d{2}-\d{2})/.exec(String(g || '')); return m ? m[1] : ''; };
const comp6 = c => /^\d{6}$/.test(String(c || '')) ? String(c).slice(4) + '/' + String(c).slice(0, 4) : (/^\d{2}\/\d{4}$/.test(String(c || '')) ? c : '');
const TIPO = { Hospital: ['05', '07', '62'], UBS: ['01', '02'], UPA: ['73'], CAPS: ['70'], 'Policlínica ou ambulatório': ['04', '36'], 'Vigilância em saúde': ['50', '64', '68', '76', '81'] };
const tipoUn = t => { const c = String(t || '').padStart(2, '0'); for (const k in TIPO) if (TIPO[k].indexOf(c) >= 0) return k; return 'Outro'; };
const ehNome = s => typeof s === 'string' && s && !/\d{11,}/.test(s);

function semana(se, ano) { // SE aproximada: domingo da semana epidemiologica, em MM/AAAA
  const d = new Date(Date.UTC(ano, 0, 1 + (se - 1) * 7)); return ('0' + (d.getUTCMonth() + 1)).slice(-2) + '/' + d.getUTCFullYear();
}

async function preencher(api) {
  const S = api.S(), m = S.mun;
  if (!m || !/^\d{7}$/.test(String(m.id))) { return { msg: '' }; }
  const cod = String(m.id);
  const [estab, nomes, cnes, rec, terr, prod] = await Promise.all([get(`rede_${cod}_estab.json`), get('rede_nomes_cnes.json'), get(`rede_${cod}_cnes.json`), get(`rede_${cod}_recursos.json`), get(`rede_${cod}_territorio.json`), get(`rede_${cod}_producao.json`)]);
  if (!estab && !cnes && !rec && !terr && !prod) return { msg: 'Este município ainda não está na lista do robô (hoje: municípios piloto do ES). Preencha as etapas manualmente, com fonte e data.' };
  const nome = (nomes && nomes.nomes) || {};
  const coleta = dia((estab || cnes || rec || prod || {}).gerado_em) || api.hoje();
  const ctx = { fonte: '', coleta: coleta, resp: ROBO };
  const novos = {};
  const add = (k, e) => { (novos[k] = novos[k] || []).push(Object.assign({ _id: 'a' + api.uid(), _auto: cod }, e)); };
  let nUn = 0;

  // etapa 1: unidades (CNES com producao ou profissionais; nome so quando publico)
  const todosEst = arr(estab && estab.secao && estab.secao.estabelecimentos);
  const ests = todosEst.some(e => e.gestao_publica != null) ? todosEst.filter(e => e.gestao_publica === true) : todosEst; // somente gestao publica (CNES), quando o arquivo traz a natureza juridica
  ests.forEach(e => {
    if (!S.unidades.some(u => u.cnes === e.cnes)) { S.unidades.push({ cnes: e.cnes, tipo: tipoUn(e.tipo_unidade), desc: ehNome(nome[e.cnes]) ? String(nome[e.cnes]).slice(0, 80) : '', _auto: cod }); nUn++; }
    else { const u = S.unidades.find(x => x.cnes === e.cnes); if (u._auto && !u.desc && ehNome(nome[e.cnes])) u.desc = String(nome[e.cnes]).slice(0, 80); }
  });

  // etapa 1: IDHM (Atlas, via IBGE Cidades), so se a API confirmar o nome do indicador
  try {
    if (!S.ident.idh) {
      const B = 'https://servicodados.ibge.gov.br/api/v1/pesquisas/37/indicadores/30255';
      const [meta, res] = await Promise.all([fetch(B).then(r => r.ok ? r.json() : null), fetch(B + '/resultados/' + cod).then(r => r.ok ? r.json() : null)]);
      const nomeInd = meta && meta[0] && meta[0].indicador, serie = res && res[0] && res[0].res && res[0].res[0] && res[0].res[0].res, anos = serie ? Object.keys(serie) : [];
      const ano = anos.sort().pop(), v = ano ? Number(String(serie[ano]).replace(',', '.')) : NaN;
      if (/IDHM|Desenvolvimento Humano/i.test(String(nomeInd || '')) && isFinite(v) && v > 0 && v <= 1) { S.ident.idh = String(v); S.ident.idhFonte = 'IDHM ' + ano + ', Atlas do Desenvolvimento Humano (PNUD, Ipea, FJP), via IBGE Cidades'; }
    }
  } catch (e) { /* IDH fica para lançamento manual */ }

  // etapa 3 e 4: por estabelecimento
  ests.forEach(e => {
    arr(e.sih).forEach(x => add('3.hosp', Object.assign({ unidade: e.cnes, comp: x.competencia, env: typeof x.rejeitadas === 'number' ? (Number(x.aih) || 0) + x.rejeitadas : '', apr: num(x.aih), rej: typeof x.rejeitadas === 'number' ? x.rejeitadas : '', np: '', vapr: num(x.valor_total), vrej: '', obs: 'Aprovadas (RD) e rejeitadas (ER) do SIH; enviadas = aprovadas + rejeitadas. Não processadas e valor rejeitado: lançar (o ER não traz R$).' }, ctx, { fonte: 'SIH/SUS (DATASUS)' })));
    arr(e.sia && e.sia.por_mes).forEach(x => add('3.amb', Object.assign({ unidade: e.cnes, comp: x.mes_processamento, qtd: num(x.quantidade_aprovada), val: num(x.valor_aprovado), obs: 'Somente produção aprovada (quantidade aprovada).' }, ctx, { fonte: 'SIA/SUS (DATASUS)' })));
    arr(e.ciha).forEach(x => add('3.ciha', Object.assign({ unidade: e.cnes, comp: x.competencia, qtd: num(x.registros), obs: 'CIHA, sem valor financeiro.' }, ctx, { fonte: 'CIHA (DATASUS)' })));
    const p = e.profissionais;
    if (p) arr(p.principais_cbo).forEach(c => {
      const h = (Number(c.horas_ambulatoriais) || 0) + (Number(c.horas_hospitalares) || 0) + (Number(c.horas_outras) || 0);
      if (/^\d{6}$/.test(String(c.cbo))) add('4.prof', Object.assign({ unidade: e.cnes, comp: comp6(p.competencia), cbo: String(c.cbo), qtd: num(c.vinculos), ch: c.vinculos ? Math.round(h / c.vinculos * 10) / 10 : '', vinculo: '', lotacao: '', obs: 'Vínculos do CNES (não é número de pessoas). Carga horária é a média por vínculo. Vínculo e lotação: lançar.' }, ctx, { fonte: 'CNES' }));
    });
  });

  // etapa 5: emendas (Radar de Recursos)
  const em = rec && rec.secao && rec.secao.emendas;
  if (em && typeof em.proposto_rs === 'number') add('5.em', Object.assign({ ano: String(em.ano_da_proposta || ''), objeto: 'Emendas parlamentares do Radar de Recursos (' + (em.propostas || 0) + ' proposta(s)). Empenhado R$ ' + (em.empenhado_rs || 0).toLocaleString('pt-BR') + ', pago R$ ' + (em.pago_rs || 0).toLocaleString('pt-BR') + '.', valor: em.proposto_rs, status: 'A verificar', prazo: '', link: '', obs: 'Valor proposto no ano. Execução financeira, não meta. Prazos e objeto por emenda: lançar.' }, ctx, { fonte: 'FNS / InvestSUS' }));

  // etapa 6: habilitacoes do CNES, so "Habilitado" com portaria
  const hb = cnes && cnes.secao && cnes.secao.habilitacoes;
  arr(hb && hb.itens).forEach(h => {
    const por = h.portaria ? String(h.portaria) + (h.data_portaria ? ', ' + h.data_portaria : '') : '';
    const vig = h.vigencia_inicio ? (comp6(h.vigencia_inicio) + ' a ' + (String(h.vigencia_fim) === '999999' ? 'sem data final' : comp6(h.vigencia_fim))) : '';
    add('6.prog', Object.assign({ programa: h.descricao || ('Habilitação CNES, código ' + h.codigo), situacao: por ? 'Habilitado' : 'A verificar', portaria: por, vigencia: vig, unidade: h.cnes, obs: 'Cadastro CNES (HB). Conferir a portaria no DOU.' }, ctx, { fonte: 'CNES' }));
  });

  // etapa 7: equipes (CNES EP)
  const eqs = cnes && cnes.secao && cnes.secao.equipes_cadastro;
  arr(eqs && eqs.itens).forEach(t => {
    const d = String(t.descricao || ''), tipo = /fam[ií]lia/i.test(d) ? 'eSF' : /aten[cç][aã]o prim/i.test(d) ? 'eAP' : /bucal/i.test(d) ? 'eSB' : /multi/i.test(d) ? 'eMulti' : 'Outra';
    add('7.eq', Object.assign({ unidade: '', comp: comp6(eqs.competencia), tipo: tipo, neq: num(t.equipes), cbo: '', qtd: '', ch: '', obs: 'Equipes ativas do município (CNES EP), ' + d + '. Unidade, CBO e profissionais: lançar.' }, ctx, { fonte: 'CNES' }));
  });

  // etapa 8: dengue (InfoDengue, via Sala de Gestao)
  const dg = terr && terr.secao && terr.secao.dengue;
  if (dg && Array.isArray(dg.valores) && typeof dg.se === 'number') {
    const ano = Number(String(terr.gerado_em || '').slice(0, 4)) || new Date().getFullYear(), c = semana(dg.se, ano), v = dg.valores;
    if (typeof v[3] === 'number') add('8.vig', Object.assign({ comp: c, ind: 'Dengue, casos (semana epidemiológica ' + dg.se + ')', valor: v[3], un: 'casos', obs: 'InfoDengue. Competência aproximada pela semana epidemiológica.' }, ctx, { fonte: 'InfoDengue' }));
    if (typeof v[4] === 'number') add('8.vig', Object.assign({ comp: c, ind: 'Dengue, incidência (semana epidemiológica ' + dg.se + ')', valor: v[4], un: 'incidência, unidade da fonte', obs: 'InfoDengue. Conferir a unidade na fonte.' }, ctx, { fonte: 'InfoDengue' }));
  }

  // troca os automaticos antigos do municipio pelos novos; os manuais ficam
  ['3.hosp', '3.amb', '3.ciha', '4.prof', '5.em', '6.prog', '7.eq', '8.vig'].forEach(k => {
    const antigos = arr(S.dados[k]).filter(e => !(e._auto === cod));
    S.dados[k] = antigos.concat(novos[k] || []);
  });
  api.save();
  const tot = Object.keys(novos).reduce((s, k) => s + novos[k].length, 0);
  return { msg: 'Preenchido automaticamente com dados do robô (' + tot + ' lançamentos e ' + nUn + ' unidades novas), com fonte e data de coleta. Campos sem dado oficial ficam como [PREENCHER]. Confira antes de emitir o relatório.' };
}
window.PartelliAuto = { preencher: preencher, msg: '' };
})();
