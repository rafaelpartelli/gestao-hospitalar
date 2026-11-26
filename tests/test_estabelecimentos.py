import os, sys, sqlite3, tempfile, unittest
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(AQUI, "..", "super_robo"), os.path.join(AQUI, "..", "robo")]
import estabelecimentos as E
import coletar_nomes_cnes as N


class T(unittest.TestCase):
    def banco(self):
        f = tempfile.mkstemp(suffix=".sqlite")[1]
        c = sqlite3.connect(f)
        c.executescript("""
        CREATE TABLE st(codufmun,cnes,competen,tp_unid,nat_jur);
        CREATE TABLE rd(munic_mov,cnes,ano,mes,n_linhas,val_tot,mortes,dias_perm);
        CREATE TABLE pa(ufmun,cnes,mvm,qtd_apr,val_apr,proc_id);
        CREATE TABLE ciha(munic_mov,cnes,ano,mes,n_linhas,qt_proc,dias_perm,mortes);
        CREATE TABLE er(cnes,ano,mes,n_linhas,co_erro);
        INSERT INTO er VALUES('1111111','2026','01',2,'0123');
        CREATE TABLE pf(codufmun,cnes,competen,cbo,n_linhas,hora_amb,horahosp,horaoutr);
        INSERT INTO st VALUES('320390','1111111','202610','05','1'),('320390','2222222','202610','02','1');
        INSERT INTO rd VALUES('320390','1111111','2026','01',10,5000.5,1,30);
        INSERT INTO pa VALUES('320390','2222222','202601',100,800.0,'0301010072'),('320390','1111111','202601',5,50.0,'0301010072');
        INSERT INTO ciha VALUES('320390','1111111','2026','02',4,8,12,0);
        INSERT INTO pf VALUES('320390','1111111','202610','225125',3,20,10,0),('320390','2222222','202610','225125',2,10,0,0);
        """)
        c.commit(); c.close(); return f

    def test_por_cnes(self):
        f = self.banco()
        try:
            r = E.montar(f, "3203908")
            m = {x["cnes"]: x for x in r["estabelecimentos"]}
            self.assertEqual(set(m), {"1111111", "2222222"})
            self.assertEqual(m["1111111"]["sih"][0]["aih"], 10)
            self.assertEqual(m["1111111"]["sih"][0]["rejeitadas"], 2)
            self.assertEqual(m["2222222"]["sia"]["por_mes"][0]["valor_aprovado"], 800.0)
            self.assertEqual(m["1111111"]["ciha"][0]["registros"], 4)
            self.assertEqual(m["1111111"]["profissionais"]["vinculos"], 3)
            self.assertNotIn("nome", m["1111111"])
        finally:
            os.remove(f)

    def test_sem_base(self):
        self.assertIn("situacao", E.montar("/tmp/nao_existe_x/y.sqlite", "3203908"))

    def test_nomes_lgpd(self):
        def buscar(url):
            return {"estabelecimentos": [
                {"codigo_cnes": "1111111", "nome_fantasia": "HOSPITAL TESTE", "codigo_tipo_unidade": "05"},
                {"codigo_cnes": "2222222", "nome_fantasia": "CONSULTORIO ISOLADO", "codigo_tipo_unidade": "22"},
                {"codigo_cnes": "3333333", "nome_fantasia": "DR FULANO", "codigo_tipo_unidade": "02"},
                {"codigo_cnes": "4444444", "nome_fantasia": "UBS 12345678901", "codigo_tipo_unidade": "02"}]}
        nomes, rec, erros = N.coletar([{"cod": "3203908"}], buscar=buscar, pausa=0)
        self.assertEqual(nomes, {"1111111": "HOSPITAL TESTE"})
        self.assertEqual(rec, 3); self.assertEqual(erros, [])

    def test_erro_de_rede_nao_grava(self):
        def buscar(url): raise OSError("sem rede")
        nomes, rec, erros = N.coletar([{"cod": "3203908"}], buscar=buscar, pausa=0)
        self.assertEqual(nomes, {}); self.assertEqual(len(erros), 1)


if __name__ == "__main__":
    unittest.main()
