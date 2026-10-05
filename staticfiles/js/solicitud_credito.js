(() => {
  requireAuth();
  const form = document.getElementById('formSolicitud');
  const campos = document.getElementById('camposSolicitud');
  const espera = document.getElementById('verificacionSolicitud');
  const resultado = document.getElementById('resultadoSolicitud');
  const error = document.getElementById('alertaError');
  const cuil = document.getElementById('cuilCuit');
  let enviando = false;
  let completada = false;
  let idEnvio = sessionStorage.getItem('credisystem_solicitud_envio');

  function nuevoId() {
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    bytes[6] = (bytes[6] & 15) | 64;
    bytes[8] = (bytes[8] & 63) | 128;
    const h = Array.from(bytes, b => b.toString(16).padStart(2, '0')).join('');
    return `${h.slice(0,8)}-${h.slice(8,12)}-${h.slice(12,16)}-${h.slice(16,20)}-${h.slice(20)}`;
  }
  function validarCuil() {
    const valor = cuil.value.trim();
    const numero = valor.replaceAll('-', '');
    let valido = /^(?:[0-9]{11}|[0-9]{2}-[0-9]{8}-[0-9])$/.test(valor);
    valido = valido && ['20','23','24','27','30','33','34'].includes(numero.slice(0,2));
    if (valido) {
      const pesos = [5,4,3,2,7,6,5,4,3,2];
      const suma = pesos.reduce((total, peso, i) => total + Number(numero[i]) * peso, 0);
      valido = (11 - suma % 11) % 11 === Number(numero[10]);
    }
    cuil.setCustomValidity(valido ? '' : 'Ingresá un CUIL/CUIT válido de 11 dígitos.');
    return valido;
  }
  cuil.addEventListener('input', () => cuil.setCustomValidity(''));
  cuil.addEventListener('blur', validarCuil);

  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (enviando || completada) return;
    error.style.display = 'none';
    validarCuil();
    if (!form.reportValidity()) return;
    const archivo = document.getElementById('archivoIngresos').files[0];
    if (!/\.(pdf|jpe?g|png)$/i.test(archivo.name) || archivo.size > 5 * 1024 * 1024) {
      error.textContent = 'Subí un archivo PDF, JPG o PNG de hasta 5 MB.';
      error.style.display = 'flex';
      return;
    }
    if (!idEnvio) {
      idEnvio = nuevoId();
      sessionStorage.setItem('credisystem_solicitud_envio', idEnvio);
    }
    const datos = new FormData();
    datos.append('monto_solicitado', document.getElementById('monto').value);
    datos.append('plazo_meses', document.getElementById('plazo').value);
    datos.append('ingresos_mensuales', document.getElementById('ingresos').value);
    datos.append('cuil_cuit', cuil.value.trim());
    datos.append('autorizacion_consulta', 'true');
    datos.append('id_envio', idEnvio);
    datos.append('comprobante', archivo);
    enviando = true;
    campos.disabled = true;
    form.hidden = true;
    espera.hidden = false;
    window.scrollTo({top: 0, behavior: 'instant'});
    try {
      const data = await API.solicitarCredito(datos);
      const mensajes = {
        aprobada: ['¡Tu solicitud fue aprobada!', 'El crédito ya está disponible para consultar en Mis créditos.', 'Ver mis créditos', '/mis-creditos/', 'solicitud-aprobada'],
        en_revision: ['Tu solicitud está en revisión', 'Recibimos tus datos. Te notificaremos cuando finalice la evaluación.', 'Ver mis solicitudes', '/mis-solicitudes/', 'solicitud-revision'],
        rechazada: ['Tu solicitud no fue aprobada', 'En este momento la solicitud no cumple las condiciones de otorgamiento. Podés consultar su estado en Mis solicitudes.', 'Ver mis solicitudes', '/mis-solicitudes/', 'solicitud-rechazada'],
      };
      const mensaje = mensajes[data.estado];
      if (!mensaje) throw new Error('No pudimos confirmar el resultado. Revisá Mis solicitudes antes de volver a intentar.');
      completada = true;
      sessionStorage.removeItem('credisystem_solicitud_envio');
      document.getElementById('resultadoEtiqueta').textContent = `Solicitud #${data.id_solicitud}`;
      document.getElementById('resultadoTitulo').textContent = mensaje[0];
      document.getElementById('resultadoMensaje').textContent = mensaje[1];
      const enlace = document.getElementById('resultadoEnlace');
      enlace.textContent = mensaje[2];
      enlace.href = mensaje[3];
      resultado.classList.add(mensaje[4]);
      resultado.hidden = false;
      document.getElementById('resultadoTitulo').focus({preventScroll: true});
      window.scrollTo({top: 0, behavior: 'instant'});
    } catch (exc) {
      form.hidden = false;
      if (!exc.status || exc.status >= 500) {
        error.textContent = 'No pudimos confirmar la respuesta. Revisá Mis solicitudes o reintentá el envío; conservamos el identificador para evitar duplicados.';
        error.style.display = 'flex';
      } else {
        mostrarErrorEnAlerta('alertaError', exc);
      }
    } finally {
      espera.hidden = true;
      campos.disabled = false;
      enviando = false;
    }
  });
})();
