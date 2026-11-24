import os, sys, tempfile, unittest, sqlite3
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


def rd_campos():
    return [("UF_ZI", "C", 6), ("ANO_CMPT", "C", 4), ("MES_CMPT", "C", 2), ("ESPEC", "C", 2), ("N_AIH", "C", 13), ("CEP", "C", 8), ("MUNIC_RES", "C", 6),
            ("NASC", "C", 8), ("SEXO", "C", 1), ("UTI_MES_TO", "N", 3), ("QT_DIARIAS", "N", 3), ("PROC_REA", "C", 10), ("VAL_SH", "N", 13),
            ("VAL_SP", "N", 13), ("VAL_TOT", "N", 14), ("DIAG_PRINC", "C", 4), ("MORTE", "N", 1), ("DIAS_PERM", "N", 5), ("CAR_INT", "C", 2),
            ("COMPLEX", "C", 2), ("FINANC", "C", 2), ("MUNIC_MOV", "C", 6), ("CNES", "C", 7), ("CPF_AUT", "C", 11)]


def rd_linha(aih, cnes, proc, sh, sp, dias, morte=0):
    return ["320000", "2026", "01", "03", aih, "29900000", "320530", "19800101", "F", 0, 2, proc, sh, sp, f"{float(sh) + float(sp):.2f}", "O800", morte, dias,
            "01", "02", "04", "320530", cnes, "12345678901"]


@unittest.skipIf(montar_dbc is None, "defina ROBO_EXTRA para achar dbc_codificador")
class Conversao(unittest.TestCase):
    def setUp(self):
        for n in os.listdir(K.ORIGEM):
            os.remove(os.path.join(K.ORIGEM, n))
        self.con = K.abrir_banco(os.path.join(tempfile.mkdtemp(), "x.sqlite"))

    def grava(self, nome, bruto):
        with open(os.path.join(K.ORIGEM, nome), "wb") as a:
            a.write(bruto)
        return os.path.join(K.ORIGEM, nome)

    def test_rd_agrega_e_nao_guarda_dado_pessoal(self):
        regs = [rd_linha("3220000000011", "2483998", "0310010039", "100.50", "50.25", 3),
                rd_linha("3220000000022", "2483998", "0310010039", "200.00", "10.00", 5, morte=1),
                rd_linha("3220000000033", "2484943", "0411010034", "300.10", "20.20", 2)]
        r = K.converter_arquivo(self.con, self.grava("RDES2601.dbc", montar_dbc(rd_campos(), regs)))
        self.assertEqual((r["linhas"], r["grupos"]), (3, 2))
        linha = self.con.execute("SELECT n_linhas, val_sh, val_sp, val_tot, dias_perm, mortes FROM rd WHERE cnes='2483998'").fetchone()
        self.assertEqual(linha[0], 2)
        self.assertAlmostEqual(linha[1], 300.50, 2)
        self.assertAlmostEqual(linha[2], 60.25, 2)
        self.assertAlmostEqual(linha[3], 360.75, 2)
        self.assertEqual(linha[4:], (8, 1))
        despejo = "\n".join(self.con.iterdump())
        for sensivel in ("3220000000011", "29900000", "19800101", "12345678901", "320530,"):
            self.assertNotIn(sensivel, despejo.replace("'320530'", "") if sensivel == "320530," else despejo)
        colunas = {c[1] for c in self.con.execute("PRAGMA table_info(rd)")}
        for proibida in ("n_aih", "cep", "nasc", "sexo", "munic_res", "cpf_aut"):
            self.assertNotIn(proibida, colunas)

    def test_reprocessar_nao_duplica(self):
        regs = [rd_linha("1", "2483998", "0310010039", "10.00", "5.00", 1)] * 4
        p = self.grava("RDES2601.dbc", montar_dbc(rd_campos(), regs))
        K.converter_arquivo(self.con, p)
        K.converter_arquivo(self.con, p)
        self.assertEqual(self.con.execute("SELECT SUM(n_linhas) FROM rd").fetchone()[0], 4)
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM arquivos").fetchone()[0], 1)

    def test_pendentes_so_novos_ou_alterados(self):
        p = self.grava("RDES2601.dbc", montar_dbc(rd_campos(), [rd_linha("1", "2483998", "0310010039", "1.00", "1.00", 1)]))
        self.grava("OUTRO.dbc", b"x")
        self.assertEqual(K.pendentes(self.con), [p])
        K.converter_arquivo(self.con, p)
        self.assertEqual(K.pendentes(self.con), [])
        self.grava("RDES2601.dbc", montar_dbc(rd_campos(), [rd_linha("1", "2483998", "0310010039", "1.00", "1.00", 1)] * 2))
        self.assertEqual(len(K.pendentes(self.con)), 1)

    def test_sp_e_pa(self):
        sp = [("SP_CNES", "C", 7), ("SP_AA", "C", 4), ("SP_MM", "C", 2), ("SP_NAIH", "C", 13), ("SP_PROCREA", "C", 10), ("SP_ATOPROF", "C", 10),
              ("SP_TP_ATO", "C", 2), ("SP_QTD_ATO", "N", 4), ("SP_VALATO", "N", 14), ("SP_PF_CBO", "C", 6), ("SP_PF_DOC", "C", 15),
              ("SP_COMPLEX", "C", 2), ("SP_FINANC", "C", 2)]
        regs = [["2483998", "2026", "01", "999", "0310010039", "0201010011", "01", 1, "10.10", "225125", "11122233344", "02", "04"],
                ["2483998", "2026", "01", "998", "0310010039", "0201010011", "01", 2, "20.20", "225125", "55566677788", "02", "04"]]
        K.converter_arquivo(self.con, self.grava("SPES2601.dbc", montar_dbc(sp, regs)))
        self.assertEqual(self.con.execute("SELECT n_linhas, qtd_ato, val_ato FROM sp").fetchone(), (2, 3, 30.30))
        self.assertNotIn("11122233344", "\n".join(self.con.iterdump()))
        pa = [("PA_CODUNI", "C", 7), ("PA_MVM", "C", 6), ("PA_CMP", "C", 6), ("PA_PROC_ID", "C", 10), ("PA_CBOCOD", "C", 6), ("PA_TPFIN", "C", 2),
              ("PA_SUBFIN", "C", 4), ("PA_NIVCPL", "C", 1), ("PA_UFMUN", "C", 6), ("PA_CNSMED", "C", 15), ("PA_QTDPRO", "N", 11), ("PA_QTDAPR", "N", 11),
              ("PA_VALPRO", "N", 20), ("PA_VALAPR", "N", 20), ("PA_SEXO", "C", 1)]
        regs = [["2483998", "202602", "202602", "0301010072", "225125", "01", "0100", "0", "320530", "700000000000001", 10, 10, "100.00", "90.00", "M"]] * 3
        K.converter_arquivo(self.con, self.grava("PAES2602.dbc", montar_dbc(pa, regs)))
        self.assertEqual(self.con.execute("SELECT n_linhas, qtd_pro, qtd_apr, val_pro, val_apr FROM pa").fetchone(), (3, 30, 30, 300.0, 270.0))
        self.assertNotIn("700000000000001", "\n".join(self.con.iterdump()))

    def test_lista_branca_sem_proibidos(self):
        for t, (_, d, m, _c) in K.TABELAS.items():
            usados = {c for _, c in d} | {c for _, c, _ in m}
            self.assertFalse(usados & K.H.PROIBIDOS)


if __name__ == "__main__":
    unittest.main()
