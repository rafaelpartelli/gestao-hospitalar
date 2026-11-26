"""Exporta do dossie os JSON que o site (painel Gestao hospitalar) le: rede_indice.json, rede_<cod>.json (hospitais), rede_rejeicao_es.json e, por municipio,
uma secao por arquivo: rede_<cod>_producao.json, _cnes.json, _financeiro.json, _recursos.json, _territorio.json e _resumo.json (populacao e pendencias).

Entra tudo que o robo colhe e valida, sempre agregado. Guarda de privacidade: o arquivo e recusado se tiver
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


SECOES_SITE = {"producao": "producao", "cnes": "cnes", "financeiro": "financeiro", "recursos": "recursos", "territorio": "territorio_saude", "estab": "estabelecimentos_producao"}


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
            sec = d.get("secoes") or {}
            disp = []
            for curto, chave in SECOES_SITE.items():
                if chave not in sec:
                    continue
                nm = f"rede_{m['cod']}_{curto}.json"
                if _gravar(saida, nm, {"gerado_em": d.get("gerado_em"), "municipio": {"cod": m["cod"], "nome": m["nome"]}, "secao": sec[chave]}):
                    gravados.append(nm)
                    disp.append(curto)
                else:
                    recusados.append(nm)
            nm = f"rede_{m['cod']}_resumo.json"
            if _gravar(saida, nm, {"gerado_em": d.get("gerado_em"), "municipio": {"cod": m["cod"], "nome": m["nome"], "populacao": (d.get("municipio") or {}).get("populacao")},
                                   "pendencias": d.get("pendencias") or []}):
                gravados.append(nm)
                disp.append("resumo")
            else:
                recusados.append(nm)
            n = hosp.get("total") if isinstance(hosp, dict) else None
            municipios.append({"cod": m["cod"], "nome": m["nome"], "hospitais": n or 0, "secoes": disp, "pendencias": len(d.get("pendencias") or [])})
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
