import random
import sre_parse

__version__ = '0.1.0'
DEFAULT_MAX_REPEATS = 100

def randre(re_text):
    pattern = sre_parse.parse(re_text)
    return Generator().gen_pattern(pattern)


class Generator:
    def __init__(self, max_repeats=DEFAULT_MAX_REPEATS):
        self.groups = {}
        self.max_repeats = max_repeats

    def gen_pattern(self, pattern):
        return ''.join(self.gen_item(op, args) for op, args in pattern)

    def gen_item(self, op, args):
        return self.RAND_GENERATORS[op](self, args)

    def gen_literal(self, lit):
        return chr(lit)

    def gen_category(self, category):
        return self.gen_pattern(CATEGORIES[category])

    def gen_any(self, _):
        return chr(random.randint(32, 127))

    def gen_in(self, options):
        if options[0][0] != sre_parse.NEGATE:
            op, args = random.choice(options)
            return self.gen_item(op, args)
        else:
            candidates = set(range(32, 128))
            for op, arg in options[1:]:
                if op == sre_parse.LITERAL:
                    try:
                        candidates.remove(arg)
                    except KeyError:
                        pass
                else:
                    assert op == sre_parse.RANGE, 'unexpected op'
                    candidates -= set(range(arg[0], arg[1] + 1))
            if candidates:
                return chr(random.choice(list(candidates)))
            else:
                raise RuntimeError('no valid candidates for pattern')

    def gen_repeat(self, args):
        min_repeats, max_repeats, subpattern = args
        max_repeats = min(max_repeats, self.max_repeats)
        repeats = random.randint(min_repeats, max_repeats)
        return ''.join(self.gen_pattern(subpattern) for _ in range(repeats))

    def gen_range(self, args):
        min_range, max_range = args
        return chr(random.randint(min_range, max_range))

    def gen_subpattern(self, args):
        groupid = args[0]
        subpattern = args[-1]
        generation = self.gen_pattern(subpattern)
        self.groups[groupid] = generation
        return generation

    def gen_branch(self, args):
        # XXX: what is first arg?
        _, subpatterns = args
        subpattern = random.choice(subpatterns)
        return self.gen_pattern(subpattern)

    def gen_groupref(self, groupid):
        return self.groups[groupid]

    def gen_groupref_exists(self, args):
        groupid, yes_pattern, no_pattern = args
        if self.groups.get(groupid, False):
            return self.gen_pattern(yes_pattern)
        elif no_pattern:
            return self.gen_pattern(no_pattern)
        else:
            return ''

    def gen_not_literal(self, lit):
        candidates = [x for x in range(32, 128) if x != lit]
        return chr(random.choice(candidates))

    def gen_assert(self, args):
        return ''

    def gen_assert_not(self, args):
        return ''

    def gen_at(self, args):
        return ''

    RAND_GENERATORS = {
        sre_parse.LITERAL: gen_literal,
        sre_parse.CATEGORY: gen_category,
        sre_parse.ANY: gen_any,
        sre_parse.IN: gen_in,
        sre_parse.MAX_REPEAT: gen_repeat,
        sre_parse.MIN_REPEAT: gen_repeat,
        sre_parse.RANGE: gen_range,
        sre_parse.SUBPATTERN: gen_subpattern,
        sre_parse.BRANCH: gen_branch,
        sre_parse.GROUPREF: gen_groupref,
        sre_parse.GROUPREF_EXISTS: gen_groupref_exists,
        sre_parse.NOT_LITERAL: gen_not_literal,
        sre_parse.ASSERT: gen_assert,
        sre_parse.ASSERT_NOT: gen_assert_not,
        sre_parse.AT: gen_at,
    }


CATEGORIES = {
    sre_parse.CATEGORY_DIGIT: sre_parse.parse("[0-9]"),
    sre_parse.CATEGORY_NOT_DIGIT: sre_parse.parse("[^0-9]"),
    sre_parse.CATEGORY_SPACE: sre_parse.parse("[ \t\n\r\f\v]"),
    sre_parse.CATEGORY_NOT_SPACE: sre_parse.parse("[^ \t\n\r\f\v]"),
    sre_parse.CATEGORY_WORD: sre_parse.parse("[a-zA-Z0-9_]"),
    sre_parse.CATEGORY_NOT_WORD: sre_parse.parse("[^a-zA-Z0-9_]"),
}

if __name__ == '__main__':
    import sys
    print(randre(sys.argv[1]))

