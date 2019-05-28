import re

class ParsingFailed(Exception):
    pass

class Literal:
    def __init__(self, value):
        self.value = value

class Name:
    def __init__(self, value):
        self.value = value

class Var:
    def __init__(name, var1):
        self.name = name
        self.var1 = var1

class ApplyBrackets:
    def __init__(self, left, right):
        self.left = left
        self.right = right

class ApplyDot:
    def __init__(self, left, right):
        self.left = left
        self.right = right

class Parser:
    def __init__(self, s):
        self.s = s.replace(" ", "")
        self.pos = 0

    def parse(self):
        res = self.parse_expression()
        if len(self.s) != self.pos:
            raise ParsingFailed()
        return res

    def parse_expression(self):
        literal = self.parse_literal()
        if literal:
            return literal
        else:
            return self.parse_var()

    def parse_literal(self):
        m = re.match('"(.*?)"', self.s[self.pos:])
        if m:
            self.pos += len(m.group(0))
            return Literal(m.group(1))

        m = re.match("\d+", self.s[self.pos:])
        if m:
            self.pos += len(m.group(0))
            return Literal(int(m.group(0)))

        m = re.match("true|false", self.s[self.pos:])
        if m:
            self.pos += len(m.group(0))
            if m.group(0) == "true":
                return Literal(True)
            else:
                return Literal(False)

    def parse_name(self):
        m = re.match("\D\w*", self.s[self.pos:])
        if m:
            self.pos += len(m.group(0))
            return Name(m.group(0))
        raise ParsingFailed()

    def parse_var(self):
        left = self.parse_name()
        while True:
            if len(self.s) == self.pos:
                break
            if self.s[self.pos] == "[":
                self.pos += 1
                e = self.parse_expression()
                if self.s[self.pos] != "]":
                    raise ParsingFailed()
                self.pos += 1
                left = ApplyBrackets(left, e)
            elif self.s[self.pos] == ".":
                self.pos += 1
                name = self.parse_name()
                left = ApplyDot(left, name)
            else:
                break
        return left
