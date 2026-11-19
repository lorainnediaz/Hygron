(() => {
  const root = document.getElementById('app');
  const tooltip = document.getElementById('tooltip');
  let autoplayTimer = null;
  let zoomLevel = 1;
  let layoutMode = readSavedLayout();
  let renderedStep = 0;
  let lastWheelZoomAt = 0;
  let lastUploadedCount = null;
  let previousQueueRecords = [];
  let deliverySnapshot = [];
  let deliveryFlashUntil = 0;
  let deliveryFlashCount = 0;
  let deliveryFocusTimer = null;

  const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[c]);
  const post = (action) => window.parent.postMessage({
    isStreamlitMessage: true,
    type: 'streamlit:setComponentValue',
    value: { action, nonce: `${Date.now()}-${Math.random().toString(16).slice(2)}` }
  }, '*');

  function render(args) {
    const a = args || {};
    const step = Math.max(0, Math.min(6, Number(a.walkthrough_step || 0)));
    renderedStep = step;
    const currentViewport = root.querySelector('.flow-viewport');
    const previousScroll = currentViewport
      ? currentViewport.scrollTop
      : readSavedScroll();
    if (autoplayTimer) window.clearInterval(autoplayTimer);

    const packet = a.latest_packet || {};
    const summary = a.latest_summary || {};
    const queueRecords = Array.isArray(a.queue_records) ? a.queue_records : [];
    const uploadedCount = Number(a.uploaded_count || 0);
    if (lastUploadedCount !== null && uploadedCount > lastUploadedCount) {
      deliveryFlashCount = uploadedCount - lastUploadedCount;
      deliverySnapshot = previousQueueRecords.slice(0, deliveryFlashCount);
      deliveryFlashUntil = Date.now() + 3600;
    }
    lastUploadedCount = uploadedCount;
    const deliveryActive = Date.now() < deliveryFlashUntil;
    const queueVisible = queueRecords.length > 0 || step === 4 || deliveryActive || !a.internet_online;
    const sensorStatus = a.sensor_online ? 'ONLINE' : 'OFFLINE';
    const internetStatus = a.internet_online ? 'ONLINE' : 'OFFLINE';
    const packetData = !packet.timestamp ? 'No sensor packet yet' : packet.online === false ?
      'Sensor offline; packet readings unavailable' :
      `${packet.temperature_c} °C · ${packet.relative_humidity_pct}% RH · ${packet.gas_resistance_ohms} Ω`;
    const summaryData = summary.timestamp ?
      `${summary.temp ?? '—'} °C · ${summary.rh ?? '—'}% RH · ${summary.voc_resistance ?? '—'} Ω` :
      'Waiting for the first validated five-minute summary';
    const piStatus = summary.complete ? 'COMPLETE' : summary.timestamp ? 'INCOMPLETE' : 'WAITING';
    const packetStatus = !packet.timestamp ? 'WAITING' : packet.online === false ? 'INCOMPLETE' : 'PACKET READY';
    const statusClass = (value) => ['OFFLINE', 'INCOMPLETE'].includes(value) ? 'error' :
      ['WAITING', 'NO SUMMARY'].includes(value) ? 'pending' : '';

    const stepNames = [
      'Ready to begin', 'BME680 sensor reading', 'ESP32 packet transmission',
      'Raspberry Pi processing', 'Internet queue', 'SQLite database storage',
      'HCI dashboard update'
    ];
    const stepDescriptions = [
      'Start the walkthrough to follow one data cycle from the room sensor to the dashboard.',
      'The virtual BME680 samples room temperature, relative humidity, and gas resistance.',
      'The ESP32 packages the sensor values into 30-second packets for the edge gateway.',
      'The Raspberry Pi validates ten packets and builds one five-minute summary.',
      !a.internet_online
        ? `Internet is offline. ${Number(a.queue_count || 0)} completed ${Number(a.queue_count || 0) === 1 ? 'summary is' : 'summaries are'} being held at the Raspberry Pi until reconnection.`
        : Number(a.queue_count || 0)
          ? `${Number(a.queue_count || 0)} completed ${Number(a.queue_count || 0) === 1 ? 'summary is' : 'summaries are'} waiting in the transmission queue.`
          : 'The summary is ready to send through the simulated Internet link.',
      'When connected, the bridge delivers queued summaries and SQLite stores them locally.',
      'The separate hotel dashboard can read delivered summaries after refresh.'
    ];
    const stepStatus = [
      'READY', sensorStatus, packetStatus, piStatus,
      !a.internet_online ? 'OFFLINE' : Number(a.queue_count || 0) ? 'QUEUED' : 'ONLINE',
      Number(a.cloud_count || 0) ? 'STORED' : 'WAITING', 'READY'
    ];
    const stepData = [
      'No simulation stage has run yet.', packetData,
      `${packet.sampling_interval_seconds || 30}-second interval · ${packet.node_id || a.node_id || 'ESP32 node'}`,
      summaryData,
      `${Number(a.queue_count || 0)} queued summaries · ${internetStatus.toLowerCase()} link`,
      `${Number(a.cloud_count || 0)} stored records · ${Number(a.valid_cloud_count || 0)} complete summaries`,
      `${Number(a.cloud_count || 0)} delivered records available in SQLite`
    ];
    const activeName = stepNames[step];
    const stepLabel = step ? `STEP ${step} OF 6 — ${activeName.toUpperCase()}` : 'READY — START THE WALKTHROUGH';
    const roomLabel = `Room ${String(a.room_id || 'room_101').replace('room_', '')}`;

    const nodes = [
      { id: 1, name: 'BME680 SENSOR', subtitle: 'Temperature · RH · gas resistance', image: 'assets/bme680.png', alt: 'BME680 environmental sensor' },
      { id: 2, name: 'ESP32', subtitle: 'Packages and sends 30-second readings', image: 'assets/esp32.png', alt: 'ESP32 development board' },
      { id: 3, name: 'RASPBERRY PI', subtitle: 'Validates readings · aggregates five-minute summaries', image: 'assets/raspberry-pi.png', alt: 'Raspberry Pi single-board computer' },
      { id: 4, name: 'WI-FI / INTERNET', subtitle: 'Simulated transport to the local cloud store', image: 'assets/wifi.png', alt: 'Wi-Fi symbol' },
      { id: 5, name: 'SQLite DATABASE', subtitle: 'Persists delivered summaries locally', image: 'assets/database.png', alt: 'Database symbol' },
      { id: 6, name: 'HCI DASHBOARD', subtitle: 'Hotel staff view of delivered readings and risk estimates', image: 'assets/dashboard.png', alt: 'Desktop dashboard symbol' }
    ];
    const showReadingDetail = step >= 1 && step <= 3;
    const links = layoutMode === 'horizontal'
      ? ['I²C', 'PACKETS', 'SUMMARY', 'UPLOAD', 'READ']
      : ['I²C SENSOR DATA', '30-SECOND PACKETS', '5-MINUTE SUMMARY', 'SIMULATED DELIVERY', 'READ AFTER REFRESH'];
    const queueTray = queueVisible ? `<aside class="queue-tray ${deliveryActive ? 'is-delivering' : ''} ${!a.internet_online ? 'is-offline' : ''}" aria-live="polite">
      <div class="queue-heading"><span class="eyebrow">TRANSMISSION QUEUE</span><b class="queue-status">${deliveryActive ? `SENDING ${deliveryFlashCount} TO SQLITE` : !a.internet_online ? 'OFFLINE · HELD AT GATEWAY' : queueRecords.length ? 'CONNECTED · PENDING UPLOAD' : 'CONNECTED · QUEUE EMPTY'}</b></div>
      <div class="queue-count"><strong>${Number(a.queue_count || 0)}</strong><span>pending ${Number(a.queue_count || 0) === 1 ? 'summary' : 'summaries'}</span></div>
      <div class="queue-records">${(deliveryActive && deliverySnapshot.length ? deliverySnapshot : queueRecords).slice(0, 3).map((record, index) => `<div class="queue-record ${deliveryActive ? 'is-sending' : ''}"><b>${deliveryActive ? 'Sending' : `Queued #${index + 1}`}</b><span>${esc(String(record.room_id || a.room_id || 'room_101').replace('room_', 'Room '))} · ${esc(record.timestamp || 'Five-minute summary')}</span><small>${record.complete ? 'Complete' : 'Incomplete'} · ${record.temp ?? '—'}°C · ${record.rh ?? '—'}% RH</small></div>`).join('') || `<div class="queue-empty">${deliveryActive ? `Moving ${deliveryFlashCount} summary/s into SQLite…` : !a.internet_online ? 'New summaries will wait here until the connection returns.' : 'No summaries are waiting to upload.'}</div>`}${(deliveryActive ? deliveryFlashCount : Number(a.queue_count || 0)) > 3 ? `<div class="queue-more">+${(deliveryActive ? deliveryFlashCount : Number(a.queue_count || 0)) - 3} more ${deliveryActive ? 'sending' : 'waiting'}</div>` : ''}</div>
      <div class="queue-destination"><span>DESTINATION</span><b>SQLite cloud store</b><strong>${Number(a.cloud_count || 0)} delivered records</strong></div>
    </aside>` : '';

    root.innerHTML = `
      <section class="board-shell">
        <div class="board" id="board">
          <header class="board-header">
            <div class="board-title"><span class="eyebrow">HYGRON · VIRTUAL IOT</span><h2>System Architecture</h2></div>
            <div class="toolbar" aria-label="Walkthrough controls">
              <button type="button" data-action="previous" ${step === 0 ? 'disabled' : ''}>Previous Step</button>
              <button type="button" class="primary" data-action="next">Next Step</button>
              <button type="button" data-action="toggle_play" class="play-button">${a.autoplay ? 'Pause' : 'Play'}</button>
              <button type="button" class="accent" data-action="reset">Reset Simulation</button>
              <button type="button" data-layout-toggle aria-label="Switch to horizontal view">Horizontal view</button>
              <button type="button" data-action="${a.fullscreen ? 'exit_fullscreen' : 'fullscreen'}" aria-label="${a.fullscreen ? 'Exit fullscreen' : 'Open fullscreen view'}">${a.fullscreen ? '⤢ Exit fullscreen' : '⛶ Fullscreen'}</button>
            </div>
          </header>
          <section class="cycle-controls" aria-label="Additional simulation controls">
            <span>${esc(roomLabel)} · ${esc(a.clock || '—')}</span>
            <div>
              <button type="button" data-action="full">Run full 5-min cycle</button>
              <button type="button" class="internet-toggle ${a.internet_online ? 'is-online' : 'is-offline'}" data-action="toggle_internet" role="switch" aria-checked="${Boolean(a.internet_online)}" aria-label="Simulated Internet ${a.internet_online ? 'on' : 'off'}">
                <span>Internet</span><span class="internet-switch-track" aria-hidden="true"><i></i></span><b>${a.internet_online ? 'ON' : 'OFF'}</b>
              </button>
            </div>
          </section>
          <section class="step-status" aria-live="polite">
            <div class="step-copy"><strong>${esc(stepLabel)}</strong><span>${esc(stepDescriptions[step])}</span></div>
            <div class="progress-count">${step}/6</div>
            <div class="progress-track"><span style="width:${step ? (step / 6) * 100 : 0}%"></span></div>
          </section>
          <div class="flow-viewport" aria-label="Vertical system architecture walkthrough">
            <div class="viewport-hud">
              <div class="zoom-controls" role="group" aria-label="Component size controls">
                <span>Zoom</span>
                <button type="button" data-zoom="out" aria-label="Zoom components out">−</button>
                <output data-zoom-value>${Math.round(zoomLevel * 100)}%</output>
                <button type="button" data-zoom="in" aria-label="Zoom components in">+</button>
                <button type="button" data-zoom="reset" aria-label="Reset component zoom">Reset</button>
              </div>
            </div>
            <div class="flow-track">
              ${nodes.map((node) => {
                const status = stepStatus[node.id];
                const state = node.id === step ? 'is-active' : node.id < step ? 'is-past' : 'is-upcoming';
                return `<div class="flow-item ${state}" data-step="${node.id}">
                  <article class="component-card">
                    <img src="${node.image}" alt="${node.alt}">
                    <div class="component-copy"><h3>${node.name}</h3><p>${node.subtitle}</p></div>
                    <span class="status ${statusClass(status)}"><i class="dot"></i>${esc(status)}</span>
                  </article>
                  ${node.id === step && showReadingDetail ? `<aside class="stage-detail" aria-live="polite">
                    <div class="focus-heading">
                      <img src="${node.image}" alt="">
                      <div><span class="eyebrow">SIMULATED DATA</span><h3>${esc(activeName)}</h3></div>
                    </div>
                    <div class="detail-status ${statusClass(stepStatus[step])}"><i class="dot"></i>${esc(stepStatus[step])}</div>
                    <p>${esc(stepDescriptions[step])}</p>
                    <div class="detail-data"><b>Data / activity</b><span>${esc(stepData[step])}</span></div>
                    ${step <= 2 ? `<small>Last reading: ${esc(packet.timestamp || 'Not generated yet')}</small>` : `<small>Summary time: ${esc(summary.timestamp || 'Not generated yet')}</small>`}
                  </aside>` : ''}
                  ${node.id === 4 ? queueTray : ''}
                </div>${node.id < 6 ? `<div class="flow-arrow ${node.id === step ? 'is-active' : ''} ${node.id === 4 && deliveryActive ? 'is-delivering' : ''}" aria-label="${esc(links[node.id - 1])}"><span>${esc(links[node.id - 1])}</span><i></i></div>` : ''}`;
              }).join('')}
            </div>
          </div>
        </div>
      </section>`;

    root.classList.toggle('fullscreen-mode', Boolean(a.fullscreen));
    bindControls();
    applyLayout();
    applyZoom();
    const viewport = root.querySelector('.flow-viewport');
    previousQueueRecords = queueRecords.slice();
    if (deliveryActive) {
      window.setTimeout(() => {
        if (Date.now() < deliveryFlashUntil) return;
        const tray = root.querySelector('.queue-tray');
        if (!tray) return;
        tray.classList.remove('is-delivering');
        root.querySelectorAll('.flow-arrow.is-delivering').forEach((arrow) => arrow.classList.remove('is-delivering'));
        const status = tray.querySelector('.queue-status');
        if (status) status.textContent = `DELIVERED ${deliveryFlashCount} TO SQLITE`;
        tray.querySelectorAll('.queue-record').forEach((row) => {
          row.classList.remove('is-sending');
          const label = row.querySelector('b');
          if (label) label.textContent = 'Stored in SQLite';
        });
        window.setTimeout(() => {
          if (Number(a.queue_count || 0) === 0) tray.remove();
        }, 1800);
      }, 3600);
    }
    viewport.scrollTop = previousScroll;
    viewport.addEventListener('scroll', () => saveScroll(viewport.scrollTop), { passive: true });
    viewport.addEventListener('wheel', (event) => {
      if (!event.ctrlKey) return;
      event.preventDefault();
      const now = performance.now();
      if (now - lastWheelZoomAt < 75) return;
      lastWheelZoomAt = now;
      zoomLevel = Math.max(0.75, Math.min(1.35, zoomLevel + (event.deltaY < 0 ? 0.1 : -0.1)));
      applyZoom();
      window.setTimeout(() => centerActive(), 240);
    }, { passive: false });
    if (deliveryActive && layoutMode === 'vertical') {
      requestAnimationFrame(() => centerNode(4));
      if (deliveryFocusTimer) window.clearTimeout(deliveryFocusTimer);
      deliveryFocusTimer = window.setTimeout(() => centerNode(renderedStep), 5600);
    } else if (step > 0) requestAnimationFrame(() => centerActive());
    else {
      viewport.scrollTop = 0;
      saveScroll(0);
    }
    setTimeout(setFrameHeight, 0);
    if (a.autoplay) autoplayTimer = window.setInterval(() => post('next'), 2600);
  }

  function setFrameHeight() {
    const height = Math.ceil(document.documentElement.scrollHeight);
    window.parent.postMessage({ isStreamlitMessage: true, type: 'streamlit:setFrameHeight', height }, '*');
  }

  function bindControls() {
    root.querySelectorAll('[data-action]').forEach((button) => button.addEventListener('click', () => post(button.dataset.action)));
    root.querySelector('[data-layout-toggle]')?.addEventListener('click', () => {
      layoutMode = layoutMode === 'vertical' ? 'horizontal' : 'vertical';
      saveLayout(layoutMode);
      applyLayout();
      window.setTimeout(() => centerActive(), 240);
    });
    root.querySelectorAll('[data-zoom]').forEach((button) => button.addEventListener('click', () => {
      if (button.dataset.zoom === 'in') zoomLevel = Math.min(1.35, zoomLevel + 0.1);
      if (button.dataset.zoom === 'out') zoomLevel = Math.max(0.75, zoomLevel - 0.1);
      if (button.dataset.zoom === 'reset') zoomLevel = 1;
      applyZoom();
      window.setTimeout(() => centerActive(), 240);
    }));
  }

  function applyZoom() {
    root.style.setProperty('--component-zoom', zoomLevel.toFixed(2));
    const output = root.querySelector('[data-zoom-value]');
    if (output) output.textContent = `${Math.round(zoomLevel * 100)}%`;
  }

  function readSavedLayout() {
    try { return window.sessionStorage.getItem('hygronBoardLayout') === 'horizontal' ? 'horizontal' : 'vertical'; }
    catch { return 'vertical'; }
  }

  function saveLayout(value) {
    try { window.sessionStorage.setItem('hygronBoardLayout', value); }
    catch { /* The selected layout still applies for the current component session. */ }
  }

  function applyLayout() {
    root.classList.toggle('horizontal-mode', layoutMode === 'horizontal');
    const button = root.querySelector('[data-layout-toggle]');
    if (!button) return;
    button.textContent = layoutMode === 'horizontal' ? 'Vertical view' : 'Horizontal view';
    button.setAttribute('aria-label', `Switch to ${layoutMode === 'horizontal' ? 'vertical' : 'horizontal'} view`);
  }

  function centerActive() {
    centerNode(renderedStep);
  }

  function centerNode(step) {
    const viewport = root.querySelector('.flow-viewport');
    const active = step > 0 && root.querySelector(`[data-step="${step}"]`);
    if (!viewport || !active) return;
    const viewportRect = viewport.getBoundingClientRect();
    const activeRect = active.getBoundingClientRect();
    if (layoutMode === 'horizontal') {
      const offset = activeRect.left + activeRect.width / 2 - (viewportRect.left + viewportRect.width / 2);
      viewport.scrollTo({ left: viewport.scrollLeft + offset, behavior: 'smooth' });
    } else {
      const offset = activeRect.top + activeRect.height / 2 - (viewportRect.top + viewportRect.height / 2);
      viewport.scrollTo({ top: viewport.scrollTop + offset, behavior: 'smooth' });
    }
  }

  function readSavedScroll() {
    try { return Number(window.sessionStorage.getItem('hygronFlowScrollTop') || 0); }
    catch { return 0; }
  }

  function saveScroll(value) {
    try { window.sessionStorage.setItem('hygronFlowScrollTop', String(value)); }
    catch { /* Scroll focus still works for the current component session. */ }
  }

  window.addEventListener('message', (event) => {
    const data = event.data || {};
    if (data.type === 'streamlit:render') render(data.args || {});
  });
  window.parent.postMessage({ isStreamlitMessage: true, type: 'streamlit:componentReady', apiVersion: 1 }, '*');
})();
