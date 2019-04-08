#include <stdio.h>

#ifdef FOO
#include "foo.h"
#define func foo
#else
#include "bar.h"
#define func bar
#endif

int main() {
	printf("%s\n", func());
}
