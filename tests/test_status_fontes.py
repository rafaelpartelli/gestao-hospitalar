import json, os, sqlite3, sys, tempfile, unittest
from datetime import datetime, timedelta
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "robo"))
import status_fontes as S

AGORA = datetime(2026, 11, 26, 12, 0, tzinfo=S.BRT)


def arquivo(pasta, nome, dias_atras, obj=None):
    c = os.path.join(pasta, nome)
    os.makedirs(os.path.dirname(c), exist_ok=True)
    json.dump({"gerado_em": (AGORA - timedelta(days=dias_atras)).isoformat(), **(obj or {})}, open(c, "w"))


class T(unittest.TestCase):
    def setUp(self):
        self.sala, self.dados = tempfile.mkdtemp(), tempfile.mkdtemp()
        self.kw = dict(agora_=AGORA, sala=self.sala, dados=self.dados, banco=os.path.join(self.dados, "x.sqlite"))

    def test_ativa_com_arquivo_no_prazo(self):
        arquivo(self.sala, "ans.json", 10)
        r = S.avaliar({"id": "ans", "sistema": "ANS", "tipo": "arquivo", "arquivos": ["ans.json"], "frescor_dias": 90, "coletor": "coletar_ans"}, **self.kw)
        self.assertEqual(r["status"], "Ativa")
        self.assertIn("10 dia", r["resultado"])

    def test_desatualizada_vira_a_confirmar(self):
        arquivo(self.sala, "ans.json", 200)
        r = S.avaliar({"id": "ans", "sistema": "ANS", "tipo": "arquivo", "arquivos": ["ans.json"], "frescor_dias": 90, "coletor": "c"}, **self.kw)
        self.assertEqual(r["status"], "A confirmar")

    def test_falta_um_arquivo_nao_e_ativa(self):
        arquivo(self.sala, "despesa.json", 1)
        r = S.avaliar({"id": "s", "sistema": "S", "tipo": "arquivo", "arquivos": ["despesa.json", "receita.json"], "frescor_dias": 90, "coletor": "c"}, **self.kw)
        self.assertEqual(r["status"], "A confirmar")

    def test_bloqueada_declarada_nao_sonda(self):
        chamadas = []
        r = S.avaliar({"id": "dou", "sistema": "DOU", "tipo": "bloqueada", "bloqueio": "Exige login", "sonda": "https://x"}, sondar=lambda u: chamadas.append(u), **self.kw)
        self.assertEqual((r["status"], chamadas), ("Bloqueada", []))

    def test_descartada(self):
        self.assertEqual(S.avaliar({"id": "e", "sistema": "E", "tipo": "descartada"}, **self.kw)["status"], "Descartada")

    def test_manual_sem_coletor_com_resposta(self):
        r = S.avaliar({"id": "t", "sistema": "TabNet", "tipo": "manual", "sonda": "https://t"}, sondar=lambda u: {"http": 200, "testado_em": "2026-11-26T12:00:00-03:00"}, **self.kw)
        self.assertEqual(r["status"], "Manual")
        self.assertIn("HTTP 200", r["resultado"])

    def test_sonda_negada_vira_bloqueada(self):
        r = S.avaliar({"id": "t", "sistema": "T", "tipo": "manual", "sonda": "https://t"}, sondar=lambda u: {"status": "Bloqueada", "http": 403, "resultado": "HTTP 403"}, **self.kw)
        self.assertEqual(r["status"], "Bloqueada")

    def test_bloqueio_anterior_que_voltou_a_responder_nao_vira_ativa(self):
        f = {"id": "fns", "sistema": "FNS", "tipo": "arquivo", "arquivos": ["financiamento.json"], "frescor_dias": 30, "coletor": "c", "sonda": "https://f", "bloqueio_anterior": "HTTP 403 no GitHub."}
        r = S.avaliar(f, sondar=lambda u: {"http": 200}, **self.kw)
        self.assertEqual(r["status"], "A confirmar")

    def test_coletor_sem_saida_e_sem_rede(self):
        r = S.avaliar({"id": "a", "sistema": "A", "tipo": "arquivo", "arquivos": ["a.json"], "coletor": "coletar_a"}, **self.kw)
        self.assertEqual(r["status"], "A confirmar")

    def test_sqlite_data_do_arquivo_convertido(self):
        con = sqlite3.connect(self.kw["banco"])
        con.execute("CREATE TABLE arquivos (tabela TEXT, convertido_em TEXT)")
        con.execute("INSERT INTO arquivos VALUES ('rd', ?)", ((AGORA - timedelta(days=5)).isoformat(),))
        con.commit(); con.close()
        r = S.avaliar({"id": "sih", "sistema": "SIH", "tipo": "sqlite", "tabelas": ["rd", "sp"], "frescor_dias": 45, "coletor": "c"}, **self.kw)
        self.assertEqual(r["status"], "Ativa")

    def test_gerar_grava_arquivo_e_resumo_com_catalogo_real(self):
        out = tempfile.mkdtemp()
        r = S.gerar(saida=out, sondar=None, sala=self.sala, dados=self.dados, banco=self.kw["banco"])
        self.assertTrue(os.path.isfile(os.path.join(out, "rede_fontes.json")))
        self.assertEqual(sum(r["resumo"].values()), len(r["fontes"]))
        self.assertEqual(r["resumo"]["Ativa"], 0)   # sem coleta nenhuma, nada e Ativa
        self.assertTrue(r["resumo"]["Bloqueada"] >= 3 and r["resumo"]["Descartada"] == 2)
        ids = [x["id"] for x in r["fontes"]]
        self.assertEqual(len(ids), len(set(ids)))


if __name__ == "__main__":
    unittest.main()
