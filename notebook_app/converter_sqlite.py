#!/usr/bin/env python3
"""Converte os DBC baixados (RDES, SPES, PAES) em uma base SQLite agregada, bem menor que os arquivos originais.

Privacidade: le somente colunas de uma lista fixa (abaixo) e grava SOMA por hospital, competencia e procedimento.
Nunca le numero da AIH, nascimento, CEP, municipio de residencia, sexo, idade, raca, CPF, CNS, numero de autorizacao,
nota fiscal ou documento de profissional. A lista e conferida contra hospital_comum.PROIBIDOS.
Base: <BASE>/base/producao_es.sqlite. Reprocessar um arquivo substitui as linhas dele (idempotente).
Uso: converter_sqlite.py [--so ARQUIVO.dbc] [--resumo] [--limpar-dias N]
"""
import fcntl, os, re, sqlite3, sys, time
from datetime import datetime

AQUI = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("PARTELLI_BASE", os.path.join(os.path.expanduser("~"), "partelli"))
for p in (os.path.join(AQUI, "..", "robo"), os.path.join(BASE, "sala-gestao", "robo")):
    if os.path.isdir(p):
        sys.path.insert(0, os.path.abspath(p))
import dbc
import hospital_comum as H
from comum import numero_br

ORIGEM = os.environ.get("PAINEL_DOWNLOADS", os.path.join(BASE, "ftp_downloads"))
BANCO = os.environ.get("PARTELLI_BANCO", os.path.join(BASE, "base", "producao_es.sqlite"))
FLUSH = 50000

# nome da tabela -> (prefixo do arquivo, dimensoes [(coluna, campo DBC)], medidas [(coluna, campo DBC, tipo)], medida de controle)
# tipo: "v" valor em R$ (somado em centavos), "i" inteiro
TABELAS = {
    "rd": ("RDES",
           [("cnes", "CNES"), ("ano", "ANO_CMPT"), ("mes", "MES_CMPT"), ("proc_rea", "PROC_REA"), ("diag_princ", "DIAG_PRINC"),
            ("espec", "ESPEC"), ("car_int", "CAR_INT"), ("complex", "COMPLEX"), ("financ", "FINANC"), ("munic_mov", "MUNIC_MOV")],
           [("val_sh", "VAL_SH", "v"), ("val_sp", "VAL_SP", "v"), ("val_tot", "VAL_TOT", "v"), ("dias_perm", "DIAS_PERM", "i"),
            ("qt_diarias", "QT_DIARIAS", "i"), ("uti_dias", "UTI_MES_TO", "i"), ("mortes", "MORTE", "i")], "val_tot"),
    "sp": ("SPES",
           [("cnes", "SP_CNES"), ("ano", "SP_AA"), ("mes", "SP_MM"), ("proc_rea", "SP_PROCREA"), ("ato_prof", "SP_ATOPROF"),
            ("tp_ato", "SP_TP_ATO"), ("cbo", "SP_PF_CBO"), ("complex", "SP_COMPLEX"), ("financ", "SP_FINANC")],
           [("qtd_ato", "SP_QTD_ATO", "i"), ("val_ato", "SP_VALATO", "v")], "val_ato"),
    # CNES, habilitacoes (HB): uma linha por habilitacao do estabelecimento na competencia. Sem CPF_CNPJ, CNPJ_MAN, COD_CEP.
    "hb": ("HBES",
           [("cnes", "CNES"), ("codufmun", "CODUFMUN"), ("sgruphab", "SGRUPHAB"), ("cmpt_ini", "CMPT_INI"), ("cmpt_fim", "CMPT_FIM"),
            ("dtportar", "DTPORTAR"), ("portaria", "PORTARIA"), ("maportar", "MAPORTAR"), ("competen", "COMPETEN"), ("tp_unid", "TP_UNID"),
            ("vinc_sus", "VINC_SUS"), ("esfera_a", "ESFERA_A"), ("nat_jur", "NAT_JUR")],
           [("nuleitos", "NULEITOS", "i")], "nuleitos"),
    # CIHA: sem campo de valor. Sem CNPJ do hospital/consorcio, nascimento, sexo, idade, municipio de residencia, datas de atendimento e saida.
    "ciha": ("CIHA",
             [("cnes", "CNES"), ("ano", "ANO_CMPT"), ("mes", "MES_CMPT"), ("proc_rea", "PROC_REA"), ("diag_princ", "DIAG_PRINC"),
              ("espec", "ESPEC"), ("car_int", "CAR_INT"), ("natureza", "NATUREZA"), ("gestao", "GESTAO"), ("modalidade", "MODALIDADE"),
              ("munic_mov", "MUNIC_MOV")],
             [("qt_proc", "QT_PROC", "i"), ("dias_perm", "DIAS_PERM", "i"), ("uti_dias", "UTI_MES_TO", "i"), ("mortes", "MORTE", "i")], "qt_proc"),
    "pa": ("PAES",
           [("cnes", "PA_CODUNI"), ("mvm", "PA_MVM"), ("cmp", "PA_CMP"), ("proc_id", "PA_PROC_ID"), ("cbo", "PA_CBOCOD"),
            ("tpfin", "PA_TPFIN"), ("subfin", "PA_SUBFIN"), ("nivcpl", "PA_NIVCPL"), ("ufmun", "PA_UFMUN")],
           [("qtd_pro", "PA_QTDPRO", "i"), ("qtd_apr", "PA_QTDAPR", "i"), ("val_pro", "PA_VALPRO", "v"), ("val_apr", "PA_VALAPR", "v")], "val_apr"),
}
NUNCA = set(H.PROIBIDOS) | {"CGC_HOSP", "CGC_CONSOR", "MUNIC_RES", "SEXO", "IDADE", "COD_IDADE", "RACA_COR", "DT_ATEND", "DT_SAIDA",
                            "HOMONIMO", "NACIONAL", "CPF_AUT", "SP_NAIH", "SP_PF_DOC"}
for _t, (_p, _d, _m, _c) in TABELAS.items():   # trava: nenhuma coluna proibida na lista
    _usados = {c for _, c in _d} | {c for _, c, _ in _m}
    assert not (_usados & NUNCA), f"coluna proibida em {_t}: {_usados & NUNCA}"


def abrir_banco(caminho=None):
    caminho = caminho or BANCO
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    con = sqlite3.connect(caminho)
    con.execute("PRAGMA synchronous=NORMAL")
    con.execute("CREATE TABLE IF NOT EXISTS arquivos (nome TEXT PRIMARY KEY, tabela TEXT, tamanho INTEGER, linhas INTEGER, grupos INTEGER, "
                "valor_controle REAL, convertido_em TEXT)")
    for t, (_, dims, meds, _c) in TABELAS.items():
        cols = ["arquivo TEXT NOT NULL"] + [f"{c} TEXT NOT NULL" for c, _ in dims] + ["n_linhas INTEGER NOT NULL"] + \
               [f"{c} {'REAL' if tp == 'v' else 'INTEGER'} NOT NULL" for c, _, tp in meds]
        pk = ", ".join(["arquivo"] + [c for c, _ in dims])
        con.execute(f"CREATE TABLE IF NOT EXISTS {t} ({', '.join(cols)}, PRIMARY KEY ({pk})) WITHOUT ROWID")
    return con


def _inteiro(v):
    return int(numero_br(v))


def converter_arquivo(con, caminho, nome=None):
    nome = nome or os.path.basename(caminho)
    prefixo = nome[:4].upper()
    tabela = next((t for t, d in TABELAS.items() if d[0] == prefixo), None)
    if not tabela:
        raise ValueError(f"tipo de arquivo nao previsto: {nome}")
    _, dims, meds, controle = TABELAS[tabela]
    campos = [c for _, c in dims] + [c for _, c, _ in meds]
    nd, nm = len(dims), len(meds)
    tipos = [tp for _, _, tp in meds]
    cols_dim = [c for c, _ in dims]
    cols_med = [c for c, _, _ in meds]
    sql = (f"INSERT INTO {tabela} (arquivo, {', '.join(cols_dim)}, n_linhas, {', '.join(cols_med)}) VALUES ({', '.join('?' * (1 + nd + 1 + nm))}) "
           f"ON CONFLICT(arquivo, {', '.join(cols_dim)}) DO UPDATE SET n_linhas=n_linhas+excluded.n_linhas, " +
           ", ".join(f"{c}={c}+excluded.{c}" for c in cols_med))
    with open(caminho, "rb") as a:
        dados = a.read()
    con.execute("BEGIN")
    try:
        con.execute(f"DELETE FROM {tabela} WHERE arquivo=?", (nome,))
        con.execute("DELETE FROM arquivos WHERE nome=?", (nome,))
        acc, lidas, ctrl_cent = {}, 0, 0
        idx_ctrl = cols_med.index(controle)
        esc = 100 if tipos[idx_ctrl] == "v" else 1     # valor em centavos ou contagem inteira

        def descarregar():
            lote = []
            for chave, v in acc.items():
                medidas = [x / 100 if tipos[i] == "v" else x for i, x in enumerate(v[1:])]
                lote.append((nome, *chave, v[0], *medidas))
            con.executemany(sql, lote)
            acc.clear()

        for r in dbc.registros(dados, campos):
            chave = tuple(r[c] for c in campos[:nd])
            v = acc.get(chave)
            if v is None:
                v = acc[chave] = [0] + [0] * nm
            v[0] += 1
            for i in range(nm):
                val = r[campos[nd + i]]
                x = round(numero_br(val) * 100) if tipos[i] == "v" else _inteiro(val)
                v[1 + i] += x
                if i == idx_ctrl:
                    ctrl_cent += x
            lidas += 1
            if len(acc) >= FLUSH:
                descarregar()
        descarregar()
        n_db, soma = con.execute(f"SELECT COALESCE(SUM(n_linhas),0), COALESCE(SUM({controle}),0) FROM {tabela} WHERE arquivo=?", (nome,)).fetchone()
        if n_db != lidas or abs(soma - ctrl_cent / esc) > 0.5:
            raise RuntimeError(f"conferencia falhou em {nome}: linhas {lidas} x {n_db}, valor {ctrl_cent / esc:.2f} x {soma:.2f}")
        vals = [c for c, _, tp in meds if tp == "v"]
        if vals:   # HB e CIHA nao tem valor em R$
            con.execute(f"UPDATE {tabela} SET " + ", ".join(f"{c}=ROUND({c},2)" for c in vals) + " WHERE arquivo=?", (nome,))
        grupos = con.execute(f"SELECT COUNT(*) FROM {tabela} WHERE arquivo=?", (nome,)).fetchone()[0]
        con.execute("INSERT INTO arquivos VALUES (?,?,?,?,?,?,?)",
                    (nome, tabela, len(dados), lidas, grupos, round(ctrl_cent / esc, 2), datetime.now().isoformat(timespec="seconds")))
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    return {"nome": nome, "tabela": tabela, "linhas": lidas, "grupos": grupos, "valor": ctrl_cent / esc, "bytes": len(dados)}


def pendentes(con, pasta=None):
    pasta = pasta or ORIGEM
    feitos = dict(con.execute("SELECT nome, tamanho FROM arquivos"))
    rx = re.compile(r"^(RDES|SPES|PAES|HBES|CIHAES)\d{4}\.dbc$", re.I)
    saida = []
    for n in sorted(os.listdir(pasta)) if os.path.isdir(pasta) else []:
        p = os.path.join(pasta, n)
        if rx.match(n) and os.path.isfile(p) and feitos.get(n) != os.path.getsize(p):
            saida.append(p)
    return saida


def resumo(con):
    for t, (_, dims, meds, controle) in TABELAS.items():
        print(f"== {t}: valor de controle = {controle}")
        for nome, linhas, grupos, valor in con.execute("SELECT nome, linhas, grupos, valor_controle FROM arquivos WHERE tabela=? ORDER BY nome", (t,)):
            print(f"{nome:14} {linhas:>9} linhas -> {grupos:>7} grupos   R$ {valor:>16,.2f}")


def main(argv):
    os.makedirs(BASE, exist_ok=True)
    trava = open(os.path.join(BASE, ".lock_conversao"), "w")
    try:
        fcntl.flock(trava, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("[conversao] outra conversao em andamento, saindo")
        return 0
    con = abrir_banco()
    if "--resumo" in argv:
        resumo(con)
        return 0
    if "--so" in argv:
        fila = [os.path.join(ORIGEM, argv[argv.index("--so") + 1])]
    else:
        fila = pendentes(con)
    print(f"[conversao] {len(fila)} arquivo(s) a converter")
    erros = 0
    for caminho in fila:
        t0 = time.time()
        try:
            r = converter_arquivo(con, caminho)
            print(f"[conversao] {r['nome']}: {r['linhas']} linhas -> {r['grupos']} grupos, {r['bytes'] / 1e6:.1f} MB lidos, {time.time() - t0:.0f}s", flush=True)
        except Exception as e:
            erros += 1
            print(f"[conversao] ERRO {os.path.basename(caminho)}: {e}", flush=True)
    if "--limpar-dias" in argv:
        dias = int(argv[argv.index("--limpar-dias") + 1])
        feitos = dict(con.execute("SELECT nome, tamanho FROM arquivos"))
        for n, tam in feitos.items():
            p = os.path.join(ORIGEM, n)
            if os.path.isfile(p) and os.path.getsize(p) == tam and time.time() - os.path.getmtime(p) > dias * 86400:
                os.remove(p)
                print(f"[conversao] bruto removido ({dias} dias): {n}")
    con.execute("PRAGMA optimize")
    con.close()
    print(f"[conversao] fim, base: {os.path.getsize(BANCO) / 1e6:.1f} MB, erros: {erros}")
    return 1 if erros else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
