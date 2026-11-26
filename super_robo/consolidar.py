#!/usr/bin/env python3
"""Super robo, camada 1: dossie por municipio (ES) no proprio notebook.

Junta, sem recalcular nem inventar, o que os coletores da Sala de Gestao ja geram (SICONFI, SIOPS, FNS/InvestSUS, transferencias,
CNES, IBGE) com a producao hospitalar (SIH) e ambulatorial aprovada (SIA) da base SQLite agregada. Cada secao leva fonte,
data de coleta e defasagem em dias. Secao sem dado vira [PREENCHER: ...] e entra na lista de pendencias. SIA: somente producao aprovada.
Saida: <BASE>/dossie/<cod>.json e <BASE>/dossie/indice.json. Uso: consolidar.py [--so COD]
"""
import json, os, sqlite3, sys
from datetime import datetime, timezone, timedelta

AQUI = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("PARTELLI_BASE", os.path.join(os.path.expanduser("~"), "partelli"))
SALA = os.environ.get("SALA_DADOS", os.path.join(BASE, "sala-gestao", "dados"))
BANCO = os.environ.get("PARTELLI_BANCO", os.path.join(BASE, "base", "producao_es.sqlite"))
SAIDA = os.environ.get("DOSSIE_SAIDA", os.path.join(BASE, "dossie"))
DADOS_SITE = os.environ.get("PARTELLI_DADOS_SITE", os.path.join(BASE, "dados_repo"))   # JSON do site; a publicacao e a rotina partelli-coleta publicar
CONFIG = os.environ.get("SUPER_MUNICIPIOS", os.path.join(AQUI, "municipios.json"))
BRT = timezone(timedelta(hours=-3))
TOP = 10
sys.path.insert(0, AQUI)
import cnes_secoes as S
import hospitais as HOSP
import exportar_site as SITE

_TAB = []


def tabelas_cnes():
    """tabelas_cnes.json (descricao oficial de codigos do CNES), se existir. Sem ele o dossie traz so o codigo.
    Se houver mais de uma copia, usa a mais recente (copias antigas nao trazem as tabelas novas)."""
    if not _TAB:
        cand = [x for x in (os.environ.get("TABELAS_CNES", ""), os.path.join(BASE, "dados_repo", "tabelas_cnes.json"),
                            os.path.join(BASE, "dados_repo", "dados", "tabelas_cnes.json"), os.path.join(SALA, "tabelas_cnes.json")) if x and os.path.isfile(x)]
        cand.sort(key=os.path.getmtime, reverse=True)
        tab = S.carregar_tabelas(cand)
        if tab is not None:
            tab["_arquivo"] = next(c for c in cand if S.carregar_tabelas([c]) is not None)
        _TAB.append(tab)
    return _TAB[0]


def ler(caminho):
    try:
        with open(caminho, encoding="utf-8") as a:
            return json.load(a)
    except (OSError, ValueError):
        return None


def agora():
    return datetime.now(BRT).isoformat(timespec="seconds")


def defasagem(gerado):
    try:
        t = datetime.fromisoformat(str(gerado))
        if t.tzinfo is None:
            t = t.replace(tzinfo=BRT)
        return max(0, (datetime.now(BRT) - t).days)
    except (TypeError, ValueError):
        return None


def pend(txt):
    return f"[PREENCHER: {txt}]"


def cabecalho(d, extra=()):
    h = {"fonte": d.get("fonte"), "coletado_em": d.get("gerado_em") or d.get("baixado_em")}
    h["defasagem_dias"] = defasagem(h["coletado_em"])
    for k in ("exercicio", "competencia", "bimestre", "periodo", "ano", "se", "meses") + tuple(extra):
        if k in d:
            h[k] = d[k]
    return h


def chaves(cod):
    return [cod, cod[:6]]


def valor_municipio(mapa, cod):
    for c in chaves(cod):
        if isinstance(mapa, dict) and c in mapa:
            return mapa[c]
    return None


def secao_mapa(nome, d, chave_mapa, cod, extras=()):
    """Arquivo nacional com mapa de municipios (chave_mapa) e lista 'campos' alinhada aos valores."""
    if d is None:
        return pend(f"arquivo {nome} nao encontrado em {SALA}")
    v = valor_municipio(d.get(chave_mapa), cod)
    if v is None:
        return {**cabecalho(d), "valores": pend(f"municipio sem registro em {nome}")}
    s = cabecalho(d)
    campos = d.get("campos")
    if isinstance(v, list) and isinstance(campos, list) and len(campos) == len(v):
        s["valores"] = dict(zip(campos, v))
    else:
        s["valores"] = v
        for k in ("campos", "tipos", "grupos", "comp"):
            if k in d:
                s[k] = d[k]
    for k in extras:
        if k in d:
            s[k] = d[k]
    return s


FONTE_RESUMO = {"siops": "siops_resumo.json", "rede": "rede_resumo.json", "profissionais": "profissionais_resumo.json",
                "recursos": "financiamento.json", "dengue": "dengue_resumo.json"}


def fonte_de(nome):
    r = ler(os.path.join(SALA, FONTE_RESUMO.get(nome, "")))
    return r.get("fonte") if isinstance(r, dict) else None


def secao_uf(nome, uf, cod):
    d = ler(os.path.join(SALA, nome, f"{uf}.json"))
    if d is None:
        return pend(f"arquivo {nome}/{uf}.json nao encontrado em {SALA}")
    s = secao_mapa(f"{nome}/{uf}", d, "m", cod, extras=("campos", "grupos", "comp", "meta"))
    if isinstance(s, dict) and not s.get("fonte"):
        s["fonte"] = fonte_de(nome) or pend(f"fonte de {nome}")
    return s


def _pct(a, b):
    return round(a / b * 100, 1) if b else None


def secao_emendas(uf, cod):
    """Emendas parlamentares do municipio a partir do Radar de Recursos (partelli.pro/fundo, que le os Paineis InvestSUS/FNS), coletado por
    coletar_recursos.py. Valores do ano da proposta (meta.anoEm): proposto, empenhado, pago. Sem numero de proposta nem autor.
    Percentuais sao de EXECUCAO (empenhado sobre proposto, pago sobre empenhado), nao meta."""
    d = ler(os.path.join(SALA, "recursos", f"{uf}.json"))
    if d is None:
        return pend(f"arquivo recursos/{uf}.json nao encontrado em {SALA}; rode coletar_recursos.py")
    m = valor_municipio(d.get("m"), cod)
    if not m or "em" not in m:
        return {"situacao": "A confirmar: municipio sem emendas no Radar de Recursos no ano da proposta", "fonte": "Radar de Recursos (InvestSUS/FNS)"}
    prop, emp, pago = m["em"]
    meta = d.get("meta") or {}
    return {"fonte": "Radar de Recursos (partelli.pro/fundo), a partir dos Paineis InvestSUS/FNS", "status_fonte": "Em teste",
            "ano_da_proposta": meta.get("anoEm"), "extracao_investsus": meta.get("extracao"), "coletado_em": d.get("gerado_em"),
            "defasagem_dias": defasagem(d.get("gerado_em")),
            "propostas": m.get("eq"), "proposto_rs": prop, "empenhado_rs": emp, "pago_rs": pago,
            "pct_empenhado_sobre_proposto": _pct(emp, prop), "pct_pago_sobre_empenhado": _pct(pago, emp), "saldo_a_pagar_rs": round(emp - pago, 2),
            "obs": "Execucao financeira, nao meta. Dado por municipio do Radar (nao depende da localidade MULTIPLO do Portal da Transparencia). "
                   "Somente o ano da proposta indicado; ganho estimado e prazos sao lancados pelo gestor."}


def secao_dengue(uf, cod):
    d = ler(os.path.join(SALA, "dengue", f"{uf}.json"))
    if d is None:
        return pend("arquivo dengue/ES.json nao encontrado")
    for linha in d.get("m", []):
        if isinstance(linha, list) and linha and linha[0] in chaves(cod):
            return {**cabecalho(d, ("se",)), "fonte": fonte_de("dengue") or pend("fonte de dengue"), "valores": linha, "obs": "Formato da Sala de Gestao: cod, nome, nivel, casos, incidencia e serie recente."}
    return {**cabecalho(d, ("se",)), "valores": pend("municipio sem registro em dengue")}


def SEM_REGISTRO(o_que):
    return {"situacao": f"A confirmar: sem {o_que} do municipio na base de 2026",
            "obs": "Ausencia de registro nao e erro de leitura. Conferir se o municipio tem estabelecimento do tipo no CNES (leitos, rede)."}


def ciha_mun(cod):
    """CIHA (internacao e atendimento hospitalar fora do SIH) do municipio: quantidades, sem valor financeiro."""
    c6 = cod[:6]
    if not os.path.isfile(BANCO):
        return pend("base SQLite nao encontrada; rode converter_sqlite.py")
    con = sqlite3.connect(BANCO)
    try:
        if not con.execute("SELECT name FROM sqlite_master WHERE name='ciha'").fetchone():
            return pend("CIHA ainda nao convertido na base")
        mes = [{"competencia": f"{m}/{a}", "registros": n, "quantidade_procedimentos": q, "dias_permanencia": d, "obitos": o}
               for a, m, n, q, d, o in con.execute(
                   "SELECT ano, mes, SUM(n_linhas), SUM(qt_proc), SUM(dias_perm), SUM(mortes) FROM ciha WHERE munic_mov=? GROUP BY ano, mes ORDER BY ano, mes", (c6,))]
        base = {"fonte": "CIHA (FTP DATASUS), agregado na base local", "convertido_em": con.execute("SELECT MAX(convertido_em) FROM arquivos WHERE tabela='ciha'").fetchone()[0],
                "obs": "CIHA nao traz valor financeiro. Complementa o SIH, nao somar com AIH sem conferir duplicidade por CNES."}
        if not mes:
            return {**SEM_REGISTRO("registro de CIHA"), **base}
        proc = [{"procedimento": p, "quantidade": q} for p, q in con.execute(
            "SELECT proc_rea, SUM(qt_proc) FROM ciha WHERE munic_mov=? GROUP BY proc_rea ORDER BY SUM(qt_proc) DESC LIMIT ?", (c6, TOP))]
        cn = [r[0] for r in con.execute("SELECT DISTINCT cnes FROM ciha WHERE munic_mov=? ORDER BY cnes", (c6,))]
        return {**base, "cnes_com_ciha": cn, "por_mes": mes, "principais_procedimentos": proc}
    finally:
        con.close()


def producao(con, cod):
    """SIH (RD, SP) e SIA (PA, somente aprovado) do municipio, a partir da base SQLite agregada."""
    c6 = cod[:6]
    if not os.path.isfile(BANCO):
        return pend("base SQLite nao encontrada; rode converter_sqlite.py"), pend("base SQLite nao encontrada")
    con = sqlite3.connect(BANCO)
    try:
        arq = {n: (l, v) for n, l, v in con.execute("SELECT tabela, MAX(convertido_em), COUNT(*) FROM arquivos GROUP BY tabela")}
        rd_mes = [{"competencia": f"{m}/{a}", "aih": n, "valor_total": round(t, 2), "sh": round(sh, 2), "sp": round(sp, 2),
                   "sh_fed": round(shf, 2), "sp_fed": round(spf, 2),
                   "media_aih": round(t / n, 2) if n else None, "obitos": mo, "dias_permanencia": dp}
                  for a, m, n, t, sh, sp, shf, spf, mo, dp in con.execute(
                      "SELECT ano, mes, SUM(n_linhas), SUM(val_tot), SUM(val_sh), SUM(val_sp), SUM(val_sh_fed), SUM(val_sp_fed), SUM(mortes), SUM(dias_perm) FROM rd "
                      "WHERE munic_mov=? GROUP BY ano, mes ORDER BY ano, mes", (c6,))]
        rd_proc = [{"procedimento": p, "aih": n, "valor_total": round(t, 2)} for p, n, t in con.execute(
            "SELECT proc_rea, SUM(n_linhas), SUM(val_tot) FROM rd WHERE munic_mov=? GROUP BY proc_rea ORDER BY SUM(val_tot) DESC LIMIT ?", (c6, TOP))]
        cnes_rd = [r[0] for r in con.execute("SELECT DISTINCT cnes FROM rd WHERE munic_mov=? ORDER BY cnes", (c6,))]
        sp_mes = []
        if cnes_rd:
            marcas = ",".join("?" * len(cnes_rd))
            sp_mes = [{"competencia": f"{m}/{a}", "atos": q, "valor": round(v, 2)} for a, m, q, v in con.execute(
                f"SELECT ano, mes, SUM(qtd_ato), SUM(val_ato) FROM sp WHERE cnes IN ({marcas}) GROUP BY ano, mes ORDER BY ano, mes", cnes_rd)]
        sih = {"fonte": "SIH/SUS, arquivos RDES e SPES (FTP DATASUS), agregados na base local",
               "convertido_em": arq.get("rd", (None,))[0], "cnes_com_aih": cnes_rd,
               "obs": "Municipio do hospital (campo MUNIC_MOV). Conferir cnes_com_aih com o CNES antes de usar. "
                      "Valor total = SH + SP + SH_FED + SP_FED (complemento federal, presente a partir de 03/2026).",
               "aih_por_mes": rd_mes or SEM_REGISTRO("AIH"), "principais_procedimentos": rd_proc,
               "servicos_profissionais_por_mes": sp_mes}
        pa_mes = [{"mes_processamento": f"{m[4:]}/{m[:4]}", "quantidade_aprovada": q, "valor_aprovado": round(v, 2)}
                  for m, q, v in con.execute("SELECT mvm, SUM(qtd_apr), SUM(val_apr) FROM pa WHERE ufmun=? GROUP BY mvm ORDER BY mvm", (c6,))]
        pa_proc = [{"procedimento": p, "quantidade_aprovada": q, "valor_aprovado": round(v, 2)} for p, q, v in con.execute(
            "SELECT proc_id, SUM(qtd_apr), SUM(val_apr) FROM pa WHERE ufmun=? GROUP BY proc_id ORDER BY SUM(val_apr) DESC LIMIT ?", (c6, TOP))]
        pa_cnes = [{"cnes": c, "valor_aprovado": round(v, 2)} for c, v in con.execute(
            "SELECT cnes, SUM(val_apr) FROM pa WHERE ufmun=? GROUP BY cnes ORDER BY SUM(val_apr) DESC LIMIT ?", (c6, TOP))]
        sia = {"fonte": "SIA/SUS, arquivo PAES (FTP DATASUS), agregado na base local", "convertido_em": arq.get("pa", (None,))[0],
               "obs": "Somente producao aprovada (decisao do responsavel). Municipio do estabelecimento (PA_UFMUN).",
               "por_mes": pa_mes or SEM_REGISTRO("producao ambulatorial aprovada"), "principais_procedimentos": pa_proc, "principais_estabelecimentos": pa_cnes}
        return sih, sia
    finally:
        con.close()


def montar(cfg, m, terr):
    cod, uf = m["cod"], cfg["uf"]
    ficha = {"cod": cod, "cod6": cod[:6], "nome": m["nome"], "uf": uf}
    if terr:
        for e in terr.get("municipios", []):
            if e.get("cod") == cod:
                ficha["populacao"] = {"valor": e.get("pop"), **cabecalho(terr)}
                break
    ficha.setdefault("populacao", pend("populacao do municipio"))
    sih, sia = producao(None, cod)
    secoes = {
        "financeiro": {
            "despesa_saude": secao_mapa("despesa.json", ler(os.path.join(SALA, "despesa.json")), "mun", cod),
            "receita": secao_mapa("receita.json", ler(os.path.join(SALA, "receita.json")), "mun", cod),
            "pessoal": secao_mapa("pessoal.json", ler(os.path.join(SALA, "pessoal.json")), "mun", cod),
            "siops": secao_uf("siops", uf, cod)},
        "recursos": {
            "fns_investsus": secao_uf("recursos", uf, cod),
            "transferencias_uniao_saude": secao_mapa("transferencias.json", ler(os.path.join(SALA, "transferencias.json")), "mun", cod),
            "emendas": secao_emendas(uf, cod)},
        "producao": {"sih": sih, "sia_aprovado": sia, "ciha": ciha_mun(cod)},
        "hospitais": HOSP.visao_hospitais(BANCO, cod[:6], tabelas_cnes()),
        "cnes": {
            "leitos": secao_mapa("leitos.json", ler(os.path.join(SALA, "leitos.json")), "mun", cod),
            "equipes": secao_mapa("equipes.json", ler(os.path.join(SALA, "equipes.json")), "mun", cod),
            "equipamentos": secao_mapa("equipamentos.json", ler(os.path.join(SALA, "equipamentos.json")), "mun", cod),
            "profissionais": secao_uf("profissionais", uf, cod),
            "rede": secao_uf("rede", uf, cod),
            "tabelas_codigos": S.secao_tabelas(tabelas_cnes()),
            "habilitacoes": S.lista_hab(BANCO, cod[:6], "hb", "HB", "habilitacao cadastrada", tabelas_cnes(), S.desc_habilitacao),
            "leitos_por_tipo": S.leitos_por_tipo(BANCO, cod[:6], tabelas_cnes()),
            "equipamentos_cadastro": S.equipamentos(BANCO, cod[:6], tabelas_cnes()),
            "profissionais_cadastro": S.profissionais(BANCO, cod[:6]),
            "servicos_especializados": S.servicos(BANCO, cod[:6], tabelas_cnes()),
            "equipes_cadastro": S.equipes(BANCO, cod[:6], tabelas_cnes()),
            "incentivos": S.lista_hab(BANCO, cod[:6], "inc", "IN", "incentivo cadastrado", tabelas_cnes(), S.desc_incentivo),
            "regras_contratuais": S.lista_hab(BANCO, cod[:6], "rc", "RC", "regra contratual cadastrada", tabelas_cnes(), S.desc_regra),
            "entidade_filantropica": S.lista_hab(BANCO, cod[:6], "ef", "EF", "registro de entidade filantropica", tabelas_cnes(), S.desc_filantropico),
            "estabelecimentos": S.estabelecimentos(BANCO, cod[:6], tabelas_cnes())},
        "territorio_saude": {
            "dengue": secao_dengue(uf, cod),
            "cobertura_planos_ans": secao_mapa("ans.json", ler(os.path.join(SALA, "ans.json")), "mun", cod)},
    }
    pendencias = []

    def varrer(o, caminho):
        if isinstance(o, str) and o.startswith("[PREENCHER"):
            pendencias.append(f"{caminho}: {o}")
        elif isinstance(o, dict):
            for k, v in o.items():
                varrer(v, f"{caminho}.{k}" if caminho else k)
        elif isinstance(o, list):
            for i, v in enumerate(o):
                varrer(v, f"{caminho}[{i}]")
    varrer({"populacao": ficha["populacao"], **secoes}, "")
    return {"municipio": ficha, "gerado_em": agora(), "secoes": secoes, "pendencias": pendencias}


def main(argv):
    cfg = ler(CONFIG)
    terr = ler(os.path.join(SALA, "territorio.json"))
    os.makedirs(SAIDA, exist_ok=True)
    alvo = argv[argv.index("--so") + 1] if "--so" in argv else None
    indice = []
    for m in cfg["municipios"]:
        if alvo and m["cod"] != alvo:
            continue
        d = montar(cfg, m, terr)
        with open(os.path.join(SAIDA, f"{m['cod']}.json"), "w", encoding="utf-8") as a:
            json.dump(d, a, ensure_ascii=False, indent=1)
        indice.append({"cod": m["cod"], "nome": m["nome"], "pendencias": len(d["pendencias"]), "gerado_em": d["gerado_em"]})
        print(f"[super] {m['nome']} ({m['cod']}): {len(d['pendencias'])} pendencias")
    if not alvo:
        with open(os.path.join(SAIDA, "estado_ES_rejeicao_por_cnes.json"), "w", encoding="utf-8") as a:
            json.dump({"gerado_em": agora(), **HOSP.rejeicao_por_cnes(BANCO)}, a, ensure_ascii=False, indent=1)
        with open(os.path.join(SAIDA, "indice.json"), "w", encoding="utf-8") as a:
            json.dump({"gerado_em": agora(), "municipios": indice}, a, ensure_ascii=False, indent=1)
        r = SITE.exportar(SAIDA, DADOS_SITE)
        print(f"[super] arquivos para o site em {DADOS_SITE}: {len(r['gravados'])} gravados, {len(r['recusados'])} recusados pela guarda de privacidade")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
