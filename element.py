from .enhanced_text import *

MAX = 32


class Element(EnhancedText):
    def __init__(self, view):
        super(Element, self).__init__(view)
        separators = []
        self.prior_dict = {}
        separators += ['{', '\\[', '\\(', '\\)', '\\]', '}']
        for c in '{[()]}':
            self.prior_dict[c] = 0
        separators.append(',')
        self.prior_dict[','] = 1
        separators += ['\\|\\|', 'or']
        for c in ['||', 'or']:
            self.prior_dict[c] = 2
        for c in ['&&', 'and']:
            separators.append(c)
            self.prior_dict[c] = 3
        for c in ['==', '!=', '~=']:
            separators.append(c)
            self.prior_dict[c] = 4
        for c in ['<', '<=', '>', '>=']:
            separators.append(c)
            self.prior_dict[c] = 5
        separators += ['\\+', '-']
        for c in '+-':
            self.prior_dict[c] = 6
        separators += ['\\*', '/', '%']
        for c in '*/%':
            self.prior_dict[c] = 7
        separators.append('"[^"]*"')
        separators.append("'[^']*'")
        self.sreg = '|'.join(separators)
        self.ws = re.compile('[ \t]')
        self.ereg = '({})?.*?({})?'.format(self.sreg, self.sreg)

    def tokens(self, beg, pos, end):
        curr = beg
        res = []
        while curr < end:
            rg = self.view.find(self.sreg, curr)
            rgb = rg.begin()
            rge = rg.end()
            if rgb < 0 or rge > end:
                ele = self.get(curr, pos, self.str(curr, end))
                if ele:
                    res.append(ele)
                break
            if curr < rgb:
                ele = self.get(curr, pos, self.str(curr, rgb))
                if ele:
                    res.append(ele)
            txt = self.view.substr(rg)
            sep = Token(txt, self.prior_dict[txt])
            sep.set_bound(rg.begin(), rg.end())
            sep.contains = rg.contains(pos)
            res.append(sep)
            curr = rg.end()
        return res

    def get(self, start, pos, string):
        n = len(string)
        lfs = string.lstrip()
        txt = lfs.strip()
        beg = start + n - len(lfs)
        token = Token(txt, MAX)
        token.set_bound(beg, beg + len(txt))
        token.contains = start <= pos <= start + n
        return token


class Token(object):
    def __init__(self, txt, prior):
        self.txt = txt
        self.prior = prior
        self.beg = -1
        self.end = -1
        self.contains = False

    def __repr__(self):
        return self.txt + '!' if self.contains else self.txt

    def __len__(self):
        return self.end - self.beg

    def set_bound(self, beg, end):
        self.beg = beg
        self.end = end


class AnySwapCommand(EnhancedText):
    def search_element(self, start, forward=True):
        def check(curr):
            if forward:
                return not self.eobp(curr)
            else:
                return curr > 0

        ws = re.compile('[ \t\n]')
        curr = start
        head = -1
        tail_flag = True
        tail = curr
        mark = SearchMark()
        while check(curr):
            c = self.char_at(curr if forward else curr - 1)
            if (ws.match(c)):
                if (tail_flag):
                    tail_flag = False
                    tail = curr
                curr += 1 if forward else -1
            else:
                tail_flag = True
                if head < 0:
                    head = curr
                if mark.next(c, forward):
                    if not mark.is_legal():
                        return -1, -1
                    break
                curr += 1 if forward else -1
                tail = curr
        return (head, tail) if forward else (tail, head)

    def process(self):
        pos = self.pt()
        beg = self.bol(pos)
        end = self.eol(pos)
        element = Element(self.view)
        tokens = element.tokens(beg, pos, end)
        parser = Parser()
        target = None
        for t in tokens:
            node = parser.add(t)
            if t.contains:
                if not target or target.token.prior < t.prior:
                    target = node
        return target

    def run(self, edit, forward=True):
        target = self.process()
        if target:
            lf, rt = target.next() if forward else target.prev()
            print(lf, rt)
            if lf and rt:
                b1, e1 = lf.bound()
                b2, e2 = rt.bound()
                self.swap(edit, self.rg(b1, e1), self.rg(b2, e2))
                self.move_to(e2 if forward else b1)


class Parser(object):
    def __init__(self):
        self.root = ParseNode(Token('?', 0))
        self.curr = self.root
        self.wait = []
        self.pair_dict = {'(': ')', '[': ']', '{': '}'}

    def add(self, token):
        new = ParseNode(token)
        if token.prior == MAX:
            self.curr.add(new)
            return new
        if token.prior > self.curr.token.prior:
            last = self.curr.pop()
            if last:
                new.add(last)
            self.curr.add(new)
            self.curr = new
            return new
        if token.prior > 0:
            node = self.curr
            while node.parent and node.parent.token.prior >= token.prior:
                node = node.parent
            if node.parent:
                node.parent.pop()
                node.parent.add(new)
            new.add(node)
            self.curr = new
            return new
        if self.wait:
            recent = self.wait[-1]
            if token.txt == recent[0]:
                self.curr = recent[1]
                self.curr.token.txt += token.txt
                self.curr.token.contains |= token.contains
                self.curr.token.prior = MAX - 1
                self.curr.token.set_bound(self.curr.token.beg, token.end)
                self.wait.pop()
            return self.curr
        back = self.pair_dict.get(token.txt)
        self.wait.append((back, new))
        self.curr.add(new)
        self.curr = new
        return new


class ParseNode(object):
    def __init__(self, token):
        self.token = token
        self.last = None
        self.parent = None
        self.sub_nodes = []
        self.index = 0

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

    def next(self):
        if not self.parent:
            return self, None
        if self.index + 1 < len(self.parent.sub_nodes):
            return self, self.parent.sub(self.index + 1)
        res = self.parent.next()
        if self.parent.parent:
            if self.parent.token.prior == self.parent.parent.token.prior:
                return self, res[1]
        return res

    def prev(self):
        if not self.parent:
            return None, self
        if self.index > 0:
            return self.parent.sub(self.index - 1), self
        res = self.parent.prev()
        if self.parent.parent:
            if self.parent.token.prior == self.parent.parent.token.prior:
                return res[0], self
        return res

    def print_all(self):
        print(self)
        for node in self.sub_nodes:
            node.print_all()
