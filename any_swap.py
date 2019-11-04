from .enhanced_text import *

MAX = 32
WORD = '[0-9a-zA-Z_\\.#@^]'


class Lexer(object):
    def __init__(self):
        self.regexes = []
        self.prior = 0
        self.prior_dict = {}
        self.rule_dict = {}
        self.register(['{', '\\[', '\\('], 1)
        self.register(['\\)', '\\]', '}'], 2)
        _left = self.register([], 1)
        self.register([';'], 2)
        self.register([','], 3)
        self.register([':'], 3)
        _assign = self.register(['\\+=', '-=', '\\*=', '%=', '&=', '\\|=', '^='], 3)
        _or = self.register(['\\|\\|'], 3)
        _and = self.register(['&&'], 3)
        _not = self.register(['!'], 1)
        self.register(['==', '!=', '~='], 3)
        self.register(['='], *_assign)
        _compare = self.register(['<=', '>='], 3)
        self.register(['\\+', '-'], 3)
        self.register(['\\*', '/', '%'], 3)
        self.register(['\\.'], 3)
        self.regexes += ['"[^"]*?"', "'[^']*?'", '<{}*?>'.format(WORD)]
        self.register(['<', '>'], *_compare)
        self.regexes.append('{}+'.format(WORD))
        self.register(['if', 'return'], *_left)
        self.register(['or'], *_or)
        self.register(['and'], *_and)
        self.register(['not'], *_not)
        self.full_reg = '|'.join(self.regexes)
        self.pair_dict = {'(': ')', '[': ']', '{': '}'}

    def register(self, ls, rule, prior=None):
        self.regexes += ls
        if prior is None:
            prior = self.prior
            self.prior += 1
        for c in ls:
            txt = c.replace('\\', '')
            self.rule_dict[txt] = rule
            self.prior_dict[txt] = prior
        return rule, prior

    def tokens(self, view, beg, end):
        curr = beg
        res = []
        while curr < end:
            rg = view.find(self.full_reg, curr)
            txt = view.substr(rg)
            token = Token(txt, self.prior_dict.get(txt, MAX), self.rule_dict.get(txt, 0))
            token.rg = rg
            curr = rg.end()
            if curr <= end:
                res.append(token)
        return res


LEXER = Lexer()


class Token(object):
    def __init__(self, txt, prior, rule):
        self.txt = txt
        self.prior = prior
        self.rule = rule
        self.rg = None

    def __repr__(self):
        return self.txt

    def __len__(self):
        return self.end - self.beg


class ParseNode(object):
    def __init__(self, token):
        self.tokens = [token]
        self.parent = None
        self.sub_nodes = []
        self.prior = token.prior
        self.rule = token.rule
        self.index = 0
        if token.rg is not None:
            self.beg = token.rg.begin()
            self.end = token.rg.end()

    def __repr__(self):
        return ''.join([t.__repr__() for t in self.tokens])

    def sub(self, index):
        return self.sub_nodes[index] if self.sub_nodes else None

    def cmp(self, node):
        return self.prior - node.prior

    def add(self, node):
        node.parent = self
        node.index = len(self.sub_nodes)
        self.sub_nodes.append(node)

    def insert(self, node):
        last = self.pop()
        self.add(node)
        node.add(last)

    def merge(self, node):
        self.tokens += node.tokens
        self.prior = node.prior
        self.rule = node.rule & 1
        self.end = node.end

    def pop(self):
        return self.sub_nodes.pop() if self.sub_nodes else None

    def bound(self):
        if not self.sub_nodes:
            return self.beg, self.end
        beg = min(self.beg, self.sub(0).bound()[0])
        end = max(self.end, self.sub(-1).bound()[1])
        return beg, end

    def prev_node(self):
        if self.index > 0:
            return self.parent.sub(self.index - 1)
        return None

    def next_node(self):
        if self.index < len(self.parent.sub_nodes) - 1:
            return self.parent.sub(self.index + 1)
        return None

    def right(self):
        # print('right', self, self.parent, self.index)
        if not self.parent:
            return self, None
        right = self.next_node()
        if right:
            return self, right
        res = self.parent.right()
        if self.parent.parent and self.parent.rule == 3:
            if self.parent.cmp(self.parent.parent) == 0:
                return self, res[1]
        return res

    def left(self):
        # print('left', self, self.parent, left)
        if not self.parent:
            return None, self
        left = self.prev_node()
        if left:
            if left.cmp(self.parent) == 0 and self.parent.rule == 3:
                left = left.sub(-1)
            return left, self
        return self.parent.left()

    def locate(self, pos):
        res = None
        if self.parent and self.beg <= pos <= self.end:
            res = self
        if not self.sub_nodes:
            return res
        for n in self.sub_nodes:
            found = n.locate(pos)
            if found:
                return found
        return res

    def locate_inner(self, pos):
        for p in enumerate(self.tokens):
            if p[1].rg.contains(pos):
                return p
        return None

    def show(self):
        return self._print([], [], [])

    def _print(self, res, p1, p2):
        res += p1 + [self.__repr__(), '\n']
        n = len(self.sub_nodes)
        for i in range(n):
            child = self.sub(i)
            if i < n - 1:
                child._print(res, p2 + ['├─'], p2 + ['│ '])
            else:
                child._print(res, p2 + ['└─'], p2 + ['  '])
        return ''.join(res)


class Parser(object):
    def __init__(self):
        self.root = ParseNode(Token('?', -1, -1))
        self.curr = self.root
        self.wait = []
        self.adders = {0: self.add0, 1: self.add1, 2: self.add2, 3: self.add3}

    def add(self, token):
        new = ParseNode(token)
        # print('add ', self.curr, token)
        self.adders[token.rule](new)
        # print('add_', self.root.show())

    def add0(self, node):
        if self.curr.rule == 0:
            self.curr.merge(node)
        else:
            if self.curr.rule & 1 == 0:
                self.curr = self.curr.parent
            self.curr.add(node)
            self.curr = node

    def add1(self, node):
        self.add0(node)
        txt = node.tokens[0].txt
        back = LEXER.pair_dict.get(txt)
        if back:
            self.wait.append((back, self.curr))

    def add2(self, node):
        if self.wait:
            txt = node.tokens[0].txt
            recent = self.wait[-1]
            if txt == recent[0]:
                self.curr = recent[1]
                self.curr.merge(node)
                self.wait.pop()
                return
        self.add3(node)

    def add3(self, node):
        if self.curr.rule & 1 == 0:
            self.curr = self.curr.parent
        while self.curr.cmp(node) >= 0:
            self.curr = self.curr.parent
        self.curr.insert(node)
        self.curr = node


class AnySwapCommand(EnhancedText):
    def process(self, pos):
        beg = self.bol(pos)
        end = self.eol(pos)
        tokens = LEXER.tokens(self.view, beg, end)
        # print('tokens', beg, end, tokens)
        parser = Parser()
        for t in tokens:
            parser.add(t)
        # print(parser.root.show())
        target = parser.root.locate(pos)
        # print('target', target)
        return target

    def run(self, edit, forward=True):
        pos = self.pt()
        target = self.process(pos)
        if not target:
            return
        lf, rt = target.right() if forward else target.left()
        # print('pair', lf, rt)
        pair = ()
        if lf and rt:
            if lf.rule == 2:
                if rt.rule != 2:
                    return
            elif rt.rule == 2:
                return
            b1, e1 = lf.bound()
            b2, e2 = rt.bound()
            pair = (self.rg(b1, e1), self.rg(b2, e2))
        elif target.parent.prior < 0:
            p = target.locate_inner(pos)
            if not p:
                return
            i = p[0]
            n = len(target.tokens)
            if forward:
                if 0 <= i < n - 1:
                    pair = (p[1].rg, target.tokens[i + 1].rg)
            else:
                if i > 0:
                    pair = (target.tokens[i - 1].rg, p[1].rg)
        if pair:
            self.swap(edit, *pair)
            self.move_to(pair[1].end() if forward else pair[0].begin())
