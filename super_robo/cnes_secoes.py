"""Secoes do CNES no dossie por municipio, lidas da base SQLite agregada (grupos ST, LT, EQ, PF, SR, EP, IN, RC, EF, HB).

Regras: sem dado inventado. Descricao de codigo so entra quando a tabela oficial do CNES (tabelas_cnes.json, gerada por
robo/coletar_cnes_tabelas.py) esta presente; sem ela, o dossie traz o codigo e uma pendencia. Profissionais: so contagem de vinculos
e horas por CBO e por CNES, nunca nome, CPF, CNS ou registro. Cada secao usa a competencia mais recente do proprio grupo."""
import os, re, sqlite3

TOP_CBO, TOP_CNES, TOP_EQUIP, TOP_SERV = 15, 10, 40, 40


def pend(txt):
    return f"[PREENCHER: {txt}]"


def sem_registro(o_que):
    return {"situacao": f"A confirmar: sem {o_que} do municipio na base de 2026",
            "obs": "Ausencia de registro nao e erro de leitura. Conferir se o municipio tem estabelecimento do tipo no CNES."}


def carregar_tabelas(candidatos):
    import json
    for c in candidatos:
        try:
            with open(c, encoding="utf-8") as a:
                d = json.load(a)
            if isinstance(d, dict) and isinstance(d.get("tabelas"), dict):
                return d
        except (OSError, ValueError):
            continue
    return None


def _T(tab):
    return (tab or {}).get("tabelas") or {}


def _pad(v, n):
    return str(v if v is not None else "").strip().rjust(n, "0")


def _sem_prefixo(t):
    return re.sub(r"^\d+\s*-\s*", "", str(t or "")).strip()


def desc_habilitacao(tab, sg):
    return _T(tab).get("habilitacao", {}).get(str(sg or "").strip(), "")


def desc_incentivo(tab, sg):
    return _sem_prefixo(_T(tab).get("incentivo", {}).get(str(sg or "").strip()))


def desc_leito(tab, tipo, cod):
    t = _T(tab)
    a = _sem_prefixo(t.get("tipo_leito", {}).get(str(tipo or "").strip()))
    b = t.get("especialidade_leito", {}).get(_pad(cod, 2), "")
    return " · ".join(x for x in (a, b) if x)


def desc_equipamento(tab, tipo, cod):
    k = _pad(tipo, 2) + _pad(cod, 2)
    t = _T(tab)
    return _sem_prefixo(t.get("equipamento", {}).get(k) or t.get("tipo_equipamento", {}).get(k))


def desc_servico(tab, serv, classe):
    return _T(tab).get("servico_classificacao_n", {}).get(_pad(serv, 3) + _pad(classe, 3), "")


def mapa_instalacoes(tab):
    out, grupo = {}, ""
    for ln in _T(tab).get("instalacoes_def") or []:
        h = re.match(r"^I\*\s*(.+?)\s*\*\s*\.?\s*,\s*\w+", ln)
        if h:
            grupo = re.sub(r"\s+", " ", h.group(1))
            grupo = grupo[:1].upper() + grupo[1:].lower()
            continue
        i = re.match(r"^IQt\.\s*(.+?)\s*,\s*QTINST(\d{2})\s*$", ln)
        if i:
            out[i.group(2)] = (grupo + ": " if grupo else "") + re.sub(r"\s+", " ", i.group(1)).strip()
    return out


def secao_tabelas(tab):
    """Uma unica indicacao no dossie: de onde vem a descricao dos codigos, ou o que falta para te-la."""
    if not tab:
        return pend("tabelas oficiais de descricao de codigos do CNES (tabelas_cnes.json): rode robo/coletar_cnes_tabelas.py no notebook")
    return {"fonte": tab.get("fonte", "CNES, tabelas auxiliares (FTP DATASUS)"), "gerado_em": tab.get("gerado_em")}


def _fmt(comp):
    return f"{comp[4:]}/{comp[:4]}" if comp and len(comp) == 6 else comp


def _comp(con, t):
    if not con.execute("SELECT name FROM sqlite_master WHERE name=?", (t,)).fetchone():
        return None
    return con.execute(f"SELECT MAX(competen) FROM {t}").fetchone()[0]


def _cab(con, t, fonte, comp):
    return {"fonte": fonte, "competencia": _fmt(comp),
            "convertido_em": con.execute("SELECT MAX(convertido_em) FROM arquivos WHERE tabela=?", (t,)).fetchone()[0]}


def _abrir(banco):
    return sqlite3.connect(banco) if os.path.isfile(banco) else None


def lista_hab(banco, c6, tabela, nome_arq, rotulo, tab, descrever=None):
    """Habilitacoes (HB), incentivos (IN), regras contratuais (RC) e entidade filantropica (EF): mesmo layout de portaria e vigencia."""
    con = _abrir(banco)
    if con is None:
        return pend("base SQLite nao encontrada; rode converter_sqlite.py")
    try:
        comp = _comp(con, tabela)
        if not comp:
            return pend(f"{rotulo}: arquivos {nome_arq} ainda nao convertidos na base")
        base = _cab(con, tabela, f"CNES, arquivo {nome_arq} (FTP DATASUS), agregado na base local", comp)
        sel = "SUM(nuleitos)" if tabela == "hb" else "0"
        linhas = []
        for a, b, i, f, po, dt, nl in con.execute(
                f"SELECT cnes, sgruphab, cmpt_ini, cmpt_fim, portaria, dtportar, {sel} FROM {tabela} WHERE codufmun=? AND competen=? "
                "GROUP BY cnes, sgruphab, cmpt_ini, cmpt_fim, portaria, dtportar ORDER BY cnes, sgruphab", (c6, comp)):
            it = {"cnes": a, "codigo": b, "vigencia_inicio": i, "vigencia_fim": f, "portaria": po, "data_portaria": dt}
            if tabela == "hb":
                it["codigo_habilitacao"] = b
                it["leitos"] = nl
            if descrever:
                d = descrever(tab, b)
                if d:
                    it["descricao"] = d
            linhas.append(it)
        if not linhas:
            return {**sem_registro(rotulo), **base}
        out = {**base, "total": len(linhas), "estabelecimentos": sorted({r["cnes"] for r in linhas}), "itens": linhas}
        return out
    finally:
        con.close()


def leitos_por_tipo(banco, c6, tab):
    con = _abrir(banco)
    if con is None:
        return pend("base SQLite nao encontrada")
    try:
        comp = _comp(con, "lt")
        if not comp:
            return pend("leitos por tipo: arquivos LT ainda nao convertidos na base")
        base = _cab(con, "lt", "CNES, arquivo LT (FTP DATASUS), agregado na base local", comp)
        itens = []
        for tp, cod, e, c, s, n in con.execute(
                "SELECT tp_leito, codleito, SUM(qt_exist), SUM(qt_contr), SUM(qt_sus), SUM(qt_nsus) FROM lt WHERE codufmun=? AND competen=? "
                "GROUP BY tp_leito, codleito ORDER BY SUM(qt_exist) DESC", (c6, comp)):
            it = {"tipo": tp, "codigo": cod, "existentes": e, "contratados": c, "sus": s, "nao_sus": n}
            d = desc_leito(tab, tp, cod)
            if d:
                it["descricao"] = d
            itens.append(it)
        if not itens:
            return {**sem_registro("leito cadastrado"), **base}
        tot = {k: sum(i[k] for i in itens) for k in ("existentes", "contratados", "sus", "nao_sus")}
        out = {**base, "totais": tot, "itens": itens}
        return out
    finally:
        con.close()


def equipamentos(banco, c6, tab):
    con = _abrir(banco)
    if con is None:
        return pend("base SQLite nao encontrada")
    try:
        comp = _comp(con, "eq")
        if not comp:
            return pend("equipamentos: arquivos EQ ainda nao convertidos na base")
        base = _cab(con, "eq", "CNES, arquivo EQ (FTP DATASUS), agregado na base local", comp)
        itens = []
        for tp, cod, e, u, n in con.execute(
                "SELECT tipequip, codequip, SUM(qt_exist), SUM(qt_uso), COUNT(DISTINCT cnes) FROM eq WHERE codufmun=? AND competen=? "
                "GROUP BY tipequip, codequip ORDER BY SUM(qt_exist) DESC LIMIT ?", (c6, comp, TOP_EQUIP)):
            it = {"tipo": tp, "codigo": cod, "existentes": e, "em_uso": u, "estabelecimentos": n}
            d = desc_equipamento(tab, tp, cod)
            if d:
                it["descricao"] = d
            itens.append(it)
        if not itens:
            return {**sem_registro("equipamento cadastrado"), **base}
        tot = con.execute("SELECT SUM(qt_exist), SUM(qt_uso) FROM eq WHERE codufmun=? AND competen=?", (c6, comp)).fetchone()
        out = {**base, "totais": {"existentes": tot[0], "em_uso": tot[1]}, "itens": itens, "obs": f"Ate {TOP_EQUIP} tipos, em ordem de quantidade."}
        return out
    finally:
        con.close()


def profissionais(banco, c6):
    """Vinculos profissionais e horas por CBO e por CNES. Um profissional com mais de um vinculo conta mais de uma vez."""
    con = _abrir(banco)
    if con is None:
        return pend("base SQLite nao encontrada")
    try:
        comp = _comp(con, "pf")
        if not comp:
            return pend("profissionais: arquivos PF ainda nao convertidos na base")
        base = _cab(con, "pf", "CNES, arquivo PF (FTP DATASUS), agregado na base local", comp)
        tot = con.execute("SELECT SUM(n_linhas), SUM(hora_amb), SUM(horahosp), SUM(horaoutr), COUNT(DISTINCT cnes) FROM pf WHERE codufmun=? AND competen=?",
                          (c6, comp)).fetchone()
        if not tot[0]:
            return {**sem_registro("profissional cadastrado"), **base}
        cbo = [{"cbo": c, "vinculos": n, "horas_ambulatoriais": a, "horas_hospitalares": h, "horas_outras": o}
               for c, n, a, h, o in con.execute(
                   "SELECT cbo, SUM(n_linhas), SUM(hora_amb), SUM(horahosp), SUM(horaoutr) FROM pf WHERE codufmun=? AND competen=? "
                   "GROUP BY cbo ORDER BY SUM(n_linhas) DESC LIMIT ?", (c6, comp, TOP_CBO))]
        por_cnes = [{"cnes": c, "vinculos": n} for c, n in con.execute(
            "SELECT cnes, SUM(n_linhas) FROM pf WHERE codufmun=? AND competen=? GROUP BY cnes ORDER BY SUM(n_linhas) DESC LIMIT ?", (c6, comp, TOP_CNES))]
        return {**base, "vinculos": tot[0], "horas_ambulatoriais": tot[1], "horas_hospitalares": tot[2], "horas_outras": tot[3], "estabelecimentos": tot[4],
                "principais_cbo": cbo, "principais_estabelecimentos": por_cnes,
                "obs": "Contagem de vinculos, nao de pessoas. Sem qualquer dado de identificacao dos profissionais.",
                "descricao_cbo": pend("descricao das ocupacoes (tabela CBO nao carregada)")}
    finally:
        con.close()


def servicos(banco, c6, tab):
    con = _abrir(banco)
    if con is None:
        return pend("base SQLite nao encontrada")
    try:
        comp = _comp(con, "sr")
        if not comp:
            return pend("servicos especializados: arquivos SR ainda nao convertidos na base")
        base = _cab(con, "sr", "CNES, arquivo SR (FTP DATASUS), agregado na base local", comp)
        itens = []
        for s, c, n in con.execute(
                "SELECT serv_esp, class_sr, COUNT(DISTINCT cnes) FROM sr WHERE codufmun=? AND competen=? GROUP BY serv_esp, class_sr "
                "ORDER BY COUNT(DISTINCT cnes) DESC, serv_esp LIMIT ?", (c6, comp, TOP_SERV)):
            it = {"servico": s, "classificacao": c, "estabelecimentos": n}
            d = desc_servico(tab, s, c)
            if d:
                it["descricao"] = d
            itens.append(it)
        if not itens:
            return {**sem_registro("servico especializado cadastrado"), **base}
        total = con.execute("SELECT COUNT(*) FROM (SELECT DISTINCT serv_esp, class_sr FROM sr WHERE codufmun=? AND competen=?)", (c6, comp)).fetchone()[0]
        out = {**base, "total_servicos_classificacoes": total, "itens": itens}
        return out
    finally:
        con.close()


def equipes(banco, c6):
    con = _abrir(banco)
    if con is None:
        return pend("base SQLite nao encontrada")
    try:
        comp = _comp(con, "ep")
        if not comp:
            return pend("equipes: arquivos EP ainda nao convertidos na base")
        base = _cab(con, "ep", "CNES, arquivo EP (FTP DATASUS), agregado na base local", comp)
        itens = [{"tipo_equipe": t, "equipes": n, "sem_data_de_desativacao": a} for t, n, a in con.execute(
            "SELECT tipo_eqp, COUNT(DISTINCT idequipe), COUNT(DISTINCT CASE WHEN TRIM(dt_desat)='' THEN idequipe END) FROM ep "
            "WHERE codufmun=? AND competen=? GROUP BY tipo_eqp ORDER BY COUNT(DISTINCT idequipe) DESC", (c6, comp))]
        if not itens:
            return {**sem_registro("equipe cadastrada"), **base}
        return {**base, "total_equipes": sum(i["equipes"] for i in itens), "itens": itens,
                "obs": "Tipo de equipe em codigo do CNES. Descricao do tipo depende da tabela auxiliar, nao carregada."}
    finally:
        con.close()


def estabelecimentos(banco, c6, tab):
    """Estabelecimentos do municipio por tipo de unidade e, para os que tem leito cadastrado, perfil e instalacoes."""
    con = _abrir(banco)
    if con is None:
        return pend("base SQLite nao encontrada")
    try:
        comp = _comp(con, "st")
        if not comp:
            return pend("estabelecimentos: arquivos ST ainda nao convertidos na base")
        base = _cab(con, "st", "CNES, arquivo ST (FTP DATASUS), agregado na base local", comp)
        total = con.execute("SELECT COUNT(DISTINCT cnes) FROM st WHERE codufmun=? AND competen=?", (c6, comp)).fetchone()[0]
        if not total:
            return {**sem_registro("estabelecimento cadastrado"), **base}
        por_tipo = [{"tipo_unidade": t, "estabelecimentos": n} for t, n in con.execute(
            "SELECT tp_unid, COUNT(DISTINCT cnes) FROM st WHERE codufmun=? AND competen=? GROUP BY tp_unid ORDER BY COUNT(DISTINCT cnes) DESC", (c6, comp))]
        vinc = {v: n for v, n in con.execute(
            "SELECT vinc_sus, COUNT(DISTINCT cnes) FROM st WHERE codufmun=? AND competen=? GROUP BY vinc_sus", (c6, comp))}
        inst = mapa_instalacoes(tab)
        cols = ["cnes", "tp_unid", "natureza", "nat_jur", "esfera_a", "tpgestao", "urgemerg", "atendamb", "centrcir", "centrobs", "centrneo",
                "atendhos", "leithosp", "av_acred", "clasaval", "qtleitp1", "qtleitp2", "qtleitp3"] + [f"qtinst{n:02d}" for n in range(1, 38)]
        hosp = []
        for r in con.execute(f"SELECT {', '.join(cols)} FROM st WHERE codufmun=? AND competen=? AND (qtleitp1+qtleitp2+qtleitp3)>0 ORDER BY cnes", (c6, comp)):
            d = dict(zip(cols, r))
            instal = {}
            for n in range(1, 38):
                q = d.pop(f"qtinst{n:02d}")
                if q:
                    instal[f"{n:02d}"] = {"quantidade": q, **({"descricao": inst[f"{n:02d}"]} if f"{n:02d}" in inst else {})}
            hosp.append({"cnes": d["cnes"], "tipo_unidade": d["tp_unid"], "natureza": d["natureza"], "natureza_juridica": d["nat_jur"], "esfera": d["esfera_a"],
                         "gestao": d["tpgestao"], "leitos_cadastro": {"p1": d["qtleitp1"], "p2": d["qtleitp2"], "p3": d["qtleitp3"]},
                         "urgencia": d["urgemerg"], "atendimento_ambulatorial": d["atendamb"], "centro_cirurgico": d["centrcir"],
                         "centro_obstetrico": d["centrobs"], "centro_neonatal": d["centrneo"], "atendimento_hospitalar": d["atendhos"],
                         "acreditacao": d["av_acred"], "classe_avaliacao": d["clasaval"], "instalacoes": instal})
        out = {**base, "total": total, "por_tipo_unidade": por_tipo, "vinculo_sus_codigos": vinc, "com_leito_cadastrado": hosp,
               "obs": "Tipo de unidade, natureza e indicadores em codigo do CNES (S e N, 1 e 0 como vieram do arquivo). Sem CNPJ, endereco, banco, alvara ou contrato."}
        return out
    finally:
        con.close()
