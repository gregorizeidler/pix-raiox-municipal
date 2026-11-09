#!/usr/bin/env python3
"""Gera o site estatico (GitHub Pages) a partir de data/modelo.json e data/nacional.json."""
import json
import os
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
DOCS = os.path.join(ROOT, 'docs')


def brl(v, casas=0):
    """Formata em reais no padrao brasileiro."""
    if v is None:
        return '—'
    s = ('{:,.%df}' % casas).format(v).replace(',', 'X').replace('.', ',').replace('X', '.')
    return 'R$ ' + s


def num(v, casas=0):
    if v is None:
        return '—'
    return ('{:,.%df}' % casas).format(v).replace(',', 'X').replace('.', ',').replace('X', '.')


def pct(v, casas=1):
    if v is None:
        return '—'
    return num(v, casas) + '%'


def sinal(v, casas=0):
    if v is None:
        return '—'
    return ('+' if v > 0 else '') + num(v, casas)


def linhas_tabela(itens, tipo='alta'):
    out = []
    for i, m in enumerate(itens, 1):
        tag = ('<span class="tag">%s</span>' % ('z %+.1f' % m['z'])) if tipo == 'alta' else (
            '<span class="tag baixo">z %+.1f</span>' % m['z'])
        out.append(
            '<tr><td class="num">%d</td><td><a href="municipio.html?id=%d">%s</a></td>'
            '<td>%s</td><td class="num">%s</td><td class="num">%s</td><td class="num">%s</td>'
            '<td class="num">%s</td><td class="num">%s</td></tr>'
            % (i, m['i'], m['n'], m['u'], num(m['p']), brl(m['recebepc']), brl(m['exppc']),
               pct(m['dev']), tag))
    return ''.join(out)


def linhas_uf(ufs):
    out = []
    for u in ufs:
        out.append('<tr><td>%s <span style="color:#71797f">%s</span></td><td class="num">%s</td>'
                   '<td class="num">%s</td><td class="num">%s</td><td class="num">%s</td></tr>'
                   % (u['uf'], u['nome'], num(u['n']), num(u['pop']), brl(u['pf'] / 1e9, 1) + ' bi',
                      brl(u['pf_pc'])))
    return ''.join(out)


def linhas_pj(itens):
    out = []
    for m in itens:
        out.append('<tr><td><a href="municipio.html?id=%d">%s</a></td><td>%s</td>'
                   '<td class="num">%s</td><td class="num">%s</td><td class="num">%s</td></tr>'
                   % (m['i'], m['n'], m['u'], num(m['p']), brl(m['pjpc']), brl(m['recebepc'])))
    return ''.join(out)


def linhas_ticket(itens):
    out = []
    for m in itens:
        out.append('<tr><td><a href="municipio.html?id=%d">%s</a></td><td>%s</td>'
                   '<td class="num">%s</td><td class="num">%s</td></tr>'
                   % (m['i'], m['n'], m['u'], num(m['p']), brl(m['tk'], 2)))
    return ''.join(out)


def main():
    modelo = json.load(open(os.path.join(DATA, 'modelo.json')))
    nac = json.load(open(os.path.join(DATA, 'nacional.json')))
    ms = modelo['municipios']
    meta = modelo['meta']
    resumo = nac['resumo']

    acima = [m for m in ms if m['z'] >= 3]
    abaixo = sorted([m for m in ms if m['z'] <= -3], key=lambda m: m['z'])
    pj_top = sorted(ms, key=lambda m: -m['zj'])[:12]
    ticket_top = sorted([m for m in ms if m['p'] > 50000], key=lambda m: -m['tk'])[:10]
    por_codigo = {m['i']: m for m in ms}

    destaque = ms[0]
    uf_mt = next((u for u in nac['ufs'] if u['uf'] == 'MT'), None)
    uf_sp = next((u for u in nac['ufs'] if u['uf'] == 'SP'), None)
    sede = pj_top[0]

    os.makedirs(os.path.join(DOCS, 'dados'), exist_ok=True)

    # ---- dados para o navegador ----
    enxuto = [{'i': m['i'], 'n': m['n'], 'u': m['u'], 'p': m['p'], 'pibpc': m['pibpc'],
               'recebepc': m['recebepc'], 'exppc': m['exppc'], 'z': m['z'], 'dev': m['dev'],
               'exc': m['exc'], 'zj': m['zj'], 'pjpc': m['pjpc'], 'tk': m['tk'],
               'serie': m['serie']} for m in ms]
    with open(os.path.join(DOCS, 'dados', 'municipios.json'), 'w', encoding='utf-8') as fh:
        json.dump(enxuto, fh, ensure_ascii=False, separators=(',', ':'))
    with open(os.path.join(DOCS, 'dados', 'resumo.json'), 'w', encoding='utf-8') as fh:
        json.dump({'meta': meta, 'resumo': resumo, 'concentracao': nac['concentracao'],
                   'serie_nacional': nac['serie_nacional'], 'ufs': nac['ufs'],
                   'distribuicao_z': nac['distribuicao_z']}, fh, ensure_ascii=False, separators=(',', ':'))

    # CSV para download (planilha de bolso)
    with open(os.path.join(DOCS, 'dados', 'municipios.csv'), 'w', encoding='utf-8') as fh:
        fh.write('ibge;municipio;uf;populacao;pib_por_hab;pix_recebido_pf_pc;esperado_pc;'
                 'desvio_pct;z;excesso_12m;ticket_pf;pj_pc;z_pj\n')
        for m in ms:
            fh.write('%d;%s;%s;%d;%d;%.2f;%.2f;%.1f;%.2f;%d;%.2f;%.2f;%.2f\n'
                     % (m['i'], m['n'], m['u'], m['p'], m['pibpc'], m['recebepc'], m['exppc'],
                        m['dev'], m['z'], m['exc'], m['tk'], m['pjpc'], m['zj']))
    open(os.path.join(DOCS, '.nojekyll'), 'w').close()

    # ---- index ----
    html = open(os.path.join(ROOT, 'src', 'index.tpl.html'), encoding='utf-8').read()
    trocas = {
        '{{MES}}': '%d/%d' % (meta['ultimo_mes'] % 100, meta['ultimo_mes'] // 100),
        '{{VOLUME}}': brl(nac['concentracao']['total_ultimo_mes'] / 1e12, 2) + ' tri',
        '{{TOP1}}': pct(nac['concentracao']['top1_pct'], 1),
        '{{TOP1N}}': num(round(nac['concentracao']['n_municipios'] * 0.01)),
        '{{N_MUN}}': num(meta['n_municipios']),
        '{{ACIMA}}': num(resumo['acima_3']),
        '{{ABAIXO}}': num(resumo['abaixo_3']),
        '{{EXCESSO}}': brl(resumo['excesso_total_12m'] / 1e9, 1) + ' bi',
        '{{MEDIANA}}': brl(resumo['mediana_pf_pc']),
        '{{DESTAQUE}}': destaque['n'], '{{DESTAQUE_UF}}': destaque['u'],
        '{{DESTAQUE_POP}}': num(destaque['p']),
        '{{DESTAQUE_PC}}': brl(destaque['recebepc']),
        '{{DESTAQUE_EXP}}': brl(destaque['exppc']),
        '{{DESTAQUE_VEZES}}': num(destaque['recebepc'] / destaque['exppc'], 1) + 'x',
        '{{DESTAQUE_ID}}': str(destaque['i']),
        '{{MT_PC}}': brl(uf_mt['pf_pc']) if uf_mt else '—',
        '{{SP_PC}}': brl(uf_sp['pf_pc']) if uf_sp else '—',
        '{{SEDE}}': sede['n'], '{{SEDE_UF}}': sede['u'], '{{SEDE_ID}}': str(sede['i']),
        '{{SEDE_PJ}}': brl(sede['pjpc']),
        '{{SEDE_POP}}': num(sede['p']),
        '{{LINHAS_ACIMA}}': linhas_tabela(acima[:25]),
        '{{LINHAS_ABAIXO}}': linhas_tabela(abaixo[:12], 'baixa'),
        '{{LINHAS_PJ}}': linhas_pj(pj_top),
        '{{LINHAS_TICKET}}': linhas_ticket(ticket_top),
        '{{LINHAS_UF}}': linhas_uf(nac['ufs']),
    }
    for k, v in trocas.items():
        html = html.replace(k, v)
    with open(os.path.join(DOCS, 'index.html'), 'w', encoding='utf-8') as fh:
        fh.write(html)

    for nome in ('municipio.html', 'metodologia.html'):
        src = os.path.join(ROOT, 'src', nome.replace('.html', '.tpl.html'))
        texto = open(src, encoding='utf-8').read()
        texto = (texto.replace('{{MES}}', trocas['{{MES}}'])
                      .replace('{{N_MUN}}', trocas['{{N_MUN}}'])
                      .replace('{{ACIMA}}', trocas['{{ACIMA}}'])
                      .replace('{{ABAIXO}}', trocas['{{ABAIXO}}'])
                      .replace('{{EXCESSO}}', trocas['{{EXCESSO}}'])
                      .replace('{{MEDIANA}}', trocas['{{MEDIANA}}'])
                      .replace('{{VOLUME}}', trocas['{{VOLUME}}'])
                      .replace('{{TOP1}}', trocas['{{TOP1}}']))
        with open(os.path.join(DOCS, nome), 'w', encoding='utf-8') as fh:
            fh.write(texto)

    print('site gerado: index, municipio, metodologia, %d municipios, csv %.1f KB'
          % (len(enxuto), os.path.getsize(os.path.join(DOCS, 'dados', 'municipios.csv')) / 1024))


if __name__ == '__main__':
    main()
