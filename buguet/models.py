class Contract:
    def __init__(self, name, src, functions, variables):
        self.name = name
        self.src = src
        self.functions = functions
        self.variables = variables
        self._variables_by_name = {}

    @property
    def variables_by_name(self):
        if not self._variables_by_name:
            for var in self.variables:
                self._variables_by_name[var.name] = var
        return self._variables_by_name

class Function:
    def __init__(self, name, src, params, local_vars):
        self.name = name
        self.src = src
        self.params = params
        self.local_vars = local_vars
        self._params_by_name = {}
        self._local_vars_by_name = {}

    @property
    def params_by_name(self):
        if not self._params_by_name:
            for var in self.params:
                self._params_by_name[var.name] = var
        return self._params_by_name

    @property
    def local_vars_by_name(self):
        if not self._local_vars_by_name:
            for var in self.local_vars:
                self._local_vars_by_name[var.name] = var
        return self._local_vars_by_name


class Variable:
    def __init__(self, var_type, name=None, location=None, offset=None, location_type=None):
        self.name = name
        self.var_type = var_type
        self.location = location
        self.offset = offset
        self.location_type = location_type

class Int:
    def __init__(self, size):
        self.size = size

class Uint:
    def __init__(self, size):
        self.size = size

class FixedBytes:
    def __init__(self, size):
        self.size = size

class Bool:
    @property
    def size(self):
        return 8

class Address:
    @property
    def size(self):
        return 160

class Bytes:
    @property
    def size(self):
        return 256

class String:
    @property
    def size(self):
        return 256

class FixedArray:
    def __init__(self, element_type, length, size = None):
        self.element_type = element_type
        self.length = length
        self.size = size

class Struct:
    def __init__(self, name, variables, size = None):
        self.name = name
        self.variables = variables
        self.size = size

class Array:
    def __init__(self, element_type):
        self.element_type = element_type

    @property
    def size(self):
        return 256

class Map:
    def __init__(self, key_type, value_type):
        self.key_type = key_type
        self.value_type = value_type

    @property
    def size(self):
        return 256
