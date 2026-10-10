# 🧠 Master Orchestrator Agent Specification

The **Master Orchestrator Agent** is the supreme command, deliberation, and quality-enforcement entity within the `krmaazha-binance-mcp` multi-agent architecture. It possesses comprehensive, deep knowledge of every specialized agent in the ecosystem, their boundary invariants, governing skills, toolchains, and epistemic duties.

---

## 1. System Multi-Agent Topology

```mermaid
graph TD
    Client["Client / Trader / LLM User"] -->|Directs Prompt / Request| Orchestrator["🧠 Master Orchestrator Agent\n(Triage, Multi-Agent Deliberation, Institutional Bottom Line)"]
    
    subgraph Specialized_SubAgents["Specialized Autonomous Sub-Agents"]
        Orchestrator -->|Key & Gate Audit| Sec["🛡️ Security & Key Guard Agent\nSkill: security-review\nBoundaries: Zero-Trust, Read/Trade Isolation"]
        Orchestrator -->|Math & Liquidity Audit| Quant["📊 Quantitative Research & Risk Agent\nSkills: async-python-patterns, python-testing-patterns\nBoundaries: Zero-Lookahead, Order-Book Depth, Net R:R"]
        Orchestrator -->|Schema & Typing Audit| Proto["⚡ MCP Protocol & Tooling Agent\nSkills: mcp-builder, improve-codebase-architecture\nBoundaries: Decimal Precision, CanonicalOrder, Error Scrubbing"]
        Orchestrator -->|Ergonomics & Epistemic Audit| UX["🖥️ Financial Dashboard & UX Agent\nSkill: frontend-design\nBoundaries: Micro-Cap Decimals, Epistemic Tags, Reactive Timestamps"]
    end

    Sec -->|Audit Verdict| Orchestrator
    Quant -->|Depth & Trade Setup| Orchestrator
    Proto -->|Wire Compliance| Orchestrator
    UX -->|Presentation Tokens| Orchestrator
    
    Orchestrator -->|Standardized Institutional Dossier| Client
```

---

## 2. Exhaustive Agent Knowledge Directory

### 2.1 🧠 Master Orchestrator Agent (`@master_orchestrator`)
* **Identity**: Apex Coordination and Quality Synthesis Engine.
* **Governing Skill**: `orchestrator` (`.agents/skills/orchestrator/SKILL.md`).
* **Python Implementation**: [`MasterOrchestratorAgent`](file:///c:/Users/Raza/Downloads/konnextBinMcp/src/krmaazha_binance_mcp/agents/orchestrator.py).
* **Core Responsibilities**:
  1. **Request Triage & Routing**: Determines which sub-agents are needed for a query and coordinates their sequential/parallel execution.
  2. **Doctrine Enforcement**: Holds the full canonical doctrine of `kb://discipline`:
     - *Rules 1–6 (Spot Portfolio)*: Cash generation, BTC/USDT standard, cyclical accumulation, risk budgeting.
     - *Rule 7 (Systematic Research)*: Quantitative edge verification across 986 USD-M futures pairs with zero survivorship bias.
  3. **Institutional Quality Gates (`IMPROVEMENTS.MD`)**:
     - Guarantees instrument venue specificity (Binance Spot vs Futures).
     - Mandates closed-bar confirmation and full indicator parameter disclosure.
     - Demands executable order-book depth (touch spread in bps, ±1% depth).
     - Converts price ideas into actionable trade setups with **Net R:R** (after 20 bps fees and estimated slippage).
     - Categorizes every claim with epistemic classification tags: `[VERIFIED FACT]`, `[QUANTITATIVE ESTIMATE]`, `[ANALYST INTERPRETATION]`.
  4. **Standardized Bottom-Line Synthesis**:
     Formulates the exact mandatory single-sentence bottom line:
     > *"At [timestamp], [instrument] is [state]. The setup is valid only if [observable condition]; it is invalidated by [condition]. Costs/risks are [items]. Otherwise, no trade."*

---

### 2.2 🛡️ Security & Key Guard Agent (`@security_guard`)
* **Identity**: Defense-in-depth guardian of API keys, process memory, and physical authorization.
* **Governing Skill**: `security-review`.
* **Python Implementation**: [`SecurityGuardAgent`](file:///c:/Users/Raza/Downloads/konnextBinMcp/src/krmaazha_binance_mcp/agents/security.py).
* **Core Responsibilities**:
  - Validates that the primary MCP server process loads **only** `BINANCE_READ_*` keys.
  - Guarantees that `BINANCE_TRADE_*` credentials remain strictly sandboxed inside the isolated `krmaazha-binance-mcp-confirmer` process.
  - Verifies that withdrawal permissions are disabled and IP whitelists are enforced on all active API keys.
  - Guarantees that no automated execution path can bypass the physical human click in the one-shot web confirmation dialog.
  - Scrubs API secrets, nonces, and HMAC signatures from logs, errors, and LLM context windows.
* **Hard Invariants**:
  - `ABORT_ON_TRADE_KEY_IN_SERVER`: If the MCP server detects trading keys in its process environment, it immediately refuses to start.
  - `NO_UNCONFIRMED_EXECUTION`: Any call to execute an order without a cryptographically signed human token is blocked.

---

### 2.3 📊 Quantitative Research & Risk Agent (`@quant_risk`)
* **Identity**: Algorithmic integrity, zero-lookahead backtesting, and order-book liquidity auditor.
* **Governing Skills**: `async-python-patterns`, `python-testing-patterns`.
* **Python Implementation**: [`QuantitativeRiskAgent`](file:///c:/Users/Raza/Downloads/konnextBinMcp/src/krmaazha_binance_mcp/agents/quantitative.py).
* **Core Responsibilities**:
  - Enforces zero-lookahead bias: indicators are computed exclusively on closed bar $t$; executions are modeled at $t+1$ open.
  - Inspects real-time order-book depth via Binance `/api/v3/depth`:
    * Computes touch spread in basis points: $\text{bps} = \frac{\text{Ask} - \text{Bid}}{\text{Mid}} \times 10,000$.
    * Measures executable capital within $\pm 1\%$ and $\pm 2\%$ price bands in USDT.
    * Flags thin order books (`is_thin_book = True`) where market impact creates severe slippage.
  - Computes complete trade setups: Entry trigger, Invalidation stop, Target, Time horizon.
  - Models **Net Reward-to-Risk**:
    $$\text{Net R:R} = \frac{\text{Reward} - (\text{Round-trip Fees } [20\text{ bps}] + \text{Slippage})}{\text{Risk} + (\text{Round-trip Fees } [20\text{ bps}] + \text{Slippage})}$$
  - Evaluates macro cycle health (Mayer Multiple, 200-day SMA distance, halving progress).

---

### 2.4 ⚡ MCP Protocol & Tooling Agent (`@mcp_protocol`)
* **Identity**: Protocol architect ensuring FastMCP compliance, typing accuracy, and API boundaries.
* **Governing Skills**: `mcp-builder`, `improve-codebase-architecture`.
* **Python Implementation**: [`McpProtocolAgent`](file:///c:/Users/Raza/Downloads/konnextBinMcp/src/krmaazha_binance_mcp/agents/protocol.py).
* **Core Responsibilities**:
  - Governs FastMCP tool registration, resource schemas (`kb://...`), and prompt templates.
  - Enforces bit-perfect financial arithmetic using Python `Decimal` across all quantities, prices, and notionals.
  - Validates `CanonicalOrder` structures against exchange `LOT_SIZE`, `PRICE_FILTER`, and `MIN_NOTIONAL` rules.
  - Ensures clean IPC socket communication (`register` / `status` verbs) between the MCP server and the confirmation daemon.
  - Intercepts and scrubs raw exceptions from the Binance SDK before returning tool payloads to the host LLM.

---

### 2.5 🖥️ Financial Dashboard & UX Agent (`@dashboard_ux`)
* **Identity**: High-density visual ergonomics, micro-cap sub-dollar formatting, and epistemic labeling.
* **Governing Skill**: `frontend-design`.
* **Python Implementation**: [`DashboardUXAgent`](file:///c:/Users/Raza/Downloads/konnextBinMcp/src/krmaazha_binance_mcp/agents/ux.py).
* **Core Responsibilities**:
  - Enforces institutional dark-mode aesthetics: obsidian `#07090e`, deep card slate `#121620`, Binance gold `#f0b90b`, emerald `#0ecb81`, crimson `#f6465d`.
  - Solves the micro-cap precision problem: formats sub-dollar assets like `NOM/USDT` ($0.002452), `RESOLV/USDT` ($0.019160), and `XVG/USDT` ($0.003152) with up to 6 decimal places, avoiding truncated `$0.00` artifacts.
  - Displays dynamic data freshness badges: `🕒 Synced: hh:mm:ss UTC (Xs ago)` with auto-polling frequency markers (5s tickers, 15s candles, 30s signals, 60s macro).
  - Emits epistemic classification badges on all claims:
    * `[VERIFIED FACT]`: Empirically proven data (e.g. order-book depth, live bid/ask, closed candle close).
    * `[QUANTITATIVE ESTIMATE]`: Mathematical model outputs (e.g. RSI, EMA, Net R:R, Mayer Multiple).
    * `[ANALYST INTERPRETATION]`: Qualitative narrative, bull/bear theses, regulatory or fundamental commentary.

---

## 3. Deliberation Protocol & Execution Flow

When a user request is received (e.g. *"Should I invest in SOLUSDT?"* or *"/asset_thesis symbol=NOMUSDT"*):

1. **Step 1: Orchestrator Triage**: The Orchestrator inspects the intent, identifies the asset (`NOMUSDT`), and initializes the multi-agent context.
2. **Step 2: Security & Key Guard Deliberation**: Audits environment, verifies read-only isolation, and flags that trade execution requires physical confirmation.
3. **Step 3: Quantitative Liquidity & Net R:R Deliberation**:
   - Queries live bid/ask touch spread: `3.22 bps`.
   - Queries $\pm 1\%$ depth: `$285,410 USDT`.
   - Computes closed-bar technical indicators: RSI 14 (`54.2`), EMA 12/26 cross.
   - Computes trade setup: Entry trigger, Invalidation stop, Gross R:R ($2.60:1$), and Net R:R ($2.41:1$ after 20 bps fees + spread friction).
4. **Step 4: Protocol & Schema Deliberation**: Verifies CanonicalOrder schema, Decimal precision, and FastMCP tool integrity.
5. **Step 5: UX & Epistemic Tagging**: Applies 6-decimal micro-cap formatting (`$0.002462`) and tags claims (`[VERIFIED FACT]`, `[QUANTITATIVE ESTIMATE]`).
6. **Step 6: Orchestrator Institutional Bottom-Line Synthesis**:
   Synthesizes the finalized output into the required template:
   > *"At 2026-10-06 00:40:57 UTC, NOMUSDT on Binance Spot is trading at $0.002462 in an accumulation structure. The setup is valid only if Confirmed 1h candle close above $0.002467; it is invalidated by $0.002401 (-2.50%). Costs/risks are friction of 0.322% (20 bps fee + spread/slippage) and potential stop execution slippage. Otherwise, no trade."*
