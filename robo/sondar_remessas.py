#!/usr/bin/env python3
"""Sondagem das paginas de remessa do DATASUS (SIHD, SIASUS, CIHA, Transmissor) e do ElastiCNES.
Regra do projeto: nao contornar bloqueio. Para cada endereco o robo (1) le o robots.txt do servidor,
(2) se o caminho for permitido para o nosso User-Agent, faz UMA requisicao GET para ver se a pagina responde,
(3) registra o resultado com data. Nada alem do codigo HTTP e do tamanho e gravado. Nenhuma pagina e lida alem disso.
Status registrados: Manual (acessivel ou nao testado), Bloqueada (robots.txt nega ou HTTP 401/403), A confirmar (erro de rede).
Saida: dados/hospital/status_fontes.json."""
import json, os, sys, urllib.error, urllib.request, urllib.robotparser
from urllib.parse import urlparse
from comum import UA, agora, escrever_json, ler_json

def sondar(url):
    p = urlparse(url)
    r = {"url": url, "testado_em": agora()}
    rp = urllib.robotparser.RobotFileParser()
    try:
        req = urllib.request.Request(f"{p.scheme}://{p.netloc}/robots.txt", headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as resp:
            rp.parse(resp.read(200_000).decode("utf-8", "replace").splitlines())
        r["robots"] = "lido"
    except urllib.error.HTTPError as e:
        # sem robots.txt (404) significa sem restricao declarada; 401/403 e tratado como bloqueio
        if e.code == 404:
            rp.parse([]); r["robots"] = "inexistente"
        else:
            r.update({"status": "Bloqueada", "resultado": f"robots.txt respondeu HTTP {e.code}"}); return r
    except Exception as e:
        r.update({"status": "A confirmar", "resultado": f"robots.txt: {type(e).__name__}"}); return r
    if not rp.can_fetch(UA, url):
        r.update({"status": "Bloqueada", "resultado": "robots.txt nega o caminho. Consulta somente manual."}); return r
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as resp:
            corpo = resp.read(300_000)
            r.update({"status": "Manual", "http": resp.status, "bytes": len(corpo), "resultado": "pagina responde; sem leitura automatica de relatorios"})
    except urllib.error.HTTPError as e:
        r.update({"status": "Bloqueada" if e.code in (401, 403) else "A confirmar", "http": e.code, "resultado": f"HTTP {e.code}"})
    except Exception as e:
        r.update({"status": "A confirmar", "resultado": type(e).__name__})
    return r

def main():
    cfg = ler_json(os.environ.get("PARTELLI_REMESSAS", "config/remessas_datasus.json"))
    alvos = [(s["id"], s["url"]) for s in cfg["sistemas"]] + [("elasticnes", cfg["elasticnes"]["url"])]
    out = {"gerado_em": agora(), "fontes": {i: sondar(u) for i, u in alvos}}
    escrever_json(os.path.join(os.environ.get("PARTELLI_DADOS", "dados"), "status_fontes.json"), out, indent=1)
    for i, r in out["fontes"].items():
        print(i, r.get("status"), r.get("resultado"))
    return 0

if __name__ == "__main__":
    sys.exit(main())
