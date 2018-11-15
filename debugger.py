import pdb
import json
import binascii
from web3.middleware import geth_poa_middleware
from web3 import Web3, HTTPProvider
import sys
import readline
from termcolor import colored
import sha3
import regex
import beeprint

data = json.load(open("Foo.json"))
source = open('Foo.sol').read()
contract_data = data['contracts']['Foo.sol:Foo']
contract_data['AST'] = data['sources']['Foo.sol']['AST']

web3 = Web3(HTTPProvider('http://localhost:8545'))
web3.middleware_stack.inject(geth_poa_middleware, layer=0)

# web3.eth.defaultAccount = web3.eth.accounts[0]
class Contract:
    def __init__(self):
        self.variables = []
        self.functions = []

    def parse_ast(self, item):
        self.src = list(map(lambda x: int(x), item['src'].split(":")))
        self.name = item['attributes']['name']
        for x in item['children']:
            if x['name'] == 'FunctionDefinition':
                func = Function()
                func.parse_ast(x)
                self.functions.append(func)
            if x['name'] == 'VariableDeclaration':
                self.variables.append({
                    'name': x['attributes']['name'],
                    'type': x['attributes']['type']
                })

    def set_storage_locations(self):
        current_storage_idx = 0
        bits_consumed = 0
        for i, var in enumerate(self.variables):
            type_size = self.type_size(var['type'])
            bits_consumed += type_size

            if bits_consumed > 256:
                bits_consumed = type_size
                current_storage_idx += 1

            self.variables[i]['type_size'] = type_size
            self.variables[i]['location'] = current_storage_idx
            self.variables[i]['offset'] = bits_consumed - type_size

    def type_size(self, type_name):
        int_match = regex.match("u?int(\d+)", type_name)
        if int_match:
            if int_match[1]:
                return int(int_match[1])
        return 256

    def find_variable(self, var_name):
        for v in self.variables:
            if v['name'] == var_name:
                return v
        return None

class Function:
    def __init__(self):
        self.local_vars = []
        self.params = []

    def parse_ast(self, item):
        self.name = item['attributes']['name']
        self.src = list(map(lambda x: int(x), item['src'].split(":")))
        for c in item['children']:
            if c['name'] == 'ParameterList':
                params = self.get_func_parameters(c)
                if params:
                    self.params = params
            if c['name'] == 'Block':
                def process_function_node(node):
                    if node['name'] == 'VariableDeclaration':
                        var_name = node['attributes']['name']
                        self.local_vars.append(var_name)
                self.traverse_all(c, lambda x: process_function_node(x))

    def traverse_all(self, node, f):
        f(node)
        if 'children' in node:
            for c in node['children']:
                self.traverse_all(c, f)

    def get_func_parameters(self, parameter_list):
        result = []
        for c in parameter_list['children']:
            if c['name'] == 'VariableDeclaration':
                var_name = c['attributes']['name']
                if var_name:
                    result.append(var_name)
        return result

class Debugger:
    def __init__(self, web3, contract_data, transaction_id, source):
        self.web3 = web3;
        self.contract_data = contract_data
        self.transaction_id = transaction_id
        self.position = 0
        self.source = source
        self.lines = source.split("\n")
        self.bp_stack = []
        self.transaction = None
        self.load_transaction_trace()
        self.validate_code()
        self.prepare_ops_mapping()
        self.prepare_sourcemap()
        self.prepare_line_offsets()
        self.init_ast()
        self.load_transaction()
        self.contract_address = self.transaction.to
        self.block_number = self.transaction.blockNumber
        self.breakpoints = []

    def init_ast(self):
        self.contracts = []
        root = contract_data['AST']
        for c in root['children']:
            if c['name'] == 'ContractDefinition':
                contract = Contract()
                contract.parse_ast(c)
                contract.set_storage_locations()
                self.contracts.append(contract)

    def load_transaction(self):
        self.transaction = self.web3.eth.getTransaction(self.transaction_id)

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

            if len(arr) > 2 and arr[2] != '':
                f = int(arr[2])
            else:
                f = self.srcmap[i-1]['f']

            if len(arr) > 3 and arr[3] != '':
                j = arr[3]
            else:
                j = self.srcmap[i-1]['j']

            self.srcmap[i] = {"s": s, "l": l, 'f': f, 'j': j}

    def prepare_line_offsets(self):
        self.offset_by_line = {}
        pos = 0
        for i in range(len(self.lines)):
            self.offset_by_line[i] = pos
            pos += len(self.lines[i]) + 1

    def current_instuction_num(self):
        return self.pc_to_op_idx[self.current_op()['pc']]

    def current_contract(self):
        s = self.current_src_fragment()['s']
        for c in self.contracts:
            if s >= c.src[0] and s < c.src[0] + c.src[1]:
                return c

    def current_func(self, contract):
        s = self.current_src_fragment()['s']
        for f in contract.functions:
            if s >= f.src[0] and s < f.src[0] + f.src[1]:
                return f

    def step(self):
        x = self.current_src_fragment()
        while x == self.current_src_fragment():
            self.advance()

    def next(self):
        depth = 0
        start_stack_height = len(self.bp_stack)
        while True:
            self.step()
            if len(self.bp_stack) == start_stack_height:
                if self.current_src_fragment()['j'] == 'o':
                    self.step()
                break

    def stepout(self):
        start_stack_height = len(self.bp_stack)
        while True:
            self.step()
            if len(self.bp_stack) == start_stack_height - 1:
                if self.current_src_fragment()['j'] == 'o':
                    self.step()
                break

    def continu(self):
        while True:
            self.advance()
            for breakpoint_linenumber in self.breakpoints:
                if breakpoint_linenumber == self.current_line_num():
                    return

    def advance(self):
        self.position += 1
        self.print_op()
        if self.current_src_fragment()['j'] == 'i':
            self.bp_stack.append(len(self.current_op().stack) - 1)
        if self.current_src_fragment()['j'] == 'o' and len(self.bp_stack) > 0:
            self.bp_stack.pop()

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

    def parse_expresion(self, str):
        m = regex.match(r"^(.+?)(?:\[(.+?)\])*$", str)
        if not m:
            return None
        return m.captures(1) + m.captures(2)

    def eval(self, line):
        expr = self.parse_expresion(line)
        if not expr:
            return None

        var_name = expr[0]
        keys = expr[1:]
        contract = self.current_contract()
        function = self.current_func(contract)

        bp = self.bp_stack[len(self.bp_stack) - 1]

        storage_var = contract.find_variable(var_name)

        if var_name in function.params:
            params = function['params']
            param_idx = len(params) - params.index(var_name) - 1
            param_location = bp - param_idx - 1
            return self.current_op().stack[param_location]
        elif var_name in function.local_vars:
            location = bp + function.local_vars.index(var_name) + 1
            return self.current_op().stack[location]
        elif storage_var:
            return self.eval_contract_variable(contract, storage_var, keys)
        else:
            return "Variable not found"

    def eval_storage_bytes(self, address):
        data = self.get_storage_at_address(address)
        data_int = (int).from_bytes(data, 'big')
        large_string = data_int & 0x1
        if large_string:
            bytes_length = (data_int - 1) // 2
            s = sha3.keccak_256()
            s.update(address)
            large_str_address = s.digest()
            result = bytes()
            for i in range(0, bytes_length // 32 + 1):
                address = (int.from_bytes(large_str_address, byteorder='big') + i).to_bytes(32, byteorder='big')
                slot_value = self.get_storage_at_address(address)
                slot_value = slot_value[:bytes_length - i*32]
                result += slot_value
        else:
            bytes_length = (data_int & 0xFF) // 2
            result = data[:bytes_length]

        return result

    def eval_contract_variable(self, contract, var, keys):
        slot = var['location']
        address = slot.to_bytes(32, byteorder='big')
        if regex.match("string", var['type']):
            return str(self.eval_storage_bytes(address), "utf8")
        if regex.match("bytes", var['type']):
            return '0x' + self.eval_storage_bytes(address).hex()
        else:
            for k in keys:
                string_match = regex.match(r"\"(.*)\"", k)
                int_match = regex.match(r"\d+", k)
                if string_match:
                    k = string_match.group(1)
                    s = sha3.keccak_256()
                    s.update(bytes(k, 'utf-8'))
                    s.update(address)
                    address = s.digest()
                elif int_match:
                    k = int(k)
                    s = sha3.keccak_256()
                    s.update(address)
                    address = (int.from_bytes(s.digest(), byteorder='big') + k).to_bytes(32, byteorder='big')

            res = self.get_storage_at_address(address)

            if var['offset'] != 0 or var['type_size'] != 256:
                res_int = int.from_bytes(res, byteorder='big')
                res_int = (res_int >> var['offset']) & ((2 << var['type_size'] - 1) - 1)
                res = res_int.to_bytes(32, byteorder='big')

            return res.hex()

    def get_storage_at_address(self, address):
        op = self.current_op()
        if op.storage and address.hex() in op.storage:
            return bytes.fromhex(op.storage[address.hex()])
        else:
            return self.web3.eth.getStorageAt(Web3.toChecksumAddress(self.contract_address), address, self.block_number - 1)

    def show_lines(self, n = 3, highlight=True):
        line_num = self.current_line_num()
        f = self.current_src_fragment()

        res = []
        for i in range(line_num - n, line_num + n + 1):
            if i >= 0  and i < len(self.lines):
                line = self.lines[i]
                offset = self.offset_by_line[i]

                if highlight:
                    start = f['s'] - offset
                    end = f['s'] - offset + f['l']
                    if start >= 0 and end <= len(line):
                        line = line[0:start] + colored(line[start:end], 'red') + line[end:len(line)]
                    elif start >= 0 and start < len(line):
                        line = line[0:start] + colored(line[start:len(line)], 'red')
                    elif end > 0 and end <= len(line):
                        line = colored(line[0:end], 'red') + line[end:len(line)]
                    elif start < 0 and end > len(line):
                        line = colored(line, 'red')

                res.append([i, line])
        return res

    def repl(self):
        while True:
            self.print_lines()
            line = input("Command: ")
            if line == "next" or line == "n":
                self.next()
            elif line == "step" or line == "s":
                self.step()
            elif line == "stepout" or line == "so":
                self.stepout()
            elif line == "continue" or line == "c":
                self.continu()
            elif line == "":
                self.advance()
            elif line == "stack" or line == "st":
                self.print_stack()
            elif line == "memory" or line == "mem":
                self.print_memory()
            elif str.startswith(line, "break"):
                linenumber = int(line.split(" ")[1])
                self.breakpoints.append(linenumber)
            else:
                print(self.eval(line))

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
            debugger.advance()

transaction_id = open("transaction_id.txt", "r").read()
debugger = Debugger(web3, contract_data, transaction_id, source)
debugger.to_next_jump_dest()
debugger.repl()
