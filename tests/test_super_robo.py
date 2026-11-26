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
    cols_rd = "(arquivo,cnes,ano,mes,proc_rea,diag_princ,espec,car_int,complex,financ,munic_mov,n_linhas,val_sh,val_sp,val_tot,dias_perm,qt_diarias,uti_dias,mortes,val_sh_fed,val_sp_fed)"
    for cnes, mun, proc, n, tot in (("2483998", "320350", "0310010039", 2, 300.0), ("2483998", "320350", "0411010034", 1, 700.0), ("2484943", "320390", "0310010039", 5, 9999.0)):
        con.execute(f"INSERT INTO rd {cols_rd} VALUES ('RDES2601.dbc',?,'2026','01',?,'O80','03','01','02','04',?,?,?,?,?,6,0,0,1,0,0)", (cnes, proc, mun, n, tot * .6, tot * .4, tot))
    con.execute("INSERT INTO sp (arquivo,cnes,ano,mes,proc_rea,ato_prof,tp_ato,cbo,complex,financ,n_linhas,qtd_ato,val_ato) VALUES ('SPES2601.dbc','2483998','2026','01','p','a','01','225125','02','04',1,3,50.5)")
    con.execute("INSERT INTO sp (arquivo,cnes,ano,mes,proc_rea,ato_prof,tp_ato,cbo,complex,financ,n_linhas,qtd_ato,val_ato) VALUES ('SPES2601.dbc','2484943','2026','01','p','a','01','225125','02','04',1,9,999)")
    for mun, proc, qa, va in (("320350", "0301010072", 40, 400.0), ("320350", "0202010120", 10, 900.0), ("320390", "0301010072", 7, 7777.0)):
        con.execute("INSERT INTO pa (arquivo,cnes,mvm,cmp,proc_id,cbo,tpfin,subfin,nivcpl,ufmun,n_linhas,qtd_pro,qtd_apr,val_pro,val_apr) VALUES ('PAES2601.dbc',?,'202601','202601',?,'225125','01','0100','0',?,1,?,?,?,?)", ("2483998" if mun == "320350" else "2484943", proc, mun, qa + 5, qa, va + 50, va))
    con.execute("INSERT INTO hb (arquivo,cnes,codufmun,sgruphab,cmpt_ini,cmpt_fim,dtportar,portaria,maportar,competen,tp_unid,vinc_sus,esfera_a,nat_jur,n_linhas,nuleitos) "
                "VALUES ('HBES2610.dbc','2483998','320350','0601','202001','999999','2020-01-10','PORTARIA 100','202001','202610','05','1','03','1023',1,10)")
    con.execute("INSERT INTO hb (arquivo,cnes,codufmun,sgruphab,cmpt_ini,cmpt_fim,dtportar,portaria,maportar,competen,tp_unid,vinc_sus,esfera_a,nat_jur,n_linhas,nuleitos) "
                "VALUES ('HBES2610.dbc','2484943','320390','0601','202001','999999','2020-01-10','PORTARIA 101','202001','202610','05','1','03','1023',1,99)")
    con.execute("INSERT INTO ciha (arquivo,cnes,ano,mes,proc_rea,diag_princ,espec,car_int,natureza,gestao,modalidade,munic_mov,n_linhas,qt_proc,dias_perm,uti_dias,mortes) "
                "VALUES ('CIHAES2609.dbc','7777777','2026','09','0310010039','O80','03','01','50','M','02','320350',4,5,12,0,1)")
    def ins(tabela, **kw):
        _, dims, meds, _c = K.TABELAS[tabela]
        row = {c: "0" for c, _ in dims}
        row.update({c: 0 for c, _, _ in meds})
        row.update(kw)
        cols = ["arquivo", "n_linhas"] + list(row)
        con.execute(f"INSERT INTO {tabela} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", [f"{tabela.upper()}ES2610.dbc", kw.pop("n_linhas", 1)] + list(row.values()))
    C10 = "202610"
    ins("lt", cnes="2483998", codufmun="320350", tp_leito="01", codleito="03", competen=C10, qt_exist=20, qt_contr=20, qt_sus=18, qt_nsus=2)
    ins("lt", cnes="2484943", codufmun="320390", tp_leito="01", codleito="03", competen=C10, qt_exist=99, qt_contr=99, qt_sus=99, qt_nsus=0)
    ins("eq", cnes="2483998", codufmun="320350", tipequip="02", codequip="05", ind_sus="1", ind_nsus="0", competen=C10, qt_exist=3, qt_uso=2)
    ins("eq", cnes="2484943", codufmun="320390", tipequip="02", codequip="05", competen=C10, qt_exist=77, qt_uso=77)
    ins("pf", cnes="2483998", codufmun="320350", cbo="225125", vinculac="010101", prof_sus="1", competen=C10, horahosp=100, hora_amb=40)
    ins("pf", cnes="2483998", codufmun="320350", cbo="225125", vinculac="010102", prof_sus="1", competen=C10, horahosp=0, hora_amb=20)
    ins("pf", cnes="2484943", codufmun="320390", cbo="999999", competen=C10, hora_amb=500)
    ins("sr", cnes="2483998", codufmun="320350", serv_esp="121", class_sr="001", competen=C10)
    ins("sr", cnes="2484943", codufmun="320390", serv_esp="122", class_sr="002", competen=C10)
    ins("ep", cnes="2483998", codufmun="320350", tipo_eqp="70", idequipe="INE1", dt_ativa="202001", dt_desat="", competen=C10)
    ins("ep", cnes="2483998", codufmun="320350", tipo_eqp="70", idequipe="INE2", dt_ativa="202001", dt_desat="202101", competen=C10)
    ins("st", cnes="2483998", codufmun="320350", tp_unid="05", natureza="3", nat_jur="1023", competen=C10, qtleitp1=20, qtinst01=2)
    ins("st", cnes="9999999", codufmun="320350", tp_unid="02", competen=C10)
    ins("inc", cnes="2483998", codufmun="320350", sgruphab="0701", cmpt_ini="202001", cmpt_fim="999999", portaria="INC 1", competen=C10)
    con.execute("CREATE TABLE rejeicao_rec (cnes TEXT, ano TEXT, mes TEXT, co_erro TEXT, rejeitadas INTEGER, recuperadas INTEGER, valor_recuperado REAL, calculado_em TEXT)")
    con.execute("INSERT INTO rejeicao_rec VALUES ('2483998','2026','01','001',1,1,80.0,'x')")
    con.execute("INSERT INTO rejeicao_rec VALUES ('2483998','2026','01','014',2,0,0,'x')")
    con.execute("INSERT INTO rejeicao_rec VALUES ('2483998','2026','09','014',5,0,0,'x')")
    ins("er", cnes="2483998", mun_mov="320350", ano="2026", mes="01", co_erro="001", n_linhas=1)
    ins("er", cnes="2483998", mun_mov="320350", ano="2026", mes="01", co_erro="014", n_linhas=2)
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
        self.assertTrue(any("tabelas_codigos" in p for p in self.d["pendencias"]))   # codigo sem descricao: nao inventar
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

    def test_grupos_cnes_do_municipio(self):
        c = self.d["secoes"]["cnes"]
        self.assertEqual(c["leitos_por_tipo"]["totais"], {"existentes": 20, "contratados": 20, "sus": 18, "nao_sus": 2})
        self.assertEqual(c["equipamentos_cadastro"]["totais"], {"existentes": 3, "em_uso": 2})
        pf = c["profissionais_cadastro"]
        self.assertEqual((pf["vinculos"], pf["horas_ambulatoriais"], pf["horas_hospitalares"]), (2, 60, 100))
        self.assertEqual(pf["principais_cbo"][0]["cbo"], "225125")
        self.assertEqual(c["servicos_especializados"]["total_servicos_classificacoes"], 1)
        self.assertEqual((c["equipes_cadastro"]["total_equipes"], c["equipes_cadastro"]["itens"][0]["sem_data_de_desativacao"]), (2, 1))
        est = c["estabelecimentos"]
        self.assertEqual(est["total"], 2)
        self.assertEqual([h["cnes"] for h in est["com_leito_cadastrado"]], ["2483998"])
        self.assertEqual(est["com_leito_cadastrado"][0]["instalacoes"]["01"]["quantidade"], 2)
        self.assertEqual(c["incentivos"]["itens"][0]["portaria"], "INC 1")
        self.assertNotIn("99", json.dumps(c["leitos_por_tipo"]))          # leitos de outro municipio nao vazam
        self.assertNotIn("77", json.dumps(c["equipamentos_cadastro"]))
        self.assertNotIn("999999", json.dumps(c["profissionais_cadastro"]))
        self.assertNotIn('"122"', json.dumps(c["servicos_especializados"]))

    def test_visao_por_hospital(self):
        h = self.d["secoes"]["hospitais"]
        self.assertEqual([i["cnes"] for i in h["itens"]], ["2483998", "7777777"])   # AIH, e CIHA sem AIH
        hosp = h["itens"][0]
        self.assertEqual(hosp["cadastro"]["leitos"], {"competencia": "10/2026", "existentes": 20, "sus": 18, "nao_sus": 2})
        self.assertEqual(hosp["cadastro"]["habilitacoes"]["codigos"], ["0601"])
        ind = hosp["indicadores"]
        self.assertEqual((ind["aih"], ind["valor_total"], ind["media_por_aih"]), (3, 1000.0, 333.33))
        self.assertEqual((ind["permanencia_media_dias"], ind["mortalidade_hospitalar_pct"]), (4.0, 66.67))
        self.assertEqual(ind["ocupacao_estimada_pct"], round(12 / (18 * 31) * 100, 1))
        self.assertEqual(hosp["producao"]["sia_aprovado_total"], {"quantidade": 50, "valor": 1300.0})
        self.assertEqual(hosp["producao"]["sih_por_mes"][0]["ocupacao_estimada_pct"], round(12 / (18 * 31) * 100, 1))
        self.assertEqual(ind["ocupacao_estimada_leitos_existentes_pct"], round(12 / (20 * 31) * 100, 1))
        rj = hosp["rejeicao_sih"]
        self.assertEqual((rj["total_rejeitadas"], rj["total_aprovadas"], rj["pct_rejeicao_periodo"]), (3, 3, 50.0))
        self.assertEqual(rj["principais_codigos_erro"][0], {"codigo_erro": "014", "aih": 2})
        rc = rj["reapresentacao"]
        self.assertEqual((rc["competencia_em_aberto"], rc["rejeitadas_em_aberto"], rc["rejeitadas_fechadas"], rc["recuperadas"], rc["nao_recuperadas"]), ("01/2026", 8, 0, 0, 0))
        self.assertEqual(hosp["criticas"], [])
        self.assertIsNone(h["itens"][1]["indicadores"])
        self.assertEqual(h["criticas_por_severidade"], {"Alta": 0, "Media": 0, "Baixa": 0})
        self.assertNotIn("2484943", json.dumps(h))   # hospital de outro municipio nao entra

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


class Criticas(unittest.TestCase):
    def test_regras_das_criticas(self):
        import hospitais as H
        sih = [{"competencia": "01/2026", "aih": 5, "valor_total": 1000.0, "sh": 500.0, "sp": 400.0, "dias_permanencia": 10, "obitos": 0, "dias_uti": 0},
               {"competencia": "04/2026", "aih": 5, "valor_total": 1000.0, "sh": 600.0, "sp": 400.0, "dias_permanencia": 900, "obitos": 0, "dias_uti": 0}]
        cad = {"leitos": {"existentes": 0, "sus": 5, "nao_sus": 0}, "habilitacoes": {"total": 0, "codigos": []}}
        ind = H._indicadores(sih, 5)
        cod = {k["codigo"][:3]: k for k in H._criticas("9", cad, sih, ind)}
        self.assertEqual(sorted(cod), ["C01", "C02", "C03", "C04", "C05"])
        self.assertEqual((cod["C01"]["severidade"], cod["C02"]["severidade"], cod["C03"]["status"]), ("Alta", "Alta", "A verificar"))
        self.assertIn("02/2026, 03/2026", cod["C03"]["descricao"])
        self.assertEqual(H._indicadores([], 5), None)
        self.assertNotIn("ocupacao_estimada_pct", H._indicadores(sih, 0))   # sem leito SUS: nao estima


class PlanoDeAvanco(unittest.TestCase):
    def test_criticas_de_rejeicao_e_plano(self):
        import hospitais as H
        rec = {"rejeitadas_fechadas": 100, "recuperadas": 40, "nao_recuperadas": 60,
               "por_codigo_erro": [{"codigo_erro": "X1", "rejeitadas": 80, "recuperadas": 30, "nao_recuperadas": 50, "pct_recuperadas": 37.5},
                                   {"codigo_erro": "X2", "rejeitadas": 20, "recuperadas": 18, "nao_recuperadas": 2, "pct_recuperadas": 90.0}]}
        cad = {"leitos": {"existentes": 35, "sus": 32, "nao_sus": 3}, "estabelecimento": {"leitos_p1_p2_p3": [4, 18, 0]}, "habilitacoes": {"total": 1}}
        ind = {"media_por_aih": 400.0}
        crit = H._criticas("9", cad, [], ind, rec)
        cod = {k["codigo"]: k for k in crit}
        self.assertIn("C06-9", cod)
        c7 = [k for k in crit if k["codigo"].startswith("C07-")]
        self.assertEqual(sorted((k["codigo"], k["severidade"]) for k in c7), [("C07-X1-9", "Alta"), ("C07-X2-9", "Media")])
        self.assertTrue(any(k["codigo"].startswith("C08-X1") for k in crit))      # 80 de 100 concentrados
        plano = H._plano(crit, rec, ind)
        primeiro = plano["itens"][0]
        self.assertEqual(primeiro["prioridade"], "Alta")
        self.assertEqual(primeiro["perda_por_rejeicao_rs"], 50 * 400.0)
        self.assertIn("ESTIMATIVA", primeiro["obs_perda"])
        self.assertIsNone(primeiro["ganho_estimado_rs"])                          # ganho e lancado pelo gestor
        self.assertTrue(plano["pendencia_ganho"].startswith("[PREENCHER"))
        # C02: com os complementos federais o total fecha e nao ha alerta; sem eles, ha
        fecha = [{"competencia": "03/2026", "valor_total": 165.0, "sh": 100.0, "sp": 50.0, "sh_fed": 10.0, "sp_fed": 5.0}]
        self.assertFalse([k for k in H._criticas("9", {"leitos": {}}, fecha, None) if k["codigo"].startswith("C02")])
        fecha[0]["sh_fed"] = 0.0
        self.assertTrue([k for k in H._criticas("9", {"leitos": {}}, fecha, None) if k["codigo"].startswith("C02")])
        self.assertEqual(H._plano([], None, None), {"itens": [], "total": 0, "pendencia_ganho": None})
        self.assertEqual([k for k in H._criticas("9", {"leitos": {"existentes": 20}, "estabelecimento": {"leitos_p1_p2_p3": [20, 0, 0]}}, [], None, {"rejeitadas_fechadas": 5, "por_codigo_erro": [{"codigo_erro": "Z", "rejeitadas": 5, "recuperadas": 5, "nao_recuperadas": 0, "pct_recuperadas": 100.0}]})], [])


class ChecklistHabilitacao(unittest.TestCase):
    def test_status_por_portaria_e_vigencia(self):
        import hospitais as H
        con = K.abrir_banco(os.path.join(tempfile.mkdtemp(), "h.sqlite"))
        base = "INSERT INTO hb (arquivo,cnes,codufmun,sgruphab,cmpt_ini,cmpt_fim,dtportar,portaria,maportar,competen,tp_unid,vinc_sus,esfera_a,nat_jur,n_linhas,nuleitos) VALUES ('x','9','320390',?,?,?,?,?,'','202610','05','1','03','1023',1,?)"
        con.execute(base, ("0601", "202001", "999999", "20200110", "PORTARIA 1", 10))     # vigente com portaria
        con.execute(base, ("0602", "202001", "999999", "", "", 0))                        # sem portaria
        con.execute(base, ("0603", "201901", "202301", "20190101", "PORTARIA 3", 5))      # vigencia encerrada
        tab = {"tabelas": {"habilitacao": {"0601": "UTI adulto tipo II"}}}
        ch = H._checklist_habilitacao(con, "9", tab)
        st = {i["codigo"]: (i["status"], i["motivo"]) for i in ch["itens"]}
        self.assertEqual(st["0601"][0], "Habilitado")
        self.assertEqual(st["0602"], ("A verificar", "sem portaria registrada no CNES"))
        self.assertEqual(st["0603"], ("A verificar", "vigencia encerrada em 01/2023"))
        self.assertEqual(ch["resumo"], {"Habilitado": 1, "A verificar": 2})
        self.assertEqual(next(i for i in ch["itens"] if i["codigo"] == "0601")["descricao"], "UTI adulto tipo II")
        self.assertTrue(ch["itens"][0]["portaria_no_dou"].startswith("[PREENCHER"))
        self.assertIn("atividades", ch["bases_do_cadastro"])
        crit = H._criticas_habilitacao("9", ch)
        self.assertEqual(sorted(k["codigo"] for k in crit), ["C09-0602-9", "C09-0603-9"])
        self.assertEqual(H._checklist_habilitacao(K.abrir_banco(os.path.join(tempfile.mkdtemp(), "v.sqlite")), "9")["situacao"][:12], "A confirmar:")


class TabelasCnesMaisRecente(unittest.TestCase):
    def test_usa_a_copia_mais_recente(self):
        import tempfile, time
        base = tempfile.mkdtemp()
        os.makedirs(os.path.join(base, "dados_repo"))
        sala = tempfile.mkdtemp()
        velho, novo = os.path.join(base, "dados_repo", "tabelas_cnes.json"), os.path.join(sala, "tabelas_cnes.json")
        json.dump({"tabelas": {"habilitacao": {"1": "a"}}}, open(velho, "w"))
        json.dump({"tabelas": {"habilitacao": {"1": "a"}, "equipe_dbf": {"70": "ESF"}}}, open(novo, "w"))
        os.utime(velho, (time.time() - 1000, time.time() - 1000))
        antigos = (C.BASE, C.SALA, list(C._TAB))
        C.BASE, C.SALA = base, sala
        C._TAB.clear()
        try:
            tab = C.tabelas_cnes()
            self.assertEqual(tab["_arquivo"], novo)
            self.assertIn("equipe_dbf", tab["tabelas"])
            self.assertIn("equipe_dbf", C.S.secao_tabelas(tab)["grupos_de_tabela"])
        finally:
            C.BASE, C.SALA = antigos[0], antigos[1]
            C._TAB.clear()
            C._TAB.extend(antigos[2])


class EmendasPorMunicipio(unittest.TestCase):
    def test_secao_emendas(self):
        import tempfile
        pasta = tempfile.mkdtemp()
        os.makedirs(os.path.join(pasta, "recursos"))
        json.dump({"gerado_em": "2026-11-18T10:32:26-03:00", "meta": {"extracao": "13/11/2026 15:00", "anoEm": 2026},
                   "m": {"3203502": {"em": [1000, 1000, 500], "eq": 4, "fb": 1}, "3204906": {"em": [1000, 1000, 0], "eq": 2},
                         "3202801": {"em": [0, 0, 0], "eq": 0}}}, open(os.path.join(pasta, "recursos", "ES.json"), "w"))
        antigo = C.SALA
        C.SALA = pasta
        try:
            e = C.secao_emendas("ES", "3203502")
            self.assertEqual((e["proposto_rs"], e["empenhado_rs"], e["pago_rs"], e["propostas"]), (1000, 1000, 500, 4))
            self.assertEqual((e["pct_empenhado_sobre_proposto"], e["pct_pago_sobre_empenhado"], e["saldo_a_pagar_rs"]), (100.0, 50.0, 500.0))
            self.assertEqual(e["ano_da_proposta"], 2026)
            self.assertEqual(C.secao_emendas("ES", "3204906")["pct_pago_sobre_empenhado"], 0.0)       # zero pago e resultado, nao ausencia
            self.assertIsNone(C.secao_emendas("ES", "3202801")["pct_pago_sobre_empenhado"])            # sem empenho: nao divide por zero
            self.assertIn("situacao", C.secao_emendas("ES", "3203908"))                                # municipio sem registro
            texto = json.dumps(e)
            for proibido in ("autor", "proposta_numero", "parlamentar"):
                self.assertNotIn(proibido, texto)
            C.SALA = tempfile.mkdtemp()
            self.assertTrue(C.secao_emendas("ES", "3203502").startswith("[PREENCHER"))                 # arquivo ausente vira marcador
        finally:
            C.SALA = antigo


class LancamentosDoGestor(unittest.TestCase):
    def _csv(self, linhas):
        import tempfile
        cab = "cnes;critica;codigo_erro;descricao_erro;qtd_aih;valor_rs;acao;prazo;responsavel;status;prioridade;ganho_estimado_rs;fonte\n"
        p = os.path.join(tempfile.mkdtemp(), "plano.csv")
        open(p, "w", encoding="utf-8").write(cab + "\n".join(linhas) + "\n")
        return p

    def test_validacao_e_lgpd(self):
        import plano_acoes as PA
        r = PA.carregar(self._csv([
            "2484943;;020069;campo X;8;3.850,80;Reapresentar;30/12/2026;Faturamento;Em andamento;Alta;5000,00;Relatorio de AIH rejeitadas do hospital",
            "2484943;;020071;;1;481,35;Corrigir;30/12/2026;Faturamento;Em andamento;;;",                      # valor sem fonte
            "2484943;;020071;;;;Treinar digitacao;31/12/2026;Faturamento;Em andamento;;;",                   # ok, sem valor
            "2484943;;020072;AIH 3220000000011;;;Reapresentar;;;;;;",                                         # numero de AIH
            "248494;;020072;;;;x;;;;;;",                                                                      # cnes invalido
            "2484943;;020073;;;;x;32/13/2026;;;;;",                                                           # prazo invalido
            "2484943;;020074;;;;x;;;Feito;;;"]))                                                              # status invalido
        self.assertEqual(len(r["lancamentos"]), 2)
        motivos = " | ".join(x["motivo"] for x in r["recusadas"])
        for trecho in ("fonte", "LGPD", "7 digitos", "DD/MM/AAAA", "status invalido"):
            self.assertIn(trecho, motivos)
        self.assertEqual(r["lancamentos"][0]["valor_rs"], 3850.80)
        self.assertEqual(PA.carregar("/nao/existe.csv")["lancamentos"], [])

    def test_aplicar_substitui_estimativa_e_cria_item(self):
        import plano_acoes as PA, hospitais as H
        rec = {"rejeitadas_fechadas": 20, "por_codigo_erro": [{"codigo_erro": "020069", "rejeitadas": 10, "recuperadas": 2, "nao_recuperadas": 8, "pct_recuperadas": 20.0}]}
        crit = H._criticas("2484943", {"leitos": {"existentes": 10}}, [], {"media_por_aih": 481.35}, rec)
        lanc = PA.carregar(self._csv([
            "2484943;;020069;campo X;8;3850,80;Reapresentar;30/12/2026;Faturamento;Em andamento;;5000,00;Relatorio do hospital",
            "2484943;;999999;;;;Acao nova;;;;Baixa;;"])) ["lancamentos"]
        plano = H._plano(crit, rec, {"media_por_aih": 481.35}, lanc, "2484943")
        it = next(i for i in plano["itens"] if i["critica_vinculada"] == "C07-020069-2484943")
        self.assertEqual((it["acao"], it["status"], it["ganho_estimado_rs"], it["perda_por_rejeicao_rs"]), ("Reapresentar", "Em andamento", 5000.0, 3850.8))
        self.assertIn("Substitui a estimativa", it["obs_perda"])
        self.assertTrue(it["lancado_pelo_gestor"])
        novo = next(i for i in plano["itens"] if i["critica_vinculada"] == "L-999999-2484943")
        self.assertEqual(novo["prioridade"], "Baixa")
        self.assertIn("2 acao", plano["pendencia_ganho"])       # C08 e o item novo seguem sem ganho


class Reapresentacao(unittest.TestCase):
    def test_meses_fechados_e_em_aberto(self):
        import hospitais as H, sqlite3
        con = sqlite3.connect(":memory:")
        con.execute("CREATE TABLE rd (ano TEXT, mes TEXT)")
        con.execute("INSERT INTO rd VALUES ('2026','09')")
        con.execute("CREATE TABLE rejeicao_rec (cnes TEXT, ano TEXT, mes TEXT, co_erro TEXT, rejeitadas INTEGER, recuperadas INTEGER, valor_recuperado REAL, calculado_em TEXT)")
        for lin in (("1", "2026", "03", "A", 100, 60, 3000.0), ("1", "2026", "04", "A", 50, 10, 500.0), ("1", "2026", "04", "B", 50, 50, 2500.0),
                    ("1", "2026", "09", "A", 40, 0, 0.0), ("2", "2026", "03", "A", 999, 999, 1.0)):
            con.execute("INSERT INTO rejeicao_rec VALUES (?,?,?,?,?,?,?,'x')", lin)
        sih = [{"aih": 10, "valor_total": 5000.0}]
        r = H._recuperacao(con, "1", sih)
        self.assertEqual((r["rejeitadas_fechadas"], r["recuperadas"], r["nao_recuperadas"], r["pct_recuperadas"]), (200, 120, 80, 60.0))
        self.assertEqual((r["rejeitadas_em_aberto"], r["competencia_em_aberto"]), (40, "09/2026"))
        self.assertEqual(r["valor_recuperado"], 6000.0)
        self.assertEqual(r["perda_liquida_estimada_rs"], 80 * 500.0)       # 80 nao recuperadas x media por AIH (5000 / 10)
        self.assertIn("ESTIMATIVA", r["obs_perda"])
        self.assertEqual(r["por_codigo_erro"][0], {"codigo_erro": "A", "rejeitadas": 150, "recuperadas": 70, "nao_recuperadas": 80, "pct_recuperadas": 46.7})
        self.assertTrue(H._recuperacao(con, "9", sih)["situacao"].startswith("A confirmar"))


class Descricoes(unittest.TestCase):
    TAB = {"tabelas": {"habilitacao": {"0601": "UTI adulto tipo II"}, "incentivo": {"0701": "07 - Incentivo exemplo"},
                       "tipo_leito": {"01": "01 - Cirurgico"}, "especialidade_leito": {"03": "Cirurgia geral"},
                       "equipamento": {"0205": "05 - Raio X"}, "servico_classificacao_n": {"121001": "Servico exemplo"},
                       "instalacoes_def": ["I* CENTRO CIRURGICO *.,QTINST", "IQt. Salas cirurgicas, QTINST01"]}}

    def test_descricoes_so_com_tabela(self):
        S = C.S
        self.assertEqual(S.desc_habilitacao(self.TAB, "0601"), "UTI adulto tipo II")
        self.assertEqual(S.desc_habilitacao(self.TAB, "9999"), "")
        self.assertEqual(S.desc_habilitacao(None, "0601"), "")
        self.assertEqual(S.desc_incentivo(self.TAB, "0701"), "Incentivo exemplo")
        self.assertEqual(S.desc_leito(self.TAB, "01", "3"), "Cirurgico · Cirurgia geral")
        self.assertEqual(S.desc_equipamento(self.TAB, "2", "5"), "Raio X")
        self.assertEqual(S.desc_servico(self.TAB, "121", "1"), "Servico exemplo")
        tab2 = {"tabelas": {"equipe_dbf": {"70": "Equipe exemplo"}, "regras_dbf": {"0001": "Regra exemplo"}, "estabelecimento_filantropico": {"1": "Sim"},
                            "equipamento_2507": {"0682": "Equip antigo"}, "servico_classificacao": {"160006": "Servico antigo"}}}
        self.assertEqual(S.desc_equipe(tab2, "070"), "Equipe exemplo")          # zeros a esquerda diferentes
        self.assertEqual(S.desc_regra(tab2, "1"), "Regra exemplo")
        self.assertEqual(S.desc_filantropico(tab2, "01"), "Sim")
        self.assertEqual(S.desc_equipamento(tab2, "6", "82"), "Equip antigo")
        self.assertEqual(S.desc_servico(tab2, "160", "6"), "Servico antigo")
        self.assertEqual((S.desc_equipe(None, "70"), S.desc_regra(tab2, "99"), S.desc_equipe(tab2, "")), ("", "", ""))
        self.assertEqual(S.mapa_instalacoes(self.TAB), {"01": "Centro cirurgico: Salas cirurgicas"})
        self.assertIsInstance(S.secao_tabelas(None), str)
        self.assertTrue(S.secao_tabelas(None).startswith("[PREENCHER"))


if __name__ == "__main__":
    unittest.main()



class MotivosDeRejeicao(unittest.TestCase):
    def test_tabela_do_manual(self):
        import motivos_rejeicao as MR
        self.assertEqual(len(MR.MOTIVOS), 230)
        for ausente in (3, 9, 80, 101, 114, 222):
            self.assertNotIn(ausente, MR.MOTIVOS)

    def test_descricao_so_para_seis_digitos_e_com_status(self):
        import motivos_rejeicao as MR
        d = MR.descricao("060082")
        self.assertEqual(d["texto_manual"], "DATA DA SAÍDA > DATA APRESENTAÇÃO")
        self.assertEqual(d["pagina_manual"], 153)
        self.assertIn("a confirmar", d["status"])
        self.assertIsNone(MR.descricao("010003"))
        self.assertIsNone(MR.descricao("014"))
        self.assertIsNone(MR.descricao(None))

    def test_critica_c07_leva_motivo_provavel(self):
        import hospitais as H
        rec = {"rejeitadas_fechadas": 20, "por_codigo_erro": [{"codigo_erro": "060082", "rejeitadas": 10, "recuperadas": 2, "nao_recuperadas": 8, "pct_recuperadas": 20.0}]}
        c = H._criticas("9", {"leitos": {"existentes": 20}, "estabelecimento": {"leitos_p1_p2_p3": [20, 0, 0]}}, [], None, rec)
        k = next(x for x in c if x["codigo"].startswith("C07-060082"))
        self.assertEqual(k["motivo_provavel"]["final_3_digitos"], "082")


class ValidarMotivos(unittest.TestCase):
    def test_sinais_de_data(self):
        import validar_motivos_rejeicao as V
        self.assertEqual(V.sinais("20260110", "20260305", "202602"), {"saida_apos_competencia": True, "saida_6m_antes": False, "inter_apos_saida": False})
        self.assertEqual(V.sinais("20260110", "20260120", "202602")["saida_apos_competencia"], False)
        self.assertEqual(V.sinais("20260310", "20260305", "202603")["inter_apos_saida"], True)
        self.assertTrue(V.sinais("20250101", "20250105", "202603")["saida_6m_antes"])
        self.assertEqual(V.sinais("", "xx", "202602"), {})

    def test_destino_da_aih_rejeitada(self):
        import validar_motivos_rejeicao as V
        self.assertEqual(V.destino([], "202603"), "nunca")
        self.assertEqual(V.destino([("202603", "", "")], "202603"), "mesma")
        self.assertEqual(V.destino([("202605", "", "")], "202603"), "posterior")
        self.assertEqual(V.destino([("202601", "", "")], "202603"), "anterior")


class RejeicaoPorCnes(unittest.TestCase):
    def test_ranking_participacao_e_recuperacao(self):
        import hospitais as H
        d = tempfile.mkdtemp()
        banco = os.path.join(d, "b.sqlite")
        con = sqlite3.connect(banco)
        con.execute("CREATE TABLE er (cnes TEXT, ano TEXT, mes TEXT, mun_mov TEXT, co_erro TEXT, n_linhas INTEGER)")
        con.execute("CREATE TABLE rd (cnes TEXT, ano TEXT, mes TEXT)")
        con.execute("CREATE TABLE rejeicao_rec (cnes TEXT, ano TEXT, mes TEXT, co_erro TEXT, rejeitadas INTEGER, recuperadas INTEGER, valor_recuperado REAL, calculado_em TEXT)")
        con.executemany("INSERT INTO er VALUES (?,?,?,?,?,?)", [("111", "2026", "01", "320530", "060082", 60), ("111", "2026", "02", "320530", "060120", 20),
                                                                ("222", "2026", "01", "320500", "020071", 20)])
        con.execute("INSERT INTO rd VALUES ('111','2026','03')")
        con.executemany("INSERT INTO rejeicao_rec VALUES (?,?,?,?,?,?,?,?)", [("111", "2026", "01", "060082", 60, 0, 0, "x"), ("111", "2026", "02", "060120", 20, 2, 10.0, "x"),
                                                                              ("222", "2026", "01", "020071", 20, 20, 5.0, "x")])
        con.commit()
        con.close()
        r = H.rejeicao_por_cnes(banco)
        self.assertEqual(r["total_rejeitadas_es"], 100)
        a, b = r["itens"]
        self.assertEqual((a["cnes"], a["rejeitadas"], a["pct_do_total"], a["pct_acumulado"], a["municipio_movimento"]), ("111", 80, 80.0, 80.0, "320530"))
        self.assertEqual((a["rejeitadas_fechadas"], a["recuperadas"], a["pct_recuperadas"]), (80, 2, 2.5))
        self.assertEqual(a["principais_codigos_erro"][0]["codigo_erro"], "060082")
        self.assertIn("motivo_provavel", a["principais_codigos_erro"][0])
        self.assertEqual((b["cnes"], b["pct_acumulado"], b["pct_recuperadas"]), ("222", 100.0, 100.0))
        self.assertNotIn("nome", a)

    def test_sem_base_ou_sem_er(self):
        import hospitais as H
        self.assertIn("A confirmar", H.rejeicao_por_cnes("/nao/existe.sqlite")["situacao"])


class ExportarSite(unittest.TestCase):
    def _dossie(self, extra=None):
        import json as J
        d = tempfile.mkdtemp()
        J.dump({"gerado_em": "g", "municipios": [{"cod": "3203908", "nome": "Municipio Teste"}]}, open(os.path.join(d, "indice.json"), "w"))
        J.dump({"gerado_em": "g", "secoes": {"hospitais": {"total": 2, "itens": [{"cnes": "1234567", "x": extra or "ok"}]}, "emendas": {"segredo": 1}}}, open(os.path.join(d, "3203908.json"), "w"))
        J.dump({"total_rejeitadas_es": 5, "itens": []}, open(os.path.join(d, "estado_ES_rejeicao_por_cnes.json"), "w"))
        return d

    def test_exporta_so_hospitais_e_estado(self):
        import exportar_site as E, json as J
        d, s = self._dossie(), tempfile.mkdtemp()
        r = E.exportar(d, s)
        self.assertEqual(sorted(r["gravados"]), ["rede_3203908.json", "rede_indice.json", "rede_rejeicao_es.json"])
        self.assertEqual(r["recusados"], [])
        m = J.load(open(os.path.join(s, "rede_3203908.json")))
        self.assertEqual(sorted(m), ["gerado_em", "hospitais", "municipio"])
        self.assertEqual(J.load(open(os.path.join(s, "rede_indice.json")))["municipios"], [{"cod": "3203908", "nome": "Municipio Teste", "hospitais": 2}])

    def test_guarda_recusa_sequencia_longa(self):
        import exportar_site as E
        d, s = self._dossie("12345678901234"), tempfile.mkdtemp()
        r = E.exportar(d, s)
        self.assertIn("rede_3203908.json", r["recusados"])
        self.assertFalse(os.path.exists(os.path.join(s, "rede_3203908.json")))
