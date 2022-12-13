from utils.tac.temp import Temp

from typing import Optional,List

from .symbol import *

"""
Variable symbol, representing a variable definition.
"""


class ArraySymbol(Symbol):
    def __init__(self, name: str, type: DecafType, index: List[int], isGlobal: bool = False) -> None:
        super().__init__(name, type)
        self.temp: Temp = None
        self.isGlobal = isGlobal
        self.index = index
        self.initValue : Optional[List[int]] = None

    def __str__(self) -> str:
        return "variable %s : %s" % (self.name, str(self.type))

    # To set the initial value of a variable symbol (used for global variable).
    def setInitValue(self,value: int) -> None:
        if self.initValue == None:
            self.initValue = [value]
        else:
            self.initValue.append(value)

    def calc_len(self) -> int:
        tot = 0
        for size in self.index:
            if tot == 0:
                tot = size
            else:
                tot = tot * (size)
        return tot