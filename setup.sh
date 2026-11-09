#!/usr/bin/env bash
# Ambiente do projeto: apenas Python 3.11 da biblioteca padrao (sem dependencias externas).
set -euo pipefail
cd "$(dirname "$0")"
python3 --version
mkdir -p data out docs/dados docs/assets
echo "pronto: nenhuma dependencia externa necessaria"
