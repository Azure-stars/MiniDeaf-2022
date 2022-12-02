"""
Module that defines a parser using `ply.yacc`.
Add your own parser rules on demand, which can be accomplished by:

1. Define a global function whose name starts with "p_".
2. Write the corresponding grammar rule(s) in its docstring.
3. Complete the function body, which is actually a syntax base translation process.
    We're using this technique to build up the AST.

Refer to https://www.dabeaz.com/ply/ply.html for more details.
"""


from ast import Continue
import ply.yacc as yacc

from frontend.ast.tree import *
from frontend.lexer import lex
from utils.error import DecafSyntaxError

tokens = lex.tokens

error_stack = list[DecafSyntaxError]()


def unary(p):
    p[0] = Unary(UnaryOp.backward_search(p[1]), p[2])


def binary(p):
    if p[2] == BinaryOp.Assign.value:
        p[0] = Assignment(p[1], p[3])
        # 赋值语句
    else:
        p[0] = Binary(BinaryOp.backward_search(p[2]), p[1], p[3])
        # 正常的二元语句

def p_empty(p: yacc.YaccProduction):
    """
    empty :
    """
    pass

def p_program_empty(p):
    """
    program : empty
    """
    p[0] = Program()

def p_program(p):
    """
    program : program function
    """
    if p[2] is not NULL:
        p[1].children.append(p[2])
    p[0] = p[1]

def p_type(p):
    """
    type : Int
    """
    p[0] = TInt()

def p_function_statement(p):
    """
    function : type Identifier LParen parameterlist RParen Semi
    """
    p[0] = Function(p[1], p[2], p[4])
    # 这里都是按照范式来规定的下标
    # 是函数的声明
    # function: 传入参数为类型名，函数名，参数列表

def p_function_def(p):
    """
    function : type Identifier LParen parameterlist RParen LBrace block RBrace
    """
    p[0] = Function(p[1], p[2], p[4], p[7])
    # 这里都是按照范式来规定的下标
    # function: 传入参数为类型名，函数名，参数列表，函数体

def p_parameterlist_empty(p):
    """
    parameterlist : empty
    """
    p[0] = ParameterList()

def p_parameter_single(p):
    """
    parameterlist : parameter
    """
    p[0] = ParameterList()
    p[0].children.append(p[1])

def p_parameterlist_multi(p):
    """
    parameterlist : parameterlist Comma parameter
    """
    if p[3] is not NULL:
        p[1].children.append(p[3])
    p[0] = p[1]

def p_parameter(p):
    """
    parameter : type Identifier
    """
    p[0] = Parameter(p[1], p[2])

def p_expressionlist_empty(p):
    """
    expressionlist : empty
    """
    p[0] = ExpressionList()

def p_expressionlist_single(p):
    """
    expressionlist : expression
    """
    p[0] = ExpressionList()
    p[0].children.append(p[1])

def p_expressionlist_multi(p):
    """
    expressionlist : expressionlist Comma expression
    """
    if p[3] is not NULL:
        p[1].children.append(p[3])
    p[0] = p[1]

def p_block(p):
    """
    block : block block_item
    """
    if p[2] is not NULL:
        p[1].children.append(p[2])
    p[0] = p[1]

def p_block_empty(p):
    """
    block : empty
    """
    p[0] = Block()


def p_block_item(p):
    """
    block_item : statement
        | declaration Semi
    """
    p[0] = p[1]


def p_statement(p):
    """
    statement : statement_matched
        | statement_unmatched
    """
    p[0] = p[1]


def p_if_else(p):
    """
    statement_matched : If LParen expression RParen statement_matched Else statement_matched
    statement_unmatched : If LParen expression RParen statement_matched Else statement_unmatched
    """
    p[0] = If(p[3], p[5], p[7])


def p_if(p):
    """
    statement_unmatched : If LParen expression RParen statement
    """
    p[0] = If(p[3], p[5])


def p_while(p):
    """
    statement_matched : While LParen expression RParen statement_matched
    statement_unmatched : While LParen expression RParen statement_unmatched
    """
    p[0] = While(p[3], p[5])

def p_for_full(p):
    """
    statement_matched : For LParen expression Semi expression Semi expression RParen statement_matched
        | For LParen declaration Semi expression Semi expression RParen statement_matched
    statement_unmatched : For LParen expression Semi expression Semi expression RParen statement_unmatched
        | For LParen declaration Semi expression Semi expression RParen statement_unmatched
    """
    p[0] = For(init = p[3], cond = p[5],update= p[7],body = p[9])

def p_for1(p):
    """
    statement_matched : For LParen Semi expression Semi expression RParen statement_matched
    statement_unmatched : For LParen Semi expression Semi expression RParen statement_unmatched
    """
    p[0] = For(cond = p[4], update = p[6], body = p[8])
    # 2 3

def p_for2(p):
    """
    statement_matched : For LParen expression Semi Semi expression RParen statement_matched
        | For LParen declaration Semi Semi expression RParen statement_matched
    statement_unmatched : For LParen expression Semi Semi expression RParen statement_unmatched
        | For LParen declaration Semi Semi expression RParen statement_unmatched
    """
    p[0] = For(init = p[3], update = p[6],body = p[8])
    # 1 3

def p_for3(p):
    """
    statement_matched : For LParen expression Semi expression Semi RParen statement_matched
        | For LParen declaration Semi expression Semi RParen statement_matched
    statement_unmatched : For LParen expression Semi expression Semi RParen statement_unmatched
        | For LParen declaration Semi expression Semi RParen statement_unmatched
    """
    p[0] = For(init= p[3],cond= p[5],body= p[8])
    # 1  2

def p_for4(p):
    """
    statement_matched : For LParen expression Semi Semi RParen statement_matched
        | For LParen declaration Semi Semi RParen statement_matched
    statement_unmatched : For LParen expression Semi Semi RParen statement_unmatched
        | For LParen declaration Semi Semi RParen statement_unmatched
    """
    p[0] = For(init=p[3],body=p[7])
    # 1 

def p_for5(p):
    """
    statement_matched : For LParen Semi expression Semi RParen statement_matched
    statement_unmatched : For LParen Semi expression Semi RParen statement_unmatched
    """
    p[0] = For(cond=p[4], body=p[7])
    # 2 

def p_for6(p):
    """
    statement_matched : For LParen Semi Semi expression RParen statement_matched
    statement_unmatched : For LParen Semi Semi expression RParen statement_unmatched
    """
    p[0] = For(update=p[5], body=p[7])
    # 3

def p_for7(p):
    """
    statement_matched : For LParen Semi Semi RParen statement_matched
    statement_unmatched : For LParen Semi Semi RParen statement_unmatched
    """
    p[0] = For(body = p[6])
    # null

def p_do_while(p):
    """
    statement_matched : Do statement_matched While LParen expression RParen Semi
    statement_unmatched : Do statement_unmatched While LParen expression RParen Semi
    """
    p[0] = DoWhile(p[5], p[2])

def p_return(p):
    """
    statement_matched : Return expression Semi
    """
    p[0] = Return(p[2])
    # return 是 保留语句


def p_expression_statement(p):
    """
    statement_matched : opt_expression Semi
    """
    p[0] = p[1]


def p_block_statement(p):
    """
    statement_matched : LBrace block RBrace
    """
    p[0] = p[2]


def p_break(p):
    """
    statement_matched : Break Semi
    """
    p[0] = Break()

def p_continue(p):
    """
    statement_matched : Continue Semi
    """
    p[0] = Continue()


def p_opt_expression(p):
    """
    opt_expression : expression
    """
    p[0] = p[1]
    # 这里


def p_opt_expression_empty(p):
    """
    opt_expression : empty
    """
    p[0] = NULL


def p_declaration(p):
    """
    declaration : type Identifier
    """
    p[0] = Declaration(p[1], p[2])
    # 声明语句

def p_declaration_init(p):
    """
    declaration : type Identifier Assign expression
    """
    p[0] = Declaration(p[1], p[2], p[4])
    # 定义语句


def p_expression_precedence(p):
    """
    expression : assignment
    assignment : conditional
    conditional : logical_or
    logical_or : logical_and
    logical_and : bit_or
    bit_or : xor
    xor : bit_and
    bit_and : equality
    equality : relational
    relational : additive
    additive : multiplicative
    multiplicative : unary
    unary : postfix
    postfix : primary
    """
    p[0] = p[1]
    # 优先级判断
    # 可以看出这是连续的产生式

def p_postfix(p):
    """
    postfix : Identifier LParen expressionlist RParen
    """
    p[0] = Call(p[1], p[3])
 

def p_unary_expression(p):
    """
    unary : Minus unary
        | BitNot unary
        | Not unary
    """
    unary(p)
    # 现在支持的一元操作为
    # 取负、二级制取反、布尔值取反

def p_binary_expression(p):
    """
    assignment : Identifier Assign expression
    logical_or : logical_or Or logical_and
    logical_and : logical_and And bit_or
    bit_or : bit_or BitOr xor
    xor : xor Xor bit_and
    bit_and : bit_and BitAnd equality
    equality : equality NotEqual relational
        | equality Equal relational
    relational : relational Less additive
        | relational Greater additive
        | relational LessEqual additive
        | relational GreaterEqual additive
    additive : additive Plus multiplicative
        | additive Minus multiplicative
    multiplicative : multiplicative Mul unary
        | multiplicative Div unary
        | multiplicative Mod unary
    """
    binary(p)
    # 二元表达式：定义为  一个左值变量 一个赋值  一个右边的表达式
    # 表达式中定义了   按位与、按位或、异或、取等、加减乘除运算（默认乘除优先级更高）、不等式

def p_conditional_expression(p):
    """
    conditional : logical_or Question expression Colon conditional
    """
    p[0] = ConditionExpression(p[1], p[3], p[5])
    # 三目运算符

def p_int_literal_expression(p):
    """
    primary : Integer
    """
    p[0] = p[1]


def p_identifier_expression(p):
    """
    primary : Identifier
    """
    p[0] = p[1]


def p_brace_expression(p):
    """
    primary : LParen expression RParen
    """
    p[0] = p[2]
    # 括号表达式

def p_error(t):
    """
    A naive (and possibly erroneous) implementation of error recovering.
    """
    if not t:
        error_stack.append(DecafSyntaxError(t, "EOF"))
        return

    inp = t.lexer.lexdata
    error_stack.append(DecafSyntaxError(t, f"\n{inp.splitlines()[t.lineno - 1]}"))

    parser.errok()
    return parser.token()


parser = yacc.yacc(start="program")
parser.error_stack = error_stack  # type: ignore
