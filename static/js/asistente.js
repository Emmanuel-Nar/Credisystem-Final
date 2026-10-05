(() => {
  'use strict';
  const fuente = document.getElementById('asistente-datos');
  const dialogo = document.getElementById('ayuda-dialogo');
  if (!fuente || !dialogo || typeof dialogo.showModal !== 'function') return;
  const datos = JSON.parse(fuente.textContent);
  const abrir = document.getElementById('ayuda-abrir');
  const buscar = document.getElementById('ayuda-buscar');
  const lista = document.getElementById('ayuda-preguntas');
  const menu = document.getElementById('ayuda-menu');
  const detalle = document.getElementById('ayuda-respuesta');
  const titulo = document.getElementById('ayuda-pregunta-titulo');
  const enlace = document.getElementById('ayuda-enlace');
  const vacio = document.getElementById('ayuda-sin-resultados');
  let ultimaPregunta;
  const normalizar = texto => texto.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('es');

  function mostrarRespuesta(pregunta, boton) {
    ultimaPregunta = boton;
    titulo.textContent = pregunta.pregunta;
    document.getElementById('ayuda-respuesta-texto').textContent = pregunta.respuesta;
    enlace.hidden = !pregunta.enlace;
    enlace.removeAttribute('href');
    if (pregunta.enlace) enlace.href = pregunta.enlace;
    enlace.textContent = pregunta.etiqueta;
    menu.hidden = true;
    detalle.hidden = false;
    titulo.focus();
    document.querySelector('.ayuda-cuerpo').scrollTop = 0;
  }

  function filtrar() {
    const terminos = normalizar(buscar.value).trim().split(/\s+/).filter(Boolean);
    lista.replaceChildren();
    const coincidencias = datos.preguntas.filter(p => {
      const texto = normalizar(`${p.pregunta} ${p.respuesta}`);
      return terminos.every(t => texto.includes(t));
    });
    coincidencias.forEach(pregunta => {
      const boton = document.createElement('button');
      boton.type = 'button';
      boton.className = 'ayuda-pregunta';
      boton.textContent = pregunta.pregunta;
      boton.addEventListener('click', () => mostrarRespuesta(pregunta, boton));
      lista.append(boton);
    });
    vacio.hidden = coincidencias.length > 0;
    if (!datos.preguntas.length) vacio.textContent = 'Estamos actualizando las preguntas frecuentes. Podés ingresar a tu cuenta para consultar tus datos.';
  }

  abrir.hidden = false;
  abrir.addEventListener('click', () => {
    menu.hidden = false;
    detalle.hidden = true;
    dialogo.showModal();
    abrir.setAttribute('aria-expanded', 'true');
    document.body.classList.add('ayuda-abierta');
    buscar.focus();
  });
  document.getElementById('ayuda-cerrar').addEventListener('click', () => dialogo.close());
  dialogo.addEventListener('click', evento => {
    const rect = dialogo.getBoundingClientRect();
    if (evento.target === dialogo && (evento.clientX < rect.left || evento.clientX > rect.right || evento.clientY < rect.top || evento.clientY > rect.bottom)) dialogo.close();
  });
  dialogo.addEventListener('close', () => {
    abrir.setAttribute('aria-expanded', 'false');
    document.body.classList.remove('ayuda-abierta');
    abrir.focus();
  });
  document.getElementById('ayuda-volver').addEventListener('click', () => {
    detalle.hidden = true;
    menu.hidden = false;
    (ultimaPregunta?.isConnected ? ultimaPregunta : buscar).focus();
  });
  buscar.addEventListener('input', filtrar);
  if (datos.whatsapp) {
    const whatsapp = document.getElementById('ayuda-whatsapp');
    whatsapp.href = datos.whatsapp;
    whatsapp.hidden = false;
  }
  filtrar();
})();
