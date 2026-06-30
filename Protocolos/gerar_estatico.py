import json, datetime, re, os

with open('dados_raw.json', encoding='utf-8') as f:
    payload = json.load(f)

data = payload['data']
data_js = json.dumps(data, ensure_ascii=False, separators=(',', ':'))

with open('dashboard.html', encoding='utf-8') as f:
    html = f.read()

today = datetime.date.today().strftime('%d/%m/%Y')
total = len(data)

# 1. Substituir banner da API
old_banner = '''<div class="api-banner" id="apiBanner">
  <span>🔌 API:</span>
  <strong id="apiUrlDisplay">—</strong>
  <span id="apiRecordInfo" style="color:var(--muted)"></span>
  <div class="api-status">
    <span class="status-dot-load" id="statusDot"></span>
    <span id="statusText" style="font-size:10px">conectando...</span>
  </div>
  <span class="refresh-time" id="refreshTime"></span>
  <button class="btn-refresh" id="btnRefresh" onclick="refreshData()">
    <svg id="refreshIcon" width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M1 4v6h6"/><path d="M23 20v-6h-6"/><path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 0 1 3.51 15"/></svg>
    Atualizar
  </button>
  <button class="btn-refresh" id="btnCfgApi" onclick="openApiConfig()" style="border-color:rgba(245,158,11,.3);color:var(--accent3)">
    ⚙️ Config
  </button>
  <button class="btn-refresh" id="btnVerSql" onclick="openSqlModal()" style="border-color:rgba(16,185,129,.3);color:var(--accent4)" disabled>
    🗄️ Ver SQL
  </button>
</div>'''

new_banner = f'''<div class="api-banner" id="apiBanner">
  <span>📦 Dados:</span>
  <strong id="apiUrlDisplay">Estático · Exportado em {today}</strong>
  <span id="apiRecordInfo" style="color:var(--muted)">{total:,} registros</span>
  <div class="api-status">
    <span class="status-dot-live" id="statusDot"></span>
    <span id="statusText" style="font-size:10px">offline</span>
  </div>
  <span class="refresh-time" id="refreshTime"></span>
  <button class="btn-refresh" id="btnVerSql" onclick="openSqlModal()" style="border-color:rgba(16,185,129,.3);color:var(--accent4)">
    🗄️ Ver SQL
  </button>
</div>'''

html = html.replace(old_banner, new_banner)

# 2. Substituir topo do script
old_top = """let API_CFG = {
  baseUrl:     'http://localhost:3001',
  path:        '/api/protocolos',
  autoRefresh: 0,      // minutos (0 = desativado)
  mode:        'api', // 'api' ou 'demo'
};
let autoRefreshTimer = null;
let lastRefresh = null;"""

new_top = f"const __STATIC_DATA__ = {data_js};\nlet lastRefresh = new Date();"

html = html.replace(old_top, new_top)

# 3. Remover buildDemoData
html = re.sub(
    r'// Gera dados demo representativos\nfunction buildDemoData\(\) \{.*?\n\}\n\n',
    '',
    html,
    flags=re.DOTALL
)

# 4. Substituir loadData/refreshData/scheduleAutoRefresh/updateRefreshTime
old_load_block = html[html.index('// ═══════════════════════════════════════════════════════\n// CARREGAMENTO DE DADOS'):
                      html.index('// ═══════════════════════════════════════════════════════\n// STATUS / LOADING / ERROR')]

new_load_block = f"""// ═══════════════════════════════════════════════════════
// CARREGAMENTO DE DADOS (MODO ESTÁTICO)
// ═══════════════════════════════════════════════════════
function loadData() {{
  showLoading('Carregando dados...', 'aguarde');
  setTimeout(() => {{
    const rows = __STATIC_DATA__;
    RAW_DATA     = rows;
    filteredData = rows;
    updateRefreshTime();
    FILTER_KEYS.forEach(k => {{
      FILTER_OPTIONS[k] = [...new Set(rows.map(r=>r[k]).filter(Boolean))].sort();
    }});
    FILTER_CFG.forEach(({{key}}) => {{
      gCnt[key] = {{}};
      rows.forEach(r => {{ if(r[key]) gCnt[key][r[key]] = (gCnt[key][r[key]] || 0) + 1; }});
    }});
    buildFilterBar();
    initDefaultCharts();
    updateTags(); updateKPIs(); redrawAllCharts();
    const mn = rows.length ? rows.map(r=>r.INICIADOEM_STR).sort()[0] : '—';
    const mx = rows.length ? rows.map(r=>r.INICIADOEM_STR).sort().reverse()[0] : '—';
    document.getElementById('footerInfo').textContent =
      `Dashboard · Dados Estáticos · ${{fmtNum(rows.length)}} registros · ${{fmtMonth(mn)}} – ${{fmtMonth(mx)}}`;
    document.getElementById('apiRecordInfo').textContent = fmtNum(rows.length)+' registros';
    hideLoading();
  }}, 100);
}}

function updateRefreshTime() {{
  const el = document.getElementById('refreshTime');
  if(el) el.textContent = 'Exportado em {today}';
}}

"""

html = html.replace(old_load_block, new_load_block)

# 5. Remover switchToDemo e openApiConfig
html = re.sub(r'function switchToDemo\(\) \{.*?\}\n', '', html, flags=re.DOTALL)

old_cfg = """function openApiConfig() {
  document.getElementById('cfgApiUrl').value      = API_CFG.baseUrl;
  document.getElementById('cfgApiPath').value     = API_CFG.path;
  document.getElementById('cfgAutoRefresh').value = API_CFG.autoRefresh;
  document.getElementById('cfgDataMode').value    = API_CFG.mode;
  document.getElementById('apiConfigModal').classList.remove('hidden');
}
document.getElementById('cfgCancelBtn').addEventListener('click', ()=>document.getElementById('apiConfigModal').classList.add('hidden'));
document.getElementById('cfgSaveBtn').addEventListener('click', ()=>{
  API_CFG.baseUrl     = document.getElementById('cfgApiUrl').value.replace(/\\/$/,'');
  API_CFG.path        = document.getElementById('cfgApiPath').value;
  API_CFG.autoRefresh = parseInt(document.getElementById('cfgAutoRefresh').value)||0;
  API_CFG.mode        = document.getElementById('cfgDataMode').value;
  document.getElementById('apiConfigModal').classList.add('hidden');
  // Reset filtros e gráficos
  FILTER_CFG.forEach(({key})=>{ sel[key].clear(); });
  document.getElementById('chartsGrid').innerHTML='';
  chartRegistry=[];
  loadData();
});"""

html = html.replace(old_cfg, '')

# 6. Remover showError
html = re.sub(r'function showError\(msg\) \{.*?\n\}\n', '', html, flags=re.DOTALL)

# 7. Remover modal apiConfigModal do HTML
html = re.sub(
    r'<!-- MODAL: Configuração da API -->.*?</div>\n</div>\n',
    '',
    html,
    flags=re.DOTALL
)

with open('dashboard_estatico.html', 'w', encoding='utf-8') as f:
    f.write(html)

size_mb = os.path.getsize('dashboard_estatico.html') / 1024 / 1024
print(f'OK! Tamanho: {size_mb:.1f} MB — dashboard_estatico.html')
