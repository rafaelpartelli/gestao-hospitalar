"""Visao por hospital no dossie do municipio: cadastro do CNES (ST, LT, EQ, PF, HB, IN, SR) cruzado com a producao (SIH, SIA aprovado, CIHA).

Tudo calculado a partir da base SQLite agregada. Sem meta inventada, sem comparacao com referencia externa. Indicadores derivados trazem a
formula e a base usada. Criticas seguem o formato da plataforma (codigo, descricao, severidade, origem, acao, status). Ocupacao e uma
ESTIMATIVA (AIH aprovadas SUS e leitos SUS do cadastro), nao substitui o censo hospitalar."""
import calendar, os, sqlite3

RESP = "A definir pelo gestor"


def _tem(con, t):
    return bool(con.execute("SELECT name FROM sqlite_master WHERE name=?", (t,)).fetchone())


def _um(con, sql, args=()):
    r = con.execute(sql, args).fetchone()
    return r if r is not None else (None,)


def _maxc(con, t):
    return _um(con, f"SELECT MAX(competen) FROM {t}")[0] if _tem(con, t) else None


def _cnes_do_municipio(con, c6):
    """CNES com AIH (MUNIC_MOV), com CIHA ou com leito cadastrado no ST, no municipio."""
    s = set()
    s |= {r[0] for r in con.execute("SELECT DISTINCT cnes FROM rd WHERE munic_mov=?", (c6,))} if _tem(con, "rd") else set()
    s |= {r[0] for r in con.execute("SELECT DISTINCT cnes FROM ciha WHERE munic_mov=?", (c6,))} if _tem(con, "ciha") else set()
    cst = _maxc(con, "st")
    if cst:
        s |= {r[0] for r in con.execute("SELECT cnes FROM st WHERE codufmun=? AND competen=? AND (qtleitp1+qtleitp2+qtleitp3)>0", (c6, cst))}
    return sorted(s)


def _cadastro(con, cnes):
    out = {}
    cst = _maxc(con, "st")
    if cst:
        r = con.execute("SELECT tp_unid, natureza, nat_jur, esfera_a, tpgestao, qtleitp1, qtleitp2, qtleitp3 FROM st WHERE cnes=? AND competen=?", (cnes, cst)).fetchone()
        if r:
            out["estabelecimento"] = {"competencia": f"{cst[4:]}/{cst[:4]}", "tipo_unidade": r[0], "natureza": r[1], "natureza_juridica": r[2],
                                      "esfera": r[3], "gestao": r[4], "leitos_p1_p2_p3": [r[5], r[6], r[7]]}
    clt = _maxc(con, "lt")
    if clt:
        e, s, n = con.execute("SELECT COALESCE(SUM(qt_exist),0), COALESCE(SUM(qt_sus),0), COALESCE(SUM(qt_nsus),0) FROM lt WHERE cnes=? AND competen=?", (cnes, clt)).fetchone()
        out["leitos"] = {"competencia": f"{clt[4:]}/{clt[:4]}", "existentes": e, "sus": s, "nao_sus": n}
    ceq = _maxc(con, "eq")
    if ceq:
        e, u = con.execute("SELECT COALESCE(SUM(qt_exist),0), COALESCE(SUM(qt_uso),0) FROM eq WHERE cnes=? AND competen=?", (cnes, ceq)).fetchone()
        out["equipamentos"] = {"competencia": f"{ceq[4:]}/{ceq[:4]}", "existentes": e, "em_uso": u,
                               "pct_em_uso": round(u / e * 100, 1) if e else None}
    cpf = _maxc(con, "pf")
    if cpf:
        v, a, h = con.execute("SELECT COALESCE(SUM(n_linhas),0), COALESCE(SUM(hora_amb),0), COALESCE(SUM(horahosp),0) FROM pf WHERE cnes=? AND competen=?", (cnes, cpf)).fetchone()
        out["profissionais"] = {"competencia": f"{cpf[4:]}/{cpf[:4]}", "vinculos": v, "horas_ambulatoriais": a, "horas_hospitalares": h}
    chb = _maxc(con, "hb")
    if chb:
        out["habilitacoes"] = {"competencia": f"{chb[4:]}/{chb[:4]}", "total": con.execute("SELECT COUNT(*) FROM hb WHERE cnes=? AND competen=?", (cnes, chb)).fetchone()[0],
                               "codigos": [r[0] for r in con.execute("SELECT DISTINCT sgruphab FROM hb WHERE cnes=? AND competen=? ORDER BY sgruphab", (cnes, chb))]}
    cin = _maxc(con, "inc")
    if cin:
        out["incentivos"] = {"competencia": f"{cin[4:]}/{cin[:4]}", "total": con.execute("SELECT COUNT(*) FROM inc WHERE cnes=? AND competen=?", (cnes, cin)).fetchone()[0]}
    csr = _maxc(con, "sr")
    if csr:
        out["servicos_especializados"] = {"competencia": f"{csr[4:]}/{csr[:4]}", "total": con.execute(
            "SELECT COUNT(*) FROM (SELECT DISTINCT serv_esp, class_sr FROM sr WHERE cnes=? AND competen=?)", (cnes, csr)).fetchone()[0]}
    return out


def _producao(con, cnes):
    sih = [{"competencia": f"{m}/{a}", "aih": n, "valor_total": round(t, 2), "sh": round(sh, 2), "sp": round(sp, 2), "dias_permanencia": d, "obitos": mo, "dias_uti": u}
           for a, m, n, t, sh, sp, d, mo, u in con.execute(
               "SELECT ano, mes, SUM(n_linhas), SUM(val_tot), SUM(val_sh), SUM(val_sp), SUM(dias_perm), SUM(mortes), SUM(uti_dias) FROM rd WHERE cnes=? GROUP BY ano, mes ORDER BY ano, mes", (cnes,))] if _tem(con, "rd") else []
    sia = [{"mes_processamento": f"{m[4:]}/{m[:4]}", "quantidade_aprovada": q, "valor_aprovado": round(v, 2)} for m, q, v in con.execute(
        "SELECT mvm, SUM(qtd_apr), SUM(val_apr) FROM pa WHERE cnes=? GROUP BY mvm ORDER BY mvm", (cnes,))] if _tem(con, "pa") else []
    ciha = [{"competencia": f"{m}/{a}", "registros": n, "quantidade_procedimentos": q} for a, m, n, q in con.execute(
        "SELECT ano, mes, SUM(n_linhas), SUM(qt_proc) FROM ciha WHERE cnes=? GROUP BY ano, mes ORDER BY ano, mes", (cnes,))] if _tem(con, "ciha") else []
    return sih, sia, ciha


def _indicadores(sih, leitos_sus):
    if not sih:
        return None
    aih = sum(x["aih"] for x in sih)
    tot = round(sum(x["valor_total"] for x in sih), 2)
    dias = sum(x["dias_permanencia"] for x in sih)
    obitos = sum(x["obitos"] for x in sih)
    meses = len(sih)
    dias_calendario = sum(calendar.monthrange(int(x["competencia"][3:]), int(x["competencia"][:2]))[1] for x in sih)
    ind = {"meses_com_producao": meses, "aih": aih, "valor_total": tot,
           "media_por_aih": round(tot / aih, 2) if aih else None,
           "permanencia_media_dias": round(dias / aih, 2) if aih else None,
           "mortalidade_hospitalar_pct": round(obitos / aih * 100, 2) if aih else None,
           "formulas": "media = valor total / AIH; permanencia = dias de permanencia / AIH; mortalidade = obitos / AIH x 100"}
    if leitos_sus:
        ind["aih_por_leito_sus_por_mes"] = round(aih / meses / leitos_sus, 2)
        ind["ocupacao_estimada_pct"] = round(dias / (leitos_sus * dias_calendario) * 100, 1)
        ind["obs_ocupacao"] = ("Estimativa: dias de permanencia das AIH aprovadas (SIH) dividido por leitos SUS do cadastro vezes dias do periodo. "
                               "Nao substitui o censo hospitalar. Leitos SUS da competencia mais recente do CNES.")
    return ind


def _criticas(cnes, cad, sih, ind):
    c = []

    def add(cod, desc, sev, origem, acao, status="Aberta"):
        c.append({"codigo": f"{cod}-{cnes}", "descricao": desc, "severidade": sev, "origem": origem, "acao_recomendada": acao,
                  "responsavel": RESP, "prazo": RESP, "status": status})
    aih = ind["aih"] if ind else 0
    ex = (cad.get("leitos") or {}).get("existentes")
    if aih and not ex:
        add("C01", "CNES com AIH aprovadas e sem leito existente no cadastro (arquivo LT).", "Alta", "CNES",
            "Conferir o cadastro de leitos do estabelecimento no CNES e atualizar, se divergente.")
    for x in sih:
        if abs(x["sh"] + x["sp"] - x["valor_total"]) > 0.5:
            add("C02", f"SH mais SP diferente do valor total em {x['competencia']}.", "Alta", "AIH",
                "Reconferir os valores da competencia no SIH antes de usar o total.")
            break
    if len(sih) >= 2:
        meses = sorted((int(x["competencia"][3:]), int(x["competencia"][:2])) for x in sih)
        todos = {(a, m) for a, m in meses}
        falta = []
        a, m = meses[0]
        while (a, m) <= meses[-1]:
            if (a, m) not in todos:
                falta.append(f"{m:02d}/{a}")
            m += 1
            if m > 12:
                a, m = a + 1, 1
        if falta:
            add("C03", f"Competencia sem producao hospitalar entre meses com producao: {', '.join(falta)}.", "Media", "AIH",
                "Verificar se houve suspensao, atraso de envio ou rejeicao integral.", "A verificar")
    if aih and (cad.get("habilitacoes") or {}).get("total") == 0:
        add("C04", "Hospital com AIH aprovadas e sem habilitacao registrada no CNES (arquivo HB).", "Media", "CNES",
            "Conferir se os procedimentos faturados exigem habilitacao e se ha portaria vigente.", "A verificar")
    if ind and ind.get("ocupacao_estimada_pct") and ind["ocupacao_estimada_pct"] > 100:
        add("C05", f"Ocupacao estimada de {ind['ocupacao_estimada_pct']}% (acima de 100%): leitos SUS do cadastro podem estar subestimados.", "Media", "CNES",
            "Conferir leitos SUS no CNES e a permanencia registrada nas AIH.", "A verificar")
    return c


def visao_hospitais(banco, c6):
    if not os.path.isfile(banco):
        return "[PREENCHER: base SQLite nao encontrada]"
    con = sqlite3.connect(banco)
    try:
        lista = _cnes_do_municipio(con, c6)
        if not lista:
            return {"situacao": "A confirmar: nenhum hospital com AIH, CIHA ou leito cadastrado do municipio na base de 2026",
                    "obs": "Ausencia de registro nao e erro de leitura. Conferir no CNES."}
        itens = []
        for cnes in lista:
            cad = _cadastro(con, cnes)
            sih, sia, ciha = _producao(con, cnes)
            ind = _indicadores(sih, (cad.get("leitos") or {}).get("sus"))
            itens.append({"cnes": cnes, "cadastro": cad,
                          "producao": {"sih_por_mes": sih, "sia_aprovado_por_mes": sia, "ciha_por_mes": ciha,
                                       "sia_aprovado_total": {"quantidade": sum(x["quantidade_aprovada"] for x in sia), "valor": round(sum(x["valor_aprovado"] for x in sia), 2)} if sia else None},
                          "indicadores": ind, "criticas": _criticas(cnes, cad, sih, ind)})
        sev = {"Alta": 0, "Media": 0, "Baixa": 0}
        for h in itens:
            for k in h["criticas"]:
                sev[k["severidade"]] += 1
        return {"fonte": "Base local: SIH (RD, SP), SIA aprovado (PA), CIHA, CNES (ST, LT, EQ, PF, HB, IN, SR)", "total": len(itens),
                "criticas_por_severidade": sev, "itens": itens,
                "obs": "SIH e SIA de 2026 ate o ultimo mes disponivel no FTP; cadastro CNES na competencia mais recente de cada grupo."}
    finally:
        con.close()
