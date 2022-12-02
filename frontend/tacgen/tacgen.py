from ast import Pass
from cmath import exp
from textwrap import indent
import utils.riscv as riscv
from frontend.ast import node
from frontend.ast.tree import *
from frontend.ast.visitor import Visitor
from frontend.symbol.varsymbol import VarSymbol
from frontend.typecheck.namer import ScopeStack
from frontend.type.array import ArrayType
from utils.tac import tacop
from utils.tac.funcvisitor import FuncVisitor
from utils.tac.programwriter import ProgramWriter
from utils.tac.tacprog import TACProg
from utils.tac.temp import Temp

"""
The TAC generation phase: translate the abstract syntax tree into three-address code.
"""


class TACGen(Visitor[FuncVisitor, None]):
    def __init__(self, ctx: ScopeStack) -> None:
        self.ctx = ctx
        pass

    # Entry of this phase
    def transform(self, program: Program) -> TACProg:
        # 应当检查所有函数，不同函数之间的tac码彼此独立
        pw = ProgramWriter(list(program.functions().keys()))

        # 其实全局变量可以在一开始就生成出来，存在符号表里面

        for name,func in program.functions().items():
            if func.body == NULL:
                # 未定义的函数不用生成
                continue
            mv = pw.visitFunc(name, len(func.parameterlist))
            # 此时不用对参数列表进行tac生成，但需要先行分配寄存器
            for para in func.parameterlist.children:
                para.accept(self, mv)
            func.body.accept(self, mv)
            # The function visitor of 'main' is special.
            # Remember to call mv.visitEnd after the translation a function.
            mv.visitEnd()
        # Remember to call pw.visitEnd before finishing the translation phase.
        return pw.visitEnd()

    def visitCall(self, call: Call, mv: FuncVisitor) ->None:
        # 生成PARAMS 和 CALL
        # 先生成PARAMS
        for param in call.argument_list.children:
            param.accept(self, mv)

        for param in call.argument_list.children:
            # 遍历完参数再生成CALL语句
            mv.visitParam(param.getattr("val"))
        call.setattr('val', mv.visitCall(mv.getFuncLabel(call.ident.value)))  

    def visitBlock(self, block: Block, mv: FuncVisitor) -> None:
        for child in block:
            child.accept(self, mv)

    def visitReturn(self, stmt: Return, mv: FuncVisitor) -> None:
        stmt.expr.accept(self, mv)
        mv.visitReturn(stmt.expr.getattr("val"))

    def visitBreak(self, stmt: Break, mv: FuncVisitor) -> None:
        mv.visitBranch(mv.getBreakLabel())

    def visitContinue(self, stmt: Continue, mv: FuncVisitor) -> None:
        mv.visitBranch(mv.getContinueLabel())

    def visitParameter(self, para: Parameter, mv: FuncVisitor) -> None:
        symbol = para.getattr('symbol')
        symbol.temp = mv.freshTemp()
        # 为参数提供寄存器，从而方便调用

    def visitIdentifier(self, ident: Identifier, mv: FuncVisitor) -> None:
        """
        1. Set the 'val' attribute of ident as the temp variable of the 'symbol' attribute of ident.
        """
        symbol = ident.getattr("symbol")
        if isinstance(symbol, VarSymbol):
            if symbol.isGlobal:
                mid_temp = mv.freshTemp()
                mv.visitGlobalAddressLoad(ident.value, mid_temp)
                symbol.temp = mv.freshTemp()
                ident.setattr('val', mv.visitGlobalOffsetLoad(symbol.temp, mid_temp, 0))
            else:
                ident.setattr("val", symbol.temp)
        else:
            ident.setattr("val", symbol.temp)

    def visitDeclaration(self, decl: Declaration, mv: FuncVisitor) -> None:
        """
        1. Get the 'symbol' attribute of decl.
        2. Use mv.freshTemp to get a new temp variable for this symbol.
        3. If the declaration has an initial value, use mv.visitAssignment to set it.
        """
        now_symbol = decl.getattr("symbol")
        now_symbol.temp = mv.freshTemp()
        if decl.init_expr != NULL:
            decl.init_expr.accept(self, mv)
            src = decl.init_expr.getattr("val")
            decl.setattr("val", mv.visitAssignment(now_symbol.temp, src))

    def visitAssignment(self, expr: Assignment, mv: FuncVisitor) -> None:
        """
        1. Visit the right hand side of expr, and get the temp variable of left hand side.
        2. Use mv.visitAssignment to emit an assignment instruction.
        3. Set the 'val' attribute of expr as the value of assignment instruction.
        """
        expr.lhs.accept(self, mv)
        expr.rhs.accept(self, mv)
        dst = expr.lhs.getattr("val")
        src = expr.rhs.getattr("val")
        # 如果全局变量在这里被修改了，需要额外添加tac码反映到实际的地址
        expr.setattr("val", mv.visitAssignment(dst, src))
        if self.ctx.globalscope.containsKey(expr.lhs.value):
            now_symbol = self.ctx.globalscope.get(expr.lhs.value)
            if isinstance(now_symbol, VarSymbol):
                mid_temp = mv.freshTemp()
                mv.visitGlobalAddressLoad(expr.lhs.value, mid_temp)
                mv.visitGlobalOffsetStore(dst, mid_temp, 0)
                # 存进全局变量的地址

    def visitIf(self, stmt: If, mv: FuncVisitor) -> None:
        stmt.cond.accept(self, mv)

        if stmt.otherwise is NULL:
            skipLabel = mv.freshLabel()
            mv.visitCondBranch(
                tacop.CondBranchOp.BEQ, stmt.cond.getattr("val"), skipLabel
            )
            stmt.then.accept(self, mv)
            mv.visitLabel(skipLabel)
        else:
            skipLabel = mv.freshLabel()
            exitLabel = mv.freshLabel()
            mv.visitCondBranch(
                tacop.CondBranchOp.BEQ, stmt.cond.getattr("val"), skipLabel
            )
            stmt.then.accept(self, mv)
            mv.visitBranch(exitLabel)
            # 挂上jump exitlabel
            mv.visitLabel(skipLabel)
            stmt.otherwise.accept(self, mv)
            mv.visitLabel(exitLabel)

    def visitWhile(self, stmt: While, mv: FuncVisitor) -> None:
        beginLabel = mv.freshLabel()
        loopLabel = mv.freshLabel()
        breakLabel = mv.freshLabel()
        mv.openLoop(breakLabel, loopLabel)

        mv.visitLabel(beginLabel)
        stmt.cond.accept(self, mv)
        mv.visitCondBranch(tacop.CondBranchOp.BEQ, stmt.cond.getattr("val"), breakLabel)

        stmt.body.accept(self, mv)
        mv.visitLabel(loopLabel)
        mv.visitBranch(beginLabel)
        mv.visitLabel(breakLabel)
        mv.closeLoop()

    def visitFor(self, stmt: For, mv: FuncVisitor) -> None:
        beginLabel = mv.freshLabel()
        loopLabel = mv.freshLabel()
        breakLabel = mv.freshLabel()
        mv.openLoop(breakLabel, loopLabel)
        if stmt.init is not NULL:
            stmt.init.accept(self,mv)
        mv.visitLabel(beginLabel)
        if stmt.cond is not NULL:
            stmt.cond.accept(self,mv)
            mv.visitCondBranch(tacop.CondBranchOp.BEQ, stmt.cond.getattr("val"), breakLabel)
        stmt.body.accept(self, mv)
        mv.visitLabel(loopLabel)
        if stmt.update is not NULL:
            stmt.update.accept(self, mv)
        mv.visitBranch(beginLabel)
        mv.visitLabel(breakLabel)
        mv.closeLoop()

    def visitDoWhile(self, stmt: DoWhile, mv: FuncVisitor) -> None:
        beginLabel = mv.freshLabel()
        loopLabel = mv.freshLabel()
        breakLabel = mv.freshLabel()
        mv.openLoop(breakLabel, loopLabel)
        mv.visitLabel(beginLabel)
        stmt.body.accept(self, mv)
        mv.visitLabel(loopLabel)
        stmt.cond.accept(self,mv)
        mv.visitCondBranch(tacop.CondBranchOp.BNE, stmt.cond.getattr("val"), beginLabel)
        mv.visitLabel(breakLabel)
        mv.closeLoop()

    def visitUnary(self, expr: Unary, mv: FuncVisitor) -> None:
        expr.operand.accept(self, mv)
        # 先解析表达式，再解析符号
        op = {
            node.UnaryOp.Neg: tacop.UnaryOp.NEG,
            node.UnaryOp.BitNot: tacop.UnaryOp.NOT,
            node.UnaryOp.LogicNot: tacop.UnaryOp.SEQZ
        }[expr.op]
        expr.setattr("val", mv.visitUnary(op, expr.operand.getattr("val")))
        # 在父结点，我们根据子结点的临时变量与操作符号，生成一条指令，将这条指令得到的目标临时变量设置为父结点的临时变量
    def visitBinary(self, expr: Binary, mv: FuncVisitor) -> None:
        expr.lhs.accept(self, mv)
        expr.rhs.accept(self, mv)
        op = {
            node.BinaryOp.Add: tacop.BinaryOp.ADD,
            node.BinaryOp.Sub: tacop.BinaryOp.SUB,
            node.BinaryOp.Mul: tacop.BinaryOp.MUL,
            node.BinaryOp.Div: tacop.BinaryOp.DIV,
            node.BinaryOp.Mod: tacop.BinaryOp.REM,
            node.BinaryOp.LT: tacop.BinaryOp.SLT,
            node.BinaryOp.GT: tacop.BinaryOp.SGT,
            node.BinaryOp.LogicAnd: tacop.BinaryOp.AND,
            node.BinaryOp.LogicOr: tacop.BinaryOp.OR,
            node.BinaryOp.EQ: tacop.BinaryOp.EQU,
            node.BinaryOp.NE: tacop.BinaryOp.NEQ,
            node.BinaryOp.LE: tacop.BinaryOp.LEQ,
            node.BinaryOp.GE: tacop.BinaryOp.GEQ,
            # You can add binary operations here.
        }[expr.op]
        expr.setattr(
            "val", mv.visitBinary(op, expr.lhs.getattr("val"), expr.rhs.getattr("val"))
        )

    def visitCondExpr(self, expr: ConditionExpression, mv: FuncVisitor) -> None:
        """
        1. Refer to the implementation of visitIf and visitBinary.
        """
        expr.cond.accept(self, mv)

        skipLabel = mv.freshLabel()
        exitLabel = mv.freshLabel()
        mv.visitCondBranch(
            tacop.CondBranchOp.BEQ, expr.cond.getattr("val"), skipLabel
        )
        expr.then.accept(self, mv)
        dst = expr.cond.getattr("val")
        src = expr.then.getattr("val")
        mv.visitAssignment(dst, src)
        expr.setattr("val", dst)
        mv.visitBranch(exitLabel)
        # 挂上jump exitlabel
        mv.visitLabel(skipLabel)
        expr.otherwise.accept(self, mv)
        src = expr.otherwise.getattr("val")
        mv.visitAssignment(dst, src)
        expr.setattr("val", dst)
        mv.visitLabel(exitLabel)

    def visitIntLiteral(self, expr: IntLiteral, mv: FuncVisitor) -> None:
        expr.setattr("val", mv.visitLoad(expr.value))
