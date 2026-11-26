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
  const E = {indice: null, nomes: {}, uf: '', mun: null, estab: '', dados: null, ufs: null, muns: {}};
  const selUF = el('select', {id: 'slUF', 'aria-label': 'Estado'}, el('option', {value: ''}, 'Escolha o estado'));
  const selMun = el('select', {id: 'slMun', 'aria-label': 'Município', disabled: true}, el('option', {value: ''}, 'Escolha o município'));
  const selEst = el('select', {id: 'slEst', 'aria-label': 'Estabelecimento', disabled: true}, el('option', {value: ''}, 'Todos os estabelecimentos'));
  const selo = el('p', {class: 'sl-selo', role: 'status', 'aria-live': 'polite'}, 'Escolha um estado e um município para ver a produção por estabelecimento.');
  const corpo = el('div', {class: 'sl-corpo'});
  const rot = (t, no) => el('label', null, t, no);

  raiz.append(
    el('header', {class: 'sl-topo'},
      el('p', {class: 'sl-marca'}, 'Rafael Partelli · Gestão em saúde pública'),
      el('h2', null, 'Gestão hospitalar'),
      el('p', {class: 'sl-lead'}, 'Escolha um estado e um município e a tela reúne, em uma só página, o ambulatório, as internações, a CIHA e os profissionais de cada estabelecimento. Cada bloco mostra a fonte e a data da última coleta.')),
    el('div', {class: 'sl-filtros', role: 'group', 'aria-label': 'Escolha do território'},
      rot('Estado', selUF), rot('Município', selMun), rot('Estabelecimento', selEst), selo),
    corpo);

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
    E.estab = ''; E.dados = null; limpar(selEst); selEst.append(el('option', {value: ''}, 'Todos os estabelecimentos')); selEst.disabled = true;
    if (!id) { E.mun = null; selo.textContent = 'Escolha um município.'; limpar(corpo); return; }
    E.mun = {id, nome: (selMun.selectedOptions[0] || {}).textContent || ''};
    selo.textContent = 'Carregando dados...';
    const item = arr(E.indice && E.indice.municipios).find(m => String(m.cod).slice(0, 6) === id.slice(0, 6));
    const arq = item ? await carregar(DS + 'rede_' + item.cod + '_estab.json') : null;
    if (!arq) { selo.textContent = 'Município fora da lista do robô.'; aviso0('Este município ainda não está na lista do robô (hoje: municípios piloto do ES). Os dados abaixo ficam em branco até a coleta cobrir o território. Você pode preencher as etapas da trilha manualmente, com fonte e data.'); return; }
    E.dados = arq;
    const sec = arq.secao || {};
    const lista = arr(sec.estabelecimentos).slice().sort((a, b) => (nomeEst(a.cnes) || 'zzz' + a.cnes).localeCompare(nomeEst(b.cnes) || 'zzz' + b.cnes, 'pt-BR'));
    lista.forEach(f => selEst.append(el('option', {value: f.cnes}, rotuloEst(f))));
    selEst.disabled = !lista.length;
    selo.textContent = lista.length ? `${inteiro(lista.length)} estabelecimento(s) com produção ou profissionais. Dados gerados em ${dtBr(arq.gerado_em) || 'data sem registro'}.` : 'Sem estabelecimentos na base.';
    pintar();
  }

  function pintar() {
    limpar(corpo);
    const arq = E.dados; if (!arq) return;
    const sec = arq.secao || {};
    const todos = arr(sec.estabelecimentos);
    if (!todos.length) { corpo.append(aviso(sec.situacao || 'A confirmar: sem produção por estabelecimento na base.')); return; }
    const sel = E.estab ? todos.filter(f => f.cnes === E.estab) : todos;
    const um = sel.length === 1 && !!E.estab ? sel[0] : null;
    const gerado = dtBr(arq.gerado_em) || 'data sem registro';
    const fonte = txt => el('p', {class: 'sl-fonte'}, 'Fonte: ' + txt + ' Coleta: ' + gerado + '.');
    const nome = f => el('div', null, el('strong', null, nomeEst(f.cnes) || 'Sem nome público'), el('div', {class: 'rd-peq'}, 'CNES ' + f.cnes + ' · ' + tipoTxt(f.tipo_unidade)));

    // resumo
    const aih = soma(sel, f => soma(f.sih, x => x.aih)), vsih = soma(sel, f => soma(f.sih, x => x.valor_total));
    const qsia = soma(sel, f => soma((f.sia || {}).por_mes, x => x.quantidade_aprovada)), vsia = soma(sel, f => soma((f.sia || {}).por_mes, x => x.valor_aprovado));
    const vinc = soma(sel, f => (f.profissionais || {}).vinculos);
    corpo.append(el('section', {class: 'sl-sec', 'aria-labelledby': 'sl-h-res'}, el('h3', {id: 'sl-h-res'}, um ? (nomeEst(um.cnes) || 'Estabelecimento sem nome público') + ' (CNES ' + um.cnes + ')' : 'Resumo do município'),
      el('div', {class: 'rd-kpis'},
        kpi('hospital', 'azul', 'Estabelecimentos', inteiro(sel.length), um ? tipoTxt(um.tipo_unidade) : 'com produção ou profissionais na base'),
        kpi('doc', 'azul', 'Internações (AIH)', inteiro(aih), vsih ? brlc(vsih) + ' em valor total SIH' : 'sem valor na base'),
        kpi('grafico', 'verde', 'Ambulatório aprovado', inteiro(qsia), vsia ? brlc(vsia) + ' em valor aprovado SIA' : 'sem valor na base'),
        kpi('pessoas', 'azul', 'Vínculos profissionais', inteiro(vinc), 'contagem de vínculos, não de pessoas'))));

    // ambulatorio
    const rowsA = sel.map(f => { const s = (f.sia || {}).por_mes; if (!arr(s).length) return [nome(f), 'sem dado', 'sem dado', 'sem competência']; return [nome(f), inteiro(soma(s, x => x.quantidade_aprovada)), brl(soma(s, x => x.valor_aprovado)), ate(s)]; });
    const secA = cartao('Ambulatório (SIA)', 'Produção ambulatorial aprovada por estabelecimento, soma das competências disponíveis.', tabela(['Estabelecimento', 'Quantidade aprovada', 'Valor aprovado', 'Competências'], rowsA, [1, 2]));
    if (um && arr((um.sia || {}).por_mes).length) secA.append(detalhesTabela('Ver por mês', tabela(['Mês de processamento', 'Quantidade aprovada', 'Valor aprovado'], um.sia.por_mes.map(x => [x.mes_processamento, inteiro(x.quantidade_aprovada), brl(x.valor_aprovado)]), [1, 2])));
    if (um && arr((um.sia || {}).principais_procedimentos).length) secA.append(detalhesTabela('Principais procedimentos (código SIGTAP)', tabela(['Procedimento', 'Quantidade aprovada', 'Valor aprovado'], um.sia.principais_procedimentos.map(x => [x.procedimento, inteiro(x.quantidade_aprovada), brl(x.valor_aprovado)]), [1, 2])));
    secA.append(fonte('SIA/SUS (arquivo PA), valores aprovados, via DATASUS.'));

    // internacoes
    const linhaI = f => { if (!arr(f.sih).length) return [nome(f), 'sem dado', 'sem dado', 'sem dado', 'sem dado', 'sem dado', 'sem dado', 'sem dado']; const s = f.sih, a = soma(s, x => x.aih), v = soma(s, x => x.valor_total), r = soma(s, x => x.rejeitadas), tem = arr(s).some(x => num(x.rejeitadas)); return [nome(f), inteiro(a), brl(v), media(v, a) == null ? 'sem dado' : brl(media(v, a)), inteiro(soma(s, x => x.obitos)), media(soma(s, x => x.dias_permanencia), a) == null ? 'sem dado' : decimal(media(soma(s, x => x.dias_permanencia), a), 1), tem ? inteiro(r) : 'sem dado', tem && a + r > 0 ? pct(r / (a + r) * 100) : 'sem dado']; };
    const secI = cartao('Internações (SIH)', 'AIH aprovadas por estabelecimento. A rejeição vem do arquivo ER, em quantidade de AIH (base: AIH rejeitadas ÷ AIH aprovadas e rejeitadas). Valor rejeitado e não processadas ficam em branco: a fonte não traz R$.', tabela(['Estabelecimento', 'AIH aprovadas', 'Valor total', 'Média por AIH', 'Óbitos', 'Permanência média (dias)', 'AIH rejeitadas', '% de rejeição'], sel.map(linhaI), [1, 2, 3, 4, 5, 6, 7]));
    if (um && arr(um.sih).length) {
      secI.append(el('div', {class: 'sl-graf'}, barrasMes(um.sih, 'aih', 'AIH aprovadas por mês')));
      secI.append(detalhesTabela('Ver por mês', tabela(['Competência', 'AIH aprovadas', 'Valor total', 'Óbitos', 'Dias de permanência', 'AIH rejeitadas'], um.sih.map(x => [x.competencia, inteiro(x.aih), brl(x.valor_total), inteiro(x.obitos), inteiro(x.dias_permanencia), num(x.rejeitadas) ? inteiro(x.rejeitadas) : 'sem dado']), [1, 2, 3, 4, 5])));
    }
    secI.append(fonte('SIH/SUS (arquivos RD e ER) via DATASUS.'));

    // CIHA
    const secC = cartao('CIHA (Comunicação de Internação Hospitalar e Ambulatorial)', 'Registros de estabelecimentos que não faturam pelo SIH, por estabelecimento.', tabela(['Estabelecimento', 'Registros', 'Procedimentos', 'Dias de permanência', 'Óbitos', 'Competências'],
      sel.map(f => !arr(f.ciha).length ? [nome(f), 'sem dado', 'sem dado', 'sem dado', 'sem dado', 'sem competência'] : [nome(f), inteiro(soma(f.ciha, x => x.registros)), inteiro(soma(f.ciha, x => x.quantidade_procedimentos)), inteiro(soma(f.ciha, x => x.dias_permanencia)), inteiro(soma(f.ciha, x => x.obitos)), ate(f.ciha)]), [1, 2, 3, 4]));
    if (um && arr(um.ciha).length) secC.append(detalhesTabela('Ver por mês', tabela(['Competência', 'Registros', 'Procedimentos', 'Dias de permanência', 'Óbitos'], um.ciha.map(x => [x.competencia, inteiro(x.registros), inteiro(x.quantidade_procedimentos), inteiro(x.dias_permanencia), inteiro(x.obitos)]), [1, 2, 3, 4])));
    secC.append(fonte('CIHA, via DATASUS.'));

    // profissionais
    const secP = cartao('Profissionais (CNES)', 'Vínculos e carga horária semanal por estabelecimento. Conta vínculos (quem atua em dois estabelecimentos aparece duas vezes). Nenhum nome de profissional é coletado ou exibido.', tabela(['Estabelecimento', 'Vínculos', 'Horas ambulatoriais', 'Horas hospitalares', 'Outras horas', 'Competência'],
      sel.map(f => { const p = f.profissionais; return [nome(f), p ? inteiro(p.vinculos) : 'sem dado', p ? inteiro(p.horas_ambulatoriais) : 'sem dado', p ? inteiro(p.horas_hospitalares) : 'sem dado', p ? inteiro(p.horas_outras) : 'sem dado', p ? String(p.competencia || '').replace(/^(\d{4})(\d{2})$/, '$2/$1') : 'sem dado']; }), [1, 2, 3, 4]));
    if (um && um.profissionais && arr(um.profissionais.principais_cbo).length) secP.append(detalhesTabela('Principais CBO (ocupações), em vínculos', tabela(['CBO', 'Vínculos', 'Horas ambulatoriais', 'Horas hospitalares', 'Outras horas'], um.profissionais.principais_cbo.map(x => [x.cbo, inteiro(x.vinculos), inteiro(x.horas_ambulatoriais), inteiro(x.horas_hospitalares), inteiro(x.horas_outras)]), [1, 2, 3, 4])));
    secP.append(fonte('CNES, profissionais (arquivo PF), via DATASUS.'));

    corpo.append(secA, secI, secC, secP);
    if (sec.truncado) corpo.append(aviso('Lista limitada aos estabelecimentos de maior produção.'));
    corpo.append(el('p', {class: 'rd-peq'}, sec.obs || ''));
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

  selUF.addEventListener('change', async () => { E.uf = selUF.value; E.dados = null; limpar(corpo); selEst.disabled = true; limpar(selMun); selMun.append(el('option', {value: ''}, 'Escolha o município')); selMun.disabled = true; if (!E.uf) { selo.textContent = 'Escolha um estado.'; return; } selo.textContent = 'Carregando municípios...'; await carregarMuns(E.uf); selo.textContent = 'Escolha o município.'; });
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
