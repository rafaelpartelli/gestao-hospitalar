#!/usr/bin/env python3
"""Producao hospitalar (SIH/SUS) por CNES configurado, a partir do FTP do DATASUS.
Arquivos: RD (AIH aprovadas), RJ (AIH rejeitadas) e ER (erros de rejeicao). Somente agregados: nenhum numero de AIH,
paciente, CID por pessoa ou data de nascimento e gravado. O numero da AIH e usado so em memoria para ligar RJ e ER.
Saida: <PARTELLI_DADOS>/<CNES>.json, bloco competencias.<AAAAMM>.sih.
Layouts dos arquivos nao confirmados em campo: use primeiro 'python3 coletar_hospital_sih.py --sondar'.
Status da fonte: Em teste ate a primeira execucao validada."""
import sys
import dbc
import hospital_comum as H
from comum import numero_br, agora
from hospital_calc_py import capitulo_cid

TOP = 40
RD_DESEJADOS = ["CNES", "PROC_REA", "VAL_SH", "VAL_SP", "VAL_TOT", "DIAS_PERM", "MORTE", "DIAG_PRINC", "ESPEC"]
RJ_DESEJADOS = ["CNES", "CNES_ESTAB", "VAL_TOT", "N_AIH"]
ER_CODIGO = ("CODERR", "COD_ERRO", "CD_ERRO", "ERRO", "ERR_COD")
ER_DESEJADOS = ["CNES", "N_AIH", *ER_CODIGO]


def novo():
    return {"aprovadas": 0, "valor_aprovado": 0.0, "sh": 0.0, "sp": 0.0, "dias_perm": 0, "obitos": 0,
            "aih_sem_sh": 0, "aih_sem_sp": 0, "aih_sh_sp_divergente": 0,
            "proc": {}, "cap": {}, "esp": {}}


def agregar_rd(registros, cnes_set):
    por = {c: novo() for c in cnes_set}
    lidos = 0
    for r in registros:
        lidos += 1
        c = (r.get("CNES") or "").strip()
        if c not in por:
            continue
        d = por[c]
        tot, sh, sp = numero_br(r.get("VAL_TOT")), numero_br(r.get("VAL_SH")), numero_br(r.get("VAL_SP"))
        d["aprovadas"] += 1
        d["valor_aprovado"] += tot; d["sh"] += sh; d["sp"] += sp
        d["dias_perm"] += int(numero_br(r.get("DIAS_PERM")))
        if (r.get("MORTE") or "").strip() == "1":
            d["obitos"] += 1
        if sh <= 0 < tot:
            d["aih_sem_sh"] += 1
        if sp <= 0 < tot:
            d["aih_sem_sp"] += 1
        if abs(sh + sp - tot) > 0.01:
            d["aih_sh_sp_divergente"] += 1
        proc = (r.get("PROC_REA") or "").strip()
        if proc:
            a = d["proc"].setdefault(proc, [0, 0.0, 0.0, 0.0])
            a[0] += 1; a[1] += tot; a[2] += sh; a[3] += sp
        cap = capitulo_cid(r.get("DIAG_PRINC"))
        if cap:
            a = d["cap"].setdefault(cap, [0, 0.0]); a[0] += 1; a[1] += tot
        esp = (r.get("ESPEC") or "").strip()
        if esp:
            a = d["esp"].setdefault(esp, [0, 0.0]); a[0] += 1; a[1] += tot
    return por, lidos


def agregar_rj(registros, cnes_set, campo_cnes="CNES"):
    por = {c: {"rejeitadas": 0, "valor_rejeitado": 0.0, "tem_valor": False} for c in cnes_set}
    naih = {}  # so em memoria, para ligar o ER
    lidos = 0
    for r in registros:
        lidos += 1
        c = (r.get(campo_cnes) or "").strip()
        if c not in por:
            continue
        d = por[c]
        d["rejeitadas"] += 1
        if r.get("VAL_TOT") not in (None, ""):
            d["valor_rejeitado"] += numero_br(r.get("VAL_TOT")); d["tem_valor"] = True
        if r.get("N_AIH"):
            naih[r["N_AIH"].strip()] = c
    return por, naih, lidos


def agregar_er(registros, cnes_set, campo_codigo, naih_para_cnes=None):
    por = {c: {} for c in cnes_set}
    lidos = 0
    for r in registros:
        lidos += 1
        c = (r.get("CNES") or "").strip() or (naih_para_cnes or {}).get((r.get("N_AIH") or "").strip(), "")
        if c not in por:
            continue
        cod = (r.get(campo_codigo) or "").strip()
        if cod:
            por[c][cod] = por[c].get(cod, 0) + 1
    return por, lidos


def top(dic, n=TOP, chave=1):
    return sorted(dic.items(), key=lambda kv: kv[1][chave], reverse=True)[:n]


def montar_bloco(rd, rj, er, arquivos, aviso):
    b = {"fonte": "SIH/SUS, FTP do DATASUS (arquivos RD, RJ e ER)", "coletado_em": agora(), "arquivos": arquivos, "status_fonte": "Em teste",
         "aprovadas": rd["aprovadas"], "valor_aprovado": round(rd["valor_aprovado"], 2), "sh": round(rd["sh"], 2), "sp": round(rd["sp"], 2),
         "dias_perm": rd["dias_perm"], "obitos": rd["obitos"],
         "aih_sem_sh": rd["aih_sem_sh"], "aih_sem_sp": rd["aih_sem_sp"], "aih_sh_sp_divergente": rd["aih_sh_sp_divergente"],
         "enviadas": None, "nao_processadas": None,
         "procedimentos": [{"codigo": k, "qtd": v[0], "valor": round(v[1], 2), "sh": round(v[2], 2), "sp": round(v[3], 2)} for k, v in top(rd["proc"])],
         "capitulos": [{"capitulo": k, "qtd": v[0], "valor": round(v[1], 2)} for k, v in top(rd["cap"], 30)],
         "especialidades": [{"codigo": k, "qtd": v[0], "valor": round(v[1], 2)} for k, v in top(rd["esp"], 30)],
         "avisos": aviso}
    if rj is not None:
        b["rejeitadas"] = rj["rejeitadas"]
        b["valor_rejeitado"] = round(rj["valor_rejeitado"], 2) if rj["tem_valor"] else None
    else:
        b["rejeitadas"] = None; b["valor_rejeitado"] = None
    b["erros_rejeicao"] = ([{"codigo": k, "qtd": v} for k, v in sorted(er.items(), key=lambda kv: -kv[1])[:20]] if er is not None else None)
    return b


def processar_uf(uf, cnes_set, meses):
    nomes = H.listar(H.PASTA_SIH, "RD" + uf)
    comps = H.competencias_recentes(nomes, "RD", uf, meses)
    if not comps:
        raise H.ErroColeta(f"nenhum arquivo RD{uf} encontrado no FTP")
    for comp in comps:
        aviso, arquivos = [], {}
        nome_rd = f"RD{uf}{comp}.dbc"
        tam = H.tamanho_remoto(H.PASTA_SIH, nome_rd)
        chave = f"SIH/{nome_rd}/{','.join(sorted(cnes_set))}"
        if H.ja_processado(chave, tam):
            print(f"{uf} {comp}: sem mudanca, pulando", flush=True)
            continue
        with H.baixar(H.PASTA_SIH, nome_rd, tam) as dados:
            ler, ausentes, _ = H.campos_presentes(dados, RD_DESEJADOS, ["CNES", "VAL_TOT"])
            rd, lidos = agregar_rd(dbc.registros(dados, ler), cnes_set)
            if ausentes:
                aviso.append(f"RD sem os campos: {ausentes}")
        arquivos["RD"] = {"nome": nome_rd, "registros_lidos": lidos}
        rj = er = None
        nome_rj = f"RJ{uf}{comp}.dbc"
        if nome_rj in H.listar(H.PASTA_SIH, "RJ" + uf):
            with H.baixar(H.PASTA_SIH, nome_rj) as dados:
                nomes_arq = {c[0] for c in dbc.cabecalho(dados)["campos"]}
                campo_cnes = H.primeiro_campo(nomes_arq, ("CNES", "CNES_ESTAB"))
                if campo_cnes:
                    ler, aus, _ = H.campos_presentes(dados, [campo_cnes, "VAL_TOT", "N_AIH"], [campo_cnes], transitorios=("N_AIH",))
                    rj, naih, l = agregar_rj(dbc.registros(dados, ler), cnes_set, campo_cnes)
                    arquivos["RJ"] = {"nome": nome_rj, "registros_lidos": l}
                else:
                    naih = {}
                    aviso.append("RJ sem campo de CNES: rejeitadas devem ser lancadas do SIHD")
            nome_er = f"ER{uf}{comp}.dbc"
            if nome_er in H.listar(H.PASTA_SIH, "ER" + uf):
                with H.baixar(H.PASTA_SIH, nome_er) as dados:
                    nomes_arq = {c[0] for c in dbc.cabecalho(dados)["campos"]}
                    campo_cod = H.primeiro_campo(nomes_arq, ER_CODIGO)
                    if campo_cod:
                        ler, aus, _ = H.campos_presentes(dados, ["CNES", "N_AIH", campo_cod], [campo_cod], transitorios=("N_AIH",))
                        er, l = agregar_er(dbc.registros(dados, ler), cnes_set, campo_cod, naih)
                        arquivos["ER"] = {"nome": nome_er, "registros_lidos": l}
                    else:
                        aviso.append("ER sem campo de codigo de erro reconhecido: lancar motivos do SIHD")
            else:
                aviso.append("arquivo ER nao encontrado para a competencia")
        else:
            aviso.append("arquivo RJ nao encontrado para a competencia: rejeitadas devem ser lancadas do SIHD")
        for c in sorted(cnes_set):
            bloco = montar_bloco(rd[c], rj[c] if rj else None, er[c] if er else None, arquivos, aviso)
            H.atualizar_hospital(c, H.aamm_para_chave(comp), "sih", bloco)
            print(f"{uf} {comp} CNES {c}: aprovadas={bloco['aprovadas']} rejeitadas={bloco['rejeitadas']}", flush=True)
        H.marcar_processado(chave, tam)


def sondar():
    """Baixa o menor arquivo de cada tipo (UF pequena) e imprime so os nomes dos campos."""
    for pref in ("RD", "RJ", "ER"):
        nomes = H.listar(H.PASTA_SIH, pref + "AP")
        comp = H.competencias_recentes(nomes, pref, "AP", 1)
        if not comp:
            print(pref, "sem arquivo AP"); continue
        with H.baixar(H.PASTA_SIH, f"{pref}AP{comp[0]}.dbc") as dados:
            cab = dbc.cabecalho(dados)
            print(pref, comp[0], "registros", cab["registros"], "campos", [c[0] for c in cab["campos"]], flush=True)


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
