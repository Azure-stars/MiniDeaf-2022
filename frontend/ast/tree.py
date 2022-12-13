"""
Module that defines all AST nodes.
Reading this file to grasp the basic method of defining a new AST node is recommended.
Modify this file if you want to add a new AST node.
"""

from __future__ import annotations

from typing import Any, Generic, Optional, TypeVar, Union,List

from frontend.type import INT, DecafType, ArrayType
from utils import T, U

from .node import NULL, BinaryOp, Node, UnaryOp
from .visitor import Visitor, accept

_T = TypeVar("_T", bound=Node)
U = TypeVar("U", covariant=True)


def _index_len_err(i: int, node: Node):
    return IndexError(
        f"you are trying to index the #{i} child of node {node.name}, which has only {len(node)} children"
    )


class ListNode(Node, Generic[_T]):
    """
    Abstract node type that represents a node sequence.
    E.g. `Block` (sequence of statements).
    """

    def __init__(self, name: str, children: list[_T]) -> None:
        super().__init__(name)
        self.children = children

    def __getitem__(self, key: int) -> Node:
        return self.children.__getitem__(key)

    def __len__(self) -> int:
        return len(self.children)

    def accept(self, v: Visitor[T, U], ctx: T):
        ret = tuple(map(accept(v, ctx), self))
        return None if ret.count(None) == len(ret) else ret


class Program(ListNode[Union["Function",'GlobalDeclaration']]):
    """
    AST root. It should have only one children before step9.
    因为没有函数，只有一个主函数入口
    """

    def __init__(self, *children: Union[Function, GlobalDeclaration]) -> None:
        super().__init__("program", list(children))

    def functions(self) -> dict[str, Function]:
        """
        得到所有函数名称
        """
        return {func.ident.value: func for func in self if isinstance(func, Function)}

    def hasMainFunc(self) -> bool:
        """
        是否有主函数
        """
        return "main" in self.functions()

    def mainFunc(self) -> Function:
        """
        得到主函数
        """
        return self.functions()["main"]

    def accept(self, v: Visitor[T, U], ctx: T):
        return v.visitProgram(self, ctx)


class Function(Node):
    """
    AST node that represents a function.
    """

    def __init__(
        self,
        ret_t: TypeLiteral,
        ident: Identifier,
        parameterlist: ParameterList,
        body: Optional[Block] = None,
    ) -> None:
        super().__init__("function")
        self.ret_t = ret_t
        self.ident = ident
        self.parameterlist = parameterlist
        self.body = body or NULL
        # 函数体由   返回值类型 + 函数名称 + 函数体组成
        # 这里似乎没有参数

    def __getitem__(self, key: int) -> Node:
        return (
            self.ret_t,
            self.ident,
            self.parameterlist,
            self.body,
        )[key]

    def __len__(self) -> int:
        return 4

    def accept(self, v: Visitor[T, U], ctx: T):
        return v.visitFunction(self, ctx)

class Parameter(Node):
    """
    AST node that represents a parameter for a function.
    """
    def __init__(
        self,
        var_t: TypeLiteral,
        ident: Identifier,
        index: Optional[IndexList] = None
    ) -> None:
        super().__init__('parameter')
        self.var_t = var_t
        self.ident = ident
        self.index = index or NULL
    
    def __getitem__(self, key: int) -> Node:
        return (self.var_t, self.ident, self.index)[key]

    def __len__(self) -> int:
        return 3
    
    def accept(self, v: Visitor[T, U], ctx: T):
        return v.visitParameter(self, ctx)

class Expression(Node):
    """
    Abstract type that represents an evaluable expression.
    可计算的表达式
    """

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.type: Optional[DecafType] = None


class Statement(Node):
    """
    Abstract type that represents a statement.
    Statement：特定语句或者语句块，如block或者返回语句
    """

    def is_block(self) -> bool:
        """
        Determine if this type of statement is `Block`.
        """
        return False


class ParameterList(Statement,ListNode[Parameter]):
    """
    AST node that represents parameters list for a function.
    """

    def __init__(
        self,
         *children:Parameter
    ) -> None:
        super().__init__('parameterlist',list(children))

    def accept(self, v: Visitor[T, U], ctx: T):
        return v.visitParameterList(self, ctx)     

    def is_block(self) -> bool:
        return False  

class ExpressionList(Statement,ListNode[Expression]):
    """
    AST node that represents expression list for a function
    """

    def __init__(
        self,
        *children: Expression
    ) -> None:
        super().__init__('expressionlist',list(children))

    def accept(self, v: Visitor[T, U], ctx: T):
        return v.visitExpressionList(self, ctx)

    def is_block(self) -> bool:
        return False

class Call(Expression):
    """
    AST node that represents call a function
    """
    def __init__(
        self,
        ident: Identifier,
        argument_list: ExpressionList,
    ) -> None:
        super().__init__("call")
        self.ident = ident
        self.argument_list = argument_list 
    def __getitem__(self, key: int) -> Node:
        return (
            self.ident,
            self.argument_list,
        )[key]

    def __len__(self) -> int:
        return 2

    def accept(self, v: Visitor[T, U], ctx: T):
        return v.visitCall(self, ctx)

class Return(Statement):
    """
    AST node of return statement.
    """

    def __init__(self, expr: Expression) -> None:
        super().__init__("return")
        self.expr = expr

    def __getitem__(self, key: Union[int, str]) -> Node:
        if isinstance(key, int):
            return (self.expr,)[key]
            # 返回值为常数
        return self.__dict__[key]

    def __len__(self) -> int:
        return 1

    def accept(self, v: Visitor[T, U], ctx: T):
        return v.visitReturn(self, ctx)


class If(Statement):
    """
    AST node of if statement.
    """

    def __init__(
        self, cond: Expression, then: Statement, otherwise: Optional[Statement] = None
    ) -> None:
        super().__init__("if")
        self.cond = cond
        # 判断条件
        self.then = then
        # if语句块的内容
        self.otherwise = otherwise or NULL

    def __getitem__(self, key: int) -> Node:
        return (self.cond, self.then, self.otherwise)[key]

    def __len__(self) -> int:
        return 3

    def accept(self, v: Visitor[T, U], ctx: T):
        return v.visitIf(self, ctx)


class While(Statement):
    """
    AST node of while statement.
    """

    def __init__(self, cond: Expression, body: Statement) -> None:
        super().__init__("while")
        self.cond = cond
        self.body = body

    def __getitem__(self, key: int) -> Node:
        return (self.cond, self.body)[key]

    def __len__(self) -> int:
        return 2

    def accept(self, v: Visitor[T, U], ctx: T):
        return v.visitWhile(self, ctx)

class For(Statement):
    """
    AST node of for statement
    """
    def __init__(self, 
        body:Statement,
        init:Optional[Statement] = None,
        cond:Optional[Expression] = None, 
        update:Optional[Statement] = None,
        ) -> None:
        super().__init__("for")
        self.init = init or NULL
        self.cond = cond or NULL
        self.update = update or NULL
        self.body = body

    def __getitem__(self, key: int) -> Node:
        return (self.init, self.cond, self.update, self.body)[key]

    def __len__(self) -> int:
        return 4

    def accept(self, v: Visitor[T, U], ctx: T):
        return v.visitFor(self, ctx)

class DoWhile(Statement):
    """
    AST node of do while statement
    """
    def __init__(self, cond: Expression, body: Statement) -> None:
        super().__init__("do while")
        self.cond = cond
        self.body = body

    def __getitem__(self, key: int) -> Node:
        return (self.cond, self.body)[key]

    def __len__(self) -> int:
        return 2

    def accept(self, v: Visitor[T, U], ctx: T):
        return v.visitDoWhile(self, ctx)


class Break(Statement):
    """
    AST node of break statement.
    """

    def __init__(self) -> None:
        super().__init__("break")

    def __getitem__(self, key: int) -> Node:
        raise _index_len_err(key, self)

    def __len__(self) -> int:
        return 0

    def accept(self, v: Visitor[T, U], ctx: T):
        return v.visitBreak(self, ctx)

    def is_leaf(self):
        return True

class Continue(Statement):
    """
    AST node of continue statement.
    """

    def __init__(self) -> None:
        super().__init__("continue")

    def __getitem__(self, key: int) -> Node:
        raise _index_len_err(key, self)

    def __len__(self) -> int:
        return 0

    def accept(self, v: Visitor[T, U], ctx: T):
        return v.visitContinue(self, ctx)

    def is_leaf(self):
        return True


class Block(Statement, ListNode[Union["Statement", "Declaration"]]):
    """
    AST node of block "statement".
    """

    def __init__(self, *children: Union[Statement, Declaration]) -> None:
        super().__init__("block", list(children))

    def accept(self, v: Visitor[T, U], ctx: T):
        return v.visitBlock(self, ctx)

    def is_block(self) -> bool:
        return True

class Identifier(Expression):
    """
    AST node of identifier "expression".
    变量
    """

    def __init__(self, value: str) -> None:
        super().__init__("identifier")
        self.value = value

    def __getitem__(self, key: int) -> Node:
        raise _index_len_err(key, self)

    def __len__(self) -> int:
        return 0

    def accept(self, v: Visitor[T, U], ctx: T):
        return v.visitIdentifier(self, ctx)

    def __str__(self) -> str:
        return f"identifier({self.value})"

    def is_leaf(self):
        return True


class IntLiteral(Expression):
    """
    AST node of int literal like `0`.
    字面值，即常量
    """

    def __init__(self, value: Union[int, str]) -> None:
        super().__init__("int_literal")
        self.value = int(value)

    def __getitem__(self, key: int) -> Node:
        raise _index_len_err(key, self)

    def __len__(self) -> int:
        return 0

    def accept(self, v: Visitor[T, U], ctx: T):
        return v.visitIntLiteral(self, ctx)

    def __str__(self) -> str:
        return f"int({self.value})"

    def is_leaf(self):
        return True


class TypeLiteral(Node):
    """
    Abstract node type that represents a type literal like `int`.
    代表一个类型符，当前仅会有int
    """

    def __init__(self, name: str, _type: DecafType) -> None:
        super().__init__(name)
        self.type = _type

    def __str__(self) -> str:
        return f"type({self.type})"

    def is_leaf(self):
        return True

class TIntArray(TypeLiteral):
    def __init__(self, slicing:Optional[List[int]] = None) -> None:
        if slicing == None:
            slicing = []
        self.slicing = slicing
        array_type = ArrayType(INT, slicing)
        super().__init__("type_int_array", array_type)
        # self.type = array_type

    def __getitem__(self, key: int) -> Node:
        raise _index_len_err(key, self)
    
    def __len__(self) -> int:
        return 0
    
    def accept(self, v: Visitor[T, U], ctx: T) -> Optional[U]:
        return v.visitArray(self, ctx)

class TInt(TypeLiteral):
    "AST node of type `int`."

    def __init__(self) -> None:
        super().__init__("type_int", INT)

    def __getitem__(self, key: int) -> Node:
        raise _index_len_err(key, self)

    def __len__(self) -> int:
        return 0

    def accept(self, v: Visitor[T, U], ctx: T):
        return v.visitTInt(self, ctx)

class IndexList(ListNode[Union[IntLiteral, Expression]]):
    def __init__(self, *children: Union[IntLiteral, Expression]) -> None:
        super().__init__('indexlist', list(children))

    def accept(self, v: Visitor[T, U], ctx: T):
        return v.visitIndexList(self, ctx)     

    def is_block(self) -> bool:
        return False  

class InitList(ListNode[IntLiteral]):
    def __init__(self, *children: IntLiteral) -> None:
        super().__init__('initlist', list(children))

    def accept(self, v: Visitor[T, U], ctx: T):
        return v.visitInitList(self, ctx)

    def is_block(self) -> bool:
        return False

class Declaration(Node):
    """
    AST node of declaration.
    声明一个变量
    """
    def __init__(
        self,
        var_t: TypeLiteral,
        ident: Identifier,
        index: Optional[IndexList] = None,
        init_expr: Optional[Union[Expression, InitList]] = None,
    ) -> None:
        super().__init__("declaration")
        self.var_t = var_t
        self.ident = ident
        self.init_expr = init_expr or NULL
        self.index = index or IndexList()
    def __getitem__(self, key: int) -> Node:
        return (self.var_t, self.ident, self.index, self.init_expr)[key]

    def __len__(self) -> int:
        return 4

    def accept(self, v: Visitor[T, U], ctx: T):
        return v.visitDeclaration(self, ctx)


class GlobalDeclaration(Node):
    """
    AST node that represents for the global variable
    """
    # 肯定写在declaration旁边啊（喜
    def __init__(
        self,
        var_t: TypeLiteral,
        ident: Identifier,
        index: Optional[IndexList] = None,
        init_expr: Optional[Union[IntLiteral, InitList]] = None,
    ) -> None:
        super().__init__("globaldeclaration")
        self.var_t = var_t
        self.ident = ident
        self.index = index or IndexList()
        self.init_expr = init_expr or NULL
        # 龟龟为常量

    def __getitem__(self, key: int) -> Node:
        return (self.var_t, self.ident, self.index, self.init_expr)[key]

    def __len__(self) -> int:
        return 4

    def accept(self, v: Visitor[T, U], ctx: T):
        return v.visitGlobalDeclaration(self, ctx)

class IndexExpr(Expression):
    """
    AST node for array index
    """
    def __init__(self, base:Identifier, index: IndexList ) -> None:
        super().__init__('indexExpr')
        self.base = base
        self.index = index

    def __getitem__(self, key: int) -> Node:
        return (self.base, self.index)[key]

    def __len__(self) -> int:
        return 2
    
    def accept(self, v: Visitor[T, U], ctx: T):
        return v.visitIndexExpr(self, ctx)


class Unary(Expression):
    """
    AST node of unary expression.
    Note that the operation type (like negative) is not among its children.
    一元表达式
    不包含负数
    """

    def __init__(self, op: UnaryOp, operand: Expression) -> None:
        super().__init__(f"unary({op.value})")
        self.op = op
        self.operand = operand

    def __getitem__(self, key: int) -> Node:
        return (self.operand,)[key]

    def __len__(self) -> int:
        return 1

    def accept(self, v: Visitor[T, U], ctx: T):
        return v.visitUnary(self, ctx)

    def __str__(self) -> str:
        return "{}({})".format(
            self.op.value,
            self.operand,
        )


class Binary(Expression):
    """
    AST node of binary expression.
    Note that the operation type (like plus or subtract) is not among its children. 
    二元表达式
    """

    def __init__(self, op: BinaryOp, lhs: Expression, rhs: Expression) -> None:
        super().__init__(f"binary({op.value})")
        self.lhs = lhs
        self.op = op
        self.rhs = rhs

    def __getitem__(self, key: int) -> Node:
        return (self.lhs, self.rhs)[key]

    def __len__(self) -> int:
        return 2

    def accept(self, v: Visitor[T, U], ctx: T):
        return v.visitBinary(self, ctx)

    def __str__(self) -> str:
        return "({}){}({})".format(
            self.lhs,
            self.op.value,
            self.rhs,
        )

class Assignment(Binary):
    """
    AST node of assignment expression.
    It's actually a kind of binary expression, but it'll make things easier if we use another accept method to handle it.
    """

    def __init__(self, lhs: Union[Identifier, IndexExpr], rhs: Expression) -> None:
        super().__init__(BinaryOp.Assign, lhs, rhs)

    def accept(self, v: Visitor[T, U], ctx: T):
        return v.visitAssignment(self, ctx)


class ConditionExpression(Expression):
    """
    AST node of condition expression (`?:`).
    """

    def __init__(
        self, cond: Expression, then: Expression, otherwise: Expression
    ) -> None:
        super().__init__("cond_expr")
        self.cond = cond
        self.then = then
        self.otherwise = otherwise

    def __getitem__(self, key: Union[int, str]) -> Node:
        if isinstance(key, int):
            return (self.cond, self.then, self.otherwise)[key]
        return self.__dict__[key]

    def __len__(self) -> int:
        return 3

    def accept(self, v: Visitor[T, U], ctx: T):
        return v.visitCondExpr(self, ctx)

    def __str__(self) -> str:
        return "({})?({}):({})".format(
            self.cond,
            self.then,
            self.otherwise,
        )

