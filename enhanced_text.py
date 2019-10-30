import sublime
import sublime_plugin


class EnhancedText(sublime_plugin.TextCommand):
    def pt(self):
        return self.view.sel()[0].begin()

    def to_pt(self, row, col):
        return self.view.text_point(row, col)

    def to_rc(self, point):
        return self.view.rowcol(point)

    def rg(self, left, right):
        return sublime.Region(left, right)

    def bol(self, point, lines=0):
        return self.to_pt(self.to_rc(point)[0] + lines, 0)

    def eol(self, point, lines=0):
        beg = self.bol(point, lines)
        return self.view.find_by_class(beg, True, sublime.CLASS_LINE_END)

    def char_at(self, point):
        return self.view.substr(point)

    def bolp(self, point):
        return self.to_rc(point)[0] == 0

    def eolp(self, point):
        return self.view.classify(point) & sublime.CLASS_LINE_END > 0

    def eobp(self, point):
        return self.to_rc(point) == self.to_rc(point + 1)

    def str(self, p1, p2):
        return self.view.substr(self.rg(p1, p2))

    def half_str_p(self, left, right):
        s = self.view.substr(self.rg(left, right))
        return s.count('\'') % 2 > 0 or s.count('"') % 2 > 0

    def row_diff(self, p1, p2):
        return self.to_rc(p1)[0] - self.to_rc(p2)[0]

    def col_diff(self, p1, p2):
        return self.to_rc(p1)[1] - self.to_rc(p2)[1]

    def search_forward(self, regexp, start, exit_str=False):
        region = self.view.find(regexp, start)
        if (region.begin() < 0):
            return None
        if exit_str:
            if self.half_str_p(start, region.begin()):
                return None
        return region

    def search_backward(self, regexp, start, exit_str=False):
        row, col = self.to_rc(start)
        pattern = '({})||$'.format(regexp)
        region = None
        curr = self.to_pt(row, 0)
        while row >= 0:
            temp = self.view.find(regexp, curr)
            beg = temp.begin()
            if 0 <= beg < start and not self.eolp(beg):
                region = temp
                curr = beg + 1
            else:
                row -= 1
                curr = self.to_pt(row, 0)
        if exit_str and region is not None:
            if self.half_str_p(region.end(), start):
                return None
        return region

    def swap(self, edit, region1, region2):
        if (region1.end() > region2.begin()):
            return
        str1 = self.view.substr(region1)
        str2 = self.view.substr(region2)
        self.view.erase(edit, region2)
        self.view.insert(edit, region2.begin(), str1)
        self.view.erase(edit, region1)
        self.view.insert(edit, region1.begin(), str2)

    def move_to(self, point):
        self.view.sel().clear()
        self.view.sel().add(self.rg(point, point))


class SearchMark(object):
    def __init__(self):
        self.a = [0, 0, 0, 0, 0]

    def is_legal(self):
        return self.a[3] == 0 and self.a[4] == 0

    def next(self, c, forward):
        if c == '(':
            self.a[0] += 1
        elif c == ')':
            self.a[0] -= 1
        elif c == '[':
            self.a[1] += 1
        elif c == ']':
            self.a[1] -= 1
        elif c == '{':
            self.a[2] += 1
        elif c == '}':
            self.a[2] -= 1
        elif c == '\'':
            self.a[3] ^= 1
        elif c == '"':
            self.a[4] ^= 1
        if self.is_legal():
            if forward:
                return max(self.a[0:3]) <= 0 and (c == ',' or min(self.a[0:3]) < 0)
            else:
                return min(self.a[0:3]) >= 0 and (c == ',' or max(self.a[0:3]) > 0)
        return False
