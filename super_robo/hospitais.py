"""Visao por hospital no dossie do municipio: cadastro do CNES (ST, LT, EQ, PF, HB, IN, SR) cruzado com a producao (SIH, SIA aprovado, CIHA).

Tudo calculado a partir da base SQLite agregada. Sem meta inventada, sem comparacao com referencia externa. Indicadores derivados trazem a
formula e a base usada. Criticas seguem o formato da plataforma (codigo, descricao, severidade, origem, acao, status). Ocupacao e uma
ESTIMATIVA (AIH aprovadas SUS e leitos SUS do cadastro), nao substitui o censo hospitalar."""
import calendar, os, sqlite3
import plano_acoes as PA

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
    sih = [{"competencia": f"{m}/{a}", "aih": n, "valor_total": round(t, 2), "sh": round(sh, 2), "sp": round(sp, 2), "sh_fed": round(shf, 2), "sp_fed": round(spf, 2),
            "dias_permanencia": d, "obitos": mo, "dias_uti": u}
           for a, m, n, t, sh, sp, shf, spf, d, mo, u in con.execute(
               "SELECT ano, mes, SUM(n_linhas), SUM(val_tot), SUM(val_sh), SUM(val_sp), SUM(val_sh_fed), SUM(val_sp_fed), SUM(dias_perm), SUM(mortes), SUM(uti_dias) FROM rd WHERE cnes=? GROUP BY ano, mes ORDER BY ano, mes", (cnes,))] if _tem(con, "rd") else []
    sia = [{"mes_processamento": f"{m[4:]}/{m[:4]}", "quantidade_aprovada": q, "valor_aprovado": round(v, 2)} for m, q, v in con.execute(
        "SELECT mvm, SUM(qtd_apr), SUM(val_apr) FROM pa WHERE cnes=? GROUP BY mvm ORDER BY mvm", (cnes,))] if _tem(con, "pa") else []
    ciha = [{"competencia": f"{m}/{a}", "registros": n, "quantidade_procedimentos": q} for a, m, n, q in con.execute(
        "SELECT ano, mes, SUM(n_linhas), SUM(qt_proc) FROM ciha WHERE cnes=? GROUP BY ano, mes ORDER BY ano, mes", (cnes,))] if _tem(con, "ciha") else []
    return sih, sia, ciha


def _ocupacao_mensal(sih, leitos_sus):
    """Taxa de ocupacao estimada por mes: dias de permanencia das AIH aprovadas / (leitos SUS x dias do mes) x 100."""
    if not leitos_sus:
        return
    for x in sih:
        dias_mes = calendar.monthrange(int(x["competencia"][3:]), int(x["competencia"][:2]))[1]
        x["ocupacao_estimada_pct"] = round(x["dias_permanencia"] / (leitos_sus * dias_mes) * 100, 1)


def _recuperacao(con, cnes, sih):
    """AIH rejeitadas que reapareceram aprovadas em competencia posterior (tabela rejeicao_rec, gerada por reconciliar_rejeicoes.py).
    A competencia mais recente da base fica 'em aberto': a AIH ainda pode ser reapresentada."""
    if not _tem(con, "rejeicao_rec"):
        return {"situacao": "A confirmar: conferencia de reapresentacao ainda nao executada (rode reconciliar_rejeicoes.py)"}
    ultima = _um(con, "SELECT MAX(ano || mes) FROM rd")[0] if _tem(con, "rd") else None
    linhas = con.execute("SELECT ano, mes, co_erro, rejeitadas, recuperadas, valor_recuperado FROM rejeicao_rec WHERE cnes=?", (cnes,)).fetchall()
    if not linhas:
        return {"situacao": "A confirmar: nenhuma rejeicao do hospital na conferencia de reapresentacao"}
    fech = [x for x in linhas if ultima and (x[0] + x[1]) < ultima]
    aberta = [x for x in linhas if not ultima or (x[0] + x[1]) >= ultima]
    rf, cf = sum(x[3] for x in fech), sum(x[4] for x in fech)
    nao = rf - cf
    media = round(sum(x["valor_total"] for x in sih) / sum(x["aih"] for x in sih), 2) if sih and sum(x["aih"] for x in sih) else None
    por_cod = {}
    for _, _, e, r, k, _v in fech:
        a = por_cod.setdefault(e, [0, 0])
        a[0] += r
        a[1] += k
    out = {"competencia_em_aberto": f"{ultima[4:]}/{ultima[:4]}" if ultima else None,
           "rejeitadas_em_aberto": sum(x[3] for x in aberta),
           "rejeitadas_fechadas": rf, "recuperadas": cf, "nao_recuperadas": nao,
           "pct_recuperadas": round(cf / rf * 100, 1) if rf else None,
           "valor_recuperado": round(sum(x[5] for x in fech), 2),
           "por_codigo_erro": [{"codigo_erro": e, "rejeitadas": r, "recuperadas": k, "nao_recuperadas": r - k,
                                "pct_recuperadas": round(k / r * 100, 1) if r else None}
                               for e, (r, k) in sorted(por_cod.items(), key=lambda kv: -kv[1][0])[:5]],
           "regra": "AIH recuperada: mesmo numero e mesmo CNES aprovado no SIH em competencia posterior a da rejeicao. O numero da AIH nao e gravado.",
           "base": "Rejeicoes de competencias anteriores a mais recente da base."}
    if media is not None and nao:
        out["perda_liquida_estimada_rs"] = round(nao * media, 2)
        out["obs_perda"] = ("ESTIMATIVA: AIH nao recuperadas x media por AIH aprovada do hospital no periodo. O arquivo ER nao traz valor. "
                            "Nao e resultado apurado.")
    return out


def _rejeicao(con, cnes, sih):
    """AIH rejeitadas (arquivo ER) por mes e percentual sobre AIH aprovadas mais rejeitadas. O arquivo ER nao traz valor em R$."""
    if not _tem(con, "er"):
        return None
    rej = {f"{m}/{a}": n for a, m, n in con.execute("SELECT ano, mes, SUM(n_linhas) FROM er WHERE cnes=? GROUP BY ano, mes", (cnes,))}
    if not rej:
        return {"situacao": "A confirmar: nenhuma AIH rejeitada do hospital na base de 2026"}
    apr = {x["competencia"]: x["aih"] for x in sih}
    meses = []
    for comp in sorted(set(rej) | set(apr), key=lambda k: (k[3:], k[:2])):
        r, a = rej.get(comp, 0), apr.get(comp, 0)
        meses.append({"competencia": comp, "aprovadas": a, "rejeitadas": r, "pct_rejeicao": round(r / (a + r) * 100, 2) if (a + r) else None})
    rec = _recuperacao(con, cnes, sih)
    tr, ta = sum(m["rejeitadas"] for m in meses), sum(m["aprovadas"] for m in meses)
    erros = [{"codigo_erro": e, "aih": n} for e, n in con.execute(
        "SELECT co_erro, SUM(n_linhas) FROM er WHERE cnes=? GROUP BY co_erro ORDER BY SUM(n_linhas) DESC LIMIT 5", (cnes,))]
    return {"total_rejeitadas": tr, "total_aprovadas": ta, "pct_rejeicao_periodo": round(tr / (ta + tr) * 100, 2) if (ta + tr) else None,
            "por_mes": meses, "principais_codigos_erro": erros, "reapresentacao": rec,
            "formula": "rejeitadas / (aprovadas + rejeitadas) x 100, por contagem de AIH",
            "obs": "O arquivo ER nao tem valor em R$: perda em R$ fica a apurar. Uma AIH rejeitada pode ser reapresentada e aprovada em competencia seguinte. "
                   "Descricao do codigo de erro depende de tabela auxiliar nao carregada."}


def _indicadores(sih, leitos_sus, leitos_exist=None):
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
    if leitos_exist:
        ind["ocupacao_estimada_leitos_existentes_pct"] = round(dias / (leitos_exist * dias_calendario) * 100, 1)
    if leitos_sus:
        ind["aih_por_leito_sus_por_mes"] = round(aih / meses / leitos_sus, 2)
        ind["ocupacao_estimada_pct"] = round(dias / (leitos_sus * dias_calendario) * 100, 1)
        ind["obs_ocupacao"] = ("Estimativa: dias de permanencia das AIH aprovadas (SIH) dividido por leitos SUS do cadastro vezes dias do periodo. "
                               "Nao substitui o censo hospitalar. Leitos SUS da competencia mais recente do CNES. Tambem calculada sobre leitos existentes.")
    return ind


def _criticas(cnes, cad, sih, ind, rec=None):
    c = []

    def add(cod, desc, sev, origem, acao, status="Aberta"):
        c.append({"codigo": f"{cod}-{cnes}", "descricao": desc, "severidade": sev, "origem": origem, "acao_recomendada": acao,
                  "responsavel": RESP, "prazo": RESP, "status": status})
    aih = (ind or {}).get("aih", 0)
    ex = (cad.get("leitos") or {}).get("existentes")
    if aih and not ex:
        add("C01", "CNES com AIH aprovadas e sem leito existente no cadastro (arquivo LT).", "Alta", "CNES",
            "Conferir o cadastro de leitos do estabelecimento no CNES e atualizar, se divergente.")
    for x in sih:
        if abs(x["sh"] + x["sp"] + x.get("sh_fed", 0) + x.get("sp_fed", 0) - x["valor_total"]) > 0.5:
            add("C02", f"SH + SP (com os complementos federais SH_FED e SP_FED, quando existem) diferente do valor total em {x['competencia']}.", "Alta", "AIH",
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
    st = (cad.get("estabelecimento") or {}).get("leitos_p1_p2_p3")
    if ex and st and sum(st) > 0 and sum(st) != ex:
        add("C06", f"Leitos existentes no arquivo LT ({ex}) diferem da soma P1+P2+P3 do cadastro do estabelecimento ({sum(st)}).", "Media", "CNES",
            "Conferir os leitos no CNES; a ocupacao estimada depende desse denominador.", "A verificar")
    if isinstance(rec, dict) and rec.get("rejeitadas_fechadas"):
        for x in rec.get("por_codigo_erro", []):
            nao, tot, pct = x["nao_recuperadas"], x["rejeitadas"], x["pct_recuperadas"]
            if nao > 0:
                sev = "Alta" if (nao >= 5 and pct is not None and pct < 50) else "Media"
                add(f"C07-{x['codigo_erro']}", f"Rejeicao sem aprovacao posterior no codigo {x['codigo_erro']}: {nao} de {tot} AIH ({round(100 - pct, 1)}%).", sev, "AIH",
                    "Obter o relatorio de rejeitadas do hospital para o codigo, corrigir a causa e reapresentar dentro do prazo.")
        tot_f = rec["rejeitadas_fechadas"]
        top = (rec.get("por_codigo_erro") or [None])[0]
        if top and tot_f >= 10 and top["rejeitadas"] / tot_f >= 0.5:
            add(f"C08-{top['codigo_erro']}", f"Rejeicoes concentradas no codigo {top['codigo_erro']}: {top['rejeitadas']} de {tot_f} ({round(top['rejeitadas'] / tot_f * 100, 1)}%). "
                f"Mesmo recuperadas, atrasam o recebimento em pelo menos uma competencia.", "Media", "AIH",
                "Prevenir na origem: validar o dado antes de fechar a remessa e treinar a digitacao do campo envolvido.")
    return c


def _plano(criticas, rec, ind, lancamentos=None, cnes=None):
    """Plano de avanco do faturamento a partir das criticas. Ganho em R$ nao e inventado: o gestor lanca. Perda e ESTIMATIVA."""
    media = (ind or {}).get("media_por_aih")
    itens = []
    for k in criticas:
        item = {"acao": k["acao_recomendada"], "critica_vinculada": k["codigo"], "prioridade": k["severidade"], "ganho_estimado_rs": None,
                "perda_por_rejeicao_rs": None, "prazo": RESP, "responsavel": RESP, "status": "A iniciar"}
        if k["codigo"].startswith("C07-") and isinstance(rec, dict) and media:
            cod = k["codigo"].split("-")[1]
            x = next((y for y in rec.get("por_codigo_erro", []) if y["codigo_erro"] == cod), None)
            if x:
                item["perda_por_rejeicao_rs"] = round(x["nao_recuperadas"] * media, 2)
                item["obs_perda"] = "ESTIMATIVA: AIH nao recuperadas x media por AIH aprovada do hospital. O arquivo ER nao traz valor."
        itens.append(item)
    ordem = {"Alta": 0, "Media": 1, "Baixa": 2}
    itens.sort(key=lambda i: ordem[i["prioridade"]])
    if lancamentos and cnes:
        PA.aplicar(itens, cnes, lancamentos)
    sem_ganho = [i for i in itens if i["ganho_estimado_rs"] is None]
    return {"itens": itens, "total": len(itens),
            "pendencia_ganho": f"[PREENCHER: ganho estimado em R$ de {len(sem_ganho)} acao(oes), lancado pelo gestor]" if sem_ganho else None}


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
        arq = PA.carregar()
        for cnes in lista:
            cad = _cadastro(con, cnes)
            sih, sia, ciha = _producao(con, cnes)
            _ocupacao_mensal(sih, (cad.get("leitos") or {}).get("sus"))
            ind = _indicadores(sih, (cad.get("leitos") or {}).get("sus"), (cad.get("leitos") or {}).get("existentes"))
            rej = _rejeicao(con, cnes, sih)
            crit = _criticas(cnes, cad, sih, ind, (rej or {}).get("reapresentacao") if isinstance(rej, dict) else None)
            itens.append({"cnes": cnes, "cadastro": cad,
                          "producao": {"sih_por_mes": sih, "sia_aprovado_por_mes": sia, "ciha_por_mes": ciha,
                                       "sia_aprovado_total": {"quantidade": sum(x["quantidade_aprovada"] for x in sia), "valor": round(sum(x["valor_aprovado"] for x in sia), 2)} if sia else None},
                          "indicadores": ind, "rejeicao_sih": rej, "criticas": crit, "plano_avanco": _plano(crit, (rej or {}).get("reapresentacao"), ind, arq["lancamentos"], cnes)})
        sev = {"Alta": 0, "Media": 0, "Baixa": 0}
        for h in itens:
            for k in h["criticas"]:
                sev[k["severidade"]] += 1
        return {"fonte": "Base local: SIH (RD, SP), SIA aprovado (PA), CIHA, CNES (ST, LT, EQ, PF, HB, IN, SR)", "total": len(itens),
                "criticas_por_severidade": sev, "plano_acoes_arquivo": {k: arq[k] for k in ("situacao", "linhas_lidas", "recusadas")}, "itens": itens,
                "obs": "SIH e SIA de 2026 ate o ultimo mes disponivel no FTP; cadastro CNES na competencia mais recente de cada grupo."}
    finally:
        con.close()
