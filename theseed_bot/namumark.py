import re, urllib.parse, json, os.path, time, logging, io, copy, colorsys, webcolors, math
from bs4 import BeautifulSoup

# namumark parser

class Document():
    def __init__(self, namespace, title, text, force_show_namespace = True):
        self.namespace = namespace
        self.title = title
        self.text = text
        self.force_show_namespace = force_show_namespace
    
class Paragraph():
    def __init__(self, namumark, title, level, hidden, content):
        if not isinstance(namumark, Namumark):
            raise TypeError()

        if title:
            self.title, i = MarkedText.parse_line(title, namumark)
        else:
            self.title = None
        
        self.level = level
        self.hidden = hidden

        self.content = content
        self.child = []

        self.namumark = namumark

        self.parse()
        
        self.content = MarkedText.parse(self.content, namumark, parent = self)

    def __str__(self):
        result = ''
        
        for content in self.content:
            result += str(content)
            result += '\n'
        
        if self.level > 0:
            hidden_text = '#' if self.hidden else ''
            level_text = ''
            for i in range(self.level):
                level_text += '='
            
            title_text = '{0}{1} {2} {1}{0}\n'.format(level_text, hidden_text, self.title)
            result = title_text + result
        
        for child in self.child:
            result += str(child)
        
        if self.level == 0:
            result = result[:-1]
        
        return result
    
    def __repr__(self):
        return '({}, {}, {}{})'.format(repr(self.title), self.level, self.hidden, ', {}'.format(self.child) if self.child else '')
    
    def add_child(self, child):
        self.child.append(child)
    
    def find_child(self, title):
        for child in self.child:
            if child.title == title:
                return child
        return None
    
    def find_child_regex(self, regex):
        for child in self.child:
            match = regex.search(child.title)
            if match:
                return child, match
        return None

    def parse(self):
        found = False
        content = None

        for p in Namumark.h_tags:
            start_pos = 0
            title = None
            hidden = False

            for match in p[0].finditer(self.content):
                if start_pos == 0:
                    content = self.content[start_pos:match.start(0)]
                else:
                    self.add_child(Paragraph(self.namumark, title, p[1], hidden, self.content[start_pos:match.start(0)]))
                
                hidden = match[1] == '#'
                title = match['title']

                start_pos = match.end(0) + 1

                found = True
            
            if found:
                self.add_child(Paragraph(self.namumark, title, p[1], hidden, self.content[start_pos:]))
            else:
                content = self.content
            
            if found:
                break
        
        self.content = content
    
    def deepest_level(self):
        result = self.level
        for child in self.child:
            result = child.deepest_level()
        
        return result
    
    def sort_level(self):
        if self.level == 0:
            for child in self.child:
                child.level = 2 if self.deepest_level() <= 6 else 1
                child.sort_level()
        else:
            for child in self.child:
                child.level = self.level + 1
                child.sort_level()
    
    def get_child_level(self):
        if self.level == 0:
            if self.child:
                return self.child[0].level
            else:
                return 2
        else:
            return self.level + 1
    
    def __iter__(self):
        yield self

        for child in self.child:
            for item in child:
                yield item
    
    def find_all(self, **kwargs):
        result = []
        
        if 'recursive' in kwargs:
            for p in self:
                if p.title:
                    result.extend(p.title.find_all(**kwargs))
                
                for content in p.content:
                    result.extend(content.find_all(**kwargs))
        else:
            if self.title:
                result.extend(self.title.find_all(**kwargs))
            
            for content in self.content:
                result.extend(content.find_all(**kwargs))
        
        return result

class MarkedText():
    open = None
    close = None
    multiline = False
    
    parent = None
    namumark = None
    
    start_newline = True
    
    name = 'MarkedText'
    
    def __init__(self, namumark, content = None, indent = 0):
        if content == None:
            self.content = []
        else:
            self.content = content
        
        self.namumark = namumark
        if not isinstance(self.namumark, Namumark):
            raise TypeError()

        self.indent = indent
    
    def __str__(self):
        result = ''
        for i in range(self.indent):
            result += ' '
        
        result += '' if not self.open else self.open
        
        for c in self.content:
            result += str(c)
            
        result += '' if not self.close else self.close
            
        return result
    
    def get_string(self):
        result = ''
        
        for c in self.content:
            result += c.get_string()
        
        return result
    
    def get_bgcolor(self):
        parent = self.parent
        while parent and not isinstance(parent, Paragraph):
            if isinstance(parent, TableCell) or isinstance(parent, Table):
                if 'bgcolor' in parent.styles:
                    return parent.styles['bgcolor']
            elif isinstance(parent, WikiDiv):
                key = ''
                
                if 'background-color' in parent.styles:
                    key = 'background-color'
                elif 'background' in parent.styles:
                    key = 'background'
                
                if key:
                    if parent.styles[key] == 'transparent':
                        return None
                    elif Color.pattern.match(parent.styles[key]):
                        return Color(parent.styles[key])
                
            parent = parent.parent
        
        return Namumark.default_bgcolor
    
    def __repr__(self):
        return '{}({}, {})'.format(self.name, self.indent, repr(self.content))
    
    @classmethod
    def parse(cls, content, namumark, offset = -1, parent = None, allow_comment = True, close = None):
        i = max(0, offset)
        result = []
        
        while i < len(content):
            p, i = cls.parse_line(content, namumark, offset = i, parent = parent, allow_comment = allow_comment, close = close)
            result.append(p)
        
        if offset < 0:
            return result
        else:
            return result, i
    
    def preprocess(self, content, offset):
        return offset
    
    def postprocess(self, content, offset):
        return offset
    
    @staticmethod
    def check_indent(content, offset, check = -1):
        indent = 0
        i = offset
        while i < len(content):
            if content[i] != ' ':
                break
            
            indent += 1
            i += 1
        
        if check >= 0:
            if indent != check:
                return False, offset
            else:
                return True, i
        
        return indent, i
    
    @classmethod
    def parse_line(cls, content, namumark, offset = 0, parent = None, allow_newline = False, start_newline = None, close = None, allow_comment = True, indent = 0):
        i = offset
        close_block = cls.close if not close else close
        multiline = cls.multiline
        start_newline = cls.start_newline if start_newline == None else start_newline
        
        closed = False
        linestart = offset == 0 or start_newline
        
        indent, i = cls.check_indent(content, i)
        
        if cls.open:
            assert content[offset:offset+len(cls.open)] == cls.open
        
        line_cls = cls

        if cls == MarkedText:
            for l in Namumark.singlelines:
                if indent >= l.allowed_indent[0] and (indent <= l.allowed_indent[1] or l.allowed_indent[1] < 0):
                    if content[i:i+len(l.open)] == l.open:
                        line_cls = l
                        break
        
        inst = line_cls(namumark, [], indent)
        inst.parent = parent
        
        if line_cls.open:
            i += len(line_cls.open)

        pre_result = inst.preprocess(content, i)
        
        if pre_result == None or (line_cls == Comment and not allow_comment):
            if line_cls in Namumark.singlelines and cls == MarkedText:
                del inst

                inst = cls(namumark, [], indent)
                inst.parent = parent

                i -= len(line_cls.open)
            else:
                return None, offset
        else:
            i = pre_result

        while i < len(content):
            found = False

            if not multiline and content[i] == '\n':
                i += 1
                break
            
            if close_block:
                if content[i:i+len(close_block)] == close_block:
                    closed = True

                    if close_block != '\n':
                        i += len(close_block)

                    i = inst.postprocess(content, i)
                    break
            
            if not found:
                if linestart and content[i] == '|':
                    r, i = Table.parse_line(content, namumark, i, inst, indent = indent)
                    if r:
                        inst.content.append(r)
                        found = True
            
            if not found:
                for b in Namumark.brackets:
                    if content[i:i+len(b.open)] == b.open:
                        r, i = b.parse_line(content, namumark, i, inst, indent = indent)
                        if r:
                            inst.content.append(r)
                            found = True
                            break
            
            linestart = False
            
            if not found:
                if content[i] == '\n':
                    linestart = True
                    
                if len(inst.content) > 0:
                    if isinstance(inst.content[-1], PlainText):
                        inst.content[-1].add_char(content[i])
                        i += 1
                        continue
                    
                inst.content.append(PlainText(content[i]))
                i += 1
        
        if closed or not close_block or allow_newline:
            return inst, i
        else:
            return None, offset
    
    def __iter__(self):
        yield self
        for child in self.content:
            for content in child:
                yield content
    
    def filter(self, **kwargs):
        result = True
        
        if 'type' in kwargs:
            result = kwargs['type'] == self.name
        
        return result
    
    def find_all(self, **kwargs):
        result = []
        
        for content in self:
            if not isinstance(content, str):
                if content.filter(**kwargs):
                    result.append(content)
        
        return result
    
    def extract(self):
        if self.parent:
            if isinstance(self.parent, Paragraph):
                idx = self.parent.content.index(self)
                del self.parent.content[idx]
            elif self in self.parent.content:
                if isinstance(self.parent, TableCell):
                    return None
                else:
                    return self.parent.content.pop(self.parent.content.index(self))
        else:
            raise TypeError()

class PlainText():
    name = 'PlainText'
    
    def __init__(self, content):
        self.content = content
    
    def __str__(self):
        return str(self.content)
    
    def __repr__(self):
        return repr(self.content)
    
    def __iter__(self):
        yield self
    
    def get_string(self):
        return self.content
    
    def filter(self, **kwargs):
        result = True
        
        if 'type' in kwargs:
            result = kwargs['type'] == self.name
        
        return result
    
    def add_char(self, char):
        assert isinstance(char, str)
        
        self.content += char

class UnorderedList(MarkedText):
    name = 'UnorderedList'

    allowed_indent = (1, -1)

    open = "*"

    def preprocess(self, content, offset):
        i = offset

        if i < len(content):
            if content[i] == ' ':
                i += 1
        
        return i

    def __str__(self):
        result = ''
        for i in range(self.indent):
            result += ' '
        
        result += self.open + ' '
        
        for c in self.content:
            result += str(c)
            
        return result

class OrderedList(MarkedText):
    name = 'OrderedList'

    allowed_indent = (1, -1)

    def preprocess(self, content, offset):
        self.order = None

        i = offset

        order_match = re.match(r'#([0-9]+)', content[offset:])
        if order_match:
            self.order = int(order_match[1])
            i += order_match.end()

        if i < len(content):
            if content[i] == ' ':
                i += 1
        
        return i

    def __str__(self):
        result = ''
        for i in range(self.indent):
            result += ' '
        
        result += self.open

        if self.order != None:
            result += '#{}'.format(self.order)
        
        result += ' '
        
        for c in self.content:
            result += str(c)
            
        return result
    
    def __repr__(self):
        return '{}({}, {}{})'.format(self.name, self.indent, '{}, '.format(self.order) if self.order else '', repr(self.content))

class DecimalList(OrderedList):
    name = 'DecimalList'

    open = "1."

class UpperAlphaList(OrderedList):
    name = 'UpperAlphaList'

    open = "A."

class AlphaList(OrderedList):
    name = 'UpperAlphaList'

    open = "a."

class UpperRomanList(OrderedList):
    name = 'UpperRomanList'

    open = "I."

class RomanList(OrderedList):
    name = 'RomanList'

    open = "i."

class Comment(MarkedText):
    name = 'Comment'

    allowed_indent = (0, 0)
    open = '##'

    def preprocess(self, content, offset):
        match = re.match(r'(.*)(?:\n|$)', content[offset:])
        assert match

        self.comment = match[1]
        return offset + match.end() - 1
    
    def __str__(self):
        return self.open + self.comment
    
    def __repr__(self):
        return '{}({})'.format(self.name, self.comment)

class QuotedText(MarkedText):
    name = 'QuotedText'

    allowed_indent = (-1, -1)
    open = '>'

    def preprocess(self, content, offset):
        i = offset
        text = ''

        while i < len(content):
            match = re.match(r'(.*)(\n|$)', content[i:])
            
            assert match
            text += match[1] + '\n'
            i += match.end()
            
            if i >= len(content):
                break
            
            old_i = i
            indent_check, i = MarkedText.check_indent(content, i, check = self.indent)
            if not indent_check:
                i -= 1
                break

            if content[i:i+len(self.open)] != self.open:
                i = old_i - 1
                break

            i += len(self.open)
        
        self.content = MarkedText.parse(text, self.namumark, parent = self, allow_comment = False)
        return i
    
    def __str__(self):
        result = ''
        indent = ''

        for i in range(self.indent):
            indent += ' '
        
        for c in self.content:

            result += str(c) + '\n'
        
        result = result[:-1]
        return re.sub(r'^', indent + '>', result, flags = re.MULTILINE)

class HorizontalLine(MarkedText):
    name = 'HorizontalLine'

    allowed_indent = (-1, -1)
    open = '----'

    def preprocess(self, content, offset):
        match = re.match(r'-{0,5}$', content[offset:], flags = re.MULTILINE)

        if not match:
            return None
        
        return offset + match.end()
    
    def __repr__(self):
        return '{}({})'.format(self.name, self.indent)

class WikiDiv(MarkedText):
    open = "{{{#!wiki"
    close = "}}}"
    multiline = True
    
    start_newline = True
    
    name = 'WikiDiv'
    
    def preprocess(self, content, offset):
        match_style = re.match(r' style="(.*?)"\n', content[offset:])
        if not match_style:
            return None
        
        self.styles = {}
        for pair in match_style[1].split(';'):
            pair_split = pair.split(':')
            
            if len(pair_split) < 2:
                continue
            
            self.styles[pair_split[0].strip()] = pair_split[1].strip()
        
        offset += match_style.end()
        return offset
    
    def separate_color(self):
        if 'color' in self.styles:
            color = self.styles.pop('color')
            
            colored_text = ColoredText(self.content)
            colored_text.color = Color(color)
            
            self.content = [colored_text]
    
    def __str__(self):
        styles = ''
        for key, value in self.styles.items():
            styles += '{}: {}; '.format(key, value)
        styles = styles[:-2]
    
        result = self.open + ' style="{}"\n'.format(styles)
        
        for c in self.content:
            result += str(c)
        
        result += self.close
        return result
    
    def __repr__(self):
        return '{}(style={}, {})'.format(self.name, self.styles, repr(self.content))

class FoldingDiv(MarkedText):
    open = "{{{#!folding"
    close = "}}}"
    multiline = True
    
    start_newline = True
    
    name = 'FoldingDiv'
    
    def preprocess(self, content, offset):
        match_style = re.match(r' (.*?)\n', content[offset:])
        if not match_style:
            return None
        
        self.title = match_style[1]
        
        offset += match_style.end()
        return offset
    
    def __str__(self):
        result = self.open + ' {}\n'.format(self.title)
        
        for c in self.content:
            result += str(c)
        
        result += self.close
        return result
    
    def __repr__(self):
        return '{}(title="{}", {})'.format(self.name, self.title, repr(self.content))

class HtmlText(MarkedText):
    open = "{{{#!html"
    close = "}}}"
    multiline = True
    
    start_newline = False
    
    name = 'HtmlText'
    
    def separate_color(self):
        soup = BeautifulSoup(self.content[0].content, 'html.parser')
        
        target = soup.find('font', recursive=True)
        
        if target:
            try:
                color = target['color']
                del target['color']
                
                target.unwrap()
                
                colored_text = ColoredText([self])
                colored_text.color = Color(color)
                
                index = self.parent.content.index(self)
                
                self.parent.content[index] = colored_text
                
                self.content[0].content = str(soup)
            except KeyError:
                pass

class OldBoxedText(MarkedText):
    open = "{{|"
    close = "|}}"
    multiline = True
    
    start_newline = False
    
    name = 'OldBoxedText'
    
    def __str__(self):
        result = '||'
        
        for c in self.content:
            result += str(c)
        
        result += '||'
        return result

class BoxedText(MarkedText):
    open = "{{{"
    close = "}}}"
    multiline = True
    
    start_newline = False
    
    name = 'BoxedText'

class NowikiText(MarkedText):
    open = "{{{"
    close = "}}}"
    multiline = False
    
    start_newline = False
    
    name = 'NowikiText'
    
    def preprocess(self, content, offset):
        cnt = 1
        i = offset
        
        while cnt > 0:
            if i >= len(content):
                return None
                
            if content[i] == '\n':
                return None
            
            if content[i:i+3] == '{{{':
                cnt += 1
                i += 3
                continue
            elif content[i:i+3] == '}}}':
                cnt -= 1
                i += 3
                continue
                
            i += 1
        
        i -= 3
        self.content = content[offset:i]
        
        return i

class SizedText(MarkedText):
    open = "{{{"
    close = "}}}"
    multiline = False
    
    start_newline = False
    
    name = 'SizedText'
    
    def preprocess(self, content, offset):
        match_style = re.match(r'([+-][1-6]) ', content[offset:])
        if not match_style:
            return None
        
        self.size = int(match_style[1])
        
        offset += match_style.end()
        return offset
    
    def __str__(self):
        result = self.open + '{}{} '.format('+' if self.size > 0 else '', self.size)
        
        for c in self.content:
            result += str(c)
        
        result += self.close
        return result
    
    def __repr__(self):
        return '{}({}, {})'.format(self.name, self.size, repr(self.content))

class ColoredText(MarkedText):
    open = "{{{"
    close = "}}}"
    multiline = True
    
    start_newline = False
    
    name = 'ColoredText'
    
    def preprocess(self, content, offset):
        if not re.match(r'((?:(?:^|(,))((?(2)|#)[A-Za-z]+|#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}))){1,2}) ', content[offset:]):
            return None
        
        if not re.match(r'#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})', content[offset:]):
            offset += 1
        
        self.color, offset = Color.parse(content, offset)
        if not self.color:
            return None
        
        if not content[offset] == ' ':
            return None
        
        return offset + 1
    
    def generate_dark(self, override = False):
        self.color.generate_dark(bgcolor = self.get_bgcolor(), foreground = True, override = override)
    
    def __str__(self):
        result = self.open + '{}{} '.format('#' if str(self.color)[0] != '#' else '', self.color)
        
        if len(self.content) >= 1:
            if isinstance(self.content[0], Table):
                result += '\n'
        
        for c in self.content:
            result += str(c)
        
        result += self.close
        return result
    
    def __repr__(self):
        return '{}(color="{}", {})'.format(self.name, self.color, repr(self.content))

class LinkedText(MarkedText):
    open = "[["
    close = "]]"
    multiline = False
    
    start_newline = False
    
    name = 'LinkedText'
    
    def __init__(self, namumark, content = [], indent = 0):
        super().__init__(namumark, content, indent)
        self.link = None
        self.anchor = None
        self.escape = False
        self.type = 0
    
    def preprocess(self, content, offset):
        match_link = re.match(r'(.*?)((?<!\\)\||(?=\]\]))', content[offset:])
        if not match_link:
            return None
        
        self.link = match_link[1].strip()
        self.anchor = None
        
        if not re.match(r'https?://', match_link[1]):
            anchor = re.split(r'(?<!\\)#', match_link[1], maxsplit = 1)
            
            if len(anchor) > 1:
                self.link = anchor[0].strip()
                self.anchor = anchor[1]
            
            if len(self.link) > 0:
                if self.link[0] == ':':
                    self.escape = True
                    self.link = self.link[1:]

            if ':' in self.link:
                index = self.link.index(':')
                ns = self.link[:index]
                l = self.link[index+1:].lstrip()

                if ns in self.namumark.available_namespaces:
                    self.link = ns + ':' + l
                elif self.escape:
                    self.escape = False
                    self.link = ':' + self.link
        
        offset += match_link.end()
        
        return offset
    
    def generate_dark(self, override = False):
        if len(self.link) >= 3:
            if self.link[:3] == '파일:':
                return
    
        if len(self.content) == 1:
            if isinstance(self.content[0], ColoredText):
                return
        
        bgcolor = self.get_bgcolor()

        if Color.get_difference(bgcolor.get_dark(), Namumark.default_link_color.dark) < 150:
            if self.content:
                colored_text = ColoredText(self.content)
            else:
                colored_text = ColoredText([PlainText(self.link)])
            
            colored_text.color = Color(Namumark.default_link_color.light)
            
            self.content = [colored_text]
    
    def filter(self, **kwargs):
        result = super().filter(**kwargs)
        
        if 'link' in kwargs:
            if isinstance(kwargs['link'], re.Pattern):
                result &= bool(kwargs['link'].search(self.link))
            elif isinstance(kwargs['link'], str):
                result &= kwargs['link'] == self.link
            else:
                raise TypeError()
        
        if 'escape' in kwargs:
            result &= kwargs['escape'] == self.escape
        
        return result
    
    def get_string(self):
        if self.content:
            return super().get_string()
        
        return self.link
    
    def __str__(self):
        result = self.open

        if self.escape:
            result += ':'

        result += self.link
        
        if self.anchor:
            result += '#' + self.anchor
        
        if self.content:
            content = ''
            for c in self.content:
                content += str(c)
            if content != self.link:
                result += '|' + content
        
        result += self.close
        return result
    
    def __repr__(self):
        link = '({}, anchor={})'.format(self.link, self.anchor) if self.anchor else self.link
        return '{}(link={}, {})'.format(self.name, link, repr(self.content)) if self.content else '{}({})'.format(self.name, link)

class FootnoteText(MarkedText):
    open = "[*"
    close = "]"
    multiline = True
    
    start_newline = False
    
    name = 'FootnoteText'
    
    def preprocess(self, content, offset):
        match_style = re.match(r'(.*?)(?: |(?=\]))', content[offset:])
        if not match_style:
            return None
        
        self.title = match_style[1]
        
        offset += match_style.end()
        return offset
    
    def __str__(self):
        result = self.open
        
        if self.title:
            result += self.title
        
        if self.content:
            result += ' '
            for c in self.content:
                result += str(c)
        
        result += self.close
        return result
    
    def __repr__(self):
        return '{}(title="{}", {})'.format(self.name, self.title, repr(self.content)) if self.title else '{}({})'.format(self.name, self.content)

class Macro(MarkedText):
    open = "["
    close = "]"
    multiline = False
    
    start_newline = False
    
    name = 'Macro'
    
    defined_macros = ['목차', 'tableofcontents', 'date', 'datetime', 'br', 'pagecount', 'include', 'footnote', 'age', 'dday', 'ruby', 'youtube', 'kakaotv', 'nicovideo', 'clearfix']
    
    def preprocess(self, content, offset):
        match_macro = re.match(r'(.*?)(?:\((.*?)(?<!\\)\))?(?=\])', content[offset:])
        if not match_macro:
            return None
        
        self.macro = match_macro[1].lower()
        
        if self.macro not in self.defined_macros:
            return None
        
        self.parameters = []
        self.named_parameters = {}
        
        if match_macro[2]:
            parameters = re.split(r'(?<!\\)\s*,\s*', match_macro[2])
            
            for param in parameters:
                if '=' in param:
                    named_param = re.split(r'(?<!\\)=\s*', param, maxsplit = 1)
                    if len(named_param) > 1:
                        self.named_parameters[named_param[0]] = named_param[1]
                else:
                    self.parameters.append(param)
        
        offset += match_macro.end()
        
        return offset
    
    def __str__(self):
        result = self.open + self.macro
        
        if self.parameters:
            result += '('
            for p in self.parameters:
                result += str(p) + ', '
                
            for k, v in self.named_parameters.items():
                result += str(k) + '=' + str(v) + ', '
                
            result = result[:-2]
            result += ')'
        
        result += self.close
        return result
    
    def __getitem__(self, idx):
        if isinstance(idx, str):
            return self.named_parameters[idx]
        elif isinstance(idx, int):
            return self.parameters[idx]
        else:
            raise KeyError
    
    def __setitem__(self, idx, value):
        if isinstance(idx, str):
            self.named_parameters[idx] = value
        elif isinstance(idx, int):
            self.parameters[idx] = value
        else:
            raise ValueError
    
    def filter(self, **kwargs):
        result = super().filter(**kwargs)
        
        if 'macro' in kwargs:
            result &= kwargs['macro'] == self.macro
        
        if 'param' in kwargs and result:
            if len(self.parameters) > 0:
                if isinstance(kwargs['param'], re.Pattern):
                    match = kwargs['param'].search(self[0])
                    if not match:
                        result = False
                else:
                    result &= kwargs['param'] == self[0]
            else:
                result = False
        
        return result
    
    def __repr__(self):
        return '{}({}, {})'.format(self.name, self.macro, self.parameters) if self.parameters else '{}({})'.format(self.name, self.macro)

class MathText(MarkedText):
    open = '['
    close = ']'
    
    name = 'MathText'

    def preprocess(self, content, offset):
        match_math = re.match(r'(.*?)(?:\((.*?)(?<!\\)\))?(?=\])', content[offset:], flags = re.DOTALL)

        if not match_math:
            return None
        
        macro = match_math[1].lower()

        if macro != 'math':
            return None

        self.math = match_math[2]

        return offset + match_math.end()
    
    def __str__(self):
        return '[math({})]'.format(self.math)
    
    def __repr__(self):
        return '{}({})'.format(self.name, repr(self.math))

class OldMathText(MathText):
    open = '<math>'
    close = '</math>'

    def preprocess(self, content, offset):
        match_math = re.match(r'(.*?)(?=</math>)', content[offset:])

        if not match_math:
            return None

        self.math = match_math[1]

        return offset + match_math.end()

class Table(MarkedText):
    open = None
    close = None
    multiline = True
    
    start_newline = False
    
    name = 'Table'

    re_color = re.compile(r'((?:(?:^|,)([A-Za-z]+|#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}))){1,2})$')
    re_length = re.compile(r'^[0-9]+(\.[0-9]+)?(%|px)?$')

    re_tablestyle = re.compile(r'<(table ?)?(.*?)(=(["\']?)(.*?)\4)?>')
    
    special_style_types = [
        (re.compile(r'^-([0-9]+)$'), 'colspan'),
        (re.compile(r'^\|([0-9]+)$'), 'rowspan'),
        (re.compile(r'^\^\|([0-9]+)$'), 'rowspan', ('valign', 'top')),
        (re.compile(r'^v\|([0-9]+)$'), 'rowspan', ('valign', 'bottom')),
        (re.compile(r'^:$'), ('align', 'center')),
        (re.compile(r'^\($'), ('align', 'left')),
        (re.compile(r'^\)$'), ('align', 'right')),
        (re_color, 'bgcolor')
    ]

    global_style_types = {
        'width': re_length, 
        'color': re_color, 
        'bgcolor': re_color, 
        'bordercolor': re_color,
        'align': re.compile(r'^(left|center|right)$')
    }

    style_types = {
        'width': re_length, 
        'height': re_length, 
        'color': re_color, 
        'bgcolor': re_color, 
        'colcolor': re_color, 
        'colbgcolor': re_color, 
        'rowcolor': re_color, 
        'rowbgcolor': re_color
    }
    
    def __init__(self, namumark, content, indent):
        super().__init__(namumark, content, indent)
        self.styles = {}
        self.comments = []
        
        self.cache_colcount = None
    
    def __iter__(self):
        yield self

        if self.caption:
            for i in self.caption:
                yield i
        
        for row in self.content:
            for cell in row:
                for content in cell.content:
                    for i in content:
                        yield i
    
    @classmethod
    def parse_caption(cls, content, namumark, offset = 0):
        assert content[offset] == '|'
        return MarkedText.parse_line(content, namumark, offset + 1, close = '|')
    
    def parse_style(self, content, offset = 0, first = False):
        styles = {}
        i = offset
        
        while i < len(content):
            match_style = self.re_tablestyle.match(content[i:])
            if not match_style:
                break
            
            if match_style[3]:
                if match_style[1]:
                    if match_style[2] in self.global_style_types:
                        if self.global_style_types[match_style[2]].search(match_style[5]):
                            if match_style[2] not in self.styles:
                                if first:
                                    self.style_order.append(match_style[1] + match_style[2])

                                self.styles[match_style[2]] = match_style[5]
                
                                i += match_style.end()
                                continue
                    break
                elif match_style[2] in self.style_types:
                    if self.style_types[match_style[2]].search(match_style[5]):
                        if first:
                            self.style_order.append(match_style[2])

                        styles[match_style[2]] = match_style[5]
                    else:
                        break
            else:
                matched = False
                for style_info in self.special_style_types:
                    match = style_info[0].search(match_style[2])
                    if match:
                        for k in range(1, len(style_info)):
                            if isinstance(style_info[k], str):
                                if first:
                                    self.style_order.append(style_info[k])

                                styles[style_info[k]] = match[k]
                            else:
                                if first:
                                    self.style_order.append(style_info[k][0])

                                styles[style_info[k][0]] = style_info[k][1]
                        matched = True
                        break
                        
                if not matched:
                    break
                
            i += match_style.end()
        
        for k in styles.keys():
            if len(k) >= 5:
                if k[-5:] == 'color':
                    styles[k] = Color.parse(styles[k])
        
        return styles, i
    
    @classmethod
    def parse_line(cls, content, namumark, offset = 0, parent = None, indent = 0):
        i = offset
        
        new_row = False
        first = True
        
        styles = {}
        
        assert content[offset] == '|'
        
        inst = cls(namumark, [[]], indent)
        inst.caption = None
        inst.parent = parent
        
        inst.style_order = []
        
        # check caption
        try:
            if not content[i+1] == '|':
                inst.caption, i = cls.parse_caption(content, namumark, i)
                if not inst.caption:
                    return None, offset
            else:
                i += 2
        except IndexError:
            return None, offset
            
        colspan = 1
        
        colinfo = []
        col_num = 0

        while i < len(content):
            comment = None

            if content[i] == '\n':
                old_i = i
                i += 1
                
                # check comment
                if content[i:i+2] == Comment.open:
                    comment, i = Comment.parse_line(content, namumark, i)
                    inst.comments.append((comment, len(inst.content)))
                
                # check indentation
                indent_check, i = cls.check_indent(content, i, check = indent)
                
                if indent_check:
                    if content[i:i+2] == '||':
                        i += 2
                    else:
                        i = old_i
                        break
                else:
                    # different indentation. exit
                    i = old_i
                    break
            
            if parent:
                if parent.close:
                    if content[i:i+len(parent.close)] == parent.close:
                        break
            
            # process old colspan
            if content[i:i+2] == '||':
                colspan += 1
                
                i += 2
                
                if i >= len(content):
                    colspan = 1
                    break
                    
                if content[i] == '\n':
                    colspan = 1
                    new_row = True
                continue
            
            # parse styles
            styles, i = inst.parse_style(content, i, first)
            
            # check align by space
            align_right = False
            while i < len(content):
                if content[i] == ' ':
                    align_right = True
                    i += 1
                else:
                    break
            
            # parse cell content
            cell = []
            old_i = i

            cell_finished = False

            while i < len(content):
                c, i = MarkedText.parse_line(content, namumark, i, allow_newline = True, close = '||', start_newline = content[i-1] == '\n')
                cell.append(c)

                if not c:
                    cell = None
                    break

                if content[i-2:i] == '||':
                    cell_finished = True
                    break
            
            if not cell_finished:
                cell = None

            if cell != None:
                if 'colspan' not in styles and colspan > 1:
                    styles['colspan'] = str(colspan)
                
                # check align by space
                if i - old_i > 1:
                    align_left = content[i-3] == ' '
                    
                    if align_left:
                        cell[-1], j = MarkedText.parse_line(str(cell[-1]).rstrip(), namumark, start_newline = False)
                    
                    if 'align' not in styles:
                        if align_right and align_left:
                            styles['gapalign'] = 'center'
                        elif align_right:
                            styles['gapalign'] = 'right'
                        elif align_left:
                            styles['gapalign'] = 'left'
            
            if new_row:
                # check if it is complete table
                if cell == None:
                    break

                # start new row
                col_num = 0

                inst.content.append([])
            else:
                if cell == None:
                    # broken table
                    return None, offset
                
            # process rowspan
            rowspan = 1
            current_col = 0
            
            if 'rowspan' in styles:
                rowspan = int(styles['rowspan'])
            if 'colspan' in styles:
                colspan = int(styles['colspan'])
                
            if len(inst.content) == 1:
                current_col = col_num
                colinfo.extend([rowspan for k in range(colspan)])
                col_num += colspan
            else:
                extend_col = False
                
                # check rowspan
                for col_num in range(col_num, len(colinfo)):
                    if colinfo[col_num] < len(inst.content):
                        break
                
                if col_num + colspan >= len(colinfo):
                    extend_col = True
                        
                current_col = col_num

                for col_num in range(col_num, min(col_num + colspan, len(colinfo))):
                    colinfo[col_num] += rowspan
                
                col_num += 1

                if extend_col:
                    colinfo.extend([rowspan for k in range(col_num + colspan - len(colinfo))])
            
            cell_inst = TableCell(inst, styles, cell, current_col)
            for c in cell:
                c.parent = cell_inst
            
            inst.content[-1].append(cell_inst)
            
            if i >= len(content):
                break
            
            if content[i] == '\n':
                colspan = 0
                new_row = True
            else:
                new_row = False
            
            colspan = 1
            first = False
        
        for k in inst.styles.keys():
            if len(k) >= 5:
                if k[-5:] == 'color':
                    inst.styles[k] = Color.parse(inst.styles[k])
            
        return inst, i
    
    def __str__(self):
        result = '||'
        if self.caption:
            result = '|{}|'.format(self.caption)
        
        first = True
        style_order = copy.deepcopy(self.style_order)
        
        row_num = 0
        
        for row in self.content:
            for comment in self.comments:
                if row_num == comment[1]:
                    result += '\n{}'.format(comment[0])
            
            if not first:
                result += '\n'
                for i in range(self.indent):
                    result += ' '
                result += '||'
            for cell in row:
                only_gapalign = True
                front_align_str = ''
                back_align_str = ''
                
                style_str = ''
                
                # apply colspan, rowspan, stated alignments
                for type, style in cell.styles.items():
                    if type == 'colspan':
                        if int(style) > 1:
                            style_str += '<-{}>'.format(style)
                    elif type == 'rowspan':
                        if 'valign' not in cell.styles:
                            if int(style) > 1:
                                style_str += '<|{}>'.format(style)
                        elif cell.styles['valign'] == 'top':
                            style_str += '<^|{}>'.format(style)
                        elif cell.styles['valign'] == 'bottom':
                            style_str += '<v|{}>'.format(style)
                    elif type == 'align':
                        if cell.styles['align'] == 'right':
                            style_str += '<)>'.format(style)
                        elif cell.styles['align'] == 'center':
                            style_str += '<:>'.format(style)
                        elif cell.styles['align'] == 'left':
                            style_str += '<(>'.format(style)
                
                if first:
                    # apply global styles
                    if 'colspan' in style_order:
                        style_order.pop(style_order.index('colspan'))
                    if 'rowspan' in style_order:
                        style_order.pop(style_order.index('rowspan'))
                    if 'valign' in style_order:
                        style_order.pop(style_order.index('valign'))
                    if 'align' in style_order:
                        style_order.pop(style_order.index('align'))
                    if 'gapalign' in style_order:
                        style_order.pop(style_order.index('gapalign'))
                
                    processed = []
                    for type in style_order:
                        match_tablestyle = re.match(r'table ?(.*)', type)
                        if match_tablestyle:
                            table_type = match_tablestyle[1]
                            
                            if table_type in self.styles:
                                processed.append('table' + table_type)
                        
                                style_str += '<{}={}>'.format(type, self.styles[table_type])
                        else:
                            if type in cell.styles:
                                processed.append(type)
                                
                                style_str += '<{}={}>'.format(type, cell.styles[type])
                    
                    for type, style in self.styles.items():
                        if not 'table' + type in processed:
                            style_str = style_str + '<table{}={}>'.format(type, style)
                
                            
                # apply styles
                for type, style in cell.styles.items():
                    if first:
                        if type in processed:
                            continue
                            
                    if type == 'colspan' or type == 'rowspan' or type == 'align' or type == 'valign' or type == 'gapalign':
                        pass # process separately
                    else:
                        style_str += '<{}={}>'.format(type, style)
                
                # apply gap alignments
                for type, style in cell.styles.items():
                    if type == 'align':
                        only_gapalign = False
                        break
                if only_gapalign:
                    for type, style in cell.styles.items():
                        if type == 'gapalign':
                            if style == 'right' or style == 'center':
                                front_align_str += ' '
                            if style == 'left' or style == 'center':
                                back_align_str += ' '
                            break
                
                content = ''
                for c in cell.content:
                    content += str(c) + '\n'
                
                if len(content) > 0:
                    content = content[:-1]
                
                if not content:
                    content = ' '
                elif content[0] == '\n' and not style_str:
                    # exceptional case
                    style_str = '<(>'
                
                if content[0] == ' ':
                    front_align_str = ''
                
                if content[-1] == ' ':
                    back_align_str = ''
                
                result += style_str + front_align_str + content + back_align_str + '||'
                first = False
            
            row_num += 1
        
        return result
    
    def get_string(self):
        return ''
    
    def get_colcount(self):
        if not self.cache_colcount:
            colcount = 0
            
            for row in self.content:
                for cell in row:
                    colcount = max(colcount, cell.column)
            
            self.cache_colcount = colcount + 1
        
        return self.cache_colcount
    
    def internal_apply_styles(self, type):
        assert type == 'bgcolor' or type == 'color'
        
        # apply tablecolor, rowcolor, colcolors
        # priority: color > colcolor > rowcolor > tablecolor
        colcolors = {}
        rowcolor = None
        tablecolor = None
        
        if type in self.styles:
            tablecolor = self.styles[type]
        
        for row in self.content:
            for cell in row:
                if 'col' + type in cell.styles:
                    colcolors[cell.column] = cell.styles.pop('col' + type)
                
                if 'row' + type in cell.styles:
                    rowcolor = cell.styles.pop('row' + type)
                
                if type not in cell.styles:
                    if cell.column in colcolors:
                        cell.styles[type] = colcolors[cell.column]
                    elif rowcolor:
                        cell.styles[type] = rowcolor
                    elif tablecolor:
                        cell.styles[type] = tablecolor
                    elif type == 'color':
                        already_colored = True
                        
                        for m in cell.content:
                            content = m.content
                            line_already_colored = False

                            if not str(content).strip():
                                line_already_colored = True
                                
                            while content:
                                if len(content) == 1:
                                    if isinstance(content[0], ColoredText):
                                        line_already_colored = True
                                        break
                                    elif isinstance(content[0], ItalicText) or isinstance(content[0], BoldText):
                                        content = content[0].content
                                    else:
                                        break
                                else:
                                    break
                            
                            already_colored &= line_already_colored
                        
                        if not already_colored:
                            cell.styles[type] = Namumark.default_text_color
                
            rowcolor = None
    
    def apply_styles(self):
        self.internal_apply_styles('color')
        self.internal_apply_styles('bgcolor')
    
    def compress(self):
        columns = []
        
        for row in self.content:
            for cell in row:
                if not cell.column in columns:
                    columns.append(cell.column)
        
        columns.append(self.get_colcount())
        
        columns.sort()
        
        for row in self.content:
            for cell in row:
                i = columns.index(cell.column)
                next_col = cell.column + int(cell.get_colspan())
                
                if next_col in columns:
                    j = columns.index(next_col)
                else:
                    for j in range(i, len(columns)):
                        if columns[j] >= next_col:
                            break
                    
                cell.styles['colspan'] = str(j - i)
                cell.column = i
        
        self.cache_colcount = len(columns)
        
        self.compress_color('color')
        self.compress_color('bgcolor')
     
    def compress_color(self, type):
        assert type == 'bgcolor' or type == 'color'
        
        # check default color
        if type == 'color':
            if type in self.styles:
                del self.styles[type]
            
            for row in self.content:
                for cell in row:
                    if type in cell.styles:
                        if Namumark.default_text_color.compare(cell.styles[type]):
                            del cell.styles[type]
        
        # check tablecolor
        colors = []
        color_count = []
        enable_tablecolor = True
        
        for row in self.content:
            for cell in row:
                if type not in cell.styles:
                    enable_tablecolor = False
                else:
                    index = None
                    
                    for c in colors:
                        if isinstance(c, Color):
                            if c.compare(cell.styles[type]):
                                index = colors.index(c)
                                break
                    
                    if index == None:
                        colors.append(cell.styles[type])
                        color_count.append(1)
                    else:
                        color_count[index] += 1
            
            if not enable_tablecolor:
                break
        
        if not color_count:
            return
        
        if enable_tablecolor:
            tablecolor = colors[color_count.index(max(color_count))]
        
            for row in self.content:
                for cell in row:
                    if tablecolor.compare(cell.styles[type]):
                        del cell.styles[type]
        
            self.styles[type] = tablecolor
        
        # check rowcolor
        for row in self.content:
            colors = []
            color_count = []
            enable_rowcolor = True
            
            for cell in row:
                if type not in cell.styles:
                    enable_rowcolor = False
                    break
                else:
                    index = None
                    
                    for c in colors:
                        if isinstance(c, Color):
                            if c.compare(cell.styles[type]):
                                index = colors.index(c)
                                break
                    
                    if index == None:
                        colors.append(cell.styles[type])
                        color_count.append(1)
                    else:
                        color_count[index] += 1
            
            
            if enable_rowcolor:
                if color_count:
                    if max(color_count) > 1:
                        rowcolor = colors[color_count.index(max(color_count))]
                        first = True
                    
                        for cell in row:
                            if rowcolor.compare(cell.styles[type]):
                                if first:
                                    cell.styles['row' + type] = rowcolor
                                
                                del cell.styles[type]
                                first = False
        
        # check colcolor
        colors = [[] for i in range(self.get_colcount())]
        color_count = [[] for i in range(self.get_colcount())]
        enable_colcolor = [0 for i in range(self.get_colcount())]
        
        for row in reversed(self.content):
            rowcolor = None
            if len(row) > 0:
                if 'row' + type in row[0].styles:
                    rowcolor = row[0].styles['row' + type]
            
            for cell in row:
                if enable_colcolor[cell.column] < self.content.index(row):
                    if type not in cell.styles:
                        if not rowcolor:
                            enable_colcolor[cell.column] = self.content.index(row) + 1
                        continue
                    else:
                        index = None
                        
                        for c in colors[cell.column]:
                            if isinstance(c, Color):
                                if c.compare(cell.styles[type]):
                                    index = colors[cell.column].index(c)
                                    break
                        
                        if index == None:
                            colors[cell.column].append(cell.styles[type])
                            color_count[cell.column].append(1)
                        else:
                            color_count[cell.column][index] += 1
        
        for col in range(self.get_colcount()):
            if enable_colcolor[col] < len(self.content) and colors[col]:
                if max(color_count[col]) <= 1:
                    continue
                    
                colcolor = colors[col][color_count[col].index(max(color_count[col]))]
                first = True
                
                for row in self.content[enable_colcolor[col]:]:
                    for cell in row:
                        if cell.column == col:
                            if type in cell.styles:
                                if colcolor.compare(cell.styles[type]):
                                    if first:
                                        cell.styles['col' + type] = colcolor
                                    
                                    del cell.styles[type]
                                    first = False
                            break
        
    def generate_dark(self, override = False):
        for type, style in self.styles.items():
            if type == 'bgcolor':
                style.generate_dark(override = override)
            elif type == 'bordercolor':
                if isinstance(style, Color):
                    light = webcolors.html5_parse_legacy_color(style.light)
                    if light.red == 255 and light.blue == 255 and light.green == 255:
                        style.dark = '#191919'
        
        background = False
        
        for row in self.content:
            for cell in row:
                for type, style in cell.styles.items():
                    if len(type) >= 7:
                        if type[-7:] == 'bgcolor':
                            if style:
                                style.generate_dark(override = override)
        
        for row in self.content:
            for cell in row:
                for type, style in cell.styles.items():
                    if len(type) >= 7:
                        if type[-7:] == 'bgcolor':
                            background = True
                    if not background and len(type) >= 5:
                        if type[-5:] == 'color':
                            bgcolor = None
                            if 'bgcolor' in cell.styles:
                                bgcolor = cell.styles['bgcolor']
                            
                            if isinstance(style, Color):
                                if style == Namumark.default_text_color:
                                    bgcolor = bgcolor if bgcolor else Namumark.default_table_bgcolor
                                    if abs(Color.get_lightness(bgcolor.get_dark()) - Color.get_lightness(Namumark.default_text_color.dark)) < 0.2:
                                        cell.styles[type] = Color(Namumark.default_text_color.light)
                                else:
                                    style.generate_dark(bgcolor = bgcolor, foreground = True, override = override)
                    background = False
                    
    
    def filter(self, **kwargs):
        result = super().filter(**kwargs)
        
        if 'align' in kwargs:
            if 'align' not in self.styles:
                result &= kwargs['align'] == 'left'
            else:
                result &= kwargs['align'] == self.styles['align']
        
        return result
    
    def compress_align(self):
        type = 'align'

        for row in self.content:
            for cell in row:
                if type in cell.styles:
                    cell.styles['gapalign'] = cell.styles.pop('align')

    def __repr__(self):
        return '{}({},{})'.format(self.name, self.styles, repr(self.content))

class TableCell():
    def __init__(self, parent, styles, content, column):
        self.parent = parent
        self.styles = styles
        self.content = content
        self.column = column
    
    def __repr__(self):
        return 'TableCell({},{},{})'.format(self.column, self.styles, repr(self.content))
    
    def get_string(self):
        return self.content.get_string()
    
    def get_colspan(self):
        colspan = 1
        if 'colspan' in self.styles:
            colspan = int(self.styles['colspan'])
        
        return colspan
    
    def get_rowspan(self):
        rowspan = 1
        if 'rowspan' in self.styles:
            rowspan = int(self.styles['rowspan'])
        
        return rowspan

class SimpleMarkedText(MarkedText):
    multiline = False
    
    start_newline = False

class BoldText(SimpleMarkedText):
    open = "'''"
    close = "'''"
    
    name = 'BoldText'

class ItalicText(SimpleMarkedText):
    open = "''"
    close = "''"
    
    name = 'ItalicText'

class StrikedText(SimpleMarkedText):
    open = '--'
    close = '--'
    
    name = 'StrikedText'

class StrikedText2(StrikedText):
    open = '~~'
    close = '~~'

class UnderlinedText(SimpleMarkedText):
    open = '__'
    close = '__'
    
    name = 'UnderlinedText'

class UpperText(SimpleMarkedText):
    open = '^^'
    close = '^^'
    
    name = 'UpperText'

class LowerText(SimpleMarkedText):
    open = ',,'
    close = ',,'
    
    name = 'LowerText'

class Color():
    light = None
    dark = None
    
    pattern = re.compile(r'(?:(?:^|,)([A-Za-z]+|#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3}))){1,2}')
    
    def __init__(self, light, dark = None):
        self.light = light
        self.dark = dark
    
    def __repr__(self):
        return '{},{}'.format(self.light, self.dark) if self.dark else self.light
    
    def compare(self, color):
        if not isinstance(color, Color):
            return False
        
        if color.light == self.light and color.dark == self.dark:
            return True
        return False
    
    @staticmethod
    def get_lightness(color):
        if isinstance(color, str):
            color = webcolors.html5_parse_legacy_color(color)

        return 0.2126 * color.red / 255 + 0.7152 * color.green / 255 + 0.0722 * color.blue / 255
    
    @staticmethod
    def get_difference(color_1, color_2):
        col_1 = webcolors.html5_parse_legacy_color(color_1)
        col_2 = webcolors.html5_parse_legacy_color(color_2)

        red_avg = (col_1.red + col_2.red) / 2
        color_distance = math.sqrt(((2 + red_avg / 256) * (col_1.red - col_2.red) ** 2 + 4 * (col_1.green - col_2.green) ** 2 + (2 + (255 - red_avg) / 256) * (col_1.blue - col_2.blue) ** 2) / 3)

        return color_distance
    
    def get_dark(self):
        return self.dark if self.dark else self.light
    
    def generate_dark(self, bgcolor = None, foreground = False, override = False):
        if self.light and (not self.dark or override):
            make = ''
            
            if not bgcolor:
                bgcolor = Namumark.default_bgcolor
            
            assert isinstance(bgcolor, Color)
            
            color_css = self.dark if self.dark and not override and not self.compare(Namumark.default_text_color) and not self.compare(Namumark.default_bgcolor) else self.light
                
            color_rgb = webcolors.html5_parse_legacy_color(color_css)
            
            color_hls = colorsys.rgb_to_hls(color_rgb.red / 255, color_rgb.green / 255, color_rgb.blue / 255)
            color_hsv = colorsys.rgb_to_hsv(color_rgb.red / 255, color_rgb.green / 255, color_rgb.blue / 255)
            color_l = self.get_lightness(color_rgb)
                
            if foreground:
                bg = bgcolor.get_dark()
                
                bgcol = webcolors.html5_parse_legacy_color(bg)
                bg_l = self.get_lightness(bgcol)
                
                if abs(color_l - bg_l) < 0.2:
                    if bg_l >= 0.5:
                        make = 'dark'
                    elif bg_l < 0.5:
                        make = 'light'
            else:
                if color_hsv[1] < 0.35 and color_l >= 0.6:
                    make = 'dark'

            if make == 'dark':
                if color_l > 0.4:
                    dark_hls = (color_hls[0], max(1.0 - color_hls[1], 0.1), color_hls[2])
                    dark_float = colorsys.hls_to_rgb(dark_hls[0], dark_hls[1], dark_hls[2])
                    
                    dark_int = (int(dark_float[0] * 255), int(dark_float[1] * 255), int(dark_float[2] * 255))
                    self.dark = webcolors.rgb_to_hex(dark_int)
            elif make == 'light':
                if color_css.lower() == Namumark.default_text_color.light:
                    self.dark = Namumark.default_text_color.dark
                elif color_l < 0.6:
                    dark_hls = (color_hls[0], min(1.0 - color_hls[1], 0.9), color_hls[2])
                    dark_float = colorsys.hls_to_rgb(dark_hls[0], dark_hls[1], dark_hls[2])
                    
                    dark_int = (int(dark_float[0] * 255), int(dark_float[1] * 255), int(dark_float[2] * 255))
                    self.dark = webcolors.rgb_to_hex(dark_int)
            elif override:
                self.dark = None

    @classmethod
    def parse(cls, content, offset = -1):
        return_offset = True
        
        if offset == -1:
            offset = 0
            return_offset = False
            
        match_color = cls.pattern.match(content[offset:])
        
        if not match_color:
            if return_offset:
                return None, offset
            else:
                return None
        
        colors = re.split(r'(?<!\\),', match_color[0])
        
        light = colors[0].lower()
        dark = None
        
        if len(colors) > 1:
            dark = colors[1].lower()
        
        if return_offset:
            return cls(light, dark), offset + match_color.end()
        else:
            return cls(light, dark)

class Namumark():
    h_tags = [
        # regex, level
        (re.compile(r'^=(#)? (?P<title>.*) (?(1)#)=$', flags=re.MULTILINE), 1),
        (re.compile(r'^==(#)? (?P<title>.*) (?(1)#)==$', flags=re.MULTILINE), 2),
        (re.compile(r'^===(#)? (?P<title>.*) (?(1)#)===$', flags=re.MULTILINE), 3),
        (re.compile(r'^====(#)? (?P<title>.*) (?(1)#)====$', flags=re.MULTILINE), 4),
        (re.compile(r'^=====(#)? (?P<title>.*) (?(1)#)=====$', flags=re.MULTILINE), 5),
        (re.compile(r'^======(#)? (?P<title>.*) (?(1)#)======$', flags=re.MULTILINE), 6),
    ]
    
    brackets = [
        OldBoxedText,
        WikiDiv, FoldingDiv, HtmlText,
        ColoredText, SizedText, 
        FootnoteText,
        LinkedText, BoldText, ItalicText, StrikedText, StrikedText2, UnderlinedText, UpperText, LowerText,
        NowikiText, BoxedText,
        Macro, MathText, OldMathText
    ]

    singlelines = [
        UnorderedList, DecimalList, UpperAlphaList, AlphaList, UpperRomanList, RomanList,
        QuotedText, HorizontalLine, Comment
    ]
    
    default_text_color = Color('#373a3c', '#dddddd')
    default_link_color = Color('#0275d8', '#eca019')
    default_table_bgcolor = Color('#f5f5f5', '#2d2f34')
    default_bgcolor = Color('#ffffff', '#1f2023')

    def __init__(self, document, available_namespaces = [], process_categories = True):
        self.document = document
        self.available_namespaces = available_namespaces

        self.parse()
        
        if process_categories:
            self.categories = self.parse_category()
        else:
            self.categories = None
    
    def parse(self):
        self.paragraphs = Paragraph(self, None, 0, False, self.document.text)
    
    def parse_category(self):
        links = self.paragraphs.find_all(type = 'LinkedText', link = re.compile(r'^분류:'), escape = False, recursive = True)
        
        categories = []
        
        for l in links:
            if l.link[3:] not in categories:
                categories.append((l.link[3:], l.anchor))
        
        for l in links:
            l.extract()
            if not l.parent.content and l.parent.parent:
                l.parent.extract()
        
        return categories
    
    def get_category_index(self, category):
        for i in range(len(self.categories)):
            if self.categories[i][0] == category:
                return i
        return None
    
    def is_in_category(self, category):
        for c, anchor in self.categories:
            if c == category:
                return True
        
        return False
    
    def add_category(self, category, blur = False):
        if not category in self.categories:
            self.categories.append((category, 'blur' if blur else None))
    
    def blur_category(self, category):
        i = self.get_category_index(category)
        if i != None:
            self.categories[i] = (self.categories[i][0], 'blur')
    
    def unblur_category(self, category):
        i = self.get_category_index(category)
        if i != None:
            self.categories[i] = (self.categories[i][0], None)
    
    def remove_category(self, category):
        i = self.get_category_index(category)
        if i != None:
            self.categories.pop(i)
    
    def render(self):
        category_paragraph = MarkedText(self)
        
        result = str(self.paragraphs)
        
        if self.categories:
            for c in self.categories:
                l = LinkedText(self)
                l.link = '분류:{}{}'.format(c[0], '#' + c[1] if c[1] else '')
                
                category_paragraph.content.append(l)
            
            result += '\n' + str(category_paragraph)
            
        return result