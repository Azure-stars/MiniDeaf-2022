from typing import Sequence, Tuple

from backend.asmemitter import AsmEmitter
from utils.error import IllegalArgumentException
from utils.label.label import Label, LabelKind
from utils.riscv import Riscv
from utils.tac.reg import Reg
from utils.tac.tacfunc import TACFunc
from utils.tac.tacinstr import *
from utils.tac.tacvisitor import TACVisitor

from ..subroutineemitter import SubroutineEmitter
from ..subroutineinfo import SubroutineInfo

"""
RiscvAsmEmitter: an AsmEmitter for RiscV
"""


class RiscvAsmEmitter(AsmEmitter):
    def __init__(
        self,
        allocatableRegs: list[Reg],
        callerSaveRegs: list[Reg],
    ) -> None:
        super().__init__(allocatableRegs, callerSaveRegs)

    
        # the start of the asm code
        # int step10, you need to add the declaration of global var here
        self.printer.println(".text")
        self.printer.println(".global main")
        self.printer.println("")

    # transform tac instrs to RiscV instrs
    # collect some info which is saved in SubroutineInfo for SubroutineEmitter
    def selectInstr(self, func: TACFunc) -> tuple[list[str], SubroutineInfo]:

        selector: RiscvAsmEmitter.RiscvInstrSelector = (
            RiscvAsmEmitter.RiscvInstrSelector(func.entry)
        )
        for instr in func.getInstrSeq():
            instr.accept(selector)

        info = SubroutineInfo(func.entry)
        return (selector.seq, info)

    # use info to construct a RiscvSubroutineEmitter
    def emitSubroutine(self, info: SubroutineInfo):
        return RiscvSubroutineEmitter(self, info)

    # return all the string stored in asmcodeprinter
    def emitEnd(self):
        return self.printer.close()

    class RiscvInstrSelector(TACVisitor):
        def __init__(self, entry: Label) -> None:
            self.entry = entry
            self.seq = []

        # in step11, you need to think about how to deal with globalTemp in almost all the visit functions. 
        def visitReturn(self, instr: Return) -> None:
            # print(instr.value)
            # print(instr)
            if instr.value is not None:
                self.seq.append(Riscv.Move(Riscv.A0, instr.value))
            else:
                self.seq.append(Riscv.LoadImm(Riscv.A0, 0))
            self.seq.append(Riscv.JumpToEpilogue(self.entry))
        def visitAssign(self, instr: Assign) -> None:
            self.seq.append(Riscv.Move(instr.dst, instr.src))

        def visitMark(self, instr: Mark) -> None:
            self.seq.append(Riscv.RiscvLabel(instr.label))

        def visitLoadImm4(self, instr: LoadImm4) -> None:
            self.seq.append(Riscv.LoadImm(instr.dst, instr.value))

        def visitUnary(self, instr: Unary) -> None:
            self.seq.append(Riscv.Unary(instr.op, instr.dst, instr.operand))
 
        def visitBinary(self, instr: Binary) -> None:
            if instr.op == BinaryOp.EQU:
                self.seq.append(Riscv.Binary(BinaryOp.SUB, instr.dst, instr.lhs, instr.rhs))
                self.seq.append(Riscv.Unary(UnaryOp.SEQZ, instr.dst, instr.dst))
            elif instr.op == BinaryOp.NEQ:
                self.seq.append(Riscv.Binary(BinaryOp.SUB, instr.dst, instr.lhs, instr.rhs))
                self.seq.append(Riscv.Unary(UnaryOp.SNEZ, instr.dst, instr.dst))
            elif instr.op == BinaryOp.LEQ:
                self.seq.append(Riscv.Binary(BinaryOp.SUB, instr.dst, instr.lhs, instr.rhs))
                self.seq.append(Riscv.Unary(UnaryOp.SGTZ, instr.dst, instr.dst))
                self.seq.append(Riscv.Unary(UnaryOp.SEQZ, instr.dst, instr.dst))
            elif instr.op == BinaryOp.GEQ:
                self.seq.append(Riscv.Binary(BinaryOp.SUB, instr.dst, instr.lhs, instr.rhs))
                self.seq.append(Riscv.Unary(UnaryOp.SLTZ, instr.dst, instr.dst))
                self.seq.append(Riscv.Unary(UnaryOp.SEQZ, instr.dst, instr.dst))
            elif instr.op == BinaryOp.OR:
                self.seq.append(Riscv.Binary(BinaryOp.OR, instr.dst, instr.lhs, instr.rhs))
                self.seq.append(Riscv.Unary(UnaryOp.SNEZ, instr.dst, instr.dst))
            elif instr.op == BinaryOp.AND:
                self.seq.append(Riscv.Unary(UnaryOp.SNEZ, instr.dst, instr.lhs))
                self.seq.append(Riscv.Binary(BinaryOp.SUB, instr.dst, Riscv.ZERO, instr.dst))
                self.seq.append(Riscv.Binary(BinaryOp.AND, instr.dst, instr.dst, instr.rhs))
                self.seq.append(Riscv.Unary(UnaryOp.SNEZ, instr.dst, instr.dst))
            else:
                self.seq.append(Riscv.Binary(instr.op, instr.dst, instr.lhs, instr.rhs))

        def visitCondBranch(self, instr: CondBranch) -> None:
            self.seq.append(Riscv.Branch(instr.op, instr.cond, instr.label))
        
        def visitBranch(self, instr: Branch) -> None:
            self.seq.append(Riscv.Jump(instr.target))

        # in step9, you need to think about how to pass the parameters and how to store and restore callerSave regs

        # in step11, you need to think about how to store the array 

        def visitParam(self, instr: Param) -> None:
            # 这里的传参很关键啊xdm
            # 要不要先把里面的值清空呢
            # 肯定要啊，这里很关键xdm
            # 专门开一个语句，在后端处理
            self.seq.append(Riscv.Param(instr.value))
            # 否则塞栈帧
            # 直接让栈帧的sp往下移动，然后之后回收就好了，喜
            # 感觉得让这个语句也在后端处理xs
            # 应该得去后端nnd
            # 摆烂！
        def visitCall(self, instr: Call) -> None:
            # 塞寄存器在后面进行，这里就是给个样子就好了
            self.seq.append(Riscv.Call(instr.label))
            self.seq.append(Riscv.Move(instr.value, Riscv.A0))

        def visitFunction(self, instr:Mark) -> None:
            # 需要
            pass
"""
RiscvAsmEmitter: an SubroutineEmitter for RiscV
"""

class RiscvSubroutineEmitter(SubroutineEmitter):
    def __init__(self, emitter: RiscvAsmEmitter, info: SubroutineInfo) -> None:
        super().__init__(emitter, info)
        
        # + 4 is for the RA reg 
        # + 4 is for the S0 reg
        self.nextLocalOffset = 4 * len(Riscv.CalleeSaved) + 4 + 4
        
        # the buf which stored all the NativeInstrs in this function
        self.buf: list[NativeInstr] = []

        # from temp to int
        # record where a temp is stored in the stack
        self.offsets = {}

        self.printer.printLabel(info.funcLabel)

        # in step9, step11 you can compute the offset of local array and parameters here

    def emitComment(self, comment: str) -> None:
        # you can add some log here to help you debug
        # self.printer.printComment(comment)
        # self.buf.append(Riscv.SPAdd(offset))
        pass
    
    def emitGetParam(self, dst: Reg, index: int) -> None:
        self.buf.append(Riscv.NativeLoadWord(dst, Riscv.FP,4 * (index - 8)))

    def emitStoreParam(self, src: Temp, index: int) -> None:
        # 只要塞进栈帧就好，不用影响原来的值
        self.buf.append(Riscv.SPAdd(-4))
        self.buf.append(Riscv.NativeLoadWord(Riscv.T0, Riscv.SP, 4 * (index + 1) + self.offsets[src.index]))
        self.buf.append(Riscv.NativeStoreWord(Riscv.T0, Riscv.SP, 0))

    def emitPopParam(self, offset:int) -> None:
        self.buf.append(Riscv.SPAdd(offset))
        # 直接回收栈帧即可

    # store some temp to stack
    # usually happen when reaching the end of a basicblock
    # in step9, you need to think about the fuction parameters here
    def emitStoreToStack(self, src: Reg) -> None:
        if src.temp.index not in self.offsets:
            # 没有记录在栈帧上

            self.offsets[src.temp.index] = self.nextLocalOffset
            # 新开一个位置
            self.nextLocalOffset += 4
        self.buf.append(
            Riscv.NativeStoreWord(src, Riscv.SP, self.offsets[src.temp.index])
        )
        # 每一个寄存器有他们各自独立的位置，好耶，这下子确定了

    def emitMoveReg(self, dst: Reg, src: Temp):
        self.buf.append(Riscv.Move(dst, src))

    # load some temp from stack
    # usually happen when using a temp which is stored to stack before
    # in step9, you need to think about the fuction parameters here
    def emitLoadFromStack(self, dst: Reg, src: Temp):
        if src.index not in self.offsets:

            # if src.index < num_args and (not )
            # 寄存器不在栈帧上
            raise IllegalArgumentException()
        else:
            self.buf.append(
                Riscv.NativeLoadWord(dst, Riscv.SP, self.offsets[src.index])
            )

    # add a NativeInstr to buf
    # when calling the fuction emitEnd, all the instr in buf will be transformed to RiscV code
    def emitNative(self, instr: NativeInstr):
        self.buf.append(instr)

    def emitLabel(self, label: Label):
        self.buf.append(Riscv.RiscvLabel(label).toNative([], []))


    def emitEnd(self):
        # numargs代表这个函数自身的参数
        # 需要在一开始就给他存好
        self.printer.printComment("start of prologue")
        self.printer.printInstr(Riscv.SPAdd(-self.nextLocalOffset))
        # 说明是在分配完寄存器之后才知道栈帧的大小，不用手工操作
        # in step9, you need to think about how to store RA here
        # you can get some ideas from how to save CalleeSaved regs
        # RA寄存器不在自由分配寄存器里面，需要我们自己写
        self.printer.printInstr(
            Riscv.NativeStoreWord(Riscv.RA, Riscv.SP, 4 * len(Riscv.CalleeSaved))
        )

        self.printer.printInstr(
            Riscv.NativeStoreWord(Riscv.FP, Riscv.SP, 4 * len(Riscv.CalleeSaved) + 4)
        )
        # 存储fp

        self.printer.printInstr(
            Riscv.Add(Riscv.FP, Riscv.SP, self.nextLocalOffset)
        )
        for i in range(len(Riscv.CalleeSaved)):
            # 这里竟然存好了所有的callee_saved？
            # 我感觉自己像个小丑
            # 那我不在一开始直接存好所有caller_saved直接开摆.jpg
            if Riscv.CalleeSaved[i].isUsed():
                # 哦用了才存，正确的
                self.printer.printInstr(
                    Riscv.NativeStoreWord(Riscv.CalleeSaved[i], Riscv.SP, 4 * i)
                )
                # callee_saved被存在了低位

        self.printer.printComment("end of prologue")
        self.printer.println("")

        self.printer.printComment("start of body")

        # in step9, you need to think about how to pass the parameters here
        # you can use the stack or regs
        # 需要把参数从寄存器中读取出来

        # using asmcodeprinter to output the RiscV code
        for instr in self.buf:
            # 每一句tac指令依次输出，多么美妙
            self.printer.printInstr(instr)

        self.printer.printComment("end of body")
        self.printer.println("")

        self.printer.printLabel(
            Label(LabelKind.TEMP, self.info.funcLabel.name + Riscv.EPILOGUE_SUFFIX)
        )
        # 输出退出标签
        self.printer.printComment("start of epilogue")

        for i in range(len(Riscv.CalleeSaved)):
            # 恢复callee_saved寄存器
            if Riscv.CalleeSaved[i].isUsed():
                self.printer.printInstr(
                    Riscv.NativeLoadWord(Riscv.CalleeSaved[i], Riscv.SP, 4 * i)
                )

        self.printer.printInstr(
            Riscv.NativeLoadWord(Riscv.FP, Riscv.SP, 4 * len(Riscv.CalleeSaved) + 4)
        )

        self.printer.printInstr(
            Riscv.NativeLoadWord(Riscv.RA, Riscv.SP, 4 * len(Riscv.CalleeSaved))
        )

        self.printer.printInstr(Riscv.SPAdd(self.nextLocalOffset))
        self.printer.printComment("end of epilogue")
        self.printer.println("")
        self.printer.printInstr(Riscv.NativeReturn())
        self.printer.println("")
