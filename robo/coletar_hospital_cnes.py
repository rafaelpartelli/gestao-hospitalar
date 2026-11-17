#!/usr/bin/env python3
"""CNES do estabelecimento configurado (FTP do DATASUS): tipo de unidade (ST), leitos (LT), servicos especializados (SR),
habilitacoes (HB) e profissionais por grupo de CBO (PF). Somente agregados e codigos. Nunca le nome, CPF, CNS, CNPJ, endereco, telefone ou e-mail.
Equivale, para a unidade, ao que o ElastiCNES mostra por tipo_estabelecimento, sem depender daquele painel.
Saida: <PARTELLI_DADOS>/<CNES>.json, bloco cnes. Status da fonte: Em teste."""
import sys
import dbc
import hospital_comum as H
from comum import numero_br, agora

ST = ["CNES", "TP_UNID", "NAT_JUR", "ESFERA_A", "NIV_HIER", "ATIVIDAD", "CLIENTEL", "TURNO_AT", "TPGESTAO", "VINC_SUS", "RETENCAO", "CODUFMUN"]
LT = ["CNES", "TP_LEITO", "CODLEITO", "QT_EXIST", "QT_CONTR", "QT_SUS", "QT_NSUS"]
SR = ["CNES", "SERV_ESP", "CLASS_SR", "SRVUNICO", "AMB_SUS", "HOSP_SUS"]
HB = ["CNES", "SGRUPHAB", "CODHAB", "PORTARIA", "DTPORTAR", "MAPORTAR", "DTPORT", "COMPETEN"]
PF = ["CNES", "CBO", "PROF_SUS", "HORA_AMB", "HORAOUTR", "HORAHOSP"]
GRUPOS_CBO = [("Médicos", ("2251", "2252", "2253", "2231")), ("Enfermeiros", ("2235",)), ("Técnicos e auxiliares de enfermagem", ("3222",)),
              ("Cirurgiões-dentistas", ("2232",)), ("Farmacêuticos", ("2234",)), ("Psicólogos", ("2515",)), ("Fisioterapeutas", ("2236",)),
              ("Nutricionistas", ("2237",)), ("Assistentes sociais", ("2516",)), ("Fonoaudiólogos e terapeutas ocupacionais", ("2238", "2239"))]


def grupo_cbo(cbo):
    c = (cbo or "").strip()
    for nome, pref in GRUPOS_CBO:
        if c.startswith(pref):
            return nome
    return "Outros"


def coletar_tipo(tipo, uf, comp, cnes_set, desejados, obrig, reduzir):
    """Baixa o arquivo do tipo e devolve {cnes: resultado} e avisos. 'reduzir' recebe (registro) e devolve None ou dado."""
    nome = f"{tipo}{uf}{comp}.dbc"
    pasta = f"{H.PASTA_CNES}/{tipo}"
    if nome not in H.listar(pasta, tipo + uf):
        return None, [f"arquivo {nome} nao encontrado"], nome
    out = {c: [] for c in cnes_set}
    with H.baixar(pasta, nome) as dados:
        ler, ausentes, _ = H.campos_presentes(dados, desejados, obrig)
        for r in dbc.registros(dados, ler):
            c = (r.get("CNES") or "").strip()
            if c in out:
                out[c].append(r)
    return out, ([f"{nome} sem os campos: {ausentes}"] if ausentes else []), nome


def resumir_leitos(regs):
    por = {}
    for r in regs:
        k = (r.get("TP_LEITO") or "").strip() + "/" + (r.get("CODLEITO") or "").strip()
        a = por.setdefault(k, [0, 0, 0])
        a[0] += int(numero_br(r.get("QT_EXIST"))); a[1] += int(numero_br(r.get("QT_SUS"))); a[2] += int(numero_br(r.get("QT_CONTR")))
    linhas = [{"tp_leito": k.split("/")[0], "cod_leito": k.split("/")[1], "existentes": v[0], "sus": v[1], "contratados": v[2]} for k, v in sorted(por.items())]
    return {"itens": linhas, "total_existentes": sum(l["existentes"] for l in linhas), "total_sus": sum(l["sus"] for l in linhas)}


def resumir_servicos(regs):
    vistos, itens = set(), []
    for r in regs:
        k = ((r.get("SERV_ESP") or "").strip(), (r.get("CLASS_SR") or "").strip())
        if k not in vistos:
            vistos.add(k); itens.append({"servico": k[0], "classificacao": k[1]})
    return {"itens": sorted(itens, key=lambda x: (x["servico"], x["classificacao"]))}


def resumir_habilitacoes(regs):
    vistos, itens = set(), []
    for r in regs:
        item = {k.lower(): (r.get(k) or "").strip() for k in ("SGRUPHAB", "CODHAB", "PORTARIA", "DTPORTAR", "DTPORT", "MAPORTAR", "COMPETEN") if k in r}
        chave = tuple(sorted(item.items()))
        if chave not in vistos:
            vistos.add(chave); itens.append(item)
    return {"itens": itens}


def resumir_profissionais(regs):
    por = {}
    for r in regs:
        g = por.setdefault(grupo_cbo(r.get("CBO")), [0, 0, 0])
        g[0] += 1
        g[1] += 1 if (r.get("PROF_SUS") or "").strip() == "1" else 0
        g[2] += int(numero_br(r.get("HORA_AMB")) + numero_br(r.get("HORAOUTR")) + numero_br(r.get("HORAHOSP")))
    return {"unidade": "vinculos profissionais (nao pessoas); horas semanais somam ambulatorial, hospitalar e outras",
            "grupos": [{"grupo": k, "vinculos": v[0], "vinculos_sus": v[1], "horas_semanais": v[2]} for k, v in sorted(por.items())],
            "total_vinculos": sum(v[0] for v in por.values())}


def processar_uf(uf, cnes_set):
    nomes = H.listar(H.PASTA_CNES + "/ST", "ST" + uf)
    comps = H.competencias_recentes(nomes, "ST", uf, 1)
    if not comps:
        raise H.ErroColeta(f"nenhum arquivo ST{uf} no FTP do CNES")
    comp = comps[0]
    blocos = {c: {"competencia_cnes": H.aamm_para_mmaaaa(comp), "fonte": "CNES, arquivos ST, LT, SR, HB e PF do FTP do DATASUS", "coletado_em": agora(),
                  "status_fonte": "Em teste", "avisos": []} for c in cnes_set}
    plano = [("ST", ST, ["CNES", "TP_UNID"], lambda regs: ({k: (regs[0].get(k) or "").strip() for k in ST if k in regs[0] and k != "CNES"} if regs else None), "estabelecimento"),
             ("LT", LT, ["CNES", "QT_EXIST"], resumir_leitos, "leitos"),
             ("SR", SR, ["CNES", "SERV_ESP"], resumir_servicos, "servicos"),
             ("HB", HB, ["CNES"], resumir_habilitacoes, "habilitacoes"),
             ("PF", PF, ["CNES", "CBO"], resumir_profissionais, "profissionais")]
    for tipo, desej, obrig, reduzir, chave in plano:
        try:
            out, avisos, nome = coletar_tipo(tipo, uf, comp, cnes_set, desej, obrig, reduzir)
        except Exception as e:
            for c in cnes_set:
                blocos[c]["avisos"].append(f"{tipo}: {type(e).__name__}: {str(e)[:160]}")
            continue
        for c in cnes_set:
            blocos[c]["avisos"] += avisos
            if out is not None:
                blocos[c][chave] = reduzir(out[c]) if out[c] or tipo != "ST" else None
    for c in sorted(cnes_set):
        H.atualizar_hospital(c, None, "cnes", blocos[c])
        print(f"{uf} CNES {c}: competencia {comp}, avisos={len(blocos[c]['avisos'])}", flush=True)


def sondar():
    for tipo in ("ST", "LT", "SR", "HB", "PF"):
        pasta = f"{H.PASTA_CNES}/{tipo}"
        comp = H.competencias_recentes(H.listar(pasta, tipo + "AP"), tipo, "AP", 1)
        if not comp:
            print(tipo, "sem arquivo AP"); continue
        with H.baixar(pasta, f"{tipo}AP{comp[0]}.dbc") as dados:
            cab = dbc.cabecalho(dados)
            print(tipo, comp[0], "registros", cab["registros"], "campos", [c[0] for c in cab["campos"]], flush=True)


def main():
    if "--sondar" in sys.argv:
        sondar(); return 0
    cfg = H.carregar_config()
    if not cfg["hospitais"]:
        print("nenhum CNES valido em config/hospitais.json: nada a coletar"); return 0
    falhas = {}
    for uf, cnes_set in sorted(H.por_uf(cfg["hospitais"]).items()):
        try:
            processar_uf(uf, cnes_set)
        except Exception as e:
            falhas[uf] = f"{type(e).__name__}: {str(e)[:200]}"; print("FALHA", uf, falhas[uf], flush=True)
    H.atualizar_indice(cfg["hospitais"])
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
