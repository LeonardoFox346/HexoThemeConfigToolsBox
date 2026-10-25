"""
按行编辑 YAML：只替换「值」那几个字符，注释、顺序、缩进、引号风格全部原样保留。

为什么不直接用 ruamel.yaml：它虽然也支持 round-trip，但重新输出时仍会
调整部分换行与缩进细节，做不到「除改动行外逐字节一致」。这里按行精确替换，
并保留原文件的换行符（\\r\\n 或 \\n），保存前后可以逐行比对。
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


def _split_value(line: str, start: int):
    """从 line[start:] 切出值。

    返回 (raw, vstart, vend, comment, quote)：
      raw      值的原文（含引号）
      vstart   值在本行内的起始列
      vend     值结束列（不含后面空格与行内注释）
      comment  行内注释（含 #）
      quote    原值用的引号字符，无引号则为空串
    """
    n = len(line)
    i = start
    while i < n and line[i] in " \t":
        i += 1
    if i >= n:
        return "", i, i, "", ""

    q = line[i] if line[i] in "\"'" else ""
    if q:
        j = i + 1
        while j < n:
            ch = line[j]
            if ch == "\\":
                j += 2
                continue
            if ch == q:
                j += 1
                break
            j += 1
        raw = line[i:j]
        k = j
        while k < n and line[k] in " \t":
            k += 1
        comment = line[k:] if k < n and line[k] == "#" else ""
        return raw, i, j, comment, q

    j = i
    while j < n:
        if line[j] == "#" and (j == i or line[j - 1] in " \t"):
            break
        j += 1
    vend = j
    while vend > i and line[vend - 1] in " \t":
        vend -= 1
    raw = line[i:vend]
    comment = line[j:] if j < n else ""
    return raw, i, vend, comment, ""


def _unquote(raw: str) -> str:
    s = raw.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1]
    return s


@dataclass
class YLeaf:
    """一个可编辑项（叶子）。"""
    key: str = ""
    path: str = ""
    line: int = 0          # 0-based 行号
    indent: int = 0
    raw: str = ""
    vstart: int = 0
    vend: int = 0
    comment: str = ""
    quote: str = ""
    group: str = ""
    parent: str = ""
    is_list_item: bool = False
    leading: list[str] = field(default_factory=list)

    @property
    def value(self) -> str:
        return _unquote(self.raw)

    @property
    def kind(self) -> str:
        v = self.value.strip()
        if v in ("true", "false", "True", "False", "yes", "no"):
            return "bool"
        if v and (v.lstrip("-").replace(".", "", 1).isdigit()):
            return "num"
        if v.startswith("[") or v.startswith("{"):
            return "seq"
        return "str"

    @property
    def is_true(self) -> bool:
        return self.value.strip().lower() in ("true", "yes", "on", "1")


class YamlDoc:
    """一个 YAML 文件的行级视图。"""

    def __init__(self, path):
        self.path = Path(path)
        self.lines: list[str] = []
        self.leaves: list[YLeaf] = []
        self.eol = "\n"
        self.trailing_newline = True
        self.dirty: dict[int, tuple[int, int, str]] = {}   # 行号 -> (vstart, vend, 新值)
        self.load()

    # ── 读取 ──
    def load(self):
        if not self.path.exists():
            self.lines = []
            self.leaves = []
            return
        with open(self.path, "r", encoding="utf-8", newline="") as f:
            text = f.read()
        self.eol = "\r\n" if "\r\n" in text else "\n"
        self.trailing_newline = text.endswith(("\n", "\r"))
        self.lines = text.replace("\r\n", "\n").split("\n")
        if self.lines and self.lines[-1] == "":
            self.lines.pop()
        self.dirty.clear()
        self._parse()

    def _parse(self):
        """扫出所有叶子。缩进栈用来拼出 a.b.c / a[0] 这样的路径。"""
        self.leaves = []
        stack: list[tuple[int, str]] = []     # (indent, key)
        pending_comments: list[str] = []
        list_idx: dict[str, int] = {}

        rows = []
        for i, line in enumerate(self.lines):
            rows.append((i, line))

        # 先前向扫一遍，记住每行的「下一个有效行缩进」，用来判断有没有子项
        next_indent = {}
        last_valid = None
        for i, line in rows:
            next_indent[i] = None
        future = None
        for i in range(len(self.lines) - 1, -1, -1):
            next_indent[i] = future
            line = self.lines[i]
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            future = len(line) - len(line.lstrip(" "))

        for i, line in enumerate(self.lines):
            s = line.strip()
            if not s:
                pending_comments = []
                continue
            if s.startswith("#"):
                pending_comments.append(s.lstrip("#").strip())
                continue

            indent = len(line) - len(line.lstrip(" "))
            body = line[indent:]
            has_child = next_indent.get(i) is not None and next_indent[i] > indent

            while stack and stack[-1][0] >= indent:
                stack.pop()
            parent_path = ".".join(k for _, k in stack)

            # ── 列表项 ──
            if body == "-" or body.startswith("- "):
                rest = body[1:]
                rest_stripped = rest.lstrip()
                key = stack[-1][1] if stack else ""
                idx = list_idx.get(parent_path, 0)
                nested = rest_stripped
                # "- key: value" 这种对象项：key 是对象里的字段名
                if ":" in rest_stripped:
                    p = rest_stripped.find(":")
                    if p > 0 and (p + 1 >= len(rest_stripped) or rest_stripped[p + 1] in " \t"):
                        field_key = rest_stripped[:p].strip()
                        col = indent + (len(body) - len(rest_stripped)) + p
                        raw, vs, ve, cm, q = _split_value(line, col + 1)
                        if raw:
                            # 有子项也要留叶子："- class_name: 我的好友" 的值本身要能改
                            path = f"{parent_path}[{idx}].{field_key}" if parent_path else f"[{idx}].{field_key}"
                            self.leaves.append(YLeaf(
                                key=field_key, path=path, line=i, indent=indent,
                                raw=raw, vstart=vs, vend=ve, comment=cm, quote=q,
                                group=self._group_of(parent_path, path), parent=parent_path,
                                is_list_item=True, leading=list(pending_comments),
                            ))
                        else:
                            stack.append((indent, field_key))
                        pending_comments = []
                        continue

                if not has_child and nested:
                    col = indent + (len(body) - len(nested))
                    raw, vs, ve, cm, q = _split_value(line, col)
                    path = f"{parent_path}[{idx}]" if parent_path else f"[{idx}]"
                    self.leaves.append(YLeaf(
                        key=f"[{idx}]", path=path, line=i, indent=indent,
                        raw=raw, vstart=vs, vend=ve, comment=cm, quote=q,
                        group=self._group_of(parent_path, path), parent=parent_path,
                        is_list_item=True, leading=list(pending_comments),
                    ))
                list_idx[parent_path] = idx + 1
                pending_comments = []
                continue

            # ── 键值行 ──
            colon = -1
            for j, ch in enumerate(body):
                if ch == ":" and (j + 1 >= len(body) or body[j + 1] in " \t"):
                    colon = j
                    break
            if colon < 0:
                pending_comments = []
                continue

            key = body[:colon].strip()
            raw, vs, ve, cm, q = _split_value(line, indent + colon + 1)

            if raw and not has_child:
                path = f"{parent_path}.{key}" if parent_path else key
                self.leaves.append(YLeaf(
                    key=key, path=path, line=i, indent=indent,
                    raw=raw, vstart=vs, vend=ve, comment=cm, quote=q,
                    group=self._group_of(parent_path, path), parent=parent_path,
                    leading=list(pending_comments),
                ))
            elif not raw or has_child:
                stack.append((indent, key))
                list_idx[parent_path] = 0 if not parent_path else list_idx.get(parent_path, 0)
            pending_comments = []

    def _group_of(self, parent_path: str, path: str) -> str:
        """分组名：顶层第一段。配置页会再按 CONFIG_GROUPS 重排，这里只是兜底。"""
        base = path.split(".")[0]
        b = base.split("[")[0]
        return b or "其它"

    # ── 改值 ──
    def set_value(self, leaf: YLeaf, new_value: str):
        """只替换该行 [vstart, vend) 区间的字符。"""
        # 值没变就一个字符都不碰：标题前缀图标那类值里带的是字面反斜杠，
        # 重新拼一遍会多转义一层，字形当场就废 —— 所以「没改」必须真的不动。
        if new_value == leaf.value:
            return
        line = self.lines[leaf.line]
        v = new_value
        need_quote = leaf.quote or ('#' in v) or v.strip() != v or (v == "")
        if need_quote:
            q = leaf.quote or '"'
            if q == "'":
                # YAML 单引号里反斜杠是普通字符，只有单引号本身要写成两个
                escaped = v.replace("'", "''")
            else:
                escaped = v.replace("\\", "\\\\").replace(q, "\\" + q)
            v = q + escaped + q
        self.lines[leaf.line] = line[:leaf.vstart] + v + line[leaf.vend:]
        # 重算这一行的值区间，方便连续修改
        new_raw, vs, ve, cm, qq = _split_value(self.lines[leaf.line], 0)
        leaf.raw = new_raw
        leaf.vstart = vs
        leaf.vend = ve
        leaf.comment = cm
        leaf.quote = qq

    # ── 保存 ──
    def save(self, backup: bool = True) -> str:
        """备份 → 写入 → 返回备份文件名。"""
        bak_name = ""
        if backup and self.path.exists():
            bak = self.path.with_name(self.path.name + ".bak-" + datetime.now().strftime("%Y%m%d%H%M%S"))
            shutil.copy2(self.path, bak)
            bak_name = bak.name

        text = self.eol.join(self.lines)
        if self.trailing_newline:
            text += self.eol
        with open(self.path, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        return bak_name

    def diff(self, bak_path) -> tuple[int, list[str]]:
        """和备份逐行比对，返回 (变化行数, 变化行摘要)。"""
        try:
            before = (Path(bak_path).read_text(encoding="utf-8")
                      .replace("\r\n", "\n").rstrip("\n").split("\n"))
            after = "\n".join(self.lines).rstrip("\n").split("\n")
        except Exception:
            return -1, []
        n = min(len(before), len(after))
        diffs = []
        for i in range(n):
            if before[i] != after[i]:
                diffs.append(f"L{i + 1}: {before[i].strip()[:60]}  →  {after[i].strip()[:60]}")
        if len(before) != len(after):
            diffs.append(f"行数变化：{len(before)} → {len(after)}")
        return len(diffs), diffs


def tip_of(leaf: YLeaf) -> str:
    """悬停提示：只写「这一项是什么、现在是什么状态」。

    键名、中文名、路径、当前值在表单里都已经写着，这里不再重复。
    """
    lines: list[str] = []

    note = (leaf.comment or "").lstrip("#").strip()
    if not note and leaf.leading:
        note = " ".join(leaf.leading[-2:])
    if note:
        lines.append(note)

    v = leaf.value.strip()
    if leaf.kind == "bool":
        pass                      # 开关状态本身就在界面上
    elif not v:
        lines.append("现在是空的——留空一般表示用主题默认值")
    elif len(v) > 40:
        lines.append("内容较长，点开单元格可看全文")

    return "\n".join(lines)
