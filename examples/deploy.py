import pdb
import json
from web3.middleware import geth_poa_middleware
from web3 import Web3, HTTPProvider
import sys
import os

web3 = Web3(HTTPProvider('http://localhost:8545'))
web3.middleware_stack.inject(geth_poa_middleware, layer=0)
web3.eth.defaultAccount = web3.eth.accounts[0]

if len(sys.argv) == 1 or sys.argv[1] == "deploy":
    cmd = "solc --combined-json abi,ast,bin,bin-runtime,srcmap,srcmap-runtime Foo.sol Bar.sol > out.json"
    status = os.system(cmd)
    if status != 0:
        raise Exception("Compile failed")

    data = json.load(open("out.json"))
    contract_data = data['contracts']['Foo.sol:Foo']

    tx_hash = web3.eth.contract(abi=contract_data['abi'], bytecode=contract_data['bin']).constructor().transact()
    tx_receipt = web3.eth.waitForTransactionReceipt(tx_hash)
    f = open("address.txt", "w")
    f.write(tx_receipt['contractAddress'])
    f.close()
    f = open("transaction_init.txt", "w")
    f.write(tx_receipt.transactionHash.hex())
    f.close()

if len(sys.argv) == 1 or sys.argv[1] == "transact":
    f = open("address.txt", "r")
    contract_address = Web3.toChecksumAddress(f.read())
    data = json.load(open("out.json"))
    contract_data = data['contracts']['Foo.sol:Foo']
    foo = web3.eth.contract(abi=contract_data['abi'], address=contract_address)
    tx_hash = foo.functions.doSomething(1, 2, 3).transact()
    tx = web3.eth.waitForTransactionReceipt(tx_hash)
    f = open("transaction_id.txt", "w")
    f.write(tx.transactionHash.hex())
    f.close()
