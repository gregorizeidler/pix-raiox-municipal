#!/usr/bin/env python3
"""Agregados nacionais e por UF que alimentam o site e o relatorio."""
import csv
import gzip
import json
import os
import statistics

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')

UF_SIGLA = {11: 'RO', 12: 'AC', 13: 'AM', 14: 'RR', 15: 'PA', 16: 'AP', 17: 'TO',
            21: 'MA', 22: 'PI', 23: 'CE', 24: 'RN', 25: 'PB', 26: 'PE', 27: 'AL',
            28: 'SE', 29: 'BA', 31: 'MG', 32: 'ES', 33: 'RJ', 35: 'SP', 41: 'PR',
            42: 'SC', 43: 'RS', 50: 'MS', 51: 'MT', 52: 'GO', 53: 'DF'}
UF_NOME = {'RO': 'Rondônia', 'AC': 'Acre', 'AM': 'Amazonas', 'RR': 'Roraima', 'PA': 'Pará',
           'AP': 'Amapá', 'TO': 'Tocantins', 'MA': 'Maranhão', 'PI': 'Piauí', 'CE': 'Ceará',
           'RN': 'Rio Grande do Norte', 'PB': 'Paraíba', 'PE': 'Pernambuco', 'AL': 'Alagoas',
           'SE': 'Sergipe', 'BA': 'Bahia', 'MG': 'Minas Gerais', 'ES': 'Espírito Santo',
           'RJ': 'Rio de Janeiro', 'SP': 'São Paulo', 'PR': 'Paraná', 'SC': 'Santa Catarina',
           'RS': 'Rio Grande do Sul', 'MS': 'Mato Grosso do Sul', 'MT': 'Mato Grosso',
           'GO': 'Goiás', 'DF': 'Distrito Federal'}


def main():
    modelo = json.load(open(os.path.join(DATA, 'modelo.json')))
    meses = modelo['meta']['meses']
    municipios = modelo['municipios']
    municipio_de = {m['i']: m for m in municipios}

    with gzip.open(os.path.join(DATA, 'pix_municipios.csv.gz'), 'rt', encoding='utf-8') as fh:
        linhas = list(csv.DictReader(fh))
    for l in linhas:
        l['anomes'] = int(l['anomes'])
        l['municipio_ibge'] = int(l['municipio_ibge'])
        for c in ('vl_rec_pf', 'vl_rec_pj', 'qt_rec_pf', 'qt_rec_pj', 'pes_rec_pf', 'vl_pag_pf'):
            l[c] = float(l[c] or 0)

    # serie nacional mensal (todos os meses completos)
    por_mes = {}
    for l in linhas:
        d = por_mes.setdefault(l['anomes'], {'pf': 0.0, 'pj': 0.0, 'qt': 0.0})
        d['pf'] += l['vl_rec_pf']
        d['pj'] += l['vl_rec_pj']
        d['qt'] += l['qt_rec_pf']
    completo = sorted(por_mes)
    mediana = statistics.median([por_mes[m]['pf'] for m in completo[-15:]])
    serie_nacional = [{'mes': m, 'pf': round(por_mes[m]['pf']), 'pj': round(por_mes[m]['pj']),
                       'qt': round(por_mes[m]['qt'])}
                      for m in completo if por_mes[m]['pf'] >= 0.6 * mediana]

    # concentracao no ultimo mes do modelo
    ultimo = modelo['meta']['ultimo_mes']
    valores = sorted([l['vl_rec_pf'] + l['vl_rec_pj'] for l in linhas if l['anomes'] == ultimo], reverse=True)
    total = sum(valores)
    corte = max(1, len(valores) // 100)
    top1 = sum(valores[:corte])

    # agregado por UF no ultimo mes
    uf = {}
    for l in linhas:
        if l['anomes'] != ultimo:
            continue
        d = uf.setdefault(l['uf'], {'pf': 0.0, 'pj': 0.0, 'n': 0, 'pop': 0})  # l['uf'] traz o codigo IBGE da UF
        d['pf'] += l['vl_rec_pf']
        d['pj'] += l['vl_rec_pj']
        d['n'] += 1
        m = municipio_de.get(l['municipio_ibge'])
        if m:
            d['pop'] += m['p']
    ufs = [{'uf': UF_SIGLA.get(int(k), str(k)), 'nome': UF_NOME.get(UF_SIGLA.get(int(k)), ''),
            'pf': round(v['pf']), 'pj': round(v['pj']), 'n': v['n'],
            'pop': v['pop'], 'pf_pc': round(v['pf'] / v['pop'], 2) if v['pop'] else None}
           for k, v in uf.items()]
    ufs.sort(key=lambda d: -d['pf_pc'])

    # distribuicao dos z
    zs = [m['z'] for m in municipios]
    faixas = [(-100, -3), (-3, -1.5), (-1.5, 1.5), (1.5, 3), (3, 4.5), (4.5, 100)]
    dist = []
    for a, b in faixas:
        dist.append({'de': a, 'ate': b, 'n': sum(1 for z in zs if a <= z < b)})

    acima = [m for m in municipios if m['z'] >= 3]
    abaixo = [m for m in municipios if m['z'] <= -3]
    exc_total = sum(m['exc'] for m in acima)
    pj_topo = sorted(municipios, key=lambda m: -m['zj'])[:15]

    saida = {
        'serie_nacional': serie_nacional,
        'concentracao': {'total_ultimo_mes': round(total), 'top1_pct': round(100 * top1 / total, 2),
                         'n_municipios': len(valores)},
        'ufs': ufs,
        'distribuicao_z': dist,
        'resumo': {
            'n_municipios': len(municipios),
            'acima_3': len(acima),
            'abaixo_3': len(abaixo),
            'excesso_total_12m': round(exc_total),
            'mediana_pf_pc': round(statistics.median([m['recebepc'] for m in municipios]), 2),
            'mediana_excesso_pct': round(statistics.median([m['dev'] for m in municipios]), 1),
        },
        'top_pj': [{'n': m['n'], 'u': m['u'], 'pjpc': m['pjpc'], 'z': m['zj']} for m in pj_topo],
    }
    with open(os.path.join(DATA, 'nacional.json'), 'w', encoding='utf-8') as fh:
        json.dump(saida, fh, ensure_ascii=False)

    print('serie nacional: %d meses completos (%s a %s)' % (len(serie_nacional), serie_nacional[0]['mes'], serie_nacional[-1]['mes']))
    print('ultimo mes %s: R$ %.2f tri recebido (PF+PJ); top 1%% dos municipios = %.1f%% do valor'
          % (ultimo, total / 1e12, 100 * top1 / total))
    print('flags: %d acima, %d abaixo de z=3; excesso somado R$ %.2f bi'
          % (len(acima), len(abaixo), exc_total / 1e9))
    print('mediana Pix recebido PF por habitante: R$ %.2f' % saida['resumo']['mediana_pf_pc'])
    print('--- UFs por Pix PF por habitante (top 5) ---')
    for u in ufs[:5]:
        print('  %s R$ %.0f/hab (%d municipios)' % (u['uf'], u['pf_pc'], u['n']))
    print('--- PJ por habitante (top 10) ---')
    for m in pj_topo[:10]:
        print('  %-28s %s R$ %10.0f/hab z=%6.2f' % (m['n'][:28], m['u'], m['pjpc'], m['zj']))


if __name__ == '__main__':
    main()
