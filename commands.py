from .enhanced_text import *


class MoveElementCommand(EnhancedText):
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

    def run(self, edit, forward=True):
        start = self.pt()
        f = self.search_forward if forward else self.search_backward
        comma = f(',', start, exit_str=True)
        if comma is None:
            return
        beg = comma.begin()
        if beg < 0:
            return
        h1, t1 = self.search_element(beg, forward=False)
        if (h1 < 0):
            return
        h2, t2 = self.search_element(comma.end())
        if (t2 < 0):
            return
        self.exchange(edit, self.rg(h1, t1), self.rg(h2, t2))
        self.move_to(t2 if forward else h1)
