import json, os, sys, tempfile, threading, time, unittest, urllib.request, urllib.error
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "notebook_app"))
extra = os.environ.get("ROBO_EXTRA")
if extra:
    sys.path.insert(0, extra)
sys.path.insert(0, os.path.join(AQUI, "..", "robo"))
os.environ.update({"PAINEL_TOKEN": "tok-teste", "PAINEL_SEGREDO": "s" * 40, "PAINEL_DOWNLOADS": tempfile.mkdtemp(),
                   "PARTELLI_BASE": tempfile.mkdtemp(), "PARTELLI_ESTADO": tempfile.mkdtemp()})
import servidor_ftp as S
from http.server import ThreadingHTTPServer


class Caminhos(unittest.TestCase):
    def test_lista_branca(self):
        self.assertEqual(S.caminho_ftp_valido("/dissemin/publicos/SIHSUS/200801_/Dados"), "/dissemin/publicos/SIHSUS/200801_/Dados")
        self.assertEqual(S.caminho_ftp_valido("/dissemin/publicos/"), "/dissemin/publicos")
        for ruim in ("/etc/passwd", "/dissemin/publicos/../privado", "/dissemin/publicosX", "..", "", "/dissemin/publicos/a\x00b", "/dissemin/publicos\\x", None):
            self.assertIsNone(S.caminho_ftp_valido(ruim), ruim)

    def test_nome_local(self):
        self.assertTrue(S.nome_local_valido("RDES2608.dbc"))
        for ruim in ("../x", "a/b", "", ".", "..", "a b", "x" * 200, None):
            self.assertFalse(S.nome_local_valido(ruim), ruim)


class Listas(unittest.TestCase):
    def test_unix(self):
        r = S.parse_lista(["-rw-r--r--   1 ftp ftp   1234567 Nov 20 10:11 RDES2608.dbc", "drwxr-xr-x   2 ftp ftp 4096 Jan  1 2020 Dados"])
        self.assertEqual((r[0]["nome"], r[0]["tipo"], r[0]["tamanho"]), ("RDES2608.dbc", "arq", 1234567))
        self.assertEqual((r[1]["nome"], r[1]["tipo"]), ("Dados", "dir"))

    def test_windows(self):
        r = S.parse_lista(["11-20-26  10:11AM            1234567 STES2608.dbc", "01-01-20  09:00AM       <DIR>          Auxiliar", "lixo"])
        self.assertEqual(len(r), 2)
        self.assertEqual((r[0]["nome"], r[0]["tamanho"]), ("STES2608.dbc", 1234567))
        self.assertEqual(r[1]["tipo"], "dir")


class Http(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), S.Painel)
        cls.porta = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def req(self, caminho, corpo=None, cookie=None):
        r = urllib.request.Request(f"http://127.0.0.1:{self.porta}{caminho}", data=None if corpo is None else json.dumps(corpo).encode(),
                                   headers={"Content-Type": "application/json", **({"Cookie": cookie} if cookie else {})})
        try:
            with urllib.request.urlopen(r) as a:
                return a.status, a.read(), a.headers
        except urllib.error.HTTPError as e:
            return e.code, e.read(), e.headers

    def login(self):
        S._falhas.clear()
        c, _, h = self.req("/api/login", {"token": "tok-teste"})
        self.assertEqual(c, 200)
        ck = h["Set-Cookie"]
        self.assertIn("HttpOnly", ck)
        self.assertIn("SameSite=Strict", ck)
        return ck.split(";")[0]

    def test_exige_login(self):
        for u in ("/api/status", "/api/ls?path=/dissemin/publicos", "/api/arquivos"):
            self.assertEqual(self.req(u)[0], 401)
        self.assertEqual(self.req("/api/baixar", {"path": "/dissemin/publicos/x"})[0], 401)
        self.assertEqual(self.req("/api/coletar", {"modo": "tudo"})[0], 401)

    def test_cookie_falso(self):
        self.assertEqual(self.req("/api/status", cookie=S.COOKIE + "=9999999999.abc")[0], 401)
        self.assertEqual(self.req("/api/status", cookie=S.COOKIE + "=1.x")[0], 401)

    def test_token_errado_e_limite(self):
        S._falhas.clear()
        codigos = [self.req("/api/login", {"token": "errado"})[0] for _ in range(6)]
        self.assertEqual(codigos[:5], [401] * 5)
        self.assertEqual(codigos[5], 429)
        S._falhas.clear()

    def test_autenticado(self):
        ck = self.login()
        c, b, _ = self.req("/api/status", cookie=ck)
        self.assertEqual(c, 200)
        st = json.loads(b)
        self.assertIn("trafego_gb", st)
        self.assertEqual(self.req("/api/ls?path=/etc", cookie=ck)[0], 403)
        self.assertEqual(self.req("/api/baixar", {"path": "/etc/passwd"}, cookie=ck)[0], 403)
        self.assertEqual(self.req("/api/baixado?nome=../../etc/passwd", cookie=ck)[0], 404)
        self.assertEqual(self.req("/api/apagar", {"nome": "../x"}, cookie=ck)[0], 404)
        self.assertEqual(self.req("/api/coletar", {"modo": "rm -rf"}, cookie=ck)[0], 400)

    def test_pagina_hospital_local(self):
        c, _, _ = self.req("/hospital/js/hospital.js")
        self.assertIn(c, (200, 302, 401))
        ck = self.login()
        c, b, _ = self.req("/hospital/", cookie=ck)
        self.assertEqual(c, 200)
        self.assertIn(b"gestao-hospitalar", b)
        self.assertEqual(self.req("/hospital/js/hospital.js", cookie=ck)[0], 200)
        self.assertEqual(self.req("/hospital/dados/indice.json", cookie=ck)[0], 200)
        for ruim in ("/hospital/js/../../etc/passwd", "/hospital/js/x.py", "/hospital/config/..%2f..%2fx.json", "/hospital/outro/a.js"):
            self.assertEqual(self.req(ruim, cookie=ck)[0], 404, ruim)

    def test_pagina(self):
        c, b, h = self.req("/")
        self.assertEqual(c, 200)
        self.assertIn(b"Painel FTP", b)
        self.assertIn("frame-ancestors", h["Content-Security-Policy"])

    def test_cabecalho_dbc(self):
        import struct
        ck = self.login()
        campos = [(b"CNES", 7), (b"CPF_PROF", 11), (b"VAL", 5)]
        tam_cab = 32 + 32 * len(campos) + 1
        cab = bytearray(tam_cab)
        cab[0] = 3
        struct.pack_into("<IHH", cab, 4, 42, tam_cab, 1 + sum(t for _, t in campos))
        for i, (n, t) in enumerate(campos):
            cab[32 + 32 * i:32 + 32 * i + len(n)] = n
            cab[32 + 32 * i + 11] = ord("C")
            cab[32 + 32 * i + 16] = t
        cab[tam_cab - 1] = 0x0D
        with open(os.path.join(S.DOWNLOADS, "TESTE.dbc"), "wb") as a:
            a.write(bytes(cab) + b"\x00" * 100)
        try:
            import dbc  # noqa
        except ImportError:
            self.skipTest("dbc nao disponivel (use ROBO_EXTRA)")
        c, b, _ = self.req("/api/cabecalho?nome=TESTE.dbc", cookie=ck)
        self.assertEqual(c, 200)
        j = json.loads(b)
        self.assertEqual(j["registros"], 42)
        sens = {x["nome"]: x["sensivel"] for x in j["campos"]}
        self.assertTrue(sens["CPF_PROF"])
        self.assertFalse(sens["CNES"])


if __name__ == "__main__":
    unittest.main()
