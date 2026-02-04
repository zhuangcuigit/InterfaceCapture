"""
菜单解析：从页面中按顺序提取菜单链接，或使用配置的页面列表
"""

import logging
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


def _flatten_pages(
    items: List[Any],
    base_url: str,
    parent_name: str = "",
) -> List[Dict[str, str]]:
    """
    将多级菜单展平为 (name, url) 列表。有 url 的为叶子；有 children 的递归展开，name 用「父级 > 子级」。
    """
    result: List[Dict[str, str]] = []
    for p in items:
        if isinstance(p, str):
            result.append({"name": p, "url": urljoin(base_url, p)})
            continue
        name = p.get("name", p.get("title", ""))
        full_name = f"{parent_name} > {name}" if parent_name else name
        url = p.get("url", p.get("href", ""))
        if url:
            if not url.startswith("http"):
                url = urljoin(base_url, url)
            result.append({"name": full_name, "url": url})
        children = p.get("children")
        if children:
            result.extend(_flatten_pages(children, base_url, full_name))
    return result


def get_pages_from_config(config: Dict[str, Any], base_url: str) -> List[Dict[str, str]]:
    """
    从配置中获取页面列表（优先使用 pages，否则用 menu_selector 从页面抓取）。
    支持多级菜单：pages 中可写 children，展平后 name 为「一级 > 二级 > 页面名」。
    返回 [{"name": str, "url": str}, ...]
    """
    pages = config.get("pages") or []
    if pages:
        return _flatten_pages(pages, base_url)

    menu_selector = config.get("menu_selector")
    if not menu_selector:
        return []

    # 从页面解析菜单
    return extract_menu_from_page(base_url, menu_selector, config.get("menu_container"))


def extract_menu_from_page(
    start_url: str,
    menu_selector: str,
    container_selector: Optional[str] = None,
) -> List[Dict[str, str]]:
    """
    使用 Playwright 打开 start_url，按 DOM 顺序提取匹配 menu_selector 的链接。
    """
    from playwright.sync_api import sync_playwright

    result: List[Dict[str, str]] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(start_url, wait_until="networkidle", timeout=30000)
            if container_selector:
                container = page.query_selector(container_selector)
                items = container.query_selector_all(menu_selector) if container else []
            else:
                items = page.query_selector_all(menu_selector)
            for node in items:
                href = node.get_attribute("href")
                text = (node.inner_text() or "").strip() or node.get_attribute("title") or ""
                if href and (href.startswith("http") or href.startswith("/") or href.startswith("#")):
                    if href.startswith("#"):
                        url = start_url + href
                    else:
                        url = urljoin(start_url, href)
                    result.append({"name": text or url, "url": url})
            browser.close()
    except Exception as e:
        logger.error(f"从页面解析菜单失败: {e}")
    return result
