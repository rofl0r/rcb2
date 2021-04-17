RcB2 - rofl0r's C builder 2nd generation
========================================

`rcb2` is the successor to [RcB](https://github.com/rofl0r/rcb).
It's a build system for C, where dependencies between files are documented with
the use of a special pragma inside the sourcefiles and headers.
So the code itself is the documentation how the program needs to be built.

When you run `rcb2`, you simply pass it the name of the sourcefile containing
the `main()` function, and `rcb2` figures out which other files are needed.

Cross-compilation is as simple as using an appropriate `CC` environment
variable.

`rcb2`, when started as `rcb2make`, writes a *GNU make* compatible Makefile
which can be used for efficiency and to support parallel builds or to create
tarballs for distribution which do not require `rcb2` itself.

`rcb2` itself is parallel and very fast, it basically uses only the C
preprocessor to figure out which files need to be built, then builds all
required files in a single compiler call.

## How it works, a small example:

You have a file `main.c` which, depending on some macros, shall use either
`foo.h` and `foo.c`, or `bar.h` and `bar.c`.

main.c:
```c
#include <stdio.h>

#ifdef FOO
#include "foo.h"
#define func foo
#else
#include "bar.h"
#define func bar
#endif

int main() { printf("%s\n", func()); }

```

foo.h:
```c
const char *foo(void);
#pragma RcB2 DEP "foo.c"
```

foo.c:
```c
const char *foo(void) { return "foo"; }
```

bar.h:
```c
const char *bar(void);
#pragma RcB2 DEP "bar.c"
```
bar.c:
```c
const char *bar(void) { return "bar"; }
```

now you can run `CFLAGS=-DFOO rcb2 main.c` and it will produce an executable
named `main` which will print `foo` when run.
if you execute `rcb2 main.c`, the build executable will print `bar`.

you can find the example in `tests/1`.

## How to use

If a file (typically a header) requires some other files, you add a
`#pragma RcB2 DEP "../src/file1.c" "lib/file2.c"`. Globs are supported too.
All path components need to be relative to the file containing the pragma.

If a .c file requires certain CFLAGS for compilation, e.g. `-std=c99`, you can
add `#pragma RcB2 CFLAGS "-std=c99"`. Note that this should be used really
sparingly, since it will be applied to **all** files in the build, and it can
unexpectedly break compilation for some files or on some systems:
For example on some BSDs, using `-std=c99` automatically enables a strict mode
which deselects certain useful POSIX, XSI and GNU features, like *strdup()* etc.

Use `#pragma RcB2 CPPFLAGS "-DFOO" "-I.."` if you need some macros or include
paths to be enabled across compilation units.
Here again, usage will be applied to **all** files, so adding e.g. `-I..` may
have unintended consequences if you use several libraries.

Likewise, if a certain library is needed, e.g. `-lncurses` and `-lm`, you
declare it like so: `#pragma RcB2 LINK "-lncurses" "-lm"`.

note that you could stuff both `-l` directives into the same set of double
quotes, and it would work, but it is advised to specify each library separately.
RcB2 drops duplicates to keep the compiler command line as short as possible.
The `LINK` directive should only be used for libraries, there's an `LDFLAGS`
directive that can be used for other necessary linker flags.

`CPPFLAGS`, `CFLAGS`, `LINK (LIBS)` and `LDFLAGS` derived via RcB2 pragmas
are considered essential for a working build and hardcoded into the resulting
Makefile, unlike environment vars or presets used for compilation.

The pragmas can be put between preprocessor `#if`s and `#ifdef`s.
Only those that survive the preprocessor pass are being picked up.

After all headers have the dependencies on the .c files they depend on properly
documented, it's sufficient to simply include a header, and run `rcb2` on the
file, and it will pick up all files required instantly.

`rcb2` has a `--pure` mode that throws all .c files onto the compiler in
a single pass.
This allows to use CFLAGS like `-fwhole-program` which can very efficiently
optimize the binary.

## Installation

copy `rcb2.py` into a directory in your *PATH* (e.g. /usr/bin) as `rcb2`.
symlink `rcb2` to `rcb2make` if you also want to use the makefile generator.

you can also simply copy/paste the following snippet into your shell:

    export RCB2DEST=/usr/bin
    cp rcb2.py "$RCB2DEST"/rcb2
    ln -sf rcb2 "$RCB2DEST"/rcb2make

## Implementation & Design

`rcb2` simply runs the C preprocessor on the file passed on the command line,
using the supplied C/CPPFLAGS, and then parses the `#pragma RcB2` directives
that survived. All referenced files are then recursively processed in the exact
same manner, until the complete list is created. As a C preprocessor is a pretty
simple program, this is a very quick process.

After the complete list of dependencies is known, they are passed to the
compiler. That's it.

Even though the current version of `rcb2` is written in python2, it is really
quick, and the concept is so simple that it could easily be rewritten in a more
performant/portable language such as C.

At this point, all command line parameters are experimental.
Run `rcb2 --help` to get a full list of options.

## History

RcB, the previous version, used comments for the same purpose, which resulted in
a number of issues, especially in regard to conditional compilation.
while experimenting with OMP, it occured to me that using a `#pragma`
directive would be the solution to those issues, as it survives a preprocessor
pass. therefore the existing conditional compilation the preprocessor offers can
be leveraged.

RcB was also written in perl, a very ugly language, which is very hard to read
once a program has been written. Everytime a new cornercase required modifying
the code, it took a substantial amount of time to make sense of the almost
random looking pile of dollar signs and curly braces.
