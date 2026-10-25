"""人话层：把 YAML 的英文键名翻成「我知道我要改什么」，再补上说明/建议值/默认值。

分三块：
  CN      键名 → 中文名（界面左边那列显示这个）
  DESC    键名 → 一句话说明（气泡第一行）
  ENUMS   键名 → [(值, 人话)]，有这一项就用下拉框，不再让人手打

原则：拿不准就退回原键名，绝不瞎编；说明只写"改了会发生什么"。
"""
from __future__ import annotations

# ── 键名 → 中文名 ──
CN = {
    # 通用
    "enable": "开启", "title": "标题", "subtitle": "副标题", "text": "文字",
    "desc": "描述", "description": "描述", "content": "内容", "name": "名称",
    "icon": "图标", "color": "颜色", "link": "链接", "url": "地址", "href": "地址",
    "img": "图片", "image": "图片", "avatar": "头像", "cover": "封面",
    "class_name": "分类名称", "class_desc": "分类描述", "flink_style": "卡片排列",
    "hundredSuffix": "后缀", "link_list": "友链条目",
    "good_things": "装备分组", "equipment_list": "装备条目",
    "creativity_list": "技能条目", "album_list": "相册照片",
    "path_name": "页面路径", "type": "类型", "rowHeight": "行高",
    "limit": "显示数量", "lazyload": "懒加载", "btnLazyload": "按钮懒加载",
    "top_link": "顶部按钮链接", "top_btn_text": "顶部按钮文字",
    "top_background": "顶部背景图", "specification": "规格",
    "address": "地点", "from": "投稿人", "date": "日期",
    "menu": "菜单", "social": "社交", "footer": "页脚",
    # 主题常见
    "index_img": "首页顶部大图", "index_site_info_top": "主页标题距顶距离",
    "index_top_img_height": "主页大图高度", "index_post_content": "首页文章摘要",
    "index_post_content.method": "摘要方式", "index_post_content.length": "摘要长度",
    "startDelay": "启动延迟", "typeSpeed": "打字速度", "backSpeed": "回退速度",
    "loop": "循环播放", "source": "来源", "effect": "特效",
    "method": "方法", "length": "长度",
    "newest_comments": "最新评论", "storage": "存储天数",
    "console_banner": "控制台横幅", "light": "浅色版", "dark": "深色版",
    "light_local": "浅色本地图", "dark_local": "深色本地图",
    "centerConsole": "居中控制台", "highlight_theme": "代码高亮主题",
    "highlight_copy": "复制按钮", "highlight_lang": "语言标签",
    "highlight_shrink": "折叠代码", "highlight_height_limit": "折叠高度",
    "code_word_wrap": "代码换行", "post_meta": "文章元信息",
    "toc": "目录", "anchor": "锚点", "wordcount": "字数统计",
    "reward": "打赏", "related_post": "相关推荐", "sharejs": "分享",
    "comments": "评论", "giscus": "Giscus", "comment_barrage_config": "弹幕",
    "local_search": "本地搜索", "darkmode": "深色模式",
    "display_mode": "显示模式", "beautify": "美化", "title-prefix-icon": "标题前缀图标",
    "title-prefix-icon-color": "标题前缀颜色", "font": "字体",
    "blog_title_font": "博客标题字体", "preloader": "预加载",
    "readmode": "阅读模式", "pjax": "PJAX", "instantpage": "预加载下一页",
    "lazyload": "图片懒加载", "pangu": "中英文加空格", "snackbar": "通知条",
    "note": "提示块", "mermaid": "流程图", "mathjax": "数学公式",
    "katex": "KaTeX 公式", "fancybox": "图片灯箱", "medium_zoom": "图片缩放",
    "translate": "翻译", "Open_Graph_meta": "OG 卡片", "pwa": "PWA",
    "icons": "图标", "chat_btn": "客服按钮", "canvas_ribbon": "彩带背景",
    "canvas_fluttering_ribbon": "飘带背景", "canvas_nest": "蛛网背景",
    "activate_power_mode": "性能模式", "fireworks": "烟花", "click_heart": "点击爱心",
    "ClickShowText": "点击显示文字", "universe": "星空背景", "bubble": "气泡",
    "peoplecanvas": "人物画布", "dynamicEffect": "动态效果",
    "rightClickMenu": "右键菜单", "diytitle": "标题动画", "mainTone": "主色调",
    "copyright": "版权", "post_copyright": "文章版权", "noticeOutdate": "过期提醒",
    "photofigcaption": "图片说明", "post_pagination": "上下篇",
    "disable_top_img": "关闭顶部图", "default_top_img": "默认顶部图",
    "error_img": "错误页图片", "error_404": "404 页面", "error_pages": "错误页",
    "copy": "复制", "aside": "侧栏", "sidebar": "侧边栏",
    "rightside_item_order": "右侧按钮顺序", "shortcutKey": "快捷键",
    "accesskey": "快捷键", "busuanzi": "访问统计", "runtimeshow": "运行时间",
    "site_verification": "站点验证", "author_status": "作者状态",
    "mourn": "哀悼模式", "nav_music": "导航音乐", "music_page_default": "音乐页默认",
    "aplayerInject": "播放器注入", "friends_vue": "友链 Vue", "linkPageTop": "友链顶部",
    "addFriendPlaceholder": "添加友链提示", "agreementPopup": "同意弹窗",
    "pageThumbnailSuffix": "缩略图后缀", "visitorMail": "访客邮箱",
    "baidu_analytics": "百度统计", "google_analytics": "谷歌统计",
    "cnzz_analytics": "友盟统计", "cloudflare_analytics": "Cloudflare 统计",
    "microsoft_clarity": "Clarity", "google_adsense": "谷歌广告", "umami": "Umami",
    "LA": "LA 统计", "CDN": "CDN", "inject": "注入代码",
    "theme_color": "主题色", "hr_icon": "分隔线图标", "h2Divider": "二级标题分隔线",
    "table_interlaced_discoloration": "表格斑马纹", "article_double_row": "双栏文章",
    "category_ui": "分类页样式", "tag_ui": "标签页样式", "css_prefix": "CSS 前缀",
    "chatra": "Chatra", "tidio": "Tidio", "daovoice": "DaoVoice",
    "crisp": "Crisp", "giscus_js": "Giscus 脚本",
}

# ── 一句话说明：只说「改了会怎样」──
DESC = {
    "enable": "总开关。关掉之后这一块在站上就不出现了。",
    "flink_style": "友链卡片的排列方式：flexcard 是卡片平铺，telescopic 是可展开的长条，anzhiyu 是安知鱼默认样式。",
    "class_name": "这一组的大分类名字，会显示在友链页顶部。",
    "class_desc": "大分类下面那句小字说明。",
    "hundredSuffix": "条目很多时显示的数字后缀，留空就行。",
    "link_list": "这一组里的友链条目，加一条就多一个朋友。",
    "name": "显示出来的名字。",
    "link": "点它跳到哪。站内用 /xxx，站外用完整 https 地址。",
    "avatar": "头像图片地址。",
    "descr": "一句个性签名，显示在名字下面。",
    "good_things": "装备页的分组，比如「生产力」「出行」。",
    "equipment_list": "这一组里的具体装备。",
    "specification": "配置/规格，比如 32G / 1TB。",
    "creativity_list": "技能图标列表，首页「技能」那块用。",
    "album_list": "这个相册里的照片条目。",
    "image": "图片地址；相册里可以写多条。",
    "date": "照片拍摄/收录时间。",
    "content": "照片配的文字。",
    "address": "拍摄地点。",
    "from": "谁拍的/谁投的。",
    "path_name": "这个相册页的地址后缀，比如 /dailyPhoto。",
    "type": "相册的展示类型（数字），不确定就别动。",
    "rowHeight": "每行照片的高度（像素）。",
    "limit": "一次加载多少张。",
    "top_link": "顶部按钮点一下去哪。",
    "top_btn_text": "顶部按钮上的字。",
    "top_background": "页面顶部的背景图地址。",
    "index_img": "首页最上面那张大图。留空就用主题默认。",
    "index_site_info_top": "主页标题离页面顶部的距离，单位 px，比如 300px。",
    "index_top_img_height": "主页大图的高度，比如 300px 或 100vh。",
    "index_post_content.method": "摘要怎么取：3 = 自动截取，1/2 是其它取法，保持现在的值就行。",
    "index_post_content.length": "自动截取时保留多少字。",
    "subtitle.enable": "首页副标题打字机效果的开关。",
    "subtitle.effect": "打字机特效开关，跟着上面的总开关走。",
    "subtitle.startDelay": "页面打开后多久开始打字，单位毫秒。",
    "subtitle.typeSpeed": "每个字打出来的速度，越小越快。",
    "subtitle.backSpeed": "删除时的速度。",
    "subtitle.loop": "打完是否循环重来。",
    "subtitle.source": "副标题从哪来：1 = 用下面自定义的那句。",
    "subtitle.sub": "自己写的那句副标题，只有 source 选自定义时才显示。",
    "highlight_theme": "代码块的配色方案，ocean / mac / pale night 这些。",
    "highlight_copy": "代码块右上角那个复制按钮。",
    "highlight_lang": "代码块左上角显示语言名。",
    "highlight_shrink": "代码太长时默认折叠。",
    "highlight_height_limit": "超过多少像素就折叠。",
    "code_word_wrap": "代码自动换行，关掉会出现横向滚动条。",
    "comments": "评论系统开关与外观。",
    "use": "评论后端名字。留空 = 不启用评论。",
    "darkmode": "深色模式跟随系统还是手动。",
    "display_mode": "默认亮色还是暗色。",
    "beautify": "标题美化，会加个图标前缀。",
    "title-prefix-icon": "标题前面那个小图标，是字体码点，别随手改。",
    "font": "全站字体设置。",
    "preloader": "页面加载时的过场动画。",
    "readmode": "阅读模式按钮。",
    "pjax": "无刷新跳页，站内切换更快。",
    "instantpage": "鼠标悬停就预加载下一页。",
    "lazyload": "图片滚到才加载，省流量。",
    "pangu": "自动在中英文之间加空格。",
    "snackbar": "右下角弹的小通知。",
    "mermaid": "支持流程图语法。",
    "mathjax": "支持数学公式。",
    "katex": "另一种公式渲染，比 MathJax 快。",
    "fancybox": "点图片全屏看。",
    "rightClickMenu": "自定义右键菜单。",
    "menu": "顶部导航菜单；每一项是「地址 || 图标」。",
    "social": "社交图标那一排。",
    "footer": "页脚内容。",
    "local_search": "站内搜索，开启后右上角有搜索框。",
    "busuanzi": "访问量统计（不蒜子）。",
    "runtimeshow": "页脚显示站点运行了多久。",
}

# ── 有固定选项的键：给下拉框，别让人手打 ──
ENUMS = {
    "flink_style": [("flexcard", "卡片平铺"), ("telescopic", "可展开长条"), ("anzhiyu", "安知鱼默认")],
    "highlight_theme": [("ocean", "ocean"), ("pale night", "pale night"), ("light", "light"),
                        ("mac", "mac"), ("mac light", "mac light"), ("false", "关闭")],
    "display_mode": [("light", "亮色"), ("dark", "暗色")],
    "darkmode": [],
    "type": [],
}

# 数值项的合理范围（只用来给建议，不做强制校验）
RANGE = {
    "index_post_content.length": (20, 1000, "一般 200–500"),
    "subtitle.startDelay": (0, 5000, "一般 0–500"),
    "subtitle.typeSpeed": (20, 500, "一般 100–200"),
    "subtitle.backSpeed": (10, 500, "一般 30–100"),
    "highlight_height_limit": (100, 2000, "一般 200–400"),
    "limit": (1, 30, "一次别超过 30 张"),
    "rowHeight": (100, 600, "一般 200–300"),
}


# ── 补一轮：主题配置里剩下的常见键 ──
CN.update({
    "descr": "签名", "tip": "提示文字", "tips": "提示", "mobile": "移动端",
    "greeting": "问候语", "startTime": "开始时间", "endTime": "结束时间",
    "position": "位置", "per_page": "每页数量", "date_type": "日期类型",
    "categories": "分类", "default": "默认", "zIndex": "层级", "field": "区域",
    "path": "路径", "shadow": "阴影", "class": "自定义类名",
    "apple_touch_icon": "苹果图标", "search": "搜索", "date_format": "日期格式",
    "tags": "标签", "label": "文字", "mode": "模式", "expand": "默认展开",
    "style": "样式", "count": "数量", "archive": "归档", "tag": "标签",
    "category": "分类", "button": "按钮", "show_more": "显示更多",
    "more_text": "更多文字", "format": "格式", "order": "排序", "version": "版本",
    "days": "天数", "limit_count": "字数限制", "BiliBili": "B站",
    "statusImg": "状态图", "preload": "预加载", "hide_scrollbar": "隐藏滚动条",
    "favicon": "网站图标", "index_enable": "首页启用", "aside_enable": "侧栏启用",
    "archives_enable": "归档页启用", "flink": "友链", "post_page": "文章页",
    "charity": "公益 404", "chrome": "浏览器", "unread": "未读",
    "api": "接口地址", "cover_change": "封面跟随", "post_wordcount": "本文字数",
    "min2read": "阅读时长", "total_wordcount": "全站字数", "post": "文章",
    "page": "页面", "number": "编号", "style_simple": "简洁样式", "decode": "加密",
    "location": "位置", "license": "许可协议", "license_url": "协议链接",
    "avatarSinks": "头像下沉", "copyright_author_link": "作者链接",
    "custom": "自定义", "QR_code": "二维码", "limit_day": "限制天数",
    "message_prev": "上一篇文字", "message_next": "下一篇文字", "sites": "分享平台",
    "card_post_count": "卡片文章数", "repo": "仓库", "repo_id": "仓库 ID",
    "category_id": "分类 ID", "custom_text": "自定义文字", "auto_ads": "自动广告",
    "enable_page_level_ads": "页级广告", "main": "主色", "dark_main": "深色主色",
    "paginator": "分页器", "text_selection": "选中文字", "link_color": "链接颜色",
    "meta_color": "元信息颜色", "hr_color": "分隔线颜色",
    "code_foreground": "代码前景色", "code_background": "代码背景色",
    "toc_color": "目录颜色", "scrollbar_color": "滚动条颜色",
    "menus_items": "菜单项", "tags_cloud": "标签云", "nav_menu_project": "导航项目",
    "footer_bg": "页脚背景", "size": "大小", "alpha": "透明度",
    "click_to_change": "点击切换", "opacity": "不透明度", "colorful": "多彩",
    "shake": "抖动", "fontSize": "字号", "random": "随机",
    "global-font-size": "全站字号", "code-font-family": "代码字体",
    "font-family": "字体", "hide": "隐藏", "name_link": "名字链接",
    "face": "正面图", "backFace": "背面图", "sort": "排序",
    "post_count": "文章数", "last_push_date": "最后更新", "site_uv": "访客数",
    "site_pv": "浏览量", "page_pv": "本页浏览", "publish_date": "建站时间",
    "autoChangeMode": "自动切换", "border_radius": "圆角",
    "light_bg_offset": "浅色底偏移", "fontawesome": "图标字体",
    "bg_light": "浅色背景", "bg_dark": "深色背景", "blur": "模糊",
    "progressive": "渐进加载", "startup_image_enable": "启动图",
    "manifest": "清单文件", "mask_icon": "遮罩图标", "bookmark_icon": "书签图标",
    "timemode": "时间模式", "siteText": "站点文字", "default_descr": "默认描述",
    "swiper_css": "轮播 CSS", "swiper_js": "轮播 JS", "vue_js": "Vue 脚本",
    "top_tips": "顶部提示", "leaveTitle": "离开时的标题",
    "backTitle": "回来时的标题", "maxBarrage": "弹幕上限",
    "barrageTime": "弹幕时长", "accessToken": "访问令牌", "mailMd5": "邮箱 MD5",
    "id": "ID", "server": "服务商", "volume": "音量", "all_playlist": "全部歌单",
    "mail": "邮箱", "delay": "延迟", "shiftDelay": "长按延迟",
    "buttonAgree": "同意按钮", "buttonDecline": "拒绝按钮",
    "internal_provider": "站内 CDN", "third_party_provider": "第三方 CDN",
    "meting_api": "音乐接口", "avatarImg": "头像", "title1": "标题一",
    "title2": "标题二", "helloAbout": "招呼语", "StrengthenTitle": "强化标题",
    "background": "背景", "backgroundDark": "深色背景", "author_name": "名字",
    "personality_type": "性格类型", "photo_url": "图片地址",
    "personality_img": "性格图片", "name_url": "名字链接", "amount": "金额",
    "datatime": "时间", "reward_list": "赞赏列表", "aboutsiteTips": "关于本站提示",
    "avatarSkills": "头像旁技能", "selfInfo": "个人信息", "personalities": "性格",
    "maxim": "格言", "buff": "加成", "comic": "追番", "like": "喜好",
    "music": "音乐", "map": "地图", "careers": "经历", "statistic": "统计",
    "comic_list": "追番条目", "description_list": "说明条目",
    "home_top": "首页顶部", "post_head_ai_description": "AI 摘要",
    "ptool": "分享工具", "friends_vue": "友链页", "album_list": "相册条目",
})

# ── 固定选项 ──
ENUMS.update({
    "post_meta.page.date_type": [
        ("date", "显示日期"), ("relative", "显示「几天前」")],
    "date_type": [("date", "日期"), ("relative", "相对时间")],
    "mode": [("auto", "跟随系统"), ("light", "亮色"), ("dark", "暗色")],
    "toc.expand": [("true", "默认展开"), ("false", "默认收起")],
    "order": [("asc", "正序"), ("desc", "倒序")],
    "sort": [("date", "按日期"), ("random", "随机"), ("hot", "按热度")],
    "hover_effect": [("", "")],
})


def human(key: str) -> str:
    """键名 → 中文名；没有就原样返回。"""
    if key.startswith("[") and key.endswith("]"):
        n = key[1:-1]
        return f"第 {int(n) + 1} 项" if n.isdigit() else key
    return CN.get(key) or CN.get(key.lower()) or key


def is_url(v: str) -> bool:
    v = (v or "").strip().lower()
    return "://" in v or v.startswith(("//", "data:")) or v.endswith(
        (".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".ico"))


def default_hint(key: str, value: str, kind: str) -> str:
    """默认值提示：只在「看一眼就知道是什么」时才写。

    图片/链接会换、自定义文字各人不同 —— 这两类一律不给默认值，免得把人带沟里。
    """
    v = (value or "").strip()
    if not v:
        return ""
    if is_url(v) or len(v) > 28 or "\n" in v:
        return ""
    if kind == "bool":
        return "开" if v.lower() in ("true", "yes", "on") else "关"
    return v


def suggest_hint(key: str, value: str, kind: str) -> str:
    """建议值：优先给固定选项/范围，其次给「留空会怎样」。"""
    opts = ENUMS.get(key) if isinstance(ENUMS.get(key), list) else None
    if opts:
        names = "、".join(v if v == n else f"{v}（{n}）" for v, n in opts if v)
        return f"可选：{names}" if names else ""
    if not (value or "").strip():
        if kind == "bool":
            return "留空按「关」处理；要开就点开开关"
        return "留空 = 用主题默认，一般就是关/不显示"
    rng = RANGE.get(key)
    if rng:
        return f"建议 {rng[2]}"
    if kind == "bool":
        return "开 / 关"
    return ""
