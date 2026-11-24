#!/usr/bin/env python3
"""Conferencia por hospital a partir da base SQLite agregada: producao mensal SIH (RD e SP) e SIA (PA).
Serve para comparar com o TabNet/DATASUS antes de usar os numeros. Uso: conferir_hospital.py [CNES ...]
Sem argumento, usa os hospitais autorizados em config/hospitais.json. Somente agregados, sem dado de pessoa."""
import os, re, sqlite3, sys
AQUI = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("PARTELLI_BASE", os.path.join(os.path.expanduser("~"), "partelli"))
BANCO = os.environ.get("PARTELLI_BANCO", os.path.join(BASE, "base", "producao_es.sqlite"))
CONFIG = os.environ.get("PARTELLI_CONFIG", os.path.join(AQUI, "..", "config"))


def brl(v):
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def hospitais(args):
    if args:
        return [(a, "") for a in args if re.fullmatch(r"\d{7}", a)]
    import json
    with open(os.path.join(CONFIG, "hospitais.json"), encoding="utf-8") as f:
        return [(h["cnes"], h.get("nome", "")) for h in json.load(f)["hospitais"] if h.get("autorizado")]


def relatorio(con, cnes):
    saida = []
    saida.append("SIH, AIH reduzida (RD): competencia | AIHs | valor total | SH | SP | media por AIH | obitos | dias de permanencia medios")
    for ano, mes, n, tot, sh, sp, mort, dias in con.execute(
            "SELECT ano, mes, SUM(n_linhas), SUM(val_tot), SUM(val_sh), SUM(val_sp), SUM(mortes), SUM(dias_perm) FROM rd WHERE cnes=? GROUP BY ano, mes ORDER BY ano, mes", (cnes,)):
        saida.append(f"  {mes}/{ano} | {n:>5} | {brl(tot):>16} | {brl(sh):>16} | {brl(sp):>16} | {brl(tot / n):>12} | {mort:>3} | {dias / n:.1f}")
    saida.append("SIH, servicos profissionais (SP): competencia | atos | valor")
    for ano, mes, q, v in con.execute("SELECT ano, mes, SUM(qtd_ato), SUM(val_ato) FROM sp WHERE cnes=? GROUP BY ano, mes ORDER BY ano, mes", (cnes,)):
        saida.append(f"  {mes}/{ano} | {q:>7} | {brl(v):>16}")
    saida.append("SIA, ambulatorial (PA): mes de processamento | quantidade apresentada | quantidade aprovada | valor aprovado")
    for mvm, qp, qa, va in con.execute("SELECT mvm, SUM(qtd_pro), SUM(qtd_apr), SUM(val_apr) FROM pa WHERE cnes=? GROUP BY mvm ORDER BY mvm", (cnes,)):
        saida.append(f"  {mvm[4:]}/{mvm[:4]} | {qp:>9} | {qa:>9} | {brl(va):>16}")
    return saida


def main(argv):
    if not os.path.isfile(BANCO):
        print("base nao encontrada: rode converter_sqlite.py")
        return 1
    con = sqlite3.connect(BANCO)
    for cnes, nome in hospitais(argv):
        print(f"\n=== CNES {cnes} {nome}")
        print("\n".join(relatorio(con, cnes)))
    print("\nConferir contra o TabNet (SIH: producao hospitalar por estabelecimento; SIA: producao ambulatorial) na mesma competencia.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
