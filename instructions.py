from types import CodeType, FunctionType
from labels import makeLabel
from debug import *
from keywords import *

class Instruction:
	def __init__(self, name=''):
		self.argcount = 0
		self.kwonlyargcount = 0
		self.nlocals = 0
		self.stacksize = 0
		self.flags = 0
		self.code = []
		self.consts = set([None])
		self.names = set(['DUMMY'])
		self.varnames = set()
		self.filename = ''
		self.name = name
		self.firstlineno = 0
		self.lnotab = b''
		self.freevars = ()
		self.cellvars = ()

	def makeCodeObj(self):
		"Converts Instruction to code object"
		self.convertSets()
		self.getIndices()
		self.convertLabels()

		self.code += [RETURN_VALUE]

		codeObject = CodeType(self.argcount,
			self.kwonlyargcount, self.nlocals,
			self.stacksize, self.flags, 
			bytes(self.code),self.consts, 
			self.names, self.varnames, 
			self.filename, self.name, 
			self.firstlineno, self.lnotab, 
			self.freevars, self.cellvars)

		return codeObject


	def adjoin(instr):
		pass

	def convertSets(self):
		"Converts sets to tuples"
		# is there a better way to do this?
		self.consts = tuple(self.consts)
		self.names = tuple(self.names)
		self.varnames = tuple(self.varnames)
		self.freevars = tuple(self.freevars)
		self.cellvars = tuple(self.cellvars)

	def getIndices(self):
		"Executes locator-lambdas"
		result, code = [], self.code

		i, length = 0, len(code)
		while i < length:
			ith = code[i]
			result.append(ith)
			j = i + 1
			if j == length:
				break
			jth = code[j]
			if (type(jth) != int): 
				# jth is a locator
				# ith is an opcode calling a tuple
				if ith in CONSTS:
					result.append(jth(self.consts))
					i += 1
				if ith in NAMES:
					result.append(jth(self.names))
					i += 1
				if ith in VARNAMES:
					result.append(jth(self.varnames))
					i += 1
				# i += 1
			i += 1

		''' side effects? '''
		# return result
		self.code = result

	def convertLabels(self):
		# does this function have to be destructive?
		code = self.code
		i, length = 0, len(code)
		while i < length:
			ith = code[i]
			j = i + 1
			if j == length:
				break
			jth = code[j]
			if ith in JUMPTARGET and type(jth) != int:
				index = jth(self.code)
				code[j] = index
				del(code[index])
			i, length = i + 1, len(code)

	def addPop(self):
		"adds POP_TOP to end of code -- for use in compSeq"
		self.code.append(POP_TOP)


def makeFunction(codeObject):
	return FunctionType(codeObject, globals())


class numInstr(Instruction):
	def __init__(self, lisp, num):
		super(numInstr, self).__init__(lisp)
		self.stacksize = 1
		self.consts = (num,)

		def numIndex(consts):
			nonlocal num
			return consts.index(num)

		self.code = [LOAD_CONST, numIndex, 0]


class varInstr(Instruction):
	def __init__(self, lisp, var):
		super(varInstr, self).__init__(lisp)
		self.stacksize = 1

		def varIndex(names):
			nonlocal var
			if var in names:
				return names.index(var)
			else:
				print('%s undefined!' % var)
				return names.index('DUMMY')

		# 124 : LOAD_FAST
		# 116 : LOAD_GLOBAL
		# 101 : LOAD_NAME
		self.code = [LOAD_GLOBAL, varIndex, 0]


class defInstr(Instruction):
	def __init__(self, lisp, var, valInstr):
		super(defInstr, self).__init__(lisp)
		self.consts = valInstr.consts
		self.freevars = valInstr.freevars
		self.cellvars = valInstr.cellvars

		self.stacksize = 2
		self.names = valInstr.names

		# names global, varnames local?
		self.names.add(var)

		def varIndex(names):
			nonlocal var
			return names.index(var)

		# 4 : DUP_TOP (to return val)
		# 125 : STORE_FAST (local?)
		# 97 : STORE_GLOBAL
		# 90 : STORE_NAME
		defCode = [DUP_TOP, 
				STORE_GLOBAL, varIndex, 0]
		self.code = valInstr.code + defCode

class ifInstr(Instruction):
	# test, then, othw are Instructions
	def __init__(self, lisp, test, then, othw):
		super(ifInstr, self).__init__(lisp)

		self.stacksize = max(test.stacksize,
			then.stacksize, othw.stacksize)

		self.consts.update(test.consts, 
			then.consts, othw.consts)
		self.names.update(test.names, 
			then.names, othw.names)
		self.varnames.update(test.varnames, 
			then.varnames, othw.varnames)

		# nlocals, etc

		'''
		<test.code>
		POP_JUMP_IF_FALSE <index(othw.code)>
		<then.code>
		<othw.code>
		'''
		falseBranch = makeLabel()
		def falseBranchIndex(code):
			nonlocal falseBranch
			return code.index(falseBranch)

		self.code = (test.code + 
			[POP_JUMP_IF_FALSE, falseBranchIndex, 0] +
			then.code + 
			[JUMP_FORWARD, len(othw.code), 0] + 
			[falseBranch] + 
			othw.code)

class lambdaInstr(Instruction):
	def __init__(self, lisp, params, bodyInstr):
		super(lambdaInstr, self).__init__(lisp)

		# ensure params are in bodyInstr varnames
		# (is this necessary?)
		bodyInstr.varnames.update(params)

		# ensure bodyInstr has the right argcount
		argcount = len(params)
		# bodyInstr.argcount = argcount
		# bodyInstr.nlocals = argcount #???

		self.argcount = argcount
		self.nlocals = argcount

		lambdaName = 'lambda: <%s>' % bodyInstr.name

		bodyCode = bodyInstr.makeCodeObj()

		self.consts.update((bodyCode, lambdaName))

		def lambdaIndex(consts):
			return consts.index(lambdaName)

		def bodyCodeIndex(consts):
			nonlocal bodyCode
			return consts.index(bodyCode)

		self.code = [
			LOAD_CONST, bodyCodeIndex, 0,
			LOAD_CONST, lambdaIndex, 0, 
			MAKE_FUNCTION, 0, 0
		]

		self.stacksize = 2

class primInstr(Instruction):
	"func is string, args are Instructions"
	def __init__(self, lisp, func, arg1, arg2):
		super(primInstr, self).__init__(lisp)

		self.consts.update(arg1.consts, arg2.consts)
		self.names.update(arg1.names, arg2.names)
		self.varnames.update(arg1.varnames, arg2.varnames)

		if func in arithFuncs:
			funcOpCode = [getOpCode(func)]
		if func in cmp_op:
			index = getCompIndex(func)
			funcOpCode = [COMPARE_OP, index, 0]

		self.code = arg1.code + arg2.code + funcOpCode

		self.stacksize = max(arg1.stacksize, arg2.stacksize)


class funcInstr(Instruction):
	"func is Instruction, args is list of Instructions"
	def __init__(self, lisp, func, args):	
		super(funcInstr, self).__init__(lisp)

		# not self.argcount???
		argcount = len(args)

		self.consts.update(func.consts)
		self.names.update(func.names)
		self.varnames.update(func.varnames)

		while args:
			[arg, *args] = args

			self.consts.update(arg.consts)
			self.names.update(arg.names)
			self.varnames.update(arg.varnames)

			self.code += arg.code
			self.stacksize += arg.stacksize # ???

		callCode = [CALL_FUNCTION, argcount, 0]

		self.code = func.code + self.code + callCode



