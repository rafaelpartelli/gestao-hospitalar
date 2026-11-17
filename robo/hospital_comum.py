"""Funcoes comuns dos coletores do modulo Gestao Hospitalar (Partelli).
Somente biblioteca padrao. Reaproveita comum.py, dbc.py e cnes_ftp.py da Sala de Gestao.

Protecoes do plano gratuito da Oracle (Always Free):
- baixa cada arquivo para o disco e le por mmap (memoria baixa, cabe na VM Micro de 1 GB);
- orcamento mensal de trafego (padrao 6 GB) registrado em arquivo de estado;
- recusa rodar com menos de 3 GB livres em disco;
- nao baixa de novo arquivo ja processado (mesmo nome e tamanho);
- um coletor por vez (trava por flock, feita no script de agendamento).
Nenhum dado pessoal e gravado: so contagens e valores agregados por CNES."""
import ftplib, json, mmap, os, re, shutil, tempfile, time
from datetime import datetime
from comum import espera_para, agora, BRT, escrever_json, ler_json

HOST = "ftp.datasus.gov.br"
PASTA_CNES = "/dissemin/publicos/CNES/200508_/Dados"
PASTA_SIH = "/dissemin/publicos/SIHSUS/200801_/Dados"
PASTA_SIA = "/dissemin/publicos/SIASUS/200801_/Dados"

ORCAMENTO_GB = float(os.environ.get("ORCAMENTO_TRAFEGO_GB", "6"))
DISCO_MIN_GB = float(os.environ.get("DISCO_MINIMO_GB", "3"))
ESTADO = os.environ.get("PARTELLI_ESTADO", os.path.join(os.path.expanduser("~"), ".partelli", "hospital"))
SAIDA = os.environ.get("PARTELLI_DADOS", "dados")          # pasta hospital/dados do site
CONFIG = os.environ.get("PARTELLI_CONFIG", "config")       # pasta privada com hospitais.json

# Campos que nunca sao lidos nem gravados (dado pessoal ou de contato).
PROIBIDOS = {"CPF_PROF", "CNS_PROF", "NOMEPROF", "CPF_CNPJ", "CNPJ_MAN", "COD_CEP", "CEP", "TELEFONE", "EMAIL", "ENDERECO",
             "NUMERO", "BAIRRO", "NASC", "NOME", "N_AIH", "NUM_PROC", "CNS_PAC", "CPFPAC"}


class ErroColeta(RuntimeError):
    pass


def cnes_valido(c):
    return bool(re.fullmatch(r"\d{7}", str(c or "").strip()))


def carregar_config(caminho=None):
    cfg = ler_json(caminho or os.path.join(CONFIG, "hospitais.json"))
    lista = [h for h in cfg.get("hospitais", []) if cnes_valido(h.get("cnes"))]
    return {"meses": int(cfg.get("meses", 2)), "hospitais": lista}


def por_uf(hospitais):
    r = {}
    for h in hospitais:
        r.setdefault(h["uf"].upper(), set()).add(h["cnes"].strip())
    return r


# ---------------------------------------------------------------- guardas do plano gratuito
def _arq_trafego():
    os.makedirs(ESTADO, exist_ok=True)
    return os.path.join(ESTADO, f"trafego_{datetime.now(BRT):%Y%m}.json")


def trafego_mes_bytes():
    try:
        return int(ler_json(_arq_trafego()).get("bytes", 0))
    except (OSError, ValueError):
        return 0


def registrar_trafego(n):
    escrever_json(_arq_trafego(), {"bytes": trafego_mes_bytes() + int(n), "atualizado": agora(), "orcamento_gb": ORCAMENTO_GB})


def checar_guardas(bytes_previstos=0, destino="."):
    livre = shutil.disk_usage(destino).free / 1e9
    if livre < DISCO_MIN_GB:
        raise ErroColeta(f"disco livre {livre:.1f} GB abaixo do minimo de {DISCO_MIN_GB} GB")
    usado = trafego_mes_bytes() + bytes_previstos
    if usado > ORCAMENTO_GB * 1e9:
        raise ErroColeta(f"orcamento mensal de trafego excedido ({usado / 1e9:.2f} de {ORCAMENTO_GB} GB)")


# ---------------------------------------------------------------- estado de arquivos ja processados
def _arq_feito():
    os.makedirs(ESTADO, exist_ok=True)
    return os.path.join(ESTADO, "arquivos_processados.json")


def ja_processado(chave, tamanho):
    try:
        return ler_json(_arq_feito()).get(chave) == tamanho
    except (OSError, ValueError):
        return False


def marcar_processado(chave, tamanho):
    try:
        d = ler_json(_arq_feito())
    except (OSError, ValueError):
        d = {}
    d[chave] = tamanho
    escrever_json(_arq_feito(), d)


# ---------------------------------------------------------------- FTP
def conectar(tentativas=4, pausa=5):
    ultimo = None
    for i in range(tentativas):
        try:
            f = ftplib.FTP(HOST, timeout=120)
            f.login()
            return f
        except Exception as e:
            ultimo = e
            if i + 1 < tentativas:
                time.sleep(espera_para(e, i, pausa))
    raise ultimo


_CACHE_LISTA = {}


def listar(pasta, prefixo=""):
    """Nomes (sem pasta) dos arquivos .dbc da pasta que comecam com o prefixo (filtro feito aqui, sem depender de curinga no servidor).
    A listagem da pasta e guardada em memoria durante a execucao para nao repetir a consulta."""
    if pasta not in _CACHE_LISTA:
        f = conectar()
        try:
            _CACHE_LISTA[pasta] = [n.split("/")[-1] for n in f.nlst(pasta)]
        finally:
            try:
                f.quit()
            except Exception:
                pass
    pref = prefixo.upper()
    return [n for n in _CACHE_LISTA[pasta] if n.lower().endswith(".dbc") and n.upper().startswith(pref)]


def tamanho_remoto(pasta, nome):
    f = conectar()
    try:
        f.voidcmd("TYPE I")
        return f.size(f"{pasta}/{nome}") or 0
    except Exception:
        return 0
    finally:
        try:
            f.quit()
        except Exception:
            pass


class Baixado:
    """Arquivo baixado em disco temporario e mapeado em memoria. Use com 'with'."""

    def __init__(self, caminho, mapa, tamanho):
        self.caminho, self.dados, self.tamanho, self._mapa = caminho, mapa, tamanho, mapa

    def __enter__(self):
        return self.dados

    def __exit__(self, *a):
        try:
            self._mapa.close()
        finally:
            try:
                os.remove(self.caminho)
            except OSError:
                pass


def baixar(pasta, nome, tamanho_previsto=0, tentativas=4, pausa=5):
    checar_guardas(tamanho_previsto)
    os.makedirs(ESTADO, exist_ok=True)
    ultimo = None
    for i in range(tentativas):
        f, tmp = None, None
        try:
            f = conectar()
            f.voidcmd("TYPE I")
            fd, tmp = tempfile.mkstemp(prefix="hosp_", suffix=".dbc", dir=os.environ.get("TMPDIR") or None)
            with os.fdopen(fd, "wb") as saida:
                f.retrbinary(f"RETR {pasta}/{nome}", saida.write, blocksize=1 << 16)
            tam = os.path.getsize(tmp)
            if tam < 100:
                raise ErroColeta(f"arquivo {nome} pequeno demais ({tam} bytes)")
            registrar_trafego(tam)
            with open(tmp, "rb") as fh:
                mapa = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
            return Baixado(tmp, mapa, tam)
        except Exception as e:
            ultimo = e
            if tmp and os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass
            if i + 1 < tentativas:
                time.sleep(espera_para(e, i, pausa))
        finally:
            if f is not None:
                try:
                    f.close()
                except Exception:
                    pass
    raise ultimo


# ---------------------------------------------------------------- competencias
def competencias_recentes(nomes, prefixo, uf, meses):
    """De nomes como RDES2609.dbc (ou PAES2609a.dbc) devolve as 'meses' competencias AAMM mais recentes, da mais nova para a mais antiga."""
    rx = re.compile(rf"^{prefixo}{uf}(\d{{4}})[a-z]?\.dbc$", re.I)
    comps = sorted({m.group(1) for n in nomes if (m := rx.match(n))}, reverse=True)
    return comps[:meses]


def aamm_para_mmaaaa(aamm):
    return f"{aamm[2:]}/20{aamm[:2]}"


def aamm_para_chave(aamm):
    return "20" + aamm  # 2609 -> 202609


# ---------------------------------------------------------------- saida
def atualizar_hospital(cnes, chave_comp, bloco, valor):
    """Le dados/hospital/<cnes>.json, atualiza competencias[chave_comp][bloco] (ou raiz se chave_comp for None) e grava de forma atomica."""
    os.makedirs(SAIDA, exist_ok=True)
    caminho = os.path.join(SAIDA, f"{cnes}.json")
    try:
        d = ler_json(caminho)
    except (OSError, ValueError):
        d = {"cnes": cnes, "competencias": {}}
    if chave_comp is None:
        d[bloco] = valor
    else:
        d.setdefault("competencias", {}).setdefault(chave_comp, {})[bloco] = valor
    d["atualizado"] = agora()
    tmp = caminho + ".tmp"
    escrever_json(tmp, d)
    os.replace(tmp, caminho)
    return caminho


def atualizar_indice(hospitais):
    """Indice publico com CNES, UF e competencias disponiveis. Nome so se autorizado na configuracao."""
    itens = []
    for h in hospitais:
        cnes = h["cnes"].strip()
        try:
            d = ler_json(os.path.join(SAIDA, f"{cnes}.json"))
            comps = sorted(d.get("competencias", {}))
        except (OSError, ValueError):
            comps = []
        itens.append({"cnes": cnes, "uf": h["uf"].upper(), "nome": h.get("nome") if h.get("autorizado") else None, "competencias": comps})
    escrever_json(os.path.join(SAIDA, "indice.json"), {"gerado_em": agora(), "hospitais": itens})


def campos_presentes(dados, desejados, obrigatorios, transitorios=()):
    """Devolve (campos a ler, ausentes opcionais). Levanta ErroColeta se faltar campo obrigatorio.
    Campos proibidos so passam se listados em 'transitorios' (uso em memoria, nunca gravado)."""
    import dbc
    nomes = {c[0] for c in dbc.cabecalho(dados)["campos"]}
    falta = [c for c in obrigatorios if c not in nomes]
    if falta:
        raise ErroColeta(f"campos obrigatorios ausentes: {falta}. Campos do arquivo: {sorted(nomes)}")
    ler = [c for c in desejados if c in nomes and (c not in PROIBIDOS or c in transitorios)]
    return ler, [c for c in desejados if c not in nomes], sorted(nomes)


def primeiro_campo(nomes_arquivo, candidatos):
    for c in candidatos:
        if c in nomes_arquivo:
            return c
    return None
