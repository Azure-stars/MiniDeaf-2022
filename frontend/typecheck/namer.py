from os import EX_OSERR
from typing import Protocol, TypeVar, cast
from frontend.ast.tree import *
from frontend.ast.visitor import RecursiveVisitor, Visitor
from frontend.scope.globalscope import GlobalScope
from frontend.scope.scope import Scope, ScopeKind
from frontend.scope.scopestack import ScopeStack
from frontend.symbol.funcsymbol import FuncSymbol
from frontend.symbol.symbol import Symbol
from frontend.symbol.varsymbol import VarSymbol
from frontend.type.array import ArrayType
from frontend.type.type import DecafType
from utils.error import *
from utils.riscv import MAX_INT

"""
The namer phase: resolve all symbols defined in the abstract syntax tree and store them in symbol tables (i.e. scopes).
"""


class Namer(Visitor[ScopeStack, None]):
    def __init__(self) -> None:
        pass

    # Entry of this phase
    def transform(self, program: Program) -> tuple[Program, ScopeStack]:
        # Global scope. You don't have to consider it until Step 9.
        program.globalScope = GlobalScope
        ctx = ScopeStack(program.globalScope)
        program.accept(self, ctx)
        return (program,ctx)

    def visitProgram(self, program: Program, ctx: ScopeStack) -> None:
        # Check if the 'main' function is missing
        if not program.hasMainFunc():
            raise DecafNoMainFuncError
        for child in program:
            child.accept(self, ctx)

    def visitFunction(self, func: Function, ctx: ScopeStack) -> None:
        # 要检查是否重复定义或者重复声明，重复声明允许类型相同。
        if ctx.globalscope.containsKey(func.ident.value):
            temp = ctx.globalscope.get(func.ident.value)
            # 在全局符号表里面找
            if(isinstance(temp, FuncSymbol)):
                # 都是函数符号
                # 先检查是否参数列表一致
                if len(temp.para_type) != len(func.parameterlist.children):
                    raise DecafDeclConflictError(func.ident.value)  
                    # 声明了两个不同的函数
                for index in range(len(temp.para_type)):
                    if temp.para_type[index] != func.parameterlist.children[index].var_t:
                        # 参数列表不一致
                        raise DecafDeclConflictError(func.ident.value)
                if temp.scope != NULL and func.body != NULL:
                    # 重复定义函数
                    raise DecafGlobalVarDefinedTwiceError(func.ident.value)
            else:
                # 全局变量符号，有问题
                raise DecafGlobalVarDefinedTwiceError(func.ident.value)
        new_symbol = FuncSymbol(func.ident.value, func.ret_t.type, NULL)
        # 现在要同时visit参数与函数体，并共享作用域
        new_score = Scope(ScopeKind.LOCAL)
        ctx.open(new_score)
        for param in func.parameterlist.children:
            new_symbol.addParaType(param.var_t)
        func.parameterlist.accept(self, ctx)
        if func.body != NULL:
            # 利用scope是否为空来判断是否为声明
            new_symbol.scope = new_score
            # 覆盖原有符号，将函数设置为定义，注意需要在全局的符号表中进行检验
        ctx.globalscope.declare(new_symbol)
        if func.body != NULL:
            # 保证body不为空
            for child in func.body.children:
                child.accept(self, ctx)
        ctx.close()

    def visitParameterList(self, parameterlist: ParameterList, ctx: ScopeStack) -> None:
        # 逐个检查参数
        for parameter in parameterlist:
            parameter.accept(self, ctx)

    def visitExpressionList(self, expressionlist: ExpressionList, ctx: ScopeStack) -> None:
        # 检查声明中的实参
        for expression in expressionlist:
            expression.accept(self, ctx)

    def visitBlock(self, block: Block, ctx: ScopeStack) -> None:
        new_score = Scope(ScopeKind.LOCAL)
        ctx.open(new_score)
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
    # 1. Open a local scope for stmt.init.
    # 2. Visit stmt.init, stmt.cond, stmt.update.
    # 3. Open a loop in ctx (for validity checking of break/continue)
    # 4. Visit body of the loop.
    # 5. Close the loop and the local scope.

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
        if not ctx.inLoop():
            raise DecafBreakOutsideLoopError()
        ctx.closeLoop()
    def visitContinue(self, stmt: Continue, ctx: ScopeStack) -> None:
        if not ctx.inLoop():
            raise DecafContinueOutsideLoopError()
        """
        1. Refer to the implementation of visitBreak.
        """

    def visitGlobalDeclaration(self, decl: GlobalDeclaration, ctx: ScopeStack) -> None:
        if ctx.globalscope.containsKey(decl.ident.value):
            # 重复定义，必定为错误
            # 不允许同时有声明与定义
            raise DecafGlobalVarDefinedTwiceError(decl.ident.value)

        now_symbol = VarSymbol(decl.ident.value, decl.var_t.type, True)
        if decl.init_expr != NULL:
            decl.init_expr.accept(self, ctx)
            now_symbol.setInitValue(decl.init_expr.value)
            # 标记其为已经定义
        ctx.globalscope.declare(now_symbol)
        # print(now_symbol.isGlobal)
        decl.setattr("symbol", now_symbol)


    def visitDeclaration(self, decl: Declaration, ctx: ScopeStack) -> None:
        """
        1. Use ctx.findConflict to find if a variable with the same name has been declared.
        2. If not, build a new VarSymbol, and put it into the current scope using ctx.declare.
        3. Set the 'symbol' attribute of decl.
        4. If there is an initial value, visit it.
        """
        temp = ctx.findConflict(decl.ident.value)
        # 判断是否重名
        if temp != None:
            raise DecafGlobalVarDefinedTwiceError(decl.ident.value)
        new_symbol = VarSymbol(decl.ident.value, decl.var_t.type)
        ctx.declare(new_symbol)
        decl.setattr("symbol", new_symbol)
        if decl.init_expr != NULL:
            decl.init_expr.accept(self, ctx)

    def visitCall(self, call : Call, ctx : ScopeStack) -> None:
        # 设置属性值
        # 还要检查在当前作用域有没有这个函数
        if ctx.currentScope() != ctx.globalscope:
            # 检查全局作用域
            temp = ctx.findConflict(call.ident.value)
            if temp != None:
                # 局部重名
                raise DecafGlobalVarDefinedTwiceError(call.ident.value)

        if ctx.globalscope.containsKey(call.ident.value):
            # 找到对应的函数符号
            fun_symbol = ctx.globalscope.get(call.ident.value)
            if isinstance(fun_symbol, FuncSymbol):
                call.ident.accept(self, ctx)
                if len(call.argument_list) != len(fun_symbol.para_type):
                    raise DecafBadFuncCallError(call.ident.value)
                call.argument_list.accept(self, ctx)
            else:
                raise DecafBadFuncCallError(call.ident.value)
        else:
            raise DecafBadFuncCallError(call.ident.value)

    def visitParameter(self, para: Parameter, ctx: ScopeStack) -> None:
        # 相当于声明变量，需要加入符号表并且新建节点
        temp = ctx.findConflict(para.ident.value)
        if temp != None:
            raise DecafDeclConflictError(para.ident.value)
        new_symbol = VarSymbol(para.ident.value, para.var_t.type)
        ctx.declare(new_symbol)
        para.setattr("symbol", new_symbol)

    def visitAssignment(self, expr: Assignment, ctx: ScopeStack) -> None:
        """
        1. Refer to the implementation of visitBinary.
        """
        expr.lhs.accept(self, ctx)
        expr.rhs.accept(self, ctx)
        pass

    def visitUnary(self, expr: Unary, ctx: ScopeStack) -> None:
        expr.operand.accept(self, ctx)

    def visitBinary(self, expr: Binary, ctx: ScopeStack) -> None:
        expr.lhs.accept(self, ctx)
        expr.rhs.accept(self, ctx)

    def visitCondExpr(self, expr: ConditionExpression, ctx: ScopeStack) -> None:
        """
        1. Refer to the implementation of visitBinary.
        """
        expr.cond.accept(self, ctx)
        expr.then.accept(self, ctx)
        expr.otherwise.accept(self, ctx)

    def visitIdentifier(self, ident: Identifier, ctx: ScopeStack) -> None:
        """
        1. Use ctx.lookup to find the symbol corresponding to ident.
        2. If it has not been declared, raise a DecafUndefinedVarError.
        3. Set the 'symbol' attribute of ident.
        """
        temp = ctx.lookup(ident.value)
        if temp == NULL:
            raise DecafUndefinedVarError(ident.value)
        ident.setattr("symbol",temp)
        # pass

    def visitIntLiteral(self, expr: IntLiteral, ctx: ScopeStack) -> None:
        value = expr.value
        if value > MAX_INT:
            raise DecafBadIntValueError(value)
