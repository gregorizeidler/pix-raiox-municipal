#!/usr/bin/env python3
"""Modelo de volume esperado de Pix por municipio e deteccao de anomalias.

Ideia: o volume de Pix que um municipio movimenta nao depende so do tamanho da
populacao, mas tambem da renda. Ajustamos, em log:

    log(Pix por habitante) = a + b*log(populacao) + c*log(PIB por habitante)
                              + efeito fixo de UF + efeito fixo de mes

e olhamos o residuo. Residuo positivo grande = o municipio movimenta mais Pix do
que o tamanho e a renda explicam. O ajuste e robusto (IRLS com peso de Huber)
para que os proprios outliers nao puxem a reta.

Sem dependencias externas: a algebra linear e resolvida aqui mesmo.
"""
import csv
import gzip
import json
import math
import os
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
OUT = os.path.join(ROOT, 'out')

# Janela do modelo: ultimos meses completos. O mes corrente entra parcial na API.
MESES_MODELO = 12

UF_SIGLA = {11: 'RO', 12: 'AC', 13: 'AM', 14: 'RR', 15: 'PA', 16: 'AP', 17: 'TO',
            21: 'MA', 22: 'PI', 23: 'CE', 24: 'RN', 25: 'PB', 26: 'PE', 27: 'AL',
            28: 'SE', 29: 'BA', 31: 'MG', 32: 'ES', 33: 'RJ', 35: 'SP', 41: 'PR',
            42: 'SC', 43: 'RS', 50: 'MS', 51: 'MT', 52: 'GO', 53: 'DF'}


def carrega_painel():
    caminho = os.path.join(DATA, 'pix_municipios.csv.gz')
    with gzip.open(caminho, 'rt', encoding='utf-8') as fh:
        linhas = list(csv.DictReader(fh))
    for l in linhas:
        l['anomes'] = int(l['anomes'])
        l['municipio_ibge'] = int(l['municipio_ibge'])
        for c in ('vl_pag_pf', 'qt_pag_pf', 'vl_pag_pj', 'qt_pag_pj',
                  'vl_rec_pf', 'qt_rec_pf', 'vl_rec_pj', 'qt_rec_pj',
                  'pes_pag_pf', 'pes_pag_pj', 'pes_rec_pf', 'pes_rec_pj'):
            l[c] = float(l[c] or 0)
    return linhas


def meses_completos(linhas):
    """Meses em que a base veio inteira: o total do mes nao pode ser menos da metade
    da mediana dos ultimos meses (mes corrente entra parcial)."""
    por_mes = {}
    for l in linhas:
        por_mes.setdefault(l['anomes'], 0.0)
        por_mes[l['anomes']] += l['vl_rec_pf']
    ordenado = sorted(por_mes)
    ultimos = [por_mes[m] for m in ordenado[-15:]]
    mediana = statistics.median(ultimos)
    completos = [m for m in ordenado if por_mes[m] >= 0.6 * mediana]
    return completos


def resolve(matriz, vetor):
    """Resolve Ax=b por eliminacao de Gauss com pivoteamento parcial."""
    n = len(matriz)
    a = [linha[:] + [vetor[i]] for i, linha in enumerate(matriz)]
    for col in range(n):
        pivo = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[pivo][col]) < 1e-12:
            a[pivo][col] += 1e-9  # regularizacao minima
        a[col], a[pivo] = a[pivo], a[col]
        inv = 1.0 / a[col][col]
        for r in range(col + 1, n):
            fator = a[r][col] * inv
            if fator:
                for c in range(col, n + 1):
                    a[r][c] -= fator * a[col][c]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        s = a[i][n] - sum(a[i][j] * x[j] for j in range(i + 1, n))
        x[i] = s / a[i][i]
    return x


def ols_pesado(X, y, pesos):
    """Minimos quadrados com pesos. X ja inclui a coluna constante."""
    p = len(X[0])
    XtX = [[0.0] * p for _ in range(p)]
    Xty = [0.0] * p
    for linha, alvo, w in zip(X, y, pesos):
        for i in range(p):
            wi = w * linha[i]
            Xty[i] += wi * alvo
            for j in range(i, p):
                XtX[i][j] += wi * linha[j]
    for i in range(p):
        for j in range(i):
            XtX[i][j] = XtX[j][i]
    return resolve(XtX, Xty)


def ajusta_robusto(X, y, iteracoes=6):
    """IRLS com peso de Huber: uma observacao extrema deixa de puxar a reta."""
    pesos = [1.0] * len(y)
    coef = ols_pesado(X, y, pesos)
    for _ in range(iteracoes):
        resid = [yi - sum(c * xi for c, xi in zip(coef, linha)) for linha, yi in zip(X, y)]
        escala = 1.4826 * statistics.median([abs(r) for r in resid]) or 1e-6
        corte = 1.345 * escala
        pesos = [1.0 if abs(r) <= corte else corte / abs(r) for r in resid]
        coef = ols_pesado(X, y, pesos)
    resid = [yi - sum(c * xi for c, xi in zip(coef, linha)) for linha, yi in zip(X, y)]
    escala = 1.4826 * statistics.median([abs(r) for r in resid]) or 1e-6
    return coef, resid, escala


def monta_design(painel, meses, indicador, pop, pib_pc):
    """Matriz de desenho com log(pop), log(PIB pc), dummies de UF e de mes."""
    ufs = sorted({l['uf'] for l in painel if l['anomes'] in meses})
    idx_uf = {u: i for i, u in enumerate(ufs[1:])}
    idx_mes = {m: i for i, m in enumerate(meses[1:])}
    X, y, refs = [], [], []
    for l in painel:
        if l['anomes'] not in idx_mes and l['anomes'] != meses[0]:
            continue
        cod = l['municipio_ibge']
        p = pop.get(cod)
        pc = pib_pc.get(cod)
        valor = l[indicador]
        if not p or not pc or valor <= 0:
            continue
        por_habitante = valor / p
        linha = [1.0, math.log(p), math.log(pc)]
        linha += [1.0 if idx_uf.get(l['uf']) == i else 0.0 for i in range(len(ufs) - 1)]
        mes_idx = idx_mes.get(l['anomes'])
        linha += [1.0 if mes_idx == i else 0.0 for i in range(len(meses) - 1)]
        X.append(linha)
        y.append(math.log(por_habitante))
        refs.append((cod, l['anomes'], por_habitante))
    return X, y, refs, ufs


def main():
    painel = carrega_painel()
    completos = meses_completos(painel)
    meses = completos[-MESES_MODELO:]
    print('meses usados no modelo: %s a %s (%d)' % (meses[0], meses[-1], len(meses)))

    caminho_fronteira = os.path.join(DATA, 'fronteira.json')
    fronteira = set(json.load(open(caminho_fronteira))['codigos']) if os.path.exists(caminho_fronteira) else set()

    pop = {int(k): v for k, v in json.load(open(os.path.join(DATA, 'populacao.json')))['valores'].items()}
    pib = {int(k): v for k, v in json.load(open(os.path.join(DATA, 'pib.json')))['valores'].items()}
    pib_pc = {k: (v * 1000.0 / pop[k]) for k, v in pib.items() if pop.get(k)}

    nomes, uf_de, reg_de = {}, {}, {}
    for l in painel:
        nomes[l['municipio_ibge']] = l['municipio'].title()
        uf_de[l['municipio_ibge']] = UF_SIGLA.get(l['uf'], str(l['uf']))
        reg_de[l['municipio_ibge']] = l['regiao']

    resultados = {}
    for chave, indicador in (('pf', 'vl_rec_pf'), ('pj', 'vl_rec_pj')):
        X, y, refs, ufs = monta_design(painel, meses, indicador, pop, pib_pc)
        coef, resid, escala = ajusta_robusto(X, y)
        print('%s: %d observacoes, %d parametros, escala do residuo %.3f'
              % (chave, len(y), len(coef), escala))
        por_municipio = {}
        for (cod, anomes, observado), r in zip(refs, resid):
            d = por_municipio.setdefault(cod, {'obs': [], 'res': [], 'pc': {'pf': [], 'pj': []}})
            d['obs'].append(observado)
            d['res'].append(r)
            d['pc'][chave].append(observado)
        for cod, d in por_municipio.items():
            mediana_res = statistics.median(d['res'])
            resultados.setdefault(cod, {})[chave] = {
                'res_mediana': mediana_res,
                'z': mediana_res / escala,
                'por_hab_medio': statistics.mean(d['pc'][chave]),
            }
        resultados_escala = resultados.get('_escala', {})
        resultados_escala[chave] = escala
        resultados['_escala'] = resultados_escala

    # serie mensal e agregados do ultimo mes de cada municipio
    ultimo = meses[-1]
    serie = {}
    ultimo_mes = {}
    for l in painel:
        if l['anomes'] not in meses:
            continue
        cod = l['municipio_ibge']
        serie.setdefault(cod, {})[l['anomes']] = {
            'pf': l['vl_rec_pf'], 'pj': l['vl_rec_pj'],
            'qtPf': l['qt_rec_pf'], 'pesPf': l['pes_rec_pf'],
            'pagPf': l['vl_pag_pf'],
        }
        if l['anomes'] == ultimo:
            ultimo_mes[cod] = l

    municipios = []
    for cod, r in resultados.items():
        if cod == '_escala':
            continue
        if cod not in pop or cod not in pib_pc:
            continue
        p = pop[cod]
        m = ultimo_mes.get(cod)
        if not m:
            continue
        z_pf = r['pf']['z']
        z_pj = r['pj']['z']
        dev = math.expm1(r['pf']['res_mediana'])
        esperado_mes = r['pf']['por_hab_medio'] / math.exp(r['pf']['res_mediana'])
        excesso = 0.0
        for anomes, v in serie.get(cod, {}).items():
            excesso += v['pf'] - esperado_mes * p
        ticket = (m['vl_rec_pf'] / m['qt_rec_pf']) if m['qt_rec_pf'] else 0.0
        serie_pf = [round(serie[cod][mm]['pf'] / p, 2) if mm in serie.get(cod, {}) else None for mm in meses]
        municipios.append({
            'i': cod, 'n': nomes[cod], 'u': uf_de[cod], 'r': reg_de[cod], 'p': round(p),
            'pibpc': round(pib_pc[cod]),
            'recebepc': round(r['pf']['por_hab_medio'], 2),
            'exppc': round(esperado_mes, 2),
            'z': round(z_pf, 2), 'dev': round(dev * 100, 1),
            'exc': round(excesso),
            'zj': round(z_pj, 2),
            'pjpc': round(r['pj']['por_hab_medio'], 2),
            'tk': round(ticket, 2),
            'pes': round(m['pes_rec_pf']),
            'fr': 1 if cod in fronteira else 0,
            'serie': serie_pf,
        })
    municipios.sort(key=lambda d: -d['z'])

    total_valor = sum(v['pf'] for cod, v in serie.items() for mm, v in v.items() if mm == ultimo) if False else None
    meta = {
        'meses': meses,
        'ultimo_mes': ultimo,
        'n_municipios': len(municipios),
        'fontes': {
            'pix': 'BCB, API Dados Abertos Pix - TransacoesPixPorMunicipio',
            'populacao': 'IBGE/SIDRA tabela 6579 variavel 9324',
            'pib': 'IBGE/SIDRA tabela 5938 variavel 37 (PIB a precos correntes, 2023)',
        },
        'metodo': ('log(Pix recebido por habitante) ~ log(populacao) + log(PIB por habitante) '
                   '+ efeito fixo de UF + efeito fixo de mes, ajuste robusto IRLS/Huber; '
                   'z = residuo mediano / (1,4826 * MAD)'),
        'escala': {k: round(v, 4) for k, v in resultados['_escala'].items()},
    }
    with open(os.path.join(DATA, 'modelo.json'), 'w', encoding='utf-8') as fh:
        json.dump({'meta': meta, 'municipios': municipios}, fh, ensure_ascii=False)

    # tabela de outliers para inspecao e para o relatorio
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, 'outliers.csv'), 'w', encoding='utf-8', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['posicao', 'ibge', 'municipio', 'uf', 'populacao', 'pib_pc',
                    'recebe_pf_pc', 'esperado_pf_pc', 'desvio_pct', 'z', 'excesso_12m',
                    'ticket_pf', 'pj_pc', 'z_pj'])
        for i, d in enumerate(municipios[:60], 1):
            w.writerow([i, d['i'], d['n'], d['u'], d['p'], d['pibpc'], d['recebepc'],
                        d['exppc'], d['dev'], d['z'], d['exc'], d['tk'], d['pjpc'], d['zj']])

    acima = [d for d in municipios if d['z'] >= 3]
    abaixo = [d for d in municipios if d['z'] <= -3]
    print('municipios acima de z=3: %d | abaixo de z=-3: %d' % (len(acima), len(abaixo)))
    for d in municipios[:12]:
        print('  %-28s %s pop %8d  R$ %9.2f/hab (esperado %7.2f, %+6.1f%%)  z=%6.2f'
              % (d['n'][:28], d['u'], d['p'], d['recebepc'], d['exppc'], d['dev'], d['z']))


if __name__ == '__main__':
    main()
