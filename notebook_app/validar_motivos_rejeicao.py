#!/usr/bin/env python3
"""Validacao por dado publico da correspondencia provavel dos codigos de rejeicao (sem depender de relatorio do hospital).

Ideia: para as AIH rejeitadas (ER) que reapareceram aprovadas (RD) em competencia posterior, compara as datas reais da AIH com o texto do motivo.
Se o motivo provavel do codigo for "data da saida maior que a data de apresentacao", quase todas as AIH daquele codigo devem ter DT_SAIDA depois do
ultimo dia da competencia da rejeicao, e os demais codigos nao. A leitura e feita so em memoria: numero da AIH e datas NAO sao gravados nem impressos.
Saida: tabela por codigo com contagens e percentuais. Percentual alto no codigo certo e baixo nos demais e indicio (nao prova) da correspondencia.
Uso: validar_motivos_rejeicao.py [CNES ...]   (sem CNES: todos os do ES)"""
import os, re, sys
AQUI = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("PARTELLI_BASE", os.path.join(os.path.expanduser("~"), "partelli"))
for p in (os.path.join(AQUI, "..", "robo"), os.path.join(BASE, "sala-gestao", "robo")):
    if os.path.isdir(p):
        sys.path.insert(0, os.path.abspath(p))
import dbc
import converter_sqlite as K
from reconciliar_rejeicoes import _arquivos


def _meses(a, b):
    """Meses entre duas datas AAAAMMDD (b - a), ou None se invalida."""
    if not (re.fullmatch(r"\d{8}", a or "") and re.fullmatch(r"\d{8}", b or "")):
        return None
    return (int(b[:4]) - int(a[:4])) * 12 + int(b[4:6]) - int(a[4:6])


def sinais(dt_inter, dt_saida, comp):
    """Sinais objetivos das datas de uma AIH frente a competencia da rejeicao (AAAAMM). Sem sinal quando a data e invalida."""
    s = {}
    if re.fullmatch(r"\d{8}", dt_saida or ""):
        s["saida_apos_competencia"] = dt_saida[:6] > comp
        s["saida_6m_antes"] = _meses(dt_saida, comp + "01") is not None and _meses(dt_saida, comp + "01") > 6
    if re.fullmatch(r"\d{8}", dt_inter or "") and re.fullmatch(r"\d{8}", dt_saida or ""):
        s["inter_apos_saida"] = dt_inter > dt_saida
    return s


def destino(aprovacoes, comp):
    """Onde a AIH rejeitada na competencia comp foi aprovada: 'mesma', 'anterior', 'posterior' (a mais proxima) ou 'nunca' (nao esta no RD do mesmo CNES)."""
    comps = sorted(x[0] for x in aprovacoes)
    if not comps:
        return "nunca"
    if comp in comps:
        return "mesma"
    post = [c for c in comps if c > comp]
    return "posterior" if post else "anterior"


def validar(pasta=None, cnes_filtro=None):
    pasta = pasta or K.ORIGEM
    rd = {}
    for caminho in _arquivos(pasta, r"^RDES\d{4}\.dbc$"):
        with open(caminho, "rb") as a:
            dados = a.read()
        for r in dbc.registros(dados, ["CNES", "N_AIH", "ANO_CMPT", "MES_CMPT", "DT_INTER", "DT_SAIDA"]):
            c = r["CNES"].strip()
            if cnes_filtro and c not in cnes_filtro:
                continue
            rd.setdefault((c, r["N_AIH"].strip()), []).append((r["ANO_CMPT"].strip() + r["MES_CMPT"].strip(), r["DT_INTER"].strip(), r["DT_SAIDA"].strip()))
    acc = {}
    for caminho in _arquivos(pasta, r"^ERES\d{4}\.dbc$"):
        with open(caminho, "rb") as a:
            dados = a.read()
        for r in dbc.registros(dados, ["CNES", "AIH", "ANO", "MES", "CO_ERRO"]):
            c = r["CNES"].strip()
            if cnes_filtro and c not in cnes_filtro:
                continue
            comp = r["ANO"].strip() + r["MES"].strip()
            v = acc.setdefault(r["CO_ERRO"].strip(), {"rejeitadas": 0, "casadas": 0, "saida_apos_competencia": [0, 0], "saida_6m_antes": [0, 0], "inter_apos_saida": [0, 0], "destino": {"mesma": 0, "anterior": 0, "posterior": 0, "nunca": 0}})
            v["rejeitadas"] += 1
            v["destino"][destino(rd.get((c, r["AIH"].strip()), []), comp)] += 1
            post = sorted(x for x in rd.get((c, r["AIH"].strip()), []) if x[0] > comp)
            if not post:
                continue
            v["casadas"] += 1
            for k, val in sinais(post[0][1], post[0][2], comp).items():
                v[k][1] += 1
                v[k][0] += 1 if val else 0
    return acc


def main(argv):
    acc = validar(cnes_filtro=set(argv[1:]) or None)
    top = sorted(acc.items(), key=lambda kv: -kv[1]["rejeitadas"])[:20]
    print("DESTINO da AIH rejeitada (mesmo CNES, numero igual no RD): % aprovada na MESMA competencia | % so em competencia ANTERIOR | % POSTERIOR | % NUNCA aprovada")
    for cod, v in top:
        d, t = v["destino"], v["rejeitadas"]
        print(cod, t, *[f"{round(d[k] / t * 100, 1)}%" for k in ("mesma", "anterior", "posterior", "nunca")], sep=" | ")
    print()
    print("codigo | rejeitadas | casadas c/ aprovacao posterior | % saida apos a competencia | % saida 6+ meses antes | % internacao apos saida")
    for cod, v in top:
        def p(k):
            n, t = v[k]
            return f"{round(n / t * 100, 1)}% (n={t})" if t else "sem dado"
        print(cod, v["rejeitadas"], v["casadas"], p("saida_apos_competencia"), p("saida_6m_antes"), p("inter_apos_saida"), sep=" | ")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
