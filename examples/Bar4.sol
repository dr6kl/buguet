pragma solidity ^0.4.10;

contract owned {
    function owned() public { owner = msg.sender; }
    address owner;
}

contract mortal is owned {
    function kill() public {
        if (msg.sender == owner) selfdestruct(owner);
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

  function ggg(uint a, uint b) {
    kkk = a + b;
  }
}

contract CounterBase {
  function some_pure_function() external returns(int) {
    return 2;
  }

  function failing_function() {
    require(false);
  }
}
