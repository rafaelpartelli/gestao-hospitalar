#!/usr/bin/env python3
"""Conferencia de reapresentacao: das AIH rejeitadas (ER), quantas foram aprovadas depois (RD).

Privacidade: o numero da AIH e lido SOMENTE em memoria, para casar rejeitada com aprovada, e nunca e gravado. A base recebe apenas
contagens e valor somado por CNES, competencia da rejeicao e codigo de erro (tabela rejeicao_rec, refeita a cada execucao).
Regra: a AIH conta como recuperada se o mesmo numero, no mesmo CNES, aparece aprovado no RD em competencia POSTERIOR a da rejeicao.
Aprovacao na mesma competencia ou anterior nao conta. Rejeicao da competencia mais recente fica "em aberto" (ainda pode ser reapresentada).
Uso: reconciliar_rejeicoes.py"""
import fcntl, os, re, sqlite3, sys
from datetime import datetime

AQUI = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("PARTELLI_BASE", os.path.join(os.path.expanduser("~"), "partelli"))
for p in (os.path.join(AQUI, "..", "robo"), os.path.join(BASE, "sala-gestao", "robo")):
    if os.path.isdir(p):
        sys.path.insert(0, os.path.abspath(p))
import dbc
from comum import numero_br
import converter_sqlite as K

TRANSITORIOS = {"AIH", "N_AIH"}      # lidos so em memoria
COLUNAS_GRAVADAS = ["cnes", "ano", "mes", "co_erro", "rejeitadas", "recuperadas", "valor_recuperado", "calculado_em"]


def _arquivos(pasta, rx):
    r = re.compile(rx, re.I)
    return [os.path.join(pasta, n) for n in sorted(os.listdir(pasta)) if r.match(n)] if os.path.isdir(pasta) else []


def aprovadas_rd(pasta):
    """(cnes, numero da AIH) -> lista de (competencia AAAAMM, valor em centavos). Fica so em memoria."""
    mapa = {}
    for caminho in _arquivos(pasta, r"^RDES\d{4}\.dbc$"):
        with open(caminho, "rb") as a:
            dados = a.read()
        for r in dbc.registros(dados, ["CNES", "N_AIH", "ANO_CMPT", "MES_CMPT", "VAL_TOT"]):
            mapa.setdefault((r["CNES"].strip(), r["N_AIH"].strip()), []).append((r["ANO_CMPT"].strip() + r["MES_CMPT"].strip(), round(numero_br(r["VAL_TOT"]) * 100)))
    return mapa


def reconciliar(con, pasta=None):
    pasta = pasta or K.ORIGEM
    rd = aprovadas_rd(pasta)
    acc, lidas = {}, 0
    for caminho in _arquivos(pasta, r"^ERES\d{4}\.dbc$"):
        with open(caminho, "rb") as a:
            dados = a.read()
        for r in dbc.registros(dados, ["CNES", "AIH", "ANO", "MES", "CO_ERRO"]):
            cnes, ano, mes = r["CNES"].strip(), r["ANO"].strip(), r["MES"].strip()
            comp = ano + mes
            posteriores = sorted(x for x in rd.get((cnes, r["AIH"].strip()), []) if x[0] > comp)
            v = acc.setdefault((cnes, ano, mes, r["CO_ERRO"].strip()), [0, 0, 0])
            v[0] += 1
            if posteriores:
                v[1] += 1
                v[2] += posteriores[0][1]      # valor da primeira aprovacao posterior
            lidas += 1
    agora = datetime.now().isoformat(timespec="seconds")
    con.execute("CREATE TABLE IF NOT EXISTS rejeicao_rec (cnes TEXT NOT NULL, ano TEXT NOT NULL, mes TEXT NOT NULL, co_erro TEXT NOT NULL, "
                "rejeitadas INTEGER NOT NULL, recuperadas INTEGER NOT NULL, valor_recuperado REAL NOT NULL, calculado_em TEXT NOT NULL, "
                "PRIMARY KEY (cnes, ano, mes, co_erro)) WITHOUT ROWID")
    con.execute("BEGIN")
    try:
        con.execute("DELETE FROM rejeicao_rec")
        con.executemany("INSERT INTO rejeicao_rec VALUES (?,?,?,?,?,?,?,?)",
                        [(*k, v[0], v[1], round(v[2] / 100, 2), agora) for k, v in acc.items()])
        n = con.execute("SELECT COALESCE(SUM(rejeitadas),0) FROM rejeicao_rec").fetchone()[0]
        if n != lidas:
            raise RuntimeError(f"conferencia falhou: rejeitadas lidas {lidas}, gravadas {n}")
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    rec = con.execute("SELECT COALESCE(SUM(recuperadas),0) FROM rejeicao_rec").fetchone()[0]
    return {"rejeitadas": lidas, "recuperadas": rec, "grupos": len(acc)}


def main(argv):
    os.makedirs(K.BASE, exist_ok=True)
    trava = open(os.path.join(K.BASE, ".lock_conversao"), "w")
    try:
        fcntl.flock(trava, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("[reconciliacao] outra conversao em andamento, saindo")
        return 0
    con = K.abrir_banco()
    if not _arquivos(K.ORIGEM, r"^ERES\d{4}\.dbc$"):
        print("[reconciliacao] sem arquivos ER, nada a fazer")
        return 0
    try:
        r = reconciliar(con)
    except Exception as e:
        print(f"[reconciliacao] ERRO: {e}")
        return 1
    pct = round(r["recuperadas"] / r["rejeitadas"] * 100, 1) if r["rejeitadas"] else 0
    print(f"[reconciliacao] {r['rejeitadas']} AIH rejeitadas, {r['recuperadas']} aprovadas depois ({pct}%), {r['grupos']} grupos gravados")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
