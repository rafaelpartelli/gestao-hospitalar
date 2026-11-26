#!/usr/bin/env python3
"""Gera rede.js (script classico, sem modulos) e rede.css para o site partelli.tec.br (SPA em nginx).
Uso: python3 montar_site_rede.py <pasta_saida>
Le hospital/js/util.js e hospital/js/rede.js do repositorio, que continuam sendo a fonte unica."""
import re, sys, pathlib
RAIZ = pathlib.Path(__file__).resolve().parents[2]
saida = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else '.')
saida.mkdir(parents=True, exist_ok=True)

util = (RAIZ / 'hospital/js/util.js').read_text(encoding='utf-8')
rede = (RAIZ / 'hospital/js/rede.js').read_text(encoding='utf-8')
# util: so o que o rede.js usa (el, limpar, carregar, tabela, inteiro, decimal)
corte = util.index('// ---- Descricao de codigos do CNES')
util = util[:corte].replace('export ', '')
rede = re.sub(r"^import .*\n", '', rede, flags=re.M)
rede = rede.replace("const D = new URL('../', import.meta.url).href + 'dados/';", "const D = '/dados/';")
rede = rede.replace('export function abaRede', 'function abaRede')
gancho = r'''
// ---- integracao com a trilha do site: rota #/rede
function mostrarRede() {
  if (location.hash.replace(/^#\/?/, '') !== 'rede') return;
  const c = document.getElementById('conteudo');
  if (!c) return;
  const w = document.createElement('div');
  w.id = 'rede-wrap';
  w.append(abaRede());
  c.replaceChildren(w);
  document.querySelectorAll('.t-item').forEach(a => {
    const on = a.dataset.r === 'rede';
    a.classList.toggle('ativo', on);
    if (on) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
  });
}
window.addEventListener('hashchange', mostrarRede);
mostrarRede();
'''
(saida / 'rede.js').write_text('(function () {\n"use strict";\n' + util + '\n' + rede + gancho + '})();\n', encoding='utf-8')

css = (RAIZ / 'hospital/css/rede.css').read_text(encoding='utf-8')
(saida / 'rede.css').write_text(css, encoding='utf-8')
print('gerado:', saida / 'rede.js', saida / 'rede.css')
