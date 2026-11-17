#!/usr/bin/env python3
"""Producao ambulatorial (SIA/SUS) por CNES configurado, a partir dos arquivos PA do FTP do DATASUS.
Mostra o valor apresentado e o aprovado (a diferenca e a glosa), por grupo e por procedimento, e a divisao por financiamento.
Somente agregados. Saida: <PARTELLI_DADOS>/<CNES>.json, bloco competencias.<AAAAMM>.sia.
Layout nao confirmado em campo: rode antes 'python3 coletar_hospital_sia.py --sondar'. Status da fonte: Em teste."""
import re, sys
import dbc
import hospital_comum as H
from comum import numero_br, agora

TOP = 40
DESEJADOS = ["PA_CODUNI", "PA_PROC_ID", "PA_QTDPRO", "PA_QTDAPR", "PA_VALPRO", "PA_VALAPR", "PA_FINANC"]
GRUPOS = {"01": "Promoção e prevenção em saúde", "02": "Diagnóstico", "03": "Procedimentos clínicos", "04": "Procedimentos cirúrgicos",
          "05": "Transplantes", "06": "Medicamentos", "07": "Órteses, próteses e materiais", "08": "Ações complementares"}


def novo():
    return {"qtd_apr": 0.0, "qtd_pro": 0.0, "val_apr": 0.0, "val_pro": 0.0, "proc": {}, "grupo": {}, "financ": {}, "linhas": 0}


def agregar_pa(registros, cnes_set, acumulado=None):
    por = acumulado or {c: novo() for c in cnes_set}
    lidos = 0
    for r in registros:
        lidos += 1
        c = (r.get("PA_CODUNI") or "").strip()
        if c not in por:
            continue
        d = por[c]
        qa, qp = numero_br(r.get("PA_QTDAPR")), numero_br(r.get("PA_QTDPRO"))
        va, vp = numero_br(r.get("PA_VALAPR")), numero_br(r.get("PA_VALPRO"))
        d["linhas"] += 1
        d["qtd_apr"] += qa; d["qtd_pro"] += qp; d["val_apr"] += va; d["val_pro"] += vp
        proc = (r.get("PA_PROC_ID") or "").strip()
        if proc:
            a = d["proc"].setdefault(proc, [0.0, 0.0, 0.0, 0.0]); a[0] += qp; a[1] += qa; a[2] += vp; a[3] += va
            g = d["grupo"].setdefault(proc[:2], [0.0, 0.0, 0.0]); g[0] += qa; g[1] += vp; g[2] += va
        f = (r.get("PA_FINANC") or "").strip()
        if f:
            a = d["financ"].setdefault(f, [0.0, 0.0]); a[0] += qa; a[1] += va
    return por, lidos


def montar_bloco(d, arquivos, aviso):
    t = sorted(d["proc"].items(), key=lambda kv: kv[1][3], reverse=True)[:TOP]
    return {"fonte": "SIA/SUS, FTP do DATASUS (arquivos PA)", "coletado_em": agora(), "arquivos": arquivos, "status_fonte": "Em teste",
            "linhas": d["linhas"], "qtd_apresentada": round(d["qtd_pro"], 2), "qtd_aprovada": round(d["qtd_apr"], 2),
            "valor_apresentado": round(d["val_pro"], 2), "valor_aprovado": round(d["val_apr"], 2),
            "grupos": [{"grupo": k, "nome": GRUPOS.get(k, "Outro grupo"), "qtd": round(v[0], 2), "valor_apresentado": round(v[1], 2), "valor_aprovado": round(v[2], 2)} for k, v in sorted(d["grupo"].items())],
            "procedimentos": [{"codigo": k, "qtd_apresentada": round(v[0], 2), "qtd_aprovada": round(v[1], 2), "valor_apresentado": round(v[2], 2), "valor_aprovado": round(v[3], 2)} for k, v in t],
            "financiamento": [{"codigo": k, "qtd": round(v[0], 2), "valor_aprovado": round(v[1], 2)} for k, v in sorted(d["financ"].items())],
            "avisos": aviso}


def processar_uf(uf, cnes_set, meses):
    nomes = H.listar(H.PASTA_SIA, "PA" + uf)
    comps = H.competencias_recentes(nomes, "PA", uf, meses)
    if not comps:
        raise H.ErroColeta(f"nenhum arquivo PA{uf} encontrado no FTP")
    rx = {c: re.compile(rf"^PA{uf}{c}[a-z]?\.dbc$", re.I) for c in comps}
    for comp in comps:
        partes = sorted(n for n in nomes if rx[comp].match(n))
        tams = {n: H.tamanho_remoto(H.PASTA_SIA, n) for n in partes}
        chave = f"SIA/{'|'.join(partes)}/{','.join(sorted(cnes_set))}"
        total = sum(tams.values())
        if H.ja_processado(chave, total):
            print(f"{uf} {comp}: sem mudanca, pulando", flush=True); continue
        acum, aviso, arquivos = None, [], {}
        for n in partes:
            with H.baixar(H.PASTA_SIA, n, tams[n]) as dados:
                ler, ausentes, _ = H.campos_presentes(dados, DESEJADOS, ["PA_CODUNI", "PA_PROC_ID", "PA_VALAPR"])
                if ausentes:
                    aviso.append(f"{n} sem os campos: {ausentes}")
                acum, l = agregar_pa(dbc.registros(dados, ler), cnes_set, acum)
                arquivos[n] = {"registros_lidos": l}
        for c in sorted(cnes_set):
            bloco = montar_bloco(acum[c], arquivos, sorted(set(aviso)))
            H.atualizar_hospital(c, H.aamm_para_chave(comp), "sia", bloco)
            print(f"{uf} {comp} CNES {c}: linhas={bloco['linhas']} valor_aprovado={bloco['valor_aprovado']}", flush=True)
        H.marcar_processado(chave, total)


def sondar():
    nomes = H.listar(H.PASTA_SIA, "PAAP")
    comp = H.competencias_recentes(nomes, "PA", "AP", 1)
    if not comp:
        print("PA sem arquivo AP"); return
    n = sorted(x for x in nomes if re.match(rf"^PAAP{comp[0]}[a-z]?\.dbc$", x, re.I))[0]
    with H.baixar(H.PASTA_SIA, n) as dados:
        cab = dbc.cabecalho(dados)
        print("PA", n, "registros", cab["registros"], "campos", [c[0] for c in cab["campos"]], flush=True)


def main():
    if "--sondar" in sys.argv:
        sondar(); return 0
    cfg = H.carregar_config()
    if not cfg["hospitais"]:
        print("nenhum CNES valido em config/hospitais.json: nada a coletar"); return 0
    falhas = {}
    for uf, cnes_set in sorted(H.por_uf(cfg["hospitais"]).items()):
        try:
            processar_uf(uf, cnes_set, cfg["meses"])
        except Exception as e:
            falhas[uf] = f"{type(e).__name__}: {str(e)[:200]}"; print("FALHA", uf, falhas[uf], flush=True)
    H.atualizar_indice(cfg["hospitais"])
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
