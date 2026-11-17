#!/usr/bin/env python3
"""Embute o modulo Gestao Hospitalar no index.html da plataforma (secao #gestao-hospitalar, item de menu, CSS e JS).
Idempotente: pode rodar varias vezes. Uso: montar_plataforma.py <index.html> [<fragmento.html>]"""
import re, sys, os

def montar(html, fragmento):
    # limpa versoes anteriores
    html = re.sub(r"<!--GH:INICIO-->.*?<!--GH:FIM-->\s*", "", html, flags=re.S)
    html = re.sub(r'<a href="(?:/hospital/|#gestao-hospitalar)"[^>]*>Gestão Hospitalar</a>', "", html)
    html = re.sub(r'<link rel="stylesheet" href="hospital/css/hospital\.css[^>]*>\s*', "", html)
    html = re.sub(r'<script type="module" src="hospital/js/hospital\.js[^>]*></script>\s*', "", html)
    menu = '<a href="#gestao-hospitalar">Gestão Hospitalar</a>'
    ancora = '<a href="#faturamento">Faturamento SUS</a>'
    aside = html[html.index('<aside'):html.index('</aside>')]
    if aside.count(ancora) != 1:
        raise SystemExit("ERRO: item de menu 'Faturamento SUS' nao encontrado no <aside>.")
    novo_aside = aside.replace(ancora, ancora + menu)
    html = html.replace(aside, novo_aside, 1)
    if html.count('<section id="apis"') != 1:
        raise SystemExit("ERRO: secao #apis nao encontrada.")
    html = html.replace('<section id="apis"', "<!--GH:INICIO-->\n" + fragmento.strip() + "\n<!--GH:FIM-->\n<section id=\"apis\"", 1)
    html = html.replace("</head>", '<link rel="stylesheet" href="hospital/css/hospital.css?v=2">\n</head>', 1)
    html = html.replace("</body>", '<script type="module" src="hospital/js/hospital.js?v=2"></script>\n</body>', 1)
    return html

if __name__ == "__main__":
    idx = sys.argv[1]
    frag = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hospital", "fragmento.html")
    saida = montar(open(idx, encoding="utf-8").read(), open(frag, encoding="utf-8").read())
    open(idx, "w", encoding="utf-8").write(saida)
    print("Gestao Hospitalar embutida em", idx)
