#!/usr/bin/env python3
"""Envia os JSON agregados da rede hospitalar (rede_*.json) ao bucket do Google Cloud lido pelo site.
Uso: publicar_gcs.py <pasta_dados> <bucket>
Credencial: arquivo apontado por GOOGLE_APPLICATION_CREDENTIALS (conta de servico restrita ao bucket). Nunca em codigo nem em tela.
Guarda de privacidade: recusa arquivo com sequencia de 11 ou mais digitos (CPF, CNS) ou JSON invalido."""
import json, os, re, sys, pathlib

NOME = re.compile(r'^rede_[A-Za-z0-9_]+\.json$')
CPF_CNS = re.compile(r'\d{11,}')


def selecionar(pasta):
    """Retorna (enviar, recusados): lista de (Path, bytes) e lista de (nome, motivo)."""
    ok, recusados = [], []
    for p in sorted(pathlib.Path(pasta).glob('rede_*.json')):
        if not NOME.match(p.name):
            recusados.append((p.name, 'nome fora do padrao')); continue
        b = p.read_bytes()
        try:
            json.loads(b)
        except ValueError:
            recusados.append((p.name, 'JSON invalido')); continue
        if CPF_CNS.search(b.decode('utf-8', 'replace')):
            recusados.append((p.name, 'sequencia de 11 ou mais digitos')); continue
        ok.append((p, b))
    return ok, recusados


def enviar(pasta, bucket, cliente=None):
    ok, recusados = selecionar(pasta)
    if cliente is None:
        from google.cloud import storage  # importado aqui para os testes nao exigirem a biblioteca
        cliente = storage.Client()
    b = cliente.bucket(bucket)
    for p, dados in ok:
        blob = b.blob(p.name)
        blob.cache_control = 'public, max-age=300'
        blob.upload_from_string(dados, content_type='application/json; charset=utf-8')
    return [p.name for p, _ in ok], recusados


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit('uso: publicar_gcs.py <pasta_dados> <bucket>')
    if not os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
        sys.exit('ERRO: GOOGLE_APPLICATION_CREDENTIALS nao definido (caminho do arquivo da conta de servico)')
    enviados, recusados = enviar(sys.argv[1], sys.argv[2])
    print(f'enviados: {len(enviados)}  recusados: {len(recusados)}')
    for n, m in recusados:
        print(f'RECUSADO {n}: {m}')
    sys.exit(1 if recusados or not enviados else 0)
