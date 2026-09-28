/* Offline household network. No requests, external libraries, or layout mutation. */
(() => {
  'use strict';
  const data = JSON.parse(document.getElementById('network-data').textContent);
  const nodes = data.nodes || [];
  const edges = data.edges || [];
  const meta = data.meta || {};
  const $ = id => document.getElementById(id);
  const finite = value => typeof value === 'number' && Number.isFinite(value);
  const number = value => Number(value || 0).toLocaleString('en-GB');
  const compact = value => Number(value || 0) >= 1e6 ? `${(value / 1e6).toFixed(2)}m` : number(value);
  const safePositive = value => finite(value) && value > 0;
  const colors = { r: '#2563eb', negative: '#eab308', mi: '#8061ae', muted: '#c1cbbd', ink: '#143f31' };
  const observedMeans = nodes.map(node => node.mean).filter(finite);
  const minMean = observedMeans.length ? Math.min(...observedMeans) : 0;
  const maxMean = observedMeans.length ? Math.max(...observedMeans) : 0;
  const middleMean = observedMeans.length ? observedMeans.reduce((sum, value) => sum + value, 0) / observedMeans.length : 0;
  // Yellow is the mean of household means; each side uses its own quadratic scale.
  const consumptionColor = value => {
    if (!finite(value)) return colors.muted;
    let fraction = 0.5;
    if (value < middleMean && middleMean > minMean) fraction = 0.5 * Math.pow(Math.max(0, (value - minMean) / (middleMean - minMean)), 2);
    if (value > middleMean && maxMean > middleMean) fraction = 0.5 + 0.5 * Math.pow(Math.min(1, (value - middleMean) / (maxMean - middleMean)), 2);
    return `hsl(${120 * (1 - fraction)}, 72%, 40%)`;
  };
  const nodeColors = nodes.map(node => consumptionColor(node.mean));
  const nodeById = new Map(nodes.map((node, index) => [String(node.id).toUpperCase(), index]));
  let pairFile = null;
  let pairDataOffset = 0;
  let pairRequest = 0;
  function pairNumber(value, signed = false) {
    return Number.isFinite(value) ? `${signed && value > 0 ? '+' : ''}${value.toFixed(6)}` : 'Unavailable';
  }
  async function comparePair(event) {
    if (event) event.preventDefault();
    const request = ++pairRequest;
    $('pair-results').hidden = true;
    const a = nodeById.get($('pair-a').value.trim().toUpperCase());
    const b = nodeById.get($('pair-b').value.trim().toUpperCase());
    if (a === undefined || b === undefined) { $('pair-status').textContent = 'Choose two valid household IDs from the suggestions.'; return; }
    if (a === b) { $('pair-status').textContent = 'Choose two different households.'; return; }
    const s = Math.min(a,b), t = Math.max(a,b);
    let pair = edges.find(edge => edge.s === s && edge.t === t);
    try {
      if (pairFile) {
        const index = s * (2 * nodes.length - s - 1) / 2 + t - s - 1;
        const bytes = await pairFile.slice(pairDataOffset + index * 10, pairDataOffset + index * 10 + 10).arrayBuffer();
        if (bytes.byteLength !== 10) throw new Error('Pair file is incomplete.');
        const view = new DataView(bytes);
        pair = { r: view.getFloat32(0,true), mi: view.getFloat32(4,true), n: view.getUint16(8,true) };
      }
      if (request !== pairRequest) return;
      if (!pair) {
        $('pair-status').textContent = 'This pair is outside the sparse graph. Open “Load all household pairs” below and choose household-pairs.gspairs to show its exact metrics.';
        document.querySelector('.pair-file-details').open = true;
        return;
      }
      $('pair-r').textContent = pairNumber(pair.r, true);
      $('pair-mi').textContent = pairNumber(pair.mi);
      $('pair-n').textContent = number(pair.n);
      $('pair-results').hidden = false;
      $('pair-status').textContent = `${nodes[a].id} ↔ ${nodes[b].id}. ${meta.miAlgorithm === 1 ? `JIDT KSG-1, k=${meta.miK}` : `JIDT binned MI, up to ${meta.miBins ?? 8} bins`}. ${pair.n < (meta.minOverlap ?? 1000) ? 'Insufficient shared readings; both metrics unavailable.' : !finite(pair.r) ? 'Pearson correlation is undefined for a constant series.' : 'Exact stored pair values; rounded to six decimal places.'}`;
    } catch(error) { if (request === pairRequest) $('pair-status').textContent = error.message; }
  }
  $('pair-form').addEventListener('submit', comparePair);
  ['pair-a','pair-b'].forEach(id => $(id).addEventListener('input', () => { ++pairRequest; $('pair-results').hidden = true; $('pair-status').textContent = 'Press Compare pair to update both metrics.'; }));
  let fileRequest = 0;
  $('pair-file').addEventListener('change', async () => {
    const request = ++fileRequest;
    ++pairRequest; pairFile = null; $('pair-results').hidden = true;
    const file = $('pair-file').files[0];
    if (!file) return;
    try {
      const prefix = await file.slice(0,12).arrayBuffer();
      if (prefix.byteLength !== 12 || new TextDecoder().decode(prefix.slice(0,8)) !== 'GSPAIR01') throw new Error('Choose a GSclone .gspairs results file.');
      const length = new DataView(prefix).getUint32(8,true);
      if (length > 2000000 || length < 2) throw new Error('Invalid pair-file header.');
      const header = JSON.parse(await file.slice(12,12+length).text());
      if (header.format !== 'GSclone-pairs-v1' || header.sourceSha256 !== meta.sourceSha256 ||
          header.miEstimator !== meta.miEstimator || (header.miAlgorithm ?? null) !== (meta.miAlgorithm ?? null) ||
          (header.miK ?? null) !== (meta.miK ?? null) || (header.miBins ?? null) !== (meta.miBins ?? null) ||
          header.minOverlap !== meta.minOverlap || !Array.isArray(header.ids) || header.ids.length !== nodes.length ||
          !header.ids.every((id,i) => id === nodes[i].id) || header.count !== nodes.length*(nodes.length-1)/2 ||
          file.size !== 12+length+header.count*10) throw new Error('This file does not match the dataset and MI estimator in this HTML.');
      if (request !== fileRequest) return;
      pairFile = file; pairDataOffset = 12+length;
      $('pair-file-status').textContent = `All ${number(header.count)} household pairs are ready. Nothing uploaded.`;
      if ($('pair-a').value && $('pair-b').value) await comparePair();
    } catch(error) { if (request === fileRequest) $('pair-file-status').textContent = error.message; }
  });
  const adjacency = Array.from({ length: nodes.length }, () => []);
  edges.forEach(edge => {
    if (Number.isInteger(edge.s) && Number.isInteger(edge.t) && adjacency[edge.s] && adjacency[edge.t]) {
      adjacency[edge.s].push(edge);
      adjacency[edge.t].push(edge);
    }
  });
  let metric = 'r';
  let selected = null;
  let hovered = null;
  let globalEdges = [];
  let selectionEdges = [];
  let selectionNeighbors = new Set();
  let lastRenderedEdges = [];
  let width = 0;
  let height = 0;
  let pixelRatio = 1;
  let fitScale = 1;
  let view = { x: 0, y: 0, scale: 1 };
  let drag = null;
  const pointers = new Map();
  let pinch = null;
  let renderQueued = false;
  const canvas = $('network');
  const ctx = canvas.getContext('2d');
  const stage = $('graph-stage');
  const score = edge => metric === 'r' ? Math.abs(edge.r) : edge.mi;
  const hasMetric = edge => finite(edge[metric]) && score(edge) > 0;
  const edgeColor = edge => metric === 'mi' ? colors.mi : edge.r < 0 ? colors.negative : colors.r;
  const sorted = {
    r: edges.filter(edge => finite(edge.r) && Math.abs(edge.r) > 0).sort((a, b) => Math.abs(b.r) - Math.abs(a.r) || a.s - b.s || a.t - b.t),
    mi: edges.filter(edge => finite(edge.mi) && edge.mi > 0).sort((a, b) => b.mi - a.mi || a.s - b.s || a.t - b.t)
  };
  const maxMi = sorted.mi[0]?.mi || 0.01;
  const candidateMi = edges.filter(edge => finite(edge.mi) && edge.mi >= 0);
  const meanMi = candidateMi.length ? candidateMi.reduce((sum, edge) => sum + edge.mi, 0) / candidateMi.length : 0;
  // Fixed candidate-population anchors: filtering never changes a given edge's style.
  function miStyle(value) {
    if (!(value > 0)) return { width: 0, opacity: 0 };
    if (value <= meanMi && meanMi > 0) {
      const q = Math.pow(value / meanMi, 2);
      return { width: 1.5 * q, opacity: 0.7 * q };
    }
    const q = maxMi > meanMi ? Math.pow(Math.min(1, (value - meanMi) / (maxMi - meanMi)), 2) : 0;
    return { width: 1.5 + 1.5 * q, opacity: 0.7 + 0.3 * q };
  }
  const eligibleByMetric = {
    r: nodes.map((node, index) => typeof node.correlationEligible === 'boolean' ? node.correlationEligible : node.eligible !== false && adjacency[index].some(edge => finite(edge.r))),
    mi: nodes.map((node, index) => typeof node.miEligible === 'boolean' ? node.miEligible : node.eligible !== false && adjacency[index].some(edge => finite(edge.mi)))
  };
  const savedThreshold = { r: 0.6, mi: Math.min(0.1, maxMi) };
  const points = nodes.map((node, index) => ({
    x: finite(node.x) ? node.x : Math.cos(index * 2.399963229728653) * Math.sqrt(index + 1),
    y: finite(node.y) ? node.y : Math.sin(index * 2.399963229728653) * Math.sqrt(index + 1)
  }));
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  points.forEach(point => { minX = Math.min(minX, point.x); maxX = Math.max(maxX, point.x); minY = Math.min(minY, point.y); maxY = Math.max(maxY, point.y); });
  if (!points.length) { minX = minY = -1; maxX = maxY = 1; }
  const midpoint = { x: (minX + maxX) / 2, y: (minY + maxY) / 2 };
  points.forEach(point => { point.x -= midpoint.x; point.y -= midpoint.y; });

  function announce(message) { $('network-announcement').textContent = message; }
  function isEligible(index) { return eligibleByMetric[metric][index]; }
  function screenPoint(index) { return { x: points[index].x * view.scale + view.x, y: points[index].y * view.scale + view.y }; }
  function formatMetric(value, signed = true) {
    if (!finite(value)) return 'Unavailable';
    if (metric === 'mi') return value.toFixed(3);
    return `${signed && value > 0 ? '+' : ''}${value.toFixed(3)}`;
  }
  function thresholdLabel(value) { return metric === 'mi' ? `${value.toFixed(2)} nats` : value.toFixed(2); }

  function updateVisibleEdges() {
    const threshold = Number($('threshold').value);
    const budget = Number($('edge-budget').value);
    globalEdges = sorted[metric].filter(edge => score(edge) >= threshold).slice(0, budget);
    $('threshold-output').textContent = thresholdLabel(threshold);
    $('budget-output').textContent = number(budget);
    $('threshold').setAttribute('aria-valuetext', thresholdLabel(threshold));
    $('edge-budget').setAttribute('aria-valuetext', `${number(budget)} edges`);
    updateSelectionEdges();
    updateEdgeStatus();
    scheduleDraw();
  }

  function updateSelectionEdges() {
    selectionEdges = selected === null ? [] : adjacency[selected].filter(hasMetric).slice().sort((a, b) => score(b) - score(a) || a.s - b.s || a.t - b.t).slice(0, 12);
    selectionNeighbors = new Set(selectionEdges.map(edge => edge.s === selected ? edge.t : edge.s));
  }

  function updateEdgeStatus() {
    const globalSet = new Set(globalEdges);
    const extras = selectionEdges.filter(edge => !globalSet.has(edge));
    lastRenderedEdges = globalEdges.concat(extras);
    $('visible-count').textContent = `${number(nodes.length)} households · ${number(globalEdges.length)} filtered edges`;
    $('selected-overlay-note').hidden = selected === null;
    $('selected-overlay-note').textContent = `${selectionEdges.length} selected connections highlighted${extras.length ? ` · ${extras.length} added beyond filter` : ''}`;
    $('graph-empty').hidden = globalEdges.length > 0 || selectionEdges.length > 0;
    $('export-edges').disabled = !lastRenderedEdges.length;
    canvas.setAttribute('aria-label', `Similarity network, not geography. ${nodes.length} households; ${globalEdges.length} filtered ${metric === 'r' ? 'correlation' : 'mutual information'} edges. ${selected === null ? 'Search a household to inspect its connections.' : `Selected ${nodes[selected].id}, ${selectionEdges.length} connections highlighted independently of the filter.`} Arrow keys pan, plus and minus zoom, zero fits, Escape clears selection.`);
  }

  function scheduleDraw() {
    if (renderQueued) return;
    renderQueued = true;
    requestAnimationFrame(() => { renderQueued = false; draw(); });
  }

  function drawEdge(edge) {
    const a = screenPoint(edge.s), b = screenPoint(edge.t);
    if ((a.x < -10 && b.x < -10) || (a.x > width + 10 && b.x > width + 10) || (a.y < -10 && b.y < -10) || (a.y > height + 10 && b.y > height + 10)) return;
    const strength = metric === 'r' ? Math.abs(edge.r) : edge.mi / maxMi;
    // Zero scores are excluded before rendering: they never acquire a positive stroke.
    if (!(strength > 0)) return;
    ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y);
    ctx.strokeStyle = edgeColor(edge);
    const style = metric === 'mi' ? miStyle(edge.mi) : { opacity: 0.04 + 0.81 * Math.min(1, strength), width: 0.25 + 3.75 * Math.min(1, strength) };
    ctx.globalAlpha = style.opacity;
    ctx.lineWidth = style.width;
    ctx.stroke();
  }

  function draw() {
    ctx.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
    ctx.clearRect(0, 0, width, height);
    // Draw each edge once so selection cannot artificially increase its opacity.
    lastRenderedEdges.forEach(drawEdge);
    const zoom = Math.min(2, Math.max(0.8, view.scale / fitScale));
    nodes.forEach((node, index) => {
      if (index === selected || index === hovered || selectionNeighbors.has(index)) return;
      const p = screenPoint(index);
      if (p.x < -6 || p.y < -6 || p.x > width + 6 || p.y > height + 6) return;
      const eligible = isEligible(index);
      ctx.beginPath(); ctx.arc(p.x, p.y, (eligible ? 1.65 : 1.9) * zoom, 0, Math.PI * 2);
      ctx.globalAlpha = selected !== null ? 0.3 : 0.92;
      ctx.fillStyle = nodeColors[index]; ctx.fill();
      if (!eligible) { ctx.strokeStyle = colors.ink; ctx.lineWidth = 0.8; ctx.setLineDash([1, 1]); ctx.stroke(); ctx.setLineDash([]); }
    });
    selectionNeighbors.forEach(index => {
      const p = screenPoint(index);
      ctx.beginPath(); ctx.arc(p.x, p.y, 3.3 * zoom, 0, Math.PI * 2);
      ctx.globalAlpha = 1; ctx.fillStyle = nodeColors[index]; ctx.fill(); ctx.strokeStyle = '#ffffff'; ctx.lineWidth = 1.5; ctx.stroke();
    });
    [hovered, selected].forEach(index => {
      if (index === null) return;
      const p = screenPoint(index);
      ctx.globalAlpha = 1;
      ctx.beginPath(); ctx.arc(p.x, p.y, 8 * zoom, 0, Math.PI * 2); ctx.fillStyle = '#ffffff'; ctx.fill();
      ctx.beginPath(); ctx.arc(p.x, p.y, 5 * zoom, 0, Math.PI * 2); ctx.fillStyle = nodeColors[index]; ctx.fill();
      ctx.font = '600 10px "Segoe UI", Arial, sans-serif';
      const text = String(nodes[index].id), labelWidth = ctx.measureText(text).width;
      const tx = Math.min(width - labelWidth - 8, Math.max(8, p.x + 13 * zoom));
      const ty = Math.min(height - 8, Math.max(16, p.y - 9 * zoom));
      ctx.fillStyle = '#fbfcf8ee'; ctx.fillRect(tx - 3, ty - 12, labelWidth + 6, 16);
      ctx.fillStyle = colors.ink; ctx.fillText(text, tx, ty);
    });
    ctx.globalAlpha = 1;
  }

  function fit() {
    view = { x: width / 2, y: height / 2, scale: fitScale };
    scheduleDraw();
  }

  function resize() {
    const rect = stage.getBoundingClientRect();
    const oldW = width, oldH = height, oldFitScale = fitScale;
    width = Math.max(1, rect.width); height = Math.max(1, rect.height);
    pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.round(width * pixelRatio); canvas.height = Math.round(height * pixelRatio);
    fitScale = Math.min(Math.max(20, width - 100) / Math.max(maxX - minX, 0.01), Math.max(20, height - 140) / Math.max(maxY - minY, 0.01));
    if (!oldW || !oldH) fit();
    else {
      // Preserve the user's zoom relative to a fitted graph, including across
      // desktop/mobile breakpoints. Absolute scale would clip a narrow viewport.
      const ratio = fitScale / oldFitScale;
      view.scale *= ratio;
      view.x = width / 2 + (view.x - oldW / 2) * ratio;
      view.y = height / 2 + (view.y - oldH / 2) * ratio;
      scheduleDraw();
    }
    if (selected !== null) drawProfile(nodes[selected]);
  }

  function zoomBy(factor, x = width / 2, y = height / 2) {
    const scale = Math.max(fitScale * 0.3, Math.min(fitScale * 30, view.scale * factor));
    const ratio = scale / view.scale;
    view.x = x - (x - view.x) * ratio; view.y = y - (y - view.y) * ratio; view.scale = scale;
    scheduleDraw();
  }

  function nearest(x, y) {
    let result = null, distance = 90;
    points.forEach((point, index) => {
      const dx = point.x * view.scale + view.x - x, dy = point.y * view.scale + view.y - y;
      const d = dx * dx + dy * dy;
      if (d < distance) { distance = d; result = index; }
    });
    return result;
  }

  function showTooltip(index, x, y) {
    const tooltip = $('node-tooltip');
    tooltip.hidden = index === null;
    if (index === null) return;
    tooltip.replaceChildren(document.createTextNode(String(nodes[index].id)), document.createElement('br'));
    const detail = document.createElement('span');
    detail.textContent = `${finite(nodes[index].mean) ? nodes[index].mean.toFixed(3) + ' kWh / half hour · ' : ''}${finite(nodes[index].coverage) ? (nodes[index].coverage * 100).toFixed(1) : '—'}% coverage · click to explore`;
    tooltip.appendChild(detail);
    tooltip.style.left = `${Math.min(width - tooltip.offsetWidth - 8, Math.max(8, x + 15))}px`;
    tooltip.style.top = `${Math.min(height - tooltip.offsetHeight - 8, Math.max(8, y + 15))}px`;
  }

  function drawProfile(node) {
    const profile = $('daily-profile');
    const bounds = profile.getBoundingClientRect();
    if (!bounds.width) return;
    profile.width = Math.round(bounds.width * pixelRatio); profile.height = Math.round(bounds.height * pixelRatio);
    const pctx = profile.getContext('2d'); pctx.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
    const values = Array.isArray(node.daily) ? node.daily : [];
    const present = values.filter(finite);
    const w = bounds.width, h = bounds.height;
    const max = Math.max(0, ...present);
    const ceiling = max > 0 ? max * 1.18 : 1;
    pctx.clearRect(0, 0, w, h);
    pctx.strokeStyle = '#e7ece2'; pctx.lineWidth = 0.7;
    [0.25, 0.65, 1].forEach(part => { pctx.beginPath(); pctx.moveTo(0, h * part - 2); pctx.lineTo(w, h * part - 2); pctx.stroke(); });
    if (!present.length) {
      pctx.fillStyle = '#84927f'; pctx.font = '10px "Segoe UI", Arial'; pctx.fillText('No daily readings available', 4, h / 2);
      profile.setAttribute('aria-label', 'No daily readings available.'); return;
    }
    const span = Math.max(values.length - 1, 1);
    let segment = [];
    const flush = () => {
      if (!segment.length) return;
      pctx.beginPath(); pctx.moveTo(segment[0].x, h - 2);
      segment.forEach(point => pctx.lineTo(point.x, point.y));
      pctx.lineTo(segment[segment.length - 1].x, h - 2); pctx.closePath(); pctx.fillStyle = '#e3eee2'; pctx.fill();
      pctx.beginPath(); segment.forEach((point, i) => i ? pctx.lineTo(point.x, point.y) : pctx.moveTo(point.x, point.y));
      pctx.strokeStyle = '#719c7e'; pctx.lineWidth = 1.6; pctx.stroke();
      if (segment.length === 1) { pctx.beginPath(); pctx.arc(segment[0].x, segment[0].y, 2, 0, Math.PI * 2); pctx.fillStyle = '#719c7e'; pctx.fill(); }
      segment = [];
    };
    values.forEach((value, index) => {
      if (!finite(value)) { flush(); return; }
      segment.push({ x: 2 + index / span * (w - 4), y: h - 2 - value / ceiling * (h - 7) });
    }); flush();
    pctx.fillStyle = '#85977d'; pctx.font = '8px "Segoe UI", Arial'; pctx.fillText(`${max.toFixed(2)} max`, 2, 9);
    profile.setAttribute('aria-label', `Daily mean half-hour electricity use for ${node.id}, January 2014: ${values.map((value, index) => `${index + 1}: ${finite(value) ? value.toFixed(3) + ' kWh' : 'missing'}`).join('; ')}. Missing days break the line.`);
  }

  function renderNeighbors() {
    const table = $('neighbor-table'); table.replaceChildren();
    $('neighbor-unit').textContent = metric === 'r' ? 'PEARSON r' : 'MI · NATS';
    $('connection-note').textContent = 'Top 12 available candidate connections. Highlighted links ignore the global edge filter.';
    if (!selectionEdges.length) {
      const empty = document.createElement('p'); empty.className = 'no-neighbors';
      const node = nodes[selected];
      empty.textContent = metric === 'mi' && isEligible(selected) && (node.effectiveBins === 1 || node.standardDeviation === 0)
        ? 'Valid MI is zero for this single-bin series. Zero-strength connections are not drawn.'
        : 'No positive-strength candidate connections are available for this metric.';
      table.appendChild(empty); return;
    }
    selectionEdges.forEach(edge => {
      const index = edge.s === selected ? edge.t : edge.s;
      const button = document.createElement('button'); button.type = 'button'; button.className = 'neighbor-row';
      const label = document.createElement('span'), dot = document.createElement('i'), value = document.createElement('span');
      dot.style.background = edgeColor(edge); dot.setAttribute('aria-hidden', 'true');
      label.append(dot, document.createTextNode(String(nodes[index].id))); value.textContent = formatMetric(edge[metric]);
      button.append(label, value);
      button.title = `${number(edge.n)} overlapping half-hour readings`;
      button.setAttribute('aria-label', `${nodes[index].id}, ${metric === 'r' ? 'Pearson correlation' : 'mutual information'} ${formatMetric(edge[metric])}${metric === 'mi' ? ' nats' : ''}, ${number(edge.n)} overlapping readings. Select household.`);
      button.addEventListener('click', () => selectNode(index, true)); table.appendChild(button);
    });
  }

  function renderSelectedStatus() {
    if (selected === null) return;
    const node = nodes[selected];
    const constant = node.standardDeviation === 0;
    const singleBin = constant || node.effectiveBins === 1;
    let message = 'January 2014 · half-hour electricity consumption';
    if (metric === 'r' && constant) message = 'Constant series: Pearson correlation is undefined. Mutual information may still be valid at zero.';
    else if (!isEligible(selected)) message = `${metric === 'r' ? 'Pearson correlation' : 'Mutual information'} unavailable: insufficient usable observations${metric === 'r' ? ' or variability' : ''}. The household remains searchable.`;
    else if (metric === 'mi' && singleBin) message = 'Constant / single-bin series: MI is 0 nats for pairs meeting the observation threshold. Zero-strength edges are not drawn.';
    else if (finite(node.observations)) message = `${number(node.observations)} usable half-hour observations · January 2014`;
    $('selected-status').textContent = message;
  }

  function selectNode(index, center = false) {
    selected = index; hovered = null; $('node-tooltip').hidden = true;
    $('selection-empty').hidden = selected !== null; $('selection-detail').hidden = selected === null;
    $('search-message').textContent = '';
    updateSelectionEdges(); updateEdgeStatus();
    if (index === null) { $('household-search').value = ''; announce('Household selection cleared.'); scheduleDraw(); return; }
    const node = nodes[index];
    $('household-search').value = node.id;
    $('selected-id').textContent = node.id;
    $('selected-coverage').textContent = finite(node.coverage) ? `${(node.coverage * 100).toFixed(1)}%` : 'Unavailable';
    $('selected-mean').textContent = finite(node.mean) ? `${node.mean.toFixed(3)} kWh` : 'Unavailable';
    $('selected-tariff').textContent = node.tariff || 'Not supplied';
    renderSelectedStatus(); renderNeighbors(); drawProfile(node);
    if (center) { view.scale = Math.max(view.scale, fitScale * 1.5); view.x = width / 2 - points[index].x * view.scale; view.y = height / 2 - points[index].y * view.scale; }
    announce(`Selected ${node.id}. ${selectionEdges.length} strongest candidate connections highlighted.`);
    scheduleDraw();
  }

  function setMetric(next) {
    savedThreshold[metric] = Number($('threshold').value); metric = next;
    document.body.classList.toggle('metric-mi', metric === 'mi');
    $('threshold').max = metric === 'r' ? '1' : String(Math.ceil(maxMi * 100) / 100);
    $('threshold').value = String(savedThreshold[metric]);
    $('threshold-label').textContent = metric === 'r' ? '|r|' : 'MI';
    $('metric-kicker').textContent = metric === 'r' ? 'READING CORRELATION' : 'READING MUTUAL INFORMATION';
    $('metric-description').textContent = metric === 'r'
      ? 'Blue edges show positive correlation; yellow edges show negative correlation. Higher absolute correlation makes an edge thicker and more opaque. Shared routines can produce similar patterns.'
      : 'Mutual information detects dependence beyond a straight-line relationship. Thicker, more opaque purple edges mean higher MI, measured in nats. It has no positive or negative sign.';
    $('graph-legend').innerHTML = metric === 'r'
      ? '<span><i class="legend-line positive"></i>Positive</span><span><i class="legend-line negative"></i>Negative</span><span class="legend-weight">Thicker + more opaque = stronger |r|</span>'
      : `<span><i class="legend-line mi"></i>MI · quadratic scale</span><span class="legend-weight">Mean ${meanMi.toFixed(3)}: 1.5 px / 70% · Max ${maxMi.toFixed(3)}: 3 px / 100%</span>`;
    $('limited-node-legend').textContent = metric === 'r' ? 'Correlation unavailable' : 'MI unavailable';
    updateVisibleEdges(); if (selected !== null) { renderSelectedStatus(); renderNeighbors(); }
    announce(`Edges now show ${metric === 'r' ? 'Pearson correlation' : 'mutual information in nats'}. Household positions are unchanged.`);
  }

  $('search-form').addEventListener('submit', event => {
    event.preventDefault();
    const query = $('household-search').value.trim().toUpperCase();
    if (nodeById.has(query)) selectNode(nodeById.get(query), true);
    else { $('search-message').textContent = query ? 'No matching household. Choose an ID from the suggestions.' : 'Enter a household ID.'; }
  });
  $('household-search').addEventListener('change', () => {
    const query = $('household-search').value.trim().toUpperCase();
    if (nodeById.has(query)) selectNode(nodeById.get(query), true);
  });
  $('example-household').addEventListener('click', () => {
    const index = sorted[metric][0]?.s ?? (nodes.length ? 0 : null);
    if (index !== null) selectNode(index, true);
  });
  $('clear-selection').addEventListener('click', () => selectNode(null));
  document.querySelectorAll('input[name="metric"]').forEach(input => input.addEventListener('change', () => { if (input.checked) setMetric(input.value); }));
  $('threshold').addEventListener('input', updateVisibleEdges);
  $('edge-budget').addEventListener('input', updateVisibleEdges);
  $('zoom-in').addEventListener('click', () => zoomBy(1.35));
  $('zoom-out').addEventListener('click', () => zoomBy(1 / 1.35));
  $('fit').addEventListener('click', fit);
  canvas.addEventListener('wheel', event => {
    event.preventDefault(); const rect = canvas.getBoundingClientRect();
    zoomBy(Math.exp(-Math.max(-200, Math.min(200, event.deltaY)) * 0.002), event.clientX - rect.left, event.clientY - rect.top);
  }, { passive: false });
  canvas.addEventListener('pointerdown', event => {
    if (event.button !== 0) return;
    const rect = canvas.getBoundingClientRect();
    pointers.set(event.pointerId, { x: event.clientX - rect.left, y: event.clientY - rect.top });
    drag = { id: event.pointerId, x: event.clientX, y: event.clientY, startX: event.clientX, startY: event.clientY, offsetX: event.clientX - rect.left, offsetY: event.clientY - rect.top, moved: false };
    if (pointers.size > 1) {
      drag = null; pinch = { ...pinchGeometry(), view: { ...view } }; hovered = null; scheduleDraw();
    }
    canvas.setPointerCapture(event.pointerId); canvas.classList.add('dragging'); $('node-tooltip').hidden = true;
  });
  function pinchGeometry() {
    const [a, b] = Array.from(pointers.values());
    return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2, distance: Math.hypot(a.x - b.x, a.y - b.y) };
  }
  canvas.addEventListener('pointermove', event => {
    const rect = canvas.getBoundingClientRect(), x = event.clientX - rect.left, y = event.clientY - rect.top;
    if (pointers.has(event.pointerId)) pointers.set(event.pointerId, { x, y });
    if (pointers.size > 1) {
      const next = pinchGeometry();
      if (pinch && pinch.distance > 0 && next.distance > 0) {
        const scale = Math.max(fitScale * 0.3, Math.min(fitScale * 30, pinch.view.scale * next.distance / pinch.distance));
        const ratio = scale / pinch.view.scale;
        view = { scale, x: next.x - (pinch.x - pinch.view.x) * ratio, y: next.y - (pinch.y - pinch.view.y) * ratio };
      }
      scheduleDraw(); return;
    }
    if (drag && drag.id === event.pointerId) {
      const dx = event.clientX - drag.x, dy = event.clientY - drag.y;
      if (Math.hypot(event.clientX - drag.startX, event.clientY - drag.startY) > 3) drag.moved = true;
      if (drag.moved) { view.x += dx; view.y += dy; }
      drag.x = event.clientX; drag.y = event.clientY; scheduleDraw(); return;
    }
    const index = nearest(x, y);
    if (hovered !== index) { hovered = index; scheduleDraw(); }
    showTooltip(index, x, y); canvas.style.cursor = index === null ? 'grab' : 'pointer';
  });
  function endPointer(event) {
    if (!pointers.has(event.pointerId)) return;
    if (event.type === 'pointerup' && drag && event.pointerId === drag.id && !drag.moved && pointers.size === 1) selectNode(nearest(drag.offsetX, drag.offsetY));
    pointers.delete(event.pointerId); drag = null; pinch = null;
    if (pointers.size > 1) pinch = { ...pinchGeometry(), view: { ...view } };
    else if (pointers.size === 1) {
      const [id, p] = pointers.entries().next().value, rect = canvas.getBoundingClientRect();
      drag = { id, x: p.x + rect.left, y: p.y + rect.top, startX: p.x + rect.left, startY: p.y + rect.top, offsetX: p.x, offsetY: p.y, moved: true };
    }
    if (!pointers.size) canvas.classList.remove('dragging');
    if (canvas.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId);
  }
  canvas.addEventListener('pointerup', endPointer);
  canvas.addEventListener('pointercancel', endPointer);
  canvas.addEventListener('lostpointercapture', endPointer);
  canvas.addEventListener('pointerleave', () => { if (!drag) { hovered = null; $('node-tooltip').hidden = true; scheduleDraw(); } });
  canvas.addEventListener('keydown', event => {
    const actions = { '+': () => zoomBy(1.3), '=': () => zoomBy(1.3), '-': () => zoomBy(1 / 1.3), '0': fit, Escape: () => selectNode(null), ArrowLeft: () => { view.x += 40; }, ArrowRight: () => { view.x -= 40; }, ArrowUp: () => { view.y += 40; }, ArrowDown: () => { view.y -= 40; } };
    if (actions[event.key]) { event.preventDefault(); actions[event.key](); scheduleDraw(); }
  });
  $('export-edges').addEventListener('click', () => {
    const cell = value => `"${String(value ?? '').replace(/"/g, '""')}"`;
    const selectedSet = new Set(selectionEdges), globalSet = new Set(globalEdges);
    const rows = [['household_a', 'household_b', 'pearson_r', 'mutual_information_nats', 'overlapping_readings', 'active_metric', 'passes_global_filter', 'selected_overlay'], ...lastRenderedEdges.map(edge => [nodes[edge.s].id, nodes[edge.t].id, edge.r, edge.mi, edge.n, metric === 'r' ? 'pearson_r' : 'mutual_information_nats', globalSet.has(edge), selectedSet.has(edge)])];
    const blob = new Blob([rows.map(row => row.map(cell).join(',')).join('\r\n') + '\r\n'], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob), link = document.createElement('a'); link.href = url; link.download = `london-household-edges-2014-01-${metric === 'r' ? 'correlation' : 'mi'}.csv`;
    document.body.appendChild(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 10000);
    announce(`Exported ${lastRenderedEdges.length} visible edges, including selected connections beyond the filter.`);
  });

  // Metadata and method copy use text nodes so embedded source fields cannot add HTML.
  $('household-count').textContent = number(nodes.length);
  $('pair-count').textContent = compact(meta.pairCount ?? nodes.length * (nodes.length - 1) / 2);
  $('reading-count').textContent = number(meta.timestampCount ?? meta.timeSlots ?? meta.slotCount ?? 1488);
  $('limited-node-legend').textContent = 'Correlation unavailable';
  $('consumption-min').textContent = minMean.toFixed(3);
  $('consumption-middle').textContent = middleMean.toFixed(3);
  $('consumption-max').textContent = maxMean.toFixed(3);
  $('node-color-legend').title = `Quadratic scale on each side of the mean: green ${minMean.toFixed(3)}, yellow ${middleMean.toFixed(3)}, red ${maxMean.toFixed(3)} kWh per observed half-hour. The midpoint is the unweighted mean of household January means. Missing readings are excluded.`;
  $('method-data').textContent = `January 1–31, 2014; ${number(nodes.length)} households, ${number(meta.timestampCount ?? meta.timeSlots ?? meta.slotCount ?? 1488)} half-hour slots, ${number(meta.pairCount ?? nodes.length * (nodes.length - 1) / 2)} unordered household pairs evaluated. UK Power Networks Low Carbon London smart-meter data from the London Datastore.`;
  $('method-cleaning').textContent = `Duplicate household/timestamp readings are resolved before analysis. Metrics use only jointly available timestamps, with a minimum of ${number(meta.minOverlap ?? 1000)} paired readings. Missing values are not imputed for either metric. Coverage describes available half-hour slots.`;
  $('method-metrics').textContent = meta.miAlgorithm === 1
    ? `Pearson correlation uses raw half-hour kWh. MI uses JIDT KSG algorithm 1 with k=${meta.miK}, continuous readings, paired-observation standardization, and reproducible tiny noise to break ties. KSG returns nats directly. Negative finite-sample estimates are retained in the complete results; only positive MI is drawn. No temporal exclusion window is applied. Constant variables have MI set to zero and undefined correlation.`
    : `Pearson correlation uses raw half-hour kWh. This displayed dataset uses JIDT's discrete estimator with up to ${meta.miBins ?? 8} quantile bins, converted to nats. Binned MI remains the active complete result while faster KSG execution is investigated. Constant series have undefined correlation.`;
  $('method-network').textContent = `All household pairs are evaluated, but this HTML contains ${number(edges.length)} candidate edges: the union of each household's strongest ${meta.topK ?? 12} neighbors per metric. Filters show a subset; selecting a household adds its strongest candidates. Node hue uses a quadratic scale on each side of the mean household consumption: green at the minimum, yellow at the mean, red at the maximum. Values are January mean kWh per observed half-hour, excluding missing readings. Correlation width and opacity rise linearly with |r|. MI uses a quadratic scale on each side of the fixed mean of nonnegative candidate-edge MI values (including zeros): below the mean, width = 1.5 × (MI / mean)² px and opacity = 70% × (MI / mean)²; above the mean, the squared fraction from mean to maximum increases width from 1.5 to 3 px and opacity from 70% to 100%. Filters do not change these anchors. Complete pair results are in analysis/pairs.npz.`;
  const sourceUrl = typeof meta.source === 'string' ? meta.source : meta.source?.url || meta.sourceUrl;
  if (sourceUrl && /^https?:\/\//.test(sourceUrl)) { $('source-link').href = sourceUrl; $('source-link').hidden = false; }
  if (meta.repository && /^https?:\/\//.test(meta.repository)) $('repository-link').href = meta.repository;
  const options = document.createDocumentFragment();
  nodes.forEach(node => { const option = document.createElement('option'); option.value = node.id; options.appendChild(option); });
  $('household-list').appendChild(options);
  if (!nodes.length) { $('example-household').disabled = true; $('search-message').textContent = 'This file contains no households.'; }
  updateVisibleEdges();
  new ResizeObserver(resize).observe(stage);
  window.addEventListener('resize', () => { if (selected !== null) drawProfile(nodes[selected]); });
  resize();
})();
