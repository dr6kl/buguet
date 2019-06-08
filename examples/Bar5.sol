pragma solidity ^0.5.0;

contract owned {
    constructor() public { owner = msg.sender; }
    address owner;
}

contract mortal is owned {
    function kill() public {

    }
}

contract Base1 is mortal {
   uint8 a;
   function kill() public { super.kill(); }
}

contract Base2 is mortal {
  function kill() public { super.kill(); }
}

contract Final is Base1, Base2 {
  uint8 b;
}

contract Bar is Final {
  uint kkk;

  function ggg(uint a, uint b) public {
    kkk = a + b;
  }
}

contract CounterBase {
  function some_pure_function() pure external returns(int) {
    return 2;
  }

  function failing_function() public {
    revert("Foo");
  }
}
