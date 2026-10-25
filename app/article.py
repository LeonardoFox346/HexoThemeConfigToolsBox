"""文章读写：扫描 _posts，解析 Front Matter，正文改完原样写回。

Front Matter 原文整段保留，保存时一字不动 —— 只替换正文部分。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .paths import POSTS


def _parse_fm(lines: list[str]) -> tuple[dict, list[str]]:
    """把 front matter 行解析成 (dict, 键顺序)。"""
    fm: dict = {}
    order: list[str] = []
    cur_key = None
    for raw in lines:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        s = raw.rstrip()
        indent = len(s) - len(s.lstrip(" "))
        if indent == 0 and ":" in s:
            k, _, v = s.partition(":")
            k = k.strip()
            v = v.strip()
            cur_key = k
            if k not in fm:
                order.append(k)
            if v:
                fm[k] = _strip_quotes(v)
            else:
                fm[k] = []
                cur_key = k
        elif s.lstrip().startswith("-") and cur_key is not None:
            item = s.lstrip()[1:].strip()
            if isinstance(fm.get(cur_key), list):
                fm[cur_key].append(_strip_quotes(item))
            else:
                fm[cur_key] = [_strip_quotes(item)]
    return fm, order


def _strip_quotes(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1]
    return s


@dataclass
class Article:
    path: Path
    fm_lines: list[str] = field(default_factory=list)
    body: str = ""
    fm: dict = field(default_factory=dict)
    order: list[str] = field(default_factory=list)
    body_dirty: bool = False
    # 首尾那两条 --- 原本用的换行符：混了 CRLF 的文件也要逐字节还原
    eol_head: str = "\n"
    eol_close: str = "\n"

    # ── 便捷属性 ──
    @property
    def title(self) -> str:
        t = self.fm.get("title", "")
        if isinstance(t, list):
            t = " ".join(t)
        return str(t).strip() or self.path.stem

    @property
    def date(self) -> str:
        d = self.fm.get("date", "")
        if isinstance(d, list):
            d = ""
        return str(d).strip()

    @property
    def categories(self) -> list[str]:
        c = self.fm.get("categories", [])
        return c if isinstance(c, list) else [str(c)]

    @property
    def tags(self) -> list[str]:
        t = self.fm.get("tags", [])
        return t if isinstance(t, list) else [str(t)]

    @property
    def cover(self) -> str:
        c = self.fm.get("cover", "")
        return "" if isinstance(c, list) else str(c).strip()

    @property
    def description(self) -> str:
        d = self.fm.get("description", "")
        return "" if isinstance(d, list) else str(d).strip()

    @property
    def author(self) -> str:
        a = self.fm.get("author", "")
        return "" if isinstance(a, list) else str(a).strip()

    @property
    def word_count(self) -> int:
        txt = re.sub(r"```.*?```", "", self.body, flags=re.S)
        txt = re.sub(r"[#>*`\-\[\]()!]", "", txt)
        cn = len(re.findall(r"[\u4e00-\u9fff]", txt))
        en = len(re.findall(r"[A-Za-z0-9]+", txt))
        return cn + en

    # ── 读写 ──
    @classmethod
    def load(cls, path: Path) -> "Article":
        path = Path(path)
        # newline="" 关掉换行翻译：文件里某一行是 CRLF、其余是 LF 时也要原样写回。
        # 否则保存一次就会把那一行悄悄改成 LF，git 里多出一条没动过的改动。
        with open(path, "r", encoding="utf-8", newline="") as f:
            text = f.read()
        lines = text.split("\n")
        a = cls(path=path)
        if lines and lines[0].strip() == "---":
            a.eol_head = "\r\n" if lines[0].endswith("\r") else "\n"
            for i in range(1, len(lines)):
                if lines[i].strip() == "---":
                    a.fm_lines = lines[1:i]
                    a.eol_close = "\r\n" if lines[i].endswith("\r") else "\n"
                    a.body = "\n".join(lines[i + 1:])
                    break
            else:
                a.fm_lines = []
                a.body = text
        else:
            a.body = text
        a.fm, a.order = _parse_fm(a.fm_lines)
        return a

    # ── 改 Front Matter（只动该字段占的那几行，别的字段一字不动）──
    def _field_range(self, key: str):
        """返回 key 字段在 fm_lines 里占的区间 [start, end)。找不到返回 (-1, -1)。

        一个字段的范围 = 它自己那一行 + 后面所有缩进的行（列表项、嵌套子键），
        直到遇到下一个顶格的新字段为止。
        """
        start = -1
        for i, ln in enumerate(self.fm_lines):
            if re.match(rf"^{re.escape(key)}\s*:", ln):
                start = i
                break
        if start < 0:
            return (-1, -1)

        end = len(self.fm_lines)
        for j in range(start + 1, len(self.fm_lines)):
            ln = self.fm_lines[j]
            if not ln.strip():
                continue
            if ln[0] not in " \t":        # 顶格 = 下一个字段
                end = j
                break
        return (start, end)

    def _reparse(self):
        self.fm, self.order = _parse_fm(self.fm_lines)

    def fm_set(self, key: str, value: str):
        """改单值字段。布尔/数字原样写，含 # 或以特殊符号开头才加引号。"""
        v = (value or "").strip()
        plain = False
        if v:
            low = v.lower()
            if low in ("true", "false", "null", "~") or re.fullmatch(r"-?\d+(\.\d+)?", v):
                plain = True
        if v and not plain and ("#" in v or v != value.strip()
                                or v.startswith(("[", "{", "*", "&", "!", "|", ">", "%", "@"))):
            v = chr(34) + v.replace(chr(92), chr(92) * 2).replace(chr(34), chr(92) + chr(34)) + chr(34)
        line = f"{key}: {v}" if v else f"{key}:"
        s, e = self._field_range(key)
        if s < 0:
            self.fm_lines.append(line)
        else:
            self.fm_lines[s:e] = [line]
        self._reparse()

    def fm_set_list(self, key: str, items):
        """改列表字段（categories / tags）。"""
        items = [x.strip() for x in items if x and x.strip()]
        new = ([f"{key}:"] + [f"  - {x}" for x in items]) if items else [f"{key}: []"]
        s, e = self._field_range(key)
        if s < 0:
            self.fm_lines.extend(new)
        else:
            self.fm_lines[s:e] = new
        self._reparse()

    def fm_set_nested(self, key: str, sub: str, value: str):
        """改嵌套字段，例如 copyright.type。

        已有该子键就只换那一行；没有就插在父键下面。
        """
        v = (value or "").strip()
        s, e = self._field_range(key)
        if s < 0:
            self.fm_lines.extend([f"{key}:", f"  {sub}: {v}"])
            self._reparse()
            return
        for j in range(s + 1, e):
            ln = self.fm_lines[j]
            if re.match(rf"^\s+{re.escape(sub)}\s*:", ln):
                indent = ln[: len(ln) - len(ln.lstrip())]
                self.fm_lines[j] = f"{indent}{sub}: {v}"
                self._reparse()
                return
        self.fm_lines.insert(s + 1, f"  {sub}: {v}")
        self._reparse()

    def fm_get_nested(self, key: str, sub: str) -> str:
        """读嵌套字段，例如 copyright.type。"""
        s, e = self._field_range(key)
        if s < 0:
            return ""
        for j in range(s + 1, e):
            m = re.match(rf"^\s+{re.escape(sub)}\s*:\s*(.*)$", self.fm_lines[j])
            if m:
                return _strip_quotes(m.group(1))
        return ""
    def render(self) -> str:
        if not self.fm_lines:
            return self.body
        head = ("---" + self.eol_head + "\n".join(self.fm_lines)
                + "\n" + "---" + self.eol_close)
        return head + self.body

    def save(self, backup: bool = True) -> None:
        if backup and self.path.exists():
            bak = self.path.with_name(
                self.path.name + ".bak-" + datetime.now().strftime("%Y%m%d%H%M%S"))
            bak.write_bytes(self.path.read_bytes())
        with open(self.path, "w", encoding="utf-8", newline="") as f:
            f.write(self.render())
        self.body_dirty = False


def scan() -> list[Article]:
    """扫描 _posts，按日期倒序。解析失败的单篇跳过，不影响其它。"""
    out: list[Article] = []
    if not POSTS.exists():
        return out
    for p in POSTS.glob("*.md"):
        try:
            out.append(Article.load(p))
        except Exception:
            continue

    def key(a: Article):
        d = a.date[:10].replace("-", "")
        if len(d) == 8 and d.isdigit():
            return d
        return datetime.fromtimestamp(a.path.stat().st_mtime).strftime("%Y%m%d")

    out.sort(key=key, reverse=True)
    return out


def new_path(title: str) -> Path:
    """按标题生成文件名：保留中文，去掉路径非法字符。"""
    slug = re.sub(r'[\\/:*?"<>|\s]+', "-", title.strip()).strip("-")
    if not slug:
        slug = "post"
    return POSTS / f"{slug}.md"


def create(title: str, category: str = "科技", tags: str = "", cover: str = "",
           date: str = "", description: str = "", copyright: str = "",
           author: str = "", seed: str = "") -> Article:
    """新建一篇文章（只建对象，不落盘，等用户点保存）。

    空字段就不写进 Front Matter —— 免得生成一堆 `key:` 空行。
    """
    path = new_path(title)
    n = 1
    while path.exists():
        path = new_path(f"{title}-{n}")
        n += 1

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fm = [f"title: {title}"]
    fm.append(f"date: {date or now}")

    cat = (category or "").strip()
    if cat:
        fm.extend(["categories:", f"  - {cat}"])

    tag_list = [t.strip() for t in re.split(r"[,，、\s]+", tags) if t.strip()]
    if tag_list:
        fm.append("tags:")
        fm.extend(f"  - {t}" for t in tag_list)

    if cover.strip():
        fm.append(f"cover: {cover.strip()}")
    if description.strip():
        fm.append(f"description: {description.strip()}")
    if copyright.strip():
        fm.extend(["copyright:", f"  type: {copyright.strip()}"])
    if author.strip():
        fm.append(f"author: {author.strip()}")

    a = Article(path=path)
    a.fm_lines = fm
    a.body = (seed.strip() + "\n\n" if seed.strip() else "") + "正文从这里开始。\n"
    a.fm, a.order = _parse_fm(fm)
    a.body_dirty = True
    return a
