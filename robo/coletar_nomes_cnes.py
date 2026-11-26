#!/usr/bin/env python3
"""Nomes dos estabelecimentos (CNES) dos municipios acompanhados, da API oficial de dados abertos do Ministerio da Saude.
Status da fonte: Em teste (endpoint e campos conferidos so na primeira rodada no Serverrobo; se mudar, o coletor registra e nao grava).
Saida: <PARTELLI_DADOS>/rede_nomes_cnes.json = {gerado_em, fonte, nomes: {cnes: nome}}.
LGPD: o CNES usa o nome do profissional como nome fantasia de pessoa fisica e de consultorio isolado. Por isso:
  - tipo de unidade 22 (consultorio isolado) e nomes de pessoa fisica NAO sao gravados (o painel mostra so 'CNES <codigo>');
  - CNPJ, endereco, telefone e e-mail nunca sao lidos para a saida; sequencia de 11 ou mais digitos recusa o nome."""
import json, os, re, sys, time, urllib.request, urllib.parse
HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("PARTELLI_BASE", os.path.join(os.path.expanduser("~"), "partelli"))
DADOS = os.environ.get("PARTELLI_DADOS", os.path.join(BASE, "dados_repo"))
MUN = os.environ.get("SUPER_MUNICIPIOS", os.path.join(HERE, "..", "super_robo", "municipios.json"))
URL = os.environ.get("CNES_API", "https://apidadosabertos.saude.gov.br/cnes/estabelecimentos")
LOTE = 20
SEQ = re.compile(r"\d{11,}")
PESSOA = re.compile(r"\b(dr|dra|dr\.|dra\.|doutor|doutora)\b", re.I)


def pegar(url):
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "partelli-robo/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def lista_de(resp):
    if isinstance(resp, list):
        return resp
    for k in ("estabelecimentos", "data", "results", "items"):
        if isinstance(resp.get(k), list):
            return resp[k]
    return []


def campo(d, *chaves):
    for k in chaves:
        v = d.get(k)
        if v not in (None, ""):
            return str(v).strip()
    return None


def aceitar(nome, tipo, natureza):
    if not nome or SEQ.search(nome):
        return False
    if str(tipo or "").strip() in ("22", "022"):
        return False
    if natureza and re.search(r"pessoa f[ií]sica", str(natureza), re.I):
        return False
    return not PESSOA.search(nome)


def coletar(municipios, buscar=pegar, pausa=0.3):
    nomes, recusados, erros = {}, 0, []
    for m in municipios:
        c6, off = m["cod"][:6], 0
        while True:
            q = urllib.parse.urlencode({"codigo_municipio": c6, "limit": LOTE, "offset": off})
            try:
                itens = lista_de(buscar(f"{URL}?{q}"))
            except Exception as e:  # sem rede, bloqueio ou formato novo: registra e segue
                erros.append(f"{m['cod']}: {type(e).__name__}")
                break
            for d in itens:
                c = campo(d, "codigo_cnes", "co_cnes", "cnes")
                nome = campo(d, "nome_fantasia", "no_fantasia", "nome_razao_social", "razao_social")
                tipo = campo(d, "codigo_tipo_unidade", "tp_unid", "tipo_unidade")
                nat = campo(d, "descricao_natureza_juridica_estabelecimento", "natureza_juridica")
                if c and re.fullmatch(r"\d{7}", c):
                    if aceitar(nome, tipo, nat):
                        nomes[c] = nome
                    else:
                        recusados += 1
            if len(itens) < LOTE:
                break
            off += LOTE
            time.sleep(pausa)
    return nomes, recusados, erros


def main():
    cfg = json.load(open(MUN, encoding="utf-8"))
    nomes, recusados, erros = coletar(cfg["municipios"])
    print(f"[nomes] {len(nomes)} nomes aceitos, {recusados} sem nome publico por regra LGPD, {len(erros)} erro(s) {erros[:3]}")
    if not nomes:
        print("[nomes] nada gravado (fonte em teste: conferir endpoint e rede)", file=sys.stderr)
        return 1
    os.makedirs(DADOS, exist_ok=True)
    txt = json.dumps({"gerado_em": time.strftime("%Y-%m-%d %H:%M"), "fonte": "API de dados abertos do Ministerio da Saude (CNES), Em teste", "nomes": nomes}, ensure_ascii=False, indent=1)
    if SEQ.search(txt):
        print("[nomes] recusado pela guarda de privacidade", file=sys.stderr); return 1
    tmp = os.path.join(DADOS, ".rede_nomes_cnes.novo")
    open(tmp, "w", encoding="utf-8").write(txt); os.replace(tmp, os.path.join(DADOS, "rede_nomes_cnes.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
