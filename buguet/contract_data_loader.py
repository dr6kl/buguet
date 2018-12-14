from buguet.models import *
import regex
import beeprint
import pdb

class ContractDataLoader:
    def __init__(self, data, asts):
        self.struct_asts = {}
        self.structs = {}
        self.data = data
        self.asts = asts

    def load(self):
        variables = []
        functions = []

        self.load_struct_asts()

        src_arr = list(map(lambda x: int(x), self.asts[0]['src'].split(":")))
        src = SrcMap(src_arr[0], src_arr[1], src_arr[2], '')

        name = self.asts[0]['attributes']['name']

        for ast in self.asts:
            for x in ast['children']:
                if x['name'] == 'FunctionDefinition':
                    func = self.parse_function(x)
                    functions.append(func)
                if x['name'] == 'VariableDeclaration':
                    var = self.parse_variable(x)
                    variables.append(var)

        contract = Contract(
                name,
                src,
                functions,
                variables,
                self.prepare_ops_mapping(),
                self.prepare_sourcemap(),
                self.data['bin-runtime']
            )

        self.set_locations(contract)
        return contract

    def load_struct_asts(self):
        for ast in self.asts:
            for x in ast['children']:
                if x['name'] == 'StructDefinition':
                    self.struct_asts[x['attributes']['name']] = x

    def init_struct(self, struct_name):
        ast = self.struct_asts[struct_name]
        variables = []
        for x in ast['children']:
            if x['name'] == 'VariableDeclaration':
                var = self.parse_variable(x)
                variables.append(var)
        self.structs[struct_name] = Struct(struct_name, variables)

    def parse_variable(self, ast):
        return Variable(
                self.parse_type(ast['children'][0]),
                ast['attributes']['name']
        )

    def parse_type(self, type_ast):
        type_str = type_ast['attributes']['type']

        match = regex.match("^int(\d+)$", type_str)
        if match:
            return Int(int(match.group(1)))

        match = regex.match("^uint(\d+)$", type_str)
        if match:
            return Uint(int(match.group(1)))

        match = regex.match("^bool$", type_str)
        if match:
            return Bool()

        match = regex.match("^bytes(\d+)$", type_str)
        if match:
            return FixedBytes(int(match.group(1)) * 8)

        match = regex.match("bytes.*", type_str)
        if match:
            return Bytes()

        match = regex.match("string.*", type_str)
        if match:
            return String()

        match = regex.match("address", type_str)
        if match:
            return Address()

        if type_ast['name'] == 'ArrayTypeName':
            if len(type_ast['children']) == 2:
                length = int(type_ast['children'][1]['attributes']['value'])
                elemType = self.parse_type(type_ast['children'][0])
                return FixedArray(elemType, length)
            else:
                element_type = self.parse_type(type_ast['children'][0])
                result = Array(element_type)
                return result

        if type_ast['name'] == 'Mapping':
            key_type = self.parse_type(type_ast['children'][0])
            value_type = self.parse_type(type_ast['children'][1])
            result = Map(key_type, value_type)
            return result

        if type_ast['name'] == 'UserDefinedTypeName':
            struct_name = type_ast['attributes']['name']
            if 'struct' in type_ast['attributes']['type']:
                if not struct_name in self.structs:
                    self.init_struct(struct_name)

                return self.structs[struct_name]
            elif 'contract' in type_ast['attributes']['type']:
                return ContractType()

    def set_locations(self, obj):
        location = 0
        bits_consumed = 0

        for var in obj.variables:
            if type(var.var_type) in [FixedArray, Struct]:
                if bits_consumed > 0:
                    location += 1
                    bits_consumed = 0
                var.location = location
                var.offset = 0
                if var.var_type.size == None:
                    self.set_size(var.var_type)
                location += var.var_type.size // 256
                bits_consumed = 0
            else:
                if bits_consumed + var.var_type.size > 256:
                    bits_consumed = 0
                    location += 1

                var.location = location
                var.offset = bits_consumed
                bits_consumed += var.var_type.size

    def set_size(self, var_type):
        if type(var_type) is FixedArray:
            if var_type.element_type.size is None:
                self.set_size(var_type.element_type)

            elem_size = var_type.element_type.size
            if elem_size < 256:
                elems_per_slot = (256 // elem_size)
                var_type.size = ((var_type.length + elems_per_slot - 1) // elems_per_slot) * 256
            else:
                slot_per_elems = elem_size // 256
                var_type.size = var_type.length * slot_per_elems * 256

        elif type(var_type) is Struct:
            self.set_locations(var_type)
            last_var = var_type.variables[-1]
            var_type.size = (last_var.location + ((last_var.var_type.size + 255) // 256)) * 256

    def parse_function(self, ast):
        name = ast['attributes']['name']

        src_arr = list(map(lambda x: int(x), ast['src'].split(":")))
        src = SrcMap(src_arr[0], src_arr[1], src_arr[2], '')

        params = []
        for x in ast['children']:
            if x['name'] == 'ParameterList' and not params:
                if x['children']:
                    for y in x['children']:
                        if y['name'] == 'VariableDeclaration':
                            var_name = y['attributes']['name']
                            if var_name:
                                params.append(self.parse_function_variable(y))
            if x['name'] == 'Block':
                local_vars = []
                def process_function_node(node):
                    if node['name'] == 'VariableDeclaration':
                        local_vars.append(self.parse_function_variable(node))
                self.traverse_all(x, lambda x: process_function_node(x))
        for i, p in enumerate(params):
            params[i].location = i
        for i, p in enumerate(local_vars):
           local_vars[i].location = i
        return Function(name, src, params, local_vars)

    def parse_function_variable(self, ast):
        if 'memory' in ast['attributes']['type']:
            location_type = 'memory'
        elif 'storage' in ast['attributes']['type']:
            location_type = 'storage'
        else:
            location_type = None
        var = self.parse_variable(ast)
        var.location_type = location_type
        return var

    def traverse_all(self, node, f):
        f(node)
        if 'children' in node:
            for c in node['children']:
                self.traverse_all(c, f)

    def prepare_ops_mapping(self):
        pc_to_op_idx = {}
        code = bytes.fromhex(self.data['bin-runtime'])
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
            pc_to_op_idx[i] = op_num
            for j in range(operands_size):
                pc_to_op_idx[i + j + 1] = op_num
            i += (1 + operands_size)
            op_num += 1
        return pc_to_op_idx

    def prepare_sourcemap(self):
        srcmap = {}

        map_items = self.data['srcmap-runtime'].split(";")

        for i in range(len(map_items)):
            map_item = map_items[i]
            arr = map_item.split(":")

            if len(arr) > 0 and arr[0] != '':
                start = int(arr[0])
            else:
                start = srcmap[i-1].start

            if len(arr) > 1 and arr[1] != '':
                length = int(arr[1])
            else:
                lenght = srcmap[i-1].length

            if len(arr) > 2 and arr[2] != '':
                file_idx = int(arr[2])
            else:
                file_idx = srcmap[i-1].file_idx

            if len(arr) > 3 and arr[3] != '':
                jump = arr[3]
            else:
                jump = srcmap[i-1].jump

            srcmap[i] = SrcMap(start, length, file_idx, jump)
        return srcmap
