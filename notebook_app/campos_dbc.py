#!/usr/bin/env python3
"""Mostra so o cabecalho dos arquivos DBC (nomes de campos, tipo, tamanho e total de registros). Nenhum valor e lido.
Uso: campos_dbc.py ARQUIVO.dbc [ARQUIVO2.dbc ...]   (sem argumento, usa um arquivo de cada tipo em ~/partelli/ftp_downloads)"""
import glob, os, sys
AQUI = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("PARTELLI_BASE", os.path.join(os.path.expanduser("~"), "partelli"))
for p in (os.path.join(AQUI, "..", "robo"), os.path.join(BASE, "sala-gestao", "robo")):
    if os.path.isdir(p):
        sys.path.insert(0, os.path.abspath(p))
import dbc
import hospital_comum as H

arqs = sys.argv[1:]
if not arqs:
    pasta = os.environ.get("PAINEL_DOWNLOADS", os.path.join(BASE, "ftp_downloads"))
    for pref in ("RDES", "SPES", "PAES"):
        achados = sorted(glob.glob(os.path.join(pasta, pref + "*.dbc")))
        if achados:
            arqs.append(achados[-1])
for a in arqs:
    with open(a, "rb") as f:
        cab = dbc.cabecalho(f.read(65536))
    print(f"== {os.path.basename(a)}: {cab['registros']} registros, {len(cab['campos'])} campos")
    print(" ".join(f"{c[0]}:{c[1]}{c[2]}" + ("*" if c[0] in H.PROIBIDOS else "") for c in cab["campos"]))
if not arqs:
    print("nenhum arquivo RDES/SPES/PAES baixado ainda")
