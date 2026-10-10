"""Demo of the physical Human-in-the-Loop Web Confirmation Gate in krmaazha-binance-mcp.

Opens the exact local web confirmation page in your default browser, displaying:
- Warning banner (REAL MONEY MAINNET vs TESTNET)
- Exact canonical order parameters
- 45-second expiry countdown
- Default-focused Cancel button and Confirm button
"""
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from decimal import Decimal
from krmaazha_binance_mcp.models import CanonicalOrder, OrderPreview
from krmaazha_binance_mcp_confirmer.dialog import render_dialog_text
from krmaazha_binance_mcp_confirmer.confirm_backends import web_confirm

def main():
    print("=" * 65)
    print("  KRMAAZHA-BINANCE-MCP EXECUTION GATE DEMO")
    print("=" * 65)
    
    # 1. Create a sample canonical order (the untrusted model's proposal)
    order = CanonicalOrder(
        symbol="BTCUSDT",
        side="BUY",
        type="LIMIT",
        price=Decimal("84500.00"),
        quantity=Decimal("0.05"),
        time_in_force="GTC",
        env="mainnet"
    )
    
    # 2. Confirmer authoritative re-validation & preview
    preview = OrderPreview(
        effective_qty=Decimal("0.05"),
        price=Decimal("84500.00"),
        est_notional=Decimal("4225.00"),
        est_commission=Decimal("4.225"),
        env="mainnet",
        feasible=True
    )
    
    # 3. Render canonical dialog text
    dialog_text = render_dialog_text(order, preview)
    
    print("\n[+] Proposed Order from AI Assistant:")
    print("-" * 40)
    print(dialog_text)
    print("-" * 40)
    print("\n[+] Launching local ephemeral web server on 127.0.0.1...")
    print("[+] Opening approval dialog in your default web browser...")
    print("[!] Notice: The web page will expire in 45 seconds if no action is taken.\n")
    
    # 4. Trigger the physical confirmation web backend
    confirmed = web_confirm(dialog_text)
    
    print("\n" + "=" * 65)
    if confirmed:
        print("  RESULT: ORDER CONFIRMED BY OPERATOR (Would execute on exchange)")
    else:
        print("  RESULT: ORDER CANCELED / REJECTED (Zero funds moved)")
    print("=" * 65)

if __name__ == "__main__":
    main()
