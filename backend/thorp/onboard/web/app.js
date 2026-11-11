// The first-run page. Vanilla on purpose: it is served by Python before the Astro dashboard exists,
// so it cannot depend on the app's bundles. All state lives on the server; this file renders what
// `/api/onboard/state` says and posts the four answers.
(() => {
  'use strict';

  const TOKEN = new URLSearchParams(location.search).get('token') || '';
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
  const STEPS = ['welcome', 'sail', 'models', 'store', 'install', 'done'];

  const app = {
    cat: null,
    data: null,
    sail: null,
    classes: new Set(),
    bands: new Set(),
    models: new Set(),
    storeMode: 'local',
    storeUrl: '',
    step: 'welcome',
    poll: null,
    started: { store: false, build: false },
    warnings: [],
  };

  const esc = (v) =>
    String(v == null ? '' : v).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  const gb = (v) => {
    if (v == null || !Number.isFinite(Number(v))) return '—';
    const n = Number(v);
    return n >= 10 ? `${n.toFixed(0)} GB` : `${n.toFixed(1)} GB`;
  };
  const pct = (v) => (v == null ? '' : `${Number(v).toFixed(0)}%`);

  function fail(msg) {
    const box = $('#error');
    box.textContent = String(msg || 'Something went wrong.');
    box.hidden = false;
    box.scrollIntoView({ block: 'nearest' });
  }
  function clearError() {
    $('#error').hidden = true;
    $('#error').textContent = '';
  }

  async function api(name, body) {
    const opts = body
      ? {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-Thorp-Onboard': TOKEN },
          body: JSON.stringify(body),
        }
      : { headers: { 'X-Thorp-Onboard': TOKEN } };
    const r = await fetch(`/api/onboard/${name}`, opts);
    let data = {};
    try {
      data = await r.json();
    } catch (_) {
      data = { error: r.statusText || `HTTP ${r.status}` };
    }
    if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
    return data;
  }

  function machineLine(m) {
    if (!m) return '';
    const bits = [m.chip, m.memory_gb ? `${m.memory_gb} GB` : null, m.free_gb ? `${m.free_gb} GB free` : null];
    return bits.filter(Boolean).join(' · ');
  }

  function fitBadge(kind) {
    const map = {
      fits: ['good', 'fits this Mac'],
      tight: ['warn', 'tight on memory'],
      'needs-more': ['bad', 'needs more memory'],
      'needs-lane': ['warn', 'needs the Vast lane'],
      unknown: ['', 'not measured'],
    };
    const [cls, label] = map[kind] || map.unknown;
    return `<span class="badge ${cls}">${esc(label)}</span>`;
  }

  function applyState(s) {
    app.data = { ...(app.data || {}), state: s };
    app.sail = s.sailing && typeof s.sailing.enabled === 'boolean' ? s.sailing.enabled : null;
    app.classes = new Set((s.sailing && s.sailing.classes) || []);
    app.bands = new Set((s.models && s.models.bands) || []);
    app.models = new Set((s.models && s.models.selected) || []);
    app.storeMode = (s.store && s.store.mode) || 'local';
    app.storeUrl = (s.store && s.store.url) || '';
    app.step = s.step || 'welcome';
    if (s.completed_at) app.step = 'done';
  }

  function renderMachine() {
    const m = app.cat ? app.cat.machine : null;
    const line = machineLine(m);
    $('#machine').textContent = line;
    $('#tokenstate').textContent = TOKEN
      ? 'The setup link is local to this terminal. It is not a password.'
      : 'No setup token: open the link printed in the terminal.';
  }

  function renderWelcome() {
    const m = (app.cat && app.cat.machine) || {};
    const rows = [
      ['chip', m.chip || '—'],
      ['memory', m.memory_gb ? `${m.memory_gb} GB` : '—'],
      ['free disk', m.free_gb ? `${m.free_gb} GB` : '—'],
      ['Python', m.python || '—'],
      ['data', m.data || '—'],
    ];
    $('#welcomecheck').innerHTML = rows.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('');
  }

  function renderClasses() {
    const wrap = $('#classwrap');
    wrap.hidden = app.sail !== true;
    $$('[data-sail]').forEach((b) =>
      b.classList.toggle(
        'selected',
        app.sail !== null && (b.dataset.sail === 'yes') === (app.sail === true),
      ),
    );
    const cards = (app.cat && app.cat.classes) || [];
    const chosen = app.classes;
    $('#classcards').innerHTML = cards
      .map(
        (c) => `<button type="button" class="classcard${chosen.has(c.preset) ? ' selected' : ''}" data-preset="${esc(c.preset)}">
          <span class="topline"><b>${esc(c.name)}</b><span class="preset">${esc(c.preset)}</span></span>
          <span class="job">${esc(c.job)}</span>
          <span class="shape">${esc(c.shape || '')}</span>
          <span>${fitBadge(c.fit)}</span>
        </button>`,
      )
      .join('');
    $('#classnote').textContent =
      chosen.size > 1
        ? `${chosen.size} classes selected. Each one sets a default; nothing starts until you queue a voyage.`
        : chosen.size === 1
          ? 'One class selected. It sets a default; nothing starts until you queue a voyage.'
          : 'Choose at least one class to sail.';
    const next = $('#sail-next');
    next.disabled = app.sail === null || (app.sail === true && chosen.size === 0);
  }

  function renderBands() {
    const bands = (app.cat && app.cat.bands) || [];
    $('#bandcards').innerHTML = bands
      .map(
        (b) => `<button type="button" class="bandcard${app.bands.has(b.key) ? ' selected' : ''}" data-band="${esc(b.key)}">
          <span class="range">${esc(b.name)}</span>
          <b>${esc(b.range)}</b>
          <span class="about">${esc(b.about)}</span>
          <span class="count">${b.count} instruct model${b.count === 1 ? '' : 's'}</span>
        </button>`,
      )
      .join('');
  }

  function fitKind(m) {
    if (m.fit) return m.fit;
    return 'unknown';
  }

  function renderModels() {
    const wrap = $('#modelwrap');
    const models = (app.cat && app.cat.models) || [];
    const visible = models.filter((m) => app.bands.has(m.band));
    wrap.hidden = app.bands.size === 0;
    if (!app.bands.size) {
      $('#models').innerHTML = '';
      $('#modeltotal').textContent = 'Choose a size band first';
      $('#models-next').disabled = true;
      return;
    }
    if (!visible.length) {
      $('#models').innerHTML = '<div class="emptymsg">No instruct models are catalogued in this band yet.</div>';
    } else {
      $('#models').innerHTML = visible
        .map(
          (m) => `<label class="modelrow${app.models.has(m.repo) ? ' selected' : ''}">
            <input type="checkbox" data-repo="${esc(m.repo)}"${app.models.has(m.repo) ? ' checked' : ''} />
            <span class="main">
              <b>${esc(m.label)}</b>
              <span class="meta">Instruct · ${esc(m.params_h)} · ${esc(m.license)}${m.note ? ` · ${esc(m.note)}` : ''}</span>
            </span>
            <span class="size">≈${gb(m.download_gb)} download<br>runs in ≈${gb(m.run_gb)}</span>
            <span class="fit">${fitBadge(fitKind(m))}</span>
          </label>`,
        )
        .join('');
    }
    const chosen = models.filter((m) => app.models.has(m.repo));
    const download = chosen.reduce((n, m) => n + Number(m.download_gb || 0), 0);
    const run = chosen.reduce((n, m) => n + Number(m.run_gb || 0), 0);
    $('#modeltotal').textContent = chosen.length
      ? `${chosen.length} model${chosen.length === 1 ? '' : 's'} · ≈${gb(download)} download · ≈${gb(run)} to run`
      : 'No models selected';
    const free = (app.cat.machine && app.cat.machine.free_gb) || 0;
    $('#disknote').textContent =
      chosen.length && free
        ? download > free * 0.9
          ? `That is more than this Mac has free (${gb(free)}).`
          : `${gb(free)} free on the disk`
        : '';
    $('#models-next').disabled = chosen.length === 0;
  }

  function renderStoreStatus(status) {
    const st = status || {};
    const missing = st.missing || [];
    const items = [
      ['Postgres tools', !missing.length, missing.length ? `missing ${missing.join(', ')}` : 'initdb, pg_ctl, psql'],
      ['Cluster', !!st.exists, st.cluster || 'data/postgres'],
      ['Server', !!st.running, `port ${st.port || 5433}`],
      ['Database', !!st.reachable, st.database || 'thorp'],
      ['Thorp schema', !!st.schema, st.schema || 'not migrated'],
    ];
    $('#storestatus').innerHTML = items
      .map(
        ([label, ok, detail]) => `<div class="checkitem ${ok ? 'ok' : 'bad'}">
          <i>${ok ? '✓' : '!'}</i><span>${esc(label)}</span><span class="s">${esc(detail)}</span>
        </div>`,
      )
      .join('');
    $('#storehead').textContent = st.ready ? 'ready' : 'not ready yet';
    $('#storesetup').textContent = st.ready ? 'Use local Postgres' : 'Set up local Postgres';
    $('#storesetup').disabled = missing.length > 0 && !st.ready;
    const msg = $('#storemsg');
    if (missing.length && !st.ready) {
      msg.textContent = `Postgres is not installed. Run \`${st.install_hint || 'brew install postgresql@17'}\`, then Retry.`;
      msg.className = 's';
    } else if (st.ready) {
      msg.textContent = `Answering at ${st.url}`;
      msg.className = 's';
    } else {
      msg.textContent = '';
    }
    const locked = $('#storelocked');
    if (st.locked) {
      locked.hidden = false;
      locked.textContent = 'THORP_PG is set in this terminal, so the environment owns the store address; the install file cannot choose another.';
    } else {
      locked.hidden = true;
    }
    if (st.mode === 'hosted') {
      // a hosted store chosen outside this page: reflect it in the cards
      $$('.storecard').forEach((b) => b.classList.toggle('selected', b.dataset.store === 'hosted'));
    }
  }

  function renderInstall(st) {
    const setup = (st && st.setup) || {};
    const jobs = (st && st.jobs) || {};
    const downloads = (st && st.downloads) || [];
    const store = setup.store || {};
    const build = setup.build || {};
    const chat = setup.chat_engine || {};
    const rows = [];

    const storeJob = jobs.store || { state: 'idle' };
    const storeRunning = storeJob.state === 'running';
    const storeDone = !!store.ready;
    const storeFailed = storeJob.state === 'failed';
    const storePct = storeDone ? 100 : storeRunning ? 45 : storeFailed ? 100 : 0;
    rows.push(
      installRow({
        key: 'store',
        title: 'The store',
        state: storeDone ? 'done' : storeFailed ? 'failed' : storeRunning ? 'running' : 'waiting',
        pct: storePct,
        detail: storeDone
          ? `Answering at ${esc(store.url)}`
          : storeFailed
            ? 'The store could not be set up.'
            : storeRunning
              ? 'Creating the cluster, starting it, migrating…'
              : store.missing && store.missing.length
                ? `Postgres is not installed (${esc(store.missing.join(', '))}).`
                : 'Waiting to start.',
        error: storeFailed ? storeJob.error : '',
        action: storeFailed ? '<button type="button" class="secondary" data-act="store">Retry the store</button>' : '',
      }),
    );

    if (!downloads.length) {
      rows.push(
        installRow({
          key: 'models',
          title: 'Models',
          state: 'waiting',
          pct: 0,
          detail: 'No models selected. You can add them later from the dashboard.',
          action: '',
        }),
      );
    } else {
      for (const d of downloads) {
        const state = d.state === 'ready' ? 'done' : d.state === 'failed' ? 'failed' : d.state === 'downloading' || d.state === 'verifying' ? 'running' : d.state === 'cancelled' ? 'failed' : 'waiting';
        const detail =
          d.state === 'ready'
            ? `${gb(d.bytes_done / 1e9)} in the cache`
            : d.state === 'failed'
              ? 'Download failed'
              : d.state === 'cancelled'
                ? 'Cancelled'
                : d.speed_bps
                  ? `${gb(d.bytes_done / 1e9)} of ≈${gb(d.bytes_total / 1e9)} · ${gb(d.speed_bps / 1e9)}/s`
                  : `${gb(d.bytes_done / 1e9)} of ≈${gb(d.bytes_total / 1e9)}`;
        const action =
          d.state === 'failed' || d.state === 'cancelled'
            ? `<button type="button" class="secondary" data-act="download" data-repo="${esc(d.repo)}">Retry</button>`
            : d.state === 'downloading' || d.state === 'queued'
              ? `<button type="button" class="linkbtn" data-act="cancel" data-repo="${esc(d.repo)}">Cancel</button>`
              : '';
        rows.push(
          installRow({
            key: `model:${d.repo}`,
            title: d.label,
            state,
            pct: d.state === 'ready' ? 100 : d.percent || 0,
            detail,
            error: d.error || '',
            action,
          }),
        );
      }
    }

    const buildJob = jobs.build || { state: 'idle' };
    const buildRunning = buildJob.state === 'running';
    const buildFailed = buildJob.state === 'failed';
    const buildDone = !!build.built;
    rows.push(
      installRow({
        key: 'build',
        title: 'The dashboard',
        state: buildDone ? 'done' : buildFailed ? 'failed' : buildRunning ? 'running' : 'waiting',
        pct: buildDone ? 100 : buildRunning ? 55 : buildFailed ? 100 : 0,
        detail: buildDone
          ? 'Built and ready to serve.'
          : buildFailed
            ? 'The frontend build failed.'
            : buildRunning
              ? 'Installing and building the Astro page…'
              : build.can_build
                ? 'Waiting to build.'
                : `Node and pnpm are needed. Run \`${esc(build.hint)}\`.`,
        error: buildFailed ? buildJob.error : '',
        action: buildFailed ? '<button type="button" class="secondary" data-act="build">Retry the build</button>' : '',
      }),
    );

    rows.push(
      installRow({
        key: 'chat',
        title: 'The chat engine',
        state: chat.installed ? 'done' : 'failed',
        pct: chat.installed ? 100 : 100,
        detail: chat.installed
          ? `mlx-lm${chat.version ? ` ${esc(chat.version)}` : ''} is installed.`
          : `mlx-lm is missing. Run \`${esc(chat.hint)}\`, then restart the first run.`,
        error: '',
        action: chat.installed ? '' : `<code>${esc(chat.hint)}</code>`,
      }),
    );

    $('#installrows').innerHTML = rows.join('');
    const running = storeRunning || buildRunning;
    const finish = $('#finish');
    // a long model download must not hold the dashboard hostage: the install page says it can finish after
    finish.disabled = running || !store.ready;
    finish.textContent = running ? 'Installing…' : 'Finish setup';
    const warn = [];
    if (!store.ready) warn.push('The store is not ready; the dashboard will have empty panels.');
    if (!buildDone) warn.push('The dashboard is not built; finish will leave you at Settings until it is.');
    if (!downloads.some((d) => d.state === 'ready')) warn.push('No model is ready yet; chat will be empty until one lands.');
    $('#installwarn').textContent = warn.join(' ');
    $('#install-later').hidden = buildDone || buildRunning;
  }

  function installRow({ key, title, state, pct, detail, error, action }) {
    const cls = state === 'done' ? ' done' : state === 'failed' ? ' failed' : '';
    return `<div class="installrow${cls}" data-row="${esc(key)}">
      <div class="head"><b>${esc(title)}</b><span class="state">${esc(state)}</span></div>
      <div class="bar"><i style="width:${Math.max(0, Math.min(100, Number(pct) || 0))}%"></i></div>
      <div class="detail"><span>${detail}</span><span>${state === 'running' ? 'working…' : ''}</span></div>
      ${error ? `<div class="err">${esc(error)}</div>` : ''}
      ${action ? `<div class="act">${action}</div>` : ''}
    </div>`;
  }

  function renderDone(st) {
    const state = (st && st.state) || (app.data && app.data.state) || {};
    const setup = (st && st.setup) || (app.data && app.data.setup) || {};
    const downloads = (st && st.downloads) || (app.data && app.data.downloads) || [];
    const ready = downloads.filter((d) => d.state === 'ready');
    const classes = (state.sailing && state.sailing.classes) || [];
    const store = setup.store || {};
    const build = setup.build || {};
    const cards = [
      ['Ships', classes.length ? classes.join(', ') : 'Chat only', classes.length ? 'The classes you chose to sail' : 'You can add sailing later'],
      ['Models', ready.length ? `${ready.length} ready` : 'None yet', ready.length ? ready.map((d) => d.label).join(', ') : 'Add one from the dashboard'],
      ['Records', store.mode === 'hosted' ? 'Hosted Postgres' : 'Local Postgres', store.url || 'data/postgres'],
      ['Dashboard', build.built ? 'Built' : 'Not built', build.built ? 'Ready to serve' : 'Run the build command in the terminal'],
    ];
    $('#donecards').innerHTML = cards
      .map(
        ([k, v, s]) => `<div class="donecard"><span class="k">${esc(k)}</span><b>${esc(v)}</b><span>${esc(s)}</span></div>`,
      )
      .join('');
    const chat = $('#chatlink');
    if (build.built) {
      chat.hidden = false;
      if (ready.length) {
        const first = (app.cat.models || []).find((m) => m.repo === ready[0].repo);
        const key = first ? first.key : '';
        chat.href = key ? `/chat?model=${encodeURIComponent(key)}` : '/chat';
        chat.textContent = `Chat to ${ready[0].label}`;
      } else {
        chat.href = '/chat';
        chat.textContent = 'Open chat';
      }
    } else {
      chat.hidden = true;
    }
    const open = document.querySelector('a[href="/"].secondary');
    if (open) open.hidden = !build.built;
    const queue = $('#queuelink');
    queue.hidden = !classes.length;
    $('#donewarn').textContent = (app.warnings || []).join(' ');
  }

  function renderRail(step) {
    const idx = STEPS.indexOf(step);
    $$('#steps li').forEach((li) => {
      const i = STEPS.indexOf(li.dataset.step);
      li.classList.toggle('current', i === idx);
      li.classList.toggle('done', i < idx);
    });
  }

  function show(step) {
    if (!STEPS.includes(step)) step = 'welcome';
    app.step = step;
    $$('.step').forEach((s) => {
      s.hidden = s.dataset.step !== step;
    });
    renderRail(step);
    if (step === 'sail') renderClasses();
    if (step === 'models') {
      renderBands();
      renderModels();
    }
    if (step === 'store') {
      renderStoreStatus((app.data && app.data.setup && app.data.setup.store) || {});
    }
    if (step === 'install') {
      startInstall().finally(startPolling);
    } else {
      stopPolling();
    }
    if (step === 'done') renderDone(app.data);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  async function saveAnswer(step, value) {
    const out = await api('answer', { step, value });
    applyState(out.state);
    return out;
  }

  async function refresh() {
    const st = await api('state');
    app.data = { ...(app.data || {}), ...st };
    applyState(st.state);
    renderMachine();
    if (app.step === 'store') renderStoreStatus(st.setup && st.setup.store);
    if (app.step === 'install') renderInstall(st);
    if (app.step === 'done') renderDone(st);
    return st;
  }

  function startPolling() {
    if (app.poll) return;
    app.poll = setInterval(async () => {
      try {
        const st = await api('state');
        app.data = { ...(app.data || {}), ...st };
        if (app.step === 'install') {
          renderInstall(st);
          const running =
            (st.jobs && Object.values(st.jobs).some((j) => j && j.state === 'running')) ||
            (st.downloads || []).some((d) => ['queued', 'downloading', 'verifying'].includes(d.state));
          if (!running) {
            // one more read after the last job settles, then stop
            clearInterval(app.poll);
            app.poll = null;
          }
        } else if (app.step === 'done') {
          renderDone(st);
          clearInterval(app.poll);
          app.poll = null;
        }
      } catch (e) {
        clearInterval(app.poll);
        app.poll = null;
        fail(e.message);
      }
    }, 1200);
  }

  function stopPolling() {
    if (app.poll) {
      clearInterval(app.poll);
      app.poll = null;
    }
  }

  async function startDownloads() {
    // idempotent on the server: cached models are marked ready, queued ones are not duplicated, and
    // a model added after a first pass is queued on the next call.
    const repos = Array.from(app.models);
    if (!repos.length) return;
    await api('downloads', { repos });
  }

  async function startStoreSetup() {
    if (app.started.store) return;
    const st = (app.data && app.data.setup && app.data.setup.store) || {};
    if (st.locked) {
      // THORP_PG owns the address: there is no local cluster to create behind its back
      app.started.store = true;
      return;
    }
    if (st.ready && app.storeMode === 'local' && !app.storeUrl) {
      app.started.store = true;
      return;
    }
    app.started.store = true;
    try {
      await api('store/setup', { mode: app.storeMode, url: app.storeUrl });
    } catch (e) {
      app.started.store = false;
      throw e;
    }
  }

  async function startBuild() {
    if (app.started.build) return;
    const st = app.data || {};
    if (st.setup && st.setup.build && st.setup.build.built) return;
    if (!(st.setup && st.setup.build && st.setup.build.can_build)) return;
    app.started.build = true;
    try {
      await api('build', {});
    } catch (e) {
      app.started.build = false;
      throw e;
    }
  }

  async function startInstall() {
    try {
      const st = await refresh();
      const store = (st.setup && st.setup.store) || {};
      const build = (st.setup && st.setup.build) || {};
      const jobs = st.jobs || {};
      // The store step's Continue normally starts this; a reload lands here with the flags empty.
      if (!store.ready && !(jobs.store && jobs.store.state === 'running')) {
        await startStoreSetup();
      } else if (store.ready) {
        app.started.store = true;
      }
      await startDownloads();
      if (!build.built && build.can_build && !(jobs.build && jobs.build.state === 'running')) {
        await startBuild();
      }
      const after = await refresh();
      renderInstall(after);
    } catch (e) {
      fail(e.message);
    }
  }

  async function finish() {
    try {
      const out = await api('finish', {});
      app.warnings = out.warnings || [];
      await refresh();
      show('done');
    } catch (e) {
      fail(e.message);
    }
  }

  // ----- events
  function bind() {
    $('#begin').addEventListener('click', async () => {
      try {
        clearError();
        await saveAnswer('welcome', {});
        show('sail');
      } catch (e) {
        fail(e.message);
      }
    });

    $$('[data-sail]').forEach((b) =>
      b.addEventListener('click', () => {
        app.sail = b.dataset.sail === 'yes';
        $$('[data-sail]').forEach((x) => x.classList.toggle('selected', x === b));
        if (app.sail && app.classes.size === 0) {
          const recommended = ((app.cat && app.cat.classes) || []).find((c) => c.recommended);
          if (recommended) app.classes.add(recommended.preset);
        }
        if (!app.sail) app.classes.clear();
        renderClasses();
      }),
    );

    $('#classcards').addEventListener('click', (e) => {
      const b = e.target.closest('[data-preset]');
      if (!b) return;
      const preset = b.dataset.preset;
      if (app.classes.has(preset)) app.classes.delete(preset);
      else app.classes.add(preset);
      renderClasses();
    });

    $('#sail-next').addEventListener('click', async () => {
      try {
        clearError();
        await saveAnswer('sail', { enabled: app.sail === true, classes: Array.from(app.classes) });
        show('models');
      } catch (e) {
        fail(e.message);
      }
    });

    $('#bandcards').addEventListener('click', (e) => {
      const b = e.target.closest('[data-band]');
      if (!b) return;
      const key = b.dataset.band;
      if (app.bands.has(key)) app.bands.delete(key);
      else app.bands.add(key);
      // a model whose band is switched off cannot stay selected
      for (const repo of Array.from(app.models)) {
        const m = (app.cat.models || []).find((x) => x.repo === repo);
        if (m && !app.bands.has(m.band)) app.models.delete(repo);
      }
      renderBands();
      renderModels();
    });

    $('#models').addEventListener('change', (e) => {
      const input = e.target.closest('input[data-repo]');
      if (!input) return;
      if (input.checked) app.models.add(input.dataset.repo);
      else app.models.delete(input.dataset.repo);
      renderModels();
    });

    $('#recommend').addEventListener('click', () => {
      for (const m of app.cat.models || []) {
        if (app.bands.has(m.band) && m.recommended) app.models.add(m.repo);
      }
      renderModels();
    });
    $('#clearmodels').addEventListener('click', () => {
      app.models.clear();
      renderModels();
    });

    $('#models-next').addEventListener('click', async () => {
      try {
        clearError();
        await saveAnswer('models', { bands: Array.from(app.bands), selected: Array.from(app.models) });
        await startDownloads();
        show('store');
      } catch (e) {
        fail(e.message);
      }
    });

    $('#skipmodels').addEventListener('click', async () => {
      try {
        clearError();
        app.models.clear();
        await saveAnswer('models', { bands: Array.from(app.bands), selected: [] });
        show('store');
      } catch (e) {
        fail(e.message);
      }
    });

    $$('[data-store]').forEach((b) =>
      b.addEventListener('click', async () => {
        if (b.disabled) return;
        app.storeMode = b.dataset.store;
        $$('[data-store]').forEach((x) => x.classList.toggle('selected', x === b));
        if (app.storeMode === 'local') app.storeUrl = '';
      }),
    );

    $('#storetest').addEventListener('click', async () => {
      const url = $('#storeurl').value.trim();
      if (!url) return;
      try {
        const out = await api('store/test', { url });
        $('#storetestmsg').textContent = out.ok
          ? `Answers: PostgreSQL ${out.version || '?'}${out.schema ? `, schema ${out.schema}` : ', no Thorp schema yet'}`
          : `No answer: ${out.error || 'unknown error'}`;
      } catch (e) {
        $('#storetestmsg').textContent = e.message;
      }
    });

    $('#storeuse').addEventListener('click', async () => {
      const url = $('#storeurl').value.trim();
      if (!url) return;
      app.storeMode = 'hosted';
      app.storeUrl = url;
      try {
        clearError();
        await saveAnswer('store', { mode: app.storeMode, url: app.storeUrl });
        await startStoreSetup();
        show('install');
      } catch (e) {
        fail(e.message);
      }
    });

    $('#storesetup').addEventListener('click', async () => {
      try {
        clearError();
        await refresh();
        const st = (app.data && app.data.setup && app.data.setup.store) || {};
        if (st.missing && st.missing.length && !st.ready) {
          fail(`Postgres is not installed. Run \`${st.install_hint || 'brew install postgresql@17'}\`, then press Retry.`);
          return;
        }
        app.storeMode = 'local';
        app.storeUrl = '';
        app.started.store = false;
        await saveAnswer('store', { mode: 'local', url: '' });
        await startStoreSetup();
        show('install');
      } catch (e) {
        app.started.store = false;
        fail(e.message);
      }
    });

    $('#store-next').addEventListener('click', async () => {
      try {
        clearError();
        await refresh();
        if (app.storeMode === 'local') {
          const st = (app.data && app.data.setup && app.data.setup.store) || {};
          if (st.missing && st.missing.length && !st.ready) {
            fail(`Postgres is not installed. Run \`${st.install_hint || 'brew install postgresql@17'}\`, then press Retry.`);
            return;
          }
        }
        await saveAnswer('store', { mode: app.storeMode, url: app.storeUrl });
        app.started.store = false;
        await startStoreSetup();
        show('install');
      } catch (e) {
        app.started.store = false;
        fail(e.message);
      }
    });

    $('#install-back').addEventListener('click', () => show('store'));

    $('#finish').addEventListener('click', finish);

    $('#installrows').addEventListener('click', async (e) => {
      const b = e.target.closest('[data-act]');
      if (!b) return;
      try {
        clearError();
        if (b.dataset.act === 'store') {
          app.started.store = false;
          await startStoreSetup();
        } else if (b.dataset.act === 'build') {
          app.started.build = false;
          await startBuild();
        } else if (b.dataset.act === 'download') {
          await api('downloads', { repos: [b.dataset.repo] });
        } else if (b.dataset.act === 'cancel') {
          await api('downloads/cancel', { repo: b.dataset.repo });
        }
        const st = await refresh();
        renderInstall(st);
        startPolling();
      } catch (err) {
        fail(err.message);
      }
    });

    $$('[data-back]').forEach((b) =>
      b.addEventListener('click', () => {
        clearError();
        show(b.dataset.back);
      }),
    );
  }

  async function boot() {
    bind();
    renderMachine();
    if (!TOKEN) {
      fail('Open the setup link printed in the terminal: it carries the one-time token this page needs.');
      $$('button').forEach((b) => (b.disabled = true));
      return;
    }
    try {
      const [cat, st] = await Promise.all([api('catalogue'), api('state')]);
      app.cat = cat;
      app.data = st;
      applyState(st.state);
      renderMachine();
      renderWelcome();
      renderClasses();
      renderBands();
      renderModels();
      renderStoreStatus(st.setup && st.setup.store);
      // an unanswered sail question starts with the recommended class in view (300k on a Mac)
      if (app.sail === null && app.classes.size === 0) {
        const recommended = (cat.classes || []).find((c) => c.recommended);
        if (recommended) app.classes.add(recommended.preset);
        renderClasses();
      }
      show(st.state.completed_at ? 'done' : st.state.step || 'welcome');
    } catch (e) {
      fail(`The first run could not read its state: ${e.message}`);
    }
  }

  boot();
})();
