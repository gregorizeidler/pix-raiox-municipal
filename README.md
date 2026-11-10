# Raio-X do Pix municipal

Onde o Pix passa fora da curva: um modelo que estima quanto Pix cada município
brasileiro *deveria* receber por habitante — dado o tamanho da população e a renda
local — e sinaliza quem está muito acima ou muito abaixo disso.

**Site:** gregorizeidler.github.io/pix-raiox-municipal
**Fontes (todas abertas):** BCB (transações Pix por município), IBGE/SIDRA (população e PIB municipal), IBGE (malha municipal e municípios da faixa de fronteira).

## O que o projeto responde

1. Quanto Pix cada município recebe por habitante, e quanto disso é explicado por população e renda.
2. Quais municípios destoam (resíduo robusto, em z), tanto para cima quanto para baixo.
3. Onde o Pix de pessoa jurídica revela município-sede (endereço fiscal) em vez de economia local.
4. Onde o ticket médio revela um Pix "de agro": valores médios por transação acima de R$ 800 nos polos de grão.

Números do build de 09/11/2026 (dados até out/2026):

- 406.518 linhas município-mês coletadas (nov/2020 a out/2026);
- 66.840 observações no modelo (12 meses × 5.570 municípios);
- 46 municípios com z ≥ 3 e 30 com z ≤ −3;
- R$ 3,27 tri de Pix recebido no último mês completo (PF+PJ); os 1% maiores municípios concentram 59,4% do valor.

## Método

Para cada município `i` e mês `t`:

    log(PixPF_it / pop_i) = a + b·log(pop_i) + c·log(PIBpc_i) + d_UF + th_t + e_it

- **PixPF/pop** — valor recebido por pessoa física por habitante. Variável-resultado escolhida
  porque o Pix de PJ é recebido na sede da empresa, o que inflaria municípios pequenos
  que abrigam tesouraria de redes.
- **log(pop)** — economias de escala e aglomeração.
- **log(PIB por habitante)** — renda. Sem este controle, município rico viraria "anomalia".
- **Efeito fixo de UF** — bancarização, costume de pagamento, estrutura tributária.
- **Efeito fixo de mês** — sazonalidade (13º, safra, festas).

Ajuste **robusto por IRLS com peso de Huber** (corte em 1,345 desvios medidos por
1,4826 × MAD), para que os próprios outliers não puxem a reta. O **z** de cada município
é o resíduo mediano em 12 meses dividido pela escala robusta. A janela de 12 meses
reduz o peso de um mês atípico; o mês corrente é descartado porque a fonte o publica parcial.

O código do modelo (regressão pesada, IRLS, eliminador de Gauss com pivoteamento) é
dependência-zero: biblioteca padrão do Python 3.

## Achados que o modelo já produziu

- **Fronteira e comércio:** cruzando com a lista oficial de municípios da faixa de
  fronteira do IBGE (590 municípios, 2024), 8 dos 46 sinalizados estão na faixa.
  Pacaraima (RR) recebe R$ 31.015 por habitante em Pix PF —
  12,5× o esperado (z = 11,9), o maior resíduo do país. A lista dos 46 sinalizados concentra
  municípios pequenos de fronteira, garimpo e rota comercial.
- **Agro:** Mato Grosso lidera o Pix PF por habitante entre UFs (R$ 7.952), e os maiores
  tickets médios do país são dos polos de grão (Lucas do Rio Verde R$ 1.252, Sorriso R$ 1.124).
- **Município-sede:** Santo Antônio de Lisboa (PI), 5.923 habitantes, aparece com R$ 491 mil
  de Pix PJ por habitante — endereço fiscal, não economia local.
- **O outro extremo:** os municípios com z ≤ −3 são pequenos, majoritariamente do
  Norte/Nordeste, muitos em área indígena — Pix baixo por habitante costuma indicar
  ausência de infraestrutura financeira, não fraude.

Anomalia estatística não é irregularidade: o sinal aponta onde olhar, nunca o que concluir.

## Estrutura

    src/coleta.py     # API BCB (TransacoesPixPorMunicipio) + SIDRA + malha; CSV gz municipal
    src/modelo.py     # regressão robusta em log, efeitos fixos de UF e mês, z por município
    src/analise.py    # agregados nacionais, por UF, concentração, distribuição do z
    src/malha.py      # GeoJSON IBGE -> SVG (Douglas-Peucker, projeção equirretangular corrigida)
    src/site.py       # gera o site estático em docs/ a partir dos JSONs
    src/*.tpl.html    # modelos das páginas
    tests/            # 20 testes: álgebra do modelo, Huber derruba outlier, integridade dos dados
    run.py            # pipeline completo, do zero
    docs/             # site publicado (GitHub Pages, branch main, pasta /docs)

## Como rodar

    bash setup.sh
    python3 run.py                 # coleta, modelo, análise, mapa, site e testes
    # ou por etapa:
    python3 src/coleta.py          # ~2 min (73 meses da API do BCB)
    python3 src/modelo.py          # ~30 s
    python3 src/analise.py
    python3 src/malha.py 0.01      # tolerância de simplificação do mapa
    python3 src/site.py
    python3 -m unittest discover tests

Sem dependências externas. A coleta é idempotente (refaz tudo a cada rodada; a API
do BCB não cobra por chamada). O workflow .github/workflows/atualizar.yml roda o
pipeline todo dia às 09:00 UTC e publica o site.

## Como ler os outputs

- data/pix_municipios.csv.gz — painel cru município-mês (nov/2020 em diante);
- data/modelo.json — um registro por município: z, desvio, esperado, excesso acumulado,
  ticket médio, série mensal;
- data/nacional.json — série nacional, UFs, concentração, distribuição do z;
- docs/dados/municipios.csv — a planilha de bolso (ponto-e-vírgula, UTF-8);
- out/outliers.csv — os 60 maiores resíduos para inspeção.

## Armadilhas que o código já trata (e você deveria saber)

- A API do BCB publica o recurso TransacoesPixPorMunicipio como *função*: sem o
  parâmetro DataBase (AAAAMM) o endpoint devolve 500, e o conjunto listado no
  $metadata com underscore (_TransacoesPixPorMunicipio) não aceita query. A URL
  que funciona é TransacoesPixPorMunicipio(DataBase='202601')?$filter=AnoMes eq 202601.
- O mês corrente vem parcial na fonte: o pipeline descarta meses com menos de 60% da
  mediana dos últimos antes de modelar.
- O GeoJSON da malha IBGE chega gzipado mesmo sem Accept-Encoding — o coletor
  confere o magic bytes antes de gravar.
- O PIB municipal mais recente é de 2023; qualquer município que mudou muito desde então
  entra como anomalia. População é a estimativa corrente do SIDRA.
- Municípios sem população ou PIB publicados ficam fora do modelo (não zerados).

## Limites

- O dado mede **fluxo liquidado por município do recebedor/pagador**, não renda: a mesma
  nota circula várias vezes no mês.
- Municípios muito pequenos têm variância alta; parte dos sinalizados tem menos de
  10 mil habitantes.
- PJ é sensível a sede de empresa; PF é sensível a fronteira (comerciante que recebe de
  outro país via Pix nacional de terceiros) e a sazonalidade de safra.
- O modelo não pretende ser triagem de PLD-FT: é um raio-X descritivo. Usá-lo como
  insumo de due diligence exige validação que este repositório não faz.

## Cruzamento: operadoras de apostas de quota fixa (SPA/MF)

Uma hipótese natural para municípios com Pix muito acima do esperado é sede de operadora de
apostas — o setor movimenta tesouraria grande e pouca gente sabe onde as empresas ficam.

- A lista oficial existe e está publicada: [SPA/MF — Empresas autorizadas](https://www.gov.br/fazenda/pt-br/composicao/orgaos/secretaria-de-premios-e-apostas/transparencia-ativa-processos-de-autorizacao-de-apostas-de-quota-fixa/empresas-autorizadas),
  na página de transparência ativa dos processos de autorização. Captura de 10/11/2026: 85 linhas,
  **82 CNPJs autorizados**, com portaria, marcas, domínios e o PDF de cada processo.
- O município da sede vem do próprio CNPJ (base pública da Receita, via BrasilAPI). As 82 operadoras
  ficam em 20 municípios: São Paulo (53), Recife (5), Nova Lima (3), Barueri (3) e mais 16 cidades.
- Dos 46 municípios com z ≥ 3 no modelo, **só Nova Lima/MG** é sede de operadora autorizada — três:
  RR Participações (Multibet, Ricobet, BRXBet), Sevenx Gaming (BullsBet, Jogão) e Ana Gaming
  (7K, Cassino, Vera). Nova Lima tem z = 3,66 e Pix PJ/hab de R$ 32,6 mil (z_j = 2,43, 7º entre os 46),
  compatível com tesouraria de operadoras.
- Nos outros 45 — Pacaraima, Campo Florido, Fernando de Noronha, Águas Frias, o interior e a
  fronteira — não há sede de operadora autorizada. **Apostas não explicam essas anomalias.**
- O snapshot fica em `data/bets-operadoras.json`. A lista não entra no pipeline diário: não muda o
  diagnóstico e depende de página HTML e de uma consulta por CNPJ.

## Licença

Código: MIT. Dados: os das fontes — ODbL (BCB) e uso permitido pelo IBGE (obrigatório
citar a fonte, vedado alterar os dados). Ao reutilizar, cite BCB e IBGE.
