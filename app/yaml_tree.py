"""结构化的 YAML 行视图：树 + 增删/排序。

和 yaml_doc.YamlDoc 共用同一份 lines：
  · 值编辑仍然走 YamlDoc.set_value —— 只换值那一段字符，注释/顺序不动；
  · 结构编辑（加/删列表项、加大分类、上下移动）只做整行插入 / 删除 / 搬移，
    没碰过的行一个字节都不改。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .yaml_doc import YamlDoc


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _is_item(body: str) -> bool:
    return body == "-" or body.startswith("- ")


def _split_key(body: str):
    for i, ch in enumerate(body):
        if ch == ":" and (i + 1 >= len(body) or body[i + 1] in " \t"):
            return body[:i].strip(), body[i + 1:].strip()
    return None, ""


@dataclass
class Node:
    kind: str = "map"          # root | map | list | scalar
    key: str = ""
    line: int = -1             # 标题行
    start: int = 0
    end: int = 0
    indent: int = 0
    parent: "Node | None" = None
    children: list = field(default_factory=list)
    leaf: object = None
    index: int = 0
    list_indent: int = -1      # kind == "list" 时 "- " 的缩进

    @property
    def is_scalar(self) -> bool:
        return self.kind == "scalar" and self.leaf is not None

    @property
    def value(self) -> str:
        return self.leaf.value if self.leaf is not None else ""

    def child(self, key: str):
        for c in self.children:
            if c.key == key:
                return c
        return None

    def scalars(self):
        return [c for c in self.children if c.is_scalar]

    def lists(self):
        return [c for c in self.children if c.kind == "list"]

    def walk(self):
        yield self
        for c in self.children:
            yield from c.walk()


class YamlTree:
    def __init__(self, doc: YamlDoc):
        self.doc = doc
        self.root = Node("root")
        self.rebuild()

    # ══════════ 解析 ══════════
    def rebuild(self):
        self.doc._parse()
        self.leaf_by_line = {lf.line: lf for lf in self.doc.leaves}
        self.root = Node("root", start=0, end=len(self.doc.lines))
        # 文件是不是「根就是列表」：不是的话，一级键才是分类
        self.root_is_list = False
        for line in self.doc.lines:
            s = line.strip()
            if s and not s.startswith("#"):
                self.root_is_list = s == "-" or s.startswith("- ")
                break
        self._parse_block(0, len(self.doc.lines), self.root)

    def _lines(self):
        return self.doc.lines

    def _sig(self, i: int, end: int) -> int:
        lines = self._lines()
        while i < end:
            s = lines[i].strip()
            if s and not s.startswith("#"):
                return i
            i += 1
        return end

    def _block_end(self, start: int, end: int, indent: int) -> int:
        lines = self._lines()
        i = start
        while i < end:
            s = lines[i].strip()
            if s and not s.startswith("#") and _indent(lines[i]) <= indent:
                return i
            i += 1
        return end

    def _parse_block(self, start: int, end: int, parent: Node):
        k = self._sig(start, end)
        if k >= end:
            return
        line = self._lines()[k]
        ind = _indent(line)
        if _is_item(line[ind:]):
            lst = Node("list", key=parent.key, line=k, start=k, end=end,
                       indent=ind, parent=parent, list_indent=ind)
            parent.children.append(lst)
            self._parse_list(k, end, ind, lst)
        else:
            self._parse_map(k, end, ind, parent)

    def _parse_map(self, i: int, end: int, indent: int, parent: Node) -> int:
        lines = self._lines()
        while True:
            i = self._sig(i, end)
            if i >= end:
                return i
            line = lines[i]
            ind = _indent(line)
            if ind != indent:
                return i
            body = line[ind:]
            if _is_item(body):
                return i
            key, _ = _split_key(body)
            if key is None:
                i += 1
                continue

            nxt = self._sig(i + 1, end)
            has_child = nxt < end and _indent(lines[nxt]) > ind
            leaf = self.leaf_by_line.get(i)

            if leaf is not None and not has_child:
                parent.children.append(Node("scalar", key, i, i, i + 1, ind, parent,
                                            leaf=leaf, index=len(parent.children)))
                i += 1
                continue

            node = Node("map", key, i, i, end, ind, parent, index=len(parent.children))
            node.leaf = leaf
            parent.children.append(node)
            j = self._block_end(i + 1, end, ind)
            node.end = j
            if j > i + 1:
                self._parse_block(i + 1, j, node)
                if len(node.children) == 1 and node.children[0].kind == "list":
                    lst = node.children[0]
                    node.kind = "list"
                    node.children = lst.children
                    node.list_indent = lst.list_indent
                    for c in node.children:
                        c.parent = node
            i = j

    def _parse_list(self, i: int, end: int, indent: int, lst: Node):
        lines = self._lines()
        while True:
            i = self._sig(i, end)
            if i >= end:
                return
            line = lines[i]
            ind = _indent(line)
            if ind != indent:
                return
            body = line[ind:]
            if not _is_item(body):
                return
            j = self._block_end(i + 1, end, indent)
            item = Node("map", "-", i, i, j, ind, lst, index=len(lst.children))
            lst.children.append(item)

            rest = body[1:].lstrip()
            if rest:
                col = ind + 1 + (len(body[1:]) - len(rest))
                key, _ = _split_key(rest)
                leaf = self.leaf_by_line.get(i)
                if key is not None:
                    if leaf is not None:
                        item.children.append(Node("scalar", leaf.key, i, i, i + 1, col,
                                                  item, leaf=leaf))
                    else:
                        node = Node("map", key, i, i, end, col, item)
                        item.children.append(node)
                        if j > i + 1:
                            node.end = j
                            self._parse_block(i + 1, j, node)
                elif leaf is not None:
                    item.kind = "scalar"
                    item.leaf = leaf
            if j > i + 1:
                self._parse_block(i + 1, j, item)
            i = j

    # ══════════ 结构编辑 ══════════
    def _blank_values(self, seg: list[str], start: int, end: int):
        """把一段行里的标量值清成 ""，键名/缩进/行内注释原样保留。"""
        for lf in self.doc.leaves:
            if not (start <= lf.line < end):
                continue
            k = lf.line - start
            if not (0 <= k < len(seg)):
                continue
            line = seg[k]
            if not (0 <= lf.vstart <= lf.vend <= len(line)):
                continue
            seg[k] = line[:lf.vstart] + '""' + line[lf.vend:]

    def add_item(self, lst: Node, shape=None, indent: int | None = None) -> bool:
        """列表末尾加一条：有现成条目就照最后一条复制，被清空过就按 shape 造。"""
        lines = self._lines()
        if lst.children:
            tpl = lst.children[-1]
            drop = set()

            def walk(node):
                for c in node.children:
                    if c.kind == "list":
                        for extra in c.children[1:]:
                            drop.update(range(extra.start, extra.end))
                    elif c.kind == "map":
                        walk(c)

            walk(tpl)
            seg = [lines[k] for k in range(tpl.start, tpl.end) if k not in drop]
            self._blank_values(seg, tpl.start, tpl.end)
            if seg and not seg[-1].strip():
                seg = seg[:-1]
            new = seg
            at = tpl.end
            while at > tpl.start and not lines[at - 1].strip():
                at -= 1
        elif shape:
            base = indent if indent is not None else (
                lst.list_indent if lst.list_indent >= 0 else lst.indent + 2)
            pad = " " * base
            new = []
            for n, (kk, vv) in enumerate(shape):
                new.append(f"{pad}{'- ' if n == 0 else '  '}{kk}: {vv if vv else '\"\"'}")
            at = lst.line + 1
        else:
            return False
        lines[at:at] = new
        self.rebuild()
        return True

    def remove(self, node: Node) -> bool:
        lines = self._lines()
        if not (0 <= node.start < node.end <= len(lines)):
            return False
        # 尾部空行属于两段之间的分隔，不跟着一起删
        end = node.end
        while end > node.start and not lines[end - 1].strip():
            end -= 1
        del lines[node.start:end]
        self.rebuild()
        return True

    def move(self, node: Node, delta: int) -> bool:
        siblings = node.parent.children if node.parent else []
        if node not in siblings:
            return False
        k = siblings.index(node)
        j = k + delta
        if not (0 <= j < len(siblings)):
            return False
        other = siblings[j]
        lines = self._lines()
        a, b = (node, other) if node.start < other.start else (other, node)
        if a.end != b.start:          # 中间隔着东西就放弃，宁可不动
            return False
        lines[a.start:b.end] = lines[b.start:b.end] + lines[a.start:a.end]
        self.rebuild()
        return True

    def insert_after(self, node: Node, new_lines: list[str]) -> bool:
        lines = self._lines()
        at = node.end
        while at > node.start and not lines[at - 1].strip():
            at -= 1
        if not new_lines:
            return False
        lines[at:at] = new_lines
        self.rebuild()
        return True

    # ══════════ 查询 ══════════
    def leaves_of(self, node: Node) -> list:
        return [n.leaf for n in node.walk() if n.is_scalar]

    def root_items(self) -> list:
        if not self.root_is_list:
            return []
        for c in self.root.children:
            if c.kind == "list":
                return c.children
        return []

    def top_nodes(self) -> list:
        if self.root_is_list:
            return []
        return list(self.root.children)
