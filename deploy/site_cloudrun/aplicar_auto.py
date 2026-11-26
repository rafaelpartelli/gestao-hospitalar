#!/usr/bin/env python3
"""Liga o preenchimento automatico das etapas 1, 3, 4, 5, 6, 7 e 8 ao site novo (app.js, index.html, Dockerfile). Uso: python3 aplicar_auto.py <pasta_do_site>
Copia hospital/js/auto.js para a pasta e faz ajustes pontuais (ancoras). Para se uma ancora nao existir. Idempotente."""
import sys, pathlib, shutil
pasta = pathlib.Path(sys.argv[1]); aqui = pathlib.Path(__file__).resolve().parent
def trocar(t, velho, novo, nome):
    if novo in t: return t
    if velho not in t: sys.exit(f'ERRO: ancora nao encontrada em {nome}: {velho[:70]!r}')
    return t.replace(velho, novo, 1)
shutil.copy(aqui.parent.parent / 'hospital' / 'js' / 'auto.js', pasta / 'auto.js')
a = (pasta / 'app.js').read_text(encoding='utf-8')
a = trocar(a, "  save(); atualizaTopo(); if (rotaAtual() === '1') render();\n}", "  save(); atualizaTopo(); await autoPreencher(); if (rotaAtual() === '1') render();\n}", 'app.js escolherMunicipio')
a = trocar(a, "/* ===================== telas ===================== */",
 "async function autoPreencher() {\n  if (!window.PartelliAuto) return;\n  try { const r = await window.PartelliAuto.preencher({ S: () => S, save: save, uid: uid, hoje: hoje }); window.PartelliAuto.msg = (r && r.msg) || ''; } catch (e) { window.PartelliAuto.msg = ''; }\n}\nwindow.PartelliApp = { refazer: async function () { await autoPreencher(); render(); } };\n\n/* ===================== telas ===================== */", 'app.js telas')
a = trocar(a, "  c.innerHTML = h;\n", "  c.innerHTML = h;\n  if (window.PartelliAuto && window.PartelliAuto.msg && S.mun) c.insertAdjacentHTML('afterbegin', '<p class=\"aviso\" role=\"status\">' + esc(window.PartelliAuto.msg) + '</p>');\n", 'app.js render')
a = trocar(a, "    if (soma !== nz(e.env)) c.push", "    if (e.env !== '' && e.env != null && soma !== nz(e.env)) c.push", 'app.js critica')
a = trocar(a, "render();\n})();", "render();\nwindow.addEventListener('load', function () { if (S.mun && S.mun.id && window.PartelliApp) window.PartelliApp.refazer(); });\n})();", 'app.js fim')
(pasta / 'app.js').write_text(a, encoding='utf-8')
h = (pasta / 'index.html').read_text(encoding='utf-8')
h = trocar(h, '<script src="rede.js"></script>', '<script src="auto.js"></script>\n<script src="rede.js"></script>', 'index.html')
(pasta / 'index.html').write_text(h, encoding='utf-8')
d = (pasta / 'Dockerfile').read_text(encoding='utf-8')
d = trocar(d, 'app.js rede.js /usr', 'app.js auto.js rede.js /usr', 'Dockerfile')
(pasta / 'Dockerfile').write_text(d, encoding='utf-8')
print('auto.js aplicado em', pasta)
