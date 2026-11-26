#!/usr/bin/env python3
"""Status automatico das fontes (config/fontes.json). Grava rede_fontes.json na pasta de dados do site.
Regras do projeto: nenhuma integracao e dada como Ativa sem coleta registrada com data; bloqueio declarado nunca e contornado.
  Ativa       : o coletor existe e o arquivo (ou tabela da base) foi gerado dentro do prazo de frescor.
  A confirmar : existe saida, porem antiga; ou fonte com bloqueio anterior que voltou a responder; ou sem resposta.
  Manual      : sem coletor automatico. Se houver endereco, o robo faz UMA requisicao de teste (respeita robots.txt) e anota se responde.
  Bloqueada   : bloqueio declarado (login, credencial) ou resposta 401/403/robots negando. Sem tentativa de contorno.
  Descartada  : fonte retirada de uso.
Guarda apenas status, datas, HTTP e nomes de arquivo. Nenhum dado de pessoa. Uso: status_fontes.py [--sem-rede]"""
import json, os, sqlite3, sys
from datetime import datetime, timezone, timedelta

BRT = timezone(timedelta(hours=-3))
AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
BASE = os.environ.get("PARTELLI_BASE", os.path.join(os.path.expanduser("~"), "partelli"))
SALA = os.environ.get("SALA_DADOS", os.path.join(BASE, "sala-gestao", "dados"))
DADOS = os.environ.get("PARTELLI_DADOS", os.path.join(BASE, "dados_repo"))
BANCO = os.environ.get("PARTELLI_BANCO", os.path.join(BASE, "base", "producao_es.sqlite"))
CATALOGO = os.environ.get("FONTES_CATALOGO", os.path.join(RAIZ, "config", "fontes.json"))
ORDEM = ["Ativa", "Em teste", "Manual", "Bloqueada", "A confirmar", "Descartada"]


def agora():
    return datetime.now(BRT)


def _data(txt):
    try:
        t = datetime.fromisoformat(str(txt).replace("Z", "+00:00"))
        return t if t.tzinfo else t.replace(tzinfo=BRT)
    except (TypeError, ValueError):
        return None


def data_arquivo(caminho):
    """Data de geracao: campo gerado_em/baixado_em/coletado_em do JSON; sem ele, a data de modificacao do arquivo."""
    if not os.path.isfile(caminho):
        return None
    try:
        with open(caminho, encoding="utf-8") as a:
            d = json.load(a)
        if isinstance(d, dict):
            for k in ("gerado_em", "baixado_em", "coletado_em"):
                t = _data(d.get(k))
                if t:
                    return t
    except (OSError, ValueError):
        pass
    return datetime.fromtimestamp(os.path.getmtime(caminho), BRT)


def data_sqlite(banco, tabelas):
    if not os.path.isfile(banco):
        return None
    con = sqlite3.connect(banco)
    try:
        marcas = ",".join("?" * len(tabelas))
        r = con.execute(f"SELECT MAX(convertido_em) FROM arquivos WHERE tabela IN ({marcas})", list(tabelas)).fetchone()
        return _data(r[0]) if r and r[0] else None
    except sqlite3.Error:
        return None
    finally:
        con.close()


def data_da_fonte(f, sala=SALA, dados=DADOS, banco=BANCO):
    if f.get("tipo") == "sqlite":
        return data_sqlite(banco, f.get("tabelas") or [])
    pasta = dados if f.get("base") == "dados" else sala
    datas = [data_arquivo(os.path.join(pasta, a)) for a in f.get("arquivos") or []]
    if not datas or any(d is None for d in datas):
        return None   # falta algum arquivo da fonte: nao ha coleta completa
    return min(datas)


def sondar_padrao(url):
    sys.path.insert(0, AQUI)
    from sondar_remessas import sondar
    return sondar(url)


def avaliar(f, agora_=None, sondar=None, sala=SALA, dados=DADOS, banco=BANCO):
    """Devolve a linha de status da fonte. `sondar` (url -> dict) e injetado nos testes; None = sem rede."""
    t0 = agora_ or agora()
    linha = {"id": f["id"], "sistema": f["sistema"], "acesso": f.get("acesso"), "uso": f.get("uso"), "coletor": f.get("coletor") or "sem coletor automatico",
             "limite": f.get("limite") or ""}
    tipo = f.get("tipo")
    if tipo == "descartada":
        return {**linha, "status": "Descartada", "ultimo_teste": None, "resultado": "Fonte retirada de uso."}
    if tipo == "bloqueada":
        return {**linha, "status": "Bloqueada", "ultimo_teste": None, "resultado": f["bloqueio"]}
    dt = data_da_fonte(f, sala, dados, banco) if tipo in ("arquivo", "sqlite") else None
    if dt is not None:
        dias = max(0, (t0 - dt).days)
        if dias <= int(f.get("frescor_dias", 45)):
            return {**linha, "status": "Ativa", "ultimo_teste": dt.isoformat(timespec="seconds"), "resultado": f"Coleta automatica de {dt:%d/%m/%Y}, {dias} dia(s) atras (prazo {f.get('frescor_dias', 45)} dias)."}
        return {**linha, "status": "A confirmar", "ultimo_teste": dt.isoformat(timespec="seconds"), "resultado": f"Ultima coleta ha {dias} dias, acima do prazo de {f.get('frescor_dias', 45)} dias. Rodar o coletor."}
    # sem coleta registrada: testa o endereco uma vez, se houver
    r = sondar(f["sonda"]) if (sondar and f.get("sonda")) else None
    if r:
        quando = r.get("testado_em")
        if r.get("status") == "Bloqueada":
            return {**linha, "status": "Bloqueada", "ultimo_teste": quando, "resultado": r.get("resultado") or "Acesso negado ao robo. Consulta manual."}
        if r.get("http") and f.get("bloqueio_anterior"):
            return {**linha, "status": "A confirmar", "ultimo_teste": quando, "resultado": f"Pagina responde (HTTP {r['http']}), mas havia bloqueio anterior. Rodar o coletor para confirmar. {f['bloqueio_anterior']}"}
        if r.get("http"):
            sufixo = "Coletor existe, mas ainda nao gerou arquivo." if f.get("coletor") else "Sem coletor automatico, lancamento manual."
            return {**linha, "status": "A confirmar" if f.get("coletor") else "Manual", "ultimo_teste": quando, "resultado": f"Pagina responde (HTTP {r['http']}). {sufixo}"}
        return {**linha, "status": "A confirmar", "ultimo_teste": quando, "resultado": f"Sem resposta no teste ({r.get('resultado') or 'erro de rede'})."}
    if f.get("coletor"):
        return {**linha, "status": "A confirmar", "ultimo_teste": None, "resultado": "Coletor existe, mas ainda nao gerou arquivo. Rodar a coleta."}
    return {**linha, "status": "Manual", "ultimo_teste": None, "resultado": "Sem coletor automatico, lancamento manual."}


def gerar(catalogo=CATALOGO, saida=DADOS, sondar=None, **kw):
    with open(catalogo, encoding="utf-8") as a:
        cat = json.load(a)
    linhas = [avaliar(f, sondar=sondar, **kw) for f in cat["fontes"]]
    resumo = {s: sum(1 for x in linhas if x["status"] == s) for s in ORDEM}
    obj = {"gerado_em": agora().isoformat(timespec="seconds"), "regra": "Status calculado pelo robo a cada rodada. Ativa so com coleta registrada dentro do prazo.", "resumo": resumo, "fontes": linhas}
    txt = json.dumps(obj, ensure_ascii=False, indent=1)
    import re
    if re.search(r"\d{11,}", txt):
        raise SystemExit("recusado: sequencia longa de digitos")
    os.makedirs(saida, exist_ok=True)
    tmp = os.path.join(saida, ".rede_fontes.json.novo")
    with open(tmp, "w", encoding="utf-8") as a:
        a.write(txt)
    os.replace(tmp, os.path.join(saida, "rede_fontes.json"))
    return obj


def main(argv):
    r = gerar(sondar=None if "--sem-rede" in argv else sondar_padrao)
    print("[fontes] " + ", ".join(f"{k}: {v}" for k, v in r["resumo"].items() if v))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
