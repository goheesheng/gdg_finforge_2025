from web3 import Web3
import requests
import json
import os
import logging
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)

class BlockchainHandler:
    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(f'https://holesky.infura.io/v3//{os.getenv("INFURA_ID")}'))
        if not self.w3.is_connected():
            raise ConnectionError("Failed to connect to Holesky network")
        logging.info("Connected to Holesky network")
        
        self.deposit_adapter_address = '0x80b5DC88C98E528bF9cb4B7F0f076aC41da24651' # this is still proxy

        
    def _get_lido_abi(self):
        try:
            response = requests.get(
                f'https://api.etherscan.io/api?module=contract&action=getabi&address={self.deposit_adapter_address}&apikey={os.getenv("HOLESKY_KEY")}'
            )
            json_response = response.json()
            if json_response['status'] == '0':
                raise Exception(f"Etherscan API error: {json_response['message']}")
            return json.loads(json_response['result'])
        except Exception as e:
            # logging.error(f"Failed to fetch ABI: {str(e)}")
            # Fallback to hardcoded ABI, this is implementation ABI
            #  https://sepolia.etherscan.io/address/0x3e3FE7dBc6B4C189E7128855dD526361c49b40Af#code
            # For Holesky: https://holesky.etherscan.io/address/0x3F1c547b21f65e10480dE3ad8E19fAAC46C95034
            return [{"constant":True,"inputs":[],"name":"proxyType","outputs":[{"name":"proxyTypeId","type":"uint256"}],"payable":False,"stateMutability":"pure","type":"function"},{"constant":True,"inputs":[],"name":"isDepositable","outputs":[{"name":"","type":"bool"}],"payable":False,"stateMutability":"view","type":"function"},{"constant":True,"inputs":[],"name":"implementation","outputs":[{"name":"","type":"address"}],"payable":False,"stateMutability":"view","type":"function"},{"constant":True,"inputs":[],"name":"appId","outputs":[{"name":"","type":"bytes32"}],"payable":False,"stateMutability":"view","type":"function"},{"constant":True,"inputs":[],"name":"kernel","outputs":[{"name":"","type":"address"}],"payable":False,"stateMutability":"view","type":"function"},{"inputs":[{"name":"_kernel","type":"address"},{"name":"_appId","type":"bytes32"},{"name":"_initializePayload","type":"bytes"}],"payable":False,"stateMutability":"nonpayable","type":"constructor"},{"payable":True,"stateMutability":"payable","type":"fallback"},{"anonymous":False,"inputs":[{"indexed":False,"name":"sender","type":"address"},{"indexed":False,"name":"value","type":"uint256"}],"name":"ProxyDeposit","type":"event"}]
    
    async def execute_swap(self, params: dict):
        # Use provided address or default
        from_address = params.get('from_address', '0x861FDed5e669068BC9d57b733C7CCFEcCF1a8eAC')
        
        # Ensure it's a checksum address
        from_address = self.w3.to_checksum_address(from_address)
        
        return {
            'to': '0xUniswapRouterAddress',  # Replace with actual Sepolia router
            'data': '0xswapdata',
            'value': Web3.to_wei(params['amount'], 'ether'),
            'from': from_address
        }

    async def submit_transaction(self, tx_data):
        signed_tx = self.w3.eth.account.sign_transaction(tx_data, private_key=os.getenv("PRIVATE_KEY"))
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        return self.w3.eth.wait_for_transaction_receipt(tx_hash)

    async def execute_stake(self, params: dict):
        try:
            # Use provided address or default
            from_address = params.get('from_address', '0x861FDed5e669068BC9d57b733C7CCFEcCF1a8eAC')
            
            # Ensure it's a checksum address
            from_address = self.w3.to_checksum_address(from_address)
            
            return {
                'to': self.deposit_adapter_address,
                'value': Web3.to_wei(params['amount'], 'ether'),
                'gas': 200000,
                'data': '0x',  # Empty data field to trigger fallback
                'nonce': self.w3.eth.get_transaction_count(from_address)
            }
        except Exception as e:
            logging.error(f"Failed to execute stake: {str(e)}")
            raise
