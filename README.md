RcB2 - rofl0r's C builder 2nd generation
========================================

`rcb2` is the successor to [RcB](https://github.com/rofl0r/rcb).
It's a build system for C, where dependencies between files are documented with
the use of a special pragma inside the sourcefiles and headers.
So the code itself is the documentation how the program needs to be built.

When you run `rcb2`, you simply pass it the name of the sourcefile containing
the `main()` function, and `rcb2` figures out which other files are needed.

## A small example:

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

## Implementation & Design

even though the current version of `rcb2` is written in python, it is really
quick, and the concept is so simple that it could easily be rewritten in a more
performant language.

`rcb2` currently supports a `-j N` parameter. if used, instead of compiling the
required files directly, it writes a GNU make compatible makefile, and executes
it with `-j N`, speeding up the build.

At this point, all command line parameters are experimental.

## History

RcB, the previous version, used comments for the same purpose, which resulted in
a number of issues, especially in regard to conditional compilation.
while experimenting with OMP, it currently occured to me that using a `#pragma`
directive would be the solution to those issues, as it survives a preprocessor
pass. therefore the existing conditional compilation the preprocessor offers can
be leveraged.

RcB was also written in perl, a very ugly language, which is very hard to read
once a program has been written. Everytime a new cornercase required modifying
the code, it took a substantial amount of time to make sense of the almost
random looking pile of dollar signs and curly braces.
