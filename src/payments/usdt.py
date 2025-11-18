from __future__ import annotations

import requests
from tronpy import Tron
from tronpy.keys import keccak256


client = Tron()
USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
TRANSFER_EVENT = keccak256("Transfer(address,address,uint256)".encode()).hex()

COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"


def fetch_usdt_rub_rate() -> float:
    resp = requests.get(
        COINGECKO_URL,
        params={"ids": "tether", "vs_currencies": "rub"},
        timeout=5,
    )
    resp.raise_for_status()
    data = resp.json()
    return float(data["tether"]["rub"])


def usdt_rub(amount: float) -> int:
    rate = fetch_usdt_rub_rate()
    return round(rate * amount + 1)

def rub_usdt(amount: float) -> int:
    rate = fetch_usdt_rub_rate()
    return round(amount / rate + 1)

def check_usdt_transaction(
        txid: str,
        expected_to: str | None = None,  # base58 address, e.g. "TN..."
        min_amount: float | None = None, # in USDT
):
    info = client.get_transaction_info(txid)
    if info.get("receipt", {}).get("result") != "SUCCESS": return False, {"status": "failed_or_pending", "raw": info}

    for log in info.get("log", []):
        if log["topics"][0] != TRANSFER_EVENT: continue

        if log["address"] != client.to_canonical_address(USDT_CONTRACT): continue

        from_addr = client.to_base58check_address("41" + log["topics"][1][-40:])
        to_addr = client.to_base58check_address("41" + log["topics"][2][-40:])
        raw_amount = int(log["data"], 16)
        amount = raw_amount / (10 ** 6)

        if expected_to and to_addr != expected_to: continue
        if min_amount and amount < min_amount: continue

        return True, {
            "status": "confirmed",
            "from": from_addr,
            "to": to_addr,
            "amount": amount,
            "tx_info": info,
        }

    return False, {"status": "not_found", "raw": info}
