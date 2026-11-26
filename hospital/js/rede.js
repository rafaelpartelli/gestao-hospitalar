// Aba "Rede e rejeicoes (ES)": le os JSON gerados pelo super robo (rede_indice, rede_<cod>, rede_rejeicao_es). Textos externos nunca entram como HTML (el()).
import {el, limpar, carregar, tabela, inteiro, decimal} from './util.js';

const D = new URL('../', import.meta.url).href + 'dados/';
const brl = v => new Intl.NumberFormat('pt-BR', {style: 'currency', currency: 'BRL'}).format(v);
const num = v => typeof v === 'number' && Number.isFinite(v);
const pct = v => num(v) ? decimal(v, 1) + '%' : (typeof v === 'string' ? v : 'sem dado');
const pend = txt => el('span', {class: 'pendente'}, `[PREENCHER: ${txt}]`);
const arr = x => Array.isArray(x) ? x : [];
const kpi = (rot, val, nota) => el('div', {class: 'kpi'}, el('div', {class: 'rot'}, rot), el('div', {class: 'val'}, val), nota ? el('div', {class: 'nota'}, nota) : null);
const aviso = txt => el('p', {class: 'aviso'}, txt);
const motivo = m => m ? `${m.texto_manual} (manual do SIH, p. ${m.pagina_manual}; ${m.status.toLowerCase()})` : 'sem descrição localizada';
const codErro = c => el('span', null, `${c.codigo_erro}: `, motivo(c.motivo_provavel));

export function abaRede() {
  const w = el('div', null, el('h2', null, 'Rede hospitalar e rejeições (ES)'));
  w.append(el('p', {class: 'fonte'}, 'Fonte: SIH/SUS (RD e ER) e CNES, arquivos do DATASUS lidos pelo super robô do notebook. Somente dados agregados, identificados por código CNES e código do município.'));
  const alvo = el('div', null, el('p', null, 'Carregando...'));
  w.append(alvo);
  montar(alvo);
  return w;
}

async function montar(alvo) {
  const [indice, estado] = await Promise.all([carregar(D + 'rede_indice.json'), carregar(D + 'rede_rejeicao_es.json')]);
  limpar(alvo);
  if (!indice && !estado) { alvo.append(aviso('[PREENCHER: dados do super robô ainda não publicados nesta página. Rode partelli-coleta publicar no notebook.]')); return; }
  if (estado) alvo.append(blocoEstado(estado));
  if (indice) alvo.append(blocoMunicipios(indice));
}

function blocoEstado(e) {
  const b = el('div', {class: 'bloco'}, el('h3', null, 'Estado: rejeição por CNES'));
  if (!arr(e.itens).length) { b.append(aviso(e.situacao || 'A confirmar: sem dados de rejeição.')); return b; }
  b.append(el('div', {class: 'kpis'},
    kpi('AIH rejeitadas no ES', inteiro(e.total_rejeitadas_es), 'arquivo ER, 2026'),
    kpi('CNES listados', inteiro(e.cnes_listados), `${pct(e.pct_acumulado_listados)} do total`),
    kpi('Competência em aberto', e.competencia_em_aberto || 'sem dado', 'fica fora da recuperação')));
  b.append(tabela(['CNES', 'Município (cód.)', 'Rejeitadas', '% do total', '% acumulado', '% recuperadas', 'Principais códigos de erro'],
    e.itens.map(i => [i.cnes, i.municipio_movimento, inteiro(i.rejeitadas), pct(i.pct_do_total), pct(i.pct_acumulado), pct(i.pct_recuperadas),
      el('div', null, arr(i.principais_codigos_erro).map(c => el('div', null, `${inteiro(c.aih)} AIH, `, codErro(c))))]), [2, 3, 4, 5]));
  b.append(el('p', {class: 'fonte'}, `${e.regra || ''} ${e.obs || ''}`));
  return b;
}

function blocoMunicipios(ind) {
  const b = el('div', {class: 'bloco'}, el('h3', null, 'Hospitais do município'));
  const lista = arr(ind.municipios);
  if (!lista.length) { b.append(aviso('A confirmar: nenhum município exportado.')); return b; }
  const sel = el('select', {id: 'selRedeMun', 'aria-label': 'Município'}, el('option', {value: ''}, 'Escolha o município'),
    lista.map(m => el('option', {value: m.cod}, `${m.nome} (${m.hospitais} hospital(is))`)));
  const corpo = el('div');
  sel.addEventListener('change', async () => {
    limpar(corpo);
    if (!sel.value) return;
    corpo.append(el('p', null, 'Carregando...'));
    const d = await carregar(D + `rede_${sel.value}.json`);
    limpar(corpo);
    corpo.append(d ? municipio(d) : aviso('A confirmar: arquivo do município não encontrado.'));
  });
  b.append(el('label', null, 'Município ', sel), corpo);
  return b;
}

function municipio(d) {
  const h = d.hospitais;
  const w = el('div');
  w.append(el('p', {class: 'fonte'}, `Gerado em: ${d.gerado_em || '[PREENCHER: data]'} · ${h && h.fonte ? h.fonte : ''}`));
  if (!h || !arr(h.itens).length) { w.append(aviso((h && (h.situacao || h.obs)) || 'A confirmar: sem hospital na base.')); return w; }
  const sev = h.criticas_por_severidade || {};
  w.append(el('div', {class: 'kpis'}, kpi('Hospitais', inteiro(h.total)), kpi('Críticas Alta', inteiro(sev.Alta)), kpi('Críticas Média', inteiro(sev.Media)), kpi('Críticas Baixa', inteiro(sev.Baixa))));
  w.append(tabela(['CNES', 'AIH (2026)', 'Valor total', 'Média por AIH', 'Ocupação estimada', 'Rejeição no período', 'Habilitações (habilitado/total)', 'Críticas'],
    h.itens.map(i => {
      const ind = i.indicadores || {}, rj = i.rejeicao_sih || {}, hb = i.checklist_habilitacao || {};
      return [i.cnes, inteiro(ind.aih), num(ind.valor_total) ? brl(ind.valor_total) : 'sem dado', num(ind.media_por_aih) ? brl(ind.media_por_aih) : 'sem dado',
        pct(ind.ocupacao_estimada_pct), pct(rj.pct_rejeicao_periodo), hb.total ? `${(hb.resumo || {}).Habilitado || 0}/${hb.total}` : 'sem dado', inteiro(arr(i.criticas).length)];
    }), [1, 2, 3, 4, 5, 6, 7]));
  const sel = el('select', {'aria-label': 'Hospital (CNES)'}, el('option', {value: ''}, 'Detalhar um hospital (CNES)'), h.itens.map(i => el('option', {value: i.cnes}, `CNES ${i.cnes}`)));
  const det = el('div');
  sel.addEventListener('change', () => { limpar(det); const i = h.itens.find(x => x.cnes === sel.value); if (i) det.append(hospital(i)); });
  w.append(el('label', null, 'Detalhe ', sel), det);
  w.append(el('p', {class: 'fonte'}, h.obs || ''));
  return w;
}

function hospital(i) {
  const w = el('div', {class: 'bloco'}, el('h3', null, `CNES ${i.cnes}`));
  const ind = i.indicadores || {};
  w.append(el('div', {class: 'kpis'},
    kpi('AIH aprovadas', inteiro(ind.aih), `${inteiro(ind.meses_com_producao)} mês(es) com produção`),
    kpi('Valor total', num(ind.valor_total) ? brl(ind.valor_total) : 'sem dado', 'SH + SP + complemento federal'),
    kpi('Média por AIH', num(ind.media_por_aih) ? brl(ind.media_por_aih) : 'sem dado', 'valor total ÷ AIH'),
    kpi('Permanência média', num(ind.permanencia_media_dias) ? decimal(ind.permanencia_media_dias, 1) + ' dias' : 'sem dado', 'dias ÷ AIH'),
    kpi('Ocupação estimada', pct(ind.ocupacao_estimada_pct), 'ESTIMATIVA, não substitui o censo'),
    kpi('Mortalidade hospitalar', pct(ind.mortalidade_hospitalar_pct), 'óbitos ÷ AIH')));
  const prod = arr((i.producao || {}).sih_por_mes);
  w.append(el('h3', null, 'Produção SIH por mês'));
  w.append(prod.length ? tabela(['Competência', 'AIH', 'Valor total', 'SH', 'SP', 'Complemento federal', 'Ocupação estimada'],
    prod.map(x => [x.competencia, inteiro(x.aih), brl(x.valor_total), brl(x.sh), brl(x.sp), brl((x.sh_fed || 0) + (x.sp_fed || 0)), pct(x.ocupacao_estimada_pct)]), [1, 2, 3, 4, 5, 6]) : aviso('A confirmar: sem produção SIH na base.'));
  const rj = i.rejeicao_sih;
  w.append(el('h3', null, 'Rejeição (arquivo ER)'));
  if (!rj || rj.situacao) w.append(aviso((rj && rj.situacao) || 'A confirmar: sem dado de rejeição.'));
  else {
    const rec = rj.reapresentacao || {};
    w.append(el('p', null, `${inteiro(rj.total_rejeitadas)} AIH rejeitadas (${pct(rj.pct_rejeicao_periodo)} sobre aprovadas e rejeitadas). ${rec.pct_recuperadas != null ? `Recuperadas em competência posterior: ${pct(rec.pct_recuperadas)}.` : ''}`));
    if (arr(rec.por_codigo_erro).length) w.append(tabela(['Código', 'Motivo provável (a confirmar)', 'Rejeitadas', 'Recuperadas', 'Não recuperadas', '% recuperadas'],
      rec.por_codigo_erro.map(c => [c.codigo_erro, motivo(c.motivo_provavel), inteiro(c.rejeitadas), inteiro(c.recuperadas), inteiro(c.nao_recuperadas), pct(c.pct_recuperadas)]), [2, 3, 4, 5]));
    if (num(rec.perda_liquida_estimada_rs)) w.append(aviso(`ESTIMATIVA de perda: ${brl(rec.perda_liquida_estimada_rs)} (AIH não recuperadas x média por AIH). Não é resultado apurado.`));
    w.append(el('p', {class: 'fonte'}, rj.obs || ''));
  }
  const hb = i.checklist_habilitacao || {};
  w.append(el('h3', null, 'Habilitações (CNES)'));
  w.append(arr(hb.itens).length ? tabela(['Código', 'Descrição', 'Portaria', 'Data', 'Vigência', 'Status', 'Motivo'],
    hb.itens.map(x => [x.codigo, x.descricao || pend('descrição'), x.portaria || pend('portaria'), x.data_portaria || '', `${x.vigencia_inicio || ''} a ${x.vigencia_fim || ''}`, x.status, x.motivo])) : aviso(hb.situacao || 'A confirmar: sem habilitação na base.'));
  w.append(el('h3', null, 'Críticas'));
  w.append(arr(i.criticas).length ? tabela(['Código', 'Descrição', 'Severidade', 'Ação recomendada', 'Status'],
    i.criticas.map(c => [c.codigo, c.descricao, c.severidade, c.acao_recomendada, c.status])) : el('p', null, 'Nenhuma crítica aberta.'));
  const pl = i.plano_avanco || {};
  w.append(el('h3', null, 'Plano de avanço do faturamento'));
  if (arr(pl.itens).length) {
    w.append(tabela(['Ação', 'Crítica', 'Prioridade', 'Perda estimada', 'Ganho estimado', 'Prazo', 'Responsável', 'Status'],
      pl.itens.map(x => [x.acao, x.critica_vinculada, x.prioridade, num(x.perda_por_rejeicao_rs) ? brl(x.perda_por_rejeicao_rs) + ' (estimativa)' : '', num(x.ganho_estimado_rs) ? brl(x.ganho_estimado_rs) : pend('ganho'), x.prazo, x.responsavel, x.status]), [3, 4]));
    if (pl.pendencia_ganho) w.append(el('p', {class: 'fonte'}, pl.pendencia_ganho));
  } else w.append(el('p', null, 'Sem ações no plano.'));
  return w;
}
