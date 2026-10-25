# 纳多狐狐的写作台

> Desktop companion for Hexo + Anzhiyu blogs — write posts, inspect server status, edit theme YAML, publish in one click.
> 给 Hexo + Anzhiyu（安知鱼）博客用的桌面写作台：写文章、看服务器状态、改主题配置、一键发布。

给 Hexo 博客用的桌面工具：写文章、看服务器状态、改主题配置、一键发布 —— 一个窗口搞定。

适用范围：主要适配 Hexo + Anzhiyu（安知鱼）主题，配置分组、中文说明、五个 _data 页面、发布流程都按它做。换 Butterfly 等其它 Hexo 主题只保证「能打开、能改值」，分组与说明可能对不上，_data 页面会缺席，发布以你仓库里的脚本为准。

## 功能

| 页面 | 做什么 |
|---|---|
| 首页 | 概览：文章数、未提交改动、上次发布、构建产物；最近文章可直接打开 |
| 写文章 | 文章列表 + Markdown 编辑器（高亮）+ 预览；支持新建、保存、文章信息面板 |
| 服务器状态 | 代理四路检查 + ssh 只读采集（内存 / 磁盘 / 证书 / fail2ban / 最后部署 / 今日请求） |
| 发布 | 构建 → 部署；发布前必须手动输入确认词 |
| 主题配置 | 编辑主题 yml：左边大分类、右边一个类型一块；开关、下拉、数字、文本按类型渲染 |
| 数据页 | 关于页数据 / 装备 / 友链增删 / 相册 / 技能（source/_data/*.yml），支持条目增删与大分类移动 |
| 导入 yml 配置 | 任选一个现成 yml 加进导航；能解析就按表单显示，解析不出来就按原文显示 |
| 赞赏与支持 | 底部心形按钮，显示内置赞赏码（完全自愿，不影响功能） |

## 安装

- Windows：下载 NardoFoxWriteDesk-Setup-x.y.exe 双击安装。默认装到当前用户目录，不需要管理员权限；自带卸载程序。
- 绿色版：解压 NardoFoxWriteDesk-x.y-win64.zip，运行 NardoFoxWriteDesk.exe。

> 精简版不含 QtWebEngine，写文章页的「样式预览」按钮会自动禁用；轻量预览不受影响。

## 首次启动

第一次运行会进入引导，共 8 步：

1. 欢迎与环境自检（Python / PySide6 / Node / Git / hexo-cli / node_modules / 字体）
2. 软件使用许可协议（需勾选同意）
3. 博客目录（校验 _config.yml、source/_posts、package.json）
4. 主题配置（自动扫描 _config.*.yml）
5. 服务器与发布（可整屏跳过，随时可在设置里补）
6. 外观（四套主题 + 跟随系统，立即生效）
7. 开源与致谢（需勾选已阅读）
8. 完成

中途点「跳过」也能进入主界面；直接关闭窗口则退出程序。

## 设置与配置文件

- 设置入口：左下角齿轮；外观入口：左下角调色盘。
- 偏好保存在程序目录的 settings.json（绿色版在 exe 同目录），原子写入。
- 可配置：外观、博客目录、主题配置文件、正文 / 代码字体、五个 _data 文件位置、服务器与 GitHub、推送方式、编辑器默认开关、侧边栏隐藏、是否退出后保留设置。
- 配置支持「导出配置… / 导入配置…」（JSON，可原样导回）。
- 编辑 yml 保存前会自动备份成 .bak-时间戳；页面顶部「回滚…」可恢复，覆盖前再存一份 .rollback-时间戳。
- 只改值所在的那几个字符，注释、顺序、缩进保持原样。

## 打包

```bash
# Windows：exe + 安装包（需要 PyInstaller；Inno Setup 可选）
powershell -ExecutionPolicy Bypass -File packaging/build_win.ps1

# Linux：.deb（含 .desktop 与 hicolor 图标）
bash packaging/linux/build_deb.sh

# macOS：.app + .dmg（必须在 macOS 上执行）
bash packaging/mac/build_dmg.sh
```

打包配置在 packaging/app.spec：onedir 模式，排除 QtWebEngine / Quick / Qml / Pdf 等未使用模块以减小体积。冒烟测试：

```bash
NardoFoxWriteDesk.exe --smoke
```

## 从源码运行

需要 Python 3.10+：

```bash
pip install PySide6 qt-material markdown pygments
python main.py
```

Windows 也可以双击 启动.bat。

## 目录结构

```
app/
  paths.py        路径与配置分组（configure() 可换博客目录）
  settings.py     用户偏好（settings.json）
  theme.py        配色与 QSS、字体加载
  fa.py           Font Awesome 图标码点
  yaml_doc.py     行级 YAML 编辑（只替换值）
  yaml_tree.py    结构化视图（块 / 列表 / 增删 / 排序）
  labels.py       键名中文名、说明与建议值
  article.py      文章 Front Matter 与正文
  md_render.py    Markdown → HTML
  remote.py       服务器只读采集与代理检查
  publish.py      构建 / 发布命令
  eula.py         软件使用许可协议
  licenses.py     许可证与第三方组件清单
  ui/             窗口与各页面
packaging/        打包脚本（PyInstaller / Inno Setup / deb / dmg）
```

## 许可证

- 本程序以 GPL-3.0-or-later 开源：可自由使用、修改、分发；分发修改版时需同样以 GPL 开源并提供源代码。见 LICENSE。
- 安装与使用还需同意 EULA.txt 中的《软件使用许可协议》；协议与 GPL 冲突时以 GPL 为准。
- 第三方组件与字体、图标许可见 THIRD-PARTY-NOTICES.md。

## 反馈与支持

- 问题与建议：https://github.com/LeonardoFox346/HexoThemeConfigToolsBox/issues
- 作者主页：https://nardofox.cn/about
- 赞赏完全自愿，不影响任何功能。
