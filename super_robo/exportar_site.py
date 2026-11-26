"""Exporta do dossie os JSON que o site (Gestao Hospitalar, aba Rede e rejeicoes) le: rede_indice.json, rede_<cod6ou7>.json e rede_rejeicao_es.json.

So entram a secao de hospitais de cada municipio e a visao estadual de rejeicao por CNES. Guarda de privacidade: o arquivo e recusado se tiver
sequencia de 11 ou mais digitos (CPF, CNS, CNPJ, numero de AIH). Nome de estabelecimento nao existe nos dados. Nome de municipio vem so do cadastro
autorizado (indice do dossie). Nada e publicado aqui: os arquivos ficam na pasta de dados do notebook e seguem a rotina `partelli-coleta publicar`."""
import json, os, re

SEQ_LONGA = re.compile(r"\d{11,}")
NOME_OK = re.compile(r"^[A-Za-z0-9_.-]+\.json$")


def _gravar(pasta, nome, obj):
    txt = json.dumps(obj, ensure_ascii=False, indent=1)
    if SEQ_LONGA.search(txt):
        return False
    assert NOME_OK.match(nome), nome
    tmp = os.path.join(pasta, "." + nome + ".novo")
    with open(tmp, "w", encoding="utf-8") as a:
        a.write(txt)
    os.replace(tmp, os.path.join(pasta, nome))
    return True


def exportar(dossie, saida):
    """Le <dossie>/indice.json, <dossie>/<cod>.json e <dossie>/estado_ES_rejeicao_por_cnes.json; grava em <saida>. Devolve {'gravados': [...], 'recusados': [...]}."""
    os.makedirs(saida, exist_ok=True)
    gravados, recusados, municipios = [], [], []
    idx_path = os.path.join(dossie, "indice.json")
    idx = json.load(open(idx_path, encoding="utf-8")) if os.path.isfile(idx_path) else {"municipios": []}
    for m in idx.get("municipios", []):
        cam = os.path.join(dossie, f"{m['cod']}.json")
        if not os.path.isfile(cam):
            continue
        d = json.load(open(cam, encoding="utf-8"))
        hosp = (d.get("secoes") or {}).get("hospitais")
        nome = f"rede_{m['cod']}.json"
        if _gravar(saida, nome, {"gerado_em": d.get("gerado_em"), "municipio": {"cod": m["cod"], "nome": m["nome"]}, "hospitais": hosp}):
            gravados.append(nome)
            n = hosp.get("total") if isinstance(hosp, dict) else None
            municipios.append({"cod": m["cod"], "nome": m["nome"], "hospitais": n or 0})
        else:
            recusados.append(nome)
    est = os.path.join(dossie, "estado_ES_rejeicao_por_cnes.json")
    if os.path.isfile(est):
        if _gravar(saida, "rede_rejeicao_es.json", json.load(open(est, encoding="utf-8"))):
            gravados.append("rede_rejeicao_es.json")
        else:
            recusados.append("rede_rejeicao_es.json")
    if _gravar(saida, "rede_indice.json", {"gerado_em": idx.get("gerado_em"), "municipios": municipios}):
        gravados.append("rede_indice.json")
    return {"gravados": gravados, "recusados": recusados}
