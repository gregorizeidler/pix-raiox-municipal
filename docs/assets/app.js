// Mapa + busca do raio-X do Pix municipal
(function () {
  var alvo = document.getElementById('mapa-alvo');
  fetch('dados/mapa.svg').then(function (r) { return r.text(); }).then(function (svg) {
    alvo.innerHTML = svg;
    var mapa = alvo.querySelector('svg');
    if (mapa) {
      mapa.addEventListener('click', function (ev) {
        var p = ev.target.closest('path');
        if (p && p.dataset.c) window.location.href = 'municipio.html?id=' + p.dataset.c;
      });
    }
  }).catch(function () {
    alvo.innerHTML = '<p style="color:#71797f">Não foi possível carregar o mapa. ' +
      'A tabela abaixo tem a mesma informação.</p>';
  });

  var lista = document.getElementById('lista-municipios');
  var busca = document.getElementById('busca');
  var ir = document.getElementById('ir');
  var dados = null;

  function carrega(cb) {
    if (dados) return cb(dados);
    fetch('dados/municipios.json').then(function (r) { return r.json(); }).then(function (j) {
      dados = j;
      var frag = document.createDocumentFragment();
      j.slice().sort(function (a, b) { return a.n.localeCompare(b.n); }).forEach(function (m) {
        var o = document.createElement('option');
        o.value = m.n + ' — ' + m.u;
        o.setAttribute('data-id', m.i);
        frag.appendChild(o);
      });
      lista.appendChild(frag);
      cb(j);
    });
  }

  function abre() {
    var texto = (busca.value || '').trim().toLowerCase();
    if (!texto) return;
    carrega(function (j) {
      var achado = j.find(function (m) {
        return (m.n + ' — ' + m.u).toLowerCase() === texto ||
               m.n.toLowerCase() === texto ||
               (m.n + ' - ' + m.u).toLowerCase() === texto;
      });
      if (achado) window.location.href = 'municipio.html?id=' + achado.i;
      else alert('Município não encontrado. Tente pelo nome exato.');
    });
  }

  if (busca) {
    busca.addEventListener('focus', function () { carrega(function () {}); });
    busca.addEventListener('change', function () {
      var op = Array.prototype.find.call(lista.options, function (o) { return o.value === busca.value; });
      if (op) window.location.href = 'municipio.html?id=' + op.getAttribute('data-id');
    });
    busca.addEventListener('keydown', function (ev) { if (ev.key === 'Enter') abre(); });
  }
  if (ir) ir.addEventListener('click', abre);
})();
