from typing import Protocol, TypeVar

from frontend.ast.node import Node
from frontend.ast.tree import *
from frontend.ast.visitor import Visitor
from frontend.scope.globalscope import GlobalScope
from frontend.scope.scope import Scope, ScopeKind
from frontend.scope.scopestack import ScopeStack
from frontend.symbol.varsymbol import VarSymbol
from frontend.symbol.Arraysymbol import ArraySymbol
from frontend.symbol.funcsymbol import FuncSymbol
from frontend.type.array import ArrayType
from utils.error import *

"""
The typer phase: type check abstract syntax tree.
"""


class Typer(Visitor[ScopeStack, None]):
    def __init__(self) -> None:
        pass

    # Entry of this phase
    def transform(self, program: Program) -> Program:
        ctx = ScopeStack(program.globalScope)
        program.accept(self, ctx)
        return program

    def visitProgram(self, program: Program, ctx: ScopeStack) -> None:
        for child in program:
            child.accept(self, ctx)

    def visitFunction(self, func: Function, ctx: ScopeStack) -> None:
        # assert(type(func.ident, Identifier))
        # assert(type(func.parameterlist, ParameterList))
        for param in func.parameterlist.children:
            param.accept(self, ctx)
        if func.body != NULL:
            for child in func.body.children:
                child.accept(self, ctx)

    def visitParameterList(self, parameterlist: ParameterList, ctx: ScopeStack) -> None:
        for parameter in parameterlist:
            parameter.accept(self, ctx)

    def visitExpressionList(self, expressionlist: ExpressionList, ctx: T) -> None:
        for expression in expressionlist.children:
            expression.accept(self, ctx)

    def visitBlock(self, block: Block, ctx: ScopeStack) -> None:
        new_scorre = Scope(ScopeKind.LOCAL)
        ctx.open(new_scorre)
        for child in block:
            child.accept(self, ctx)
        ctx.close()

    def visitReturn(self, stmt: Return, ctx: ScopeStack) -> None:
        stmt.expr.accept(self, ctx)

    def visitFor(self, stmt: For, ctx: ScopeStack) -> None:
        ctx.open(Scope(ScopeKind.LOCAL))
        ctx.openLoop()
        stmt.init.accept(self,ctx)
        stmt.cond.accept(self,ctx)
        stmt.update.accept(self,ctx)
        stmt.body.accept(self, ctx)
        ctx.closeLoop()
        ctx.close()

    def visitIf(self, stmt: If, ctx: ScopeStack) -> None:
        stmt.cond.accept(self, ctx)
        stmt.then.accept(self, ctx)
        # 对于不同的类型，有可能visit的变量数目不定
        # check if the else branch exists
        if not stmt.otherwise is NULL:
            stmt.otherwise.accept(self, ctx)

    def visitWhile(self, stmt: While, ctx: ScopeStack) -> None:
        ctx.open(Scope(ScopeKind.LOCAL))
        stmt.cond.accept(self, ctx)
        ctx.openLoop()
        stmt.body.accept(self, ctx)
        ctx.closeLoop()
        ctx.close()

    def visitDoWhile(self, stmt: DoWhile, ctx: ScopeStack) -> None:
        ctx.open(Scope(ScopeKind.LOCAL))
        ctx.openLoop()
        stmt.body.accept(self,ctx)
        ctx.closeLoop()
        stmt.cond.accept(self,ctx)
        ctx.close()

    def visitBreak(self, stmt: Break, ctx: ScopeStack) -> None:
        ctx.closeLoop()
    def visitContinue(self, stmt: Continue, ctx: ScopeStack) -> None:
        return


    def visitGlobalDeclaration(self, decl: GlobalDeclaration, ctx: ScopeStack) -> None:
        # 检查下标是否为int
        # 检查符号是不是一个数组或者变量
        # 检查返回值与初始化式子的值是否对应
        # 若当前为变量，则初始化值为一个常数
        # 若当前为数组，则初始化值为一个集合
        
        now_symbol = decl.getattr('symbol')

        # if len(decl.index.children) == 0 and type(now_symbol) != VarSymbol:
        #     raise DecafTypeMismatchError

        # if len(decl.index.children) != 0 and type(now_symbol) != ArraySymbol:
        #     raise DecafTypeMismatchError
        
        if decl.init_expr != NULL:
            decl.init_expr.accept(self, ctx)
            if type(now_symbol) == VarSymbol and type(decl.init_expr) != IntLiteral:
                raise DecafTypeMismatchError
            if type(now_symbol) == ArraySymbol and type(decl.init_expr) != InitList:
                # 之后会修改，加上集合
                raise DecafTypeMismatchError
            
    def visitDeclaration(self, decl: Declaration, ctx: ScopeStack) -> None:
        # 检查类型是否对应
        # 此时右边的东西是一个表达式，需要仔细判断
        now_symbol = decl.getattr('symbol')
        if decl.init_expr != NULL:
            # 只检查数组，数组的赋值比较特别 
            decl.init_expr.accept(self, ctx) 
            if type(now_symbol) == ArraySymbol and type(decl.init_expr) != InitList:
                # 需要为集合
                raise DecafTypeMismatchError
            # 其余情况下
            if type(now_symbol) == VarSymbol:
                # 仅有一种可能，即对应的初始化式子是一个数组的名字或者不完整的数组。
                # 不完整的数组会被我pass掉
                # 应该在name.py里面检查的
                if type(decl.init_expr) == Identifier:
                    init_symbol = decl.init_expr.getattr('symbol')
                    if type(init_symbol) == ArraySymbol:
                        raise DecafTypeMismatchError
    
    def visitCall(self, call : Call, ctx : ScopeStack) -> None:
        # 设置属性值
        # 还要检查在当前作用域有没有这个函数
        fun_symbol = ctx.globalscope.get(call.ident.value)
        if isinstance(fun_symbol, FuncSymbol):
            call.ident.accept(self, ctx)
            # call.argument_list.accept(self, ctx)
            for (id, arg) in enumerate(call.argument_list.children):
                real_type = fun_symbol.para_type[id]
                # 获取真实定义的参数type
                if isinstance(real_type, TIntArray):
                    if isinstance(arg, Identifier): 
                        arg_symbol = arg.getattr('symbol')
                        if isinstance(arg_symbol, ArraySymbol):
                            arg_slicing = real_type.slicing
                            pass_slicing = arg_symbol.index
                            if len(arg_slicing) != len(pass_slicing):
                                raise DecafBadFuncCallError(call.ident.value)
                            for id in range(1, len(arg_slicing)):
                                if arg_slicing[id] != pass_slicing[id]:
                                    raise DecafBadFuncCallError
                        # 若当前位置是数组，那么我们传入的参数一定是数组名
                        else:
                            # 检查长度维数是否一致
                            raise DecafBadFuncCallError
                    else:
                        raise DecafBadFuncCallError
                elif isinstance(real_type, TInt):
                    if isinstance(arg, Identifier):
                        arg_symbol = arg.getattr('symbol')
                        if isinstance(arg_symbol, ArraySymbol):
                        # 若当前位置是数组，那么我们传入的参数一定是数组名
                            raise DecafBadFuncCallError
                # 检查参数列表的时候应当注意，需要每一个位置的类型也一样
        else:
            raise DecafBadFuncCallError(call.ident.value)
        # call总是返回int

    def visitParameter(self, para: Parameter, ctx: ScopeStack) -> None:
        # 相当于声明变量，需要加入符号表并且新建节点
        return
        # 没啥好检查的

    def visitAssignment(self, expr: Assignment, ctx: ScopeStack) -> None:
        """
        1. Refer to the implementation of visitBinary.
        """
        expr.lhs.accept(self, ctx)
        expr.rhs.accept(self, ctx)    
        # 检查时赋值需要满足，集合给数组赋值，其他情况下给变量赋值

    def visitUnary(self, expr: Unary, ctx: ScopeStack) -> None:
        # 不允许给数组进行操作
        expr.operand.accept(self, ctx)
        
    def visitBinary(self, expr: Binary, ctx: ScopeStack) -> None:
        expr.lhs.accept(self, ctx)
        expr.rhs.accept(self, ctx)

    def visitIndexList(self, indexlist: IndexList, ctx: ScopeStack) -> None:
        for child in indexlist.children:
            child.accept(self, ctx)
        
    def visitIndexExpr(self, expr: IndexExpr, ctx: ScopeStack) -> None:
        # 这里有意思
        # 你需要去找到这里的长度是否和arraysymbol的长度一样。
        now_symbol = expr.getattr('symbol')
        if isinstance(now_symbol, ArraySymbol):
            if len(now_symbol.index) != len(expr.index.children):
                raise DecafTypeMismatchError
            # 越界检查不用在这里搞
            expr.index.accept(self, ctx)
        else:
            raise DecafTypeMismatchError

    def visitCondExpr(self, expr: ConditionExpression, ctx: ScopeStack) -> None:
        """
        1. Refer to the implementation of visitBinary.
        """
        expr.cond.accept(self, ctx)
        expr.then.accept(self, ctx)
        expr.otherwise.accept(self, ctx)

    def visitIdentifier(self, ident: Identifier, ctx: ScopeStack) -> None:
        """
        这里是用来给普通变量的，所以不能出现数组名称
        """
        now_symbol = ident.getattr('symbol')
        if type(now_symbol) == ArraySymbol:
            raise DecafTypeMismatchError

    def visitIntLiteral(self, expr: IntLiteral, ctx: ScopeStack) -> None:
        return
        