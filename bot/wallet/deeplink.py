from pywalletconnect import WCClient

def generate_wallet_deeplink(tx_data: dict) -> str:
    # Set wallet metadata (optional)
    WCClient.set_wallet_metadata({
        "name": "FinanceBot",
        "description": "Crypto transaction bot",
        "url": "https://yourbot.com",
        "icons": ["https://yourbot.com/icon.png"]
    })
    
    # For a POC, you can create a mock URI
    uri = f"wc:00000000-0000-0000-0000-000000000000@1?bridge=https://bridge.walletconnect.org&key=00000000000000000000000000000000"
    
    return f"{uri}&tx={tx_data}"
