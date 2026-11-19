#!/usr/bin/env python3
"""Tabelas auxiliares oficiais do CNES (FTP do DATASUS, pasta Auxiliar, arquivo TAB_CNES.zip): descricao dos codigos de
servico, leito, habilitacao, equipamento, incentivo e instalacao. Conteudo publico, sem dado pessoal.
Modo atual: --listar (mostra o que ha dentro do zip e o layout de cada tabela, para confirmar nomes reais antes de extrair).
Status: Em teste."""
import sys, zipfile
import hospital_comum as H

PASTA_AUX = H.PASTA_CNES.rsplit("/", 1)[0] + "/Auxiliar"
ARQUIVO = "TAB_CNES.zip"


def main():
    if "--listar" not in sys.argv:
        print("uso: coletar_cnes_tabelas.py --listar"); return 2
    b = H.baixar(PASTA_AUX, ARQUIVO)
    try:
        with zipfile.ZipFile(b.caminho) as z:
            print(f"{ARQUIVO}: {b.tamanho} bytes, {len(z.namelist())} arquivos", flush=True)
            for i in z.infolist():
                print(f"- {i.filename} ({i.file_size} bytes)")
            for i in z.infolist():
                if i.file_size == 0 or i.filename.endswith("/"):
                    continue
                with z.open(i) as f:
                    amostra = f.read(400)
                nome = i.filename.lower()
                if nome.endswith((".csv", ".txt", ".cnv", ".def")):
                    print(f"\n== {i.filename}: {amostra.decode('latin-1', 'replace')[:300]!r}")
                elif nome.endswith(".dbf") and len(amostra) >= 32:
                    n_campos = (int.from_bytes(amostra[8:10], "little") - 33) // 32
                    with z.open(i) as f:
                        cab = f.read(32 + 32 * max(n_campos, 0))
                    campos = [cab[32 + 32 * k:32 + 32 * k + 11].split(b"\0")[0].decode("latin-1") for k in range(n_campos)]
                    print(f"\n== {i.filename}: DBF campos {campos}")
    finally:
        b.__exit__()
    return 0


if __name__ == "__main__":
    sys.exit(main())
