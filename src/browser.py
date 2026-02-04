"""
浏览器自动化与页面截图
使用 Playwright 按顺序访问页面并截图
"""

import os
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


class BrowserScreenshot:
    """基于 Playwright 的页面截图"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        browser_cfg = config.get("browser", {})
        self.headless = browser_cfg.get("headless", True)
        self.viewport_width = browser_cfg.get("viewport_width", 1920)
        self.viewport_height = browser_cfg.get("viewport_height", 1080)
        self.full_page = browser_cfg.get("full_page", True)
        self.wait_after_load = browser_cfg.get("wait_after_load", 2)
        self.scroll_delay = browser_cfg.get("scroll_delay", 0.5)
        # 使用本机已安装的 Chrome，无需 playwright install；可选 "msedge" 使用 Edge
        self.channel = browser_cfg.get("channel", "chrome")
        self._playwright = None
        self._browser = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.close()

    def start(self):
        """启动浏览器（默认使用本机已安装的 Chrome，无需单独下载 Chromium）"""
        try:
            from playwright.sync_api import sync_playwright
            self._playwright = sync_playwright().start()
            # channel="chrome" 使用系统已安装的 Chrome；设为 None 则使用 Playwright 自带的 Chromium（需 playwright install）
            launch_options = {"headless": self.headless}
            if self.channel:
                launch_options["channel"] = self.channel
            self._browser = self._playwright.chromium.launch(**launch_options)
            logger.info("浏览器已启动（%s）", self.channel or "chromium")
        except ImportError:
            raise RuntimeError("请先安装 Playwright: pip install playwright")
        except Exception as e:
            if "channel" in str(e).lower() or "executable" in str(e).lower():
                raise RuntimeError(
                    "未找到本机 Chrome。请安装 Google Chrome，或在 config 的 browser 下设置 channel: null 后执行 playwright install chromium"
                ) from e
            raise

    def close(self):
        """关闭浏览器"""
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()
        logger.info("浏览器已关闭")

    def capture_pages(
        self,
        pages: List[Dict[str, str]],
        base_url: str,
        output_dir: str,
        image_format: str = "png",
        login_cookies: Optional[List[Dict[str, str]]] = None,
    ) -> List[str]:
        """
        按顺序访问页面并截图，返回截图文件路径列表。
        pages: [{"name": "首页", "url": "https://..."}, ...]
        login_cookies: 可选，[{"name","value","domain","path"}, ...]，在访问页面前注入到浏览器。
        """
        from playwright.sync_api import sync_playwright

        if not self._browser:
            self.start()

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        saved_files: List[str] = []

        context = self._browser.new_context(
            viewport={
                "width": self.viewport_width,
                "height": self.viewport_height,
            },
            ignore_https_errors=True,
        )
        page = context.new_page()

        try:
            # 若提供了 Cookie，先注入再访问页面
            if login_cookies:
                context.add_cookies(login_cookies)
                logger.info("已注入 %d 条 Cookie", len(login_cookies))

            for idx, item in enumerate(pages, 1):
                name = item.get("name", f"page_{idx}")
                url = item.get("url", "")
                if not url:
                    logger.warning(f"跳过无 URL 的项: {name}")
                    continue
                # 相对路径转绝对
                if url.startswith("/"):
                    url = urljoin(base_url.rstrip("/") + "/", url.lstrip("/"))
                elif not url.startswith("http"):
                    url = urljoin(base_url, url)

                safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in name)
                filename = f"{idx:03d}_{safe_name}.{image_format}"
                filepath = output_path / filename

                try:
                    page.goto(url, wait_until="networkidle", timeout=30000)
                    time.sleep(self.wait_after_load)
                    if self.full_page:
                        self._maybe_scroll_full_page(page)
                    page.screenshot(path=str(filepath), full_page=self.full_page)
                    saved_files.append(str(filepath))
                    logger.info(f"已截图: {name} -> {filepath}")
                except Exception as e:
                    logger.error(f"截图失败 {name} ({url}): {e}")
                    # 可选：保存空白或错误页
                    continue
        finally:
            context.close()

        return saved_files

    def _do_login(
        self,
        page,
        login_url: str,
        loginName: str,
        password: str,
        login_config: Dict[str, Any],
        base_url: str,
    ) -> None:
        """打开登录页，填写账号密码并提交。"""
        page.goto(login_url, wait_until="networkidle", timeout=30000)
        wait_before = login_config.get("wait_before_fill", 2)
        time.sleep(wait_before)

        username_sel = login_config.get("username_selector") or "input[name='loginName'], input[name='user'], input[type='text']"
        password_sel = login_config.get("password_selector") or "input[name='password'], input[type='password']"
        submit_sel = login_config.get("submit_selector") or "button[type='submit'], input[type='submit'], .btn-login, button:has-text('登录')"

        # 先等“在 DOM 中”，再尝试滚动到可见并填写（部分页面表单延迟显示或需滚动）
        try:
            page.wait_for_selector(username_sel, state="visible", timeout=15000)
        except Exception:
            page.wait_for_selector(username_sel, state="attached", timeout=10000)
            # 滚动到第一个匹配的输入框，便于显示/可操作
            try:
                page.locator(username_sel).first.scroll_into_view_if_needed(timeout=5000)
                time.sleep(0.5)
            except Exception:
                pass
        page.locator(username_sel).first.fill(loginName)
        page.locator(password_sel).first.fill(password)
        time.sleep(0.3)
        submit_el = page.query_selector(submit_sel)
        if submit_el:
            submit_el.click()
        else:
            page.keyboard.press("Enter")
        wait_after = login_config.get("wait_after_login", 3)
        time.sleep(wait_after)
        logger.info("登录步骤已执行")

    def _maybe_scroll_full_page(self, page):
        """整页截图前简单滚动以触发懒加载"""
        try:
            page.evaluate(
                """
                async () => {
                    const delay = ms => new Promise(r => setTimeout(r, ms));
                    const scrollHeight = document.documentElement.scrollHeight;
                    let pos = 0;
                    while (pos < scrollHeight) {
                        window.scrollTo(0, pos);
                        await delay(500);
                        pos += window.innerHeight;
                    }
                    window.scrollTo(0, 0);
                }
                """
            )
            time.sleep(0.5)
        except Exception:
            pass
