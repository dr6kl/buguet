import pdb
import json
import binascii
from web3.middleware import geth_poa_middleware
from web3 import Web3, HTTPProvider
import sys
import readline
from termcolor import colored

data = json.load(open("Foo.json"))
source = open('Foo.sol').read()
contract_data = data['contracts']['Foo.sol:Foo']
contract_data['AST'] = data['sources']['Foo.sol']['AST']

web3 = Web3(HTTPProvider('http://localhost:8545'))
web3.middleware_stack.inject(geth_poa_middleware, layer=0)

# web3.eth.defaultAccount = web3.eth.accounts[0]

class Debugger:
    def __init__(self, web3, contract_data, transaction_id, source):
        self.web3 = web3;
        self.contract_data = contract_data
        self.transaction_id = transaction_id
        self.position = 0
        self.source = source
        self.lines = source.split("\n")

    def init(self):
        self.load_transaction_trace()
        self.validate_code()
        self.prepare_ops_mapping()
        self.prepare_sourcemap()
        self.prepare_line_offsets()
        self.init_ast()

    def init_ast(self):
        root = contract_data['AST']
        # print(root['children'][1]['name'])
        contract_definition = root['children'][2]
        function_definition = contract_definition['children'][8]
        # print(contract_definition.keys())
        # print(json.dumps(function_definition, indent=4))
        # pdb.set_trace()

    def load_transaction_trace(self):
        res = self.web3.manager.request_blocking("debug_traceTransaction", [transaction_id])
        self.struct_logs = res.structLogs

    def validate_code(self):
        tx = self.web3.eth.getTransaction(self.transaction_id)
        code = self.web3.eth.getCode(tx.to)
        code = binascii.hexlify(code).decode('utf-8')
        if not code == contract_data['bin-runtime']:
            raise Exception("Contract code doesn't match")

    def prepare_ops_mapping(self):
        self.pc_to_op_idx = {}
        code = bytes.fromhex(contract_data['bin-runtime'])
        i = 0
        op_num = 0
        while i < len(code):
            if code[i] == 0xa1 and code[i+1] == 0x65:
                break
            b = code[i]
            if b >= 0x60 and b < 0x80:
                operands_size = b - 0x60 + 1
            else:
                operands_size = 0
            self.pc_to_op_idx[i] = op_num
            for j in range(operands_size):
                self.pc_to_op_idx[i + j + 1] = op_num
            i += (1 + operands_size)
            op_num += 1

    def line_by_offset(self, offset):
        start = 0
        end = len(self.offset_by_line)
        while True:
            idx = (start + end) // 2
            s = self.offset_by_line[idx]
            if offset >= s and offset < s + len(self.lines[idx]) + 1:
                return idx
            elif offset < s:
                end = idx - 1
            elif offset >= s + len(self.lines[idx]) + 1:
                start = idx + 1

    def prepare_sourcemap(self):
        self.srcmap = {}

        map_items = self.contract_data['srcmap-runtime'].split(";")

        for i in range(len(map_items)):
            item = {}
            map_item = map_items[i]
            arr = map_item.split(":")

            if len(arr) > 0 and arr[0] != '':
                s = int(arr[0])
            else:
                s = self.srcmap[i-1]['s']

            if len(arr) > 1 and arr[1] != '':
                l = int(arr[1])
            else:
                l = self.srcmap[i-1]['l']

            self.srcmap[i] = {"s": s, "l": l}

    def prepare_line_offsets(self):
        self.offset_by_line = {}
        pos = 0
        for i in range(len(self.lines)):
            self.offset_by_line[i] = pos
            pos += len(self.lines[i]) + 1

    def current_instuction_num(self):
        return self.pc_to_op_idx[self.current_op()['pc']]

    def step(self):
        l = self.current_line_num()
        while self.current_line_num() == l:
            self.position += 1

    def next(self):
        # l = self.current_line_num()
        # while self.current_line_num() == l:
        self.position += 1

    def print_stack(self):
        stack = self.struct_logs[self.position]['stack']
        for x in reversed(stack):
            print(x)
        print("\n\n")

    def print_memory(self):
        for i, x in enumerate(self.struct_logs[self.position]['memory']):
            print(hex(i * 32) + ': ' + x)
        print("\n\n")

    def print_op(self):
        op = self.struct_logs[self.position]['op']
        print(op, end=' ')
        if str.startswith(op, 'PUSH') and self.position < len(self.struct_logs):
            next_stack = self.struct_logs[self.position + 1]['stack']
            print(next_stack[len(next_stack) - 1], end='')
        print()

    def current_src_fragment(self):
        return self.srcmap[self.current_instuction_num()]

    def current_op(self):
        return self.struct_logs[self.position]

    def current_line_num(self):
        offset = self.current_src_fragment()['s']
        line_num = self.line_by_offset(offset)
        return line_num

    def show_lines(self, n = 3, highlight=True):
        line_num = self.current_line_num()
        res = []
        for i in range(line_num - n, line_num + n + 1):
            if i >= 0  and i < len(self.lines):
                res.append([i, self.lines[i]])
        return res

    def repl(self):
        while True:
            self.print_op()
            self.print_lines()
            line = input("Command: ")
            if line == "next" or line == "n":
                self.next()
            elif line == "step" or line == "s":
                self.step()
            elif line == "stack" or line == "st":
                self.print_stack()
            elif line == "memory" or line == "mem":
                self.print_memory()

    def print_lines(self, n = 3):
        lines = self.show_lines(n)
        for i, line in enumerate(lines):
            if len(lines) // 2 == i:
                print(" => ", end='')
            else:
                print("    ", end='')
            print(":" + str(line[0]) + ' ', end='')
            print(line[1])

    def to_next_jump_dest(self):
        while(debugger.current_op()['op'] != 'JUMPDEST'):
            debugger.next()


transaction_id = "0x1381371786638d992c8532a62df971fa59500abce9e911e7fb45bb61690defe8"
debugger = Debugger(web3, contract_data, transaction_id, source)
debugger.init()
debugger.to_next_jump_dest()
debugger.repl()
