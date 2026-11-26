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

css = '''#rede-wrap{--rd-azul:#1351b4;--rd-escuro:#0c326f;--rd-linha:#d9dde3;--rd-mudo:#4b5563;--rd-aviso-bg:#fff4d6;--rd-aviso-tx:#6b4e00}
#rede-wrap h2{color:var(--rd-escuro)}
#rede-wrap .bloco{background:#fff;border:1px solid var(--rd-linha);border-radius:10px;padding:18px 16px;margin:24px 0}
#rede-wrap .fonte{margin:0 0 14px;font-size:.82rem;color:var(--rd-mudo)}
#rede-wrap .aviso{background:var(--rd-aviso-bg);color:var(--rd-aviso-tx);border-radius:8px;padding:10px 12px;font-size:.9rem;margin:8px 0}
#rede-wrap .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}
#rede-wrap .kpi{background:#fff;border:1px solid var(--rd-linha);border-radius:10px;padding:12px 14px}
#rede-wrap .kpi .rot{font-size:.78rem;color:var(--rd-mudo)}
#rede-wrap .kpi .val{font-size:1.5rem;font-weight:700;line-height:1.25;color:var(--rd-escuro)}
#rede-wrap .kpi .nota{font-size:.75rem;color:var(--rd-mudo)}
#rede-wrap table{border-collapse:collapse;width:100%;font-size:.88rem}
#rede-wrap th,#rede-wrap td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--rd-linha);vertical-align:top}
#rede-wrap td.n,#rede-wrap th.n{text-align:right;font-variant-numeric:tabular-nums}
#rede-wrap .tabela-rolavel{overflow-x:auto}
#rede-wrap .pendente{color:var(--rd-aviso-tx);background:var(--rd-aviso-bg);border-radius:4px;padding:0 4px;font-size:.85em}
#rede-wrap select{font:inherit;min-height:44px;padding:6px 10px;border:1px solid var(--rd-linha);border-radius:8px;background:#fff;max-width:100%}
#rede-wrap label{display:block;margin:10px 0}
'''
(saida / 'rede.css').write_text(css, encoding='utf-8')
print('gerado:', saida / 'rede.js', saida / 'rede.css')
