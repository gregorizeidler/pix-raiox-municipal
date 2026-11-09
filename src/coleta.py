#!/usr/bin/env python3
"""Coleta dos dados abertos: Pix por municipio (BCB), populacao e PIB (IBGE), malha municipal.

Fonte Pix: API OData do BCB, servico Pix_DadosAbertos.
  O conjunto TransacoesPixPorMunicipio exige o parametro DataBase (AAAAMM) e e
  consultado no formato de funcao: /TransacoesPixPorMunicipio(DataBase='202601')?$filter=AnoMes eq 202601
Fonte populacao: IBGE/SIDRA, tabela 6579, variavel 9324 (estimativa mais recente).
Fonte PIB: IBGE/SIDRA, tabela 5938, variavel 37 (PIB a precos correntes, mil reais).
Fonte malha: IBGE, API de malhas, GeoJSON qualidade minima, municipios do Brasil.
"""
import concurrent.futures as cf
import csv
import gzip
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')

PIX = ('https://olinda.bcb.gov.br/olinda/servico/Pix_DadosAbertos/versao/v1/odata/'
       'TransacoesPixPorMunicipio')
SIDRA = 'https://apisidra.ibge.gov.br/values'
MALHA = ('https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR'
         '?formato=application/vnd.geo+json&qualidade=minima&intrarregiao=municipio')

CAMPOS = ['anomes', 'municipio_ibge', 'municipio', 'uf', 'uf_sigla', 'regiao',
          'vl_pag_pf', 'qt_pag_pf', 'vl_pag_pj', 'qt_pag_pj',
          'vl_rec_pf', 'qt_rec_pf', 'vl_rec_pj', 'qt_rec_pj',
          'pes_pag_pf', 'pes_pag_pj', 'pes_rec_pf', 'pes_rec_pj']


def http_get(url, timeout=180, tentativas=4):
    """GET com retentativa e backoff. Devolve bytes."""
    espera = 2
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'pix-raiox-municipal/1.0'})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            if i == tentativas - 1:
                raise RuntimeError('falhou %s: %s' % (url, e))
            time.sleep(espera)
            espera *= 2


def limpa_json(bruto):
    """A API do BCB as vezes embrulha o JSON num comentario /* ... */."""
    texto = bruto.decode('utf-8').strip()
    if texto.startswith('/*'):
        texto = texto[2:]
    if texto.endswith('*/'):
        texto = texto[:-2]
    return json.loads(texto)


def num(valor):
    """Converte null da API em 0."""
    return 0 if valor is None else valor


def meses(inicio='202011'):
    """Todos os AAAAMM de inicio ate o mes corrente, do mais antigo ao mais novo."""
    hoje = time.localtime()
    a, m = int(inicio[:4]), int(inicio[4:])
    while (a, m) <= (hoje.tm_year, hoje.tm_mon):
        yield '%04d%02d' % (a, m)
        m += 1
        if m == 13:
            a, m = a + 1, 1


def busca_mes(anomes):
    """Uma requisicao por mes. Devolve lista de registros crus."""
    url = ('%s(DataBase=%%27%s%%27)?$filter=%s&$format=json'
           % (PIX, anomes, urllib.parse.quote('AnoMes eq %s' % anomes)))
    bruto = http_get(url)
    return limpa_json(bruto).get('value', [])


def coleta_pix():
    os.makedirs(DATA, exist_ok=True)
    destino = os.path.join(DATA, 'pix_municipios.csv.gz')
    todos = []
    ignorados = 0
    with cf.ThreadPoolExecutor(max_workers=4) as pool:
        futuros = {pool.submit(busca_mes, m): m for m in meses()}
        for fut in cf.as_completed(futuros):
            m = futuros[fut]
            try:
                registros = fut.result()
            except Exception as e:  # mes sem dado ou falha: registra e segue
                print('aviso: mes %s falhou (%s)' % (m, e), flush=True)
                continue
            print('mes %s: %d registros' % (m, len(registros)), flush=True)
            for r in registros:
                if r['Municipio_Ibge'] is None:  # linhas sem municipio identificado
                    ignorados += 1
                    continue
                todos.append([
                    r['AnoMes'], r['Municipio_Ibge'], r['Municipio'],
                    r['Estado_Ibge'], r['Sigla_Regiao'], r['Regiao'],
                    num(r['VL_PagadorPF']), num(r['QT_PagadorPF']),
                    num(r['VL_PagadorPJ']), num(r['QT_PagadorPJ']),
                    num(r['VL_RecebedorPF']), num(r['QT_RecebedorPF']),
                    num(r['VL_RecebedorPJ']), num(r['QT_RecebedorPJ']),
                    num(r['QT_PES_PagadorPF']), num(r['QT_PES_PagadorPJ']),
                    num(r['QT_PES_RecebedorPF']), num(r['QT_PES_RecebedorPJ']),
                ])
    todos.sort(key=lambda x: (x[0], x[1]))
    with gzip.open(destino, 'wt', encoding='utf-8', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(CAMPOS)
        w.writerows(todos)
    print('gravado %s com %d linhas (%d linhas sem municipio ignoradas)'
          % (destino, len(todos), ignorados), flush=True)
    return len(todos)


def coleta_sidra(tabela, variavel):
    """Le uma tabela do SIDRA para todos os municipios e devolve {codigo: valor}."""
    url = '%s/t/%s/n6/all/v/%s/p/last' % (SIDRA, tabela, variavel)
    linhas = json.loads(http_get(url))
    saida = {}
    for linha in linhas[1:]:  # primeira posicao e o cabecalho
        valor = linha['V']
        if valor in ('-', '...', '..', 'X', ''):
            continue
        try:
            saida[int(linha['D1C'])] = float(valor.replace(',', '.'))
        except ValueError:
            continue
    return saida


def coleta_ibge():
    pop = coleta_sidra(6579, 9324)
    pib = coleta_sidra(5938, 37)
    with open(os.path.join(DATA, 'populacao.json'), 'w', encoding='utf-8') as fh:
        json.dump({'fonte': 'IBGE/SIDRA tabela 6579 variavel 9324 (populacao residente estimada)',
                   'valores': {str(k): v for k, v in pop.items()}}, fh)
    with open(os.path.join(DATA, 'pib.json'), 'w', encoding='utf-8') as fh:
        json.dump({'fonte': 'IBGE/SIDRA tabela 5938 variavel 37 (PIB a precos correntes, mil reais)',
                   'valores': {str(k): v for k, v in pib.items()}}, fh)
    print('populacao: %d municipios | PIB: %d municipios' % (len(pop), len(pib)), flush=True)


def coleta_malha():
    bruto = http_get(MALHA, timeout=300)
    if bruto[:2] == b'\x1f\x8b':  # o servidor devolve gzip mesmo sem Accept-Encoding
        bruto = gzip.decompress(bruto)
    destino = os.path.join(DATA, 'malha_br.json')
    with open(destino, 'wb') as fh:
        fh.write(bruto)
    print('malha: %d bytes' % len(bruto), flush=True)


if __name__ == '__main__':
    os.makedirs(DATA, exist_ok=True)
    etapas = {'pix': coleta_pix, 'ibge': coleta_ibge, 'malha': coleta_malha}
    alvo = sys.argv[1:] or ['pix', 'ibge', 'malha']
    for nome in alvo:
        print('== %s ==' % nome, flush=True)
        etapas[nome]()
