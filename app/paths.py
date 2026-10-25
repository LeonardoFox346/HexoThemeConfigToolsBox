"""路径常量与静态配置。所有路径集中在这里，改一处即可。

运行时可以用 configure() 换成别的博客目录 / 主题配置（设置里选的），
其余模块请用 paths.BLOG 这种写法取值，别在 import 时把值拷走。
"""
import sys as _sys
from pathlib import Path


def _app_dir() -> Path:
    """资源目录：源码运行时是项目根；PyInstaller 打包后是解包目录。"""
    if getattr(_sys, "frozen", False):
        return Path(getattr(_sys, "_MEIPASS", Path(_sys.executable).parent))
    return Path(__file__).resolve().parents[1]


def _user_dir() -> Path:
    """用户目录：设置文件放这里。打包后就是 exe 所在目录，不写临时目录。"""
    if getattr(_sys, "frozen", False):
        return Path(_sys.executable).parent
    return _app_dir()


APP_DIR = _app_dir()
USER_DIR = _user_dir()


def _guess_blog() -> Path:
    """按程序所在位置猜博客目录：同级的 blog/、上一级的 blog/、或者程序目录本身就是博客。"""
    for cand in (APP_DIR / "blog", APP_DIR.parent / "blog", APP_DIR):
        try:
            if (cand / "_config.yml").exists() and (cand / "source").exists():
                return cand
        except OSError:
            pass
    return APP_DIR.parent / "blog"


DEFAULT_ROOT = APP_DIR.parent
DEFAULT_BLOG = _guess_blog()
DEFAULT_ORG = "NardoFox"

ROOT = DEFAULT_ROOT
BLOG = DEFAULT_BLOG
POSTS = BLOG / "source" / "_posts"
DATA_DIR = BLOG / "source" / "_data"
PUBLIC = BLOG / "public"

CONFIG_YML = BLOG / "_config.anzhiyu.yml"
PUBLISH_PS1 = BLOG / "publish.ps1"
PUBLISH_LOG = BLOG / "publish.log"
HEXO_CLI = BLOG / "node_modules" / "hexo-cli" / "bin" / "hexo"
PUBLIC_CSS = PUBLIC / "css" / "index.css"

PREVIEW_URL = "http://127.0.0.1:4173"
SERVER_NAME = "blog-server"

CATEGORIES = ["科技", "学习", "游戏", "生活"]

# 五个数据页：(标题, 文件)。configure() 会就地改这个列表，别重新赋值。
DATA_PAGES = [
    ("关于页数据", DATA_DIR / "about.yml"),
    ("装备", DATA_DIR / "equipment.yml"),
    ("友链增删", DATA_DIR / "link.yml"),
    ("相册", DATA_DIR / "album.yml"),
    ("技能", DATA_DIR / "creativity.yml"),
]


def configure(blog_root=None, config_path=None):
    """按设置换博客目录 / 主题配置。必须在建界面之前调用。"""
    global BLOG, POSTS, DATA_DIR, PUBLIC, CONFIG_YML
    global PUBLISH_PS1, PUBLISH_LOG, HEXO_CLI, PUBLIC_CSS

    blog = Path(blog_root) if blog_root else DEFAULT_BLOG
    BLOG = blog
    POSTS = blog / "source" / "_posts"
    DATA_DIR = blog / "source" / "_data"
    PUBLIC = blog / "public"
    if config_path:
        CONFIG_YML = Path(config_path)
    else:
        CONFIG_YML = blog / "_config.anzhiyu.yml"
        if not CONFIG_YML.exists():
            # 别的主题不一定叫 anzhiyu：退而求其次找 _config.*.yml，再不行用站点主配置
            cands = sorted(p for p in blog.glob("_config.*.yml") if p.is_file())
            CONFIG_YML = cands[0] if cands else blog / "_config.yml"
    PUBLISH_PS1 = blog / "publish.ps1"
    PUBLISH_LOG = blog / "publish.log"
    HEXO_CLI = blog / "node_modules" / "hexo-cli" / "bin" / "hexo"
    PUBLIC_CSS = PUBLIC / "css" / "index.css"

    try:
        from . import settings
        base = Path(settings.get("data_dir").strip() or DATA_DIR)
    except Exception:
        base = DATA_DIR
    if not base.is_absolute():
        base = DATA_DIR / base

    def _data_path(key: str, filename: str) -> Path:
        try:
            from . import settings
            v = settings.get(key).strip()
        except Exception:
            v = ""
        if v:
            p = Path(v)
            return p if p.is_absolute() else base / p
        return base / filename

    DATA_PAGES[:] = [
        ("关于页数据", _data_path("data_about", "about.yml")),
        ("装备", _data_path("data_equipment", "equipment.yml")),
        ("友链增删", _data_path("data_link", "link.yml")),
        ("相册", _data_path("data_album", "album.yml")),
        ("技能", _data_path("data_skills", "creativity.yml")),
    ]


# 配置文件的界面分组：组名 -> 该组包含的顶层 key。
# 未列出的 key 会落到「其它」组里。
CONFIG_GROUPS = [
    ("首页", "home_top index_img index_site_info_top index_top_img_height "
             "index_post_content subtitle greetingBox ptool newest_comments "
             "console_banner centerConsole"),
    ("文章页", "post_meta toc anchor wordcount post_copyright reward related_post "
              "post_pagination noticeOutdate sharejs photofigcaption "
              "post_head_ai_description disable_top_img default_top_img error_img "
              "error_404 error_pages copy code_word_wrap highlight_theme "
              "highlight_copy highlight_lang highlight_shrink highlight_height_limit cover"),
    ("侧栏与右侧按钮", "aside sidebar rightside_item_order rightside-bottom "
                     "shortcutKey accesskey"),
    ("页脚", "footer footer_bg busuanzi runtimeshow site_verification author_status mourn"),
    ("导航与菜单", "menu nav_music music_page_default aplayerInject friends_vue "
                 "linkPageTop social"),
    ("搜索", "local_search"),
    ("评论", "comments giscus comment_barrage_config"),
    ("统计与分析", "baidu_analytics google_analytics cnzz_analytics cloudflare_analytics "
                 "microsoft_clarity google_adsense umami LA"),
    ("特效与装饰", "canvas_ribbon canvas_fluttering_ribbon canvas_nest activate_power_mode "
                 "fireworks click_heart ClickShowText universe bubble peoplecanvas "
                 "dynamicEffect rightClickMenu diytitle mainTone"),
    ("插件与交互", "pjax lazyload instantpage pangu snackbar note mermaid medium_zoom "
                 "fancybox translate Open_Graph_meta agreementPopup pageThumbnailSuffix "
                 "visitorMail mathjax katex pwa icons"),
    ("客服与第三方", "chat_btn chat_hide_show chatra tidio daovoice crisp"),
    ("外观与主题", "theme_color darkmode display_mode beautify font blog_title_font hr_icon "
                 "preloader readmode h2Divider table_interlaced_discoloration "
                 "article_double_row category_ui tag_ui css_prefix"),
    ("注入与 CDN", "CDN inject"),
    ("其它", "favicon apple_touch_icon avatar"),
]

# 中文名对照：把常见的英文 key 翻成人话
ZH_KEY = {
    "enable": "开启", "title": "标题", "subtitle": "副标题", "icon": "图标",
    "text": "文字", "content": "内容", "desc": "描述", "link": "链接",
    "url": "地址", "href": "地址", "name": "名称", "img": "图片",
    "avatar": "头像", "cover": "封面", "color": "颜色", "size": "大小",
    "height": "高度", "width": "宽度", "top": "顶部", "left": "左侧",
    "right": "右侧", "bottom": "底部", "position": "位置", "style": "样式",
    "path": "路径", "page": "页面", "pages": "页面", "menu": "菜单",
    "social": "社交", "comment": "评论", "comments": "评论", "share": "分享",
    "search": "搜索", "music": "音乐", "player": "播放器", "cdn": "CDN",
    "inject": "注入", "head": "头部", "body": "正文", "footer": "页脚",
    "chat": "聊天", "analytics": "统计", "mode": "模式", "theme": "主题",
    "font": "字体", "icon_font": "图标字体", "loading": "加载",
    "lazyload": "懒加载", "pjax": "PJAX", "notice": "公告", "reward": "打赏",
    "copyright": "版权", "tags": "标签", "categories": "分类", "date": "日期",
    "author": "作者", "email": "邮箱", "site": "站点", "site_name": "站点名",
    "index": "首页", "post": "文章", "archive": "归档", "category": "分类",
    "tag": "标签", "about": "关于", "friend": "友链", "album": "相册",
    "equipment": "装备", "creativity": "创造力", "darkmode": "深色模式",
    "display_mode": "显示模式", "beautify": "美化", "preloader": "预加载",
    "readmode": "阅读模式", "wordcount": "字数统计", "toc": "目录",
}
