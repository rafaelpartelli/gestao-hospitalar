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


# Nomes de campos dos arquivos reais de 2026 (saida de campos_dbc.py no notebook). ST e EP aparecem com os campos usados e os de identificacao.
LAYOUTS_REAIS = {
    "ER": "SEQUENCIA REMESSA CNES AIH ANO MES DT_INTER DT_SAIDA MUN_MOV UF_ZI MUN_RES UF_RES CO_ERRO".split(),
    "HB": "CNES CODUFMUN REGSAUDE MICR_REG DISTRSAN DISTRADM TPGESTAO PF_PJ CPF_CNPJ NIV_DEP CNPJ_MAN ESFERA_A RETENCAO ATIVIDAD NATUREZA CLIENTEL TP_UNID TURNO_AT NIV_HIER TERCEIRO COD_CEP VINC_SUS TP_PREST SGRUPHAB CMPT_INI CMPT_FIM DTPORTAR PORTARIA MAPORTAR NULEITOS COMPETEN NAT_JUR".split(),
    "IN": "CNES CODUFMUN REGSAUDE MICR_REG DISTRSAN DISTRADM TPGESTAO PF_PJ CPF_CNPJ NIV_DEP CNPJ_MAN ESFERA_A RETENCAO ATIVIDAD NATUREZA CLIENTEL TP_UNID TURNO_AT NIV_HIER TERCEIRO COD_CEP VINC_SUS TP_PREST SGRUPHAB CMPT_INI CMPT_FIM DTPORTAR PORTARIA MAPORTAR COMPETEN NAT_JUR".split(),
    "LT": "CNES CODUFMUN REGSAUDE MICR_REG DISTRSAN DISTRADM TPGESTAO PF_PJ CPF_CNPJ NIV_DEP CNPJ_MAN ESFERA_A ATIVIDAD RETENCAO NATUREZA CLIENTEL TP_UNID TURNO_AT NIV_HIER TERCEIRO TP_LEITO CODLEITO QT_EXIST QT_CONTR QT_SUS QT_NSUS COMPETEN NAT_JUR".split(),
    "EQ": "CNES CODUFMUN REGSAUDE MICR_REG DISTRSAN DISTRADM TPGESTAO PF_PJ CPF_CNPJ NIV_DEP CNPJ_MAN ESFERA_A ATIVIDAD RETENCAO NATUREZA CLIENTEL TP_UNID TURNO_AT NIV_HIER TERCEIRO TIPEQUIP CODEQUIP QT_EXIST QT_USO IND_SUS IND_NSUS COMPETEN NAT_JUR".split(),
    "PF": "CNES CODUFMUN REGSAUDE MICR_REG DISTRSAN DISTRADM TPGESTAO PF_PJ CPF_CNPJ NIV_DEP CNPJ_MAN ESFERA_A ATIVIDAD RETENCAO NATUREZA CLIENTEL TP_UNID TURNO_AT NIV_HIER TERCEIRO CPF_PROF CPFUNICO CBO CBOUNICO NOMEPROF CNS_PROF CONSELHO REGISTRO VINCULAC VINCUL_C VINCUL_A VINCUL_N PROF_SUS PROFNSUS HORAOUTR HORAHOSP HORA_AMB COMPETEN UFMUNRES NAT_JUR".split(),
    "RC": "CNES CODUFMUN REGSAUDE MICR_REG DISTRSAN DISTRADM TPGESTAO PF_PJ CPF_CNPJ NIV_DEP CNPJ_MAN ESFERA_A RETENCAO ATIVIDAD NATUREZA CLIENTEL TP_UNID TURNO_AT NIV_HIER TERCEIRO COD_CEP VINC_SUS TP_PREST SGRUPHAB CMPT_INI CMPT_FIM DTPORTAR PORTARIA MAPORTAR COMPETEN NAT_JUR".split(),
    "EF": "CNES CODUFMUN REGSAUDE MICR_REG DISTRSAN DISTRADM TPGESTAO PF_PJ CPF_CNPJ NIV_DEP CNPJ_MAN ESFERA_A RETENCAO ATIVIDAD NATUREZA CLIENTEL TP_UNID TURNO_AT NIV_HIER TERCEIRO COD_CEP VINC_SUS TP_PREST SGRUPHAB CMPT_INI CMPT_FIM DTPORTAR PORTARIA MAPORTAR COMPETEN NAT_JUR".split(),
    "SR": "CNES CODUFMUN SERV_ESP CLASS_SR SRVUNICO REGSAUDE MICR_REG DISTRSAN DISTRADM TPGESTAO PF_PJ CPF_CNPJ NIV_DEP ESFERA_A ATIVIDAD RETENCAO NATUREZA CLIENTEL TP_UNID TURNO_AT NIV_HIER TERCEIRO CNPJ_MAN CARACTER AMB_NSUS AMB_SUS HOSP_NSUS HOSP_SUS COMPETEN CONTSRVU CNESTERC NAT_JUR".split(),
    "EP": "CNES CODUFMUN COD_CEP CPF_CNPJ PF_PJ NIV_DEP CNPJ_MAN COD_IR REGSAUDE MICR_REG DISTRSAN DISTRADM VINC_SUS TPGESTAO ESFERA_A RETENCAO ATIVIDAD NATUREZA CLIENTEL TP_UNID TURNO_AT NIV_HIER TERCEIRO TP_PREST IDEQUIPE TIPO_EQP NOME_EQP ID_AREA NOMEAREA ID_SEGM DESCSEGM TIPOSEGM DT_ATIVA DT_DESAT MOTDESAT TP_DESAT COMPETEN NAT_JUR".split(),
    "ST": "CNES CODUFMUN COD_CEP CPF_CNPJ PF_PJ NIV_DEP CNPJ_MAN COD_IR REGSAUDE MICR_REG DISTRSAN DISTRADM VINC_SUS TPGESTAO ESFERA_A RETENCAO ATIVIDAD NATUREZA CLIENTEL TP_UNID TURNO_AT NIV_HIER TP_PREST AV_ACRED CLASAVAL AV_PNASS URGEMERG ATENDAMB CENTRCIR CENTROBS CENTRNEO ATENDHOS LEITHOSP QTLEITP1 QTLEITP2 QTLEITP3 COMPETEN NAT_JUR QTINST01 QTINST02 QTINST03 QTINST04 QTINST05 QTINST06 QTINST07 QTINST08 QTINST09 QTINST10 QTINST11 QTINST12 QTINST13 QTINST14 QTINST15 QTINST16 QTINST17 QTINST18 QTINST19 QTINST20 QTINST21 QTINST22 QTINST23 QTINST24 QTINST25 QTINST26 QTINST27 QTINST28 QTINST29 QTINST30 QTINST31 QTINST32 QTINST33 QTINST34 QTINST35 QTINST36 QTINST37".split(),
}


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


    def test_hb_sem_documento_e_cep(self):
        campos = [("CNES", "C", 7), ("CODUFMUN", "C", 6), ("CPF_CNPJ", "C", 14), ("CNPJ_MAN", "C", 14), ("COD_CEP", "C", 8), ("TP_UNID", "C", 2),
                  ("VINC_SUS", "C", 1), ("ESFERA_A", "C", 2), ("SGRUPHAB", "C", 4), ("CMPT_INI", "C", 6), ("CMPT_FIM", "C", 6), ("DTPORTAR", "C", 10),
                  ("PORTARIA", "C", 50), ("MAPORTAR", "C", 6), ("NULEITOS", "N", 3), ("COMPETEN", "C", 6), ("NAT_JUR", "C", 4)]
        regs = [["2483998", "320350", "12345678000199", "99999999000100", "29900000", "05", "1", "03", "0601", "202001", "999999", "2020-01-10",
                 "PORTARIA GM/MS 100", "202001", 10, "202610", "1023"],
                ["2483998", "320350", "12345678000199", "99999999000100", "29900000", "05", "1", "03", "0602", "202101", "999999", "2021-02-10",
                 "PORTARIA GM/MS 200", "202102", 5, "202610", "1023"]]
        r = K.converter_arquivo(self.con, self.grava("HBES2610.dbc", montar_dbc(campos, regs)))
        self.assertEqual((r["tabela"], r["linhas"], r["grupos"]), ("hb", 2, 2))
        self.assertEqual(self.con.execute("SELECT SUM(nuleitos) FROM hb").fetchone()[0], 15)
        despejo = "\n".join(self.con.iterdump())
        for sensivel in ("12345678000199", "99999999000100", "29900000"):
            self.assertNotIn(sensivel, despejo)

    def test_ciha_sem_cnpj_nascimento_nem_residencia(self):
        campos = [("ANO_CMPT", "C", 4), ("MES_CMPT", "C", 2), ("ESPEC", "C", 2), ("CGC_HOSP", "C", 14), ("MUNIC_RES", "C", 6), ("NASC", "C", 8),
                  ("SEXO", "C", 1), ("UTI_MES_TO", "N", 3), ("PROC_REA", "C", 10), ("QT_PROC", "N", 6), ("DT_ATEND", "C", 8), ("DT_SAIDA", "C", 8),
                  ("DIAG_PRINC", "C", 4), ("NATUREZA", "C", 2), ("GESTAO", "C", 1), ("MUNIC_MOV", "C", 6), ("IDADE", "C", 2), ("DIAS_PERM", "N", 5),
                  ("MORTE", "N", 1), ("CAR_INT", "C", 2), ("CNES", "C", 7), ("CGC_CONSOR", "C", 14), ("MODALIDADE", "C", 2)]
        lin = lambda p, q, d, m: ["2026", "09", "03", "11111111000111", "320530", "19800101", "F", 0, p, q, "20260901", "20260905", "O800", "50", "M",
                                  "320350", "30", d, m, "01", "2483998", "22222222000122", "02"]
        regs = [lin("0310010039", 1, 3, 0), lin("0310010039", 1, 4, 1), lin("0411010034", 2, 2, 0)]
        r = K.converter_arquivo(self.con, self.grava("CIHAES2609.dbc", montar_dbc(campos, regs)))
        self.assertEqual((r["tabela"], r["linhas"], r["grupos"]), ("ciha", 3, 2))
        self.assertEqual(self.con.execute("SELECT n_linhas, qt_proc, dias_perm, mortes FROM ciha WHERE proc_rea='0310010039'").fetchone(), (2, 2, 7, 1))
        despejo = "\n".join(self.con.iterdump())
        for sensivel in ("11111111000111", "22222222000122", "19800101", "20260901"):
            self.assertNotIn(sensivel, despejo)


    def _dbc_da_tabela(self, tabela, extras, n=3):
        _, dims, meds, _ = K.TABELAS[tabela]
        campos = [(c, "C", 14) for _, c in dims] + [(c, "N", 6) for _, c, _ in meds] + [(c, "C", 14) for c in extras]
        linhas = []
        for k in range(n):
            lin = [("2483998" if k < 2 else "2484943") if c == "CNES" else "320350" if c == "CODUFMUN" else "225125" if c == "CBO" else f"v{k % 2}" if tp == "C" else 2
                   for c, tp, _ in [(c, "C", 0) for _, c in dims]]
            lin += [3 for _ in meds] + ["SEGREDO-123456" for _ in extras]
            linhas.append(lin)
        return montar_dbc(campos, linhas)

    def test_er_conta_rejeicoes_sem_numero_da_aih(self):
        campos = [("SEQUENCIA", "N", 9), ("REMESSA", "C", 21), ("CNES", "C", 7), ("AIH", "C", 13), ("ANO", "C", 4), ("MES", "C", 2), ("DT_INTER", "C", 10),
                  ("DT_SAIDA", "C", 10), ("MUN_MOV", "C", 6), ("UF_ZI", "C", 6), ("MUN_RES", "C", 6), ("UF_RES", "C", 2), ("CO_ERRO", "C", 6)]
        lin = lambda aih, erro: [1, "REMESSA-SECRETA-0001", "2483998", aih, "2026", "09", "2026-09-01", "2026-09-05", "320350", "320000", "320530", "ES", erro]
        regs = [lin("3220000000011", "001"), lin("3220000000022", "001"), lin("3220000000033", "014")]
        r = K.converter_arquivo(self.con, self.grava("ERES2609.dbc", montar_dbc(campos, regs)))
        self.assertEqual((r["tabela"], r["linhas"], r["grupos"]), ("er", 3, 2))
        self.assertEqual(self.con.execute("SELECT n_linhas FROM er WHERE co_erro='001'").fetchone()[0], 2)
        despejo = "\n".join(self.con.iterdump())
        for sensivel in ("3220000000011", "REMESSA-SECRETA", "2026-09-01", "320530"):
            self.assertNotIn(sensivel, despejo)

    def test_novos_grupos_cnes_convertem_e_nao_guardam_dado_pessoal(self):
        casos = {"LTES2610": ("lt", []), "EQES2610": ("eq", []), "SRES2610": ("sr", ["CPF_CNPJ", "CNPJ_MAN"]), "EPES2610": ("ep", ["NOME_EQP", "NOMEAREA"]),
                 "INES2610": ("inc", ["CPF_CNPJ", "COD_CEP"]), "RCES2610": ("rc", []), "EFES2610": ("ef", []),
                 "STES2610": ("st", ["CPF_CNPJ", "CO_BANCO", "C_CORREN", "ALVARA"]),
                 "PFES2610": ("pf", ["CPF_PROF", "NOMEPROF", "CNS_PROF", "REGISTRO", "UFMUNRES"])}
        for nome, (tab, extras) in casos.items():
            r = K.converter_arquivo(self.con, self.grava(nome + ".dbc", self._dbc_da_tabela(tab, extras)))
            self.assertEqual((r["tabela"], r["linhas"]), (tab, 3), nome)
        despejo = "\n".join(self.con.iterdump())
        self.assertNotIn("SEGREDO-123456", despejo)
        pf = self.con.execute("SELECT SUM(n_linhas), SUM(hora_amb) FROM pf").fetchone()
        self.assertEqual(pf, (3, 9))
        self.assertEqual(self.con.execute("SELECT SUM(n_linhas) FROM sr").fetchone()[0], 3)   # tabela sem medida: controle por linhas
        self.assertEqual(len(K.pendentes(self.con)), 0)
        for t in ("pf", "st", "sr", "ep"):
            colunas = {c[1] for c in self.con.execute(f"PRAGMA table_info({t})")}
            for proibida in ("cpf_prof", "nomeprof", "cns_prof", "registro", "ufmunres", "cpf_cnpj", "cnpj_man", "cod_cep", "c_corren", "alvara", "nome_eqp"):
                self.assertNotIn(proibida, colunas)


class MudancaDeLayout(unittest.TestCase):
    def test_tabela_vazia_com_layout_antigo_e_recriada_e_com_dados_para(self):
        import sqlite3 as sq
        caminho = os.path.join(tempfile.mkdtemp(), "m.sqlite")
        K.abrir_banco(caminho).close()
        con = sq.connect(caminho)
        con.execute("DROP TABLE hb")
        con.execute("CREATE TABLE hb (arquivo TEXT, cnes TEXT, n_linhas INTEGER, PRIMARY KEY (arquivo, cnes))")
        con.commit()
        con.close()
        con = K.abrir_banco(caminho)            # vazia: recria com o layout atual
        self.assertIn("sgruphab", [r[1] for r in con.execute("PRAGMA table_info(hb)")])
        con.execute("INSERT INTO hb (arquivo,cnes,codufmun,sgruphab,cmpt_ini,cmpt_fim,dtportar,portaria,maportar,competen,tp_unid,vinc_sus,esfera_a,nat_jur,n_linhas,nuleitos) "
                    "VALUES ('x','1','2','3','4','5','6','7','8','9','a','b','c','d',1,1)")
        con.execute("DROP TABLE lt")
        con.execute("CREATE TABLE lt (arquivo TEXT, cnes TEXT, n_linhas INTEGER, PRIMARY KEY (arquivo, cnes))")
        con.execute("INSERT INTO lt VALUES ('x','1',1)")
        con.commit()
        con.close()
        with self.assertRaises(RuntimeError):   # com dados: nao apaga, avisa
            K.abrir_banco(caminho)


class LayoutsReais(unittest.TestCase):
    def test_todo_campo_lido_existe_no_arquivo_real(self):
        mapa = {"hb": "HB", "inc": "IN", "lt": "LT", "eq": "EQ", "pf": "PF", "rc": "RC", "ef": "EF", "sr": "SR", "ep": "EP", "st": "ST", "er": "ER"}
        for tabela, grupo in mapa.items():
            _, dims, meds, _c = K.TABELAS[tabela]
            usados = [c for _, c in dims] + [c for _, c, _ in meds]
            ausentes = [c for c in usados if c not in LAYOUTS_REAIS[grupo]]
            self.assertEqual(ausentes, [], f"{tabela}: campos que o arquivo real nao tem")
            self.assertFalse(set(usados) & K.NUNCA)


if __name__ == "__main__":
    unittest.main()
