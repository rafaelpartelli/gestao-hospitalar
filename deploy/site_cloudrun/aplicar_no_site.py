#!/usr/bin/env python3
"""Aplica a aba Rede na pasta do site (index.html, Dockerfile, nginx.conf). Uso: python3 aplicar_no_site.py <pasta_do_site> <bucket>
Para se um ancora nao for encontrada. Idempotente."""
import sys, pathlib, re
pasta = pathlib.Path(sys.argv[1]); bucket = sys.argv[2]
def ler(n): return (pasta / n).read_text(encoding='utf-8')
def gravar(n, t): (pasta / n).write_text(t, encoding='utf-8')
def trocar(t, velho, novo, nome):
    if novo in t: return t
    if velho not in t: sys.exit(f'ERRO: ancora nao encontrada em {nome}: {velho[:60]!r}')
    return t.replace(velho, novo, 1)

h = ler('index.html')
h = trocar(h, '<link rel="stylesheet" href="styles.css">', '<link rel="stylesheet" href="styles.css">\n<link rel="stylesheet" href="rede.css">', 'index.html')
h = trocar(h, '    <a href="#/fontes"', '    <a href="#/rede" data-r="rede" class="t-item t-aux"><span class="t-n">R</span><span>Rede hospitalar e rejeições (ES)</span></a>\n    <a href="#/fontes"', 'index.html')
h = trocar(h, '<script src="app.js"></script>', '<script src="app.js"></script>\n<script src="rede.js"></script>', 'index.html')
gravar('index.html', h)

d = ler('Dockerfile')
d = trocar(d, 'COPY index.html styles.css app.js /usr/share/nginx/html/', 'COPY index.html styles.css rede.css app.js rede.js /usr/share/nginx/html/', 'Dockerfile')
gravar('Dockerfile', d)

n = ler('nginx.conf')
bloco = f'''  # dados do super robo: mesma origem, lidos do bucket (somente agregados por CNES)
  location /dados/ {{
    resolver 8.8.8.8 valid=300s ipv6=off;
    set $bucket "storage.googleapis.com";
    rewrite ^/dados/(.*)$ /{bucket}/$1 break;
    proxy_pass https://$bucket;
    proxy_ssl_server_name on;
    proxy_set_header Host storage.googleapis.com;
    proxy_hide_header x-goog-meta-owner;
    add_header Cache-Control "public, max-age=300";
    add_header X-Content-Type-Options "nosniff" always;
  }}

'''
n = trocar(n, '  location / {', bloco + '  location / {', 'nginx.conf')
gravar('nginx.conf', n)
print('aplicado em', pasta)
