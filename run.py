#!/usr/bin/env python3
"""
根据菜单对平台页面按顺序截图并生成 PDF 文档
用法:
  python run.py                    # 使用 config.yaml
  python run.py -c my_config.yaml  # 指定配置文件
  python run.py --no-headless      # 有界面运行浏览器
"""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime

import click

# 项目根目录加入 path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.browser import BrowserScreenshot
from src.menu_parser import get_pages_from_config
from src.doc_builder import build_pdf_from_images


def _cookie_domain_from_url(url: str) -> str:
    """从 base_url 解析出域名（用于 Cookie 的 domain）。"""
    from urllib.parse import urlparse
    p = urlparse(url)
    host = p.hostname or ""
    return host.strip()


def _parse_cookies(cookie_input: str, domain: str, path: str = "/") -> list:
    """
    解析 Cookie：支持 "name1=value1; name2=value2" 或 JSON 文件路径。
    返回 Playwright 可用的 [{"name","value","domain","path"}, ...]。
    """
    cookie_input = (cookie_input or "").strip()
    if not cookie_input:
        return []
    # 若是文件路径且存在，按 JSON 读取
    p = Path(cookie_input)
    if p.exists() and p.is_file():
        import json
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            # 确保每条都有 domain/path
            out = []
            for c in data:
                if isinstance(c, dict) and "name" in c and "value" in c:
                    out.append({
                        "name": str(c["name"]),
                        "value": str(c["value"]),
                        "domain": c.get("domain") or domain,
                        "path": c.get("path", path),
                    })
            return out
        return []
    # 按字符串解析：name1=value1; name2=value2（value 中可能含 =）
    cookies = []
    for part in cookie_input.split(";"):
        part = part.strip()
        if "=" not in part:
            continue
        name, _, value = part.partition("=")
        name, value = name.strip(), value.strip()
        if name:
            cookies.append({"name": name, "value": value, "domain": domain, "path": path})
    return cookies


def load_config(config_path: str) -> dict:
    """加载 YAML 配置"""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except ImportError:
        import json
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)


@click.command()
@click.option("-c", "--config", "config_file", default="config.yaml", help="配置文件路径")
@click.option("--no-headless", is_flag=True, help="显示浏览器窗口")
@click.option("--screenshots-only", is_flag=True, help="仅截图，不生成 PDF")
@click.option("--pdf-only", is_flag=True, help="仅从已有截图生成 PDF（需 output 目录中已有截图）")
def main(config_file: str, no_headless: bool, screenshots_only: bool, pdf_only: bool):
    """按菜单顺序截取平台页面并生成 PDF 文档。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    logger = logging.getLogger(__name__)

    # 若没有 config.yaml 则尝试 config.example.yaml
    if not Path(config_file).exists() and Path("config.example.yaml").exists():
        config_file = "config.example.yaml"
        logger.warning("未找到 config.yaml，使用 config.example.yaml（请复制并修改）")

    try:
        config = load_config(config_file)
    except Exception as e:
        logger.error(str(e))
        sys.exit(1)

    base_url = config.get("base_url", "").rstrip("/")
    output_cfg = config.get("output", {})
    output_dir = output_cfg.get("dir", "./output")
    doc_name = output_cfg.get("doc_name", "平台页面文档")
    image_format = output_cfg.get("image_format", "png")

    # 带时间戳的输出目录
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_output_dir = os.path.join(output_dir, f"run_{timestamp}")
    os.makedirs(run_output_dir, exist_ok=True)

    if pdf_only:
        # 仅生成 PDF：收集当前输出目录下的图片
        image_paths = sorted(Path(run_output_dir).glob(f"*.{image_format}"))
        if not image_paths:
            # 尝试 output_dir 下最新一次 run_* 目录
            parent = Path(output_dir)
            runs = sorted(parent.glob("run_*"), key=lambda p: p.stat().st_mtime, reverse=True)
            if runs:
                image_paths = sorted(runs[0].glob(f"*.{image_format}"))
        if not image_paths:
            logger.error("未找到截图文件，请先执行截图")
            sys.exit(1)
        image_paths = [str(p) for p in image_paths]
        pdf_path = os.path.join(output_dir, f"{doc_name}_{timestamp}.pdf")
        build_pdf_from_images(image_paths, pdf_path)
        logger.info(f"完成。PDF: {pdf_path}")
        return

    # 获取页面列表
    pages = get_pages_from_config(config, base_url)
    if not pages:
        logger.error("配置中未提供 pages 或有效的 menu_selector，无法获取页面列表")
        sys.exit(1)

    logger.info(f"共 {len(pages)} 个页面待截图")

    # 若配置了登录，则询问粘贴 Cookie（不输入则跳过登录）
    login_cookies = None
    login_config = config.get("login") or {}
    if login_config.get("enabled", True):
        try:
            hint = "请粘贴 Cookie（格式：name1=value1; name2=value2），或输入 Cookie JSON 文件路径，留空跳过: "
            cookie_input = input(hint).strip()
            if cookie_input:
                domain = login_config.get("cookie_domain") or _cookie_domain_from_url(base_url)
                login_cookies = _parse_cookies(cookie_input, domain)
                if login_cookies:
                    logger.info("将使用所粘贴的 Cookie 进行访问后再截图")
                else:
                    logger.warning("Cookie 解析结果为空，将跳过登录")
        except (EOFError, KeyboardInterrupt):
            logger.warning("未输入 Cookie，将跳过登录（若页面需登录可能截图失败）")

    # 浏览器截图
    if no_headless:
        config.setdefault("browser", {})["headless"] = False

    with BrowserScreenshot(config) as engine:
        image_paths = engine.capture_pages(
            pages=pages,
            base_url=base_url,
            output_dir=run_output_dir,
            image_format=image_format,
            login_cookies=login_cookies,
        )

    if not image_paths:
        logger.error("未成功截取任何页面")
        sys.exit(1)

    if screenshots_only:
        logger.info(f"仅截图完成，共 {len(image_paths)} 张，目录: {run_output_dir}")
        return

    # 生成 PDF（传入页面名称与地址，显示在每张截图上方）
    pdf_path = os.path.join(output_dir, f"{doc_name}_{timestamp}.pdf")
    try:
        build_pdf_from_images(image_paths, pdf_path, page_infos=pages)
        logger.info(f"完成。截图: {run_output_dir}，PDF: {pdf_path}")
    except Exception as e:
        logger.error(f"生成 PDF 失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
