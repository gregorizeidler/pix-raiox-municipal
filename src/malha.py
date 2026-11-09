#!/usr/bin/env python3
"""Converte a malha municipal do IBGE num SVG enxuto, colorido pela anomalia.

Simplificacao: Douglas-Peucker em graus (tolerancia configuravel) e arredondamento
das coordenadas do viewBox para inteiro. Sem biblioteca de geo: projecao
equirretangular com correcao de cosseno na latitude media do Brasil.
"""
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
DOCS = os.path.join(ROOT, 'docs')

LARGURA = 1000.0
LAT_MEDIA = -14.0
COS = math.cos(math.radians(LAT_MEDIA))


def simplifica(pontos, tol):
    """Douglas-Peucker sobre [(x, y)] projetados."""
    if len(pontos) < 4:
        return pontos
    pilha = [(0, len(pontos) - 1)]
    manter = [False] * len(pontos)
    manter[0] = manter[-1] = True
    while pilha:
        ini, fim = pilha.pop()
        ax, ay = pontos[ini]
        bx, by = pontos[fim]
        dx, dy = bx - ax, by - ay
        norma = math.hypot(dx, dy)
        melhor, idx = -1.0, -1
        for i in range(ini + 1, fim):
            px, py = pontos[i]
            if norma == 0:
                d = math.hypot(px - ax, py - ay)
            else:
                d = abs(dx * (ay - py) - (ax - px) * dy) / norma
            if d > melhor:
                melhor, idx = d, i
        if melhor > tol and idx > 0:
            manter[idx] = True
            pilha.append((ini, idx))
            pilha.append((idx, fim))
    return [p for p, k in zip(pontos, manter) if k]


def projeta(lon, lat):
    x = (lon + 74.0) * COS
    y = (6.0 - lat)
    return x, y


def anel_para_path(anel, tol, escala_x, escala_y):
    pts = [projeta(lon, lat) for lon, lat in anel]
    pts = simplifica(pts, tol)
    if len(pts) < 4:
        return ''
    d = []
    for i, (x, y) in enumerate(pts):
        px, py = int(round(x * escala_x)), int(round(y * escala_y))
        d.append(('M%d %d' if i == 0 else 'L%d %d') % (px, py))
    return ''.join(d) + 'Z'


def faixa(z):
    if z >= 4.5:
        return 'z4'
    if z >= 3:
        return 'z3'
    if z >= 1.5:
        return 'z2'
    if z > -1.5:
        return 'z0'
    if z > -3:
        return 'zm2'
    return 'zm3'


def main():
    tol = float(sys.argv[1]) if len(sys.argv) > 1 else 0.02
    malha = json.load(open(os.path.join(DATA, 'malha_br.json')))
    modelo = json.load(open(os.path.join(DATA, 'modelo.json')))
    por_codigo = {m['i']: m for m in modelo['municipios']}

    xs, ys = [], []
    for f in malha['features']:
        geom = f['geometry']
        aneis = geom['coordinates'] if geom['type'] == 'Polygon' else [a for p in geom['coordinates'] for a in p]
        for anel in aneis:
            for lon, lat in anel:
                x, y = projeta(lon, lat)
                xs.append(x)
                ys.append(y)
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    escala = LARGURA / (x1 - x0)
    altura = (y1 - y0) * escala

    partes = []
    fora = 0
    for f in malha['features']:
        cod = int(f['properties']['codarea'])
        geom = f['geometry']
        aneis = geom['coordinates'] if geom['type'] == 'Polygon' else [a for p in geom['coordinates'] for a in p]
        d = ''.join(anel_para_path(a, tol, escala, escala) for a in aneis)
        if not d:
            fora += 1
            continue
        m = por_codigo.get(cod)
        classe = faixa(m['z']) if m else 'z0'
        rotulo = ('%s / %s — Pix R$ %.0f/hab, esperado R$ %.0f (z %.1f)'
                  % (m['n'], m['u'], m['recebepc'], m['exppc'], m['z'])) if m else str(cod)
        partes.append('<path d="%s" class="%s" data-c="%d"><title>%s</title></path>'
                      % (d, classe, cod, rotulo.replace('&', 'e')))

    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" '
           'role="img" aria-label="Mapa dos municipios brasileiros por anomalia de Pix">%s</svg>'
           % (int(LARGURA), int(altura), ''.join(partes)))
    os.makedirs(DOCS, exist_ok=True)
    destino = os.path.join(DOCS, 'dados', 'mapa.svg')
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    with open(destino, 'w', encoding='utf-8') as fh:
        fh.write(svg)
    print('mapa: %d municipios, %d sem area visivel, %.1f KB (tol %.3f, viewBox %dx%d)'
          % (len(partes), fora, len(svg) / 1024.0, tol, int(LARGURA), int(altura)))


if __name__ == '__main__':
    main()
