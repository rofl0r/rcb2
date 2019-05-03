#!/usr/bin/python2

import sys, os, subprocess, glob, collections, getopt, re
import multiprocessing as mu, Queue, time
from multiprocessing.managers import BaseManager, DictProxy

class JobPool():
	def proc_wrapper(self):
		while 1:
			job = self.getjob()
			if job is None: break
			try:
				if self.func(self, job, self.args):
					self.donejob()
				else:
					break
			except KeyboardInterrupt:
				break

	def start(self):
		for x in xrange(self.nprocs):
			p = mu.Process(target=self.proc_wrapper, args=())
			p.start()
			self.procs.append(p)

	def __init__(self, nprocs, func, args=None):
		self.nprocs = nprocs
		self.func = func
		self.args = args
		self.procs = []
		self.jobqueue = mu.Queue()

		self.jobs_count_lock = mu.Lock()
		self.jobs_total = mu.Value('i', 0, lock=False) #, lock=jobs_count_lock)
		self.jobs_done = mu.Value('i', 0, lock=False) #, lock=jobs_count_lock)

		self.want_quit = mu.Value('i', 0)

	def addjob(self, job):
		q = self.jobqueue
		q.put(job)
		self.jobs_count_lock.acquire()
		self.jobs_total.value += 1
		self.jobs_count_lock.release()
	def getjob(self):
		while 1:
			if self.finished() or self.want_quit.value > 0: return None
			try:
				res = self.jobqueue.get_nowait()
				return res
			except Queue.Empty:
				time.sleep(0.0001)
			except KeyboardInterrupt:
				return None
	def donejob(self):
		self.jobs_count_lock.acquire()
		self.jobs_done.value += 1
		self.jobs_count_lock.release()

	def finished(self):
		#print "%d %d"%(self.jobs_total.value,  self.jobs_done.value)
		result = False
		self.jobs_count_lock.acquire()
		if self.jobs_done.value > 0 and self.jobs_total.value == self.jobs_done.value: result = True
		self.jobs_count_lock.release()
		return result

	def step(self):
		if self.finished(): return False
		time.sleep(0.0001)
		return True
	def terminate(self):
		self.want_quit.value = 1
		time.sleep(0.0001)
		for p in self.procs:
			if p.is_alive(): p.terminate()
		for p in self.procs: p.join()
		self.procs = None

def procfunc(pool, job, args):
	G = args
	scanfile(G, dirname(abspath(job)), basename(job) )
	return True

class ODManager(BaseManager): pass
ODManager.register('OrderedDict', collections.OrderedDict, DictProxy)
ODManager.register('Dict', dict, DictProxy)
verbose = False
use_color = True
nm = os.environ['NM'] if 'NM' in os.environ else 'nm'

class StateManager():
	def __init__(self):
		m = ODManager()
		m.start()
		self.m = m
		self.flags_dict = m.Dict()
		self.cdeps = m.Dict()
		self.cc = 'cc'
		self.cpp = 'cc -E'
		self.setup_env()
		try:
			nproc = mu.cpu_count()
		except NotImplementedError:
			nproc = 1
		self.pool = JobPool(nproc, procfunc, self)

	def get_flags(self, name):
		dic = self.flags_dict[name]
		s = ''
		for v in dic.keys():
			s += v + ' '
		return s

	def add_cdep(self, dep):
		dic = self.cdeps
		if dep in dic: return False
		dic[dep] = True
		self.cdeps = dic
		self.pool.addjob(dep)
		return True

	def set_flags(self, name, flag):
		dic = self.flags_dict[name]
		dic[flag] = True
		self.flags_dict[name] = dic

	def set_flags_internal(self, name, flag):
		self.set_flags(name, flag)
		self.set_flags('internal_' + name, flag)

	def init_flags(self, name):
		self.flags_dict[name] = self.m.OrderedDict()

	def setup_env(self):
		for f in ['cflags', 'cppflags', 'ldflags', 'libs']:
			self.init_flags(f)
			bigf = f.upper()
			if bigf in os.environ: self.set_flags(f, os.environ[bigf])
			self.init_flags('internal_' + f)
		if 'CC' in os.environ: self.cc = os.environ['CC']
		if 'CPP' in os.environ:	self.cpp = os.environ['CPP']
		else: self.cpp = "%s -E" % self.cc

def abspath(path):
	return os.path.abspath(path)

def basename(path):
	return os.path.basename(path)

def dirname(path):
	return os.path.dirname(path)

def append_trailing_directory_slash(path):
	if os.path.isdir(path) and path[-1:] != '/': return path + '/'
	return path

def make_relative(basepath, relpath):
	if basepath[0] != '/' or relpath[0] != '/':
		die("error: both paths must start with / (got %s,%s)"%(basepath, relpath))
	basepath = append_trailing_directory_slash(basepath)
	relpath = append_trailing_directory_slash(relpath)
	l = 0
	mn = min(len(basepath), len(relpath))
	while l < mn and basepath[l] == relpath[l]:
		l += 1
	if l != 0:
		if l < mn and basepath[l] == "/": l -= 1
		while l == len(basepath) or basepath[l] != "/": l -= 1
	if relpath[l] == "/": l += 1
	res = relpath[l:]
	l2 = l
	sl = 0
	while l2 < len(basepath):
		if basepath[l2] == "/": sl += 1
		l2 += 1
	i = 0
	while i < sl:
		res = "../" + res
		i += 1
	return res

def printc(color, text, file=sys.stdout):
	if not use_color:
		sys.stdout.write(text)
		return
	cols = {
		"default": 98,
		"white" : 97,
		"cyan" : 96,
		"magenta" : 95,
		"blue" : 94,
		"yellow" : 93,
		"green" : 92,
		"red" : 91,
		"gray" : 90,
		"end" : 0
	}
	colstr = "\033[%dm"
	file.write( "%s%s%s" % (colstr%cols[color], text, colstr%cols['end']) )

def v_printc(color, text, file=sys.stdout):
	if verbose: printc(color, text, file)

def die(msg):
	printc('red', msg, file=sys.stderr)
	sys.exit(1)

def shellcmd(cmd):
	proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	out, err = proc.communicate()
	ec = proc.returncode
	return ec, out, err

def compile(cmdline):
	printc ("magenta", "[CC] " + cmdline + "\n");
	ec, out, err = shellcmd(cmdline)
	sys.stdout.write(out)
	if ec:
		printc("red", "ERROR: compiler exit status %d\n"%ec, sys.stderr)
		lines = err.split('\n')
		for line in lines:
			col = "default"
			if 'error:' in line or "undefined reference" in line: col = "red"
			printc(col, line + '\n', sys.stderr)
		sys.exit(ec)
	else: sys.stderr.write(err)
	return out

def preprocess(G, file):
	cmdline = "%s %s %s %s" % (G.cpp, G.get_flags('cflags'), G.get_flags('cppflags'), file)
	printc ("default", "[CPP] " + cmdline + "\n");
	ec, out, err = shellcmd(cmdline  + " | grep '^#'")
	if ec: die("ERROR %d: %s"%(ec, err))
	return out

def strip_file_ext(fn):
	return fn[:fn.find('.')]

def strip_quotes(s):
	return s[1:-1]

class Tag(object):
	def __init__(self, type, vals):
		self.type = type
		self.vals = vals
		for i in xrange(len(self.vals)):
			if len(vals[i]) >= 2 and vals[i][0] == '"':
				vals[i] = strip_quotes(vals[i])
			else:
				die("syntax error: rcb values need to be enclosed in double quotes")

def parse_tag(line):
	if len(line) >= 15 and line.startswith('#pragma RcB2 '):
		rest = line[13:]
		vals = split_tokens(rest)
		return Tag(vals[0], vals[1:])
	return None

#split_tokens("int main(int foo(aaa(bbb, ccc);") ->
#['int', 'main', '(', 'int', 'foo', '(', 'aaa', '(', 'bbb', ',', 'ccc', ')', ';']
def split_tokens(x):
	b = []
	i = 0
	start = 0
	in_str = False
	while i < len(x):
		if not in_str:
			if x[i] in " \t\n":
				if i > start:
					b.append(x[start:i])
				start = i+1
			if x[i] in "(),={}*":
				token = x[i]
				if i > start:
					b.append(x[start:i])
				start = i+1
				b.append(token)

		if x[i] in '"':
			if i > 0 and x[i-1] == '\\':
				pass
			else:
				in_str = not in_str

		i += 1
	if i > start:
		b.append(x[start:i])
	return b

def isnumeric(s):
	for x in s:
		if not x in "0123456789": return False
	return True

def scanfile(G, path, file):
	self = "%s/%s"%(path, file)
	v_printc ("default", "scanfile: %s\n" % self)
	pp = preprocess(G, self)
	curr_cpp_file = ''
	for line in pp.split('\n'):
		if len(line) >= 2 and line[0] == '#' and line[1] == ' ':
			tokens = split_tokens(line[2:])
			if len(tokens) > 1 and isnumeric(tokens[0]) and tokens[1][0] == '"':
				curr_cpp_file = strip_quotes(tokens[1])
				continue
		tag = parse_tag(line)
		if tag is None: continue
		if tag.type == 'DEP':
			for dep in tag.vals:
				dest = "%s/%s" % (dirname(curr_cpp_file), dep)
				v_printc ("default", "found RcB2 DEP %s -> %s\n"%(self, dest))
				files = glob.glob(dest)
				for f in files:
					G.add_cdep(abspath(f))
		elif tag.type == 'LINK':
			v_printc ("default", "found RcB2 LINK %s in %s\n"%(repr(tag.vals), curr_cpp_file))
			for dep in tag.vals:
				G.set_flags_internal('libs', dep)
		elif tag.type == 'LDFLAGS':
			v_printc ("default", "found RcB2 LDFLAGS %s in %s\n"%(repr(tag.vals), curr_cpp_file))
			for dep in tag.vals:
				G.set_flags_internal('ldflags', dep)
		elif tag.type == 'CFLAGS':
			v_printc ("default", "found RcB2 CFLAGS %s in %s\n"%(repr(tag.vals), curr_cpp_file))
			for dep in tag.vals:
				G.set_flags_internal('cflags', dep)
		elif tag.type == 'CPPFLAGS':
			v_printc ("default", "found RcB2 CPPFLAGS %s in %s\n"%(repr(tag.vals), curr_cpp_file))
			for dep in tag.vals:
				G.set_flags_internal('cppflags', dep)
		else:
			printc ("yellow", "warning: unknown tag %s found in %s\n"%(tag.type, curr_cpp_file))

def use_preset(G, name):
	base_cflags = '-Wa,--noexecstack'
	base_ldflags= '-Wl,-z,relro,-z,now -Wl,-z,text'
	presets={
		'debug':('-g3 -O0',''),
		'test':('-g0 -O0',''),
		'size':('-Os -ffunction-sections -fdata-sections -fno-unwind-tables -fno-asynchronous-unwind-tables -fomit-frame-pointer','-Wl,--gc-sections -s'),
		'whopr':('-Os -flto -fwhole-program -fno-unwind-tables -fno-asynchronous-unwind-tables -fomit-frame-pointer','-flto -s'),
	}
	G.set_flags('cflags',  base_cflags)
	G.set_flags('ldflags', base_ldflags)
	if name not in presets:
		printc("yellow", "warning: preset %s not found\n"%name)
	else:
		G.set_flags('cflags',  presets[name][0])
		G.set_flags('ldflags', presets[name][1])

def rcb_scan(G, mainfile):
	printc ("blue",  "[RcB2] scanning deps...\n")

	G.add_cdep(abspath(mainfile))

	G.pool.start()

	while 1:
		try:
			if not G.pool.step(): break
		except KeyboardInterrupt():
			break

	G.pool.terminate()

	filelist = []
	basedir = dirname(abspath(mainfile))
	for dep in G.cdeps.keys():
		filelist.append(make_relative(basedir, dep))
	return filelist

# T: function defined
# U: undefined sym
# C: uninit. data sym defined in obj
# B: uninit. data sym defined in binary
# D: init. data sym defined in obj/binary
# R: r/o (const) data sym defined in obj/binary
def get_object_syms(obj, symtypes='T'):
	ec, out, err = shellcmd('%s %s'%(nm, obj))
	if ec:
		sys.stderr.write(err)
		return None
	rex = re.compile('([0-9a-f]+|[ ]+) ([%s]) (.*)'%symtypes)
	syms = {}
	for letter in symtypes:
		syms[letter] = {}
	lines = out.split('\n')
	for line in lines:
		m = rex.match(line)
		if not m: continue
		addr, letter, sym = m.groups(0)
		syms[letter][sym] = int(addr, 16) if letter != 'U' else -1
	return syms

def fold_dicts(dick, wantedkeys):
	ret = {}
	for x in wantedkeys:
		if not x in dick: continue
		for y in dick[x].keys(): ret[y] = dick[x][y]
	return ret

def find_sym(symname, objsyms):
	for obj in objsyms.keys():
		if 'used' in objsyms[obj]: continue
		if 'got' in objsyms[obj] and symname in objsyms[obj]['got']:
			objsyms[obj]['used'] = True
			for needed in objsyms[obj]['needed']:
				find_sym(needed, objsyms)

# this requires that the objs are built with debug syms on
# and optimally no optimization
def get_used_object_files(objfilelist):
	objsyms = dict()
	for obj in objfilelist:
		syms = get_object_syms(obj, 'UTCDR')
		if syms is None: return None
		osyms = {}
		osyms['needed'] = fold_dicts(syms, 'U')
		osyms['got'] = fold_dicts(syms, 'TCDR')
		objsyms[obj] = osyms
	find_sym('main', objsyms)
	used = []
	for obj in objfilelist:
		if 'used' in objsyms[obj]: used.append(obj)
	return used

def optimize_dependencies(filelist):
	objfl = map(lambda x : re.sub(r"\.c$", ".o", x), filelist)
	filelist = get_used_object_files(objfl)
	if filelist is None: return None
	return map(lambda x : re.sub(r"\.o$", ".c", x), filelist)

def pure_compile(G, bin, filelist):
	cmdline = "%s %s %s " % (G.cc, G.get_flags('cppflags'), G.get_flags('cflags'))

	for dep in filelist:
		cmdline += "%s "%dep

	cmdline += "-o %s %s" % (bin, G.get_flags('ldflags'))
	out = compile(cmdline)
	if len(out): sys.stdout.write(out)
	return 0

def usage():
	print "%s [options] file.c"%sys.argv[0]
	print "builds file.c"
	print "options:"
	print "-v/--verbose: verbose output"
	print "-e/--extension EXT: file extension EXT for the generated binary"
	print "-j N: build with N parallel jobs"
	print "-f/--force: forces rescan and new Makefile written"
	print "-p/--preset: use CFLAGS preset [debug/size/test]"
	print "--static: add --static to LDFLAGS"
	print "--nocolor: do not use colors"
	print "--pure: do not use Makefiles"
	print
	print "influential environment vars:"
	print "CC, CPP, CFLAGS, CPPFLAGS, LDFLAGS, NM"
	print "if crosscompiling, CC and NM need to be prefixed with the target triplet"
	sys.exit(1)

def main():
	global verbose
	global use_color
	nprocs = 1
	ext = ''
	use_force, pure = False, False

	G = StateManager()

	optlist, args = getopt.getopt(sys.argv[1:], ":j:e:p:fv", [
		'extension=', 'preset=', 'static',
		'verbose', 'nocolor', 'force', 'pure', 'help'
	])
	for a,b in optlist:
		if a == '-v' or a == '--verbose': verbose = True
		if a == '--nocolor': use_color = False
		if a == '-p' or a == '--preset': use_preset(G, b)
		if a == '-f' or a == '--force': use_force = True
		if a == '--help': usage()
		if a == '--pure': pure = True
		if a == '--static': G.set_flags('ldflags', '--static')
		if a == '-j' : nprocs = int(b)

	mainfile = args.pop(0)
	if not len(args): args.append('all')

	cnd = strip_file_ext(basename(mainfile))
	bin = cnd + ext
	makefile = 'rcb.%s.mak'% cnd

	if not os.path.exists(makefile) or use_force or pure:

		filelist = rcb_scan(G, mainfile)
		if pure: return pure_compile(G, bin, filelist)

		write_makefile(G, makefile, bin, filelist)
		run_makefile(G, makefile, ["clean"], 1, "") and \
		run_makefile(G, makefile, ["all"], nprocs, "-O0 -g")
		filelist = optimize_dependencies(filelist)
		if filelist is None: sys.exit(1)
		run_makefile(G, makefile, ["clean"], 1, "") and \
		write_makefile(G, makefile, bin, filelist)

	run_makefile(G, makefile, args, nprocs)

def sys_cmd(cmd):
	print cmd
	return not os.system(cmd)

def run_makefile(G, makefile, args, nprocs, cflags=None, cppflags=None, ldflags=None):
	#ec, out, err = shellcmd(cmdline)
	my_cflags = cflags if cflags else G.get_flags('cflags')
	my_cppflags = cppflags if cppflags else G.get_flags('cppflags')
	my_ldflags = ldflags if ldflags else G.get_flags('ldflags')
	return sys_cmd("make -f %s -j %d CFLAGS=\"%s\" CPPFLAGS=\"%s\" LDFLAGS=\"%s\" %s" \
		% (makefile, nprocs, my_cflags, my_cppflags, my_ldflags, ' '.join(args)))


def write_makefile(G, makefile, bin, files):
	make_template = """#Makefile autogenerated by RcB2
prefix = /usr/local
bindir = $(prefix)/bin

PROG = @PROG@
SRCS = @SRCS@

LIBS = @LIBS@

CFLAGS = @CFLAGS@
CPPFLAGS = @CPPFLAGS@
LDFLAGS = @LDFLAGS@

OBJS = $(SRCS:.c=.o)

MAKEFILE := $(firstword $(MAKEFILE_LIST))

-include config.mak

all: $(PROG)

clean:
	rm -f $(PROG)
	rm -f $(OBJS)

rebuild:
	$(MAKE) -f $(MAKEFILE) clean && $(MAKE) -f $(MAKEFILE) all

install: $(PROG)
	install -d $(DESTDIR)/$(bindir)
	install -D -m 755 $(PROG) $(DESTDIR)/$(bindir)/

src: $(SRCS)
	$(CC) $(CPPFLAGS) $(CFLAGS) $ -o $(PROG) $^ $(LDFLAGS) $(LIBS)

%.o: %.c
	$(CC) $(CPPFLAGS) $(CFLAGS) -c -o $@ $<

$(PROG): $(OBJS)
	$(CC) $(CFLAGS) $(LDFLAGS) $(OBJS) $(LIBS) -o $@

.PHONY: all clean rebuild install src
"""
	make_template = make_template.replace('@PROG@', bin)
	make_template = make_template.replace('@SRCS@', " \\\n\t".join(files))
	make_template = make_template.replace('@LIBS@', G.get_flags('internal_libs'))
	make_template = make_template.replace('@LDFLAGS@', G.get_flags('internal_ldflags'))
	make_template = make_template.replace('@CFLAGS@', G.get_flags('internal_cflags'))
	make_template = make_template.replace('@CPPFLAGS@', G.get_flags('internal_cppflags'))

	with open(makefile, "w") as h:
		h.write(make_template)

if __name__ == '__main__':
	main()
