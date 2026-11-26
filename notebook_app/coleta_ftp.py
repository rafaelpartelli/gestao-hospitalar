#!/usr/bin/env python3
"""Download automatico de arquivos DBC do FTP do DATASUS para o notebook (somente ES, ano configurado).

Arquivos: RDES, SPES e PAES do ano (config em automacao.json). Pula o que ja esta baixado (mesmo tamanho),
respeita orcamento de trafego e disco minimo (hospital_comum), um download por vez, grava estado em
<downloads>/_estado_automacao.json. Nenhum arquivo e aberto: so copia. Uso: coleta_ftp.py [--listar]
"""
import fcntl, json, os, re, sys, time
from datetime import datetime

AQUI = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("PARTELLI_BASE", os.path.join(os.path.expanduser("~"), "partelli"))
for p in (os.path.join(AQUI, "..", "robo"), os.path.join(BASE, "sala-gestao", "robo")):
    if os.path.isdir(p):
        sys.path.insert(0, os.path.abspath(p))
import hospital_comum as H

DESTINO = os.environ.get("PAINEL_DOWNLOADS", os.path.join(BASE, "ftp_downloads"))
CONFIG = os.environ.get("AUTOMACAO_CONFIG", os.path.join(AQUI, "automacao.json"))


def carregar():
    with open(CONFIG, encoding="utf-8") as a:
        return json.load(a)


def padrao(cfg, prefixo):
    aa = f"{int(cfg['ano']) % 100:02d}"
    return re.compile(rf"^{prefixo}{cfg['uf']}{aa}(0[1-9]|1[0-2])[a-z]?\.dbc$", re.I)


def planejar(cfg, listagens):
    """listagens: {pasta: [(nome, tamanho)]}. Retorna lista de dicts a baixar, ordem cronologica."""
    plano = []
    for fonte in cfg["fontes"]:
        rx = padrao(cfg, fonte["prefixo"])
        itens = [{"nome": nome, "pasta": fonte["pasta"], "tamanho": int(tam), "sistema": fonte["sistema"]}
                 for nome, tam in listagens.get(fonte["pasta"], []) if rx.match(nome)]
        if fonte.get("ultimos"):   # grupos cadastrais (CNES): so as competencias mais recentes, para poupar trafego
            itens.sort(key=lambda i: re.search(r"(\d{4})[a-z]?\.dbc$", i["nome"], re.I).group(1))
            itens = itens[-int(fonte["ultimos"]):]
        plano.extend(itens)
    plano.sort(key=lambda i: (i["nome"][-8:-4] if i["nome"][-5].isdigit() else i["nome"][-9:-5], i["nome"]))
    return plano


def ja_baixado(item):
    p = os.path.join(DESTINO, item["nome"])
    return os.path.isfile(p) and os.path.getsize(p) == item["tamanho"] and item["tamanho"] > 0


def listar_pasta(pasta, aceita=None):
    """Lista a pasta. Com `aceita` (funcao nome->bool), so pede o tamanho dos arquivos aceitos: pasta do DATASUS tem milhares de arquivos."""
    aceita = aceita or (lambda nome: True)
    f = H.conectar()
    try:
        saida = []
        try:
            for nome, fatos in f.mlsd(pasta, facts=["type", "size"]):
                if fatos.get("type") == "file" and aceita(nome):
                    saida.append((nome, int(fatos.get("size", 0) or 0)))
        except Exception:
            f.cwd(pasta)
            f.voidcmd("TYPE I")
            for nome in f.nlst():
                if not aceita(nome):
                    continue
                try:
                    saida.append((nome, int(f.size(nome) or 0)))
                except Exception:
                    saida.append((nome, 0))
        return saida
    finally:
        try:
            f.quit()
        except Exception:
            pass


def baixar(item):
    os.makedirs(DESTINO, exist_ok=True)
    destino = os.path.join(DESTINO, item["nome"])
    parcial = destino + ".parte"
    recebido = 0
    f = H.conectar()
    try:
        f.voidcmd("TYPE I")
        with open(parcial, "wb") as saida:
            def escreve(b):
                nonlocal recebido
                saida.write(b)
                recebido += len(b)
            f.retrbinary("RETR " + item["pasta"].rstrip("/") + "/" + item["nome"], escreve, 64 * 1024)
        if item["tamanho"] and recebido != item["tamanho"]:
            raise IOError(f"tamanho recebido {recebido} diferente de {item['tamanho']}")
        os.replace(parcial, destino)
    finally:
        if recebido:
            H.registrar_trafego(recebido)
        try:
            f.quit()
        except Exception:
            pass
        if os.path.exists(parcial):
            os.remove(parcial)
    return recebido


def main(argv):
    cfg = carregar()
    os.makedirs(BASE, exist_ok=True)
    trava = open(os.path.join(BASE, ".lock"), "w")      # mesma trava dos robos de coleta: nunca dois ao mesmo tempo
    try:
        fcntl.flock(trava, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("outra execucao em andamento, saindo")
        return 0
    listagens = {}
    for pasta in sorted({f["pasta"] for f in cfg["fontes"]}):
        rxs = [padrao(cfg, f["prefixo"]) for f in cfg["fontes"] if f["pasta"] == pasta]
        print(f"[ftp-es] lendo {pasta}", flush=True)
        try:
            listagens[pasta] = listar_pasta(pasta, lambda nome, rxs=rxs: any(r.match(nome) for r in rxs))
        except Exception as e:   # pasta inexistente ou indisponivel nao derruba as demais
            listagens[pasta] = []
            print(f"[ftp-es] pasta indisponivel {pasta}: {str(e)[:100]}", flush=True)
    plano = planejar(cfg, listagens)
    pendentes = [i for i in plano if not ja_baixado(i)]
    estado = {"atualizado": datetime.now().isoformat(timespec="seconds"), "ano": cfg["ano"], "uf": cfg["uf"],
              "encontrados": len(plano), "pendentes": len(pendentes), "baixados_agora": 0, "erros": [], "bloqueado": None}
    print(f"[ftp-es] {len(plano)} arquivos de {cfg['uf']} {cfg['ano']} no FTP, {len(pendentes)} a baixar")
    if "--listar" in argv:
        falta = sum(i["tamanho"] for i in plano if not ja_baixado(i))
        print(f"[ftp-es] a baixar: {falta / 1e6:.1f} MB ({falta / 1e9 / max(float(H.ORCAMENTO_GB), 0.001) * 100:.1f}% do orcamento mensal de trafego)")
        for i in plano:
            print(("ok       " if ja_baixado(i) else "pendente ") + f"{i['nome']:18} {i['tamanho'] / 1e6:8.1f} MB ({i['tamanho']:>10,} bytes)  {i['sistema']}")
        return 0
    for i in pendentes:
        try:
            H.checar_guardas(i["tamanho"], DESTINO if os.path.isdir(DESTINO) else BASE)
        except H.ErroColeta as e:
            estado["bloqueado"] = str(e)
            print(f"[ftp-es] parado pelas protecoes: {e}")
            break
        try:
            n = baixar(i)
            estado["baixados_agora"] += 1
            print(f"[ftp-es] {i['nome']} {n / 1e6:.1f} MB")
        except Exception as e:
            estado["erros"].append(f"{i['nome']}: {str(e)[:120]}")
            print(f"[ftp-es] ERRO {i['nome']}: {e}")
    estado["pendentes"] = len([i for i in plano if not ja_baixado(i)])
    os.makedirs(DESTINO, exist_ok=True)
    with open(os.path.join(DESTINO, "_estado_automacao.json"), "w", encoding="utf-8") as a:
        json.dump(estado, a, ensure_ascii=False, indent=1)
    print(f"[ftp-es] fim: baixados {estado['baixados_agora']}, pendentes {estado['pendentes']}, erros {len(estado['erros'])}")
    return 1 if estado["erros"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
