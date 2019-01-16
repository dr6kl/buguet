import argparse
import json
from buguet.debugger import Debugger
from web3.middleware import geth_poa_middleware
from web3 import Web3, HTTPProvider

def main():
    parser = argparse.ArgumentParser(description='Ethereum debugger')

    parser.add_argument('--rpc', help="RPC of the ethereum node. Default is http://localhost:8545.", default="http://localhost:8545")
    parser.add_argument('combined_json', help="""
        Json file produced by solidity compiler with --combined-json argument. It should
        contain all the contracts affected by the transaction""")
    parser.add_argument('transaction_id', help='Id of the transaction to debug')
    parser.add_argument('sources_root', help='Root directory for solidity sources')

    args = parser.parse_args()

    web3 = Web3(HTTPProvider(args.rpc))
    web3.middleware_stack.inject(geth_poa_middleware, layer=0)
    data = json.load(open(args.combined_json))

    debugger = Debugger(web3, data, args.transaction_id, args.sources_root)
    debugger.repl()

