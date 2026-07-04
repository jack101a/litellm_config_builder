const state = {
  providers: [],
  selectedProviderIds: new Set(['nvidia']),
  // Map of provider_id -> { count: number, envPrefix: string, envNames: list[string], pastedKeys: list[string] }
  providerPlans: new Map([
    ['nvidia', { count: 5, envPrefix: 'NVIDIA_KEY', envNames: ['NVIDIA_KEY_1', 'NVIDIA_KEY_2', 'NVIDIA_KEY_3', 'NVIDIA_KEY_4', 'NVIDIA_KEY_5'], pastedKeys: [] }]
  ]),
  providerRouting: new Map(),
  models: [],
  selectedModels: new Map(), // key: "provider_id:model_id"
  outputFiles: {},
  currentTab: 'config.yaml',
  visibleModelIds: [],
  currentSection: 'dashboard'
};

const $ = (id) => document.getElementById(id);
const pretty = (obj) => JSON.stringify(obj, null, 2);

// Step Navigation
const stepsOrder = ['dashboard', 'providers', 'keys', 'models', 'routing', 'tests', 'output'];

function showSection(id) {
  if (!stepsOrder.includes(id) && id !== 'import') return;
  state.currentSection = id;
  
  document.querySelectorAll('.section').forEach(el => el.classList.remove('active'));
  
  const targetSec = $(id);
  if (targetSec) targetSec.classList.add('active');
  
  const currentIndex = stepsOrder.indexOf(id);
  document.querySelectorAll('.step-item').forEach((el, index) => {
    el.classList.remove('active', 'completed');
    if (el.dataset.target === id || el.dataset.step === id) {
      el.classList.add('active');
    } else if (currentIndex > -1 && index < currentIndex) {
      el.classList.add('completed');
    }
  });

  // Trigger page-specific renders
  if (id === 'keys') {
    renderProviderPlanners();
  } else if (id === 'models') {
    saveAllPlans();
    renderModelFetchers();
    renderModels();
  } else if (id === 'tests') {
    populateTestSelectors();
  }
}

document.querySelectorAll('.step-item').forEach(btn => {
  btn.addEventListener('click', () => showSection(btn.dataset.target || btn.dataset.step || btn.dataset.section));
});

// Wizard Back/Continue buttons
document.querySelectorAll('.wizard-next').forEach(btn => {
  btn.addEventListener('click', () => {
    const next = btn.dataset.next;
    showSection(next);
  });
});

document.querySelectorAll('.wizard-prev').forEach(btn => {
  btn.addEventListener('click', () => {
    const prev = btn.dataset.prev;
    showSection(prev);
  });
});

// Move wizard buttons to top of panels for sticky scrolling
document.querySelectorAll('.panel.section').forEach(sec => {
  const btnRow = sec.querySelector('.button-row.justify-between');
  const panelHead = sec.querySelector('.panel-head');
  if (btnRow && panelHead) {
    btnRow.classList.add('sticky-action-bar');
    panelHead.insertAdjacentElement('afterend', btnRow);
  }
});

async function api(path, body = null) {
  const opts = body ? {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)} : {};
  const res = await fetch(path, opts);
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return await res.json();
}

function updateDashboard() {
  $('selectedProviderCount').textContent = state.selectedProviderIds.size;
  $('envCount').textContent = Array.from(state.providerPlans.values()).reduce((sum, p) => sum + p.count, 0);
  $('loadedModelCount').textContent = state.models.length;
  $('selectedModelsSummary').textContent = state.selectedModels.size;
  renderModelFetchers();
  renderProviderRouting();
}

async function loadProviders() {
  try {
    const data = await api('/api/providers');
    state.providers = data.providers;
    renderProviders();
    updateDashboard();
  } catch (err) {
    console.error('Failed to load providers:', err);
  }
}

function providerInfo(id) { return state.providers.find(p => p.provider_id === id); }

function renderProviders() {
  const grid = $('providerGrid');
  if (!grid) return;
  grid.innerHTML = '';
  state.providers.forEach(p => {
    const selected = state.selectedProviderIds.has(p.provider_id);
    const card = document.createElement('div');
    card.className = `provider-card ${selected ? 'selected' : ''}`;
    const notes = (p.capability_notes || []).map(n => `<li>${escapeHtml(n)}</li>`).join('');
    card.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
        <h3 style="font-size: 16px; font-weight: 600; margin: 0; color: var(--text);">${escapeHtml(p.display_name)}</h3>
        <div style="width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; background: ${selected ? 'var(--brand)' : '#f1f5f9'}; color: ${selected ? 'white' : 'var(--muted)'}; font-weight: bold; font-size: 14px;">${selected ? '✓' : '+'}</div>
      </div>
      <p style="font-size: 13px; color: var(--muted); margin: 0 0 12px 0; line-height: 1.4;">${escapeHtml(p.notes || '')}</p>
      
      <details class="provider-specs" style="margin-top: auto;" onclick="event.stopPropagation()">
        <summary style="font-size: 12px; color: var(--brand); cursor: pointer; list-style: none; user-select: none;">View API specs</summary>
        <div class="meta-grid" style="margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--line);">
          <div class="meta-row"><span style="flex-shrink: 0; margin-right: 8px;">Model fetch</span><strong style="text-align: right;">${escapeHtml(p.model_fetch)}</strong></div>
          <div class="meta-row"><span style="flex-shrink: 0; margin-right: 8px;">Rich metadata</span><strong style="text-align: right;">${escapeHtml(p.rich_metadata)}</strong></div>
          <div class="meta-row"><span style="flex-shrink: 0; margin-right: 8px;">Thinking</span><strong style="text-align: right;">${escapeHtml(p.thinking_mode)}</strong></div>
          <div class="meta-row"><span style="flex-shrink: 0; margin-right: 8px;">Wildcard</span><strong style="text-align: right;">${escapeHtml(p.wildcard)}</strong></div>
        </div>
        ${notes ? `<ul class="tiny-list" style="margin-top: 12px;">${notes}</ul>` : ''}
      </details>`;
    card.addEventListener('click', () => {
      if (state.selectedProviderIds.has(p.provider_id)) {
        state.selectedProviderIds.delete(p.provider_id);
      } else {
        state.selectedProviderIds.add(p.provider_id);
      }
      if (!state.selectedProviderIds.size) {
        state.selectedProviderIds.add(p.provider_id);
      }
      renderProviders();
      updateDashboard();
    });
    grid.appendChild(card);
  });
}

// Step 2: Dynamic Provider Planners
function renderProviderPlanners() {
  const container = $('providerPlannersContainer');
  if (!container) return;
  container.innerHTML = '';

  state.selectedProviderIds.forEach(providerId => {
    const pInfo = providerInfo(providerId);
    if (!pInfo) return;

    // Initialize plan if not present
    if (!state.providerPlans.has(providerId)) {
      const count = providerId === 'nvidia' ? 5 : 1;
      const prefix = pInfo.default_env_prefix || 'API_KEY';
      state.providerPlans.set(providerId, {
        count: count,
        envPrefix: prefix,
        envNames: generateEnvNamesList(prefix, count),
        pastedKeys: []
      });
    }

    const plan = state.providerPlans.get(providerId);

    const plannerBlock = document.createElement('div');
    plannerBlock.style.padding = '24px';
    plannerBlock.style.marginBottom = '28px';
    plannerBlock.style.background = 'linear-gradient(145deg, #ffffff, #f8fafc)';
    plannerBlock.style.boxShadow = 'var(--shadow-md)';
    plannerBlock.style.borderRadius = '16px';
    plannerBlock.style.position = 'relative';
    plannerBlock.style.overflow = 'hidden';
    plannerBlock.style.border = '1px solid var(--line)';
    plannerBlock.style.transition = 'all 0.3s cubic-bezier(0.16, 1, 0.3, 1)';
    plannerBlock.style.transform = 'translateY(0)';

    // Glow top border
    const accent = document.createElement('div');
    accent.style.position = 'absolute';
    accent.style.top = '0';
    accent.style.left = '0';
    accent.style.width = '100%';
    accent.style.height = '4px';
    accent.style.background = 'linear-gradient(90deg, var(--brand), #8b5cf6, #ec4899)';
    plannerBlock.appendChild(accent);

    const innerDiv = document.createElement('div');
    innerDiv.innerHTML = `
      <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 28px; margin-top: 6px;">
        <h3 style="margin: 0; font-size: 20px; color: var(--text); display: flex; align-items: center; gap: 10px;">
          <span style="display: inline-block; width: 10px; height: 10px; border-radius: 50%; background: var(--ok); box-shadow: 0 0 10px var(--ok);"></span>
          ${escapeHtml(pInfo.display_name)} Key Planner
        </h3>
        <span style="font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--brand); background: var(--brand-soft); padding: 4px 10px; border-radius: 99px; border: 1px solid rgba(79, 70, 229, 0.1);">Provider Auth</span>
      </div>

      <div class="form-grid" style="margin-bottom: 28px; gap: 24px;">
        <div style="display: flex; flex-direction: column; gap: 8px; position: relative;">
          <label style="color: var(--muted); font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em;">Number of keys</label>
          <input type="number" class="key-count-input" data-provider="${providerId}" min="0" max="200" value="${plan.count}" style="font-size: 15px; padding: 14px 16px; border-radius: 12px; background: rgba(255,255,255,0.9); backdrop-filter: blur(8px); box-shadow: inset 0 2px 4px rgba(0,0,0,0.03); transition: all 0.2s;" />
        </div>
        <div style="display: flex; flex-direction: column; gap: 8px; position: relative;">
          <label style="color: var(--muted); font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em;">Environment Prefix</label>
          <input class="env-prefix-input" data-provider="${providerId}" value="${escapeAttr(plan.envPrefix)}" style="font-size: 15px; padding: 14px 16px; border-radius: 12px; background: rgba(255,255,255,0.9); backdrop-filter: blur(8px); box-shadow: inset 0 2px 4px rgba(0,0,0,0.03); transition: all 0.2s;" />
        </div>
      </div>
      
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 24px; margin-top: 16px;">
        <div style="background: var(--bg); border: 1px solid var(--line); border-radius: 12px; padding: 20px; position: relative;">
          <h4 style="margin: 0 0 16px 0; font-size: 13px; color: var(--text); display: flex; align-items: center; gap: 8px;">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--brand)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
            Generated Variables
          </h4>
          <pre class="code small generated-envs" id="envs-${providerId}" style="margin: 0; padding: 14px; min-height: 120px; max-height: 160px; overflow-y: auto; background: #0f172a; color: #a5b4fc; border-radius: 8px; box-shadow: inset 0 2px 10px rgba(0,0,0,0.4); font-size: 13px; line-height: 1.6;">${plan.envNames.join('\n')}</pre>
        </div>
        <div style="background: var(--bg); border: 1px solid var(--line); border-radius: 12px; padding: 20px; display: flex; flex-direction: column;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
            <h4 style="margin: 0; font-size: 13px; color: var(--text); display: flex; align-items: center; gap: 8px;">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg>
              Live Testing Keys
            </h4>
            <select class="key-paste-mode" style="width: auto; padding: 4px 8px; font-size: 11px; border-radius: 6px; border: 1px solid var(--line); background: white; cursor: pointer;">
              <option value="bulk">Bulk Paste</option>
              <option value="individual">Individual Fields</option>
            </select>
          </div>
          <div class="paste-bulk-container" style="flex: 1; display: flex; flex-direction: column;">
            <textarea class="textarea pasted-keys-input" data-provider="${providerId}" rows="5" placeholder="Paste real keys here for live smoke tests (one per line). These are NEVER saved to file." style="margin: 0; width: 100%; flex: 1; font-size: 13px; padding: 14px; border-radius: 8px; border: 1px solid var(--line); box-shadow: inset 0 2px 4px rgba(0,0,0,0.02); resize: vertical; min-height: 120px;">${plan.pastedKeys.join('\n')}</textarea>
          </div>
          <div class="paste-individual-container" style="display: none; flex-direction: column; gap: 8px; flex: 1; overflow-y: auto; max-height: 160px; padding-right: 4px;">
          </div>
        </div>
      </div>
    `;
    plannerBlock.appendChild(innerDiv);

    plannerBlock.addEventListener('mouseenter', () => {
      plannerBlock.style.transform = 'translateY(-4px)';
      plannerBlock.style.boxShadow = 'var(--shadow-lg)';
    });
    plannerBlock.addEventListener('mouseleave', () => {
      plannerBlock.style.transform = 'translateY(0)';
      plannerBlock.style.boxShadow = 'var(--shadow-md)';
    });

    const countInput = plannerBlock.querySelector('.key-count-input');
    const prefixInput = plannerBlock.querySelector('.env-prefix-input');
    const pastedInput = plannerBlock.querySelector('.pasted-keys-input');
    const envsPre = plannerBlock.querySelector('.generated-envs');
    const pasteModeSelect = plannerBlock.querySelector('.key-paste-mode');
    const bulkContainer = plannerBlock.querySelector('.paste-bulk-container');
    const individualContainer = plannerBlock.querySelector('.paste-individual-container');

    const renderIndividualFields = (names, keys) => {
      individualContainer.innerHTML = '';
      if (names.length === 0) {
        individualContainer.innerHTML = '<span style="font-size:12px; color:var(--muted);">No keys planned.</span>';
        return;
      }
      names.forEach((name, i) => {
        const val = keys[i] || '';
        individualContainer.innerHTML += \`
          <div style="display: flex; align-items: center; gap: 8px;">
            <span style="font-size: 11px; font-weight: 600; font-family: monospace; color: var(--muted); width: 110px; overflow: hidden; text-overflow: ellipsis;" title="\${name}">\${name}</span>
            <input type="text" class="individual-key-input" data-index="\${i}" value="\${escapeAttr(val)}" placeholder="Paste key..." style="flex: 1; padding: 8px 12px; font-size: 12px; border-radius: 6px; border: 1px solid var(--line); background: #fff;" />
          </div>
        \`;
      });
      individualContainer.querySelectorAll('.individual-key-input').forEach(input => {
        input.addEventListener('input', updatePlanFromIndividual);
      });
    };

    const updatePlanFromIndividual = () => {
      const inputs = individualContainer.querySelectorAll('.individual-key-input');
      const keys = Array.from(inputs).map(i => i.value.trim());
      pastedInput.value = keys.filter(Boolean).join('\\n');
      
      const count = Math.max(0, parseInt(countInput.value) || 0);
      const prefix = prefixInput.value.trim().toUpperCase().replace(/[^A-Z0-9_]+/g, '_') || 'API_KEY';
      const names = generateEnvNamesList(prefix, count);
      
      state.providerPlans.set(providerId, {
        count: count,
        envPrefix: prefix,
        envNames: names,
        pastedKeys: keys.filter(Boolean)
      });
    };

    const updatePlan = () => {
      const count = Math.max(0, parseInt(countInput.value) || 0);
      const prefix = prefixInput.value.trim().toUpperCase().replace(/[^A-Z0-9_]+/g, '_') || 'API_KEY';
      const names = generateEnvNamesList(prefix, count);
      
      if (count === 0) {
        envsPre.textContent = '(0 keys planned. Safe for local keyless endpoints)';
      } else {
        envsPre.textContent = names.join('\\n');
      }
      
      const keys = pastedInput.value.split('\\n').map(x => x.trim()).filter(Boolean);
      
      state.providerPlans.set(providerId, {
        count: count,
        envPrefix: prefix,
        envNames: names,
        pastedKeys: keys
      });
      
      if (pasteModeSelect.value === 'individual') {
        renderIndividualFields(names, keys);
      }
      updateDashboard();
    };

    pasteModeSelect.addEventListener('change', (e) => {
      if (e.target.value === 'bulk') {
        bulkContainer.style.display = 'flex';
        individualContainer.style.display = 'none';
      } else {
        bulkContainer.style.display = 'none';
        individualContainer.style.display = 'flex';
        
        const count = Math.max(0, parseInt(countInput.value) || 0);
        const prefix = prefixInput.value.trim().toUpperCase().replace(/[^A-Z0-9_]+/g, '_') || 'API_KEY';
        const names = generateEnvNamesList(prefix, count);
        const keys = pastedInput.value.split('\\n').map(x => x.trim()).filter(Boolean);
        renderIndividualFields(names, keys);
      }
    });

    countInput.addEventListener('input', updatePlan);
    prefixInput.addEventListener('input', updatePlan);
    pastedInput.addEventListener('input', updatePlan);

    container.appendChild(plannerBlock);
  });
}

function generateEnvNamesList(prefix, count) {
  if (count <= 1) return [prefix];
  const list = [];
  for (let i = 1; i <= count; i++) {
    list.push(`${prefix}_${i}`);
  }
  return list;
}

function saveAllPlans() {
  state.selectedProviderIds.forEach(providerId => {
    const countInput = document.querySelector(`.key-count-input[data-provider="${providerId}"]`);
    const prefixInput = document.querySelector(`.env-prefix-input[data-provider="${providerId}"]`);
    const pastedInput = document.querySelector(`.pasted-keys-input[data-provider="${providerId}"]`);
    
    if (countInput && prefixInput && pastedInput) {
      const count = Math.max(0, parseInt(countInput.value) || 0);
      const prefix = prefixInput.value.trim().toUpperCase().replace(/[^A-Z0-9_]+/g, '_') || 'API_KEY';
      const names = generateEnvNamesList(prefix, count);
      
      state.providerPlans.set(providerId, {
        count: count,
        envPrefix: prefix,
        envNames: names,
        pastedKeys: pastedInput.value.split('\n').map(x => x.trim()).filter(Boolean)
      });
    }
  });

  // Re-sync all checked models with provider-specific key lists
  for (const [key, value] of state.selectedModels.entries()) {
    const plan = state.providerPlans.get(value.provider_id);
    const envs = plan && plan.envNames.length ? plan.envNames : [`${value.provider_id.toUpperCase()}_API_KEY`];
    state.selectedModels.set(key, { ...value, env_names: envs });
  }
  updateDashboard();
}

// Step 3: Dynamic Model Fetchers per Provider
function renderProviderRouting() {
  const container = $('providerRoutingContainer');
  if (!container) return;
  container.innerHTML = '';
  
  if (state.selectedProviderIds.size === 0) {
    container.innerHTML = '<span style="color: var(--muted); font-size: 13px;">Select providers in Step 1 to configure rate limits.</span>';
    return;
  }
  
  state.selectedProviderIds.forEach(providerId => {
    const pInfo = providerInfo(providerId);
    if (!pInfo) return;
    
    const limits = state.providerRouting.get(providerId) || {rpm: null, tpm: null};
    
    const div = document.createElement('div');
    div.style.border = '1px solid var(--line)';
    div.style.padding = '12px';
    div.style.borderRadius = '8px';
    div.style.display = 'flex';
    div.style.flexDirection = 'column';
    div.style.gap = '8px';
    div.style.background = '#fafafa';
    
    div.innerHTML = `
      <div style="font-weight: 500; font-size: 13px; border-bottom: 1px solid var(--line); padding-bottom: 8px; margin-bottom: 4px; display: flex; align-items: center; gap: 8px;">
        <img src="${pInfo.logo_url}" style="width:16px;height:16px;border-radius:4px;">
        ${escapeHtml(pInfo.display_name || providerId)}
      </div>
      <label style="margin:0;">RPM per key
        <input type="number" class="prov-rpm" value="${limits.rpm || ''}" placeholder="Optional (e.g. 15)" />
      </label>
      <label style="margin:0;">TPM per key
        <input type="number" class="prov-tpm" value="${limits.tpm || ''}" placeholder="Optional" />
      </label>
    `;
    
    div.querySelector('.prov-rpm').addEventListener('change', (e) => {
      const v = numberOrNull(e.target.value);
      state.providerRouting.set(providerId, {...(state.providerRouting.get(providerId)||{}), rpm: v});
    });
    
    div.querySelector('.prov-tpm').addEventListener('change', (e) => {
      const v = numberOrNull(e.target.value);
      state.providerRouting.set(providerId, {...(state.providerRouting.get(providerId)||{}), tpm: v});
    });
    
    container.appendChild(div);
  });
}

function renderModelFetchers() {
  const container = $('providerFetchersContainer');
  if (!container) return;
  container.innerHTML = '';

  state.selectedProviderIds.forEach(providerId => {
    const pInfo = providerInfo(providerId);
    if (!pInfo) return;

    const block = document.createElement('div');
    block.className = 'panel';
    block.style.padding = '18px';
    block.style.border = '1px solid var(--line)';
    block.style.borderRadius = '14px';
    block.style.marginBottom = '16px';
    block.style.background = '#ffffff';

    const isNvidia = providerId === 'nvidia';

    block.innerHTML = `
      <div class="panel-head" style="margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center;">
        <h3 style="font-size: 16px; margin: 0;">${escapeHtml(pInfo.display_name)}</h3>
        <span class="status-badge" id="badge-${providerId}" style="font-size: 12px; font-weight: bold; background: #f2f4f7; padding: 4px 8px; border-radius: 999px;">Not fetched</span>
      </div>
      <div class="form-grid">
        <label>Base URL override
          <input class="api-base-override" data-provider="${providerId}" placeholder="${escapeAttr(pInfo.default_api_base || 'Optional')}" />
        </label>
        <label>API key for fetch
          <input class="api-key-fetch" type="password" data-provider="${providerId}" placeholder="Optional / uses pasted keys" />
        </label>

      </div>
      <div class="button-row" style="margin-top: 14px;">
        <button class="primary fetch-provider-btn" data-provider="${providerId}">Fetch ${escapeHtml(pInfo.display_name)} Models</button>
      </div>
      <div class="notice hidden" id="status-${providerId}" style="margin-top: 10px;"></div>
    `;

    const fetchBtn = block.querySelector('.fetch-provider-btn');
    const statusMsg = block.querySelector(`#status-${providerId}`);
    const badge = block.querySelector(`#badge-${providerId}`);

    fetchBtn.addEventListener('click', async () => {
      fetchBtn.disabled = true;
      statusMsg.className = 'notice info';
      statusMsg.classList.remove('hidden');
      statusMsg.textContent = 'Fetching models...';
      badge.textContent = 'Fetching...';
      badge.style.background = '#e8f0ff';
      badge.style.color = 'var(--brand)';

      const baseInput = block.querySelector('.api-base-override').value.trim() || null;
      const keyInput = block.querySelector('.api-key-fetch').value.trim() || null;
      const enrichLimit = 20;
      const enrichChecked = false;

      // Fallback API key to pasted key in step 2 if present
      const plan = state.providerPlans.get(providerId);
      const api_key = keyInput || (plan && plan.pastedKeys && plan.pastedKeys[0]) || null;

      try {
        const data = await api('/api/models/fetch', {
          provider_id: providerId,
          api_key: api_key,
          base_url: baseInput,
          enrich_nvidia: enrichChecked,
          enrich_limit: enrichLimit
        });

        if (!data.ok) {
          statusMsg.className = 'notice bad';
          statusMsg.textContent = data.message || 'Model fetch failed';
          badge.textContent = 'Failed';
          badge.style.background = '#fff0f0';
          badge.style.color = 'var(--bad)';
          fetchBtn.disabled = false;
          return;
        }

        state.models = mergeModels(state.models, data.models);
        statusMsg.className = 'notice ok';
        statusMsg.textContent = `Successfully fetched ${data.count} models. Loaded total: ${state.models.length}.`;
        badge.textContent = `Fetched (${data.count})`;
        badge.style.background = '#eaf8f0';
        badge.style.color = 'var(--ok)';
        fetchBtn.disabled = false;
        renderModels();
      } catch (err) {
        statusMsg.className = 'notice bad';
        statusMsg.textContent = String(err);
        badge.textContent = 'Error';
        badge.style.background = '#fff0f0';
        badge.style.color = 'var(--bad)';
        fetchBtn.disabled = false;
      }
    });

    container.appendChild(block);
  });
}

function mergeModels(existing, incoming) {
  const byKey = new Map(existing.map(m => [`${m.provider_id}:${m.model_id}`, m]));
  incoming.forEach(m => byKey.set(`${m.provider_id}:${m.model_id}`, m));
  return Array.from(byKey.values());
}

$('clearModels').addEventListener('click', () => {
  state.models = [];
  state.selectedModels.clear();
  renderModels();
  updateDashboard();
});
$('clearSelection').addEventListener('click', () => {
  state.selectedModels.clear();
  renderModels();
  updateDashboard();
});
$('bulkEnrich').addEventListener('click', async () => {
  const btn = $('bulkEnrich');
  const originalText = btn.textContent;
  btn.disabled = true;
  btn.textContent = 'Enriching...';
  let enriched = 0;
  let total = 0;
  
  // Collect full model objects from state.models based on selected items
  const toEnrich = Array.from(state.selectedModels.values())
    .filter(m => m.provider_id === 'nvidia')
    .map(sm => state.models.find(x => x.provider_id === sm.provider_id && x.model_id === sm.model_id))
    .filter(m => m);
    
  total = toEnrich.length;
  for (let i = 0; i < total; i++) {
    const m = toEnrich[i];
    btn.textContent = `Enriching... ${i + 1}/${total}`;
    try {
      const data = await api('/api/models/enrich', {provider_id: m.provider_id, model: m});
      if (data.ok) {
        const idx = state.models.findIndex(x => x.provider_id === m.provider_id && x.model_id === m.model_id);
        if (idx >= 0) {
          state.models[idx] = data.model;
          syncEnrichedDefaults(data.model);
        }
        enriched++;
      }
    } catch (err) {}
  }
  renderModels();
  btn.disabled = false;
  btn.textContent = total > 0 ? `Enriched ${enriched}/${total} Models` : 'No NVIDIA models selected';
  setTimeout(() => btn.textContent = originalText, 3000);
});

$('selectVisible').addEventListener('click', () => {
  state.visibleModelIds.forEach(id => {
    const m = state.models.find(x => `${x.provider_id}:${x.model_id}` === id);
    if (m) state.selectedModels.set(id, selectedFromModel(m));
  });
  renderModels();
  updateDashboard();
});

['modelSearch', 'filterReasoning', 'filterDeprecated', 'filterTools', 'filterVision'].forEach(id => {
  const el = $(id);
  if (el) el.addEventListener('input', renderModels);
});

function modelCapabilities(m) {
  const c = m.capabilities || {};
  const badges = [];
  if (c.reasoning || c.thinking) badges.push(['Reasoning', 'ok']);
  if (c.function_calling) badges.push(['Tools', 'ok']);
  if (c.structured_output) badges.push(['Structured', 'ok']);
  if (c.vision) badges.push(['Vision', 'ok']);
  if (c.streaming) badges.push(['Streaming', 'ok']);
  if (m.extra_body_presets?.length) badges.push(['extra_body', 'warn']);
  if (m.warnings?.length) badges.push(['Warnings', 'warn']);
  return badges;
}

function renderModels() {
  const wrap = $('modelsTable');
  if (!wrap) return;
  wrap.innerHTML = '';
  
  const searchEl = $('modelSearch');
  const q = searchEl ? searchEl.value.toLowerCase() : '';
  const reasoningOnly = $('filterReasoning')?.checked;
  const toolsOnly = $('filterTools')?.checked;
  const visionOnly = $('filterVision')?.checked;
  const hideDeprecated = $('filterDeprecated')?.checked;
  
  const filtered = state.models.filter(m => {
    // Only display models if their provider is still selected in Step 1
    if (!state.selectedProviderIds.has(m.provider_id)) return false;
    
    const text = `${m.model_id} ${m.display_name || ''} ${m.description || ''}`.toLowerCase();
    const caps = m.capabilities || {};
    if (q && !text.includes(q)) return false;
    if (reasoningOnly && !(caps.reasoning || caps.thinking || m.extra_body_presets?.length)) return false;
    if (toolsOnly && !(caps.function_calling || caps.structured_output)) return false;
    if (visionOnly && !caps.vision) return false;
    if (hideDeprecated && (m.warnings || []).some(w => /deprecat|removed|available until/i.test(w))) return false;
    return true;
  });
  
  state.visibleModelIds = filtered.map(m => `${m.provider_id}:${m.model_id}`);

  if (!filtered.length) {
    wrap.innerHTML = '<div class="notice">No models loaded or no models match current filters. Make sure to fetch models above.</div>';
    updateDashboard();
    return;
  }

  filtered.slice(0, 500).forEach(m => wrap.appendChild(modelCard(m)));
  if (filtered.length > 500) {
    const note = document.createElement('div');
    note.className = 'notice warn';
    note.textContent = `Showing first 500 of ${filtered.length} filtered models. Use search/filters to narrow results.`;
    wrap.appendChild(note);
  }
  updateDashboard();
}

function modelCard(m) {
  const id = `${m.provider_id}:${m.model_id}`;
  const selected = state.selectedModels.get(id);
  const card = document.createElement('div');
  card.className = `model-card ${selected ? 'selected' : ''}`;
  const badges = modelCapabilities(m).map(([b, cls]) => `<span class="badge ${cls}">${escapeHtml(b)}</span>`).join('');
  const presetOptions = [`<option value="">No extra_body preset</option>`]
    .concat((m.extra_body_presets || []).map((p, idx) => `<option value="${idx}">${escapeHtml(p.label)}</option>`)).join('');
  const sources = Object.entries(m.sources || {}).slice(0, 8).map(([k,v]) => `<span class="source-pill">${escapeHtml(k)}: ${escapeHtml(v)}</span>`).join('');
  
  const providerLabel = providerInfo(m.provider_id)?.display_name || m.provider_id;

  card.innerHTML = `
    <div class="model-top">
      <div style="display: flex; gap: 12px; align-items: center; flex-wrap: wrap;">
        <label class="checkbox-row compact" style="margin-right: 8px;"><input type="checkbox" class="select-model" ${selected ? 'checked' : ''}/> <strong class="model-title">${escapeHtml(m.display_name || m.model_id)}</strong></label>
        <span class="model-id" style="margin-top:2px;">${escapeHtml(m.model_id)}</span>
        <div class="badges" style="margin-top:2px;">${badges || '<span class="badge">metadata partial</span>'}</div>
      </div>
      <div style="display: flex; gap: 12px; align-items: center;">
        <div class="model-metrics" style="display: flex; gap: 12px; font-size: 11px; color: var(--muted); background: #f8fafc; padding: 4px 10px; border-radius: 999px; border: 1px solid var(--line);">
          <span>Ctx: <strong>${m.context_window || '?'}</strong></span>
          <span>Out: <strong>${m.max_output_tokens || '?'}</strong></span>
        </div>
        <button class="secondary enrich-one" style="padding: 4px 12px; font-size: 12px;" ${m.provider_id === 'nvidia' ? '' : 'disabled'}>Enrich</button>
      </div>
    </div>
    <div class="source-row" style="margin-top: 4px;">${sources}</div>
    
    <details class="model-settings-drawer">
      <summary>⚙️ Advanced Model Settings</summary>
      <div class="model-actions" style="margin-top: 12px; padding: 12px; background: #f8fafc; border-radius: 8px; border: 1px solid var(--line);">
        <label>Alias <input class="alias" value="${escapeAttr(selected?.alias || aliasFromModel(m.model_id))}" /></label>
        <label>LiteLLM model <input class="litellm-model" value="${escapeAttr(selected?.litellm_model || m.litellm_model || defaultLiteLLMName(m))}" /></label>
        <label>API base <input class="api-base" value="${escapeAttr(selected?.api_base || m.api_base || '')}" /></label>
        <label>Max tokens <input class="max-tokens" type="number" value="${selected?.max_tokens || m.max_output_tokens || ''}" /></label>
        <label>Temperature <input class="temperature" type="number" step="0.01" value="${selected?.temperature ?? m.temperature ?? ''}" /></label>
        <label>Top P <input class="top-p" type="number" step="0.01" value="${selected?.top_p ?? m.top_p ?? ''}" /></label>
        <label>extra_body preset <select class="preset">${presetOptions}</select></label>
      </div>
    </details>
    ${m.description ? `<p style="font-size: 13px; color: var(--muted); margin-top: 12px;">${escapeHtml(m.description)}</p>` : ''}
    ${m.warnings?.length ? `<div class="notice warn">${escapeHtml(m.warnings.join('\n'))}</div>` : ''}`;

  const checkbox = card.querySelector('.select-model');
  const update = () => updateSelectedFromCard(m, card);
  card.style.cursor = 'pointer';
  card.addEventListener('click', (e) => {
    if (e.target.closest('.checkbox-row') || e.target.tagName === 'INPUT' || e.target.tagName === 'BUTTON' || e.target.closest('.enrich-one') || e.target.closest('details') || e.target.tagName === 'SELECT' || e.target.tagName === 'A') {
      return;
    }
    checkbox.click();
  });

  checkbox.addEventListener('change', () => {
    if (checkbox.checked) update(); else state.selectedModels.delete(id);
    renderSelectedSummary();
    updateDashboard();
  });
  card.querySelectorAll('input,select').forEach(el => el.addEventListener('change', () => { if (checkbox.checked) update(); }));
  
  card.querySelector('.enrich-one').addEventListener('click', async () => {
    const btn = card.querySelector('.enrich-one');
    btn.disabled = true;
    btn.textContent = 'Enriching...';
    try {
      const data = await api('/api/models/enrich', {provider_id: m.provider_id, model: m});
      if (data.ok) {
        const idx = state.models.findIndex(x => x.provider_id === m.provider_id && x.model_id === m.model_id);
        if (idx >= 0) {
          state.models[idx] = data.model;
          syncEnrichedDefaults(data.model);
        }
        renderModels();
      } else {
        alert(data.message || 'Enrichment failed');
        btn.disabled = false;
        btn.textContent = 'Enrich';
      }
    } catch (err) {
      alert(`Enrichment failed: ${err}`);
      btn.disabled = false;
      btn.textContent = 'Enrich';
    }
  });
  return card;
}

function selectedFromModel(m) {
  const plan = state.providerPlans.get(m.provider_id);
  const envs = plan && plan.envNames.length ? plan.envNames : [`${m.provider_id.toUpperCase()}_API_KEY`];
  return {
    provider_id: m.provider_id,
    model_id: m.model_id,
    alias: aliasFromModel(m.model_id),
    litellm_model: m.litellm_model || defaultLiteLLMName(m),
    api_base: m.api_base || null,
    env_names: envs,
    max_tokens: m.max_output_tokens || null,
    temperature: m.temperature ?? null,
    top_p: m.top_p ?? null,
    rpm: numberOrNull($('rpm').value),
    tpm: numberOrNull($('tpm').value),
    extra_body: null,
    mode: 'explicit',
    notes: (m.warnings || []).slice(0, 3)
  };
}

function updateSelectedFromCard(m, card) {
  const id = `${m.provider_id}:${m.model_id}`;
  const presetIdx = card.querySelector('.preset').value;
  let extraBody = null;
  if (presetIdx !== '') extraBody = m.extra_body_presets[Number(presetIdx)].body;

  const plan = state.providerPlans.get(m.provider_id);
  const envs = plan && plan.envNames.length ? plan.envNames : [`${m.provider_id.toUpperCase()}_API_KEY`];

  state.selectedModels.set(id, {
    provider_id: m.provider_id,
    model_id: m.model_id,
    alias: card.querySelector('.alias').value || aliasFromModel(m.model_id),
    litellm_model: card.querySelector('.litellm-model').value || defaultLiteLLMName(m),
    api_base: card.querySelector('.api-base').value || null,
    env_names: envs,
    max_tokens: numberOrNull(card.querySelector('.max-tokens').value),
    temperature: numberOrNull(card.querySelector('.temperature').value),
    top_p: numberOrNull(card.querySelector('.top-p').value),
    rpm: null,
    tpm: null,
    extra_body: extraBody,
    mode: 'explicit',
    notes: (m.warnings || []).slice(0, 3)
  });
  renderSelectedSummary();
}

function syncEnrichedDefaults(m) {
  const id = `${m.provider_id}:${m.model_id}`;
  if (state.selectedModels.has(id)) {
    const selected = state.selectedModels.get(id);
    if (selected.max_tokens === null && m.max_output_tokens != null) selected.max_tokens = m.max_output_tokens;
    if (selected.temperature === null && m.temperature != null) selected.temperature = m.temperature;
    if (selected.top_p === null && m.top_p != null) selected.top_p = m.top_p;
    state.selectedModels.set(id, selected);
  }
}

function renderSelectedSummary() {
  const el = $('selectedSummary');
  if (!el) return;
  const selected = Array.from(state.selectedModels.values());
  if (!selected.length) {
    el.innerHTML = '<div class="notice">No models selected yet.</div>';
    return;
  }
  const deployments = selected.reduce((sum, m) => sum + (m.env_names?.length || 0), 0);
  
  // Aggregate env keys across selected
  const uniqEnvs = new Set();
  selected.forEach(m => m.env_names.forEach(e => uniqEnvs.add(e)));

  el.innerHTML = `
    <div class="summary-card">
      <strong>${selected.length}</strong> explicit model(s), <strong>${deployments}</strong> deployment(s) using <strong>${uniqEnvs.size}</strong> planned key(s).
      <span>${selected.map(m => `<code>${escapeHtml(m.alias)}</code>`).slice(0, 8).join(' ')}${selected.length > 8 ? ' …' : ''}</span>
    </div>`;
}

function numberOrNull(v) { return v === '' || v === null || v === undefined ? null : Number(v); }
function aliasFromModel(id) { return id.split('/').pop().replace(/[^a-zA-Z0-9_.-]+/g, '-'); }
function defaultLiteLLMName(m) {
  if (m.provider_id === 'nvidia') return `openai/${m.model_id}`;
  if (m.provider_id === 'openrouter') return `openrouter/${m.model_id}`;
  if (m.provider_id === 'gemini') return `gemini/${m.model_id}`;
  if (m.provider_id === 'groq') return `groq/${m.model_id}`;
  if (m.provider_id === 'openai') return m.model_id.startsWith('openai/') ? m.model_id : `openai/${m.model_id}`;
  return m.model_id;
}

$('addManualModel').addEventListener('click', () => {
  const tpl = $('manualModelTemplate').content.cloneNode(true);
  document.body.appendChild(tpl);
  const backdrop = document.querySelector('.modal-backdrop');
  
  const manualProviderInput = document.querySelector('#manualProvider');
  const manualApiBaseInput = document.querySelector('#manualApiBase');
  
  // Prefill default provider from the first active provider
  const currentProvider = Array.from(state.selectedProviderIds)[0] || 'nvidia';
  manualProviderInput.value = currentProvider;
  
  const pInfo = providerInfo(currentProvider);
  if (pInfo && pInfo.default_api_base) {
    manualApiBaseInput.value = pInfo.default_api_base;
  }

  manualProviderInput.addEventListener('change', () => {
    const info = providerInfo(manualProviderInput.value);
    if (info) manualApiBaseInput.value = info.default_api_base || '';
  });

  document.querySelector('#cancelManual').addEventListener('click', () => backdrop.remove());
  document.querySelector('#saveManual').addEventListener('click', () => {
    const modelId = document.querySelector('#manualModelId').value.trim();
    if (!modelId) return alert('Model ID is required');
    const provider_id = manualProviderInput.value.trim() || 'custom_openai';
    const newModel = {
      provider_id,
      model_id: modelId,
      display_name: modelId,
      litellm_model: document.querySelector('#manualLiteLLM').value.trim() || defaultLiteLLMName({provider_id, model_id: modelId}),
      api_base: manualApiBaseInput.value.trim() || null,
      capabilities: {chat: true},
      extra_body_presets: [],
      warnings: ['Manual model. Metadata should be verified.'],
      sources: {model_id: 'user_override'},
      raw: {}
    };
    state.models.unshift(newModel);
    backdrop.remove();
    renderModels();
    updateDashboard();
  });
});

function parseFallbacks() {
  return $('fallbackText').value.split('\n').map(line => line.trim()).filter(Boolean).map(line => {
    const [primary, rest] = line.split(':');
    return {primary: (primary || '').trim(), fallbacks: (rest || '').split(',').map(x => x.trim()).filter(Boolean)};
  }).filter(x => x.primary && x.fallbacks.length);
}

function buildWildcardRoutes(selected) {
  const mode = $('generationMode').value;
  if (mode === 'explicit') return [];
  const providers = new Map();
  selected.forEach(m => {
    if (!providers.has(m.provider_id)) providers.set(m.provider_id, m);
  });
  if (mode === 'wildcard') {
    return Array.from(providers.values()).map(wildcardFromSelected);
  }
  if (mode === 'hybrid') {
    return Array.from(providers.values()).map(wildcardFromSelected);
  }
  return [];
}

function wildcardFromSelected(m) {
  let litellm_model = `${m.provider_id}/*`;
  let alias = `${m.provider_id}/*`;
  let api_base = null;
  
  if (m.provider_id === 'nvidia') {
    litellm_model = 'openai/*';
    alias = 'nvidia/*';
    api_base = m.api_base || 'https://integrate.api.nvidia.com/v1';
  } else if (m.provider_id === 'openrouter') {
    litellm_model = 'openrouter/*';
    alias = 'openrouter/*';
  } else if (m.provider_id === 'gemini') {
    litellm_model = 'gemini/*';
    alias = 'gemini/*';
  } else if (m.provider_id === 'openai') {
    litellm_model = 'openai/*';
    alias = 'openai/*';
  } else {
    // Custom OpenAI gateways, LMStudio, Ollama, etc.
    const pInfo = providerInfo(m.provider_id);
    litellm_model = 'openai/*';
    alias = `${m.provider_id}/*`;
    api_base = m.api_base || (pInfo ? pInfo.default_api_base : null);
  }

  const plan = state.providerPlans.get(m.provider_id);
  const envs = plan && plan.envNames.length ? plan.envNames : [`${m.provider_id.toUpperCase()}_API_KEY`];

  return {
    provider_id: m.provider_id,
    alias,
    litellm_model,
    api_base,
    env_names: envs,
    rpm: null,
    tpm: null,
    notes: ['Wildcard route generated by LiteLLM Config Studio. Test /v1/models in your target client.']
  };
}

async function buildGenerationRequest() {
  let selected = Array.from(state.selectedModels.values()).map(m => {
    const plan = state.providerPlans.get(m.provider_id);
    const envs = plan && plan.envNames.length ? plan.envNames : m.env_names;
    return {
      ...m,
      env_names: envs,
      rpm: null,
      tpm: null,
      mode: 'explicit'
    };
  });
  
  const mode = $('generationMode').value;
  const wildcardRoutes = buildWildcardRoutes(selected);
  if (mode === 'wildcard') selected = [];
  
  const provider_routing = [];
  state.providerRouting.forEach((limits, pid) => {
    provider_routing.push({
      provider_id: pid,
      rpm: limits.rpm || null,
      tpm: limits.tpm || null
    });
  });
  
  return {
    selected_models: selected,
    wildcard_routes: wildcardRoutes,
    fallback_groups: parseFallbacks(),
    provider_routing: provider_routing,
    routing: {
      routing_strategy: $('routingStrategy').value,
      num_retries: Number($('numRetries').value || 0),
      cooldown_time: Number($('cooldownTime').value || 0),
      timeout: numberOrNull($('timeout').value),
      max_parallel_requests: numberOrNull($('maxParallel').value),
      background_health_checks: $('backgroundHealth').checked,
      health_check_interval: 60,
      enable_health_check_routing: $('healthRouting').checked,
      prompt_cache_mode: $('promptCacheMode').value
    },
    litellm_master_key_env: 'LITELLM_MASTER_KEY',
    include_docker_compose: true,
    include_import_script: true,
    include_models_report: true,
    generation_mode: mode
  };
}

// Step 5: Test Selector Population
function populateTestSelectors() {
  const provSelect = $('testProviderSelect');
  const modelSelect = $('testModelSelect');
  if (!provSelect || !modelSelect) return;

  provSelect.innerHTML = '';
  modelSelect.innerHTML = '';

  // Providers
  state.selectedProviderIds.forEach(pId => {
    const info = providerInfo(pId);
    if (!info) return;
    const opt = document.createElement('option');
    opt.value = pId;
    opt.textContent = info.display_name;
    provSelect.appendChild(opt);
  });

  // Models
  const selectedModelsArray = Array.from(state.selectedModels.values());
  if (selectedModelsArray.length === 0) {
    const opt = document.createElement('option');
    opt.value = '';
    opt.textContent = '(No models selected in Step 3)';
    modelSelect.appendChild(opt);
  } else {
    selectedModelsArray.forEach(m => {
      const opt = document.createElement('option');
      opt.value = `${m.provider_id}:${m.model_id}`;
      opt.textContent = `${m.alias} [${m.model_id}]`;
      modelSelect.appendChild(opt);
    });
  }
}

// Outputs
$('generateOutput').addEventListener('click', async () => {
  const resultsArea = $('outputLint');
  resultsArea.textContent = 'Generating output files...';

  try {
    const req = await buildGenerationRequest();
    if (!req.selected_models.length && !req.wildcard_routes.length) {
      alert('Select at least one model first in Step 3.');
      return;
    }
    const data = await api('/api/generate', req);
    state.outputFiles = data.files;
    state.currentTab = 'config.yaml';
    renderOutputTabs();
    $('outputEditor').value = state.outputFiles[state.currentTab] || '';
    resultsArea.textContent = pretty(data.lint);
    updateDashboard();
  } catch (err) {
    resultsArea.textContent = `Error: ${err}`;
    alert(`Generation failed: ${err}`);
  }
});

function renderOutputTabs() {
  const tabs = $('outputTabs');
  if (!tabs) return;
  tabs.innerHTML = '';
  Object.keys(state.outputFiles).forEach(name => {
    if (!state.outputFiles[name]) return;
    const btn = document.createElement('button');
    btn.className = `tab ${name === state.currentTab ? 'active' : ''}`;
    btn.textContent = name;
    btn.addEventListener('click', () => {
      state.outputFiles[state.currentTab] = $('outputEditor').value;
      state.currentTab = name;
      $('outputEditor').value = state.outputFiles[name] || '';
      renderOutputTabs();
    });
    tabs.appendChild(btn);
  });
}

$('copyCurrent').addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText($('outputEditor').value);
    $('outputLint').textContent = `Copied ${state.currentTab} to clipboard!`;
  } catch (err) {
    $('outputLint').textContent = `Copy failed: ${err}`;
  }
});

$('downloadCurrent').addEventListener('click', () => {
  const blob = new Blob([$('outputEditor').value], {type: 'text/plain'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = state.currentTab || 'output.txt';
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
});

$('downloadZip').addEventListener('click', async () => {
  if (!Object.keys(state.outputFiles).length) {
    alert('Generate output first.'); return;
  }
  state.outputFiles[state.currentTab] = $('outputEditor').value;
  try {
    const res = await fetch('/api/export-zip', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({files: state.outputFiles})
    });
    if (!res.ok) throw new Error(await res.text());
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'litellm-config-studio-export.zip';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (err) {
    alert(`Export ZIP failed: ${err}`);
  }
});

$('validateCurrent').addEventListener('click', async () => {
  if (!state.currentTab.endsWith('.yaml') && state.currentTab !== 'config.yaml') {
    $('outputLint').textContent = 'Validation currently supports YAML files.';
    return;
  }
  try {
    const data = await api('/api/lint', {yaml_text: $('outputEditor').value});
    $('outputLint').textContent = pretty(data);
  } catch (err) {
    $('outputLint').textContent = `Validation call failed: ${err}`;
  }
});

$('estimateTests').addEventListener('click', async () => {
  try {
    const req = await buildGenerationRequest();
    const data = await api('/api/test/estimate', req);
    $('testResults').textContent = pretty(data);
  } catch (err) {
    $('testResults').textContent = `Estimate failed: ${err}`;
  }
});

// Helper to look up key and base URL for selected provider testing
function getTestCredentials(providerId) {
  const plan = state.providerPlans.get(providerId);
  const pastedKey = plan && plan.pastedKeys && plan.pastedKeys[0] ? plan.pastedKeys[0] : null;

  const fetchInput = document.querySelector(`.api-key-fetch[data-provider="${providerId}"]`);
  const fetchKey = fetchInput ? fetchInput.value.trim() : null;

  const api_key = pastedKey || fetchKey || null;

  const baseInput = document.querySelector(`.api-base-override[data-provider="${providerId}"]`);
  const base_url = baseInput ? baseInput.value.trim() : null;

  return { api_key, base_url };
}

$('testKey').addEventListener('click', async () => {
  const providerId = $('testProviderSelect').value;
  if (!providerId) return alert('Select a provider to test.');
  
  const { api_key, base_url } = getTestCredentials(providerId);
  $('testResults').textContent = 'Testing connection/key...';

  try {
    const data = await api('/api/test/key', {
      provider_id: providerId,
      api_key,
      base_url
    });
    $('testResults').textContent = pretty(data);
  } catch (err) {
    $('testResults').textContent = `Test connection failed: ${err}`;
  }
});

$('testChat').addEventListener('click', async () => {
  const modelKey = $('testModelSelect').value;
  if (!modelKey) return alert('Select a selected model to test.');
  
  const selected = state.selectedModels.get(modelKey);
  if (!selected) return alert('Model config could not be resolved.');

  const { api_key, base_url } = getTestCredentials(selected.provider_id);
  $('testResults').textContent = `Sending test chat completions request to ${selected.litellm_model}...`;

  // Strip prefix (e.g. openai/ or openrouter/) for native provider testing
  const modelName = selected.litellm_model.replace(/^(openai|openrouter|gemini|groq)\//, '');

  try {
    const data = await api('/api/test/chat', {
      provider_id: selected.provider_id,
      api_key,
      base_url,
      model: modelName,
      max_tokens: 10,
      messages: [{role: 'user', content: 'Reply with only OK.'}],
      extra_body: selected.extra_body || null
    });
    $('testResults').textContent = pretty(data);
  } catch (err) {
    $('testResults').textContent = `Chat test failed: ${err}`;
  }
});

$('testMatrix').addEventListener('click', async () => {
  const resultsArea = $('testResults');
  resultsArea.innerHTML = '<div style="margin-bottom:12px; font-weight:bold;">Running matrix test...</div><table style="width:100%; border-collapse: collapse; text-align: left;"><thead><tr style="border-bottom:1px solid var(--line);"><th style="padding:8px;">Model</th><th style="padding:8px;">Key</th><th style="padding:8px;">Status</th><th style="padding:8px;">Response</th></tr></thead><tbody id="matrixBody"></tbody></table>';
  
  const tbody = document.getElementById('matrixBody');
  const selectedModels = Array.from(state.selectedModels.values());
  
  if (selectedModels.length === 0) {
    resultsArea.innerHTML = '<span style="color:red;">Select at least one model in Step 3.</span>';
    return;
  }
  
  for (const selected of selectedModels) {
    const providerId = selected.provider_id;
    const plan = state.providerPlans.get(providerId);
    let keys = plan ? plan.pastedKeys : [];
    
    if (!keys || keys.length === 0) {
      const fetchInput = document.querySelector(`.api-key-fetch[data-provider="${providerId}"]`);
      if (fetchInput && fetchInput.value.trim()) keys = [fetchInput.value.trim()];
    }
    
    if (!keys || keys.length === 0) {
       tbody.innerHTML += `<tr><td style="padding:8px; border-bottom:1px solid #f0f0f0;">${escapeHtml(selected.alias)}</td><td style="padding:8px; border-bottom:1px solid #f0f0f0;">(No keys)</td><td style="padding:8px; color:var(--danger); border-bottom:1px solid #f0f0f0;">Skipped</td><td style="padding:8px; border-bottom:1px solid #f0f0f0;">No test keys provided</td></tr>`;
       continue;
    }
    
    const baseInput = document.querySelector(`.api-base-override[data-provider="${providerId}"]`);
    const base_url = baseInput ? baseInput.value.trim() : null;
    const modelName = selected.litellm_model.replace(/^(openai|openrouter|gemini|groq)\//, '');
    
    for (const key of keys) {
       const keyPrefix = key.length > 8 ? escapeHtml(key.substring(0, 8)) + '...' : escapeHtml(key);
       
       const tr = document.createElement('tr');
       tr.style.borderBottom = '1px solid #f0f0f0';
       tr.innerHTML = `<td style="padding:8px;">${escapeHtml(selected.alias)}</td><td style="padding:8px;">${keyPrefix}</td><td style="padding:8px; font-weight:bold;">Testing...</td><td style="padding:8px; color:var(--muted);">Waiting...</td>`;
       tbody.appendChild(tr);
       
       try {
         const data = await api('/api/test/chat', {
           provider_id: providerId,
           api_key: key,
           base_url,
           model: modelName,
           max_tokens: 10,
           messages: [{role: 'user', content: 'Reply with only OK.'}],
           extra_body: selected.extra_body || null
         });
         
         const statusTd = tr.children[2];
         const resTd = tr.children[3];
         if (data.ok) {
           statusTd.textContent = 'Pass';
           statusTd.style.color = 'var(--success)';
           resTd.textContent = String(data.content || 'OK').substring(0, 60);
           resTd.style.color = 'inherit';
         } else {
           statusTd.textContent = 'Fail';
           statusTd.style.color = 'var(--danger)';
           resTd.textContent = String(data.message || 'Error').substring(0, 80);
           resTd.style.color = 'inherit';
         }
       } catch(err) {
         tr.children[2].textContent = 'Error';
         tr.children[2].style.color = 'var(--danger)';
         tr.children[3].textContent = String(err).substring(0, 80);
       }
    }
  }
});

$('analyzeConfig').addEventListener('click', async () => {
  try {
    const data = await api('/api/analyze-config', {yaml_text: $('existingConfig').value});
    $('analysisResults').textContent = pretty(data);
  } catch (err) {
    $('analysisResults').textContent = `Analysis failed: ${err}`;
  }
});

function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
}
function escapeAttr(s) { return escapeHtml(s).replace(/'/g, '&#39;'); }

// Initial startup
$('compatButton').addEventListener('click', async () => {
  try {
    const data = await api('/api/compatibility');
    const el = $('compatReport');
    el.classList.remove('hidden');
    el.textContent = pretty(data);
    showSection('dashboard');
  } catch (err) {
    alert(`Could not fetch compatibility report: ${err}`);
  }
});

loadProviders();
