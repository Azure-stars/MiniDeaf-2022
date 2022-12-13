import random

from backend.dataflow.basicblock import BasicBlock, BlockKind
from backend.dataflow.cfg import CFG
from backend.dataflow.loc import Loc
from backend.reg.regalloc import RegAlloc
from backend.riscv.riscvasmemitter import RiscvAsmEmitter
from backend.subroutineemitter import SubroutineEmitter
from backend.subroutineinfo import SubroutineInfo
from utils.riscv import Riscv
from utils.tac.holeinstr import HoleInstr
from utils.tac.reg import Reg
from utils.tac.temp import Temp
from utils.tac.tacop import InstrKind
"""
BruteRegAlloc: one kind of RegAlloc

bindings: map from temp.index to Reg

we don't need to take care of GlobalTemp here
because we can remove all the GlobalTemp in selectInstr process

1. accept：根据每个函数的 CFG 进行寄存器分配，寄存器分配结束后生成相应汇编代码
2. bind：将一个 Temp 与寄存器绑定
3. unbind：将一个 Temp 与相应寄存器解绑定
4. localAlloc：根据数据流对一个 BasicBlock 内的指令进行寄存器分配
5. allocForLoc：每一条指令进行寄存器分配
6. allocRegFor：根据数据流决定为当前 Temp 分配哪一个寄存器
"""

class BruteRegAlloc(RegAlloc):
    def __init__(self, emitter: RiscvAsmEmitter) -> None:
        super().__init__(emitter)
        self.bindings = {}
        # self.argtemp = {}
        self.numargs = 0
        # 记录这个函数自身的参数数目
        self.allarg = []
        # 记录当前函数调用的子函数所使用的参数数目

        self.first_arg = {}
        # 记录每一个虚拟寄存器对应的实际寄存器

        self.caller_temp = {}
        # caller_saved寄存器对应的虚拟寄存器

        for reg in emitter.allocatableRegs:
            reg.used = False
            # used代表是否曾经被使用过
            # 一个寄存器若被used，里面一定有值

    def accept(self, graph: CFG, info: SubroutineInfo, numargs: int) -> None:
        self.numargs = numargs
        subEmitter = self.emitter.emitSubroutine(info)
        # 也许我该在这里开
        for index in range(min(8, numargs)):
            # 先存进去保平安
            self.bind(Temp(index), Riscv.ArgRegs[index])
            subEmitter.emitStoreToStack(Riscv.ArgRegs[index])
        for (index,bb) in enumerate(graph.iterator()) :
            # you need to think more here
            # maybe we don't need to alloc regs for all the basic blocks
            if bb.label is not None:
                subEmitter.emitLabel(bb.label)
            if graph.judge(index) == True:
                self.localAlloc(bb, subEmitter)            
        subEmitter.emitEnd()
        # 生成汇编代码

    def bind(self, temp: Temp, reg: Reg):
        reg.used = True
        self.bindings[temp.index] = reg
        reg.occupied = True
        reg.temp = temp

    def unbind(self, temp: Temp):
        if temp.index in self.bindings:
            self.bindings[temp.index].occupied = False
            self.bindings.pop(temp.index)

    def localAlloc(self, bb: BasicBlock, subEmitter: SubroutineEmitter):
        self.bindings.clear()
        for reg in self.emitter.allocatableRegs:
            reg.occupied = False

        # in step9, you may need to think about how to store callersave regs here
        for loc in bb.allSeq():
            # 为每一个riscv语句分配寄存器
            # 你说得对，但是我首先要生成riscv语句
            # 所以我可以操作一手
            # 如何去保存caller_saved
            # 似乎无法知道子函数如何搞了我的caller_saved
            # 所以我直接暴力存进去，非常地美妙、
            subEmitter.emitComment(str(loc.instr))
            self.allocForLoc(loc, subEmitter)

        for tempindex in bb.liveOut:
            # 对于基本块中出口活跃的寄存器
            if tempindex in self.bindings:
                # 若它当前已有分配寄存器，则把这个寄存器存储在栈帧上，把寄存器留出来给其他变量
                subEmitter.emitStoreToStack(self.bindings.get(tempindex))

        if (not bb.isEmpty()) and (bb.kind is not BlockKind.CONTINUOUS):
            # 跳转离开这个基本块，则最后一个tac语句未被分析，需要额外为这一句分配寄存器
            self.allocForLoc(bb.locs[len(bb.locs) - 1], subEmitter)

    def allocForLoc(self, loc: Loc, subEmitter: SubroutineEmitter):
        instr = loc.instr
        srcRegs: list[Reg] = []
        dstRegs: list[Reg] = []

        for i in range(len(instr.srcs)):
            # 为源虚拟寄存器分配实际寄存器
            temp = instr.srcs[i]
            if isinstance(temp, Reg):
                # 已经是真实寄存器
                srcRegs.append(temp)
            else:
                srcRegs.append(self.allocRegFor(temp, True, loc.liveIn, subEmitter))
        
        for i in range(len(instr.dsts)):
            temp = instr.dsts[i]
            if isinstance(temp, Reg):
                dstRegs.append(temp)
            else:
                # 目的寄存器还未被读取，因此暂时不从栈帧上获取
                dstRegs.append(self.allocRegFor(temp, False, loc.liveIn, subEmitter))
        if instr.kind == InstrKind.CALL:
            # 提前存入caller_saved
            # 传参由params进行
            # subEmitter.emitStoreCallerSaved()
            
            for reg in Riscv.CallerSaved:
                # 存入栈帧之后就可以解绑定
                if reg in Riscv.ArgRegs[:min(8,len(self.allarg))]:
                    # 若已经被初始化过，则不需要修改
                    continue 
                if reg.occupied:
                    # 首先你得有值
                    self.caller_temp[reg] = reg.temp
                    subEmitter.emitStoreToStack(reg)
                    self.unbind(reg.temp)

            if len(self.allarg) > 8:
                for (index, temp) in enumerate(reversed(self.allarg[8:])) :
                    # 从右往左插入
                    # 新开栈帧
                    subEmitter.emitStoreParam(temp, index)
            subEmitter.emitNative(instr.toNative(dstRegs, srcRegs))

            if len(self.allarg) > 8:
                subEmitter.emitPopParam(4 * (len(self.allarg) - 8))
                # 恢复栈帧

            self.allarg = []

            for reg, temp in self.caller_temp.items():
                # 包括恢复参数寄存器
                if isinstance(reg, Reg) and isinstance(temp, Temp):
                    if reg == Riscv.A0:
                        continue
                    # 返回值不变
                    if reg.occupied:
                        self.unbind(reg.temp)
                    self.bind(temp, reg)
                    subEmitter.emitLoadFromStack(reg, temp)

            for reg in Riscv.CallerSaved:
                if reg.occupied:
                    self.unbind(reg.temp)
                # 可能在其他地方被用了

                    # 重新恢复caller_saved寄存器
            self.caller_temp = {}
                # 直接设置这个寄存器为空，因为真正的值已经存在了栈帧上面
        elif instr.kind == InstrKind.PARAM:
            # 首先检查是否有寄存器可以放
            # 如何检查当前到了哪个寄存器
            # 记得检查当前即将放入的寄存器是否有东西
            # 如果有东西就记得放到栈帧上
            assert len(instr.srcs) == 1
            now_len = len(self.allarg)
            if now_len < 8:
                reg = Riscv.ArgRegs[now_len]
                if reg.occupied:
                    # 首先你得有值
                    self.caller_temp[reg] = reg.temp
                    subEmitter.emitStoreToStack(reg)
                    self.unbind(reg.temp)
                subEmitter.emitMoveReg(reg, srcRegs[0])
            self.allarg.append(temp)
            # 先拿个列表存起来
            # 之后倒着插进栈帧里面
            # 开栈帧
        elif instr.kind == InstrKind.ALLOC:
            subEmitter.AllocArrayInStack(dstRegs[0], instr.dsts[0], instr.size) 
        else:
            subEmitter.emitNative(instr.toNative(dstRegs, srcRegs))
        # 把tac代码转化为riscv代码
        # 是否要从栈帧上恢复原有的值呢

    def allocRegFor(
        self, temp: Temp, isRead: bool, live: set[int], subEmitter: SubroutineEmitter
    ):
        # 为虚拟寄存器分配实际物理寄存器
        if temp.index in self.bindings:
            return self.bindings[temp.index]

        for reg in self.emitter.allocatableRegs:
            # 这个列表代表可供分配的寄存器，但不一定真的可以分配
            # 寻找空闲寄存器或者是已经不活跃的寄存器
            # 注意可供使用的寄存器里面竟然没有参数寄存器
            if (not reg.occupied) or (not reg.temp.index in live):
                subEmitter.emitComment(
                    "  allocate {} to {}  (read: {}):".format(
                        str(temp), str(reg), str(isRead)
                    )
                )
                # if reg.occupied == False:
                #     self.first_reg[temp] = reg
                # 记录每一个虚拟寄存器第一  个使用的实际物理寄存器   
                if isRead:
                    # 若不是物理寄存器，然后又是源，说明赋过值，所以你一定在栈帧上么kora
                    subEmitter.emitLoadFromStack(reg, temp)

                if reg.occupied:
                    # 若之前绑定过其他变量，则解绑定
                    self.unbind(reg.temp)
                # 绑定到当前的变量
                self.bind(temp, reg)
                return reg

        reg = self.emitter.allocatableRegs[
            random.randint(0, len(self.emitter.allocatableRegs) - 1)
        ]
        # 若没有空闲的寄存器，则随机选一个寄存器spill到栈帧上
        subEmitter.emitStoreToStack(reg)
        subEmitter.emitComment("  spill {} ({})".format(str(reg), str(reg.temp)))
        self.unbind(reg.temp)
        self.bind(temp, reg)
        subEmitter.emitComment(
            "  allocate {} to {} (read: {})".format(str(temp), str(reg), str(isRead))
        )
        # 然后重新分配
        if isRead:
            subEmitter.emitLoadFromStack(reg, temp)
        return reg
