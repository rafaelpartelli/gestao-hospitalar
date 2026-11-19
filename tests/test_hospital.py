import json, os, sys, tempfile, unittest
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, "..", "robo"))
if os.environ.get("ROBO_EXTRA"):
    sys.path.insert(0, os.environ["ROBO_EXTRA"])   # pasta robo/ da Sala de Gestao (comum.py e dbc.py), quando fora do pacote
os.environ["PARTELLI_ESTADO"] = tempfile.mkdtemp()
os.environ["PARTELLI_DADOS"] = tempfile.mkdtemp()
import hospital_comum as H
import coletar_hospital_sih as SIH
import coletar_hospital_sia as SIA
import coletar_hospital_cnes as CNES
from hospital_calc_py import capitulo_cid


class Comum(unittest.TestCase):
    def test_cnes_valido(self):
        self.assertTrue(H.cnes_valido("2483998")); self.assertFalse(H.cnes_valido("[PREENCHER: CNES]")); self.assertFalse(H.cnes_valido("123"))

    def test_competencias_recentes(self):
        nomes = ["RDES2607.dbc", "RDES2609.dbc", "RDES2608.dbc", "RDSP2609.dbc", "PAES2609a.dbc", "PAES2609b.dbc"]
        self.assertEqual(H.competencias_recentes(nomes, "RD", "ES", 2), ["2609", "2608"])
        self.assertEqual(H.competencias_recentes(nomes, "PA", "ES", 1), ["2609"])
        self.assertEqual(H.aamm_para_chave("2609"), "202609"); self.assertEqual(H.aamm_para_mmaaaa("2609"), "09/2026")

    def test_por_uf(self):
        self.assertEqual(H.por_uf([{"cnes": "1111111", "uf": "es"}, {"cnes": "2222222", "uf": "ES"}, {"cnes": "3333333", "uf": "MG"}]), {"ES": {"1111111", "2222222"}, "MG": {"3333333"}})

    def test_guarda_de_orcamento(self):
        H.registrar_trafego(5_900_000_000)
        H.checar_guardas(50_000_000)
        with self.assertRaises(H.ErroColeta):
            H.checar_guardas(200_000_000)

    def test_estado_de_arquivos(self):
        self.assertFalse(H.ja_processado("k", 10)); H.marcar_processado("k", 10)
        self.assertTrue(H.ja_processado("k", 10)); self.assertFalse(H.ja_processado("k", 11))

    @staticmethod
    def _dbf(nomes):
        """Cabecalho dBase minimo e valido (bytes), no formato lido por dbc.cabecalho."""
        import struct
        campos = b"".join(n.encode("latin-1").ljust(11, b"\x00") + b"C" + b"\x00" * 4 + bytes([8]) + b"\x00" * 15 for n in nomes)
        tam_cab = 32 + len(campos) + 1
        cab = bytes([3, 26, 1, 1]) + struct.pack("<IHH", 0, tam_cab, 1 + 8 * len(nomes)) + b"\x00" * 20
        return cab + campos + b"\x0d"

    def test_equipamentos_e_incentivos(self):
        e = CNES.resumir_equipamentos([{"TIPEQUIP": "1", "CODEQUIP": "01", "QT_EXIST": "3", "QT_USO": "2"},
                                       {"TIPEQUIP": "1", "CODEQUIP": "01", "QT_EXIST": "1", "QT_USO": "1"}])
        self.assertEqual(e["total_existentes"], 4); self.assertEqual(e["total_em_uso"], 3)
        i = CNES.resumir_incentivos([{"INCENTIV": "0101", "COMPETEN": "202610"}, {"INCENTIV": "0101", "COMPETEN": "202610"}, {}])
        self.assertEqual(len(i["itens"]), 1)

    def test_campos_obrigatorios_e_proibidos(self):
        d = self._dbf(["CNES", "VAL_TOT", "NOMEPROF", "N_AIH"])
        ler, aus, _ = H.campos_presentes(d, ["CNES", "VAL_TOT", "NOMEPROF", "N_AIH", "X"], ["CNES"])
        self.assertEqual(ler, ["CNES", "VAL_TOT"]); self.assertEqual(aus, ["X"])
        ler, _, _ = H.campos_presentes(d, ["CNES", "N_AIH"], ["CNES"], transitorios=("N_AIH",))
        self.assertIn("N_AIH", ler)
        with self.assertRaises(H.ErroColeta):
            H.campos_presentes(self._dbf(["A"]), ["CNES"], ["CNES"])

    def test_gravacao_atomica_e_indice(self):
        H.atualizar_hospital("1111111", "202609", "sih", {"a": 1}); H.atualizar_hospital("1111111", None, "cnes", {"b": 2})
        with open(os.path.join(H.SAIDA, "1111111.json")) as fh:
            d = json.load(fh)
        self.assertEqual(d["competencias"]["202609"]["sih"], {"a": 1}); self.assertEqual(d["cnes"], {"b": 2})
        H.atualizar_indice([{"cnes": "1111111", "uf": "ES", "nome": "Hospital X", "autorizado": False}, {"cnes": "2222222", "uf": "ES", "nome": "Y", "autorizado": True}])
        with open(os.path.join(H.SAIDA, "indice.json")) as fh:
            idx = json.load(fh)["hospitais"]
        self.assertIsNone(idx[0]["nome"]); self.assertEqual(idx[0]["competencias"], ["202609"]); self.assertEqual(idx[1]["nome"], "Y")


def rd(cnes, proc, tot, sh, sp, dias="3", morte="0", cid="J189", esp="03"):
    return {"CNES": cnes, "PROC_REA": proc, "VAL_TOT": tot, "VAL_SH": sh, "VAL_SP": sp, "DIAS_PERM": dias, "MORTE": morte, "DIAG_PRINC": cid, "ESPEC": esp}


class SIHTestes(unittest.TestCase):
    def test_agregar_rd(self):
        regs = [rd("1111111", "0303010010", "1000.00", "700.00", "300.00"), rd("1111111", "0303010010", "500.00", "500.00", "0.00", morte="1", cid="I219"),
                rd("1111111", "0407040064", "800.00", "500.00", "200.00"), rd("9999999", "0303010010", "9999", "1", "1")]
        por, lidos = SIH.agregar_rd(iter(regs), {"1111111"})
        d = por["1111111"]
        self.assertEqual(lidos, 4); self.assertEqual(d["aprovadas"], 3)
        self.assertAlmostEqual(d["valor_aprovado"], 2300.0); self.assertAlmostEqual(d["sh"], 1700.0); self.assertAlmostEqual(d["sp"], 500.0)
        self.assertEqual(d["obitos"], 1); self.assertEqual(d["dias_perm"], 9)
        self.assertEqual(d["aih_sem_sp"], 1); self.assertEqual(d["aih_sem_sh"], 0); self.assertEqual(d["aih_sh_sp_divergente"], 1)
        self.assertEqual(d["proc"]["0303010010"][0], 2)
        self.assertIn("X. Doenças do aparelho respiratório", d["cap"]); self.assertIn("IX. Doenças do aparelho circulatório", d["cap"])

    def test_rj_er_ligacao_por_numero_da_aih(self):
        rj, naih, _ = SIH.agregar_rj(iter([{"CNES": "1111111", "VAL_TOT": "200.00", "N_AIH": "A1"}, {"CNES": "1111111", "VAL_TOT": "100.00", "N_AIH": "A2"}, {"CNES": "5555555", "N_AIH": "A3"}]), {"1111111"})
        self.assertEqual(rj["1111111"]["rejeitadas"], 2); self.assertAlmostEqual(rj["1111111"]["valor_rejeitado"], 300.0); self.assertTrue(rj["1111111"]["tem_valor"])
        er, _ = SIH.agregar_er(iter([{"N_AIH": "A1", "CODERR": "104"}, {"N_AIH": "A2", "CODERR": "104"}, {"N_AIH": "A9", "CODERR": "7"}]), {"1111111"}, "CODERR", naih)
        self.assertEqual(er["1111111"], {"104": 2})

    def test_bloco_nao_leva_numero_de_aih_nem_dado_pessoal(self):
        por, _ = SIH.agregar_rd(iter([rd("1111111", "0303010010", "10", "6", "4")]), {"1111111"})
        rj, naih, _ = SIH.agregar_rj(iter([{"CNES": "1111111", "N_AIH": "SEGREDO123"}]), {"1111111"})
        er, _ = SIH.agregar_er(iter([{"N_AIH": "SEGREDO123", "CODERR": "104"}]), {"1111111"}, "CODERR", naih)
        b = SIH.montar_bloco(por["1111111"], rj["1111111"], er["1111111"], {}, [])
        txt = json.dumps(b, ensure_ascii=False)
        self.assertNotIn("SEGREDO123", txt); self.assertNotIn("N_AIH", txt)
        self.assertIsNone(b["valor_rejeitado"]); self.assertEqual(b["rejeitadas"], 1); self.assertIsNone(b["enviadas"])
        self.assertEqual(b["status_fonte"], "Em teste")


class SIATestes(unittest.TestCase):
    def test_partes_acumulam_e_glosa(self):
        a = [{"PA_CODUNI": "1111111", "PA_PROC_ID": "0301010072", "PA_QTDPRO": "10", "PA_QTDAPR": "8", "PA_VALPRO": "100.00", "PA_VALAPR": "80.00", "PA_FINANC": "06"}]
        b = [{"PA_CODUNI": "1111111", "PA_PROC_ID": "0204030188", "PA_QTDPRO": "5", "PA_QTDAPR": "5", "PA_VALPRO": "50.00", "PA_VALAPR": "50.00", "PA_FINANC": "06"}, {"PA_CODUNI": "0000000", "PA_PROC_ID": "x", "PA_VALAPR": "1"}]
        acum, _ = SIA.agregar_pa(iter(a), {"1111111"}); acum, _ = SIA.agregar_pa(iter(b), {"1111111"}, acum)
        bl = SIA.montar_bloco(acum["1111111"], {}, [])
        self.assertAlmostEqual(bl["valor_apresentado"], 150.0); self.assertAlmostEqual(bl["valor_aprovado"], 130.0); self.assertEqual(bl["linhas"], 2)
        self.assertEqual({g["grupo"] for g in bl["grupos"]}, {"02", "03"})
        self.assertEqual(bl["financiamento"][0]["codigo"], "06")


class CNESTestes(unittest.TestCase):
    def test_resumos(self):
        l = CNES.resumir_leitos([{"TP_LEITO": "1", "CODLEITO": "01", "QT_EXIST": "10", "QT_SUS": "8", "QT_CONTR": "0"}, {"TP_LEITO": "1", "CODLEITO": "01", "QT_EXIST": "5", "QT_SUS": "5", "QT_CONTR": "0"}, {"TP_LEITO": "2", "CODLEITO": "74", "QT_EXIST": "4", "QT_SUS": "4", "QT_CONTR": "0"}])
        self.assertEqual(l["total_existentes"], 19); self.assertEqual(l["total_sus"], 17); self.assertEqual(len(l["itens"]), 2)
        s = CNES.resumir_servicos([{"SERV_ESP": "125", "CLASS_SR": "001"}, {"SERV_ESP": "125", "CLASS_SR": "001"}, {"SERV_ESP": "126", "CLASS_SR": "002"}])
        self.assertEqual(len(s["itens"]), 2)
        h = CNES.resumir_habilitacoes([{"SGRUPHAB": "0901", "PORTARIA": "123"}, {"SGRUPHAB": "0901", "PORTARIA": "123"}])
        self.assertEqual(len(h["itens"]), 1)
        p = CNES.resumir_profissionais([{"CBO": "225125", "PROF_SUS": "1", "HORA_AMB": "20", "HORAOUTR": "0", "HORAHOSP": "10"}, {"CBO": "223505", "PROF_SUS": "0", "HORA_AMB": "0", "HORAOUTR": "0", "HORAHOSP": "40"}, {"CBO": "999999", "PROF_SUS": "1"}])
        g = {x["grupo"]: x for x in p["grupos"]}
        self.assertEqual(g["Médicos"]["vinculos"], 1); self.assertEqual(g["Médicos"]["horas_semanais"], 30); self.assertEqual(g["Enfermeiros"]["vinculos"], 1); self.assertEqual(g["Outros"]["vinculos"], 1)
        self.assertNotIn("NOMEPROF", json.dumps(p))


class CID(unittest.TestCase):
    def test_capitulos(self):
        self.assertTrue(capitulo_cid("D30").startswith("II.")); self.assertTrue(capitulo_cid("D50").startswith("III.")); self.assertTrue(capitulo_cid("H66").startswith("VIII.")); self.assertIsNone(capitulo_cid("123"))


if __name__ == "__main__":
    unittest.main()
