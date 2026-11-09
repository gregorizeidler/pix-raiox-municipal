#!/usr/bin/env python3
"""Pipeline completo do raio-X do Pix municipal: coleta -> modelo -> analise -> mapa -> site -> testes.

Uso: python3 run.py            # tudo, do zero
     python3 run.py --sem-testes
"""
import subprocess
import sys
import os

ROOT = os.path.dirname(os.path.abspath(__file__))


def etapa(nome, script, *args):
    print('\n===== %s =====' % nome, flush=True)
    cmd = ['python3', os.path.join(ROOT, 'src', script)] + list(args)
    subprocess.run(cmd, check=True, cwd=ROOT)


def main():
    etapa('coleta', 'coleta.py')
    etapa('modelo', 'modelo.py')
    etapa('analise', 'analise.py')
    etapa('mapa', 'malha.py', '0.01')
    etapa('site', 'site.py')
    if '--sem-testes' not in sys.argv:
        print('\n===== testes =====', flush=True)
        subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s',
                        os.path.join(ROOT, 'tests'), '-v'], check=True, cwd=ROOT)
    print('\npipeline completo.')


if __name__ == '__main__':
    main()
