#!/usr/bin/env python3
"""Painel FTP do Serverrobo (Partelli). Servidor HTTP local, somente biblioteca padrao.

Funcoes: explorar o FTP publico do DATASUS (somente /dissemin/publicos/), baixar arquivos com as mesmas
protecoes dos robos (orcamento de trafego e disco), listar e apagar os downloads, ver o status e disparar coletas.
Seguranca: bind local por padrao, entrada por token, cookie HttpOnly SameSite=Strict, limite de tentativas,
nenhuma credencial no codigo (token em /etc/partelli/ftp.env). Nao le dado pessoal de arquivo algum.
"""
import ftplib, hashlib, hmac, json, os, posixpath, re, shutil, subprocess, sys, threading, time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

AQUI = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("PARTELLI_BASE", os.path.join(os.path.expanduser("~"), "partelli"))
for p in (os.path.join(AQUI, "..", "robo"), os.path.join(BASE, "sala-gestao", "robo")):
    if os.path.isdir(p):
        sys.path.insert(0, os.path.abspath(p))
try:
    import hospital_comum as H
except Exception:  # painel sobe mesmo sem os robos, com protecoes basicas
    H = None

HOST_FTP = "ftp.datasus.gov.br"
RAIZ = "/dissemin/publicos/"
DOWNLOADS = os.environ.get("PAINEL_DOWNLOADS", os.path.join(BASE, "ftp_downloads"))
LOGS = os.path.join(BASE, "log")
COLETOR = os.environ.get("PARTELLI_COLETOR", "/usr/local/bin/partelli-coleta")
MODOS = {"diaria", "semanal", "tudo", "espelho"}
REPO_HOSP = os.path.abspath(os.path.join(AQUI, "..", "hospital"))     # codigo da pagina hospitalar (no proprio notebook)
DADOS_HOSP = os.environ.get("PAINEL_DADOS", os.path.join(BASE, "dados_repo"))  # JSON gerados pelos robos
_MIME = {".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".json": "application/json; charset=utf-8"}
LIMITE_CONFIRMAR = 200 * 1024 * 1024
ORC_GB = H.ORCAMENTO_GB if H else 6.0
DISCO_MIN_GB = H.DISCO_MIN_GB if H else 3.0
COOKIE = "partelli_painel"
SESSAO_S = 8 * 3600
TOKEN = os.environ.get("PAINEL_TOKEN", "")
SEGREDO = os.environ.get("PAINEL_SEGREDO", "").encode()
_falhas = {}
_trava_dl = threading.Lock()
_dl = {"estado": "ocioso"}
_cache_ls = {}
_proc = {"p": None, "modo": None}


# ------------------------------------------------------------------ seguranca
def caminho_ftp_valido(p):
    """Normaliza e confere a lista branca. Retorna o caminho ou None."""
    if not isinstance(p, str) or "\x00" in p or "\\" in p or len(p) > 400:
        return None
    n = posixpath.normpath("/" + p.strip("/")) + "/"
    if ".." in p.split("/") or not n.startswith(RAIZ):
        return None
    return n.rstrip("/") or "/"


def nome_local_valido(nome):
    return isinstance(nome, str) and re.fullmatch(r"[A-Za-z0-9._-]{1,120}", nome) is not None and nome not in (".", "..")


def assinar(exp):
    return f"{exp}.{hmac.new(SEGREDO, str(exp).encode(), hashlib.sha256).hexdigest()}"


def sessao_ok(cookie):
    try:
        exp, ass = cookie.split(".", 1)
        return int(exp) > time.time() and hmac.compare_digest(ass, assinar(int(exp)).split(".", 1)[1])
    except Exception:
        return False


def token_ok(t):
    return bool(TOKEN) and isinstance(t, str) and hmac.compare_digest(t.encode(), TOKEN.encode())


def bloqueado(ip):
    agora = time.time()
    _falhas[ip] = [t for t in _falhas.get(ip, []) if agora - t < 60]
    return len(_falhas[ip]) >= 5


# ------------------------------------------------------------------ FTP
def conectar():
    f = ftplib.FTP(HOST_FTP, timeout=60)
    f.login()
    return f


_UNIX = re.compile(r"^([\-dl])[rwxsStT\-]{9}\S*\s+\d+\s+\S+\s+\S+\s+(\d+)\s+(\w{3}\s+\d+\s+[\d:]+)\s+(.+)$")
_DOS = re.compile(r"^(\d{2}-\d{2}-\d{2,4})\s+(\d{1,2}:\d{2}[AP]M)\s+(<DIR>|\d+)\s+(.+)$")


def parse_lista(linhas):
    """Entende LIST estilo Unix e estilo Windows IIS. Retorna [{nome, tipo, tamanho, data}]."""
    saida = []
    for ln in linhas:
        ln = ln.rstrip("\r\n")
        m = _UNIX.match(ln)
        if m:
            tipo = "dir" if m.group(1) in "dl" else "arq"
            saida.append({"nome": m.group(4).split(" -> ")[0], "tipo": tipo, "tamanho": int(m.group(2)), "data": m.group(3)})
            continue
        m = _DOS.match(ln)
        if m:
            dire = m.group(3) == "<DIR>"
            saida.append({"nome": m.group(4), "tipo": "dir" if dire else "arq", "tamanho": 0 if dire else int(m.group(3)),
                          "data": m.group(1) + " " + m.group(2)})
    return saida


def listar_ftp(caminho):
    agora = time.time()
    c = _cache_ls.get(caminho)
    if c and agora - c[0] < 300:
        return c[1]
    f = conectar()
    try:
        itens = []
        try:
            for nome, fatos in f.mlsd(caminho, facts=["type", "size", "modify"]):
                if nome in (".", ".."):
                    continue
                itens.append({"nome": nome, "tipo": "dir" if fatos.get("type") in ("dir", "cdir", "pdir") else "arq",
                              "tamanho": int(fatos.get("size", 0) or 0), "data": fatos.get("modify", "")})
        except ftplib.error_perm:
            linhas = []
            f.cwd(caminho)
            f.retrlines("LIST", linhas.append)
            itens = parse_lista(linhas)
    finally:
        try:
            f.quit()
        except Exception:
            pass
    itens.sort(key=lambda i: (i["tipo"] != "dir", i["nome"].lower()))
    _cache_ls[caminho] = (agora, itens)
    return itens


def trafego_gb():
    return (H.trafego_mes_bytes() if H else 0) / 1e9


def disco_livre_gb():
    os.makedirs(DOWNLOADS, exist_ok=True)
    return shutil.disk_usage(DOWNLOADS).free / 1e9


def checar(bytes_previstos):
    if disco_livre_gb() - bytes_previstos / 1e9 < DISCO_MIN_GB:
        raise RuntimeError(f"disco livre abaixo do minimo de {DISCO_MIN_GB:g} GB")
    if trafego_gb() + bytes_previstos / 1e9 > ORC_GB:
        raise RuntimeError(f"orcamento mensal de trafego excedido ({trafego_gb():.2f} de {ORC_GB:g} GB)")


def tamanho_remoto(f, caminho):
    try:
        f.voidcmd("TYPE I")
        return int(f.size(caminho) or 0)
    except Exception:
        return 0


def _baixar(caminho, nome, tamanho):
    destino = os.path.join(DOWNLOADS, nome)
    parcial = destino + ".parte"
    recebido = 0
    try:
        f = conectar()
        f.voidcmd("TYPE I")
        with open(parcial, "wb") as saida:
            def escreve(b):
                nonlocal recebido
                saida.write(b)
                recebido += len(b)
                _dl.update({"recebido": recebido})
            f.retrbinary("RETR " + caminho, escreve, 64 * 1024)
        try:
            f.quit()
        except Exception:
            pass
        os.replace(parcial, destino)
        _dl.update({"estado": "concluido", "recebido": recebido, "fim": datetime.now().isoformat(timespec="seconds")})
    except Exception as e:
        _dl.update({"estado": "erro", "erro": str(e)[:300]})
        try:
            os.remove(parcial)
        except OSError:
            pass
    finally:
        if H and recebido:
            H.registrar_trafego(recebido)
        _trava_dl.release()


def iniciar_download(caminho, confirmar):
    nome = posixpath.basename(caminho)
    if not nome_local_valido(nome):
        raise ValueError("nome de arquivo invalido")
    if not _trava_dl.acquire(blocking=False):
        raise RuntimeError("ja existe um download em andamento")
    try:
        f = conectar()
        try:
            tam = tamanho_remoto(f, caminho)
        finally:
            try:
                f.quit()
            except Exception:
                pass
        if tam > LIMITE_CONFIRMAR and not confirmar:
            _trava_dl.release()
            return {"precisa_confirmar": True, "tamanho": tam}
        checar(tam)
        os.makedirs(DOWNLOADS, exist_ok=True)
        _dl.clear()
        _dl.update({"estado": "baixando", "nome": nome, "total": tam, "recebido": 0, "inicio": datetime.now().isoformat(timespec="seconds")})
        threading.Thread(target=_baixar, args=(caminho, nome, tam), daemon=True).start()
        return {"iniciado": True, "tamanho": tam}
    except Exception:
        if _trava_dl.locked() and _dl.get("estado") != "baixando":
            _trava_dl.release()
        raise


# ------------------------------------------------------------------ local
def arquivos_locais():
    os.makedirs(DOWNLOADS, exist_ok=True)
    itens = []
    for n in sorted(os.listdir(DOWNLOADS)):
        p = os.path.join(DOWNLOADS, n)
        if os.path.isfile(p):
            st = os.stat(p)
            itens.append({"nome": n, "tamanho": st.st_size, "data": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="minutes")})
    return itens


def cabecalho_dbc(nome):
    """Somente nomes e tipos de campo e a contagem de registros. Nenhum valor e lido."""
    import dbc
    with open(os.path.join(DOWNLOADS, nome), "rb") as a:
        topo = a.read(65536)
    cab = dbc.cabecalho(topo)
    proib = getattr(H, "PROIBIDOS", set()) if H else set()
    return {"registros": cab["registros"], "campos": [{"nome": c[0], "tipo": c[1], "tam": c[2], "sensivel": c[0] in proib} for c in cab["campos"]]}


def ultima_linhas(caminho, n=60):
    try:
        with open(caminho, "rb") as a:
            a.seek(0, 2)
            a.seek(max(0, a.tell() - 16000))
            return a.read().decode("utf-8", "replace").splitlines()[-n:]
    except OSError:
        return []


def status():
    timers = []
    try:
        r = subprocess.run(["systemctl", "list-timers", "--no-pager", "--no-legend", "partelli-*"], capture_output=True, text=True, timeout=10)
        timers = [l.strip() for l in r.stdout.splitlines() if "partelli" in l]
    except Exception:
        pass
    ult = {}
    for m in MODOS:
        p = os.path.join(BASE, "estado", f"ultima_execucao_{m}.txt")
        if os.path.isfile(p):
            ult[m] = open(p, encoding="utf-8", errors="replace").read().strip()[:200]
    rodando = _proc["p"] is not None and _proc["p"].poll() is None
    tg = trafego_gb()
    return {"trafego_gb": round(tg, 3), "orcamento_gb": ORC_GB, "trafego_pct": round(100 * tg / ORC_GB, 1) if ORC_GB else 0,
            "disco_livre_gb": round(disco_livre_gb(), 1), "disco_minimo_gb": DISCO_MIN_GB, "timers": timers, "ultima": ult,
            "coleta_rodando": rodando, "coleta_modo": _proc["modo"] if rodando else None, "download": dict(_dl),
            "agora": datetime.now().isoformat(timespec="seconds")}


def disparar_coleta(modo):
    if modo not in MODOS:
        raise ValueError("modo invalido")
    if _proc["p"] is not None and _proc["p"].poll() is None:
        raise RuntimeError("ja existe uma coleta em andamento")
    if not os.path.isfile(COLETOR):
        raise RuntimeError("executor da coleta nao instalado")
    os.makedirs(LOGS, exist_ok=True)
    saida = open(os.path.join(LOGS, "painel_coleta.log"), "ab")
    _proc["p"] = subprocess.Popen([COLETOR, modo], stdout=saida, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
    _proc["modo"] = modo


# ------------------------------------------------------------------ pagina hospitalar local
def arquivo_hospital(sub):
    """Mapeia /hospital/<sub> para um arquivo local. Somente js, css, config e dados, nomes simples."""
    m = re.fullmatch(r"(js|css|config|dados)/([A-Za-z0-9._-]{1,80})", sub)
    if not m or not m.group(2).endswith((".js", ".css", ".json")):
        return None
    pasta = DADOS_HOSP if m.group(1) == "dados" else os.path.join(REPO_HOSP, m.group(1))
    caminho = os.path.join(pasta, m.group(2))
    if m.group(1) == "dados" and not os.path.isfile(caminho):
        caminho = os.path.join(REPO_HOSP, "dados", m.group(2))   # modelo vazio do repositorio
    return caminho if os.path.isfile(caminho) else None


def pagina_hospital():
    with open(os.path.join(REPO_HOSP, "fragmento.html"), encoding="utf-8") as a:
        frag = a.read()
    return ('<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Gestão Hospitalar | Partelli (local)</title><link rel="stylesheet" href="/hospital/css/hospital.css">'
            '<style>body{margin:0;font:16px/1.45 system-ui,Arial,sans-serif;background:#f6f7f9;color:#1f2933}.topo{background:#0c326f;color:#fff;padding:12px 18px}.topo a{color:#fff}main{max-width:1100px;margin:0 auto;padding:0 16px 40px}</style></head><body>'
            '<div class="topo"><a href="/">Painel FTP</a> &nbsp;|&nbsp; Dados lidos do próprio notebook</div><main>' + frag +
            '</main><script type="module" src="/hospital/js/hospital.js"></script></body></html>').encode()


# ------------------------------------------------------------------ HTTP
class Painel(BaseHTTPRequestHandler):
    server_version = "PartelliPainel"
    sys_version = ""

    def log_message(self, *a):
        pass

    def _enviar(self, codigo, corpo, tipo="application/json; charset=utf-8", extra=None):
        dados = corpo if isinstance(corpo, bytes) else json.dumps(corpo, ensure_ascii=False).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(dados)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; frame-ancestors 'none'")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(dados)

    def _autenticado(self):
        for parte in (self.headers.get("Cookie") or "").split(";"):
            k, _, v = parte.strip().partition("=")
            if k == COOKIE and sessao_ok(v):
                return True
        return False

    def _corpo(self):
        n = min(int(self.headers.get("Content-Length") or 0), 10000)
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except ValueError:
            return {}

    def _erro(self, e, codigo=400):
        self._enviar(codigo, {"erro": str(e)})

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path in ("/", "/index.html"):
            with open(os.path.join(AQUI, "static", "index.html"), "rb") as a:
                return self._enviar(200, a.read(), "text/html; charset=utf-8")
        if u.path.startswith("/hospital"):
            if not self._autenticado():
                return self._enviar(302, b"", "text/plain", {"Location": "/"})
            if u.path in ("/hospital", "/hospital/"):
                return self._enviar(200, pagina_hospital(), "text/html; charset=utf-8")
            arq = arquivo_hospital(u.path[len("/hospital/"):])
            if not arq:
                return self._enviar(404, {"erro": "nao encontrado"})
            with open(arq, "rb") as a:
                return self._enviar(200, a.read(), _MIME.get(os.path.splitext(arq)[1], "application/octet-stream"))
        if u.path == "/api/sessao":
            return self._enviar(200, {"autenticado": self._autenticado(), "configurado": bool(TOKEN and SEGREDO)})
        if not u.path.startswith("/api/"):
            return self._enviar(404, {"erro": "nao encontrado"})
        if not self._autenticado():
            return self._enviar(401, {"erro": "entre com o token"})
        try:
            if u.path == "/api/status":
                return self._enviar(200, status())
            if u.path == "/api/ls":
                cam = caminho_ftp_valido((q.get("path") or [RAIZ])[0])
                if not cam:
                    return self._erro("caminho fora de /dissemin/publicos/", 403)
                return self._enviar(200, {"caminho": cam, "itens": listar_ftp(cam)})
            if u.path == "/api/arquivos":
                return self._enviar(200, {"itens": arquivos_locais(), "pasta": DOWNLOADS})
            if u.path == "/api/cabecalho":
                nome = (q.get("nome") or [""])[0]
                if not nome_local_valido(nome) or not os.path.isfile(os.path.join(DOWNLOADS, nome)):
                    return self._erro("arquivo invalido", 404)
                return self._enviar(200, cabecalho_dbc(nome))
            if u.path == "/api/log":
                nome = (q.get("arq") or ["painel_coleta.log"])[0]
                if not nome_local_valido(nome) or not nome.endswith(".log"):
                    return self._erro("log invalido", 404)
                return self._enviar(200, {"linhas": ultima_linhas(os.path.join(LOGS, nome))})
            if u.path == "/api/baixado":
                nome = (q.get("nome") or [""])[0]
                p = os.path.join(DOWNLOADS, nome)
                if not nome_local_valido(nome) or not os.path.isfile(p):
                    return self._erro("arquivo invalido", 404)
                with open(p, "rb") as a:
                    return self._enviar(200, a.read(), "application/octet-stream",
                                        {"Content-Disposition": f'attachment; filename="{nome}"'})
        except Exception as e:
            return self._erro(e, 500)
        self._enviar(404, {"erro": "nao encontrado"})

    def do_POST(self):
        u = urlparse(self.path)
        ip = self.client_address[0]
        corpo = self._corpo()
        if u.path == "/api/login":
            if bloqueado(ip):
                return self._enviar(429, {"erro": "muitas tentativas, aguarde 1 minuto"})
            if not (TOKEN and SEGREDO):
                return self._enviar(503, {"erro": "token nao configurado no servidor"})
            if token_ok(corpo.get("token")):
                exp = int(time.time()) + SESSAO_S
                ck = f"{COOKIE}={assinar(exp)}; HttpOnly; SameSite=Strict; Path=/; Max-Age={SESSAO_S}"
                return self._enviar(200, {"ok": True}, extra={"Set-Cookie": ck})
            _falhas.setdefault(ip, []).append(time.time())
            return self._enviar(401, {"erro": "token incorreto"})
        if u.path == "/api/sair":
            return self._enviar(200, {"ok": True}, extra={"Set-Cookie": f"{COOKIE}=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0"})
        if not self._autenticado():
            return self._enviar(401, {"erro": "entre com o token"})
        origem = self.headers.get("Origin")
        if origem and urlparse(origem).netloc != self.headers.get("Host"):
            return self._erro("origem nao permitida", 403)
        try:
            if u.path == "/api/baixar":
                cam = caminho_ftp_valido(corpo.get("path"))
                if not cam or cam.endswith("/"):
                    return self._erro("caminho fora de /dissemin/publicos/", 403)
                return self._enviar(200, iniciar_download(cam, bool(corpo.get("confirmar"))))
            if u.path == "/api/apagar":
                nome = corpo.get("nome")
                p = os.path.join(DOWNLOADS, nome or "")
                if not nome_local_valido(nome) or not os.path.isfile(p):
                    return self._erro("arquivo invalido", 404)
                os.remove(p)
                return self._enviar(200, {"ok": True})
            if u.path == "/api/coletar":
                disparar_coleta(corpo.get("modo"))
                return self._enviar(200, {"iniciado": True})
        except Exception as e:
            return self._erro(e)
        self._enviar(404, {"erro": "nao encontrado"})


def main():
    host = os.environ.get("PAINEL_HOST", "127.0.0.1")
    porta = int(os.environ.get("PAINEL_PORT", "8765"))
    if not TOKEN or len(SEGREDO) < 16:
        print("AVISO: PAINEL_TOKEN/PAINEL_SEGREDO ausentes; login desabilitado.", file=sys.stderr)
    srv = ThreadingHTTPServer((host, porta), Painel)
    print(f"Painel FTP em http://{host}:{porta}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
