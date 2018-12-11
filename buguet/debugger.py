import pdb
import binascii
from web3 import Web3
import readline
from termcolor import colored
import sha3
import regex
from collections import namedtuple
import beeprint
from buguet.models import *
from buguet.contract_data_loader import *

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
        root = self.contract_data['AST']
        for c in root['children']:
            if c['name'] == 'ContractDefinition':
                contract = ContractDataLoader(c).load()
                self.contracts.append(contract)

    def load_transaction(self):
        self.transaction = self.web3.eth.getTransaction(self.transaction_id)

    def load_transaction_trace(self):
        print("Loading transaction trace...")
        res = self.web3.manager.request_blocking("debug_traceTransaction", [self.transaction_id])
        print("Done")
        self.struct_logs = res.structLogs

    def validate_code(self):
        tx = self.web3.eth.getTransaction(self.transaction_id)
        code = self.web3.eth.getCode(tx.to)
        code = binascii.hexlify(code).decode('utf-8')
        if not code == self.contract_data['bin-runtime']:
            raise Exception("Contract code doesn't match")

    def prepare_ops_mapping(self):
        self.pc_to_op_idx = {}
        code = bytes.fromhex(self.contract_data['bin-runtime'])
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
            if self.is_ended():
                return

    def next(self):
        depth = 0
        start_stack_height = len(self.bp_stack)
        while True:
            self.step()
            if self.is_ended():
                return
            if len(self.bp_stack) == start_stack_height:
                if self.current_src_fragment()['j'] == 'o':
                    self.step()
                break

    def stepout(self):
        start_stack_height = len(self.bp_stack)
        while True:
            self.step()
            if self.is_ended():
                return
            if len(self.bp_stack) == start_stack_height - 1:
                if self.current_src_fragment()['j'] == 'o':
                    self.step()
                break

    def continu(self):
        while True:
            self.advance()
            if self.is_ended():
                return
            for breakpoint_linenumber in self.breakpoints:
                if breakpoint_linenumber == self.current_line_num() + 1:
                    return

    def is_ended(self):
        return self.position >= len(self.struct_logs)


    def advance(self):
        self.position += 1
        if self.is_ended():
            return
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

    def parse_expression(self, str):
        m = regex.match(r"^(.+?)((\[(.+?)\])|(\.(.+?)))*$", str)
        if not m:
            return None
        result = []
        result.append(m.captures(1)[0])
        for capture in m.captures(2):
            if capture.startswith("["):
                result.append(capture[1:-1])
            else:
                result.append(capture[1:])
        return result

    def eval(self, line):
        expr = self.parse_expression(line)
        if not expr:
            return None

        var_name = expr[0]
        keys = expr[1:]
        contract = self.current_contract()
        function = self.current_func(contract)

        bp = self.bp_stack[-1]

        if var_name in function.params_by_name:
            var = function.params_by_name[var_name]
            location = bp - len(function.params) + var.location
            new_var = Variable(var.var_type, location = location, location_type = var.location_type)
            return self.eval_stack(new_var, keys)
        elif var_name in function.local_vars_by_name:
            var = function.local_vars_by_name[var_name]
            location = bp + var.location + 1
            new_var = Variable(var.var_type, location = location, location_type = var.location_type)
            return self.eval_stack(new_var, keys)
        elif var_name in contract.variables_by_name:
            var = contract.variables_by_name[var_name]
            return self.eval_storage(var, keys)
        else:
            return "Can not evaluate expression"

    def eval_stack(self, var, keys):
        stack = self.current_op().stack
        if var.location >= len(stack):
            return "Variable is not yet initialized"
        data = bytes.fromhex(stack[var.location])
        if type(var.var_type) in [Int, Uint, FixedBytes, Bool, Address]:
            return self.elementary_type_as_obj(var.var_type, data)
        else:
            location = (int).from_bytes(data, 'big')
            new_var = Variable(var.var_type, location = location, offset = 0)
            if var.location_type == 'memory':
                return self.eval_memory(new_var, keys)
            elif var.location_type == 'storage':
                return self.eval_storage(new_var, keys)

    def get_memory(self, idx):
        return bytes.fromhex(self.current_op().memory[idx//32])

    def eval_memory(self, var, keys):
        if type(var.var_type) in [Int, Uint, FixedBytes, Bool, Address]:
            return self.eval_memory_elementary_type(var)
        if type(var.var_type) in [Array, FixedArray]:
            return self.eval_memory_array(var, keys)
        if type(var.var_type) is Struct:
            return self.eval_memory_struct(var, keys)
        if type(var.var_type) in [String, Bytes]:
            return self.eval_memory_string_or_bytes(var)

    def eval_memory_elementary_type(self, var):
        data = self.get_memory(var.location)
        return self.elementary_type_as_obj(var.var_type, data)

    def eval_memory_array(self, var, keys):
        if keys:
            if type(var.var_type) == FixedArray:
                idx = int(keys[0])
            elif type(var.var_type) == Array:
                idx = int(keys[0]) + 1
            addr = var.location + idx * 32
            if not type(var.var_type.element_type) in [Int, Uint, FixedBytes, Bool, Address]:
                addr = (int).from_bytes(self.get_memory(addr), 'big')
            new_var = Variable(var.var_type.element_type, location = addr)
            return self.eval_memory(new_var, keys[1:])

    def eval_memory_struct(self, var, keys):
        if keys:
            key = keys[0]
            for i, field in enumerate(var.var_type.variables):
                if field.name == key:
                    addr = var.location + i * 32
                    if not type(field.var_type) in [Int, Uint, FixedBytes, Bool, Address]:
                        addr = (int).from_bytes(self.get_memory(addr), 'big')
                    new_var = Variable(field.var_type, location = addr)
                    return self.eval_memory(new_var, keys[1:])
        else:
            result = {}
            for field in var.var_type.variables:
                result[field.name] = self.eval_memory_struct(var, [field.name])
            return result

    def eval_memory_string_or_bytes(self, var):
        result = bytes()
        length = (int).from_bytes(self.get_memory(var.location), 'big')
        num_memory_words = (length + 31) // 32
        for i in range(num_memory_words):
            data = self.get_memory(var.location + (i + 1) * 32)[:length - i*32]
            result += data
        return self.elementary_type_as_obj(var.var_type, result)

    def eval_storage_string_or_bytes(self, var):
        address = var.location.to_bytes(32, 'big')
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
                value = self.get_storage_at_address(address)
                value = value[:bytes_length - i*32]
                result += value
        else:
            bytes_length = (data_int & 0xFF) // 2
            result = data[:bytes_length]

        return self.elementary_type_as_obj(var.var_type, result)

    def eval_storage_fixed_array(self, var, keys):
        if keys:
            idx = int(keys[0])
            return self.eval_storage_fixed_array_at_idx(var, keys[1:], idx)
        else:
            result = []
            for i in range(0, var.var_type.length):
                result.append(self.eval_storage_fixed_array_at_idx(var, [], i))
            return result

    def eval_storage_fixed_array_at_idx(self, var, keys, idx):
        element_type = var.var_type.element_type
        rel_location, offset = self.location_and_offset_for_array_idx(var.var_type, idx)
        location = var.location + rel_location
        new_var = Variable(element_type, location = location, offset = offset)
        return self.eval_storage(new_var, keys)

    def eval_storage_map(self, var, keys):
        if not keys:
            return "Mapping"
        key_match = regex.match(r"\"(.*)\"", keys[0])
        if key_match:
            k = key_match.group(1)
            s = sha3.keccak_256()
            s.update(bytes(k, 'utf-8'))
            s.update(var.location.to_bytes(32, 'big'))
            value_address = s.digest()
            value_type = var.var_type.value_type
            location = int.from_bytes(value_address, 'big')
            new_var = Variable(value_type, location = location, offset = 0)
            return self.eval_storage(new_var, keys[1:])
        else:
            return None

    def eval_storage_struct(self, var, keys):
        if keys:
            key = keys[0]
            for field in var.var_type.variables:
                if field.name == key:
                    location = var.location + field.location
                    new_var = Variable(field.var_type, location = location, offset = field.offset)
                    return self.eval_storage(new_var, keys[1:])
        else:
            result = {}
            for field in var.var_type.variables:
                location = var.location + field.location
                offset = field.offset
                new_var = Variable(field.var_type, location = location, offset = offset)
                value = self.eval_storage(new_var, [])
                result[field.name] = value
            return result

    def eval_storage_array(self, var, keys):
        if not keys:
            return "DynamicArray"
        idx = int(keys[0])
        s = sha3.keccak_256()
        s.update(var.location.to_bytes(32, 'big'))
        elem_address = int.from_bytes(s.digest(), byteorder='big')
        location, offset = self.location_and_offset_for_array_idx(var.var_type, idx)
        new_var = Variable(var.var_type.element_type, location = elem_address + location, offset = offset)
        return self.eval_storage(new_var, keys[1:])

    def location_and_offset_for_array_idx(self, arr, idx):
        if arr.element_type.size < 256:
            elems_per_slot = (256 // arr.element_type.size)
            location = idx // elems_per_slot
            offset = (idx % elems_per_slot) * arr.element_type.size
        else:
            slot_per_elems = arr.element_type.size // 256
            location = idx * slot_per_elems
            offset = 0
        return [location, offset]

    def eval_storage_elementary_type(self, var):
        address = var.location.to_bytes(32, byteorder='big')
        result = self.get_storage_at_address(address)
        result_int = int.from_bytes(result, byteorder='big')
        result_int = (result_int >> var.offset) & ((2 << var.var_type.size - 1) - 1)
        result = result_int.to_bytes(var.var_type.size // 8, byteorder='big')
        return self.elementary_type_as_obj(var.var_type, result)

    def eval_storage(self, var, keys):
        if type(var.var_type) in [Int, Uint, FixedBytes, Bool, Address]:
            return self.eval_storage_elementary_type(var)
        elif type(var.var_type) in [String, Bytes]:
            return self.eval_storage_string_or_bytes(var)
        elif type(var.var_type) is FixedArray:
            return self.eval_storage_fixed_array(var, keys)
        elif type(var.var_type) is Map:
            return self.eval_storage_map(var, keys)
        elif type(var.var_type) is Struct:
            return self.eval_storage_struct(var, keys)
        elif type(var.var_type) is Array:
            return self.eval_storage_array(var, keys)

    def elementary_type_as_obj(self, var_type, data):
        if type(var_type) is Int:
            return (int).from_bytes(data, byteorder = 'big', signed = True)
        if type(var_type) is Uint:
            return (int).from_bytes(data, byteorder = 'big', signed = False)
        if type(var_type) is Bool:
            if (int).from_bytes(data, 'big') == 1:
                return 'true'
            else:
                return 'false'
        if type(var_type) is String:
            return str(data, 'utf8')

        return '0x' + data.hex()

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

                res.append([i + 1, line])
        return res

    def repl(self):
        while not self.is_ended():
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
        while(self.current_op()['op'] != 'JUMPDEST'):
            self.advance()

