# -*- coding: utf-8 -*-
"""Testes do pipeline do raio-X do Pix municipal. Rodam com:
    python3 -m unittest discover tests
"""
import gzip
import json
import math
import os
import statistics
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'src'))

import coleta  # noqa: E402
import modelo  # noqa: E402

DATA = os.path.join(ROOT, 'data')


def tem_dados():
    return os.path.exists(os.path.join(DATA, 'pix_municipios.csv.gz'))


class TestColeta(unittest.TestCase):
    def test_limpa_json_comentario(self):
        bruto = b'/*{"a": 1}*/'
        self.assertEqual(coleta.limpa_json(bruto), {'a': 1})

    def test_limpa_json_puro(self):
        self.assertEqual(coleta.limpa_json(b'{"a": 2}'), {'a': 2})

    def test_meses_comeca_em_202011(self):
        lista = list(coleta.meses())
        self.assertEqual(lista[0], '202011')
        self.assertEqual(lista[1], '202012')
        self.assertEqual(lista[2], '202101')

    def test_num_null(self):
        self.assertEqual(coleta.num(None), 0)
        self.assertEqual(coleta.num(3.5), 3.5)


class TestAlgebra(unittest.TestCase):
    def test_gauss_resolve_identidade(self):
        matriz = [[1.0, 0.0], [0.0, 1.0]]
        self.assertEqual(modelo.resolve(matriz, [3.0, 4.0]), [3.0, 4.0])

    def test_gauss_resolve_sistema(self):
        matriz = [[2.0, 1.0], [1.0, 3.0]]
        x = modelo.resolve(matriz, [5.0, 10.0])
        for a, esperado in zip((2 * x[0] + x[1], x[0] + 3 * x[1]), (5.0, 10.0)):
            self.assertAlmostEqual(a, esperado, places=9)

    def test_ols_recupera_coeficientes(self):
        X = [[1.0, 0.0], [1.0, 1.0], [1.0, 2.0], [1.0, 3.0]]
        y = [1.0, 3.0, 5.0, 7.0]  # y = 1 + 2x
        coef = modelo.ols_pesado(X, y, [1.0] * 4)
        self.assertAlmostEqual(coef[0], 1.0, places=6)
        self.assertAlmostEqual(coef[1], 2.0, places=6)

    def test_huber_derruba_outlier(self):
        # sem robustez, o outlier desloca a reta; com Huber, o coeficiente fica perto do real
        X = [[1.0, float(i)] for i in range(20)]
        y = [2.0 * i + 1.0 for i in range(20)]
        y[3] += 500.0  # um outlier absurdo
        coef, resid, escala = modelo.ajusta_robusto(X, y)
        self.assertAlmostEqual(coef[1], 2.0, delta=0.05)


class TestModeloDados(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not tem_dados():
            raise unittest.SkipTest('dados ainda nao coletados: rode python3 src/coleta.py')
        cls.painel = modelo.carrega_painel()
        cls.completos = modelo.meses_completos(cls.painel)

    def test_painel_tem_registros(self):
        self.assertGreater(len(self.painel), 300000)

    def test_codigos_ibge_validos(self):
        for l in self.painel[:2000]:
            cod = str(l['municipio_ibge'])
            self.assertEqual(len(cod), 7)
            self.assertTrue(cod[:2].isdigit())

    def test_meses_completos_descarta_parcial(self):
        # o mes corrente entra parcial na fonte; a funcao tem que remove-lo
        import time
        agora = time.localtime()
        ultimo = self.completos[-1]
        self.assertNotEqual(ultimo, agora.tm_year * 100 + agora.tm_mon,
                            'mes corrente apareceu como completo')

    def test_z_mediana_e_zero(self):
        modelo_json = json.load(open(os.path.join(DATA, 'modelo.json')))
        zs = [m['z'] for m in modelo_json['municipios']]
        self.assertLess(abs(statistics.median(zs)), 0.5)

    def test_desvio_consistente_com_z(self):
        modelo_json = json.load(open(os.path.join(DATA, 'modelo.json')))
        for m in modelo_json['municipios']:
            if m['z'] >= 3:
                self.assertGreater(m['dev'], 50)  # z alto implica desvio positivo grande
            if m['z'] <= -3:
                self.assertLess(m['dev'], 0)

    def test_excesso_so_para_acima(self):
        modelo_json = json.load(open(os.path.join(DATA, 'modelo.json')))
        acima = [m for m in modelo_json['municipios'] if m['z'] >= 3]
        self.assertTrue(all(m['exc'] > 0 for m in acima))

    def test_municipios_somam_5570(self):
        modelo_json = json.load(open(os.path.join(DATA, 'modelo.json')))
        self.assertIn(len(modelo_json['municipios']), (5570, 5571))


class TestSite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(os.path.join(ROOT, 'docs', 'index.html')):
            raise unittest.SkipTest('site ainda nao gerado: rode python3 src/site.py')

    def test_index_sem_placeholder(self):
        html = open(os.path.join(ROOT, 'docs', 'index.html'), encoding='utf-8').read()
        self.assertNotIn('{{', html)

    def test_metodologia_sem_placeholder(self):
        html = open(os.path.join(ROOT, 'docs', 'metodologia.html'), encoding='utf-8').read()
        self.assertNotIn('{{', html)

    def test_csv_tem_todos_os_municipios(self):
        csv_texto = open(os.path.join(ROOT, 'docs', 'dados', 'municipios.csv'), encoding='utf-8').read()
        self.assertEqual(csv_texto.count('\n'), 5571)  # cabecalho + 5570

    def test_json_de_navegador_valido(self):
        dados = json.load(open(os.path.join(ROOT, 'docs', 'dados', 'municipios.json'), encoding='utf-8'))
        self.assertEqual(len(dados), 5570)
        obrig = {'i', 'n', 'u', 'p', 'recebepc', 'exppc', 'z', 'dev', 'serie'}
        self.assertTrue(obrig.issubset(dados[0].keys()))

    def test_mapa_svg_existe(self):
        svg = open(os.path.join(ROOT, 'docs', 'dados', 'mapa.svg'), encoding='utf-8').read()
        self.assertGreater(svg.count('<path'), 5500)
        self.assertIn('data-c="1400456"', svg)  # Pacaraima presente


if __name__ == '__main__':
    unittest.main()
