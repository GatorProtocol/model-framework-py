import os
import json
import time

from web3 import Web3

class Model:
    def __init__(self, callback=None, id=None, provider=None, boost=1, env=None, errorcallback=None, checkfreq=2):
        if id is None: raise Exception("Model ID cannot be None")
        if provider is None: raise Exception("Web3 provider cannot be None")
        if env is None: raise Exception("ENV cannot be None")
        if errorcallback is None: raise Exception("Error callback cannot be None")
        if callback is None: raise Exception("Callback cannot be None")

        self.id = id
        self.boost = boost
        self.callback = callback
        self.checkfreq = checkfreq
        self.errorcallback = errorcallback
        
        if list(str(provider))[0].lower() == "h":
            self.provider = Web3(Web3.HTTPProvider(str(provider)))
        elif list(str(provider))[0].lower() == "w":
            self.provider = Web3(Web3.WebsocketProvider(str(provider)))
                
        self.contract_abi = json.loads(open("gator/data/contract_abi.json", "r").read())
        self.contract_address = Web3.to_checksum_address(open("gator/data/contract_address.txt", "r").read())
        
        self.private_key = env["PRIVATE_KEY"]
        self.public_key = Web3.to_checksum_address(env["PUBLIC_KEY"])

    def start(self):
        known_ids = []

        contract = self.provider.eth.contract(address=self.contract_address, abi=self.contract_abi)
        listener = contract.events.RequestCreated.create_filter(fromBlock='latest')
        
        while True:
            time.sleep(self.checkfreq)

            try:
                for event in listener.get_all_entries():
                    if int(event["args"]["modelId"]) == self.id and event["args"]["requestId"] not in known_ids:
                        print("---------------------------------------------------------------------\n")
                        print("   Request")
                        print("      Model:    " + str(event["args"]["modelId"]))
                        print("      Prompt:   " + str(event["args"]["prompt"]))
                        print("\n---------------------------------------------------------------------\n")

                        result = self.callback(self.id, str(event["args"]["prompt"]), int(event["args"]["entropy"]))

                        function = contract.functions.fufillRequest(event["args"]["requestId"], event["args"]["modelId"], str(result))
                        nonce = self.provider.eth.get_transaction_count(self.public_key)

                        gasEstimate = function.estimate_gas({'from': self.public_key})
                        gasPrice = self.provider.eth.generate_gas_price()
                        if gasPrice is None:
                            gasPrice = self.provider.eth.gas_price * 25

                        estimated_gas_cost = gasEstimate * gasPrice
                        balance = self.provider.eth.get_balance(self.public_key)
                        if balance < estimated_gas_cost:
                            raise Exception(f"ERROR: insufficient funds. Have {balance}, need {estimated_gas_cost}")
                        else:
                            txn_dict = function.build_transaction({
                                'gas': int(gasEstimate * self.boost),
                                'gasPrice': int(gasPrice * self.boost),
                                'nonce': nonce,
                                'from': self.public_key
                            })
                            
                            signed_txn = self.provider.eth.account.sign_transaction(txn_dict, private_key=self.private_key)
                            
                            tx = self.provider.eth.send_raw_transaction(signed_txn.rawTransaction)
                            print("---------------------------------------------------------------------\n")
                            print("    Success")
                            print("         TX: " + str(tx.hex()) + "\n")
                            print("---------------------------------------------------------------------\n")
                        known_ids.append(event["args"]["requestId"])
        
            except Exception as e:
                print(e)
                self.start()