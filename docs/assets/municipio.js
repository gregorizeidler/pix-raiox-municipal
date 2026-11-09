// Ficha do município
(function () {
  var id = parseInt((location.search.match(/[?&]id=(\d+)/) || [])[1], 10);
  var fmt = function (v, c) {
    if (v === null || v === undefined || isNaN(v)) return '—';
    return Number(v).toLocaleString('pt-BR', { minimumFractionDigits: c || 0, maximumFractionDigits: c || 0 });
  };
  var brl = function (v, c) { return 'R$ ' + fmt(v, c); };

  Promise.all([
    fetch('dados/municipios.json').then(function (r) { return r.json(); }),
    fetch('dados/resumo.json').then(function (r) { return r.json(); })
  ]).then(function (par) {
    var lista = par[0], resumo = par[1].resumo;
    var m = lista.find(function (x) { return x.i === id; });
    if (!m) {
      document.getElementById('titulo').textContent = 'Município não encontrado';
      document.getElementById('subtitulo').textContent = 'Volte ao mapa e escolha um município na lista.';
      return;
    }
    document.title = m.n + ' (' + m.u + ') — Raio-X do Pix municipal';
    document.getElementById('titulo').textContent = m.n + ' · ' + m.u +
      (m.fr ? ' · faixa de fronteira' : '');
    document.getElementById('subtitulo').textContent =
      fmt(m.p) + ' habitantes · PIB por habitante de ' + brl(m.pibpc) +
      ' · Pix de pessoa física no município: ' + brl(m.recebepc) + ' por habitante.';

    var ztxt = m.z >= 3 ? 'muito acima do esperado' : m.z <= -3 ? 'muito abaixo do esperado'
             : Math.abs(m.z) <= 1.5 ? 'dentro do esperado' : (m.z > 0 ? 'levemente acima' : 'levemente abaixo');
    var itens = [
      ['Pix PF por habitante', brl(m.recebepc), 'média de 12 meses'],
      ['Esperado pelo modelo', brl(m.exppc), 'população + renda + UF + mês'],
      ['Desvio', (m.dev > 0 ? '+' : '') + fmt(m.dev, 1) + '%', 'diferença para o esperado'],
      ['Resíduo (z)', (m.z > 0 ? '+' : '') + fmt(m.z, 2), ztxt],
      ['Pix PJ por habitante', brl(m.pjpc), 'z de ' + fmt(m.zj, 1)],
      ['Ticket médio PF', brl(m.tk, 2), 'valor por transação recebida']
    ];
    document.getElementById('ficha').innerHTML = itens.map(function (it) {
      return '<div class="item"><div class="k">' + it[0] + '</div><div class="v">' + it[1] +
             '</div><div class="k" style="text-transform:none;letter-spacing:0;margin-top:4px">' + it[2] + '</div></div>';
    }).join('');

    var serie = m.serie.filter(function (v) { return v !== null; });
    var w = 720, h = 260, pad = { l: 64, r: 16, t: 16, b: 34 };
    var maxv = Math.max.apply(null, serie.concat([m.exppc]));
    var minv = Math.min.apply(null, serie.concat([m.exppc]));
    var span = (maxv - minv) || 1;
    var x = function (i) { return pad.l + i * (w - pad.l - pad.r) / Math.max(1, serie.length - 1); };
    var y = function (v) { return pad.t + (1 - (v - minv) / span) * (h - pad.t - pad.b); };
    var pontos = serie.map(function (v, i) { return x(i) + ',' + y(v); }).join(' ');
    var svg = '<svg class="grafico" viewBox="0 0 ' + w + ' ' + h + '" role="img" aria-label="Série mensal de Pix por habitante">';
    svg += '<line x1="' + pad.l + '" y1="' + y(m.exppc) + '" x2="' + (w - pad.r) + '" y2="' + y(m.exppc) +
           '" stroke="#c2410c" stroke-dasharray="6 5" stroke-width="1.5"/>';
    svg += '<text x="' + (w - pad.r) + '" y="' + (y(m.exppc) - 6) + '" text-anchor="end" font-size="11" fill="#c2410c">esperado</text>';
    svg += '<polyline points="' + pontos + '" fill="none" stroke="#0f9d8f" stroke-width="2.5"/>';
    serie.forEach(function (v, i) {
      svg += '<circle cx="' + x(i) + '" cy="' + y(v) + '" r="3" fill="#0f9d8f"/>';
    });
    svg += '<text x="' + (pad.l - 8) + '" y="' + (pad.t + 10) + '" text-anchor="end" font-size="11" fill="#71797f">' + brl(maxv) + '</text>';
    svg += '<text x="' + (pad.l - 8) + '" y="' + (h - pad.b) + '" text-anchor="end" font-size="11" fill="#71797f">' + brl(minv) + '</text>';
    svg += '</svg>';
    document.getElementById('grafico').innerHTML = svg;
    document.getElementById('rodape-grafico').textContent =
      'Valores em reais por habitante, recebidos por pessoa física, um ponto por mês.';

    var grupo = m.z >= 3 ? ' Entre os ' + fmt(resumo.n_municipios) + ' municípios, está no grupo de ' +
        fmt(resumo.acima_3) + ' que movimentam mais Pix do que população e renda explicam.'
      : m.z <= -3 ? ' Está no grupo de ' + fmt(resumo.abaixo_3) + ' municípios que movimentam menos Pix do que o esperado.'
      : ' Está dentro da faixa que o modelo explica — sem sinal de anomalia.';
    document.getElementById('leitura').textContent =
      'O modelo previa ' + brl(m.exppc) + ' por habitante e o município entregou ' + brl(m.recebepc) +
      ' — ' + (m.dev > 0 ? 'acima' : 'abaixo') + ' em ' + fmt(Math.abs(m.dev), 1) + '% (z ' +
      (m.z > 0 ? '+' : '') + fmt(m.z, 2) + ').' + grupo;

    var linhas = [
      ['População (IBGE, 2026)', fmt(m.p), 'estimativa mais recente'],
      ['PIB por habitante (2023)', brl(m.pibpc), 'PIB a preços correntes ÷ população'],
      ['Pix PF recebido por habitante', brl(m.recebepc), 'média dos 12 meses do modelo'],
      ['Excesso acumulado em 12 meses', brl(m.exc), 'acima do esperado no período'],
      ['Pix PJ recebido por habitante', brl(m.pjpc), 'sede de empresa infla este número'],
      ['Ticket médio PF', brl(m.tk, 2), 'valor médio por transação recebida']
    ];
    document.getElementById('tabela').innerHTML = linhas.map(function (l) {
      return '<tr><td>' + l[0] + '</td><td class="num">' + l[1] + '</td><td style="color:#71797f">' + l[2] + '</td></tr>';
    }).join('');

    document.getElementById('link-bcb').href = 'https://www.bcb.gov.br/estabilidadefinanceira/estatisticaspix';
    document.getElementById('link-ibge').href = 'https://cidades.ibge.gov.br/brasil/' + m.u.toLowerCase() +
      '/' + m.n.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9]+/g, '-');
  }).catch(function (e) {
    document.getElementById('titulo').textContent = 'Erro ao carregar a ficha';
    console.error(e);
  });
})();
