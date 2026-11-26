import os, sys, tempfile, unittest
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "notebook_app"))
sys.path.insert(0, os.path.join(AQUI, "..", "robo"))
extra = os.environ.get("ROBO_EXTRA")
if extra:
    sys.path.insert(0, extra)
    sys.path.insert(0, os.path.join(extra, "..", "tests"))
os.environ.update({"PAINEL_DOWNLOADS": tempfile.mkdtemp(), "PARTELLI_BASE": tempfile.mkdtemp(), "PARTELLI_ESTADO": tempfile.mkdtemp(),
                   "PARTELLI_BANCO": os.path.join(tempfile.mkdtemp(), "t.sqlite")})
try:
    from dbc_codificador import montar_dbc
except ImportError:
    montar_dbc = None
import converter_sqlite as K
import reconciliar_rejeicoes as R
from test_converter_sqlite import rd_campos, rd_linha

ER_CAMPOS = [("SEQUENCIA", "N", 9), ("REMESSA", "C", 21), ("CNES", "C", 7), ("AIH", "C", 13), ("ANO", "C", 4), ("MES", "C", 2), ("DT_INTER", "C", 10),
             ("DT_SAIDA", "C", 10), ("MUN_MOV", "C", 6), ("UF_ZI", "C", 6), ("MUN_RES", "C", 6), ("UF_RES", "C", 2), ("CO_ERRO", "C", 6)]


def er(cnes, aih, mes, erro):
    return [1, "REMESSA-SECRETA", cnes, aih, "2026", mes, "2026-01-01", "2026-01-05", "320350", "320000", "320530", "ES", erro]


def rd(aih, cnes, mes, valor):
    lin = rd_linha(aih, cnes, "0310010039", f"{valor:.2f}", "0.00", 3)
    lin[2] = mes
    return lin


@unittest.skipIf(montar_dbc is None, "defina ROBO_EXTRA para achar dbc_codificador")
class Reapresentacao(unittest.TestCase):
    def grava(self, nome, bruto):
        with open(os.path.join(K.ORIGEM, nome), "wb") as a:
            a.write(bruto)

    def test_conta_so_aprovacao_posterior_no_mesmo_cnes_e_nao_grava_numero(self):
        for n in os.listdir(K.ORIGEM):
            os.remove(os.path.join(K.ORIGEM, n))
        self.grava("ERES2601.dbc", montar_dbc(ER_CAMPOS, [er("2483998", "1111111111111", "01", "020071"), er("2483998", "2222222222222", "01", "020071"),
                                                         er("2483998", "3333333333333", "01", "020081"), er("2483998", "4444444444444", "01", "020071")]))
        self.grava("RDES2601.dbc", montar_dbc(rd_campos(), [rd("2222222222222", "2483998", "01", 50.0)]))     # mesma competencia: nao conta
        self.grava("RDES2602.dbc", montar_dbc(rd_campos(), [rd("1111111111111", "2483998", "02", 100.50),     # recuperada
                                                           rd("4444444444444", "2484943", "02", 70.0)]))     # outro CNES: nao conta
        con = K.abrir_banco(os.path.join(tempfile.mkdtemp(), "r.sqlite"))
        r = R.reconciliar(con)
        self.assertEqual((r["rejeitadas"], r["recuperadas"]), (4, 1))
        self.assertEqual(con.execute("SELECT rejeitadas, recuperadas, valor_recuperado FROM rejeicao_rec WHERE co_erro='020071'").fetchone(), (3, 1, 100.5))
        self.assertEqual(con.execute("SELECT recuperadas FROM rejeicao_rec WHERE co_erro='020081'").fetchone()[0], 0)
        despejo = "\n".join(con.iterdump())
        for sensivel in ("1111111111111", "2222222222222", "3333333333333", "4444444444444", "REMESSA-SECRETA", "2026-01-01"):
            self.assertNotIn(sensivel, despejo)
        self.assertEqual([c[1] for c in con.execute("PRAGMA table_info(rejeicao_rec)")], R.COLUNAS_GRAVADAS)
        r2 = R.reconciliar(con)           # reprocessar nao duplica
        self.assertEqual(con.execute("SELECT SUM(rejeitadas) FROM rejeicao_rec").fetchone()[0], 4)
        self.assertEqual(r2["recuperadas"], 1)


if __name__ == "__main__":
    unittest.main()
