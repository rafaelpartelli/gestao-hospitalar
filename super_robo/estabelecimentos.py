"""Producao por estabelecimento (CNES) do municipio: ambulatorio (SIA aprovado), internacoes (SIH), CIHA e profissionais (CNES PF).
Somente agregados por codigo CNES. Nunca nome de profissional, CPF, CNS, CNPJ, endereco, telefone ou e-mail. Nome do estabelecimento NAO vem daqui:
fica em rede_nomes_cnes.json (coletor proprio, sujeito a filtro de pessoa fisica)."""
import sqlite3

TOP_PROC = 5
TOP_CBO = 8
MAX_ESTAB = 300


def _tem(con, t):
    return con.execute("SELECT 1 FROM sqlite_master WHERE name=?", (t,)).fetchone() is not None


def _comp_pf(con, c6):
    r = con.execute("SELECT MAX(competen) FROM pf WHERE codufmun=?", (c6,)).fetchone()
    return r[0] if r else None


def montar(banco, cod):
    """Devolve {'fonte', 'estabelecimentos': [{cnes, tipo_unidade, sih, sia, ciha, profissionais}]} ou {'situacao': ...}."""
    c6 = cod[:6]
    try:
        con = sqlite3.connect(banco)
    except sqlite3.Error:
        return {"situacao": "A confirmar: base SQLite nao encontrada"}
    try:
        e = {}
        def ficha(c):
            return e.setdefault(c, {"cnes": c, "tipo_unidade": None, "sih": [], "sia": {"por_mes": [], "principais_procedimentos": []}, "ciha": [], "profissionais": None})
        if _tem(con, "st"):
            comp = con.execute("SELECT MAX(competen) FROM st WHERE codufmun=?", (c6,)).fetchone()[0]
            for c, t in con.execute("SELECT DISTINCT cnes, tp_unid FROM st WHERE codufmun=? AND competen=?", (c6, comp)):
                ficha(c)["tipo_unidade"] = t
        if _tem(con, "rd"):
            for c, a, m, n, v, o, d in con.execute("SELECT cnes, ano, mes, SUM(n_linhas), SUM(val_tot), SUM(mortes), SUM(dias_perm) FROM rd WHERE munic_mov=? GROUP BY cnes, ano, mes ORDER BY cnes, ano, mes", (c6,)):
                ficha(c)["sih"].append({"competencia": f"{m}/{a}", "aih": n, "valor_total": round(v or 0, 2), "obitos": o, "dias_permanencia": d})
        if _tem(con, "pa"):
            for c, mv, q, v in con.execute("SELECT cnes, mvm, SUM(qtd_apr), SUM(val_apr) FROM pa WHERE ufmun=? GROUP BY cnes, mvm ORDER BY cnes, mvm", (c6,)):
                ficha(c)["sia"]["por_mes"].append({"mes_processamento": f"{mv[4:]}/{mv[:4]}", "quantidade_aprovada": q, "valor_aprovado": round(v or 0, 2)})
            for c, p, q, v in con.execute("SELECT cnes, proc_id, SUM(qtd_apr), SUM(val_apr) FROM pa WHERE ufmun=? GROUP BY cnes, proc_id ORDER BY cnes, SUM(val_apr) DESC", (c6,)):
                lst = ficha(c)["sia"]["principais_procedimentos"]
                if len(lst) < TOP_PROC:
                    lst.append({"procedimento": p, "quantidade_aprovada": q, "valor_aprovado": round(v or 0, 2)})
        if _tem(con, "ciha"):
            for c, a, m, n, q, d, o in con.execute("SELECT cnes, ano, mes, SUM(n_linhas), SUM(qt_proc), SUM(dias_perm), SUM(mortes) FROM ciha WHERE munic_mov=? GROUP BY cnes, ano, mes ORDER BY cnes, ano, mes", (c6,)):
                ficha(c)["ciha"].append({"competencia": f"{m}/{a}", "registros": n, "quantidade_procedimentos": q, "dias_permanencia": d, "obitos": o})
        if _tem(con, "pf"):
            comp = _comp_pf(con, c6)
            if comp:
                for c, n, a, h, o in con.execute("SELECT cnes, SUM(n_linhas), SUM(hora_amb), SUM(horahosp), SUM(horaoutr) FROM pf WHERE codufmun=? AND competen=? GROUP BY cnes", (c6, comp)):
                    ficha(c)["profissionais"] = {"competencia": comp, "vinculos": n, "horas_ambulatoriais": a, "horas_hospitalares": h, "horas_outras": o, "principais_cbo": []}
                for c, b, n, a, h, o in con.execute("SELECT cnes, cbo, SUM(n_linhas), SUM(hora_amb), SUM(horahosp), SUM(horaoutr) FROM pf WHERE codufmun=? AND competen=? GROUP BY cnes, cbo ORDER BY cnes, SUM(n_linhas) DESC", (c6, comp)):
                    p = ficha(c)["profissionais"]
                    if p and len(p["principais_cbo"]) < TOP_CBO:
                        p["principais_cbo"].append({"cbo": b, "vinculos": n, "horas_ambulatoriais": a, "horas_hospitalares": h, "horas_outras": o})
        if _tem(con, "er") and e:
            for c in list(e):  # ER nao tem municipio: filtra pelos CNES do municipio (por RD, SIA, CIHA, PF ou ST)
                for ano, m, n in con.execute("SELECT ano, mes, SUM(n_linhas) FROM er WHERE cnes=? GROUP BY ano, mes", (c,)):
                    comp = f"{m}/{ano}"
                    x = next((y for y in e[c]["sih"] if y["competencia"] == comp), None)
                    if x is None:
                        x = {"competencia": comp, "aih": 0, "valor_total": 0, "obitos": 0, "dias_permanencia": 0}; e[c]["sih"].append(x)
                    x["rejeitadas"] = n
        def peso(f):
            return sum(x["valor_total"] for x in f["sih"]) + sum(x["valor_aprovado"] for x in f["sia"]["por_mes"])
        lista = [f for f in e.values() if f["sih"] or f["sia"]["por_mes"] or f["ciha"] or f["profissionais"]]
        lista.sort(key=lambda f: (-peso(f), f["cnes"]))
        if not lista:
            return {"situacao": "A confirmar: sem producao ou profissionais por estabelecimento na base"}
        return {"fonte": "SIH, SIA (aprovado), CIHA e CNES PF, agregados por CNES na base local", "total": len(lista), "truncado": len(lista) > MAX_ESTAB,
                "obs": "Contagem de vinculos, nao de pessoas. Sem nome de profissional ou qualquer dado de identificacao.", "estabelecimentos": lista[:MAX_ESTAB]}
    finally:
        con.close()
