#!/usr/bin/env python3
"""Tabelas auxiliares oficiais do CNES (FTP do DATASUS, pasta Auxiliar, arquivo TAB_CNES.zip, cerca de 128 MB).
Extrai somente tabelas de descricao de codigos (habilitacao, incentivo, servico/classificacao, equipamento, leito,
instalacao). Conteudo publico, sem dado pessoal. Saida: <PARTELLI_DADOS>/tabelas_cnes.json (chaves e textos como vieram do arquivo).
O zip so e baixado de novo se o JSON nao existir ou tiver mais de 60 dias (use --forcar para ignorar).
Modos: sem argumento (extrai), --listar (mostra o conteudo do zip), --forcar. Status: Em teste."""
import json, os, re, struct, sys, zipfile
from datetime import datetime, timedelta
import hospital_comum as H
from comum import agora, escrever_json, BRT

PASTA_AUX = H.PASTA_CNES.rsplit("/", 1)[0] + "/Auxiliar"
ARQUIVO = "TAB_CNES.zip"
VALIDADE_DIAS = 60

CNV = {"equipamento": "CNV/equipam2508.cnv", "tipo_equipamento": "CNV/Equip_Tp.cnv", "especialidade_leito": "CNV/Esp_leit.CNV",
       "tipo_leito": "CNV/tip1leit.cnv", "indicador_sus": "CNV/IND_SUS.CNV"}
DBF = {"habilitacao": "DBF/HABILITA.DBF", "incentivo": "DBF/incentivos.dbf", "servico_classificacao": "DBF/S_CLASSEA.dbf",
       "servico_classificacao_n": "DBF/S_CLASSEN.dbf", "tipo_equipamento_dbf": "DBF/TP_EQUIPAM.dbf"}
DEF_LINHAS = {"instalacoes_def": ("Estabelecimento.def", re.compile(r"QTINST|CENTRCIR|CENTROBS|CENTRNEO|URGEMERG|ATENDAMB|ATENDHOS", re.I)),
              "servico_def": ("Servico_Especializado_200803_.def", re.compile(r"SERV|CLASS", re.I))}


def parse_cnv(texto):
    """Linhas 'seq  descricao  codigo' (codigo = ultimo termo). A primeira linha e o cabecalho do TabWin."""
    out = {}
    for ln in texto.splitlines()[1:]:
        if not ln.strip() or ln.lstrip().startswith(";"):
            continue
        m = re.match(r"^\s*\d+\s+(.*\S)\s+(\S+)\s*$", ln)
        if m:
            out.setdefault(m.group(2), m.group(1).strip())
    return out


def ler_dbf(dados):
    """Leitor minimo de DBF simples (tabelas pequenas de descricao). Devolve lista de dicts com texto em latin-1."""
    n, tam_cab, tam_reg = struct.unpack("<IHH", dados[4:12])
    campos, pos = [], 32
    while pos < len(dados) and dados[pos] != 0x0D:
        nome = dados[pos:pos + 11].split(b"\0")[0].decode("latin-1")
        campos.append((nome, dados[pos + 16]))
        pos += 32
    regs = []
    for i in range(n):
        ini = tam_cab + i * tam_reg
        reg = dados[ini:ini + tam_reg]
        if len(reg) < tam_reg or reg[:1] == b"*":
            continue
        off, d = 1, {}
        for nome, tam in campos:
            d[nome] = reg[off:off + tam].decode("latin-1").strip()
            off += tam
        regs.append(d)
    return regs


def tabela_dbf(dados):
    regs = ler_dbf(dados)
    if not regs:
        return {}
    ch = list(regs[0].keys())
    return {r[ch[0]]: r[ch[1]] for r in regs if r.get(ch[0])}


def _membro(z, nome):
    achados = [i for i in z.namelist() if i.lower() == nome.lower()]
    return z.read(achados[0]) if achados else None


def extrair(zip_path, tamanho):
    saida = {"fonte": "TAB_CNES.zip (FTP DATASUS, pasta Auxiliar)", "coletado_em": agora(), "tamanho_zip": tamanho,
             "status_fonte": "Em teste", "tabelas": {}, "ausentes": []}
    with zipfile.ZipFile(zip_path) as z:
        for chave, nome in CNV.items():
            b = _membro(z, nome)
            if b is None:
                saida["ausentes"].append(nome); continue
            saida["tabelas"][chave] = parse_cnv(b.decode("latin-1"))
        for chave, nome in DBF.items():
            b = _membro(z, nome)
            if b is None:
                saida["ausentes"].append(nome); continue
            saida["tabelas"][chave] = tabela_dbf(b)
        for chave, (nome, rx) in DEF_LINHAS.items():
            b = _membro(z, nome)
            if b is None:
                saida["ausentes"].append(nome); continue
            saida["tabelas"][chave] = [l.strip() for l in b.decode("latin-1").splitlines() if rx.search(l)]
    return saida


def cobertura(saida):
    """Quantos codigos ja coletados nos JSON dos hospitais encontram descricao (guia para ajustar a ligacao)."""
    t = saida["tabelas"]
    linhas = []
    for nome in sorted(os.listdir(H.SAIDA)) if os.path.isdir(H.SAIDA) else []:
        if not re.fullmatch(r"\d{7}\.json", nome):
            continue
        c = (json.load(open(os.path.join(H.SAIDA, nome), encoding="utf-8")).get("cnes") or {})
        def conta(itens, f):
            return sum(1 for i in itens if f(i)), len(itens)
        hab = conta((c.get("habilitacoes") or {}).get("itens", []), lambda i: i.get("sgruphab") in t.get("habilitacao", {}))
        inc = conta((c.get("incentivos") or {}).get("itens", []), lambda i: i.get("sgruphab") in t.get("incentivo", {}))
        lei = conta((c.get("leitos") or {}).get("itens", []), lambda i: i.get("cod_leito") in t.get("especialidade_leito", {}))
        eq = conta((c.get("equipamentos") or {}).get("itens", []),
                   lambda i: any(k in t.get("equipamento", {}) or k in t.get("tipo_equipamento", {}) for k in (i["tipo"] + i["codigo"], i["tipo"].zfill(2) + i["codigo"].zfill(2), i["codigo"].zfill(4))))
        sv = conta((c.get("servicos") or {}).get("itens", []),
                   lambda i: (i["servico"].zfill(3) + i["classificacao"].zfill(3)) in t.get("servico_classificacao_n", {}))
        linhas.append(f"{nome[:7]}: habilitacoes {hab[0]}/{hab[1]}, incentivos {inc[0]}/{inc[1]}, leitos {lei[0]}/{lei[1]}, equipamentos {eq[0]}/{eq[1]}, servicos {sv[0]}/{sv[1]}")
    return linhas


def recente(caminho):
    try:
        d = json.load(open(caminho, encoding="utf-8"))
        return datetime.now(BRT) - datetime.fromisoformat(d["coletado_em"]) < timedelta(days=VALIDADE_DIAS)
    except Exception:
        return False


def main():
    alvo = os.path.join(H.SAIDA, "tabelas_cnes.json")
    if "--listar" in sys.argv:
        b = H.baixar(PASTA_AUX, ARQUIVO)
        try:
            with zipfile.ZipFile(b.caminho) as z:
                print(f"{ARQUIVO}: {b.tamanho} bytes, {len(z.namelist())} arquivos")
                for i in z.infolist():
                    print(f"- {i.filename} ({i.file_size} bytes)")
        finally:
            b.__exit__()
        return 0
    if "--forcar" not in sys.argv and recente(alvo):
        print("tabelas_cnes.json com menos de 60 dias: nada a baixar"); return 0
    b = H.baixar(PASTA_AUX, ARQUIVO)
    try:
        saida = extrair(b.caminho, b.tamanho)
    finally:
        b.__exit__()
    os.makedirs(H.SAIDA, exist_ok=True)
    escrever_json(alvo, saida)
    print("tabelas:", {k: (len(v) if hasattr(v, "__len__") else v) for k, v in saida["tabelas"].items()}, "| ausentes:", saida["ausentes"])
    for ln in cobertura(saida):
        print(ln)
    return 0


if __name__ == "__main__":
    sys.exit(main())
