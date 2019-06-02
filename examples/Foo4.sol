pragma solidity ^0.4.10;

import "Bar4.sol";

contract Counter {
  uint cnt = 12;

  function Counter() {
    uint b = 13;
    uint d = aaa(b, 1);
  }

  function increment() external {
    uint x = aaa(1, 2);
    cnt = cnt + x;
  }

  function aaa(uint a, uint b) internal returns(uint) {
    uint d = a + b;
    return d;
  }
}

contract Foo is Bar {
  MyStruct strct1;
  Counter counter;

  struct MyStruct {
    uint8 a;
    uint32 b;
    string c;
    address d;
    MyStruct2 e;
  }

  struct MyStruct2 {
    uint a;
    uint b;
  }

  struct MapTest {
    mapping(uint8 => uint) x1;
    mapping(int => uint) x2;
    mapping(bytes24 => uint) x3;
    mapping(address => uint) x4;
    mapping(bytes => uint) x5;
    mapping(bool => uint) x6;
  }

  uint8 aaa1;
  uint8 aaa2;
  bool flag;
  bool flag2;
  uint8 aaa3;
  uint256 cnt;
  address myAddr;
  byte vv;
  uint zz;
  int16 qqq;
  string str;
  MyStruct strct;
  string str2;
  uint8[2][13][15][100] arr_aa;
  uint96[10] arr;
  bytes24 qqq1;
  int8 qqq2;
  bytes bts;
  bytes bts2;
  MapTest ccc;
  mapping (string => MyStruct) zz1;
  mapping (string => MyStruct[]) zz2;
  mapping (string => uint256) myMap;
  mapping (string => mapping(string => uint256)) myMap2;
  uint8[] myArray;
  mapping(string => uint256[]) aaa;
  mapping(string => uint256)[] bbb;


  function Foo() public {
    myMap2["foo"]["bar"] = 13;
    myMap2["bar"]["foo"] = 17;
    myArray.length = 1001;
    myArray[1000] = 37;
    aaa["foo"].length = 10;
    aaa["foo"][3] = 151;
    bbb.length = 10;
    bbb[7]["bar"] = 49;
    flag = true;
    flag2 = false;
    vv = 49;
    aaa1 = 100;
    aaa2 = 101;
    aaa3 = 103;
    str = "hello world hello world";
    str2 = "hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world hello world xxx";
    bts.length = 13;
    bts2.length = 1000;
    uint i;
    for (i = 0; i < 13; i++) {
      bts[i] = byte(i);
    }
    bts2[900] = 0xFF;
    myAddr = 0xaAaAaAaaAaAaAaaAaAAAAAAAAaaaAaAaAaaAaaAa;
    qqq = 1422;
    qqq1 = 0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb;
    qqq2 = 26;
    arr[1] = 12;
    arr[2] = 100;
    arr_aa[4][3][2][1] = 15;
    strct1.a = 3;
    strct1.b = 24;
    strct1.c = "hello world";
    strct1.d = 0xbAAaaaaaAAaAAaaAaAaAaaaaaaaaaaaaaaaAAAAb;
    strct1.e.a = 12;
    strct1.e.b = 34;

    strct.a = 4;
    strct.b = 25;
    strct.c = "hello world 1";
    strct.d = 0xbAAaaaaaAAaAAaaAaAaAaaaaaaaaaaaaaaaAAAAb;
    strct.e.a = 13;
    strct.e.b = 35;

    zz1["foo"].e.a = 15;
    zz2["foo"].push(strct);
    zz2["foo"].push(strct1);

    uint b = createCounter(18);

    ccc.x1[12] = 15;
    ccc.x2[12] = 15;
    ccc.x3[qqq1] = 15;
    ccc.x4[myAddr] = 15;
    ccc.x5[bts] = 15;
    ccc.x6[true] = 15;
    ccc.x6[false] = 11;
  }

  function createCounter(uint a) returns (uint) {
    counter = new Counter();
    return a + 2;
  }

  function doSomething(uint a, uint8 b, uint8 d) public {
    a = b + d;
    myfunc();
  }

  function myfunc() internal {
    cnt += arr[3];

    uint a = myMap2["foo"]["bar"];
    if (aaa2 > 0) {
      a += 1;
    }
    if (aaa1 > 0) {
      a += 1;
    }
    if (aaa3 > 0) {
      a += 1;
    }
    uint b = myArray[1000];
    test_blocks();
    ggg(5, 6);
    buzz(1, 2);

    uint c = aaa["foo"][3];
    uint d = bbb[7]["bar"];

    cnt += b;
    cnt += a;
    cnt += c;
    cnt += d;

    uint x = foo(1, 2, 3) + foo1(1, 2, 3);
    x += foo2(2, strct1, 3);
    counter.increment();

    if (x > 0) {
      cnt += 1;
    } else {
      cnt -= 1;
    }
  }

  function foo2(uint a, MyStruct storage b, uint c1) internal returns (uint) {
    string memory st = "hello hello hello";
    return 0;
  }

  function foo(uint a, uint b, uint c1) internal returns (uint) {
    uint d;
    uint[] memory ee = new uint[](7);
    bytes memory mbytes = new bytes(100);
    for (uint i = 0; i < 100; i++) {
      mbytes[i] = 0xaa;
    }
    ee[3] = 502;
    MyStruct[] memory gg = new MyStruct[](7);
    MyStruct[10] memory hh;
    MyStruct sss;

    sss = strct;

    gg[3] = sss;
    hh[8] = sss;
    uint8 l = 6;
    ee[5] = 14;
    uint256 vvv = 8;
    d = bar(a+b, a-b, c1);
    return d - 10;
  }

  function bar(uint a, uint b, uint c) internal returns (uint) {
    MyStruct[10] memory hh;
    a = a * 2;
    uint d;
    d = a - b + c;
    var jrku = hh;
    return d;
  }

  function buzz(uint a, uint b) internal returns (uint, uint, uint, uint) {
    uint d = a + b;
    return (0, 1, 2, d);
  }

  function foo1(uint8 a, uint8 b, uint8 c) internal returns (uint) {
    uint8 d;
    uint128 e;
    uint16 f;
    d = a + b + c;
    e = a - b;
    f = c * a;
    return d + e + f;
  }

  function test_blocks() internal {
    uint a = 1;
    uint b = 2;
    for (uint i = 0; i < 10; i++) {
      for (uint j = 0; j < 10; j++) {
        uint k = 0;
        while (k < 10) {
          uint d = 0;
          if (i >= 3 && j >= 4 && k >= 5) {
            uint e = 27;
            d = e;
            a++;
          } else {
            uint f = 33;
            d = f;
            a++;
          }
          k++;
        }
        do {
          uint g = 0;
          if (i < 5) {
            uint h = 21;
            g = h;
            a++;
          }
          k++;
        } while (k < 20);
      }
    }
    uint p = 11;
    a++;
  }
}

