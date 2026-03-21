import json
from datetime import date

from flask import Blueprint, Response, render_template

from dashboard_routes import DASHBOARD_HTML, LOGIN_HTML
from demo_data import DEMO_ALUMNOS, DEMO_INGRESOS, DEMO_PORTAL_RESUMEN
from portal_routes import PORTAL_HTML, PORTAL_HOME_CONTENT

demo_bp = Blueprint("demo", __name__)

# Script para demo: acceso profesora sin POST real al servidor
DEMO_LOGIN_FORM_SCRIPT = """
<script>
(function(){
  try {
    var forms = document.querySelectorAll('form[method="POST"]');
    var i;
    for (i = 0; i < forms.length; i++) {
      forms[i].addEventListener('submit', function(ev) {
        ev.preventDefault();
        window.location.href = '/demo/dashboard';
      });
    }
  } catch (e) {}
})();
</script>
"""


def aplicar_enlaces_demo_login_logout(html):
    """En páginas demo: Salir → /demo/login; href a /login → /demo/login (no toca /dashboard/login)."""
    html = html.replace('href="/dashboard/logout"', 'href="/demo/login"')
    html = html.replace("href='/dashboard/logout'", "href='/demo/login'")
    html = html.replace('href="/portal/logout"', 'href="/demo/login"')
    html = html.replace("href='/portal/logout'", "href='/demo/login'")
    html = html.replace('href="/login"', 'href="/demo/login"')
    html = html.replace("href='/login'", "href='/demo/login'")
    return html


def aplicar_rutas_navegacion_demo(html):
    """Trainer, portal home/progreso y redirects JS → rutas /demo/* (no toca /portal/api ni /auth/google)."""
    html = html.replace('href="/trainer"', 'href="/demo/trainer"')
    html = html.replace("href='/trainer'", "href='/demo/trainer'")
    html = html.replace('href="/portal/entrenamiento"', 'href="/demo/portal"')
    html = html.replace("href='/portal/entrenamiento'", "href='/demo/portal'")
    html = html.replace('href="/portal/home"', 'href="/demo/portal"')
    html = html.replace("href='/portal/home'", "href='/demo/portal'")
    html = html.replace("window.location.href='/trainer'", "window.location.href='/demo/trainer'")
    html = html.replace('window.location.href="/trainer"', 'window.location.href="/demo/trainer"')
    html = html.replace("window.location.href = '/trainer'", "window.location.href = '/demo/trainer'")
    html = html.replace('window.location.href = "/trainer"', 'window.location.href = "/demo/trainer"')
    html = html.replace("window.location.href='/portal/home'", "window.location.href='/demo/portal'")
    html = html.replace('window.location.href="/portal/home"', 'window.location.href="/demo/portal"')
    html = html.replace("window.location.href = '/portal/home'", "window.location.href = '/demo/portal'")
    html = html.replace('window.location.href = "/portal/home"', 'window.location.href = "/demo/portal"')
    html = html.replace("window.location.href='/login'", "window.location.href='/demo/login'")
    html = html.replace('window.location.href="/login"', 'window.location.href="/demo/login"')
    html = html.replace("window.location.href = '/login'", "window.location.href = '/demo/login'")
    html = html.replace('window.location.href = "/login"', 'window.location.href = "/demo/login"')
    html = html.replace("location.href='/login'", "location.href='/demo/login'")
    html = html.replace('location.href="/login"', 'location.href="/demo/login"')
    html = html.replace("location.href = '/login'", "location.href = '/demo/login'")
    html = html.replace('location.href = "/login"', 'location.href = "/demo/login"')
    return html


def aplicar_todas_las_rutas_demo(html):
    return aplicar_rutas_navegacion_demo(aplicar_enlaces_demo_login_logout(html))


# Clases ficticias para la demo del dashboard (misma lista que usa el intercept en el navegador)
DEMO_CLASES = [
    {
        "fecha": "2026-03-02",
        "hora": "18:00",
        "estado": "dada",
        "origen": "calendar",
        "pago_id": 1,
        "ausente": 0,
        "nombre": "Lucas M.",
        "pais": "AR",
        "moneda": "USD",
        "modalidad": "online",
    },
    {
        "fecha": "2026-03-05",
        "hora": "19:30",
        "estado": "dada",
        "origen": "calendar",
        "pago_id": 2,
        "ausente": 0,
        "nombre": "Grace K.",
        "pais": "UK",
        "moneda": "GBP",
        "modalidad": "online",
    },
    {
        "fecha": "2026-03-06",
        "hora": "17:00",
        "estado": "agendada",
        "origen": "calendar",
        "pago_id": None,
        "ausente": 0,
        "nombre": "Henry S.",
        "pais": "US",
        "moneda": "USD",
        "modalidad": "online",
    },
    {
        "fecha": "2026-03-08",
        "hora": "18:30",
        "estado": "dada",
        "origen": "calendar",
        "pago_id": 3,
        "ausente": 0,
        "nombre": "Emma R.",
        "pais": "AR",
        "moneda": "ARS",
        "modalidad": "online",
    },
    {
        "fecha": "2026-03-09",
        "hora": "20:00",
        "estado": "dada",
        "origen": "calendar",
        "pago_id": None,
        "ausente": 0,
        "nombre": "Santiago P.",
        "pais": "CL",
        "moneda": "USD",
        "modalidad": "online",
    },
    {
        "fecha": "2026-03-11",
        "hora": "19:00",
        "estado": "agendada",
        "origen": "calendar",
        "pago_id": None,
        "ausente": 0,
        "nombre": "Ana L.",
        "pais": "MX",
        "moneda": "USD",
        "modalidad": "online",
    },
    {
        "fecha": "2026-03-12",
        "hora": "18:00",
        "estado": "cancelada-profe",
        "origen": "calendar",
        "pago_id": None,
        "ausente": 0,
        "nombre": "Michael B.",
        "pais": "US",
        "moneda": "USD",
        "modalidad": "online",
    },
    {
        "fecha": "2026-03-14",
        "hora": "16:30",
        "estado": "dada",
        "origen": "calendar",
        "pago_id": 4,
        "ausente": 0,
        "nombre": "Lucía G.",
        "pais": "ES",
        "moneda": "EUR",
        "modalidad": "online",
    },
    {
        "fecha": "2026-03-16",
        "hora": "18:00",
        "estado": "dada",
        "origen": "calendar",
        "pago_id": None,
        "ausente": 1,
        "nombre": "Tom H.",
        "pais": "CA",
        "moneda": "USD",
        "modalidad": "online",
    },
    {
        "fecha": "2026-03-18",
        "hora": "19:30",
        "estado": "agendada",
        "origen": "calendar",
        "pago_id": None,
        "ausente": 0,
        "nombre": "Valentina R.",
        "pais": "AR",
        "moneda": "ARS",
        "modalidad": "online",
    },
]


DEMO_BANNER_SNIPPET = """
<style>
.demo-banner-root{font-family:'DM Sans',system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}
.demo-banner{background:rgba(18,18,18,0.96);color:#f4f4f4;border-bottom:1px solid rgba(255,255,255,0.06);padding:0.45rem 1.25rem;display:flex;align-items:center;justify-content:space-between;gap:0.75rem;font-size:0.8rem;backdrop-filter:blur(10px);position:sticky;top:0;z-index:2000}
.demo-banner-left{display:flex;align-items:center;gap:0.5rem;min-width:0}
.demo-badge{background:#3b5c3b;color:#e6ffe6;font-size:0.7rem;font-weight:600;text-transform:uppercase;letter-spacing:0.08em;border-radius:999px;padding:0.15rem 0.55rem;border:1px solid rgba(230,255,230,0.18);white-space:nowrap}
.demo-text{color:#d0d0d0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.demo-banner-right{display:flex;align-items:center;gap:0.75rem;flex-wrap:wrap;justify-content:flex-end}
.demo-nav-links{display:flex;align-items:center;gap:0.6rem;flex-wrap:wrap}
.demo-link{color:#d0e7ff;text-decoration:none;font-size:0.78rem;opacity:0.9;transition:opacity 0.15s,transform 0.15s}
.demo-link:hover{opacity:1;transform:translateY(-1px)}
.demo-toggle-group{display:flex;align-items:center;gap:0.25rem}
.demo-toggle{background:transparent;border:1px solid rgba(255,255,255,0.25);color:#f4f4f4;border-radius:999px;padding:0.12rem 0.5rem;font-size:0.72rem;cursor:pointer;display:inline-flex;align-items:center;gap:0.25rem;opacity:0.9;transition:background 0.15s,border-color 0.15s,opacity 0.15s,transform 0.15s}
.demo-toggle:hover{opacity:1;transform:translateY(-1px)}
.demo-toggle span{font-size:0.9rem}
.demo-toggle-active{background:#f4f4f4;color:#181818;border-color:#f4f4f4}
.demo-lang-pill{display:inline-flex;border-radius:999px;overflow:hidden;border:1px solid rgba(255,255,255,0.25)}
.demo-lang-btn{background:transparent;border:none;color:#f4f4f4;font-size:0.72rem;padding:0.14rem 0.55rem;cursor:pointer;opacity:0.7}
.demo-lang-btn-active{background:#f4f4f4;color:#181818;opacity:1}
.theme-light .demo-banner{background:rgba(245,246,250,0.96);color:#1e293b;border-bottom-color:rgba(15,23,42,0.08)}
.theme-light .demo-badge{background:#d9f99d;color:#3f6212;border-color:rgba(163,230,53,0.6)}
.theme-light .demo-text{color:#1e293b}
.theme-light .demo-link{color:#1d4ed8}
.theme-light .demo-toggle{border-color:rgba(15,23,42,0.25);color:#111827}
.theme-light .demo-lang-pill{border-color:rgba(15,23,42,0.25)}
.theme-light .demo-lang-btn{color:#111827}
.theme-light .demo-toggle-active{background:#111827;color:#f9fafb;border-color:#111827}
.theme-light .demo-lang-btn-active{background:#111827;color:#f9fafb}
@media(max-width:720px){.demo-text{display:none}.demo-banner{padding-inline:0.75rem}}
.demo-empty-card{font-family:inherit}
#demo-action-toast{position:fixed;bottom:1.1rem;right:1.1rem;z-index:10050;max-width:20rem;padding:0.65rem 1rem;border-radius:8px;font-size:0.8rem;line-height:1.35;color:var(--text);background:var(--surface2);border:1px solid var(--border);box-shadow:0 4px 20px var(--shadow);opacity:0;pointer-events:none;transition:opacity 0.35s ease;font-family:'DM Sans',system-ui,sans-serif}
#demo-action-toast.demo-toast-visible{opacity:1}
</style>
<div class="demo-banner-root">
  <div class="demo-banner">
    <div class="demo-banner-left">
      <span class="demo-badge">DEMO</span>
      <span class="demo-text" data-es="Esta es una demo en vivo con datos ficticios" data-en="This is a live demo with fictional data">Esta es una demo en vivo con datos ficticios</span>
    </div>
    <div class="demo-banner-right">
      <nav class="demo-nav-links">
        <a class="demo-link" href="/demo/dashboard" data-es="Dashboard demo" data-en="Dashboard demo">Dashboard demo</a>
        <a class="demo-link" href="/demo/portal" data-es="Portal demo" data-en="Portal demo">Portal demo</a>
        <a class="demo-link" href="/demo/trainer" data-es="Trainer demo" data-en="Trainer demo">Trainer demo</a>
        <a class="demo-link" href="https://andreferdev.com" data-es="← Volver al portfolio" data-en="← Back to portfolio">← Volver al portfolio</a>
      </nav>
      <div class="demo-toggle-group">
        <button type="button" id="demo-theme-toggle" class="demo-toggle" aria-label="Theme">
          <span id="demo-theme-icon">🌙</span>
        </button>
        <div class="demo-lang-pill" role="group" aria-label="Language">
          <button type="button" id="demo-lang-es" class="demo-lang-btn demo-lang-btn-active">ES</button>
          <button type="button" id="demo-lang-en" class="demo-lang-btn">EN</button>
        </div>
      </div>
    </div>
  </div>
</div>
<script>
(function() {{
  try {{
    // THEME
    var storedTheme = null;
    try { storedTheme = window.localStorage.getItem('dashboard-theme'); } catch(e) {}
    var theme = (storedTheme === 'light' || storedTheme === 'dark' || storedTheme === 'navy') ? storedTheme : 'light';
    if (typeof window.setTheme === 'function') {
      window.setTheme(theme, null);
    } else {
      document.documentElement.setAttribute('data-theme', theme);
    }
    var themeIcon = document.getElementById('demo-theme-icon');
    if (themeIcon) {{
      themeIcon.textContent = theme === 'light' ? '🌙' : '☀️';
    }}
    var themeBtn = document.getElementById('demo-theme-toggle');
    if (themeBtn) {{
      themeBtn.addEventListener('click', function() {{
        theme = (theme === 'light') ? 'dark' : 'light';
        try {{ window.localStorage.setItem('dashboard-theme', theme); }} catch(e) {{}}
        if (typeof window.setTheme === 'function') {{
          window.setTheme(theme, null);
        }} else {{
          document.documentElement.setAttribute('data-theme', theme);
        }}
        if (themeIcon) {{
          themeIcon.textContent = theme === 'light' ? '🌙' : '☀️';
        }}
      }});
    }}
    // LANG
    function applyLang(lang) {{
      var nodes = document.querySelectorAll('[data-es],[data-en]');
      nodes.forEach(function(el) {{
        var text = lang === 'en' ? el.getAttribute('data-en') : el.getAttribute('data-es');
        if (text !== null) el.textContent = text;
      }});
      var html = document.documentElement;
      if (html) html.setAttribute('lang', lang === 'en' ? 'en' : 'es');
    }}
    var storedLang = window.localStorage.getItem('demo_lang');
    var lang = (storedLang === 'en' || storedLang === 'es') ? storedLang : 'es';
    applyLang(lang);
    var btnEs = document.getElementById('demo-lang-es');
    var btnEn = document.getElementById('demo-lang-en');
    function updateLangButtons() {{
      if (!btnEs || !btnEn) return;
      if (lang === 'es') {{
        btnEs.classList.add('demo-lang-btn-active');
        btnEn.classList.remove('demo-lang-btn-active');
      }} else {{
        btnEn.classList.add('demo-lang-btn-active');
        btnEs.classList.remove('demo-lang-btn-active');
      }}
    }}
    updateLangButtons();
    if (btnEs) btnEs.addEventListener('click', function() {{
      lang = 'es';
      window.localStorage.setItem('demo_lang', lang);
      applyLang(lang);
      updateLangButtons();
    }});
    if (btnEn) btnEn.addEventListener('click', function() {{
      lang = 'en';
      window.localStorage.setItem('demo_lang', lang);
      applyLang(lang);
      updateLangButtons();
    }});

    // --- Demo UX: pestañas atascadas en "Cargando..." y acciones sin backend (dashboard + portal) ---
    var demoPath = window.location.pathname;
    var demoIsDash = demoPath === '/demo/dashboard';
    var demoIsPortal = demoPath === '/demo/portal';

    function demoToastEnsure() {{
      var el = document.getElementById('demo-action-toast');
      if (el) return el;
      el = document.createElement('div');
      el.id = 'demo-action-toast';
      el.setAttribute('role', 'status');
      document.body.appendChild(el);
      return el;
    }}

    function demoToastShow() {{
      var el = demoToastEnsure();
      var t = lang === 'en' ? 'Feature available in the full version' : 'Función disponible en la versión completa';
      el.textContent = t;
      el.classList.add('demo-toast-visible');
      if (window._demoToastHideT) clearTimeout(window._demoToastHideT);
      window._demoToastHideT = setTimeout(function() {{
        el.classList.remove('demo-toast-visible');
      }}, 2000);
    }}

    function demoFillEmptyInto(container, es, en) {{
      if (!container) return;
      container.innerHTML = '';
      var wrap = document.createElement('div');
      wrap.className = 'demo-empty-card';
      wrap.style.cssText = 'max-width:28rem;margin:2.5rem auto;padding:1.75rem 1.5rem;border:1px solid var(--border);border-radius:8px;background:var(--surface);box-shadow:0 2px 10px var(--shadow);text-align:center;';
      var icon = document.createElement('div');
      icon.style.cssText = 'font-size:1.75rem;line-height:1;margin-bottom:0.75rem;';
      icon.textContent = '\u2139\uFE0F';
      var p = document.createElement('p');
      p.className = 'demo-empty-msg';
      p.style.cssText = 'margin:0;font-size:0.9rem;color:var(--text-dim);line-height:1.5;';
      p.setAttribute('data-es', es);
      p.setAttribute('data-en', en);
      p.textContent = lang === 'en' ? en : es;
      wrap.appendChild(icon);
      wrap.appendChild(p);
      container.appendChild(wrap);
    }}

    function demoFillTableEmpty(tbodyId, colspan, es, en) {{
      var tb = document.getElementById(tbodyId);
      if (!tb) return;
      var cell = tb.querySelector('tr td');
      if (!cell || cell.textContent.indexOf('Cargando') === -1) return;
      if (tb.querySelector('.demo-empty-card')) return;
      var tr = document.createElement('tr');
      var td = document.createElement('td');
      td.colSpan = colspan;
      td.style.padding = '0';
      td.style.verticalAlign = 'middle';
      var inner = document.createElement('div');
      td.appendChild(inner);
      tr.appendChild(td);
      tb.innerHTML = '';
      tb.appendChild(tr);
      demoFillEmptyInto(inner, es, en);
    }}

    function demoMaybeGraficosEmpty() {{
      if (!demoIsDash) return;
      var panel = document.getElementById('tab-graficos');
      if (!panel || !panel.classList.contains('active')) return;
      if (panel.querySelector('.demo-empty-card')) return;
      var chOk = typeof charts !== 'undefined' && charts && charts.anual;
      if (chOk) return;
      var grid = panel.querySelector('.grid-2');
      if (!grid) return;
      grid.innerHTML = '';
      demoFillEmptyInto(grid,
        'Esta sección muestra gráficos de ingresos por moneda y por mes en la versión completa.',
        'This section shows revenue charts by currency and month in the full version.');
      applyLang(lang);
    }}

    function demoDashboardApplyLoadingEmptyStates() {{
      if (!demoIsDash) return;
      var cob = document.getElementById('cobros-content');
      if (cob && cob.textContent.indexOf('Cargando') !== -1 && !cob.querySelector('.demo-empty-card')) {{
        demoFillEmptyInto(cob,
          'Esta sección muestra el seguimiento de cobros y pagos por alumno y por semana en la versión completa.',
          'This section shows payment tracking by student and week in the full version.');
        applyLang(lang);
      }}
      demoFillTableEmpty('t-pagos', 8,
        'Esta sección muestra el historial completo de pagos con comprobantes en la versión completa.',
        'This section shows the full payment history with receipts in the full version.');
      demoFillTableEmpty('t-deuda', 6,
        'Esta sección muestra a los alumnos con saldo pendiente en la versión completa.',
        'This section shows students with outstanding balances in the full version.');
      demoFillTableEmpty('t-alumnos', 11,
        'Esta sección muestra el listado completo de alumnos con perfil y estadísticas en la versión completa.',
        'This section shows the full student roster with profile and stats in the full version.');
      applyLang(lang);
      demoMaybeGraficosEmpty();
    }}

    function demoTabIdFromBtn(tabBtn) {{
      var oc = tabBtn.getAttribute('onclick') || '';
      var ids = ['cobros', 'pagos', 'deuda', 'alumnos', 'graficos'];
      for (var i = 0; i < ids.length; i++) {{
        if (oc.indexOf("showTab('" + ids[i] + "'") !== -1) return ids[i];
      }}
      return null;
    }}

    if (demoIsDash) {{
      setTimeout(function() {{ demoDashboardApplyLoadingEmptyStates(); }}, 1500);
      document.addEventListener('click', function(ev) {{
        var tabBtn = ev.target && ev.target.closest && ev.target.closest('.tab-btn');
        if (!tabBtn) return;
        var tid = demoTabIdFromBtn(tabBtn);
        if (!tid) return;
        setTimeout(function() {{
          demoDashboardApplyLoadingEmptyStates();
          if (tid === 'graficos') demoMaybeGraficosEmpty();
        }}, 1600);
      }}, false);
    }}

    if (demoIsDash || demoIsPortal) {{
      function demoFetchUrl(input) {{
        if (typeof input === 'string') return input;
        if (input && input.url) return input.url;
        return '';
      }}

      function demoAllowPostThrough(url) {{
        if (demoIsDash && url.indexOf('/dashboard/api/chat') !== -1) return true;
        return false;
      }}

      function demoFakeJsonResponse() {{
        var body = JSON.stringify({ ok: true, nuevos: 0, cancelados: 0, modificados: 0 });
        if (window.Response) {{
          return Promise.resolve(new Response(body, {
            status: 200,
            headers: { 'Content-Type': 'application/json' }
          }));
        }}
        return Promise.resolve({
          ok: true,
          status: 200,
          json: function() {{ return Promise.resolve(JSON.parse(body)); }},
          text: function() {{ return Promise.resolve(body); }}
        });
      }}

      var prevFetchBanner = window.fetch;
      if (typeof prevFetchBanner === 'function') {{
        window.fetch = function(input, init) {{
          init = init || {};
          var method = (init.method || 'GET').toUpperCase();
          var url = demoFetchUrl(input);
          if (method === 'POST' || method === 'PUT' || method === 'DELETE') {{
            if (!demoAllowPostThrough(url)) {{
              demoToastShow();
              return demoFakeJsonResponse();
            }}
          }}
          return prevFetchBanner.call(this, input, init);
        }};
      }}

      if (window.XMLHttpRequest) {{
        var XHRb = XMLHttpRequest.prototype;
        var prevOpenBanner = XHRb.open;
        var prevSendBanner = XHRb.send;
        XHRb.open = function(method, url) {{
          this._demoBannerMethod = method;
          this._demoBannerUrl = url;
          return prevOpenBanner.apply(this, arguments);
        }};
        XHRb.send = function(body) {{
          try {{
            var m = (this._demoBannerMethod || 'GET').toUpperCase();
            var u = this._demoBannerUrl || '';
            if (m === 'POST' || m === 'PUT' || m === 'DELETE') {{
              if (!demoAllowPostThrough(u)) {{
                demoToastShow();
                var self = this;
                var fake = JSON.stringify({ ok: true, nuevos: 0, cancelados: 0, modificados: 0 });
                setTimeout(function() {{
                  self.readyState = 4;
                  self.status = 200;
                  self.responseText = fake;
                  if (self.onreadystatechange) self.onreadystatechange();
                  if (self.onload) self.onload();
                }}, 0);
                return;
              }}
            }}
          }} catch (e1) {{}}
          return prevSendBanner.apply(this, arguments);
        }};
      }}

      document.addEventListener('click', function(ev) {{
        var el = ev.target;
        if (!el || !el.closest) return;
        if (el.closest('.tab-btn')) return;
        if (el.closest('.mes-btn')) return;
        if (el.closest('.demo-banner-root')) return;
        if (el.closest('#demo-theme-toggle') || el.closest('.demo-toggle') || el.closest('.demo-lang-btn')) return;
        var btn = el.closest('button, input[type="submit"], input[type="button"], a.btn');
        if (!btn) return;
        var cls = btn.className || '';
        if (typeof cls !== 'string') cls = '';
        var hit = cls.indexOf('btn-danger') !== -1 || cls.indexOf('btn-warning') !== -1 || cls.indexOf('btn-primary') !== -1;
        if (!hit) return;
        ev.preventDefault();
        if (ev.stopImmediatePropagation) ev.stopImmediatePropagation();
        ev.stopPropagation();
        demoToastShow();
      }}, true);
    }}
  }} catch (e) {{
    console && console.warn && console.warn('demo banner init error', e);
  }}
}})();
</script>
"""


# JS puro: sin % / .format / f-string en el cuerpo. Los datos vienen de var DEMO_DATA (inyectado en demo_dashboard).
DEMO_DASHBOARD_INTERCEPT_JS = """
(function(){
  try {
    if (window.location.pathname !== '/demo/dashboard') { return; }
    if (typeof DEMO_DATA === 'undefined' || !DEMO_DATA) { return; }

    var demoResumen = {
      total_alumnos: DEMO_DATA.resumen.total_alumnos,
      clases_agendadas: DEMO_DATA.resumen.clases_agendadas,
      clases_canceladas: DEMO_DATA.resumen.clases_canceladas,
      pagos: DEMO_DATA.resumen.pagos
    };

    var demoClases = DEMO_DATA.clases;

    // Derivar datos ficticios adicionales a partir de las clases de demo
    var demoAlumnos = [];
    var alumnosIndex = {};
    var nextId = 1;
    demoClases.forEach(function(c) {
      var nombre = c.nombre;
      if (!alumnosIndex[nombre]) {
        var alumno = {
          id: nextId++,
          nombre: nombre,
          representante: '',
          pais: c.pais || 'AR',
          moneda: c.moneda || 'USD',
          metodo_pago: 'Wise',
          modalidad: 'Mensual',
          whatsapp: '',
          mail: '',
          lichess_usernames: '',
          clases_mes: 0,
          pago_este_mes: c.pago_id ? 1 : 0
        };
        alumnosIndex[nombre] = alumno;
        demoAlumnos.push(alumno);
      }
      alumnosIndex[nombre].clases_mes += 1;
      if (c.pago_id) {
        alumnosIndex[nombre].pago_este_mes = 1;
      }
    });

    var demoPagos = [];
    var pagoIdSeen = {};
    demoClases.forEach(function(c) {
      if (!c.pago_id || pagoIdSeen[c.pago_id]) { return; }
      pagoIdSeen[c.pago_id] = true;
      demoPagos.push({
        id: c.pago_id,
        fecha: c.fecha,
        monto: 50,
        moneda: c.moneda || 'USD',
        metodo: 'Wise',
        notas: 'Demo payment',
        nombre: c.nombre,
        representante: '',
        responsable: c.nombre,
        clases_resumen: '1 clase — dias ' + c.fecha.split('-')[2]
      });
    });

    var demoDeudores = demoAlumnos.filter(function(a) {
      return a.modalidad === 'Mensual' && !a.pago_este_mes;
    }).map(function(a) {
      return {
        nombre: a.nombre,
        representante: '-',
        clases: a.clases_mes,
        precio_unitario: 30,
        total: 30 * a.clases_mes,
        moneda: a.moneda
      };
    });

    var demoRecordatorios = demoAlumnos.slice(0, 3).map(function(a, idx) {
      return {
        id: idx + 1,
        alumno_id: a.id,
        alumno_nombre: a.nombre,
        minutos_antes: 60 * (idx + 1),
        alcance: 'todas',
        canal: 'mail',
        mail_destino: 'demo+' + (idx + 1) + '@example.com',
        creado: '2026-03-01 10:00:00'
      };
    });

    var demoEntrenamientoResumen = demoAlumnos.map(function(a, idx) {
      return {
        id: a.id,
        nombre: a.nombre,
        representante: '',
        ejercicios: 5 + idx,
        rating_prom: 10.0 * (idx + 1),
        ultima_fecha: '2026-03-0' + ((idx % 9) + 1)
      };
    });

    var demoUltimaSync = {
      ts: '01/03 09:00',
      meses: ['3/2026']
    };

    function makeJsonResponse(body) {
      var json = JSON.stringify(body);
      if (window.Response) {
        return Promise.resolve(new Response(json, {
          status: 200,
          headers: { 'Content-Type': 'application/json' }
        }));
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        json: function() { return Promise.resolve(body); },
        text: function() { return Promise.resolve(json); }
      });
    }

    var origFetch = window.fetch;
    if (origFetch) {
      window.fetch = function(input, init) {
        try {
          var url = (typeof input === 'string') ? input : (input && input.url) || '';
          console.log('[DEMO] intercepted fetch:', url);
          if (url && url.indexOf('/dashboard/api/resumen') !== -1) {
            return makeJsonResponse(demoResumen);
          }
          if (url && url.indexOf('/dashboard/api/clases') !== -1) {
            return makeJsonResponse(demoClases);
          }
          if (url && url.indexOf('/dashboard/api/chat') !== -1) {
            var l = 'es';
            try { l = localStorage.getItem('demo_lang') || 'es'; } catch(e) {}
            var respuesta = (l === 'en')
              ? 'DEMO BOT: explore the Dashboard tabs and then try Portal → Trainer.'
              : 'BOT DEMO: explorá las pestañas del Dashboard y después probá Portal → Trainer.';
            return makeJsonResponse({respuesta: respuesta});
          }
          if (url && url.indexOf('/dashboard/api/alumnos') !== -1) {
            return makeJsonResponse(demoAlumnos);
          }
          if (url && url.indexOf('/dashboard/api/pagos') !== -1) {
            return makeJsonResponse(demoPagos);
          }
          if (url && url.indexOf('/dashboard/api/deudores') !== -1) {
            return makeJsonResponse(demoDeudores);
          }
          if (url && url.indexOf('/dashboard/api/recordatorios_alumnos') !== -1) {
            return makeJsonResponse(demoRecordatorios);
          }
          if (url && url.indexOf('/dashboard/api/entrenamiento_resumen') !== -1) {
            return makeJsonResponse(demoEntrenamientoResumen);
          }
          if (url && url.indexOf('/dashboard/api/ultima_sync') !== -1) {
            return makeJsonResponse(demoUltimaSync);
          }
        } catch (e) {}
        return origFetch.apply(this, arguments);
      };
    }

    if (window.XMLHttpRequest) {
      var XHR = XMLHttpRequest;
      var origOpen = XHR.prototype.open;
      var origSend = XHR.prototype.send;
      XHR.prototype.open = function(method, url) {
        this._demoUrl = url;
        return origOpen.apply(this, arguments);
      };
      XHR.prototype.send = function(body) {
        try {
          var url = this._demoUrl || '';
          var self = this;
          console.log && console.log('[DEMO] intercepted XHR:', url);
          if (url && url.indexOf('/dashboard/api/resumen') !== -1) {
            var payload = JSON.stringify(demoResumen);
            setTimeout(function() {
              self.readyState = 4;
              self.status = 200;
              self.responseText = payload;
              if (self.onreadystatechange) self.onreadystatechange();
              if (self.onload) self.onload();
            }, 0);
            return;
          }
          if (url && url.indexOf('/dashboard/api/clases') !== -1) {
            var payload2 = JSON.stringify(demoClases);
            setTimeout(function() {
              self.readyState = 4;
              self.status = 200;
              self.responseText = payload2;
              if (self.onreadystatechange) self.onreadystatechange();
              if (self.onload) self.onload();
            }, 0);
            return;
          }
          if (url && url.indexOf('/dashboard/api/chat') !== -1) {
            var l2 = 'es';
            try { l2 = localStorage.getItem('demo_lang') || 'es'; } catch(e) {}
            var respuesta2 = (l2 === 'en')
              ? 'DEMO BOT: explore the Dashboard tabs and then try Portal → Trainer.'
              : 'BOT DEMO: explorá las pestañas del Dashboard y después probá Portal → Trainer.';
            var payloadChat = JSON.stringify({respuesta: respuesta2});
            setTimeout(function() {
              self.readyState = 4;
              self.status = 200;
              self.responseText = payloadChat;
              if (self.onreadystatechange) self.onreadystatechange();
              if (self.onload) self.onload();
            }, 0);
            return;
          }
          if (url && url.indexOf('/dashboard/api/alumnos') !== -1) {
            var p3 = JSON.stringify(demoAlumnos);
            setTimeout(function() {
              self.readyState = 4;
              self.status = 200;
              self.responseText = p3;
              if (self.onreadystatechange) self.onreadystatechange();
              if (self.onload) self.onload();
            }, 0);
            return;
          }
          if (url && url.indexOf('/dashboard/api/pagos') !== -1) {
            var p4 = JSON.stringify(demoPagos);
            setTimeout(function() {
              self.readyState = 4;
              self.status = 200;
              self.responseText = p4;
              if (self.onreadystatechange) self.onreadystatechange();
              if (self.onload) self.onload();
            }, 0);
            return;
          }
          if (url && url.indexOf('/dashboard/api/deudores') !== -1) {
            var p5 = JSON.stringify(demoDeudores);
            setTimeout(function() {
              self.readyState = 4;
              self.status = 200;
              self.responseText = p5;
              if (self.onreadystatechange) self.onreadystatechange();
              if (self.onload) self.onload();
            }, 0);
            return;
          }
          if (url && url.indexOf('/dashboard/api/recordatorios_alumnos') !== -1) {
            var p6 = JSON.stringify(demoRecordatorios);
            setTimeout(function() {
              self.readyState = 4;
              self.status = 200;
              self.responseText = p6;
              if (self.onreadystatechange) self.onreadystatechange();
              if (self.onload) self.onload();
            }, 0);
            return;
          }
          if (url && url.indexOf('/dashboard/api/entrenamiento_resumen') !== -1) {
            var p7 = JSON.stringify(demoEntrenamientoResumen);
            setTimeout(function() {
              self.readyState = 4;
              self.status = 200;
              self.responseText = p7;
              if (self.onreadystatechange) self.onreadystatechange();
              if (self.onload) self.onload();
            }, 0);
            return;
          }
          if (url && url.indexOf('/dashboard/api/ultima_sync') !== -1) {
            var p8 = JSON.stringify(demoUltimaSync);
            setTimeout(function() {
              self.readyState = 4;
              self.status = 200;
              self.responseText = p8;
              if (self.onreadystatechange) self.onreadystatechange();
              if (self.onload) self.onload();
            }, 0);
            return;
          }
        } catch (e) {}
        return origSend.apply(this, arguments);
      };
    }
  } catch (e) {
    console && console.warn && console.warn('demo intercept error', e);
  }
})();
"""


@demo_bp.route("/demo/login")
def demo_login():
    html = LOGIN_HTML.replace("ERRORBLOCK", "")
    html = html.replace('href="/portal/auth/lichess"', 'href="/demo/portal"')
    html = html.replace('href="/portal/auth/google"', 'href="/demo/portal"')
    html = html.replace(
        "<body>",
        '<body style="flex-direction:column;align-items:stretch;justify-content:flex-start;min-height:100vh">'
        + DEMO_BANNER_SNIPPET,
        1,
    )
    html = html.replace(
        '<div class="login-container">',
        '<div class="demo-login-body-wrap" style="flex:1;display:flex;align-items:center;justify-content:center;width:100%;box-sizing:border-box;padding:1.5rem">'
        '<div class="login-container">',
        1,
    )
    html = html.replace(
        "</div>\n</body>",
        "</div></div>\n" + DEMO_LOGIN_FORM_SCRIPT + "\n</body>",
        1,
    )
    html = aplicar_todas_las_rutas_demo(html)
    return Response(html, mimetype="text/html; charset=utf-8")


@demo_bp.route("/demo/dashboard")
def demo_dashboard():
    # Reusar el mismo HTML base que /dashboard (mismas clases, CSS y lógica de tema).
    hoy = date.today()
    meses = [
        "Enero",
        "Febrero",
        "Marzo",
        "Abril",
        "Mayo",
        "Junio",
        "Julio",
        "Agosto",
        "Septiembre",
        "Octubre",
        "Noviembre",
        "Diciembre",
    ]
    mes_options = "".join(
        f'<option value="{i+1}"{" selected" if i + 1 == hoy.month else ""}>{m}</option>'
        for i, m in enumerate(meses)
    )
    html = DASHBOARD_HTML.replace("{MES_OPTIONS}", mes_options).replace(
        "{AUTH_ERROR_BANNER}", ""
    )
    # Inyectar el banner de demo justo después de <body>, sin tocar el resto del layout.
    if "<body>" in html:
        html = html.replace("<body>", "<body>" + DEMO_BANNER_SNIPPET, 1)
    elif "<body " in html:
        html = html.replace("<body ", "<body " + DEMO_BANNER_SNIPPET, 1)

    # AÑADIR data-es/data-en a textos visibles del dashboard (sin tocar dashboard_routes.py)
    # Tabs
    html = html.replace(
        '<button class="tab-btn active" onclick="showTab(\'clases\',this)">Clases</button>',
        '<button class="tab-btn active" onclick="showTab(\'clases\',this)" data-es="Clases" data-en="Classes">Clases</button>',
    )
    html = html.replace(
        '<button class="tab-btn" onclick="showTab(\'cobros\',this)">Cobros</button>',
        '<button class="tab-btn" onclick="showTab(\'cobros\',this)" data-es="Cobros" data-en="Collections">Cobros</button>',
    )
    html = html.replace(
        '<button class="tab-btn" onclick="showTab(\'pagos\',this)">Pagos</button>',
        '<button class="tab-btn" onclick="showTab(\'pagos\',this)" data-es="Pagos" data-en="Payments">Pagos</button>',
    )
    html = html.replace(
        '<button class="tab-btn" onclick="showTab(\'deuda\',this)">Deuda</button>',
        '<button class="tab-btn" onclick="showTab(\'deuda\',this)" data-es="Deuda" data-en="Debt">Deuda</button>',
    )
    html = html.replace(
        '<button class="tab-btn" onclick="showTab(\'alumnos\',this)">Alumnos</button>',
        '<button class="tab-btn" onclick="showTab(\'alumnos\',this)" data-es="Alumnos" data-en="Students">Alumnos</button>',
    )
    html = html.replace(
        '<button class="tab-btn" onclick="showTab(\'portal\',this)">Portal</button>',
        '<button class="tab-btn" onclick="showTab(\'portal\',this)" data-es="Portal" data-en="Portal">Portal</button>',
    )
    html = html.replace(
        '<button class="tab-btn" onclick="showTab(\'entrenamiento\',this)">Entrenamiento</button>',
        '<button class="tab-btn" onclick="showTab(\'entrenamiento\',this)" data-es="Entrenamiento" data-en="Training">Entrenamiento</button>',
    )
    html = html.replace(
        '<button class="tab-btn" onclick="showTab(\'graficos\',this)">Graficos</button>',
        '<button class="tab-btn" onclick="showTab(\'graficos\',this)" data-es="Graficos" data-en="Charts">Graficos</button>',
    )

    # Métricas (labels)
    html = html.replace(
        '<div class="metric-label">Alumnos activos</div>',
        '<div class="metric-label" data-es="Alumnos activos" data-en="Active students">Alumnos activos</div>',
    )
    html = html.replace(
        '<div class="metric-label">Clases agendadas</div>',
        '<div class="metric-label" data-es="Clases agendadas" data-en="Scheduled lessons">Clases agendadas</div>',
    )
    html = html.replace(
        '<div class="metric-label">Canceladas</div>',
        '<div class="metric-label" data-es="Canceladas" data-en="Cancelled">Canceladas</div>',
    )
    html = html.replace(
        '<div class="metric-label">Cobrado USD</div>',
        '<div class="metric-label" data-es="Cobrado USD" data-en="Collected USD">Cobrado USD</div>',
    )
    html = html.replace(
        '<div class="metric-label">Cobrado GBP</div>',
        '<div class="metric-label" data-es="Cobrado GBP" data-en="Collected GBP">Cobrado GBP</div>',
    )
    html = html.replace(
        '<div class="metric-label">Cobrado ARS</div>',
        '<div class="metric-label" data-es="Cobrado ARS" data-en="Collected ARS">Cobrado ARS</div>',
    )

    # Botones
    html = html.replace(
        '<button class="btn" onclick="cargarTodo()">&#8635; Actualizar</button>',
        '<button class="btn" onclick="cargarTodo()">&#8635; <span data-es="Actualizar" data-en="Refresh">Actualizar</span></button>',
    )
    html = html.replace(
        '<button class="btn" id="btn-sync" onclick="sincronizarCalendario()">&#128197; Sincronizar</button>',
        '<button class="btn" id="btn-sync" onclick="sincronizarCalendario()">&#128197; <span data-es="Sincronizar" data-en="Sync">Sincronizar</span></button>',
    )
    html = html.replace(
        '<a href="/dashboard/logout"><button class="btn">Salir</button></a>',
        '<a href="/dashboard/logout"><button class="btn" data-es="Salir" data-en="Logout">Salir</button></a>',
    )

    # Filtros principales (opciones de la tabla de clases)
    html = html.replace(
        '<option value="">Todos los alumnos</option>',
        '<option value="" data-es="Todos los alumnos" data-en="All students">Todos los alumnos</option>',
    )
    html = html.replace(
        '<option value="">Todos los estados</option>',
        '<option value="" data-es="Todos los estados" data-en="All statuses">Todos los estados</option>',
    )
    html = html.replace(
        '<option value="agendada">Agendada</option>',
        '<option value="agendada" data-es="Agendada" data-en="Scheduled">Agendada</option>',
    )
    html = html.replace(
        '<option value="cancelada">Cancelada</option>',
        '<option value="cancelada" data-es="Cancelada" data-en="Cancelled">Cancelada</option>',
    )
    html = html.replace(
        '<option value="dada">Dada</option>',
        '<option value="dada" data-es="Dada" data-en="Given">Dada</option>',
    )
    html = html.replace(
        '<option value="">Pagas y no pagas</option>',
        '<option value="" data-es="Pagas y no pagas" data-en="Paid and unpaid">Pagas y no pagas</option>',
    )
    html = html.replace(
        '<option value="paga">&#10003; Pagas</option>',
        '<option value="paga" data-es="Pagas" data-en="Paid">&#10003; Pagas</option>',
    )
    html = html.replace(
        '<option value="impaga">&#9633; No pagas</option>',
        '<option value="impaga" data-es="No pagas" data-en="Unpaid">&#9633; No pagas</option>',
    )
    html = html.replace(
        '<option value="">Todo el mes</option>',
        '<option value="" data-es="Todo el mes" data-en="All month">Todo el mes</option>',
    )
    html = html.replace(
        '<option value="semana">Esta semana</option>',
        '<option value="semana" data-es="Esta semana" data-en="This week">Esta semana</option>',
    )

    # Encabezados de tabla (clases)
    html = html.replace(
        '<table><thead><tr><th>Fecha</th><th>Hora</th><th>Alumno</th><th>Estado</th><th>Pago</th><th>Pais</th></tr></thead>',
        '<table><thead><tr>'
        '<th data-es="Fecha" data-en="Date">Fecha</th>'
        '<th data-es="Hora" data-en="Time">Hora</th>'
        '<th data-es="Alumno" data-en="Student">Alumno</th>'
        '<th data-es="Estado" data-en="Status">Estado</th>'
        '<th data-es="Pago" data-en="Payment">Pago</th>'
        '<th data-es="Pais" data-en="Country">Pais</th>'
        '</tr></thead>',
    )

    # Datos ficticios para el intercept (sin % en el JS embebido: se serializan aquí)
    demo_total_alumnos = len(DEMO_ALUMNOS)
    demo_clases_agendadas = sum(a.get("clases_mes", 0) for a in DEMO_ALUMNOS)
    demo_clases_canceladas = 0
    demo_pagos_dict = {}
    for a in DEMO_ALUMNOS:
        moneda = a.get("moneda") or ""
        monto = a.get("pagado_mes", 0)
        demo_pagos_dict[moneda] = demo_pagos_dict.get(moneda, 0) + monto

    demo_data_dict = {
        "resumen": {
            "total_alumnos": demo_total_alumnos,
            "clases_agendadas": demo_clases_agendadas,
            "clases_canceladas": demo_clases_canceladas,
            "pagos": demo_pagos_dict,
        },
        "clases": DEMO_CLASES,
    }
    intercept_script = (
        "<script>"
        "var DEMO_DATA = "
        + json.dumps(demo_data_dict)
        + ";"
        + DEMO_DASHBOARD_INTERCEPT_JS
        + "</script>"
    )
    html = html.replace("<head>", "<head>" + intercept_script, 1)

    html = aplicar_todas_las_rutas_demo(html)
    return Response(html, mimetype="text/html; charset=utf-8")


@demo_bp.route("/demo/portal")
def demo_portal():
    # Reusar el mismo HTML base del portal real, con contenido simulado.
    resumen = DEMO_PORTAL_RESUMEN
    nombre = resumen[0]["nombre"]
    contenido = PORTAL_HOME_CONTENT.replace("{NOMBRE}", nombre)

    # Añadir traducciones a labels que el portal construye desde JS (sin tocar portal_routes.py)
    contenido = contenido.replace(
        "var l1 = document.createElement('div'); l1.className = 'metric-label'; l1.textContent = 'Próxima clase';",
        "var l1 = document.createElement('div'); l1.className = 'metric-label'; l1.setAttribute('data-es','Próxima clase'); l1.setAttribute('data-en','Next lesson'); l1.textContent = 'Próxima clase';",
    )
    contenido = contenido.replace(
        "var l2 = document.createElement('div'); l2.className = 'metric-label'; l2.textContent = 'Clases este mes';",
        "var l2 = document.createElement('div'); l2.className = 'metric-label'; l2.setAttribute('data-es','Clases este mes'); l2.setAttribute('data-en','This month lessons'); l2.textContent = 'Clases este mes';",
    )
    contenido = contenido.replace(
        "var l3 = document.createElement('div'); l3.className = 'metric-label'; l3.textContent = 'Dadas';",
        "var l3 = document.createElement('div'); l3.className = 'metric-label'; l3.setAttribute('data-es','Dadas'); l3.setAttribute('data-en','Given'); l3.textContent = 'Dadas';",
    )
    contenido = contenido.replace(
        "var l5 = document.createElement('div'); l5.className = 'metric-label'; l5.textContent = 'Clases restantes';",
        "var l5 = document.createElement('div'); l5.className = 'metric-label'; l5.setAttribute('data-es','Clases restantes'); l5.setAttribute('data-en','Remaining classes'); l5.textContent = 'Clases restantes';",
    )
    contenido = contenido.replace(
        "var l6 = document.createElement('div'); l6.className = 'metric-label'; l6.textContent = 'Ejercicios trainer';",
        "var l6 = document.createElement('div'); l6.className = 'metric-label'; l6.setAttribute('data-es','Ejercicios trainer'); l6.setAttribute('data-en','Trainer exercises'); l6.textContent = 'Ejercicios trainer';",
    )
    contenido = contenido.replace(
        "v1.textContent = 'Sin clases agendadas';",
        "v1.setAttribute('data-es','Sin clases agendadas'); v1.setAttribute('data-en','No lessons scheduled'); v1.textContent = 'Sin clases agendadas';",
    )

    # Botones laterales (entrenamiento)
    contenido = contenido.replace(
        "<a href=\"/trainer\" class=\"btn\" style=\"width:100%;justify-content:center\">Entrar al entrenamiento</a>",
        "<a href=\"/trainer\" class=\"btn\" style=\"width:100%;justify-content:center\" data-es=\"Entrar al entrenamiento\" data-en=\"Enter training\">Entrar al entrenamiento</a>",
    )
    contenido = contenido.replace(
        "<a href=\"/portal/entrenamiento\" class=\"btn\" style=\"width:100%;justify-content:center\">Ver mi progreso</a>",
        "<a href=\"/portal/entrenamiento\" class=\"btn\" style=\"width:100%;justify-content:center\" data-es=\"Ver mi progreso\" data-en=\"View progress\">Ver mi progreso</a>",
    )

    contenido = contenido.replace("{RESUMEN_JSON}", json.dumps(resumen))
    contenido = contenido.replace("PORTAL_NOMBRE_JSON", json.dumps(nombre))
    html = PORTAL_HTML.replace("{PORTAL_CONTENT}", contenido)
    # Inyectar el banner demo justo después de <body>.
    if "<body>" in html:
        html = html.replace("<body>", "<body>" + DEMO_BANNER_SNIPPET, 1)
    elif "<body " in html:
        html = html.replace("<body ", "<body " + DEMO_BANNER_SNIPPET, 1)
    # Añadir data-es/data-en a textos clave que no lo tienen en el HTML original
    html = html.replace(
        '<h3 style="font-size:0.95rem;margin-bottom:0.5rem">Recordatorios</h3>',
        '<h3 style="font-size:0.95rem;margin-bottom:0.5rem" data-es="Recordatorios" data-en="Reminders">Recordatorios</h3>',
    )
    html = html.replace(
        '<h3 style="font-size:0.95rem;margin-bottom:0.5rem">Entrenamiento de patrones</h3>',
        '<h3 style="font-size:0.95rem;margin-bottom:0.5rem" data-es="Entrenamiento de patrones" data-en="Pattern training">Entrenamiento de patrones</h3>',
    )
    html = html.replace(
        'class="btn" id="home-logout" style="display:inline-block;margin-top:1rem">Salir</a>',
        'class="btn" id="home-logout" style="display:inline-block;margin-top:1rem" data-es="Salir" data-en="Logout">Salir</a>',
    )
    html = aplicar_todas_las_rutas_demo(html)
    return Response(html, mimetype="text/html; charset=utf-8")


@demo_bp.route("/demo/trainer")
def demo_trainer():
    # Reutilizamos el mismo HTML del trainer real, sólo agregando el banner DEMO.
    html = render_template("trainer.html")
    if "<body" in html:
        # Insertar clase de tema y banner + pequeño script para ajustar el botón de salida
        if "<body>" in html:
            html = html.replace("<body>", '<body class="theme-dark">', 1)
        elif "<body " in html:
            html = html.replace("<body ", '<body class="theme-dark" ', 1)
        injection = DEMO_BANNER_SNIPPET + """
<script>
(function(){
  try {
    // Cambiar el botón de salida sólo en modo demo
    var btn = document.getElementById('btn-exit-portal');
    if (btn) {
      btn.textContent = '← Back to demo';
      btn.onclick = function(ev){ ev.preventDefault(); window.location.href = '/demo/dashboard'; };
    }
  } catch (e) {
    console && console.warn && console.warn('demo trainer exit override failed', e);
  }
})();
</script>
"""
        html = html.replace("</body>", injection + "</body>", 1)
    html = aplicar_todas_las_rutas_demo(html)
    return Response(html, mimetype="text/html; charset=utf-8")

