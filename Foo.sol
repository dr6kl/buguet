pragma solidity ^0.4.13;

contract Foo {
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
  string str2;
  uint8[2][13][15][100] arr_aa;
  uint96[10] arr;
  bytes24 qqq1;
  int8 qqq2;
  bytes bts;
  bytes bts2;
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
    //for (i = 0; i < 100; i++) {
      //arr[i] = uint8(i);
    //}
  }

  function doSomething() public {
    myfunc();
  }

  function myfunc() internal returns (uint256) {
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

    uint c = aaa["foo"][3];
    uint d = bbb[7]["bar"];

    cnt += b;
    cnt += a;
    cnt += c;
    cnt += d;

    uint x = foo(1, 2, 3) + foo1(1, 2, 3);
    if (x > 0) {
      cnt += 1;
    } else {
      cnt -= 1;
    }

    return 0;
  }

  function foo(uint a, uint b, uint c) internal returns (uint) {
    uint d;
    d = bar(a+b, a-b, c);
    return d - 10;
  }

  function bar(uint a, uint b, uint c) internal returns (uint) {
    a = a * 2;
    uint d;
    d = a - b + c;
    return d;
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
}

