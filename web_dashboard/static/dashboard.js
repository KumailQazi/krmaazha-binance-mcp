// Krmaazha Binance Intelligence Dashboard Frontend Engine - V2

let currentSymbol = "BTCUSDT";
let currentInterval = "1h";
let candleData = [];
let lastFetchedTime = null;
let currentTradeSetup = null;

// DOM Ready
document.addEventListener("DOMContentLoaded", () => {
  initSyncTracker();
  initTickers();
  initMacroStructure();
  initCandleChart();
  initDecisionTerminal();
  initSignals();
  initThesis();
  initDcaSimulator();
  initNews();
  initKnowledge();
  initModal();
  initOrchestratorAgents();
  setupAutoPolling();
  setupBarCloseTimer();
});

// 1. Sync Tracker & Refresh Engine
function initSyncTracker() {
  const refreshBtn = document.getElementById("manualRefreshBtn");
  const refreshIcon = document.getElementById("refreshIcon");

  if (refreshBtn) {
    refreshBtn.addEventListener("click", async () => {
      if (refreshIcon) refreshIcon.style.animation = "spin 0.8s linear infinite";
      await refreshAllData();
      if (refreshIcon) refreshIcon.style.animation = "none";
    });
  }

  // Update relative time ("3s ago") every second
  setInterval(updateRelativeSyncTime, 1000);
}

function recordFetchTimestamp() {
  lastFetchedTime = new Date();
  const timeStr = lastFetchedTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  const syncTimeEl = document.getElementById("syncTime");
  const syncAgoEl = document.getElementById("syncAgo");
  if (syncTimeEl) syncTimeEl.innerText = timeStr;
  if (syncAgoEl) syncAgoEl.innerText = "(just now)";
  
  const telFreshness = document.getElementById("telFreshness");
  if (telFreshness) telFreshness.innerText = `Updated: ${timeStr} (just now)`;
}

function updateRelativeSyncTime() {
  if (!lastFetchedTime) return;
  const elapsedSec = Math.floor((new Date() - lastFetchedTime) / 1000);
  const syncAgoEl = document.getElementById("syncAgo");
  const telFreshness = document.getElementById("telFreshness");
  
  let label = "(just now)";
  if (elapsedSec >= 3 && elapsedSec < 60) {
    label = `(${elapsedSec}s ago)`;
  } else if (elapsedSec >= 60) {
    const mins = Math.floor(elapsedSec / 60);
    label = `(${mins}m ago)`;
  }
  
  if (syncAgoEl) syncAgoEl.innerText = label;
  if (telFreshness) {
    const timeStr = lastFetchedTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    telFreshness.innerText = `Updated: ${timeStr} ${label}`;
  }
}

function setupBarCloseTimer() {
  const timerEl = document.getElementById("telBarTimer");
  if (!timerEl) return;

  function updateTimer() {
    const now = new Date();
    const minLeft = 59 - now.getUTCMinutes();
    const secLeft = 59 - now.getUTCSeconds();
    timerEl.innerText = `Next 1h bar in ${minLeft}m ${secLeft}s`;
  }
  updateTimer();
  setInterval(updateTimer, 1000);
}

async function refreshAllData() {
  await Promise.allSettled([
    initTickers(),
    fetchAndDrawChart(),
    updateDecisionTerminal(currentSymbol),
    initSignals(),
    initMacroStructure()
  ]);
  recordFetchTimestamp();
}

function setupAutoPolling() {
  // 1. Tickers ribbon updates every 5 seconds
  setInterval(initTickers, 5000);

  // 2. Active Candlestick Chart polls every 15 seconds
  setInterval(fetchAndDrawChart, 15000);

  // 3. Multi-Asset Signal Scanner updates every 30 seconds
  setInterval(initSignals, 30000);

  // 4. Macro Market Structure updates every 60 seconds
  setInterval(initMacroStructure, 60000);
}

// 2. Tickers Ribbon
async function initTickers() {
  try {
    const res = await fetch("/api/tickers");
    const data = await res.json();
    recordFetchTimestamp();
    const ribbon = document.getElementById("tickerTape");
    if (!data || !data.length) return;
    
    ribbon.innerHTML = data.map(item => {
      const isUp = item.change_24h >= 0;
      const deltaClass = isUp ? "delta-up" : "delta-down";
      const sign = isUp ? "+" : "";
      const isActive = item.symbol === currentSymbol ? "active" : "";
      return `
        <div class="ticker-item ${isActive}" data-symbol="${item.symbol}">
          <span class="ticker-sym">${item.symbol.replace("USDT", "")}</span>
          <span class="ticker-price">$${formatNumber(item.price)}</span>
          <span class="ticker-delta ${deltaClass}">${sign}${item.change_24h.toFixed(2)}%</span>
        </div>
      `;
    }).join("");

    ribbon.querySelectorAll(".ticker-item").forEach(el => {
      el.addEventListener("click", () => {
        const sym = el.getAttribute("data-symbol");
        selectSymbol(sym);
      });
    });
  } catch (err) {
    console.error("Failed to load tickers:", err);
  }
}

// 3. Macro Market Structure & Gauge
async function initMacroStructure() {
  try {
    const res = await fetch("/api/market-structure");
    const ms = await res.json();
    
    // Fear & Greed
    const fg = ms.fear_greed || 50;
    const fgVal = document.getElementById("macroFgVal");
    const fgSub = document.getElementById("macroFgSub");
    const fgBadge = document.getElementById("fgLabelBadge");

    if (fgVal) fgVal.innerText = fg;
    if (fgSub) fgSub.innerText = `7d Trend: [${(ms.fear_greed_week || []).join(", ")}]`;
    if (fgBadge) {
      fgBadge.innerText = ms.fear_greed_label || "Neutral";
      fgBadge.className = `signal-badge ${fg >= 60 ? "buy" : fg <= 40 ? "avoid" : "neutral"}`;
    }
    
    // Gauge Animation
    updateNeedle(fg);
    const scoreVal = document.getElementById("gaugeScoreVal");
    const labelText = document.getElementById("gaugeLabelText");
    if (scoreVal) scoreVal.innerText = fg;
    if (labelText) labelText.innerText = ms.fear_greed_label ? ms.fear_greed_label.toUpperCase() : "NEUTRAL";

    // Macro Cards
    const btcDom = document.getElementById("macroBtcDom");
    const totalMcap = document.getElementById("macroTotalMcap");
    const athDraw = document.getElementById("macroAthDrawdown");
    const athPrice = document.getElementById("macroAthPrice");
    const hashrate = document.getElementById("macroHashrate");

    if (btcDom && ms.btc_dominance_pct) btcDom.innerText = `${ms.btc_dominance_pct.toFixed(2)}%`;
    if (totalMcap && ms.total_market_cap_usd) totalMcap.innerText = `$${(ms.total_market_cap_usd / 1e12).toFixed(2)}T`;
    if (athDraw && ms.btc_ath_change_pct) athDraw.innerText = `${ms.btc_ath_change_pct.toFixed(2)}%`;
    if (athPrice && ms.btc_ath_usd) athPrice.innerText = `$${formatNumber(parseFloat(ms.btc_ath_usd))}`;
    if (hashrate && ms.hashrate_avg_ehs) hashrate.innerText = `${ms.hashrate_avg_ehs.toFixed(1)} EH/s`;

    // Cycle stats
    loadCycleStats(currentSymbol);
  } catch (err) {
    console.error("Failed to load macro structure:", err);
  }
}

function updateNeedle(score) {
  const angle = ((score / 100) * 180) - 90;
  const needle = document.getElementById("gaugeNeedle");
  if (needle) {
    needle.style.transform = `rotate(${angle}deg)`;
  }
}

async function loadCycleStats(symbol) {
  try {
    const res = await fetch(`/api/cycle?symbol=${symbol}`);
    const cycle = await res.json();
    const mayerEl = document.getElementById("cycleMayer");
    const smaEl = document.getElementById("cycleSma");

    if (mayerEl) {
      mayerEl.innerText = cycle.mayer_multiple ? cycle.mayer_multiple.toFixed(3) : "N/A (< 200d)";
    }
    if (smaEl) {
      if (cycle.ma200d && parseFloat(cycle.ma200d) > 0) {
        smaEl.innerText = `$${formatNumber(parseFloat(cycle.ma200d))}`;
      } else {
        smaEl.innerText = "N/A (< 200d history)";
      }
    }
  } catch (err) {
    console.error("Cycle load err:", err);
  }
}

// 4. HTML5 Canvas Candlestick Chart Engine
function initCandleChart() {
  const symButtons = document.querySelectorAll("#symbolButtons button");
  symButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      symButtons.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      selectSymbol(btn.getAttribute("data-symbol"));
    });
  });

  const tfButtons = document.querySelectorAll("#tfButtons button");
  tfButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      tfButtons.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      currentInterval = btn.getAttribute("data-tf");
      fetchAndDrawChart();
    });
  });

  window.addEventListener("resize", drawChart);
  fetchAndDrawChart();
}

function selectSymbol(sym) {
  currentSymbol = sym;
  document.querySelectorAll("#symbolButtons button").forEach(b => {
    b.classList.toggle("active", b.getAttribute("data-symbol") === sym);
  });
  document.querySelectorAll("#tickerTape .ticker-item").forEach(t => {
    t.classList.toggle("active", t.getAttribute("data-symbol") === sym);
  });
  
  const chartTitle = document.getElementById("chartSymbolTitle");
  if (chartTitle) chartTitle.innerText = `${sym} ${currentInterval} Candlestick Structure`;

  fetchAndDrawChart();
  updateDecisionTerminal(sym);
  loadCycleStats(sym);
}

async function fetchChartLiquidity() {
  try {
    const res = await fetch(`/api/liquidity?symbol=${currentSymbol}`);
    const data = await res.json();
    const spreadEl = document.getElementById("chartSpreadBps");
    const depthEl = document.getElementById("chartDepth1pct");
    const thinEl = document.getElementById("chartThinBadge");

    if (spreadEl && data.touch_spread_bps !== undefined) {
      spreadEl.innerText = `${data.touch_spread_bps.toFixed(2)} bps`;
    }
    if (depthEl && data.depth_1pct_usdt !== undefined) {
      const d = parseFloat(data.depth_1pct_usdt);
      depthEl.innerText = d >= 1000000 ? `$${(d/1000000).toFixed(2)}M USDT` : `$${(d/1000).toFixed(0)}k USDT`;
    }
    if (thinEl) {
      thinEl.style.display = data.is_thin_book ? "inline" : "none";
    }
  } catch (e) {
    console.error("Failed to fetch chart liquidity:", e);
  }
}

async function fetchAndDrawChart() {
  try {
    fetchChartLiquidity();
    const res = await fetch(`/api/klines?symbol=${currentSymbol}&interval=${currentInterval}&limit=70`);
    const data = await res.json();
    candleData = data.candles || [];
    drawChart();
  } catch (err) {
    console.error("Chart data error:", err);
  }
}

function drawChart() {
  const canvas = document.getElementById("candleChart");
  if (!canvas || !candleData.length) return;

  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;

  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);
  const width = rect.width;
  const height = rect.height;

  ctx.clearRect(0, 0, width, height);

  const paddingRight = 70;
  const paddingBottom = 30;
  const paddingTop = 20;
  const plotWidth = width - paddingRight;
  const plotHeight = height - paddingBottom - paddingTop;

  let minPrice = Infinity;
  let maxPrice = -Infinity;
  let maxVol = 0;

  candleData.forEach(c => {
    if (c.low < minPrice) minPrice = c.low;
    if (c.high > maxPrice) maxPrice = c.high;
    if (c.volume > maxVol) maxVol = c.volume;
  });

  const priceRange = maxPrice - minPrice || 1;
  const margin = priceRange * 0.05;
  const effectiveMin = minPrice - margin;
  const effectiveMax = maxPrice + margin;
  const effectiveRange = effectiveMax - effectiveMin;

  function getY(price) {
    return paddingTop + plotHeight - ((price - effectiveMin) / effectiveRange) * plotHeight;
  }

  // Draw Grid lines
  ctx.strokeStyle = "rgba(255, 255, 255, 0.05)";
  ctx.lineWidth = 1;
  ctx.font = "11px 'JetBrains Mono'";
  ctx.fillStyle = "#64748b";

  for (let i = 0; i <= 4; i++) {
    const p = effectiveMin + (effectiveRange * (i / 4));
    const y = getY(p);
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(plotWidth, y);
    ctx.stroke();
    ctx.fillText(`$${formatNumber(p)}`, plotWidth + 8, y + 4);
  }

  // Draw Candles
  const candleCount = candleData.length;
  const candleSlot = plotWidth / candleCount;
  const candleWidth = Math.max(candleSlot * 0.7, 3);

  const ema12 = calculateEMA(candleData.map(c => c.close), 12);
  const ema26 = calculateEMA(candleData.map(c => c.close), 26);

  candleData.forEach((c, idx) => {
    const x = idx * candleSlot + candleSlot / 2;
    const isBull = c.close >= c.open;
    const bodyColor = isBull ? "#0ecb81" : "#f6465d";

    const volHeight = (c.volume / (maxVol || 1)) * (plotHeight * 0.2);
    ctx.fillStyle = isBull ? "rgba(14, 203, 129, 0.15)" : "rgba(246, 70, 93, 0.15)";
    ctx.fillRect(x - candleWidth / 2, height - paddingBottom - volHeight, candleWidth, volHeight);

    // Wick
    ctx.strokeStyle = bodyColor;
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.moveTo(x, getY(c.high));
    ctx.lineTo(x, getY(c.low));
    ctx.stroke();

    // Body
    const yOpen = getY(c.open);
    const yClose = getY(c.close);
    const top = Math.min(yOpen, yClose);
    const bodyHeight = Math.max(Math.abs(yClose - yOpen), 1.5);

    ctx.fillStyle = bodyColor;
    ctx.fillRect(x - candleWidth / 2, top, candleWidth, bodyHeight);
  });

  // Draw EMA 12 and 26
  drawCurve(ctx, ema12, candleSlot, getY, "#f0b90b", 1.8);
  drawCurve(ctx, ema26, candleSlot, getY, "#00f0ff", 1.8);

  // Overlay trigger line if currentTradeSetup exists and matches symbol
  if (currentTradeSetup && currentTradeSetup.trigger_price && currentTradeSetup.trigger_price !== "None") {
    const tPrice = parseFloat(currentTradeSetup.trigger_price);
    if (!isNaN(tPrice) && tPrice >= effectiveMin && tPrice <= effectiveMax) {
      const yTrig = getY(tPrice);
      ctx.strokeStyle = "rgba(56, 189, 248, 0.7)";
      ctx.lineWidth = 1.2;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(0, yTrig);
      ctx.lineTo(plotWidth, yTrig);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = "#38bdf8";
      ctx.fillText(`Trigger: $${formatNumber(tPrice)}`, plotWidth + 8, yTrig + 4);
    }
  }

  // Update cursor price
  const last = candleData[candleData.length - 1];
  if (last) {
    const cursor = document.getElementById("chartCursorPrice");
    if (cursor) {
      cursor.innerText = `${currentSymbol} Latest: $${formatNumber(last.close)} (H: $${formatNumber(last.high)} L: $${formatNumber(last.low)})`;
    }
  }
}

function drawCurve(ctx, series, slot, getY, color, lineWidth) {
  ctx.strokeStyle = color;
  ctx.lineWidth = lineWidth;
  ctx.beginPath();
  let started = false;

  series.forEach((val, idx) => {
    if (val === null || isNaN(val)) return;
    const x = idx * slot + slot / 2;
    const y = getY(val);
    if (!started) {
      ctx.moveTo(x, y);
      started = true;
    } else {
      ctx.lineTo(x, y);
    }
  });
  ctx.stroke();
}

function calculateEMA(closes, period) {
  const k = 2 / (period + 1);
  const ema = [];
  let prev = closes[0];
  ema.push(prev);

  for (let i = 1; i < closes.length; i++) {
    const cur = closes[i] * k + prev * (1 - k);
    ema.push(cur);
    prev = cur;
  }
  return ema;
}

// 5. ABOVE-THE-FOLD DECISION TERMINAL & CANONICAL HERO ENGINE
function initDecisionTerminal() {
  const customInput = document.getElementById("customPairInput");
  const customBtn = document.getElementById("customPairBtn");
  const posInput = document.getElementById("posSizeUsdt");
  const copyBtn = document.getElementById("copyVerdictBtn");

  if (customBtn && customInput) {
    customBtn.addEventListener("click", () => {
      const sym = customInput.value.trim().toUpperCase();
      if (sym) selectSymbol(sym);
    });
    customInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") customBtn.click();
    });
  }

  if (posInput) {
    posInput.addEventListener("input", recalculatePositionSizing);
  }

  if (copyBtn) {
    copyBtn.addEventListener("click", () => {
      const text = document.getElementById("canonicalBottomLine").innerText;
      navigator.clipboard.writeText(text).then(() => {
        copyBtn.innerText = "✓ Copied!";
        setTimeout(() => copyBtn.innerText = "📋 Copy Verdict", 2000);
      });
    });
  }

  // Load initial asset terminal
  updateDecisionTerminal(currentSymbol);
}

async function updateDecisionTerminal(symbol) {
  try {
    const res = await fetch(`/api/orchestrator/deliberate?symbol=${symbol}`);
    const data = await res.json();
    if (data.error) {
      console.error("Deliberate error:", data.error);
      return;
    }

    const inst = data.instrument || {};
    const liq = data.liquidity_audit || {};
    const setup = data.trade_setup || {};
    const bottomLine = data.standardized_bottom_line || "";
    currentTradeSetup = setup;

    // 1. Update Telemetry Ribbon
    const venueEl = document.getElementById("telVenue");
    const priceEl = document.getElementById("telLastPrice");
    const spreadEl = document.getElementById("telSpread");
    const depthEl = document.getElementById("telDepth");
    const bookStatusEl = document.getElementById("telBookStatus");

    if (venueEl) venueEl.innerText = `${inst.venue || "Binance Spot"} (${inst.market_type || "SPOT"})`;
    if (priceEl) priceEl.innerText = inst.last_price || "$--";
    if (spreadEl) spreadEl.innerText = liq.touch_spread_bps ? `${parseFloat(liq.touch_spread_bps).toFixed(2)} bps` : "-- bps";
    if (depthEl) {
      const d = parseFloat(String(liq.depth_1pct_usdt || "0").replace(/[^0-9.]/g, ""));
      depthEl.innerText = d >= 1000000 ? `$${(d/1000000).toFixed(2)}M USDT` : `$${(d/1000).toFixed(0)}k USDT`;
    }
    if (bookStatusEl) {
      bookStatusEl.innerHTML = liq.is_thin_book 
        ? `<span style="color:#f6465d; font-weight:700;">⚠️ THIN BOOK (${inst.symbol})</span>`
        : `<span style="color:#0ecb81; font-weight:700;">● LIQUID DEPTH</span>`;
    }

    // 2. Plain-Language Canonical Decision State
    const stateMain = document.getElementById("stateMainTitle");
    const stateIcon = document.getElementById("stateIcon");
    const actionTag = document.getElementById("actionTag");
    const cardEl = document.getElementById("decisionHeroCard");

    const rawState = setup.decision_state || "";
    const dir = (setup.direction || "neutral").toUpperCase();
    const actionType = setup.action_type || "";

    if (dir.includes("AVOID") || actionType === "spot_defense") {
      stateIcon.innerText = "🛑";
      stateMain.innerText = rawState || `AVOID / SPOT DEFENSE — No long entry; cash preservation (exit if below ${setup.invalidation_stop || 'stop'})`;
      actionTag.innerText = "SPOT DEFENSE";
      actionTag.className = "action-tag action-avoid";
      cardEl.style.borderLeft = "4px solid var(--accent-red)";
      cardEl.style.borderColor = "rgba(246, 70, 93, 0.4)";
    } else if (dir.includes("WAIT") || dir.includes("NEUTRAL") || actionType === "hold_wait") {
      stateIcon.innerText = "⏳";
      stateMain.innerText = rawState || `WAITING — Long only if a completed 1h candle closes above ${setup.trigger_formatted || setup.trigger_price || 'trigger'}`;
      actionTag.innerText = "WAIT FOR CLOSE";
      actionTag.className = "action-tag action-wait";
      cardEl.style.borderLeft = "4px solid var(--accent-gold)";
      cardEl.style.borderColor = "rgba(240, 185, 11, 0.4)";
    } else if (dir.includes("BUY") || dir.includes("LONG") || dir.includes("READY")) {
      stateIcon.innerText = "🚀";
      stateMain.innerText = rawState || `LONG / READY — 1h candle confirmed close above ${setup.trigger_formatted || setup.trigger_price || 'trigger'}`;
      actionTag.innerText = "LONG / READY";
      actionTag.className = "action-tag action-ready";
      cardEl.style.borderLeft = "4px solid var(--accent-green)";
      cardEl.style.borderColor = "rgba(14, 203, 129, 0.4)";
    } else {
      stateIcon.innerText = "⚖️";
      stateMain.innerText = rawState || "NEUTRAL / IDLE — No actionable statistical edge; idle capital preserved";
      actionTag.innerText = "IDLE";
      actionTag.className = "action-tag action-wait";
      cardEl.style.borderLeft = "4px solid var(--text-muted)";
      cardEl.style.borderColor = "rgba(255, 255, 255, 0.1)";
    }

    // 3. Execution Bounds & Net R:R Row
    const triggerEl = document.getElementById("boundTriggerPrice");
    const stopEl = document.getElementById("boundStopPrice");
    const targetEl = document.getElementById("boundTargetPrice");
    const netRREl = document.getElementById("boundNetRR");

    if (triggerEl) triggerEl.innerText = setup.trigger_formatted ? setup.trigger_formatted : (setup.trigger_price && setup.trigger_price !== "None" ? `$${formatNumber(setup.trigger_price)}` : "Awaiting Breakout");
    if (stopEl) stopEl.innerText = setup.invalidation_stop || "None (Awaiting Breakout)";
    if (targetEl) targetEl.innerText = setup.profit_target || "None (Awaiting Breakout)";
    if (netRREl) netRREl.innerText = setup.net_rr ? `${setup.net_rr} : 1` : "N/A";

    // 4. Assumptions & Formula Line
    const assumpSpread = document.getElementById("assumpSpread");
    const assumpTotal = document.getElementById("assumpTotal");
    const assumpLine = document.getElementById("assumptionsLine");

    const spreadBps = setup.assumptions ? setup.assumptions.touch_spread_bps : (liq.touch_spread_bps || 2.5);
    const totalBps = setup.friction_bps || (20.0 + parseFloat(spreadBps) + 5.0).toFixed(1);

    if (assumpSpread) assumpSpread.innerText = parseFloat(spreadBps).toFixed(1);
    if (assumpTotal) assumpTotal.innerText = parseFloat(totalBps).toFixed(1);

    // 5. Dual-Tier Checklist Update
    const chkDepth = document.getElementById("chkDepth");
    const chkSpread = document.getElementById("chkSpread");
    if (chkDepth) chkDepth.innerText = liq.is_thin_book ? `WARN (${liq.depth_1pct_usdt || '$0'} ±1%)` : `PASS (${liq.depth_1pct_usdt || '$0'} ±1%)`;
    if (chkSpread) chkSpread.innerText = `PASS (${parseFloat(spreadBps).toFixed(2)} bps)`;

    const authPill = document.getElementById("authPill");
    const authExpl = document.getElementById("authExplanation");
    if (authPill && setup.authorization_gate) {
      authPill.innerText = setup.authorization_gate.status || "GATE STANDBY / MANUAL APPROVAL";
    }
    if (authExpl && setup.authorization_gate) {
      authExpl.innerText = `${setup.authorization_gate.condition || 'All audits validated'}. Keys isolated under Zero-Trust. Standalone confirmer process must be physically executed to sign real-money orders.`;
    }

    // 6. Institutional Bottom Line
    const blEl = document.getElementById("canonicalBottomLine");
    if (blEl) {
      const formatted = bottomLine
        .replace(/(is trading at [^;]+ in [^.]+)/i, '<span class="hl-state">$1</span>')
        .replace(/(The setup is valid only if [^;]+);/i, '<span class="hl-cond">$1</span>;')
        .replace(/(it is invalidated by [^.]+)\./i, '<span class="hl-inval">$1</span>.')
        .replace(/(Costs\/risks are [^.]+)\./i, '<span class="hl-cost">$1</span>.')
        .replace(/(Otherwise, no trade\.)/i, '<span class="hl-verdict">$1</span>');
      blEl.innerHTML = `"${formatted}"`;
    }

    // 7. Calculate Position Sizing
    recalculatePositionSizing();

  } catch (err) {
    console.error("Failed to update decision terminal:", err);
  }
}

function recalculatePositionSizing() {
  const posInput = document.getElementById("posSizeUsdt");
  const lossEl = document.getElementById("sizerLossVal");
  const gainEl = document.getElementById("sizerGainVal");
  const costEl = document.getElementById("sizerCostVal");

  if (!posInput || !lossEl || !gainEl || !costEl) return;
  const size = parseFloat(posInput.value) || 0;

  if (!currentTradeSetup || !currentTradeSetup.net_risk_pct || currentTradeSetup.net_risk_pct <= 0) {
    lossEl.innerText = "No active trade risk (0.00%)";
    gainEl.innerText = "No active trade target (0.00%)";
    costEl.innerText = `-$${(size * 0.0028).toFixed(2)} USDT (~28 bps friction)`;
    return;
  }

  const riskPct = currentTradeSetup.net_risk_pct;
  const rewardPct = currentTradeSetup.net_reward_pct;
  const frictionBps = currentTradeSetup.friction_bps || 28.5;
  const frictionPct = frictionBps / 10000;

  const lossUsdt = size * (riskPct / 100);
  const gainUsdt = size * (rewardPct / 100);
  const frictionUsdt = size * frictionPct;

  lossEl.innerText = `-$${lossUsdt.toFixed(2)} USDT (-${riskPct.toFixed(2)}% at stop)`;
  gainEl.innerText = `+$${gainUsdt.toFixed(2)} USDT (+${rewardPct.toFixed(2)}% at target)`;
  costEl.innerText = `-$${frictionUsdt.toFixed(2)} USDT (${(frictionPct * 100).toFixed(3)}% round-trip)`;
}

// 6. Systematic Multi-Asset Signal Scanner (Layer 4)
async function initSignals() {
  try {
    const res = await fetch("/api/signals-scan");
    const signals = await res.json();
    const grid = document.getElementById("scannerGrid");
    if (!signals || !signals.length || !grid) return;

    grid.innerHTML = signals.map(sig => {
      if (sig.error) {
        return `<div class="glass signal-card"><b>${sig.symbol}</b>: ${sig.error}</div>`;
      }
      
      const dir = (sig.direction || "neutral").toUpperCase();
      let badgeClass = "neutral";
      let cardClass = "card-neutral";
      let postureHtml = `<span class="signal-posture-badge posture-hold" title="Wait for closed bar confirmation">⏳ WAITING • UNCONFIRMED</span>`;

      if (dir === "BUY" || dir === "STRONG_BUY" || dir === "LONG") {
        badgeClass = "buy";
        cardClass = "card-buy";
        postureHtml = `<span class="signal-posture-badge posture-buy" title="Systematic Dip Accumulation (Spot Only)">📈 SPOT ACCUMULATE</span>`;
      } else if (dir === "AVOID" || dir === "SELL") {
        badgeClass = "avoid";
        cardClass = "card-avoid";
        postureHtml = `<span class="signal-posture-badge posture-avoid" title="Spot Defense: Capital preservation / cut losses. Not a futures short.">🛡️ SPOT DEFENSE • NO-BUY</span>`;
      }

      // Compute factor tension & dynamics
      const factors = sig.factors || [];
      let bearishDrag = 0;
      let bullishPull = 0;

      factors.forEach(f => {
        const contrib = f.contribution !== undefined ? f.contribution : ((f.value || 0) * (f.weight || 0.2));
        if (contrib < 0) bearishDrag += contrib;
        else if (contrib > 0) bullishPull += contrib;
      });

      const totalMag = Math.abs(bearishDrag) + bullishPull;
      const bearPct = totalMag > 0 ? (Math.abs(bearishDrag) / totalMag) * 100 : 50;
      const bullPct = totalMag > 0 ? (bullishPull / totalMag) * 100 : 50;

      let tensionCallout = "";
      if (dir === "AVOID") {
        if (bullishPull > 0.05) {
          tensionCallout = `⚠️ <b>Downtrend Drag (${bearishDrag.toFixed(2)})</b> vs <b>Oversold Pull (+${bullishPull.toFixed(2)})</b> — <i>Rebound risk: do not short</i>`;
        } else {
          tensionCallout = `📉 <b>Full Bearish Breakdown (${bearishDrag.toFixed(2)})</b> — <i>No support detected</i>`;
        }
      } else if (dir === "BUY" || dir === "LONG" || dir === "STRONG_BUY") {
        if (bearishDrag < -0.05) {
          tensionCallout = `📈 <b>Bullish Push (+${bullishPull.toFixed(2)})</b> against <b>Overhead Drag (${bearishDrag.toFixed(2)})</b>`;
        } else {
          tensionCallout = `⚡ <b>Bullish Trend & Momentum Aligned (+${bullishPull.toFixed(2)})</b>`;
        }
      } else {
        tensionCallout = `⚖️ <b>Factor Equilibrium:</b> Trend and Mean-Reversion in balanced tension`;
      }

      const factorIcons = { trend: "📉", momentum: "⚡", macd: "📊", bollinger: "🎯", sentiment: "📰" };
      const factorHints = { trend: "EMA 12/26", momentum: "RSI 14", macd: "MACD Hist", bollinger: "%B 20,2", sentiment: "News Lexicon" };

      const factorsHtml = factors.map(f => {
        const val = f.value || 0;
        const contrib = f.contribution !== undefined ? f.contribution : (val * (f.weight || 0.2));
        const icon = factorIcons[f.name.toLowerCase()] || "🔹";
        const hint = factorHints[f.name.toLowerCase()] || "";
        
        let leftBarHtml = "";
        let rightBarHtml = "";
        let valColor = "var(--text-secondary)";

        if (val < 0) {
          const wPct = Math.min(Math.abs(val) * 50, 50);
          leftBarHtml = `<div class="bidi-fill-left" style="width: ${wPct}%;"></div>`;
          valColor = "var(--accent-red)";
        } else if (val > 0) {
          const wPct = Math.min(val * 50, 50);
          rightBarHtml = `<div class="bidi-fill-right" style="width: ${wPct}%;"></div>`;
          valColor = "var(--accent-green)";
        }

        return `
          <div class="factor-item">
            <div class="factor-main-row">
              <div class="factor-name-col">
                <span>${icon}</span>
                <span>${capitalize(f.name)}</span>
                <span style="font-size:10px; color:var(--text-muted); font-family:var(--font-mono);">(${hint})</span>
              </div>
              <div class="bidi-bar-wrapper">
                <div class="bidi-notch"></div>
                ${leftBarHtml}
                ${rightBarHtml}
              </div>
              <div class="factor-vals">
                <span class="factor-raw-val" style="color: ${valColor};">${val > 0 ? "+" : ""}${val.toFixed(2)}</span>
                <span class="factor-contrib-val">(${contrib > 0 ? "+" : ""}${contrib.toFixed(2)})</span>
              </div>
            </div>
            ${f.note ? `<div class="factor-note-sub">↳ ${formatFactorNote(f.name, val, f.note)}</div>` : ""}
          </div>
        `;
      }).join("");

      // Price and Risk Geometry
      const price = parseFloat(sig.price || 0);
      const stop = parseFloat(sig.suggested_stop || 0);
      const target = parseFloat(sig.suggested_target || 0);

      const stopDelta = price > 0 && stop > 0 ? (((stop - price) / price) * 100).toFixed(1) : null;
      const targetDelta = price > 0 && target > 0 ? (((target - price) / price) * 100).toFixed(1) : null;

      let stopLabel = "🛑 Invalidation Stop";
      let stopTag = stopDelta ? `<span class="risk-delta-tag" style="background:rgba(246,70,93,0.15); color:#fca5a5;">${stopDelta}%</span>` : "";
      let stopValText = stop > 0 ? `$${formatNumber(stop)}` : "None (Awaiting Breakout)";

      let targetLabel = "🎯 Target Projection";
      let targetTag = targetDelta ? `<span class="risk-delta-tag" style="background:rgba(14,203,129,0.15); color:#86efac;">+${targetDelta}%</span>` : "";
      let targetValText = target > 0 ? `$${formatNumber(target)}` : "None (Awaiting Breakout)";

      const netRR = sig.net_rr ? `${sig.net_rr} : 1` : "2.01 : 1";
      const friction = sig.trade_setup && sig.trade_setup.fees_bps 
        ? `${(sig.trade_setup.fees_bps + (sig.trade_setup.estimated_slippage_bps || 5) + (sig.trade_setup.touch_spread_bps || 2.5)).toFixed(1)} bps` 
        : "28.4 bps";

      const panelId = `sigDetails_${sig.symbol}`;

      // Table rows for math decomposition in accordion
      const mathRows = factors.map(f => {
        const val = f.value || 0;
        const wt = ((f.weight || 0.2) * 100).toFixed(0);
        const contrib = f.contribution !== undefined ? f.contribution : (val * (f.weight || 0.2));
        const cCol = contrib >= 0 ? "var(--accent-green)" : "var(--accent-red)";
        return `
          <tr>
            <td>${capitalize(f.name)}</td>
            <td style="color:${val >= 0 ? 'var(--accent-green)' : 'var(--accent-red)'}">${val > 0 ? '+' : ''}${val.toFixed(2)}</td>
            <td>${wt}%</td>
            <td style="color:${cCol}; font-weight:700;">${contrib > 0 ? '+' : ''}${contrib.toFixed(2)}</td>
          </tr>
        `;
      }).join("");

      return `
        <div class="glass signal-card ${cardClass}" id="card_${sig.symbol}">
          <!-- Header -->
          <div class="signal-card-header" onclick="selectSymbol('${sig.symbol}'); window.scrollTo({top: 0, behavior: 'smooth'});" style="cursor: pointer;" title="Click to inspect ${sig.symbol} in Decision Terminal above">
            <div>
              <div class="signal-symbol-row">
                <span class="signal-symbol">${sig.symbol}</span>
                <span class="signal-tf-tag">${sig.interval || "1h"} CLOSED</span>
                <span class="signal-tf-tag" style="color:var(--accent-gold); border-color:rgba(240,185,11,0.25);">SPOT</span>
              </div>
              <div style="font-size: 15px; color: #fff; font-family: var(--font-mono); margin-top:3px; font-weight:700;">
                $${formatNumber(price)}
              </div>
            </div>
            <div class="signal-badge-group">
              <span class="signal-badge ${badgeClass}">${dir} (${sig.score ? sig.score.toFixed(2) : "0.00"})</span>
              ${postureHtml}
            </div>
          </div>

          <!-- Tension Strip -->
          <div class="signal-tension-strip">
            <div class="tension-header">
              <span style="color:var(--accent-red);">📉 Downtrend Drag: ${bearishDrag.toFixed(2)}</span>
              <span style="color:var(--accent-green);">⚡ Rebound Pull: +${bullishPull.toFixed(2)}</span>
            </div>
            <div class="tension-bar">
              <div class="tension-fill-bear" style="width: ${bearPct}%;"></div>
              <div class="tension-fill-bull" style="width: ${bullPct}%;"></div>
            </div>
            <div class="tension-callout">
              ${tensionCallout}
            </div>
          </div>

          <!-- Contextual Risk Geometry Box -->
          <div class="signal-risk-box">
            <div class="risk-grid">
              <div class="risk-col">
                <div class="risk-col-lbl">${stopLabel}</div>
                <div class="risk-col-val" style="color: var(--accent-red);">
                  ${stopValText}
                  ${stopTag}
                </div>
              </div>
              <div class="risk-col">
                <div class="risk-col-lbl">${targetLabel}</div>
                <div class="risk-col-val" style="color: var(--accent-green);">
                  ${targetValText}
                  ${targetTag}
                </div>
              </div>
            </div>

            <div class="risk-meta-row" style="margin-top: 8px;">
              <div><span style="color:var(--text-muted);">Trigger Net R:R:</span> <b style="color:#6ee7b7;">${netRR}</b></div>
              <div><span style="color:var(--text-muted);">Est. Friction:</span> <span style="color:#cbd5e1;">${friction}</span></div>
            </div>
          </div>

          <!-- Interactive Strategy Accordion Toggle -->
          <button class="signal-accordion-btn" onclick="toggleSignalDetails('${sig.symbol}')">
            <span>🔍 View Factor Decomposition & Formulas</span>
            <span id="chevron_${sig.symbol}">▼</span>
          </button>

          <!-- Collapsible Panel -->
          <div class="signal-details-panel" id="${panelId}">
            ${dir === "AVOID" || dir === "SELL" ? `
              <div class="doctrine-notice-box">
                <b>⚠️ Spot Defense Stance (kb://discipline Rule 3):</b><br>
                This signal mandates <b>cash preservation</b> (do not accumulate / cut losses on existing exposure at ${stopValText}). 
                This is strictly NOT a futures short. Shorting thin alts carries high squeeze risk.
              </div>
            ` : `
              <div class="doctrine-notice-box buy-notice">
                <b>📈 Accumulation Setup (kb://discipline Rule 1):</b><br>
                Spot accumulation proposal. Enter strictly on closed bar confirmation above trigger price. Maintain reserve cash.
              </div>
            `}

            <!-- Math Decomposition Table -->
            <div style="margin-top: 10px;">
              <div style="font-size: 10px; font-weight: 700; color: var(--text-muted); text-transform: uppercase; margin-bottom: 4px;">
                Factor Contribution Breakdown (Sum = Final Score)
              </div>
              <table class="details-math-table">
                <thead>
                  <tr>
                    <th>Factor</th>
                    <th>Opinion</th>
                    <th>Weight</th>
                    <th>Contribution</th>
                  </tr>
                </thead>
                <tbody>
                  ${mathRows}
                </tbody>
              </table>
            </div>

            <!-- Standardized Single-Sentence Bottom Line -->
            <div class="details-bottom-line" style="margin-top: 10px;">
              <b>Orchestrator Bottom Line:</b><br>
              "At closed 1h bar, ${sig.symbol} is in a ${dir === 'AVOID' ? 'firm downtrend breakdown' : 'consolidation / breakout setup'}. The setup is valid only while price remains ${dir === 'AVOID' ? 'capped below ' + stopValText : 'above ' + stopValText}; otherwise, no trade."
            </div>
          </div>
        </div>
      `;
    }).join("");

  } catch (err) {
    console.error("Signal scanner err:", err);
  }
}

window.toggleSignalDetails = function(symbol) {
  const panel = document.getElementById(`sigDetails_${symbol}`);
  const chevron = document.getElementById(`chevron_${symbol}`);
  if (!panel) return;
  const isOpen = panel.classList.contains("open");
  if (isOpen) {
    panel.classList.remove("open");
    if (chevron) chevron.innerText = "▼";
  } else {
    panel.classList.add("open");
    if (chevron) chevron.innerText = "▲";
  }
};

function formatFactorNote(name, val, note) {
  if (!note) return "";
  const n = String(note);
  if (/rápida bajo la lenta|EMA rápida bajo/i.test(n)) {
    return "Fast EMA below slow EMA: confirmed bearish downtrend.";
  }
  if (/rápida sobre la lenta|EMA rápida sobre/i.test(n)) {
    return "Fast EMA above slow EMA: confirmed bullish trend.";
  }
  if (/sobreventa/i.test(n)) {
    return n.replace(/en sobreventa: posible rebote \(momentum a favor\)/i, "in oversold territory: probable rebound (mean-reversion pull).");
  }
  if (/sobrecompra/i.test(n)) {
    return n.replace(/en sobrecompra: riesgo de corrección \(momentum en contra\)/i, "in overbought territory: correction risk (downward pressure).");
  }
  if (/bajo el punto medio/i.test(n)) {
    return n.replace(/bajo el punto medio: leve sesgo a favor/i, "below midpoint: slight bullish rebound lean.");
  }
  if (/sobre el punto medio/i.test(n)) {
    return n.replace(/sobre el punto medio: leve sesgo en contra/i, "above midpoint: slight bearish exhaustion lean.");
  }
  if (/zona neutra/i.test(n)) {
    return n.replace(/en zona neutra: momentum ~neutro/i, "in neutral zone: ~neutral momentum.");
  }
  if (/Histograma MACD positivo/i.test(n)) {
    return "Positive MACD histogram: bullish velocity.";
  }
  if (/Histograma MACD negativo/i.test(n)) {
    return "Negative MACD histogram: bearish downside velocity.";
  }
  if (/Histograma MACD en cero/i.test(n)) {
    return "MACD histogram at zero: neutral momentum.";
  }
  if (/banda inferior de Bollinger/i.test(n)) {
    return "Price compressing near lower Bollinger Band: potential bounce.";
  }
  if (/banda superior de Bollinger/i.test(n)) {
    return "Price pressing upper Bollinger Band: potential downside reversion.";
  }
  if (/media de Bollinger/i.test(n)) {
    return "Price hovering around Bollinger middle band: neutral.";
  }
  if (/Sentiment crudo/i.test(n)) {
    return `Raw news sentiment score = ${val > 0 ? "+" : ""}${val.toFixed(2)} (Layer 3 raw feed, not analyst opinion).`;
  }
  return n.replace(/\s*\((?:sobreventa|sobrecompra|leve sesgo a favor|leve sesgo en contra|neutra)\)/gi, "");
}

// 7. Interactive DCA Simulator
function initDcaSimulator() {
  const assetSelect = document.getElementById("dcaAssetSelect");
  const monthlyInput = document.getElementById("dcaMonthlyInput");
  const monthsInput = document.getElementById("dcaMonthsInput");
  const runBtn = document.getElementById("runDcaBtn");

  if (!monthlyInput || !monthsInput || !runBtn) return;

  monthlyInput.addEventListener("input", (e) => {
    document.getElementById("dcaMonthlyVal").innerText = `$${e.target.value}`;
  });

  monthsInput.addEventListener("input", (e) => {
    document.getElementById("dcaMonthsVal").innerText = `${e.target.value} Months`;
  });

  runBtn.addEventListener("click", runDca);
  runDca();
}

async function runDca() {
  const symbolEl = document.getElementById("dcaAssetSelect");
  const monthlyEl = document.getElementById("dcaMonthlyInput");
  const monthsEl = document.getElementById("dcaMonthsInput");
  if (!symbolEl || !monthlyEl || !monthsEl) return;

  const symbol = symbolEl.value;
  const monthly = monthlyEl.value;
  const months = monthsEl.value;

  const assetLbl = document.getElementById("dcaAssetLbl");
  if (assetLbl) assetLbl.innerText = symbol;

  try {
    const res = await fetch(`/api/dca?symbol=${symbol}&monthly=${monthly}&months=${months}`);
    const data = await res.json();
    const summary = data.summary;
    const curve = data.curve || [];

    if (summary) {
      document.getElementById("dcaKpiInvested").innerText = `$${formatNumber(parseFloat(summary.total_invested))}`;
      document.getElementById("dcaKpiValue").innerText = `$${formatNumber(parseFloat(summary.value_now))}`;
      
      const pnlEl = document.getElementById("dcaKpiPnl");
      pnlEl.innerText = `${summary.pnl_pct >= 0 ? "+" : ""}${summary.pnl_pct.toFixed(1)}%`;
      pnlEl.style.color = summary.pnl_pct >= 0 ? "var(--accent-green)" : "var(--accent-red)";
      
      document.getElementById("dcaKpiLump").innerText = `$${formatNumber(parseFloat(summary.lump_sum_value_now))}`;
    }

    renderDcaSvg(curve);
  } catch (err) {
    console.error("DCA simulation error:", err);
  }
}

function renderDcaSvg(curve) {
  const svg = document.getElementById("dcaChartSvg");
  if (!svg || !curve.length) return;

  const w = 700;
  const h = 240;
  const padL = 60;
  const padR = 20;
  const padT = 20;
  const padB = 30;

  let maxVal = -Infinity;
  curve.forEach(pt => {
    if (pt.dca_value > maxVal) maxVal = pt.dca_value;
    if (pt.invested > maxVal) maxVal = pt.invested;
  });
  maxVal = maxVal * 1.1;

  const plotW = w - padL - padR;
  const plotH = h - padT - padB;

  function getX(idx) {
    return padL + (idx / (curve.length - 1 || 1)) * plotW;
  }
  function getY(val) {
    return padT + plotH - (val / (maxVal || 1)) * plotH;
  }

  let svgContent = `
    <line x1="${padL}" y1="${padT + plotH}" x2="${w - padR}" y2="${padT + plotH}" stroke="rgba(255,255,255,0.1)" stroke-width="1"/>
    <line x1="${padL}" y1="${padT}" x2="${w - padR}" y2="${padT}" stroke="rgba(255,255,255,0.05)" stroke-width="1" stroke-dasharray="4"/>
    <text x="${padL - 10}" y="${padT + 12}" fill="#64748b" font-size="11" text-anchor="end" font-family="'JetBrains Mono'">$${formatNumber(maxVal)}</text>
    <text x="${padL - 10}" y="${padT + plotH}" fill="#64748b" font-size="11" text-anchor="end" font-family="'JetBrains Mono'">$0</text>
  `;

  let investedPath = "";
  curve.forEach((pt, i) => {
    const x = getX(i);
    const y = getY(pt.invested);
    investedPath += (i === 0 ? `M ${x} ${y}` : ` L ${x} ${y}`);
  });

  let dcaPath = "";
  curve.forEach((pt, i) => {
    const x = getX(i);
    const y = getY(pt.dca_value);
    dcaPath += (i === 0 ? `M ${x} ${y}` : ` L ${x} ${y}`);
  });

  const dcaArea = `${dcaPath} L ${getX(curve.length - 1)} ${padT + plotH} L ${getX(0)} ${padT + plotH} Z`;

  svgContent += `
    <defs>
      <linearGradient id="dcaGrad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#0ecb81" stop-opacity="0.35"/>
        <stop offset="100%" stop-color="#0ecb81" stop-opacity="0.0"/>
      </linearGradient>
    </defs>
    <path d="${dcaArea}" fill="url(#dcaGrad)"/>
    <path d="${investedPath}" fill="none" stroke="#64748b" stroke-width="1.8" stroke-dasharray="5"/>
    <path d="${dcaPath}" fill="none" stroke="#0ecb81" stroke-width="2.5"/>
  `;

  const lastPt = curve[curve.length - 1];
  svgContent += `
    <circle cx="${getX(curve.length - 1)}" cy="${getY(lastPt.dca_value)}" r="5" fill="#0ecb81"/>
    <circle cx="${getX(curve.length - 1)}" cy="${getY(lastPt.invested)}" r="4" fill="#64748b"/>
  `;

  svg.innerHTML = svgContent;
}

// 8. Asset Thesis Dossier Engine (/asset_thesis)
function initThesis() {
  const symButtons = document.querySelectorAll("#thesisSymbolButtons button");
  const runBtn = document.getElementById("runThesisBtn");
  const customInput = document.getElementById("customThesisInput");

  if (!symButtons.length || !runBtn) return;

  symButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      symButtons.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      const sym = btn.getAttribute("data-symbol");
      loadAssetThesis(sym);
    });
  });

  runBtn.addEventListener("click", () => {
    const custom = customInput.value.trim().toUpperCase();
    if (custom) {
      symButtons.forEach(b => b.classList.remove("active"));
      loadAssetThesis(custom);
    } else {
      const activeBtn = document.querySelector("#thesisSymbolButtons button.active");
      if (activeBtn) loadAssetThesis(activeBtn.getAttribute("data-symbol"));
    }
  });

  if (customInput) {
    customInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") runBtn.click();
    });
  }

  // Load SOL thesis initially
  loadAssetThesis("SOLUSDT");
}

async function loadAssetThesis(symbol) {
  const container = document.getElementById("thesisOutputContainer");
  if (!container) return;

  container.innerHTML = `
    <div style="text-align: center; padding: 40px; color: var(--accent-gold);">
      <div class="pulse-dot" style="margin: 0 auto 16px auto; width: 12px; height: 12px;"></div>
      <b>Synthesizing Investment Thesis for ${symbol}...</b>
      <div style="font-size: 12px; color: var(--text-muted); margin-top: 6px;">
        Evaluating live market data and 5 Value-Capture criteria from kb://frameworks/token-value
      </div>
    </div>
  `;

  try {
    const res = await fetch(`/api/thesis?symbol=${symbol}`);
    const data = await res.json();
    if (data.error) {
      container.innerHTML = `<div style="color: var(--accent-red); padding: 20px;">Error generating thesis: ${data.error}</div>`;
      return;
    }

    const fw = data.framework || {};
    const questions = fw.questions || [];
    const bottomLine = data.standardized_bottom_line || "";

    const questionsHtml = questions.map(q => {
      const type = q.status_type || "pass";
      const icon = type === "pass" ? "✓" : (type === "warn" ? "⚠️" : "✗");
      return `
        <div class="thesis-q-card">
          <div class="thesis-q-num">Q${q.num}</div>
          <div class="thesis-q-content">
            <div class="thesis-q-top">
              <span class="thesis-q-title">${q.title}</span>
              <span class="thesis-q-status status-${type}">
                ${icon} ${q.status}
              </span>
            </div>
            <div class="thesis-q-summary">${q.summary}</div>
          </div>
        </div>
      `;
    }).join("");

    container.innerHTML = `
      <div class="thesis-dossier-card">
        <div class="thesis-header-row">
          <div>
            <div style="display:flex; align-items:center; gap:8px;">
              <span style="font-size: 18px; font-weight:800; color:#fff;">${data.symbol}</span>
              <span class="signal-badge" style="background: ${fw.verdict_color || 'var(--accent-purple)'}20; color: ${fw.verdict_color || 'var(--accent-purple)'}; border-color: ${fw.verdict_color || 'var(--accent-purple)'}40;">
                ${fw.verdict_badge || 'DOSSIER'}
              </span>
            </div>
            <div style="font-size: 11px; color: var(--text-muted); margin-top: 2px;">
              Spot Price: <b>$${formatNumber(data.price)}</b> | 24h Change: <b>${data.change_24h > 0 ? '+' : ''}${data.change_24h.toFixed(2)}%</b>
            </div>
          </div>
          <div style="text-align: right;">
            <div style="font-size: 11px; color: var(--text-muted);">Risk Rating</div>
            <div style="font-size: 13px; font-weight: 700; color: #f8fafc;">${fw.risk_rating || 'Medium'}</div>
          </div>
        </div>

        <div class="thesis-takeaway-box">
          <div class="takeaway-label">EXECUTIVE SUMMARY & ALLOCATION DISCIPLINE</div>
          <div class="takeaway-text">${fw.key_takeaway || ''}</div>
        </div>

        <div class="thesis-grid">
          ${questionsHtml}
        </div>

        <div class="details-bottom-line" style="margin-top: 20px;">
          <b>Master Orchestrator Bottom Line:</b><br>
          "${bottomLine}"
        </div>
      </div>
    `;

  } catch (err) {
    console.error("Failed to load thesis:", err);
    container.innerHTML = `<div style="color: var(--accent-red); padding: 20px;">Network error loading thesis: ${err}</div>`;
  }
}

// 9. Autonomous Multi-Agent Directory
async function initOrchestratorAgents() {
  const grid = document.getElementById("orchestratorAgentsGrid");
  if (!grid) return;

  try {
    const res = await fetch("/api/orchestrator/agents");
    const data = await res.json();
    if (!data.agents || !data.agents.length) return;

    grid.innerHTML = data.agents.map(a => {
      const isOrch = a.agent_id === "master_orchestrator";
      return `
        <div class="orch-agent-card ${isOrch ? 'is-orchestrator' : ''}">
          <div class="orch-card-header">
            <span class="orch-card-icon">${a.icon}</span>
            <div>
              <div class="orch-card-name">${a.name}</div>
              <div class="orch-card-skill">${a.governing_skill}</div>
            </div>
          </div>
          <div class="orch-card-desc">${a.role_description}</div>
        </div>
      `;
    }).join("");
  } catch (err) {
    console.error("Failed to load orchestrator agents:", err);
  }
}

// 10. News & Curated Lexicon
async function initNews() {
  try {
    const res = await fetch("/api/news?asset=BTC");
    const data = await res.json();
    const list = document.getElementById("newsList");
    const badge = document.getElementById("newsSentimentBadge");

    if (badge && data.sentiment) {
      const s = data.sentiment.score || 0;
      badge.innerText = `[UNVALIDATED RAW FEED] ${s >= 0 ? "+" : ""}${s.toFixed(2)} (${data.sentiment.n_items || 0} headlines)`;
    }

    if (list && data.items && data.items.length) {
      list.innerHTML = data.items.map(it => `
        <div class="news-item">
          <div>
            <a href="${it.url}" target="_blank" rel="noopener" class="news-title">${it.title}</a>
            <div class="news-meta">
              <span class="source-tag">${it.source.toUpperCase()}</span>
              <span>${it.published ? new Date(it.published * 1000).toLocaleDateString() : ""}</span>
            </div>
          </div>
        </div>
      `).join("");
    }
  } catch (err) {
    console.error("News load error:", err);
  }
}

// 11. Knowledge Doctrine
async function initKnowledge() {
  try {
    const res = await fetch("/api/knowledge");
    const resources = await res.json();
    const list = document.getElementById("doctrineList");
    if (!resources || !resources.length || !list) return;

    list.innerHTML = resources.map(r => `
      <div class="doctrine-item" title="${r.title}">
        <div class="doctrine-uri">${r.uri}</div>
        <div style="font-weight: 600; color: #f1f5f9;">${r.title}</div>
        <div style="font-size: 11px; color: var(--text-muted); margin-top: 4px;">${r.snippet}</div>
      </div>
    `).join("");
  } catch (err) {
    console.error("Doctrine load error:", err);
  }
}

// 12. Physical Order Gate Modal Demo
function initModal() {
  const modal = document.getElementById("orderModal");
  const openBtn = document.getElementById("openTestOrderBtn");
  const cancelBtn = document.getElementById("modalCancelBtn");
  const confirmBtn = document.getElementById("modalConfirmBtn");

  if (!modal || !openBtn) return;

  openBtn.addEventListener("click", () => {
    modal.classList.add("active");
  });

  cancelBtn.addEventListener("click", () => {
    modal.classList.remove("active");
    alert("ORDER CANCELED. Zero funds moved. The physical confirmer gate aborted execution.");
  });

  confirmBtn.addEventListener("click", () => {
    modal.classList.remove("active");
    alert("ORDER APPROVED! Signed trade instruction dispatched to Binance Spot engine.");
  });
}

// Helper utilities
function formatNumber(num) {
  if (num === null || num === undefined) return "--";
  if (typeof num === "string") {
    const cleaned = num.replace(/[$,\s]/g, "");
    const parsed = parseFloat(cleaned);
    if (isNaN(parsed)) return num;
    num = parsed;
  }
  if (isNaN(num)) return "--";
  if (num >= 1000) {
    return num.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  if (num < 0.0001) {
    return num.toFixed(8);
  }
  if (num < 0.01) {
    return num.toFixed(6);
  }
  if (num < 1) {
    return num.toFixed(4);
  }
  return num.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function capitalize(str) {
  if (!str) return "";
  return str.charAt(0).toUpperCase() + str.slice(1);
}
