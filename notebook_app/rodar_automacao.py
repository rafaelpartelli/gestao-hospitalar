#!/usr/bin/env python3
"""Rotina completa da automacao: baixa os arquivos pendentes (ES) converte para SQLite e confere a reapresentacao das AIH rejeitadas. Usada pelo timer e pelo painel."""
import os, sys
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import coleta_ftp, converter_sqlite, reconciliar_rejeicoes

if __name__ == "__main__":
    a = coleta_ftp.main([])
    b = converter_sqlite.main([])
    c = reconciliar_rejeicoes.main([])
    sys.exit(1 if (a or b or c) else 0)
