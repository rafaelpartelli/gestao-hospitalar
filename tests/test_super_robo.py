import json, os, sqlite3, sys, tempfile, unittest
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "super_robo"))
sys.path.insert(0, os.path.join(AQUI, "..", "notebook_app"))
sys.path.insert(0, os.path.join(AQUI, "..", "robo"))
if os.environ.get("ROBO_EXTRA"):
    sys.path.insert(0, os.environ["ROBO_EXTRA"])
T = tempfile.mkdtemp()
os.environ.update({"PARTELLI_BASE": T, "SALA_DADOS": os.path.join(T, "sala"), "DOSSIE_SAIDA": os.path.join(T, "dossie"),
                   "PARTELLI_BANCO": os.path.join(T, "b.sqlite"), "PARTELLI_ESTADO": tempfile.mkdtemp(), "PAINEL_DOWNLOADS": tempfile.mkdtemp()})
import consolidar as C
import converter_sqlite as K

MONT, NV, ITA = "3203502", "3203908", "3202801"


def grava(rel, obj):
    p = os.path.join(C.SALA, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as a:
        json.dump(obj, a)


def prepara():
    agora = C.agora()
    grava("territorio.json", {"gerado_em": agora, "fonte": "SICONFI", "municipios": [{"cod": MONT, "nome": "Montanha", "uf": "ES", "pop": 19830}]})
    grava("despesa.json", {"gerado_em": agora, "fonte": "SICONFI DCA", "exercicio": 2025, "campos": ["empenhada", "liquidada", "paga", "populacao"], "mun": {MONT: [10, 9, 8, 19830]}})
    grava("siops/ES.json", {"gerado_em": agora, "campos": ["ano", "pct"], "m": {MONT: {"atual": [2026, 21.5]}}})
    grava("siops_resumo.json", {"fonte": "SIOPS RREO Anexo 12"})
    grava("leitos.json", {"gerado_em": agora, "fonte": "CNES", "competencia": "202609", "campos": ["EST", "SUS"], "mun": {MONT[:6]: [1, 35]}})
    con = K.abrir_banco(C.BANCO)
    cols_rd = "(arquivo,cnes,ano,mes,proc_rea,diag_princ,espec,car_int,complex,financ,munic_mov,n_linhas,val_sh,val_sp,val_tot,dias_perm,qt_diarias,uti_dias,mortes)"
    for cnes, mun, proc, n, tot in (("2483998", "320350", "0310010039", 2, 300.0), ("2483998", "320350", "0411010034", 1, 700.0), ("2484943", "320390", "0310010039", 5, 9999.0)):
        con.execute(f"INSERT INTO rd {cols_rd} VALUES ('RDES2601.dbc',?,'2026','01',?,'O80','03','01','02','04',?,?,?,?,?,6,0,0,1)", (cnes, proc, mun, n, tot * .6, tot * .4, tot))
    con.execute("INSERT INTO sp (arquivo,cnes,ano,mes,proc_rea,ato_prof,tp_ato,cbo,complex,financ,n_linhas,qtd_ato,val_ato) VALUES ('SPES2601.dbc','2483998','2026','01','p','a','01','225125','02','04',1,3,50.5)")
    con.execute("INSERT INTO sp (arquivo,cnes,ano,mes,proc_rea,ato_prof,tp_ato,cbo,complex,financ,n_linhas,qtd_ato,val_ato) VALUES ('SPES2601.dbc','2484943','2026','01','p','a','01','225125','02','04',1,9,999)")
    for mun, proc, qa, va in (("320350", "0301010072", 40, 400.0), ("320350", "0202010120", 10, 900.0), ("320390", "0301010072", 7, 7777.0)):
        con.execute("INSERT INTO pa (arquivo,cnes,mvm,cmp,proc_id,cbo,tpfin,subfin,nivcpl,ufmun,n_linhas,qtd_pro,qtd_apr,val_pro,val_apr) VALUES ('PAES2601.dbc','2483998','202601','202601',?,'225125','01','0100','0',?,1,?,?,?,?)", (proc, mun, qa + 5, qa, va + 50, va))
    con.execute("INSERT INTO hb (arquivo,cnes,codufmun,sgruphab,cmpt_ini,cmpt_fim,dtportar,portaria,maportar,competen,tp_unid,vinc_sus,esfera_a,nat_jur,n_linhas,nuleitos) "
                "VALUES ('HBES2610.dbc','2483998','320350','0601','202001','999999','2020-01-10','PORTARIA 100','202001','202610','05','1','03','1023',1,10)")
    con.execute("INSERT INTO hb (arquivo,cnes,codufmun,sgruphab,cmpt_ini,cmpt_fim,dtportar,portaria,maportar,competen,tp_unid,vinc_sus,esfera_a,nat_jur,n_linhas,nuleitos) "
                "VALUES ('HBES2610.dbc','2484943','320390','0601','202001','999999','2020-01-10','PORTARIA 101','202001','202610','05','1','03','1023',1,99)")
    con.execute("INSERT INTO ciha (arquivo,cnes,ano,mes,proc_rea,diag_princ,espec,car_int,natureza,gestao,modalidade,munic_mov,n_linhas,qt_proc,dias_perm,uti_dias,mortes) "
                "VALUES ('CIHAES2609.dbc','7777777','2026','09','0310010039','O80','03','01','50','M','02','320350',4,5,12,0,1)")
    con.execute("INSERT INTO arquivos VALUES ('RDES2601.dbc','rd',1,1,1,1,'2026-11-23T23:00:00')")
    con.commit()
    con.close()


class Dossie(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        prepara()
        C.main([])
        cls.d = json.load(open(os.path.join(C.SAIDA, f"{MONT}.json")))

    def test_municipio_e_populacao(self):
        self.assertEqual(self.d["municipio"]["nome"], "Montanha")
        self.assertEqual(self.d["municipio"]["populacao"]["valor"], 19830)

    def test_zip_de_campos_e_fonte(self):
        desp = self.d["secoes"]["financeiro"]["despesa_saude"]
        self.assertEqual(desp["valores"]["paga"], 8)
        self.assertEqual(self.d["secoes"]["financeiro"]["siops"]["fonte"], "SIOPS RREO Anexo 12")
        self.assertEqual(self.d["secoes"]["cnes"]["leitos"]["valores"]["SUS"], 35)   # chave de 6 digitos

    def test_sih_so_do_municipio(self):
        sih = self.d["secoes"]["producao"]["sih"]
        self.assertEqual(sih["cnes_com_aih"], ["2483998"])
        mes = sih["aih_por_mes"][0]
        self.assertEqual((mes["aih"], mes["valor_total"], mes["media_aih"]), (3, 1000.0, 333.33))
        self.assertEqual(sih["principais_procedimentos"][0]["procedimento"], "0411010034")
        self.assertEqual(sih["servicos_profissionais_por_mes"][0]["atos"], 3)

    def test_sia_somente_aprovado_do_municipio(self):
        sia = self.d["secoes"]["producao"]["sia_aprovado"]
        self.assertEqual(sia["por_mes"][0], {"mes_processamento": "01/2026", "quantidade_aprovada": 50, "valor_aprovado": 1300.0})
        txt = json.dumps(sia)
        self.assertNotIn("val_pro", txt)
        self.assertNotIn("apresentad", txt)

    def test_pendencias_sem_inventar(self):
        self.assertTrue(any("emendas" in p for p in self.d["pendencias"]))
        self.assertTrue(any("descricao_codigos" in p for p in self.d["pendencias"]))   # codigo sem descricao: nao inventar
        self.assertIsInstance(self.d["secoes"]["recursos"]["transferencias_uniao_saude"], str)   # arquivo ausente vira marcador

    def test_habilitacoes_do_municipio(self):
        h = self.d["secoes"]["cnes"]["habilitacoes"]
        self.assertEqual((h["competencia"], h["total"], h["estabelecimentos"]), ("10/2026", 1, ["2483998"]))
        self.assertEqual(h["itens"][0]["portaria"], "PORTARIA 100")
        self.assertNotIn("PORTARIA 101", json.dumps(h))   # habilitacao de outro municipio nao vaza

    def test_ciha_sem_valor_e_so_do_municipio(self):
        c = self.d["secoes"]["producao"]["ciha"]
        self.assertEqual(c["por_mes"][0], {"competencia": "09/2026", "registros": 4, "quantidade_procedimentos": 5, "dias_permanencia": 12, "obitos": 1})
        self.assertEqual(c["cnes_com_ciha"], ["7777777"])
        ita = json.load(open(os.path.join(C.SAIDA, f"{ITA}.json")))
        self.assertTrue(ita["secoes"]["producao"]["ciha"]["situacao"].startswith("A confirmar"))
        self.assertTrue(ita["secoes"]["cnes"]["habilitacoes"]["situacao"].startswith("A confirmar"))

    def test_municipio_sem_dado(self):
        ita = json.load(open(os.path.join(C.SAIDA, f"{ITA}.json")))
        self.assertTrue(ita["secoes"]["producao"]["sih"]["aih_por_mes"]["situacao"].startswith("A confirmar"))
        self.assertTrue(ita["secoes"]["producao"]["sia_aprovado"]["por_mes"]["situacao"].startswith("A confirmar"))
        nv = json.load(open(os.path.join(C.SAIDA, f"{NV}.json")))   # outro municipio nao vaza para Montanha
        self.assertEqual(nv["secoes"]["producao"]["sih"]["aih_por_mes"][0]["valor_total"], 9999.0)

    def test_sem_dado_pessoal_no_dossie(self):
        txt = json.dumps(self.d)
        for proibido in ("n_aih", "cpf", "cns", "nasc"):
            self.assertNotIn(proibido, txt.lower())


if __name__ == "__main__":
    unittest.main()
