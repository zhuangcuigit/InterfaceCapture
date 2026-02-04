# 平台菜单截图文档生成器

根据配置的**菜单顺序**，自动打开平台各页面、按顺序截图，并合并为一份 **PDF 文档**。

## 功能

- **按顺序截图**：按你配置的页面列表（或从页面解析的菜单）依次访问并截图  
- **整页长图**：可选整页滚动截图，适合长内容  
- **一键成 PDF**：截图自动按顺序合并为单个 PDF，便于归档或分享  

## 环境要求

- Python 3.8+
- **本机已安装 Google Chrome**（默认使用系统 Chrome，无需单独下载 Chromium）

## 安装

```bash
cd menu_screenshot_doc
pip install -r requirements.txt
```

默认使用本机已安装的 Chrome，**无需执行** `playwright install`。若希望使用 Playwright 自带的 Chromium，在配置中设置 `browser.channel: null` 后执行 `playwright install chromium`。使用 Edge 时可设置 `browser.channel: "msedge"`。

## 配置

1. 复制示例配置并修改：

   ```bash
   copy config.example.yaml config.yaml
   ```

2. 在 `config.yaml` 中填写：

   - **base_url**：平台根地址（如 `https://your-platform.com`）
   - **pages**：按菜单顺序列出的页面，每项包含 `name`（显示名）和 `url`（链接）

示例：

```yaml
base_url: "http://admin.nongyudi.com/"
pages:
  - name: "个人设置"
    url: "/account/settings"
```

若希望从页面**自动解析菜单**，可留空 `pages`，并设置 `menu_selector`（菜单链接的 CSS 选择器），详见 `config.example.yaml`。

### 需要登录时（粘贴 Cookie）

在配置中增加 `login` 段后，运行时会**提示粘贴 Cookie**，再按顺序截图。示例：

```yaml
login:
  enabled: true
  # cookie_domain 可选，不填则从 base_url 自动取
```

运行后按提示操作：
- **粘贴 Cookie 字符串**：格式为 `name1=value1; name2=value2`（可从浏览器开发者工具 → Application → Cookies 复制，或从请求头里复制 Cookie 后粘贴）。
- **或输入 Cookie JSON 文件路径**：文件内容为 `[{"name":"xx","value":"yy","domain":"..."}, ...]`。
- **留空回车**：跳过登录（需登录的页面可能截图失败）。

## 使用

```bash
# 创建虚拟环境并激活
python -m venv venv && source venv/bin/activate  # Linux/Mac
# 或: python -m venv venv && venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 修改config.yaml中的网址、菜单配置

# 截图并生成 PDF
python run.py

# 指定配置文件
python run.py -c config.yaml

# 显示浏览器窗口（便于调试或需登录）
python run.py --no-headless

# 只截图，不生成 PDF
python run.py --screenshots-only

# 仅从已有截图生成 PDF
python run.py --pdf-only
```

## 输出说明

- 截图保存在：`output/run_YYYYMMDD_HHMMSS/`，按 `001_页面名.png` 顺序命名  
- PDF 保存在：`output/平台页面文档_YYYYMMDD_HHMMSS.pdf`  

## 需要登录的平台

在 `config.yaml` 中增加 `login.enabled: true` 后，运行时会提示**粘贴 Cookie**。请先在浏览器中登录目标站点，再在开发者工具（F12）→ Application → Cookies 中复制所需 Cookie，或从请求头中复制 `Cookie:` 整段，粘贴到终端即可。

## 许可证

MIT
