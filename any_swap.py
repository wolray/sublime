from .enhanced_text import *

MAX = 32
INF = 1024


class Lexer(object):
    def __init__(self):
        self.regexes = []
        self.prior_dict = {}
        self.limit_dict = {}
        self.fixed_dict = {}
        self.register(0, ['{', '\\[', '\\(', '\\)', '\\]', '}'], INF)
        self.register(1, [';'], 1, 1 | 2)
        self.register(2, [','], fixed=2)
        self.register(3, [':'])
        assign = self.register(4, ['\\+=', '-=', '\\*=', '%=', '&=', '\\|=', '^='], fixed=1)
        self.register(5, ['\\|\\|', 'or'])
        self.register(6, ['&&', 'and'])
        self.register(7, ['==', '!=', '~='])
        self.register(assign, ['='], fixed=1)
        compare = self.register(8, ['<=', '>='])
        self.register(9, ['\\+', '-'])
        self.register(10, ['\\*', '/', '%'])
        self.register(11, ['\\.'], fixed=1)
        self.regexes.append('"[^"]*?"')
        self.regexes.append("'[^']*?'")
        self.regexes.append('<[^<>]*?>')
        self.register(compare, ['<', '>'])
        self.regexes.append('[0-9a-zA-Z_\\.#@^]+')
        self.full_reg = '|'.join(self.regexes)
        self.pair_dict = {'(': ')', '[': ']', '{': '}'}

    def register(self, prior, ls, limit=2, fixed=0):
        self.regexes += ls
        for c in ls:
            txt = c.replace('\\', '')
            self.prior_dict[txt] = prior
            self.limit_dict[txt] = limit
            self.fixed_dict[txt] = fixed
        return prior

    def new_token(self, txt):
        prior = self.prior_dict.get(txt)
        if prior is None:
            prior = MAX
        limit = self.limit_dict.get(txt)
        if limit is None:
            limit = 0
        fixed = self.fixed_dict.get(txt)
        if fixed is None:
            fixed = 0
        return Token(txt, prior, limit, fixed)

    def tokens(self, view, beg, end):
        curr = beg
        res = []
        while curr < end:
            rg = view.find(self.full_reg, curr)
            txt = view.substr(rg)
            token = self.new_token(txt)
            token.set_bound(rg.begin(), rg.end())
            res.append(token)
            curr = rg.end()
        return res


LEXER = Lexer()


class Token(object):
    def __init__(self, txt, prior, limit, fixed):
        self.txt = txt
        self.postfix = ''
        self.prior = prior
        self.limit = limit
        self.fixed = fixed
        self.beg = -1
        self.end = -1

    def __repr__(self):
        return self.txt + self.postfix

    def __len__(self):
        return self.end - self.beg

    def compare_to(self, token):
        return self.prior - token.prior

    def set_bound(self, beg, end):
        self.beg = beg
        self.end = end

    def contains(self, token):
        return self.beg <= token.beg and token.end <= self.end

    def merge(self, token):
        self.postfix += token.__repr__()
        self.prior = token.prior
        self.limit = token.limit
        self.fixed = token.fixed
        self.set_bound(self.beg, token.end)


class Parser(object):
    def __init__(self):
        self.root = ParseNode(Token('?', -MAX, INF, 0))
        self.curr = self.root
        self.wait = []

    def upward(self):
        while self.curr.full():
            self.curr = self.curr.parent

    def add(self, token):
        # print('add', self.curr.parent, self.curr, token, self.wait)
        new = ParseNode(token)
        last = self.curr.sub(-1)
        if token.prior == MAX:
            self.upward()
            self.curr.add(new)
            return
        back = LEXER.pair_dict.get(token.txt)
        if back:
            # print('last', last)
            if last and last.after:
                last.token.merge(token)
                new = last
            else:
                self.upward()
                self.curr.add(new)
            self.curr = new
            self.wait.append((back, new))
            return
        if token.prior == 0 and self.wait:
            recent = self.wait[-1]
            if token.txt == recent[0]:
                self.curr = recent[1]
                self.curr.token.postfix += token.txt
                self.curr.token.prior = MAX
                self.curr.token.forbidden = False
                self.curr.token.set_bound(self.curr.token.beg, token.end)
                self.wait.pop()
                new = self.curr
                self.curr = self.curr.parent
                return
        if token.prior > self.curr.token.prior:
            if last and last.after:
                self.curr.pop()
                new.add(last)
                last.after = False
            self.curr.add(new)
            self.curr = new
        else:
            node = self.curr
            while node.parent and node.parent.token.compare_to(token) >= 0:
                node = node.parent
            if node.parent:
                node.parent.pop()
                node.parent.add(new)
            new.add(node)
            node.after = False
            self.curr = new


class ParseNode(object):
    def __init__(self, token):
        self.token = token
        self.parent = None
        self.sub_nodes = []
        self.index = 0
        self.after = True

    def __repr__(self):
        return self.token.__repr__()

    def sub(self, index):
        return self.sub_nodes[index] if self.sub_nodes else None

    def add(self, node):
        node.parent = self
        node.index = len(self.sub_nodes)
        self.sub_nodes.append(node)

    def pop(self):
        return self.sub_nodes.pop() if self.sub_nodes else None

    def bound(self):
        if not self.sub_nodes:
            return self.token.beg, self.token.end
        beg = min(self.token.beg, self.sub(0).bound()[0])
        end = max(self.token.end, self.sub(-1).bound()[1])
        return beg, end

    def full(self):
        return len(self.sub_nodes) >= self.token.limit

    def allow1(self):
        return len(self.sub_nodes) >= 2 and self.token.fixed & 1 == 0

    def allow2(self):
        return self.token.fixed & 2 == 0

    def right(self):
        # print('swap', self, self.parent, self.token.limit, self.token.fixed)
        if not self.parent:
            return self, None
        if self.index + 1 < len(self.parent.sub_nodes) and self.parent.allow1():
            right = self.parent.sub(self.index + 1)
            if right.allow2():
                return self, right
        res = self.parent.right()
        if self.parent.parent:
            if self.parent.token.prior == self.parent.parent.token.prior:
                if self.allow2():
                    return self, res[1]
        return res

    def left(self):
        # print('swap', self, self.parent, self.token.limit, self.token.fixed)
        if not self.parent:
            return None, self
        if self.index > 0 and self.parent.allow1():
            left = self.parent.sub(self.index - 1)
            if left.token.prior == self.parent.token.prior:
                left = left.sub(-1)
            if left.allow2() and self.allow2():
                return left, self
        return self.parent.left()

    def locate(self, pos):
        res = None
        if self.token.beg <= pos <= self.token.end:
            # print('locate has', self)
            res = self
        if not self.sub_nodes:
            return res
        for n in self.sub_nodes:
            found = n.locate(pos)
            if found:
                return found
        return res

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


class AnySwapCommand(EnhancedText):
    def process(self):
        pos = self.pt()
        beg = self.bol(pos)
        end = self.eol(pos)
        tokens = LEXER.tokens(self.view, beg, end)
        # print('tokens', tokens)
        parser = Parser()
        for t in tokens:
            parser.add(t)
        # print(parser.root.show())
        target = parser.root.locate(pos)
        # print('target', target)
        return target

    def run(self, edit, forward=True):
        target = self.process()
        if not target:
            return
        lf, rt = target.right() if forward else target.left()
        # print('pair', lf, rt)
        if lf and rt and lf.allow2() and rt.allow2():
            b1, e1 = lf.bound()
            b2, e2 = rt.bound()
            self.swap(edit, self.rg(b1, e1), self.rg(b2, e2))
            self.move_to(e2 if forward else b1)
