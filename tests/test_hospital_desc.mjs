import test from 'node:test';
import assert from 'node:assert/strict';
import * as D from '../hospital/js/cnes_desc.js';

const tab = {tabelas: {
  servico_classificacao_n: {'122003': '122 SERVICO DE DIAGNOSTICO / 003 CLASSE'},
  tipo_leito: {'1': '1-Cirúrgico'}, especialidade_leito: {'03': 'CIRURGIA GERAL'},
  habilitacao: {'1902': 'HAB TESTE'}, incentivo: {'8101': '8101-INTEGRASUS NIVEL A'},
  equipamento: {'0105': '0105-Raio X'},
  instalacoes_def: ['I* URGÊNCIA/EMERGÊNCIA *,URGEMERG', 'IQt.Sala Atendimento Pediatria ,QTINST01', 'I* ATEND. AMBULATORIAL *.,ATENDAMB',
    'IQt.Consultório Clínica Básica,QTINST15', 'I* CENTRO CIRÚRGICO *,CENTRCIR', 'IQt.sala Cirurgia,   QTINST31']}};

test('descricoes de codigos', () => {
  assert.match(D.descServico(tab, '122', '3'), /003 CLASSE/);
  assert.equal(D.descLeito(tab, '1', '03'), 'Cirúrgico · CIRURGIA GERAL');
  assert.equal(D.descHabilitacao(tab, '1902'), 'HAB TESTE');
  assert.equal(D.descIncentivo(tab, '8101'), 'INTEGRASUS NIVEL A');
  assert.equal(D.descEquipamento(tab, '01', '05'), 'Raio X');
  assert.equal(D.descServico(null, '1', '1'), '');
});

test('instalacoes por grupo e competencia do CNES', () => {
  assert.equal(D.descInstalacao(tab, '01'), 'Urgência/emergência: Sala Atendimento Pediatria');
  assert.equal(D.descInstalacao(tab, 15), 'Atend. ambulatorial: Consultório Clínica Básica');
  assert.equal(D.descInstalacao(tab, '31'), 'Centro cirúrgico: sala Cirurgia');
  assert.equal(D.fmtCompCnes('202605'), '05/2026');
  assert.equal(D.fmtCompCnes('999999'), 'sem data final');
});
