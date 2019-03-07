from buguet.models import *
import regex

class ContractDataLoader:
    def __init__(self, data, asts, source_list, sources):
        self.struct_asts = {}
        self.structs = {}
        self.data = data
        self.asts = asts
        self.source_list = source_list
        self.sources = sources

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
                if x['name'] == 'VariableDeclaration' and not x['attributes'].get('constant'):
                    var = self.parse_variable(x)
                    variables.append(var)

        contract = Contract(
                name,
                src,
                functions,
                variables,
                self.data['bin-runtime'],
                self.prepare_ops_mapping(self.data['bin-runtime']),
                self.prepare_sourcemap(self.data['srcmap-runtime']),
                self.data['bin'],
                self.prepare_ops_mapping(self.data['bin']),
                self.prepare_sourcemap(self.data['srcmap']),
                self.source_list,
                self.sources,
                self.prepare_line_offsets()
            )

        self.set_locations(contract)
        for struct in self.structs.values():
            if not struct.size:
                self.set_size(struct)
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
                self.parse_type(ast['attributes']['type']),
                ast['attributes']['name']
        )

    def parse_type(self, type_str):
        match = regex.match("int(\d+)$", type_str)
        if match:
            return Int(int(match.group(1)))

        match = regex.match("uint(\d+)$", type_str)
        if match:
            return Uint(int(match.group(1)))

        match = regex.match("bool$", type_str)
        if match:
            return Bool()

        match = regex.match("bytes(\d+)$", type_str)
        if match:
            return FixedBytes(int(match.group(1)) * 8)

        location_regex = "(( storage \w+)| memory)?"

        match = regex.match(f"bytes{location_regex}$", type_str)
        if match:
            return Bytes()

        match = regex.match(f"string{location_regex}$", type_str)
        if match:
            return String()

        match = regex.match("address$", type_str)
        if match:
            return Address()

        match = regex.match(f"struct \w+\.(\w+){location_regex}$", type_str)
        if match:
            struct_name = match.group(1)
            if not struct_name in self.structs:
                self.init_struct(struct_name)
            return self.structs[struct_name]

        match = regex.match("contract \w+", type_str)
        if match:
            return Address()

        match = regex.match(f"(.*)\[(\d+)\]{location_regex}$", type_str)
        if match:
            length = int(match.group(2))
            elemType = self.parse_type(match.group(1))
            return FixedArray(elemType, length)

        match = regex.match("mapping\((.*?) => (.*)\)$", type_str)
        if match:
            key_type = self.parse_type(match.group(1))
            value_type = self.parse_type(match.group(2))
            result = Map(key_type, value_type)
            return result

        match = regex.match(f"(.*)\[\]{location_regex}$", type_str)
        if match:
            elemType = self.parse_type(match.group(1))
            return Array(elemType)

        raise Exception(f"Can not parse type {type_str}")

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
        local_vars = []

        return_count = 0
        params_parsed = False

        for x in ast['children']:
            if x['name'] == 'ParameterList':
                if not params_parsed:
                    if x['children']:
                        for y in x['children']:
                            if y['name'] == 'VariableDeclaration':
                                var_name = y['attributes']['name']
                                if var_name:
                                    params.append(self.parse_function_variable(y))
                    params_parsed = True
                else:
                    if x['children']:
                        return_count = len(x['children'])
            if x['name'] == 'Block':
                def process_function_node(node):
                    if node['name'] == 'VariableDeclaration':
                        local_vars.append(self.parse_function_variable(node))
                self.traverse_all(x, lambda x: process_function_node(x))
        for i, p in enumerate(params):
            params[i].location = i
        for i, p in enumerate(local_vars):
           local_vars[i].location = i
        return Function(name, src, params, local_vars, return_count)

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

    def prepare_ops_mapping(self, code):
        pc_to_op_idx = {}
        code = bytes.fromhex(code)
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

    def prepare_sourcemap(self, srcmap_str):
        srcmap = {}

        map_items = srcmap_str.split(";")

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

    def prepare_line_offsets(self):
        source_offsets = {}
        for i, lines in enumerate(self.sources):
            offset_by_line = {}
            pos = 0
            for j in range(len(lines)):
                offset_by_line[j] = pos
                pos += len(lines[j]) + 1
            source_offsets[i] = offset_by_line
        return source_offsets

