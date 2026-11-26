import os, sys, tempfile, unittest
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "notebook_app"))
sys.path.insert(0, os.path.join(AQUI, "..", "robo"))
if os.environ.get("ROBO_EXTRA"):
    sys.path.insert(0, os.environ["ROBO_EXTRA"])
os.environ.update({"PAINEL_DOWNLOADS": tempfile.mkdtemp(), "PARTELLI_BASE": tempfile.mkdtemp(), "PARTELLI_ESTADO": tempfile.mkdtemp()})
import coleta_ftp as C

CFG = C.carregar()
SIH, SIA = "/dissemin/publicos/SIHSUS/200801_/Dados", "/dissemin/publicos/SIASUS/200801_/Dados"
LIST = {SIH: [("RDES2601.dbc", 10), ("RDES2602.dbc", 11), ("RDES2512.dbc", 5), ("RDSP2601.dbc", 9), ("RDES2613.dbc", 1), ("SPES2601.dbc", 7),
              ("SPSP2601.dbc", 7), ("RDES2601.dbc.bak", 3), ("rdes2603.DBC", 12), ("ERES2601.dbc", 4), ("ERSP2601.dbc", 4)],
        SIA: [("PAES2601a.dbc", 100), ("PAES2601b.dbc", 90), ("PAES2602a.dbc", 80), ("PAES2501a.dbc", 70), ("PASP2601a.dbc", 60), ("PAES2600a.dbc", 5)]}


class Plano(unittest.TestCase):
    def test_somente_es_2026_e_tres_prefixos(self):
        nomes = [i["nome"] for i in C.planejar(CFG, LIST)]
        self.assertEqual(sorted(n.upper() for n in nomes), sorted(["RDES2601.DBC", "RDES2602.DBC", "RDES2603.DBC", "SPES2601.DBC", "ERES2601.DBC", "PAES2601A.DBC", "PAES2601B.DBC", "PAES2602A.DBC"]))
        for ruim in ("RDES2512.dbc", "RDSP2601.dbc", "SPSP2601.dbc", "ERSP2601.dbc", "PASP2601a.dbc", "PAES2501a.dbc", "RDES2613.dbc", "PAES2600a.dbc", "RDES2601.dbc.bak"):
            self.assertNotIn(ruim, nomes)

    def test_ultimos_meses_so_nos_grupos_cadastrais(self):
        pasta = "/dissemin/publicos/CNES/200508_/Dados/LT"
        lst = {pasta: [(f"LTES26{m:02d}.dbc", 5) for m in range(1, 11)]}
        cfg = dict(CFG, fontes=[{"prefixo": "LT", "pasta": pasta, "sistema": "x", "ultimos": 3}])
        self.assertEqual([i["nome"] for i in C.planejar(cfg, lst)], ["LTES2608.dbc", "LTES2609.dbc", "LTES2610.dbc"])
        cfg2 = dict(CFG, fontes=[{"prefixo": "LT", "pasta": pasta, "sistema": "x"}])
        self.assertEqual(len(C.planejar(cfg2, lst)), 10)

    def test_ano_configuravel(self):
        cfg = dict(CFG, ano=2025)
        self.assertEqual([i["nome"] for i in C.planejar(cfg, LIST) if i["nome"].startswith("PA")], ["PAES2501a.dbc"])

    def test_ja_baixado_pelo_tamanho(self):
        item = {"nome": "RDES2601.dbc", "tamanho": 10}
        self.assertFalse(C.ja_baixado(item))
        with open(os.path.join(C.DESTINO, "RDES2601.dbc"), "wb") as a:
            a.write(b"x" * 10)
        self.assertTrue(C.ja_baixado(item))
        self.assertFalse(C.ja_baixado({"nome": "RDES2601.dbc", "tamanho": 11}))


if __name__ == "__main__":
    unittest.main()
