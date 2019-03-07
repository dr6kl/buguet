from web3 import Web3
import readline
from termcolor import colored
import sha3
import regex
from buguet.models import *
from buguet.contract_data_loader import *
from os import path

class Debugger:
    def __init__(self, web3, contracts_data, transaction_id):
        self.web3 = web3;
        self.transaction_id = transaction_id
        self.position = 0
        self.bp_stack = []
        self.bp_stack.append(-1)
        self.contracts_stack = []
        self.load_transaction_trace()
        self.init_contracts(contracts_data)
        self.load_transaction()
        if self.transaction.to:
            self.load_contract_by_address(self.transaction.to)
        else:
            code =  self.transaction.input.replace("0x", "")
            contract = self.find_contract_by_init_code(code)
            tx_receipt = web3.eth.waitForTransactionReceipt(self.transaction.hash)
            el = ContractStackElement(tx_receipt.contractAddress, contract, True)
            self.contracts_stack.append(el)

        self.block_number = self.transaction.blockNumber
        self.breakpoints = []

    def init_contracts(self, contracts_data):
        self.contracts = []

        for contract_data in contracts_data:
            contract_ast_by_id = {}
            contract_ast_by_name = {}

            source_list = contract_data['sourceList']
            sources = []
            for src_path in source_list:
                sources.append(open(src_path, "rb").read().split(b"\n"))

            for key in contract_data['sources']:
                base_ast = contract_data['sources'][key]['AST']
                for contract_ast in base_ast.get('children', []):
                    if contract_ast['name'] == 'ContractDefinition':
                        contract_ast_by_id[contract_ast['id']] = contract_ast
                        contract_ast_by_name[contract_ast['attributes']['name']] = contract_ast

            for key in contract_data.get('contracts', []):
                name = key.split(":")[1]
                asts = []
                for contract_id in contract_ast_by_name[name]['attributes']['linearizedBaseContracts']:
                    asts.append(contract_ast_by_id[contract_id])
                data = contract_data['contracts'][key]
                if data['bin']:
                    contract = ContractDataLoader(data, list(reversed(asts)), source_list, sources).load()
                    self.contracts.append(contract)

    def load_transaction(self):
        self.transaction = self.web3.eth.getTransaction(self.transaction_id)

    def load_transaction_trace(self):
        print("Loading transaction trace...")
        res = self.web3.manager.request_blocking("debug_traceTransaction", [self.transaction_id])
        print("Done")
        self.struct_logs = res.structLogs

    def load_contract_by_address(self, address):
        code = self.web3.eth.getCode(Web3.toChecksumAddress(address)).hex()
        code = code.replace("0x", "")
        el = ContractStackElement(address, self.find_contract_by_code(code), False)
        self.contracts_stack.append(el)

    def find_contract_by_code(self, code):
        code = self.cut_bin_metadata(code)
        for contract in self.contracts:
            if self.cut_bin_metadata(contract.bin_runtime) == code:
                return contract
        raise Exception("No matching contract found in provided solidity data")

    def find_contract_by_init_code(self, code):
        code = self.cut_bin_metadata(code)
        for contract in self.contracts:
            if self.cut_bin_metadata(contract.bin_init) == code:
                return contract
        raise Exception("No matching contract found in provided solidity data")

    def current_contract(self):
        return self.contracts_stack[-1].contract

    def current_contract_address(self):
        return self.contracts_stack[-1].address

    def current_contract_is_init(self):
        return self.contracts_stack[-1].is_init

    def cut_bin_metadata(self, code):
        metadata_start = code.index("a165627a7a72305820")
        return code[:metadata_start]

    def current_op(self):
        return self.struct_logs[self.position]

    def is_ended(self):
        return self.position >= len(self.struct_logs)

    def current_instuction_num(self):
        if self.current_contract_is_init():
            pc_to_op_idx = self.current_contract().pc_to_op_idx_init
        else:
            pc_to_op_idx = self.current_contract().pc_to_op_idx_runtime
        return pc_to_op_idx[self.current_op()['pc']]

    def current_src_fragment(self):
        if self.current_contract_is_init():
            srcmap = self.current_contract().srcmap_init
        else:
            srcmap = self.current_contract().srcmap_runtime
        return srcmap[self.current_instuction_num()]

    def current_source(self):
        return self.current_contract().sources[self.current_src_fragment().file_idx]

    def current_source_path(self):
        return self.current_contract().source_list[self.current_src_fragment().file_idx]

    def current_line_number(self):
        frag = self.current_src_fragment()
        offset_by_line = self.current_contract().source_offsets[frag.file_idx]
        offset = frag.start
        start = 0
        end = len(offset_by_line)
        while True:
            idx = (start + end) // 2
            s = offset_by_line[idx]
            if offset >= s and offset < s + len(self.current_source()[idx]) + 1:
                return idx
            elif offset < s:
                end = idx - 1
            elif offset >= s + len(self.current_source()[idx]) + 1:
                start = idx + 1

    def current_func(self, contract):
        start = self.current_src_fragment().start
        for f in contract.functions:
            if start >= f.src.start and start < f.src.start + f.src.length:
                return f

    def get_storage_at_address(self, address):
        op = self.current_op()
        if op.storage and address.hex() in op.storage:
            return bytes.fromhex(op.storage[address.hex()])
        else:
            return self.web3.eth.getStorageAt(
                    Web3.toChecksumAddress(self.current_contract_address()),
                    address, self.block_number - 1)

    def advance(self):
        self.check_function_switch()
        self.check_contract_switch()
        self.position += 1

    def check_function_switch(self):
        if self.current_src_fragment().jump == 'i':
            self.bp_stack.append(len(self.current_op().stack) - 1)
        if self.current_src_fragment().jump == 'o' and len(self.bp_stack) > 0:
            self.bp_stack.pop()

    def check_contract_switch(self):
        op = self.current_op()
        if op.op == 'CALL':
            address = op.stack[-2][24:]
            self.load_contract_by_address(address)
            self.bp_stack.append(-1)
        elif op.op == 'CREATE':
            offset = int.from_bytes(bytes.fromhex(op.stack[-2]), 'big')
            length = int.from_bytes(bytes.fromhex(op.stack[-3]), 'big')
            code = self.memory_as_bytes(op.memory)[offset:offset+length].hex()
            contract = self.find_contract_by_init_code(code)
            address = self.scan_created_address()
            el = ContractStackElement(address, contract, True)
            self.contracts_stack.append(el)
        elif op.op in ['STOP', 'RETURN']:
            self.contracts_stack.pop()

    def memory_as_bytes(self, memory):
        res = bytearray()
        for x in memory:
            res += bytes.fromhex(x)
        return res

    def scan_created_address(self):
        i = self.position
        call_depth = 1
        while True:
            i += 1
            op = self.struct_logs[i]
            if op.op in ['STOP', 'RETURN']:
                call_depth -= 1
            if op.op in ['CALL', 'CREATE']:
                call_depth += 1
            if call_depth == 0:
                break
        return self.struct_logs[i+1].stack[-1][-40:]

    def show_lines(self, n = 3, highlight=True):
        src_frag = self.current_src_fragment()
        if (src_frag.file_idx == -1):
            return []
        line_num = self.current_line_number()

        res = []
        for i in range(line_num - n, line_num + n + 1):
            if i >= 0  and i < len(self.current_source()):
                line = self.current_source()[i]

                if highlight:
                    offset = self.current_contract().source_offsets[src_frag.file_idx][i]
                    start = src_frag.start - offset
                    end = src_frag.start - offset + src_frag.length
                    if start >= 0 and end <= len(line):
                        line = str(line[0:start], "utf8") + colored(str(line[start:end], "utf8"), 'red') + str(line[end:len(line)],"utf8")
                    elif start >= 0 and start < len(line):
                        line = str(line[0:start], "utf8") + colored(str(line[start:len(line)], "utf8"), 'red')
                    elif end > 0 and end <= len(line):
                        line = colored(str(line[0:end], "utf8"), 'red') + str(line[end:len(line)], "utf8")
                    elif start < 0 and end > len(line):
                        line = colored(str(line, "utf8"), 'red')
                    else:
                        line = str(line, "utf8")

                res.append([i + 1, line])
        return res

    def step(self):
        x = self.current_src_fragment()
        while x == self.current_src_fragment() or self.current_src_fragment().file_idx == -1:
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
                if self.current_src_fragment().jump == 'o':
                    self.step()
                break

    def stepout(self):
        start_stack_height = len(self.bp_stack)
        while True:
            self.step()
            if self.is_ended():
                return
            if len(self.bp_stack) == start_stack_height - 1:
                break

    def continu(self):
        while True:
            self.step()
            if self.is_ended():
                return
            for bp in self.breakpoints:
                if (bp.src in self.current_source_path()
                        and bp.line == self.current_line_number() + 1):
                    return

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
        op = self.struct_logs[self.position].op
        print(op, end=' ')
        if str.startswith(op, 'PUSH') and self.position < len(self.struct_logs):
            next_stack = self.struct_logs[self.position + 1]['stack']
            print(next_stack[len(next_stack) - 1], end='')
        print()

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
        function = self.current_func(self.current_contract())

        bp = self.bp_stack[-1]
        if bp == -1:
            bp = len(function.params) + 2

        if var_name in function.params_by_name:
            var = function.params_by_name[var_name]
            location = bp - len(function.params) + var.location
            new_var = Variable(var.var_type, location = location, location_type = var.location_type)
            return self.eval_stack(new_var, keys)
        elif var_name in function.local_vars_by_name:
            var = function.local_vars_by_name[var_name]
            location = bp + var.location + function.return_count
            new_var = Variable(var.var_type, location = location, location_type = var.location_type)
            return self.eval_stack(new_var, keys)
        elif var_name in self.current_contract().variables_by_name:
            var = self.current_contract().variables_by_name[var_name]
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
        else:
            if type(var.var_type) == FixedArray:
                length = var.var_type.length
            elif type(var.var_type) == Array:
                length = (int).from_bytes(self.get_memory(var.location), 'big')
            result = []
            for i in range(length):
                result.append(self.eval_memory(var, [i]))
            return result

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

        key = keys[0]
        key_bytes = None

        key_type = var.var_type.key_type

        if type(key_type) == String:
            key_match = regex.match(r"\"(.*)\"", key)
            if key_match:
                k = key_match.group(1)
                key_bytes = bytes(k, 'utf-8')
        elif type(key_type) in [Int, Uint]:
            try:
                key_bytes = int(key).to_bytes(32, "big")
            except ValueError:
                return
        elif type(key_type) == Address:
            key_bytes = bytes(12) + bytes.fromhex(key.replace("0x", ""))
        elif type(key_type) == Bytes:
            key_bytes = bytes.fromhex(key.replace("0x", ""))
        elif type(key_type) == Bool:
            if key == "true":
                key_bytes = (1).to_bytes(32, "big")
            else:
                key_bytes = (0).to_bytes(32, "big")

        if not key_bytes:
            return

        s = sha3.keccak_256()
        s.update(key_bytes)
        s.update(var.location.to_bytes(32, 'big'))
        value_address = s.digest()
        value_type = var.var_type.value_type
        location = int.from_bytes(value_address, 'big')
        new_var = Variable(value_type, location = location, offset = 0)
        return self.eval_storage(new_var, keys[1:])

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
            length = (int).from_bytes(self.get_storage_at_address(var.location.to_bytes(32, 'big')), 'big')
            result = []
            for i in range(length):
                result.append(self.eval_storage_array(var, [i]))
            return result
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
                return True
            else:
                return False
        if type(var_type) is String:
            return str(data, 'utf8')
        if type(var_type) is Address:
            return data[-20:].hex()

        return data.hex()

    def parse_breakpoint(self, bp):
        arr = bp.split(":")
        if len(arr) != 2:
            return
        try:
            filename, line = arr[0], int(arr[1])
            return Breakpoint(filename, line)
        except ValueError:
            return

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
            elif str.startswith(line, "break "):
                bp = self.parse_breakpoint(line.split(" ")[1])
                if bp:
                    self.breakpoints.append(bp)
                    print("Breakpoint is set")
                else:
                    print("Breakpoint is invalid")
            elif line == "op":
                self.print_op()
                self.advance()
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
