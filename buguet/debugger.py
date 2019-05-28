from web3 import Web3
import readline
from termcolor import colored
import sha3
import regex
from buguet.models import *
from buguet.contract_data_loader import *
from os import path
from buguet.tracer import Tracer
from buguet.parser import *
import json
import copy
import os

class EvalFailed(Exception):
    pass

class VarNotYetInitialized(Exception):
    pass

class Debugger:
    def __init__(self, web3, contracts_data, transaction_id, source_roots = []):
        self.web3 = web3;
        self.transaction_id = transaction_id
        self.source_roots = source_roots
        self.position = 0
        self.bp_stack = []
        self.contracts_stack = []
        self.load_transaction_trace()
        self.init_contracts(contracts_data)
        self.load_transaction()

        if self.transaction.to:
            self.load_contract_by_address(self.transaction.to.lower().replace('0x', ''), False)
        else:
            tx_receipt = web3.eth.waitForTransactionReceipt(self.transaction.hash)
            addr = tx_receipt.contractAddress.lower().replace('0x', '')
            self.load_contract_by_address(addr, True)

        self.breakpoints = []

    def init_contracts(self, contracts_data):
        self.contracts = []

        for contract_data in contracts_data:
            version = self.parse_version(contract_data['version'])

            contract_ast_by_id = {}
            contract_ast_by_name = {}

            source_list = self.resolve_source_list(contract_data['sourceList'])
            sources = []
            for src_path in source_list:
                f = open(src_path, "rb")
                src = f.read()
                f.close()
                sources.append(src.split(b"\n"))

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
                    contract = ContractDataLoader(data, list(reversed(asts)), source_list, sources, version).load()
                    self.contracts.append(contract)

    def resolve_source_list(self, source_list):
        result = []
        for src_path in source_list:
            if not os.path.isabs(src_path):
                abs_path = None
                for src_root in self.source_roots:
                    p = os.path.abspath(os.path.join(src_root, src_path))
                    if os.path.exists(p):
                        abs_path = p
                        break
                if not abs_path:
                    raise Exception(f"Can not find file: {src_path}")
                result.append(abs_path)
            else:
                result.append(src_path)
        return result

    def parse_version(self, version_str):
        m = regex.match(r".*(\d+)\.(\d+)\.(\d+)*", version_str)
        return [int(m.group(1)), int(m.group(2)), int(m.group(3))]

    def load_transaction(self):
        self.transaction = self.web3.eth.getTransaction(self.transaction_id)

    def load_transaction_trace(self):
        self.tracer = Tracer(self.web3, self.transaction_id)
        self.trace_logs = self.tracer.get_base_logs()

    def load_contract_by_address(self, address, is_init):
        code = self.web3.eth.getCode(Web3.toChecksumAddress(address)).hex()
        code = code.replace("0x", "")
        if len(code) > 0:
            el = ContractStackElement(address, self.find_contract_by_code(code), is_init)
            self.contracts_stack.append(el)
            self.bp_stack.append(-1)

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
        metadata_start = code.find("a165627a7a72305820")
        if metadata_start == -1:
            return code
        return code[:metadata_start]

    def current_op(self):
        return self.trace_logs[self.position]

    def is_ended(self):
        return self.position >= len(self.trace_logs)

    def current_instruction_num(self):
        if self.current_contract_is_init():
            pc_to_op_idx = self.current_contract().pc_to_op_idx_init
        else:
            pc_to_op_idx = self.current_contract().pc_to_op_idx_runtime
        return pc_to_op_idx.get(self.current_op()["pc"], -1)

    def current_src_fragment(self):
        if self.current_contract_is_init():
            srcmap = self.current_contract().srcmap_init
        else:
            srcmap = self.current_contract().srcmap_runtime
        instruction_num = self.current_instruction_num()
        if instruction_num == -1:
            return SrcMap(-1, -1, -1, -1)
        return srcmap[instruction_num]

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

    def current_func(self):
        contract = self.current_contract()
        start = self.current_src_fragment().start
        for f in contract.functions:
            if start >= f.src.start and start < f.src.start + f.src.length:
                return f

    def get_storage_at_address(self, address):
        return self.tracer.get_storage(self.position, address.hex())

    def advance(self):
        self.check_function_switch()
        self.check_contract_switch()
        self.position += 1

    def check_function_switch(self):
        if self.current_src_fragment().jump == 'i':
            self.bp_stack.append(self.current_op()['stack_length'] - 1)
        if self.current_src_fragment().jump == 'o' and len(self.bp_stack) > 0:
            self.bp_stack.pop()

    def check_contract_switch(self):
        op = self.current_op()
        if op['op'] in ['CALL', 'DELEGATECALL']:
            address = op['new_address']
            self.load_contract_by_address(address, False)
        elif op['op'] == 'CREATE':
            address = op['new_address']
            self.load_contract_by_address(address, True)
        elif op['op'] in ['STOP', 'RETURN']:
            if self.current_contract_is_init():
                self.bp_stack.pop()
            self.contracts_stack.pop()

    def memory_as_bytes(self, memory):
        res = bytearray()
        for x in memory:
            res += bytes.fromhex(x)
        return res

    def show_lines(self, n = 3):
        src_frag = self.current_src_fragment()
        if (src_frag.file_idx == -1):
            return []
        line_num = self.current_line_number()

        res = []
        for i in range(line_num - n, line_num + n + 1):
            if i >= 0  and i < len(self.current_source()):
                line = self.current_source()[i]

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
                if (bp.src == self.current_source_path()
                        and bp.line == self.current_line_number() + 1):
                    return

    def print_stack(self):
        stack = self.tracer.get_all_stack(self.position)
        for i, x in enumerate(reversed(stack)):
            print(x.hex())
            if (len(stack) - i - 1) in self.bp_stack:
                print()
        print("-----------")
        print("\n")

    def print_memory(self):
        mem = self.tracer.get_all_memory(self.position)
        for i, w in enumerate(mem):
            print(hex(i * 32) + ': ' + w)
        print("-----------")
        print("\n")

    def print_op(self):
        op = self.current_op()
        frag = self.current_src_fragment()
        print(op['op'], end = '')
        if op.get('arg'):
            print(' ' + int(op['arg']).to_bytes(32, 'big').hex(), end = '')
        if frag.jump != '-':
            print(' ' + frag.jump, end = '')
        print()

    def eval(self, line):
        try:
            expr = Parser(line).parse()
            return self.eval_expr(expr)
        except ParsingFailed:
            return "Can not parse expression"
        except EvalFailed:
            return "Can not evaluate expression"
        except VarNotYetInitialized:
            return "Variable is not yet initialized"

    def eval_expr(self, expr):
        if type(expr) is Literal:
            return expr.value
        elif type(expr) is Name:
            return self.eval_var(expr.value)
        elif type(expr) is ApplyBrackets:
            return self.eval_apply_brackets(expr)
        elif type(expr) is ApplyDot:
            return self.eval_apply_dot(expr)

    def eval_var(self, var_name):
        function = self.current_func()
        if not function:
            raise EvalFailed()

        bp = self.bp_stack[-1]
        if bp == -1:
            if self.current_contract_is_init():
                bp = len(function.params) + 0
            else:
                bp = len(function.params) + 2

        var = None
        location = None

        if var_name in function.params_by_name:
            var = function.params_by_name[var_name]
            location = bp - len(function.params) + var.location
        elif var_name in function.local_vars_by_name:
            var = function.local_vars_by_name[var_name]
            location = bp + var.location + len(function.return_vars)
        elif var_name in function.return_vars_by_name:
            var = function.return_vars_by_name[var_name]
            location = bp + var.location

        if var:
            if location >= self.current_op()['stack_length']:
                raise VarNotYetInitialized()
            data = self.tracer.get_stack(self.position, location)
            if type(var.var_type) in [Int, Uint, FixedBytes, Bool, Address]:
                return self.elementary_type_as_obj(var.var_type, data)
            else:
                new_location = (int).from_bytes(data, 'big')
                new_var = Variable(var.var_type, location = new_location, offset = 0, location_type = var.location_type)
                if var.location_type == 'memory':
                    return self.eval_memory(new_var)
                elif var.location_type == 'storage':
                    return self.eval_storage(new_var)
                else:
                    raise EvalFailed()

        if var_name in self.current_contract().variables_by_name:
            var = self.current_contract().variables_by_name[var_name]
            return self.eval_storage(var)
        else:
            raise EvalFailed()

    def eval_apply_brackets(self, expr):
        var = self.eval_expr(expr.left)
        key = self.eval_expr(expr.right)
        if not type(var) is Variable:
            raise EvalFailed()
        if var.location_type == 'memory':
            if type(var.var_type) in [Array, FixedArray]:
                return self.eval_memory_array_at_idx(var, key)
            else:
                raise EvalFailed()
        elif var.location_type == 'storage':
            if type(var.var_type) is Map:
                return self.eval_storage_map_at_key(var, key)
            elif type(var.var_type) is FixedArray:
                return self.eval_storage_fixed_array_at_idx(var, key)
            elif type(var.var_type) is Array:
                return self.eval_storage_array_at_idx(var, key)
            else:
                raise EvalFailed()
        else:
            raise EvalFailed()

    def eval_apply_dot(self, expr):
        var = self.eval_expr(expr.left)
        if not type(var) is Variable or not type(var.var_type) is Struct:
            raise EvalFailed()
        key = expr.right.value
        if var.location_type == 'memory':
            return self.eval_memory_struct_at_key(var, key)
        elif var.location_type == 'storage':
            return self.eval_storage_struct_at_key(var, key)
        else:
            raise EvalFailed()

    def get_memory(self, idx):
        return self.tracer.get_memory(self.position, idx)

    def eval_memory(self, var):
        if type(var.var_type) in [Int, Uint, FixedBytes, Bool, Address]:
            return self.eval_memory_elementary_type(var)
        elif type(var.var_type) in [String, Bytes]:
            return self.eval_memory_string_or_bytes(var)
        else:
            return var

    def eval_memory_elementary_type(self, var):
        data = self.get_memory(var.location)
        return self.elementary_type_as_obj(var.var_type, data)

    def eval_memory_array_at_idx(self, var, idx):
        if type(var.var_type) is FixedArray:
            off = idx
        elif type(var.var_type) is Array:
            off = idx + 1
        addr = var.location + off * 32
        if type(var.var_type.element_type) in [String, Bytes, Struct, Array, FixedArray]:
            addr = int.from_bytes(self.get_memory(addr), byteorder='big')
        new_var = Variable(var.var_type.element_type, location = addr, location_type = 'memory')
        return self.eval_memory(new_var)

    def eval_memory_struct_at_key(self, var, key):
        for i, field in enumerate(var.var_type.variables):
            if field.name == key:
                addr = var.location + i * 32
                if type(field.var_type) in [String, Bytes, Struct, Array, FixedArray]:
                    addr = int.from_bytes(self.get_memory(addr), byteorder='big')
                new_var = Variable(field.var_type, location = addr, location_type = 'memory')
                return self.eval_memory(new_var)
        raise EvalFailed()

    def eval_memory_string_or_bytes(self, var):
        result = bytes()
        length = (int).from_bytes(self.get_memory(var.location), 'big')
        num_memory_words = (length + 31) // 32
        for i in range(num_memory_words):
            data = self.get_memory(var.location + (i + 1) * 32)[:length - i*32]
            result += data
        return self.elementary_type_as_obj(var.var_type, result)

    def eval_storage(self, var):
        if type(var.var_type) in [Int, Uint, FixedBytes, Bool, Address]:
            return self.eval_storage_elementary_type(var)
        elif type(var.var_type) in [String, Bytes]:
            return self.eval_storage_string_or_bytes(var)
        else:
            return var

    def eval_storage_elementary_type(self, var):
        address = var.location.to_bytes(32, byteorder='big')
        result = self.get_storage_at_address(address)
        result_int = int.from_bytes(result, byteorder='big')
        result_int = (result_int >> var.offset) & ((2 << var.var_type.size - 1) - 1)
        result = result_int.to_bytes(var.var_type.size // 8, byteorder='big')
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

    def eval_storage_fixed_array_at_idx(self, var, idx):
        element_type = var.var_type.element_type
        rel_location, offset = self.location_and_offset_for_array_idx(var.var_type, idx)
        location = var.location + rel_location
        new_var = Variable(element_type, location = location, offset = offset, location_type = 'storage')
        return self.eval_storage(new_var)

    def eval_storage_array_at_idx(self, var, idx):
        s = sha3.keccak_256()
        s.update(var.location.to_bytes(32, 'big'))
        elem_address = int.from_bytes(s.digest(), byteorder='big')
        location, offset = self.location_and_offset_for_array_idx(var.var_type, idx)
        new_var = Variable(var.var_type.element_type, location = elem_address + location, offset = offset, location_type = 'storage')
        return self.eval_storage(new_var)

    def eval_storage_map_at_key(self, var, key):
        key_bytes = None

        key_type = var.var_type.key_type

        if type(key_type) == String:
            key_bytes = bytes(key, 'utf-8')
        elif type(key_type) in [Int, Uint]:
            try:
                key_bytes = int(key).to_bytes(32, "big")
            except ValueError:
               raise EvalFailed()
        elif type(key_type) is Address:
            key_bytes = bytes(12) + bytes.fromhex(key.replace("0x", ""))
        elif type(key_type) is Bytes:
            key_bytes = bytes.fromhex(key.replace("0x", ""))
        elif type(key_type) is FixedBytes:
            key_bytes = bytes.fromhex(key.replace("0x", ""))
            key_bytes =  key_bytes + bytes(32 - len(key_bytes))
        elif type(key_type) is Bool:
            if key:
                key_bytes = (1).to_bytes(32, "big")
            else:
                key_bytes = (0).to_bytes(32, "big")
        else:
            raise EvalFailed()

        s = sha3.keccak_256()
        s.update(key_bytes)
        s.update(var.location.to_bytes(32, 'big'))
        value_address = s.digest()
        value_type = var.var_type.value_type
        location = int.from_bytes(value_address, 'big')
        var = Variable(value_type, location = location, offset = 0, location_type = 'storage')
        return self.eval_storage(var)

    def eval_storage_struct_at_key(self, var, key):
        for field in var.var_type.variables:
            if field.name == key:
                location = var.location + field.location
                new_var = Variable(field.var_type, location = location, offset = field.offset, location_type = 'storage')
                return self.eval_storage(new_var)

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

    def add_breakpoint(self, breakpoint):
        abs_path = None
        for contract in self.contracts:
            for src_path in contract.source_list:
                if breakpoint.src in src_path:
                    abs_path = src_path
                    break
        if abs_path:
            bp = Breakpoint(abs_path, breakpoint.line)
            self.breakpoints.append(bp)
            return bp

    def repl(self):
        self.print_lines()
        while not self.is_ended():
            line = input("Command: ")
            if line == "next" or line == "n":
                self.next()
                if not self.is_ended():
                    self.print_lines()
            elif line == "step" or line == "s":
                self.step()
                if not self.is_ended():
                    self.print_lines()
            elif line == "stepout" or line == "so":
                self.stepout()
                if not self.is_ended():
                    self.print_lines()
            elif line == "continue" or line == "c":
                self.continu()
                if not self.is_ended():
                    self.print_lines()
            elif line == "stack" or line == "st":
                self.print_stack()
            elif line == "memory" or line == "mem":
                self.print_memory()
            elif str.startswith(line, "break "):
                bp = self.parse_breakpoint(line.split(" ")[1])
                if bp:
                    bp = self.add_breakpoint(bp)
                    if bp:
                        print(f"Breakpoint is set at {bp.src}:{bp.line}")
                    else:
                        print(f"Breakpoint is not set. Location is not found.")
                else:
                    print("Breakpoint is invalid. Specify in format file:line")
            elif str.startswith(line, "breakpoints"):
                for i, bp in enumerate(self.breakpoints):
                    print(f"[{i}] {bp.src}:{bp.line}")
            elif str.startswith(line, "unbreak "):
                arr = line.split(" ")
                if len(arr) == 2:
                    try:
                        num = int(arr[1])
                        if num < len(self.breakpoints) and num >= 0:
                            self.breakpoints.pop(num)
                    except ValueError:
                        pass
            elif line == "op":
                self.print_op()
                self.advance()
                if not self.is_ended():
                    self.print_lines()
            else:
                print(self.eval(line))

    def print_lines(self, n = 3):
        lines = self.show_lines(n)
        print()
        path = self.current_contract().source_list[self.current_src_fragment().file_idx]
        print(colored(self.current_contract_address(), "blue") + "#" + colored(path, "green"))
        for i, line in enumerate(lines):
            if len(lines) // 2 == i:
                print(" => ", end='')
            else:
                print("    ", end='')
            print(":" + str(line[0]) + ' ', end='')
            print(line[1])

def ppp(x):
    print(json.dumps(x, default=lambda o: {**o.__dict__, 'type': type(o).__name__ }, sort_keys=True, indent=4))
