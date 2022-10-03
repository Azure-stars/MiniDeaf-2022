"""
Module that defines the base type of visitor.
"""


from __future__ import annotations

from typing import Callable, Protocol, Sequence, TypeVar

from .node import *
from .tree import *

T = TypeVar("T", covariant=True)
U = TypeVar("U", covariant=True)


def accept(visitor: Visitor[T, U], ctx: T) -> Callable[[Node], Optional[U]]:
    return lambda node: node.accept(visitor, ctx)


class Visitor(Protocol[T, U]):  # type: ignore
    def visitOther(self, node: Node, ctx: T) -> None:
        return None
    # python类函数都要带self参数，但是在静态方法中，带ctx参数而不是self

    # self指的是实例对象; 而ctx用在静态方法中, 调用的时候不需要实例化对象, 直接通过类名就可以调用, 所以self在静态方法中没有意义

    # 自定义的forward()方法和backward()方法的第一个参数必须是ctx; ctx可以保存forward()中的变量,以便在backward()中继续使用

    # visit模式：每一个被检查的点调用相应的visit函数，传入参数一般为自身类型的实例

    def visitNULL(self, that: NullType, ctx: T) -> Optional[U]:
        return self.visitOther(that, ctx)

    def visitProgram(self, that: Program, ctx: T) -> Optional[Sequence[Optional[U]]]:
        return self.visitOther(that, ctx)

    def visitBlock(self, that: Block, ctx: T) -> Optional[Sequence[Optional[U]]]:
        return self.visitOther(that, ctx)

    def visitFunction(self, that: Function, ctx: T) -> Optional[U]:
        return self.visitOther(that, ctx)

    def visitIf(self, that: If, ctx: T) -> Optional[U]:
        return self.visitOther(that, ctx)

    def visitReturn(self, that: Return, ctx: T) -> Optional[U]:
        return self.visitOther(that, ctx)

    def visitWhile(self, that: While, ctx: T) -> Optional[U]:
        return self.visitOther(that, ctx)

    def visitBreak(self, that: Break, ctx: T) -> Optional[U]:
        return self.visitOther(that, ctx)

    def visitDeclaration(self, that: Declaration, ctx: T) -> Optional[U]:
        return self.visitOther(that, ctx)

    def visitUnary(self, that: Unary, ctx: T) -> Optional[U]:
        return self.visitOther(that, ctx)

    def visitBinary(self, that: Binary, ctx: T) -> Optional[U]:
        return self.visitOther(that, ctx)

    def visitAssignment(self, that: Assignment, ctx: T) -> Optional[U]:
        """
        ## ! Note that the default behavior is `visitBinary`, not `visitOther`
        """
        return self.visitBinary(that, ctx)

    def visitCondExpr(self, that: ConditionExpression, ctx: T) -> Optional[U]:
        return self.visitOther(that, ctx)

    def visitIdentifier(self, that: Identifier, ctx: T) -> Optional[U]:
        return self.visitOther(that, ctx)

    def visitIntLiteral(self, that: IntLiteral, ctx: T) -> Optional[U]:
        return self.visitOther(that, ctx)

    def visitTInt(self, that: TInt, ctx: T) -> Optional[U]:
        return self.visitOther(that, ctx)


class RecursiveVisitor(Visitor[T, U]):
    def visitOther(self, node: Node, ctx: T) -> Optional[Sequence[Optional[U]]]:
        ret = tuple(map(accept(self, ctx), node))
        return ret if ret and ret.count(None) == len(ret) else None
