#!/usr/bin/python2

import sys, os, subprocess, glob, collections, getopt

# global vars
verbose = False
use_color = True
cc = 'cc'
cpp = 'cc'
cdeps = dict()
flags_dict = dict()
def get_flags(name):
	dic = flags_dict[name]
	s = ''
	for v in dic.keys():
		s += v + ' '
	return s

def set_flags(name, flag):
	dic = flags_dict[name]
	dic[flag] = True

def init_flags(name):
	flags_dict[name] = collections.OrderedDict()

def setup_env():
	for f in ['cflags', 'cppflags', 'ldflags']:
		init_flags(f)
		bigf = f.upper()
		if bigf in os.environ: set_flags(f, os.environ[bigf])
	global cc
	if 'CC' in os.environ: cc = os.environ['CC']
	if 'CPP' in os.environ:	cpp = os.environ['CPP']
	else: cpp = cc

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
		die("error: both path's must start with / (got %s,%s)"%(basepath, relpath))
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

def printc(color, text):
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
	sys.stdout.write( "%s%s%s" % (colstr%cols[color], text, colstr%cols['end']) )

def v_printc(color, text):
	if verbose: printc(color, text)

def die(msg):
	printc('red', msg)
	sys.exit(1)

def shellcmd(cmd):
	proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
	out, err = proc.communicate()
	ec = proc.returncode
	return ec, out, err

def compile(cmdline):
	printc ("magenta", "[CC] " + cmdline + "\n");
	ec, out, err = shellcmd(cmdline)
	if ec: die("ERROR %d: %s"%(ec, err))
	print out
	return out

def preprocess(file):
	global cpp
#	cpp_opts = "-E -CC"
	cpp_opts = "-E"
	cmdline = "%s %s %s %s %s" % (cpp, get_flags('cflags'), get_flags('cppflags'), cpp_opts, file)
	printc ("magenta", "[CPP] " + cmdline + "\n");
	ec, out, err = shellcmd(cmdline)
	if ec: die("ERROR %d: %s"%(ec, err))
	#print out
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

def scanfile(path, file):
	self = "%s/%s"%(path, file)
	if self in cdeps: return
	cdeps[self] = True
	v_printc ("default", "scanfile: %s\n" % self)
	pp = preprocess(self)
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
					scanfile( dirname(abspath(f)), basename(f) )
		elif tag.type == 'LINK' or tag.type == 'LDFLAGS':
			for dep in tag.vals:
				set_flags('ldflags', dep)
		elif tag.type == 'CFLAGS':
			for dep in tag.vals:
				set_flags('cflags', dep)
		elif tag.type == 'CPPFLAGS':
			for dep in tag.vals:
				set_flags('cppflags', dep)


def main():
	nprocs = 1
	ext = ''
	global verbose
	global use_color
	optlist, args = getopt.getopt(sys.argv[1:], ":j:e:vc", ['verbose', 'nocolor', 'extension='])
	for a,b in optlist:
		if a == '-v' or a == '--verbose': verbose = True
		if a == '-c' or a == '--nocolor': use_color = False
		if a == '-e' or a == '--extension': ext = b
		if a == '-j' : nprocs = int(b)

	setup_env()

	mainfile = args[0]

	cnd = strip_file_ext(basename(mainfile))
	bin = cnd + ext

	printc ("blue",  "[RcB] scanning deps...")

	scanfile( dirname(abspath(mainfile)), basename(mainfile) );

	printc ("green",  "done\n")

	filelist = []
	basedir = dirname(abspath(mainfile))
	for dep in cdeps.keys():
		filelist.append(make_relative(basedir, dep))

	if nprocs == 1: # direct build
		cmdline = "%s %s %s " % (cc, get_flags('cppflags'), get_flags('cflags'))

		for dep in filelist:
			cmdline += "%s "%dep

		cmdline += "-o %s %s" % (bin, get_flags('ldflags'))

		compile(cmdline)
	else:
		make(bin, filelist, nprocs)


def make(bin, files, nprocs):
	make_template = """
prefix = /usr/local
bindir = $(prefix)/bin

PROG = @PROG@
SRCS = @SRCS@

LIBS = @LIBS@
OBJS = $(SRCS:.c=.o)

CFLAGS = @CFLAGS@

-include config.mak

all: $(PROG)

install: $(PROG)
	install -d $(DESTDIR)/$(bindir)
	install -D -m 755 $(PROG) $(DESTDIR)/$(bindir)/

clean:
	rm -f $(PROG)
	rm -f $(OBJS)

%.o: %.c
	$(CC) $(CPPFLAGS) $(CFLAGS) $(INC) $(PIC) -c -o $@ $<

$(PROG): $(OBJS)
	$(CC) $(LDFLAGS) $(OBJS) $(LIBS) -o $@

.PHONY: all clean install
"""
	make_template = make_template.replace('@PROG@', bin)
	make_template = make_template.replace('@SRCS@', " \\\n\t".join(files))
	make_template = make_template.replace('@LIBS@', get_flags('ldflags'))
	make_template = make_template.replace('@LDFLAGS@', get_flags('ldflags'))
	make_template = make_template.replace('@CFLAGS@', get_flags('cflags'))
	make_template = make_template.replace('@CPPFLAGS@', get_flags('cppflags'))

	with open("rcb.mak", "w") as h:
		h.write(make_template)

	#ec, out, err = shellcmd(cmdline)
	os.system("make -f rcb.mak -j %d" % nprocs)


if __name__ == '__main__':
	main()
