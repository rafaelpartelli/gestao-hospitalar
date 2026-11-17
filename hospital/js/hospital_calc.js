// Formulas oficiais da plataforma Partelli (secao 4.1) e criticas de dados (secao 6.1).
// Funcoes puras: usam somente valores lancados. Sem valor, devolvem null (a tela mostra [PREENCHER]).

const num = v => (v === '' || v == null || isNaN(Number(v))) ? null : Number(v);
const dado = v => num(v) !== null;

export function div(a, b) {
  a = num(a); b = num(b);
  if (a === null || b === null || b <= 0) return null;
  return a / b;
}

// 1. Media por AIH
export const mediaAIH = (valorAprovado, aprovadas) => div(valorAprovado, aprovadas);

// 2. Percentual de rejeicao (fracao). Base por AIH enviada; sem enviadas, base de AIH processadas (aprovadas + rejeitadas).
// Alternativa por valor: rejeitado / (aprovado + rejeitado). Informa sempre a base usada.
export function rejeicao(l) {
  const env = num(l.enviadas), rej = num(l.rejeitadas), apr = num(l.aprovadas);
  if (env !== null && env > 0 && rej !== null) return {valor: rej / env, base: 'AIHs enviadas'};
  if (rej !== null && apr !== null && rej + apr > 0) return {valor: rej / (rej + apr), base: 'AIHs processadas (aprovadas + rejeitadas)'};
  return {valor: null, base: null};
}
export function rejeicaoValor(l) {
  const r = num(l.valor_rejeitado), a = num(l.valor_aprovado);
  if (r === null || a === null || r + a <= 0) return {valor: null, base: null};
  return {valor: r / (r + a), base: 'valor (rejeitado / (aprovado + rejeitado))'};
}

// 3. Percentual de nao processadas
export const pctNaoProcessadas = l => div(l.nao_processadas, l.enviadas);

// 4 e 5. Composicao SH e SP
export const compSH = l => div(l.sh, l.valor_total ?? somaValores(l));
export const compSP = l => div(l.sp, l.valor_total ?? somaValores(l));
export function somaValores(l) {
  const a = num(l.valor_aprovado);
  return a;
}
// SH + SP deve ser igual ao valor total. Tolerancia de R$ 1,00 no agregado.
export function shSpConfere(l) {
  const sh = num(l.sh), sp = num(l.sp), t = num(l.valor_aprovado);
  if (sh === null || sp === null || t === null) return null;
  return Math.abs(sh + sp - t) <= 1;
}

// 6. Perda por rejeicao em R$
export const perdaRejeicao = l => num(l.valor_rejeitado);

// 7. Oportunidade por procedimento: so se media do benchmark e do hospital estiverem lancadas.
export function oportunidade(mediaBench, mediaHosp, qtd) {
  const b = num(mediaBench), h = num(mediaHosp), q = num(qtd);
  if (b === null || h === null || q === null) return {valor: null, acima: false};
  if (h > b) return {valor: 0, acima: true};
  return {valor: (b - h) * q, acima: false};
}

// 8. Delta comparativo (B menos A) e percentual (so se A > 0)
export const delta = (a, b) => (dado(a) && dado(b)) ? num(b) - num(a) : null;
export const deltaPct = (a, b) => (dado(a) && dado(b) && num(a) > 0) ? (num(b) - num(a)) / num(a) : null;

// 9. Similaridade entre CNES: itens em comum / total de itens unicos nos dois
export function similaridade(listaA, listaB) {
  const A = new Set(listaA), B = new Set(listaB);
  const uni = new Set([...A, ...B]);
  if (!uni.size) return {valor: null, comuns: 0, total: 0};
  let comuns = 0;
  for (const x of A) if (B.has(x)) comuns++;
  return {valor: comuns / uni.size, comuns, total: uni.size};
}

// 14 e 15. Benchmark: media por hospital e media geral
export const mediaHospitalBench = (valorTotal, qtd) => div(valorTotal, qtd);
export function mediaGeralBench(linhas) {
  let v = 0, q = 0;
  for (const l of linhas) { if (dado(l.valor) && dado(l.qtd)) { v += num(l.valor); q += num(l.qtd); } }
  return q > 0 ? v / q : null;
}

// Dias para o prazo (data ISO AAAA-MM-DD). Negativo = vencido.
export function diasParaPrazo(iso, hoje = new Date()) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(iso || '')) return null;
  const [a, m, d] = iso.split('-').map(Number);
  const alvo = Date.UTC(a, m - 1, d);
  const h = Date.UTC(hoje.getFullYear(), hoje.getMonth(), hoje.getDate());
  return Math.round((alvo - h) / 86400000);
}

// Capitulo do CID-10 a partir do codigo do diagnostico principal (ex.: J18, I21.0, C50).
export function capituloCID(cid) {
  const c = String(cid || '').trim().toUpperCase();
  if (!/^[A-Z]\d{2}/.test(c)) return null;
  const L = c[0], n = parseInt(c.slice(1, 3), 10);
  if (L === 'A' || L === 'B') return 'I. Doenças infecciosas e parasitárias';
  if (L === 'C' || (L === 'D' && n <= 48)) return 'II. Neoplasias';
  if (L === 'D') return 'III. Doenças do sangue e imunitárias';
  if (L === 'E') return 'IV. Doenças endócrinas, nutricionais e metabólicas';
  if (L === 'F') return 'V. Transtornos mentais e comportamentais';
  if (L === 'G') return 'VI. Doenças do sistema nervoso';
  if (L === 'H') return n <= 59 ? 'VII. Doenças do olho e anexos' : 'VIII. Doenças do ouvido';
  if (L === 'I') return 'IX. Doenças do aparelho circulatório';
  if (L === 'J') return 'X. Doenças do aparelho respiratório';
  if (L === 'K') return 'XI. Doenças do aparelho digestivo';
  if (L === 'L') return 'XII. Doenças da pele e do tecido subcutâneo';
  if (L === 'M') return 'XIII. Doenças osteomusculares e do tecido conjuntivo';
  if (L === 'N') return 'XIV. Doenças do aparelho geniturinário';
  if (L === 'O') return 'XV. Gravidez, parto e puerpério';
  if (L === 'P') return 'XVI. Afecções do período perinatal';
  if (L === 'Q') return 'XVII. Malformações congênitas';
  if (L === 'R') return 'XVIII. Sintomas e achados anormais';
  if (L === 'S' || L === 'T') return 'XIX. Lesões, envenenamentos e causas externas';
  if (L === 'V' || L === 'W' || L === 'X' || L === 'Y') return 'XX. Causas externas de morbidade e mortalidade';
  if (L === 'Z') return 'XXI. Fatores que influenciam o estado de saúde';
  if (L === 'U') return 'XXII. Códigos para propósitos especiais';
  return null;
}

// Criticas automaticas (6.1) aplicadas aos lancamentos de uma competencia.
// l = lancamento da competencia: {sih:{...}, procedimentos:[...], fonte, ano}, ctx = {habilitacoes:[], benchmark:{codigo:media}}
// Devolve {criticas:[...], nao_avaliadas:[...]}. Cada critica: codigo, descricao, severidade, origem, acao.
export function criticas(comp, ctx = {}) {
  const out = [], nao = [];
  const s = comp.sih || {};
  const add = (codigo, descricao, severidade, origem, acao) => out.push({codigo, descricao, severidade, origem, acao, status: 'Aberta'});

  if (!dado(s.aprovadas) && !dado(s.valor_aprovado) && !(comp.sia && dado(comp.sia.valor_aprovado))) {
    add('C04', 'Competência sem produção lançada (SIH e SIA).', 'Alta', 'AIH', 'Conferir a remessa no SIHD e no SIASUS e lançar a produção da competência.');
  }
  const conf = shSpConfere(s);
  if (conf === false) {
    add('C08', 'SH mais SP diferente do valor total aprovado.', 'Alta', 'AIH', 'Conferir os valores no relatório de AIH aprovadas e corrigir o lançamento ou abrir análise da AIH.');
  }
  if (dado(s.aih_sem_sh) && num(s.aih_sem_sh) > 0) {
    add('C03', `${num(s.aih_sem_sh)} AIH aprovada(s) sem valor de serviço hospitalar (SH).`, 'Alta', 'AIH', 'Listar as AIHs sem SH e conferir o procedimento realizado e a regra no SIGTAP.');
  }
  if (dado(s.aih_sem_sp) && num(s.aih_sem_sp) > 0) {
    add('C03b', `${num(s.aih_sem_sp)} AIH aprovada(s) sem valor de serviço profissional (SP).`, 'Média', 'AIH', 'Conferir se o procedimento admite SP zerado e se os profissionais foram lançados.');
  }
  if (dado(s.aih_sh_sp_divergente) && num(s.aih_sh_sp_divergente) > 0) {
    add('C08b', `${num(s.aih_sh_sp_divergente)} AIH(s) com SH mais SP diferente do total da própria AIH.`, 'Alta', 'AIH', 'Abrir o detalhamento das AIHs divergentes e conferir os componentes de valor.');
  }
  const rj = rejeicao(s);
  if (rj.valor !== null && rj.valor > 0) {
    add('C12', `Há AIH rejeitada na competência (${(rj.valor * 100).toFixed(1).replace('.', ',')}% pela base ${rj.base}).`, 'Média', 'AIH', 'Levantar os motivos de rejeição (arquivo ER ou SIHD), corrigir e reapresentar dentro do prazo.');
  }
  for (const p of (comp.procedimentos || [])) {
    const q = num(p.qtd), v = num(p.valor);
    if (q === 0 && v > 0) add('C11', `Procedimento ${p.codigo}: quantidade zero com valor maior que zero.`, 'Média', 'SIGTAP', 'Conferir o lançamento do procedimento.');
    if (v === 0 && q > 0) add('C11', `Procedimento ${p.codigo}: valor zero com quantidade maior que zero.`, 'Média', 'SIGTAP', 'Conferir o valor do procedimento na tabela SIGTAP da competência.');
    const b = ctx.benchmark && num(ctx.benchmark[p.codigo]);
    if (b && q > 0 && v > 0) {
      const media = v / q;
      if (media < b * 0.8 || media > b * 1.2) add('C05', `Procedimento ${p.codigo}: média por unidade fora de 20% do benchmark lançado (a confirmar com o gestor).`, 'Baixa', 'AIH', 'Confirmar com o gestor se a diferença tem justificativa assistencial.');
    }
  }
  if (!comp.fonte || !comp.ano) {
    add('C07', 'Lançamento sem fonte ou sem ano informado.', 'Média', 'outro', 'Informar a fonte oficial e o ano de referência.');
  }
  // Criticas que dependem de dado ainda nao lancado
  if (!(ctx.habilitacoes && ctx.habilitacoes.length)) nao.push('C01 e C06: CNES sem habilitação para o procedimento e divergência entre CNES e produção. Falta: [PREENCHER: habilitações e leitos do CNES].');
  nao.push('C02: procedimento sem CID. Falta: [PREENCHER: CID por AIH, só com base legal e sem dado pessoal].');
  nao.push('C09 e C10: competência sem SIGTAP correspondente e faixa de idade ou sexo. Falta: [PREENCHER: tabela SIGTAP da competência].');
  return {criticas: out, nao_avaliadas: nao};
}

export const ORDEM_SEV = {Alta: 0, Média: 1, Baixa: 2};
