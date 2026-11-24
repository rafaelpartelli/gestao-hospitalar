#!/usr/bin/env python3
"""Rotina completa da automacao: baixa os arquivos pendentes (ES) e converte para SQLite. Usada pelo timer e pelo painel."""
import os, sys
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import coleta_ftp, converter_sqlite

if __name__ == "__main__":
    a = coleta_ftp.main([])
    b = converter_sqlite.main([])
    sys.exit(1 if (a or b) else 0)
