import unittest
from buguet.debugger import Debugger
from web3 import Web3, HTTPProvider
from web3.middleware import geth_poa_middleware
import json
from buguet.models import Breakpoint
from buguet.repl import Repl

class TestDebugger(unittest.TestCase):
    def prepare_debugger(self):
        web3 = Web3(HTTPProvider("http://localhost:8545"))
        web3.middleware_stack.inject(geth_poa_middleware, layer=0)
        f = open("examples/out.json")
        data = [json.load(f)]
        f.close()
        f = open("examples/transaction_id.txt")
        transaction_id = f.read()
        f.close()
        return Debugger(web3, data, transaction_id, ["examples"])

    def test1(self):
        debugger = self.prepare_debugger()
        debugger.add_breakpoint(Breakpoint("Foo", 235))
        debugger.continu()
        self.assertEqual(debugger.eval("a"), 1)
        self.assertEqual(debugger.eval("b"), 2)
        self.assertEqual(debugger.eval("c"), 3)
        self.assertEqual(debugger.eval("d"), 6)
        self.assertEqual(debugger.eval("e"), 255)
        self.assertEqual(debugger.eval("f"), 3)

    def test2(self):
        debugger = self.prepare_debugger()
        debugger.add_breakpoint(Breakpoint("Foo", 153))
        debugger.continu()
        self.assertEqual(debugger.eval("strct1.a"), 3);
        self.assertEqual(debugger.eval("strct1.b"), 24);
        self.assertEqual(debugger.eval("strct1.c"), "hello world");
        self.assertEqual(debugger.eval("strct1.d"), "baaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaab");
        self.assertEqual(debugger.eval("strct1.e.a"), 12);
        self.assertEqual(debugger.eval("strct1.e.b"), 34);
        self.assertRegex(debugger.eval("counter"), "[a-f0-9]{20}")
        self.assertEqual(debugger.eval("aaa1"), 100)
        self.assertEqual(debugger.eval("aaa2"), 101)
        self.assertEqual(debugger.eval("flag"), True)
        self.assertEqual(debugger.eval("flag2"), False)
        self.assertEqual(debugger.eval("aaa3"), 103)
        self.assertEqual(debugger.eval("cnt"), 0)
        self.assertEqual(debugger.eval("myAddr"), 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa')
        self.assertEqual(debugger.eval("vv"), '31')
        self.assertEqual(debugger.eval("zz"), 0)
        self.assertEqual(debugger.eval("qqq"), 1422)
        self.assertEqual(debugger.eval("str"), "hello world hello world")
        self.assertEqual(debugger.eval("strct.a"), 4);
        self.assertEqual(debugger.eval("strct.b"), 25);
        self.assertEqual(debugger.eval("strct.c"), "hello world 1");
        self.assertEqual(debugger.eval("strct.d"), "baaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaab");
        self.assertEqual(debugger.eval("strct.e.a"), 13);
        self.assertEqual(debugger.eval("strct.e.b"), 35);
        self.assertEqual(debugger.eval("str2"), "hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world xxx")
        self.assertEqual(debugger.eval("arr_aa[4][3][2][1]"), 15);
        self.assertEqual(debugger.eval("arr_aa[1][3][2][1]"), 0);
        self.assertEqual(debugger.eval("arr[1]"), 12);
        self.assertEqual(debugger.eval("arr[2]"), 100);
        self.assertEqual(debugger.eval("qqq1"), "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb");
        self.assertEqual(debugger.eval("qqq2"), 26);
        self.assertEqual(debugger.eval("bts"), "000102030405060708090a0b0c");
        self.assertRegex(debugger.eval("bts2"), "00{900}ff(00){99}");
        self.assertEqual(debugger.eval("ccc.x1[12]"), 15)
        self.assertEqual(debugger.eval("ccc.x2[12]"), 15)
        self.assertEqual(debugger.eval("ccc.x3[qqq1]"), 15)
        self.assertEqual(debugger.eval("ccc.x4[myAddr]"), 15)
        self.assertEqual(debugger.eval("ccc.x5[bts]"), 15)
        self.assertEqual(debugger.eval("ccc.x6[true]"), 15)
        self.assertEqual(debugger.eval("ccc.x6[false]"), 11)
        self.assertEqual(debugger.eval("zz1[\"foo\"].e.a"), 15)
        self.assertEqual(debugger.eval("zz2[\"foo\"][0].e.b"), 35)
        self.assertEqual(debugger.eval("zz2[\"foo\"][1].e.b"), 34)
        self.assertEqual(debugger.eval("myMap2[\"foo\"][\"bar\"]"), 13)
        self.assertEqual(debugger.eval("myMap2[\"bar\"][\"foo\"]"),  17)
        self.assertEqual(debugger.eval("myArray[1000]"), 37)
        self.assertEqual(debugger.eval("aaa[\"foo\"][3]"), 151)
        self.assertEqual(debugger.eval("bbb[7][\"bar\"]"), 49)

    def test3(self):
        debugger = self.prepare_debugger()
        debugger.add_breakpoint(Breakpoint("Foo", 225))
        debugger.continu()
        self.assertEqual(debugger.eval("d"), 3)

    def test4(self):
        debugger = self.prepare_debugger()
        debugger.add_breakpoint(Breakpoint("Foo", 210))
        debugger.continu()
        self.assertEqual(debugger.eval("ee[3]"), 502);
        self.assertEqual(debugger.eval("ee[5]"), 14);
        self.assertEqual(debugger.eval("gg[3].e.b"), 35);
        self.assertEqual(debugger.eval("hh[8].e.b"), 35);
        self.assertEqual(debugger.eval("hh[8].c"), "hello world 1");
        self.assertEqual(debugger.eval("sss.b"), 25);
        self.assertRegex(debugger.eval("mbytes"), "a{200}");

    def test5(self):
        debugger = self.prepare_debugger()
        debugger.add_breakpoint(Breakpoint("Foo", 188))
        debugger.continu()
        self.assertEqual(debugger.eval("st"), "hello hello hello");
        self.assertEqual(debugger.eval("b.e.b"), 34);

    def test6(self):
        debugger = self.prepare_debugger()
        debugger.add_breakpoint(Breakpoint("Foo", 235))
        debugger.continu()
        self.assertEqual(debugger.eval("ccc.x1[myMap2[\"foo\"][\"bar\"] + myMap2[\"bar\"][\"foo\"] - arr_aa[4][c][b][a] - 3]"), 15);

    def test6(self):
        debugger = self.prepare_debugger()
        debugger.add_breakpoint(Breakpoint("Foo", 145))
        debugger.continu()
        self.assertEqual(debugger.eval("a"), 1);
        self.assertEqual(debugger.eval("b"), 2);
        self.assertEqual(debugger.eval("d"), 3);

    def test7(self):
        debugger = self.prepare_debugger()
        debugger.add_breakpoint(Breakpoint("Foo", 15))
        debugger.continu()
        self.assertEqual(debugger.eval("x"), 3);
        self.assertEqual(debugger.eval("cnt"), 12);
        debugger.breakpoints = []
        debugger.add_breakpoint(Breakpoint("Foo", 179))
        debugger.continu()
        self.assertEqual(debugger.eval("b"), 37);

    def prepare_debugger_init(self):
        web3 = Web3(HTTPProvider("http://localhost:8545"))
        web3.middleware_stack.inject(geth_poa_middleware, layer=0)
        f = open("examples/out.json")
        data = [json.load(f)]
        f.close()
        f = open("examples/transaction_init.txt")
        transaction_id = f.read()
        f.close()
        return Debugger(web3, data, transaction_id, ["examples"])

    def test8(self):
        debugger = self.prepare_debugger_init()
        debugger.add_breakpoint(Breakpoint("Foo", 112))
        debugger.continu()
        self.assertEqual(debugger.eval("i"), 13)
        debugger.breakpoints = []
        debugger.add_breakpoint(Breakpoint("Foo", 20))
        debugger.continu()
        debugger.stepout()
        self.assertEqual(debugger.eval("b"), 13)
        self.assertEqual(debugger.eval("cnt"), 12)
        debugger.breakpoints = []
        debugger.add_breakpoint(Breakpoint("Foo", 130))
        debugger.continu()
        self.assertEqual(debugger.eval("b"), 20)

    def test9(self):
        debugger = self.prepare_debugger()
        debugger.add_breakpoint(Breakpoint("Foo", 153))
        debugger.continu()
        self.assertEqual(debugger.eval("strct"), {'a': 4, 'b': 25, 'c': 'hello world 1', 'd': 'baaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaab', 'e': {'a': 13, 'b': 35}})
        self.assertEqual(debugger.eval("arr_aa[4][3]"), [[0, 0], [0, 0], [0, 15], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0], [0, 0]])
        self.assertEqual(debugger.eval("aaa"), "Map")
        self.assertEqual(debugger.eval("zz2[\"foo\"]"), [{'a': 4, 'b': 25, 'c': 'hello world 1', 'd': 'baaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaab', 'e': {'a': 13, 'b': 35}}, {'a': 3, 'b': 24, 'c': 'hello world', 'd': 'baaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaab', 'e': {'a': 12, 'b': 34}}])

    def test10(self):
        debugger = self.prepare_debugger()
        debugger.add_breakpoint(Breakpoint("Foo", 249))
        debugger.continu()
        self.assertEqual(debugger.eval("b"), 2)
        self.assertEqual(debugger.eval("i"), 3)
        self.assertEqual(debugger.eval("j"), 4)
        self.assertEqual(debugger.eval("k"), 5)
        self.assertEqual(debugger.eval("d"), 27)
        self.assertEqual(debugger.eval("e"), 27)
        debugger.breakpoints = []
        debugger.add_breakpoint(Breakpoint("Foo", 262))
        debugger.continu()
        self.assertEqual(debugger.eval("b"), 2)
        self.assertEqual(debugger.eval("i"), 3)
        self.assertEqual(debugger.eval("j"), 4)
        self.assertEqual(debugger.eval("k"), 10)
        self.assertEqual(debugger.eval("g"), 21)
        self.assertEqual(debugger.eval("h"), 21)
        debugger.breakpoints = []
        debugger.add_breakpoint(Breakpoint("Foo", 253))
        debugger.continu()
        self.assertEqual(debugger.eval("i"), 3)
        self.assertEqual(debugger.eval("j"), 5)
        self.assertEqual(debugger.eval("f"), 33)
        self.assertEqual(debugger.eval("d"), 33)
        debugger.breakpoints = []
        debugger.add_breakpoint(Breakpoint("Foo", 269))
        debugger.continu()
        self.assertEqual(debugger.eval("p"), 11)

    def test11(self):
        debugger = self.prepare_debugger()
        debugger.add_breakpoint(Breakpoint("Foo", 179))
        debugger.continu()
        self.assertEqual(debugger.eval("b"), 37);
