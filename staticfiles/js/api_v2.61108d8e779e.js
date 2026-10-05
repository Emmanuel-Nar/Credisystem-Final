const API = (() => {
  const BASE_URL = "";

  const endpoints = {
    login: "/api/auth/login/",
    loginWeb: "/api/auth/login-web/",
    registro: "/api/auth/registro/",
    verificarEmail: "/api/auth/verificar/",
    reenviarCodigo: "/api/auth/verificar/reenviar/",
    refresh: "/api/auth/token/refresh/",
    logout: "/api/auth/logout/",
    me: "/api/auth/perfil/",
    cambiarPassword: "/api/auth/password/cambiar/",
    recuperarPassword: "/api/auth/password/recuperar/",
    confirmarPassword: "/api/auth/password/confirmar/",
    misCreditos: "/api/creditos/",
    detalleCredito: (id) => `/api/creditos/${id}/`,
    estadoCuenta: "/api/creditos/estado-cuenta/",
    simularCredito: "/api/creditos/simular/",
    solicitudesCredito: "/api/creditos/solicitudes/",
    solicitudCredito: (id) => `/api/creditos/solicitudes/${id}/`,
    crearPreferenciaPago: (creditoId) => `/api/creditos/${creditoId}/pagos/`,
    comprobantePago: (pagoId) => `/api/creditos/pagos/${pagoId}/comprobante/`,
    notificaciones: "/api/notificaciones/",
    marcarNotificacionLeida: (id) => `/api/notificaciones/${id}/leer/`,
    marcarTodasLeidas: "/api/notificaciones/leer-todas/",
    transacciones: "/api/transacciones/",
  };

  const TOKEN_KEY = "credisystem_access";
  const REFRESH_KEY = "credisystem_refresh";

  function getAccessToken() { return localStorage.getItem(TOKEN_KEY); }
  function getRefreshToken() { return localStorage.getItem(REFRESH_KEY); }
  function setTokens({ access, refresh }) {
    if (access) localStorage.setItem(TOKEN_KEY, access);
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
  }
  function clearTokens() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
  }
  function isLoggedIn() { return !!getAccessToken(); }

  async function refreshAccessToken() {
    const refresh = getRefreshToken();
    if (!refresh) return false;
    try {
      const res = await fetch(BASE_URL + endpoints.refresh, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh }),
      });
      if (!res.ok) return false;
      const data = await res.json();
      setTokens({ access: data.access });
      return true;
    } catch (e) {
      return false;
    }
  }

  async function request(path, { method = "GET", body = null, isForm = false, auth = true, csrfToken = null } = {}) {
    const makeOptions = () => {
      const headers = {};
      if (csrfToken) headers["X-CSRFToken"] = csrfToken;
      if (!isForm) headers["Content-Type"] = "application/json";
      if (auth && getAccessToken()) headers["Authorization"] = `Bearer ${getAccessToken()}`;
      const opts = { method, headers };
      if (body !== null) opts.body = isForm ? body : JSON.stringify(body);
      return opts;
    };

    let res = await fetch(BASE_URL + path, makeOptions());

    if (res.status === 401 && auth) {
      const refreshed = await refreshAccessToken();
      if (refreshed) res = await fetch(BASE_URL + path, makeOptions());
      else {
        clearTokens();
        window.location.href = "/login/?next=" + encodeURIComponent(window.location.pathname);
        return Promise.reject(new Error("Sesión expirada"));
      }
    }

    let data = null;
    try { data = await res.json(); } catch (e) {}

    if (!res.ok) {
      let msg = "Ocurrió un error. Probá de nuevo.";
      if (data) {
        if (typeof data.detail === "string") msg = data.detail;
        else if (typeof data.mensaje === "string") msg = data.mensaje;
        else if (typeof data.error === "string") msg = data.error;
        else {
          const first = Object.values(data).find(v => Array.isArray(v) && v.length) || Object.values(data).find(v => typeof v === "string");
          if (Array.isArray(first)) msg = first.join(" ");
          else if (typeof first === "string") msg = first;
        }
      }
      const err = new Error(msg);
      err.status = res.status;
      err.data = data;
      throw err;
    }
    return data;
  }

  function extraerResultados(data) {
    if (Array.isArray(data)) return data;
    if (data && Array.isArray(data.results)) return data.results;
    return [];
  }

  async function login(email, password, csrfToken = null) {
    const path = csrfToken ? endpoints.loginWeb : endpoints.login;
    const data = await request(path, { method: "POST", body: { email, password }, auth: false, csrfToken });
    clearTokens();
    if (!data.admin_url) setTokens({ access: data.access, refresh: data.refresh });
    return data;
  }
  async function registro(payload) { return request(endpoints.registro, { method: "POST", body: payload, auth: false }); }
  async function verificarEmail(email, codigo) { return request(endpoints.verificarEmail, { method: "POST", body: { email, codigo }, auth: false }); }
  async function reenviarCodigo(email) { return request(endpoints.reenviarCodigo, { method: "POST", body: { email }, auth: false }); }

  async function logout() {
    const refresh = getRefreshToken();
    try {
      if (refresh && getAccessToken()) await request(endpoints.logout, { method: "POST", body: { refresh } });
    } catch (e) {}
    clearTokens();
    window.location.href = "/login/";
  }

  async function me() { return request(endpoints.me); }
  async function actualizarPerfil(payload) { return request(endpoints.me, { method: "PATCH", body: payload }); }
  async function cambiarPassword(passwordActual, passwordNueva, passwordNueva2) {
    return request(endpoints.cambiarPassword, { method: "POST", body: { password_actual: passwordActual, password_nueva: passwordNueva, password_nueva2: passwordNueva2 } });
  }
  async function solicitarRecuperacion(email) { return request(endpoints.recuperarPassword, { method: "POST", body: { email }, auth: false }); }
  async function confirmarRecuperacion(email, codigo, passwordNueva, passwordNueva2) {
    return request(endpoints.confirmarPassword, { method: "POST", body: { email, codigo, password_nueva: passwordNueva, password_nueva2: passwordNueva2 }, auth: false });
  }

  async function misCreditos() { return extraerResultados(await request(endpoints.misCreditos)); }
  async function detalleCredito(id) { return request(endpoints.detalleCredito(id)); }
  async function estadoCuenta() { return request(endpoints.estadoCuenta); }
  async function simularCredito(monto, plazoMeses) {
    return request(endpoints.simularCredito, { method: "POST", body: { monto, plazo_meses: plazoMeses } });
  }
  async function solicitarCredito(formData) { return request(endpoints.solicitudesCredito, { method: "POST", body: formData, isForm: true }); }
  async function solicitudesCredito() { return extraerResultados(await request(endpoints.solicitudesCredito)); }
  async function detalleSolicitud(id) { return request(endpoints.solicitudCredito(id)); }

  async function crearPreferenciaPago(creditoId, monto, pagoTotal = false) {
    return request(endpoints.crearPreferenciaPago(creditoId), { method: "POST", body: { monto, pago_total: pagoTotal } });
  }

  async function notificaciones() { return extraerResultados(await request(endpoints.notificaciones)); }
  async function marcarNotificacionLeida(id) { return request(endpoints.marcarNotificacionLeida(id), { method: "PATCH" }); }
  async function marcarTodasLeidas() { return request(endpoints.marcarTodasLeidas, { method: "POST" }); }
  async function transacciones(params = "") { return extraerResultados(await request(endpoints.transacciones + params)); }

  return {
    endpoints, isLoggedIn, getAccessToken, clearTokens, logout,
    login, registro, verificarEmail, reenviarCodigo,
    me, actualizarPerfil, cambiarPassword, solicitarRecuperacion, confirmarRecuperacion,
    misCreditos, detalleCredito, estadoCuenta, simularCredito, solicitarCredito, solicitudesCredito, detalleSolicitud,
    crearPreferenciaPago, notificaciones, marcarNotificacionLeida, marcarTodasLeidas, transacciones,
  };
})();

function formatoARS(valor) {
  return new Intl.NumberFormat("es-AR", { style: "currency", currency: "ARS", maximumFractionDigits: 0 }).format(Number(valor) || 0);
}

function requireAuth() {
  if (!API.isLoggedIn()) window.location.href = "/login/?next=" + encodeURIComponent(window.location.pathname);
}

function mostrarErrorEnAlerta(alertaId, error) {
  const el = document.getElementById(alertaId);
  if (!el) return;
  el.textContent = error && error.message ? error.message : "Ocurrió un error. Probá de nuevo.";
  el.style.display = "flex";
}
