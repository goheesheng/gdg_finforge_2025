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
        self.w3 = Web3(Web3.HTTPProvider(f'https://sepolia.infura.io/v3/{os.getenv("INFURA_ID")}'))
        if not self.w3.is_connected():
            raise ConnectionError("Failed to connect to Sepolia network")
        logging.info("Connected to Sepolia network")
        
        self.deposit_adapter_address = '0x80b5DC88C98E528bF9cb4B7F0f076aC41da24651' # this is still proxy

        
    def _get_lido_abi(self):
        try:
            response = requests.get(
                f'https://api.etherscan.io/api?module=contract&action=getabi&address={self.deposit_adapter_address}&apikey={os.getenv("SEPOLIA_KEY")}'
            )
            json_response = response.json()
            if json_response['status'] == '0':
                raise Exception(f"Etherscan API error: {json_response['message']}")
            return json.loads(json_response['result'])
        except Exception as e:
            # logging.error(f"Failed to fetch ABI: {str(e)}")
            # Fallback to hardcoded ABI, this is implementation ABI
            #  https://sepolia.etherscan.io/address/0x3e3FE7dBc6B4C189E7128855dD526361c49b40Af#code
            return[{"inputs":[{"internalType":"address","name":"_deposit_contract","type":"address"}],"stateMutability":"nonpayable","type":"constructor"},{"inputs":[],"name":"BepoliaRecoverFailed","type":"error"},{"inputs":[],"name":"DepositFailed","type":"error"},{"inputs":[],"name":"EthRecoverFailed","type":"error"},{"inputs":[],"name":"InvalidContractVersionIncrement","type":"error"},{"inputs":[],"name":"NonZeroContractVersionOnInit","type":"error"},{"inputs":[{"internalType":"uint256","name":"expected","type":"uint256"},{"internalType":"uint256","name":"received","type":"uint256"}],"name":"UnexpectedContractVersion","type":"error"},{"inputs":[{"internalType":"string","name":"field","type":"string"}],"name":"ZeroAddress","type":"error"},{"anonymous":False,"inputs":[{"indexed":False,"internalType":"uint256","name":"amount","type":"uint256"}],"name":"BepoliaRecovered","type":"event"},{"anonymous":False,"inputs":[{"indexed":False,"internalType":"uint256","name":"version","type":"uint256"}],"name":"ContractVersionSet","type":"event"},{"anonymous":False,"inputs":[{"indexed":False,"internalType":"bytes","name":"pubkey","type":"bytes"},{"indexed":False,"internalType":"bytes","name":"withdrawal_credentials","type":"bytes"},{"indexed":False,"internalType":"bytes","name":"amount","type":"bytes"},{"indexed":False,"internalType":"bytes","name":"signature","type":"bytes"},{"indexed":False,"internalType":"bytes","name":"index","type":"bytes"}],"name":"DepositEvent","type":"event"},{"anonymous":False,"inputs":[{"indexed":False,"internalType":"address","name":"sender","type":"address"},{"indexed":False,"internalType":"uint256","name":"amount","type":"uint256"}],"name":"EthReceived","type":"event"},{"anonymous":False,"inputs":[{"indexed":False,"internalType":"uint256","name":"amount","type":"uint256"}],"name":"EthRecovered","type":"event"},{"anonymous":False,"inputs":[{"indexed":True,"internalType":"address","name":"previousOwner","type":"address"},{"indexed":True,"internalType":"address","name":"newOwner","type":"address"}],"name":"OwnershipTransferred","type":"event"},{"inputs":[{"internalType":"bytes","name":"pubkey","type":"bytes"},{"internalType":"bytes","name":"withdrawal_credentials","type":"bytes"},{"internalType":"bytes","name":"signature","type":"bytes"},{"internalType":"bytes32","name":"deposit_data_root","type":"bytes32"}],"name":"deposit","outputs":[],"stateMutability":"payable","type":"function"},{"inputs":[],"name":"getContractVersion","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"get_deposit_count","outputs":[{"internalType":"bytes","name":"","type":"bytes"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"get_deposit_root","outputs":[{"internalType":"bytes32","name":"","type":"bytes32"}],"stateMutability":"view","type":"function"},{"inputs":[{"internalType":"address","name":"_owner","type":"address"}],"name":"initialize","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[],"name":"originalContract","outputs":[{"internalType":"contract ISepoliaDepositContract","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"owner","outputs":[{"internalType":"address","name":"","type":"address"}],"stateMutability":"view","type":"function"},{"inputs":[],"name":"recoverBepolia","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[],"name":"recoverEth","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[],"name":"renounceOwnership","outputs":[],"stateMutability":"nonpayable","type":"function"},{"inputs":[{"internalType":"address","name":"newOwner","type":"address"}],"name":"transferOwnership","outputs":[],"stateMutability":"nonpayable","type":"function"},{"stateMutability":"payable","type":"receive"}]
    
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
