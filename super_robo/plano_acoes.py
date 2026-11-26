"""Lancamentos do gestor no plano de avanco do faturamento (arquivo CSV opcional).

O gestor lanca, por CNES e codigo de erro, o que o relatorio de AIH rejeitadas do hospital mostrou e o que decidiu: acao, prazo, responsavel,
status, quantidade e valor em R$, ganho estimado. Nada e inventado: sem arquivo, o plano segue com as estimativas e [PREENCHER].

LGPD: o arquivo NAO aceita numero de AIH, CPF, CNS nem qualquer sequencia de 11 ou mais digitos; linhas com isso sao recusadas por inteiro.
Responsavel: usar cargo ou setor, nunca nome de pessoa.

Arquivo: <PARTELLI_BASE>/entrada/plano_acoes.csv (ou a variavel PLANO_ACOES). Separador ; ou , (detectado). Modelo em config/plano_acoes_modelo.csv.
Colunas: cnes;critica;codigo_erro;descricao_erro;qtd_aih;valor_rs;acao;prazo;responsavel;status;prioridade;ganho_estimado_rs;fonte
"""
import csv, io, os, re
from datetime import datetime

BASE = os.environ.get("PARTELLI_BASE", os.path.join(os.path.expanduser("~"), "partelli"))
ARQUIVO = os.environ.get("PLANO_ACOES", os.path.join(BASE, "entrada", "plano_acoes.csv"))
COLUNAS = ["cnes", "critica", "codigo_erro", "descricao_erro", "qtd_aih", "valor_rs", "acao", "prazo", "responsavel", "status", "prioridade", "ganho_estimado_rs", "fonte"]
STATUS = {"a iniciar": "A iniciar", "em andamento": "Em andamento", "concluida": "Concluida", "concluída": "Concluida", "cancelada": "Cancelada"}
PRIORIDADE = {"alta": "Alta", "media": "Media", "média": "Media", "baixa": "Baixa"}
SEQ_LONGA = re.compile(r"\d{11,}|\d{3}\.\d{3}\.\d{3}-\d{2}")


def _numero(txt):
    t = txt.strip().replace("R$", "").replace(" ", "")
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    return float(t)


def _linha(l):
    """Valida uma linha. Devolve (lancamento, None) ou (None, motivo)."""
    if any(SEQ_LONGA.search(v or "") for v in l.values()):
        return None, "sequencia de 11 ou mais digitos (possivel AIH, CPF ou CNS): linha recusada por LGPD"
    cnes = (l.get("cnes") or "").strip()
    if not re.fullmatch(r"\d{7}", cnes):
        return None, "cnes deve ter 7 digitos"
    critica = (l.get("critica") or "").strip().upper()
    cod = (l.get("codigo_erro") or "").strip()
    if not critica and not cod:
        return None, "informe critica (ex.: C06) ou codigo_erro"
    out = {"cnes": cnes, "critica": critica, "codigo_erro": cod, "descricao_erro": (l.get("descricao_erro") or "").strip() or None,
           "acao": (l.get("acao") or "").strip() or None, "responsavel": (l.get("responsavel") or "").strip() or None}
    st = (l.get("status") or "").strip().lower()
    if st and st not in STATUS:
        return None, f"status invalido: use {sorted(set(STATUS.values()))}"
    out["status"] = STATUS.get(st)
    pr = (l.get("prioridade") or "").strip().lower()
    if pr and pr not in PRIORIDADE:
        return None, "prioridade invalida: use Alta, Media ou Baixa"
    out["prioridade"] = PRIORIDADE.get(pr)
    prazo = (l.get("prazo") or "").strip()
    if prazo:
        try:
            datetime.strptime(prazo, "%d/%m/%Y")
        except ValueError:
            return None, "prazo deve ser DD/MM/AAAA"
    out["prazo"] = prazo or None
    for campo in ("qtd_aih", "valor_rs", "ganho_estimado_rs"):
        v = (l.get(campo) or "").strip()
        try:
            out[campo] = (int(_numero(v)) if campo == "qtd_aih" else round(_numero(v), 2)) if v else None
        except ValueError:
            return None, f"{campo} nao e numero"
        if out[campo] is not None and out[campo] < 0:
            return None, f"{campo} negativo"
    out["fonte"] = (l.get("fonte") or "").strip() or None
    if (out["valor_rs"] is not None or out["ganho_estimado_rs"] is not None or out["qtd_aih"] is not None) and not out["fonte"]:
        return None, "valor, quantidade ou ganho exigem a coluna fonte (regra da plataforma: sem fonte nao entra)"
    return out, None


def carregar(caminho=None):
    """Devolve {situacao, lancamentos, recusadas, linhas_lidas}. Arquivo ausente nao e erro."""
    caminho = caminho or ARQUIVO
    if not os.path.isfile(caminho):
        return {"situacao": "A confirmar: arquivo de lancamentos do gestor nao encontrado (opcional)", "lancamentos": [], "recusadas": [], "linhas_lidas": 0}
    with open(caminho, encoding="utf-8-sig", newline="") as f:
        texto = f.read()
    primeira = texto.splitlines()[0] if texto.strip() else ""
    delim = ";" if primeira.count(";") >= primeira.count(",") else ","
    leitor = csv.DictReader(io.StringIO(texto), delimiter=delim)
    faltam = [c for c in ("cnes",) if c not in (leitor.fieldnames or [])]
    if faltam:
        return {"situacao": f"Arquivo sem a coluna obrigatoria: {faltam}. Use o modelo config/plano_acoes_modelo.csv", "lancamentos": [], "recusadas": [], "linhas_lidas": 0}
    lanc, rec, n = [], [], 0
    for i, l in enumerate(leitor, start=2):
        if not any((v or "").strip() for v in l.values()):
            continue
        n += 1
        ok, motivo = _linha({k: v for k, v in l.items() if k in COLUNAS})
        (lanc.append(ok) if ok else rec.append({"linha": i, "motivo": motivo}))
    return {"situacao": f"{len(lanc)} lancamento(s) aplicado(s), {len(rec)} recusado(s)", "lancamentos": lanc, "recusadas": rec, "linhas_lidas": n}


def aplicar(itens, cnes, lancamentos):
    """Sobrepoe os lancamentos do CNES aos itens do plano (por critica ou C07-<codigo>) e cria itens para o que nao casou."""
    usados = set()
    for k, lc in enumerate(lancamentos):
        if lc["cnes"] != cnes:
            continue
        alvo = f"{lc['critica']}-{cnes}" if lc["critica"] else f"C07-{lc['codigo_erro']}-{cnes}"
        item = next((x for x in itens if x["critica_vinculada"] == alvo), None)
        if item is None:
            item = {"acao": "[PREENCHER: acao]", "critica_vinculada": alvo if lc["critica"] else f"L-{lc['codigo_erro']}-{cnes}",
                    "prioridade": "Media", "ganho_estimado_rs": None, "perda_por_rejeicao_rs": None, "prazo": "A definir pelo gestor",
                    "responsavel": "A definir pelo gestor", "status": "A iniciar", "origem": "Lancamento do gestor"}
            itens.append(item)
        for campo in ("acao", "prazo", "responsavel", "status", "prioridade", "ganho_estimado_rs", "descricao_erro", "fonte"):
            if lc.get(campo) is not None:
                item[campo if campo != "fonte" else "fonte_lancamento"] = lc[campo]
        if lc.get("qtd_aih") is not None:
            item["qtd_aih_lancada"] = lc["qtd_aih"]
        if lc.get("valor_rs") is not None:
            item["perda_por_rejeicao_rs"] = lc["valor_rs"]
            item["obs_perda"] = f"Valor lancado pelo gestor (fonte: {lc['fonte']}). Substitui a estimativa."
        item["lancado_pelo_gestor"] = True
        usados.add(k)
    ordem = {"Alta": 0, "Media": 1, "Baixa": 2}
    itens.sort(key=lambda i: ordem[i["prioridade"]])
    return itens
