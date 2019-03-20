import pdb
import json
from web3.middleware import geth_poa_middleware
from web3 import Web3, HTTPProvider
import sys

data = json.load(open("Foo.json"))
contract_data = data['contracts']['Foo.sol:Foo']
counter_contract_data = data['contracts']['Foo.sol:Counter']

web3 = Web3(HTTPProvider('http://localhost:8545'))
web3.middleware_stack.inject(geth_poa_middleware, layer=0)
web3.eth.defaultAccount = web3.eth.accounts[0]


if len(sys.argv) == 1 or sys.argv[1] == "deploy":
    tx_hash = web3.eth.contract(abi=counter_contract_data['abi'], bytecode=counter_contract_data['bin']).constructor().transact()
    tx_receipt = web3.eth.waitForTransactionReceipt(tx_hash)
    counter_address = tx_receipt['contractAddress']

    tx_hash = web3.eth.contract(abi=contract_data['abi'], bytecode=contract_data['bin']).constructor(counter_address).transact()
    tx_receipt = web3.eth.waitForTransactionReceipt(tx_hash)
    f = open("address.txt", "w")
    f.write(tx_receipt['contractAddress'])
    f.close()
    print(tx_receipt)

if len(sys.argv) == 1 or sys.argv[1] == "transact":
    f = open("address.txt", "r")
    contract_address = Web3.toChecksumAddress(f.read())
    foo = web3.eth.contract(abi=contract_data['abi'], address=contract_address)
    tx_hash = foo.functions.doSomething(1, 2, 3).transact()
    tx = web3.eth.waitForTransactionReceipt(tx_hash)
    f = open("transaction_id.txt", "w")
    f.write(tx.transactionHash.hex())
    f.close()
