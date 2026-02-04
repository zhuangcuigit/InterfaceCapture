"""
将截图按顺序合并为 PDF 文档，每页可带页面名称和可点击链接
"""

import logging
import os
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# PDF 页面宽度（A4 点），留边距后的可用宽度
PDF_PAGE_WIDTH = 595
PDF_TOP_MARGIN = 50
PDF_SIDE_MARGIN = 40
PDF_TITLE_HEIGHT = 90  # 每张截图上方：页面名称、地址 区域高度

# 中文字体注册名，用于 PDF 内显示中文
PDF_FONT_CN = "ChineseFont"
PDF_FONT_CN_BOLD = "ChineseFontBold"


def _register_chinese_font() -> bool:
    """注册系统中文字体（Windows 微软雅黑/黑体/宋体），成功返回 True。"""
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except ImportError:
        return False
    windir = os.environ.get("WINDIR", "C:\\Windows")
    font_dir = os.path.join(windir, "Fonts")
    # 先注册正体
    for fname in ["msyh.ttc", "simhei.ttf", "simsun.ttc"]:
        path = os.path.join(font_dir, fname)
        if not os.path.isfile(path):
            continue
        try:
            if fname.endswith(".ttc"):
                font = TTFont(PDF_FONT_CN, path, subfontIndex=0)
            else:
                font = TTFont(PDF_FONT_CN, path)
            pdfmetrics.registerFont(font)
            # 粗体用同字体或雅黑 Bold
            bold_path = os.path.join(font_dir, "msyhbd.ttc")
            if os.path.isfile(bold_path):
                try:
                    bold_font = TTFont(PDF_FONT_CN_BOLD, bold_path, subfontIndex=0)
                    pdfmetrics.registerFont(bold_font)
                except Exception:
                    bold_font = TTFont(PDF_FONT_CN_BOLD, path, subfontIndex=0) if fname.endswith(".ttc") else TTFont(PDF_FONT_CN_BOLD, path)
                    pdfmetrics.registerFont(bold_font)
            else:
                bold_font = TTFont(PDF_FONT_CN_BOLD, path, subfontIndex=0) if fname.endswith(".ttc") else TTFont(PDF_FONT_CN_BOLD, path)
                pdfmetrics.registerFont(bold_font)
            return True
        except Exception as e:
            logger.debug("注册字体 %s 失败: %s", path, e)
    return False


def build_pdf_from_images(
    image_paths: List[str],
    output_pdf_path: str,
    page_infos: Optional[List[dict]] = None,
) -> str:
    """
    将多张图片按顺序合并为 PDF。若提供 page_infos，每页上方显示页面名称和可点击链接。
    image_paths: 截图文件路径列表（按顺序）
    output_pdf_path: 输出 PDF 路径
    page_infos: 可选，与 image_paths 同序的 [{"name": str, "url": str}, ...]
    返回生成的 PDF 路径。
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except ImportError as e:
        raise RuntimeError("请安装 reportlab: pip install reportlab（当前错误: %s）" % e) from e

    from PIL import Image

    valid: List[tuple] = []
    for i, p in enumerate(image_paths):
        path = Path(p)
        if path.exists():
            info = None
            if page_infos and i < len(page_infos):
                info = page_infos[i]
            valid.append((str(path.resolve()), info))
        else:
            logger.warning("图片不存在，已跳过: %s", p)

    if not valid:
        raise ValueError("没有有效的截图文件可生成 PDF")

    out = Path(output_pdf_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.suffix.lower() != ".pdf":
        out = out.with_suffix(".pdf")

    c = canvas.Canvas(str(out), pagesize=A4)
    usable_width = PDF_PAGE_WIDTH - 2 * PDF_SIDE_MARGIN
    use_cn_font = _register_chinese_font()
    font_name = PDF_FONT_CN if use_cn_font else "Helvetica"
    font_bold = PDF_FONT_CN_BOLD if use_cn_font else "Helvetica-Bold"

    for img_path, info in valid:
        img = Image.open(img_path)
        iw, ih = img.size
        scale = usable_width / iw if iw else 1
        img_width_pt = usable_width
        img_height_pt = ih * scale * (72 / 96.0) if ih else 100  # 近似 96dpi -> pt

        page_height_pt = PDF_TOP_MARGIN + PDF_TITLE_HEIGHT + img_height_pt + 20
        c.setPageSize((PDF_PAGE_WIDTH, page_height_pt))

        y = page_height_pt - PDF_TOP_MARGIN

        if info:
            name = (info.get("name") or "").strip()
            url = (info.get("url") or "").strip()
            c.setFont(font_name, 9)
            c.setFillColorRGB(0.3, 0.3, 0.3)
            c.drawString(PDF_SIDE_MARGIN, y, "页面名称：")
            y -= 14
            c.setFont(font_bold, 12)
            c.setFillColorRGB(0, 0, 0)
            c.drawString(PDF_SIDE_MARGIN, y, name[:90] + ("..." if len(name) > 90 else ""))
            y -= 16
            c.setFont(font_name, 9)
            c.setFillColorRGB(0.3, 0.3, 0.3)
            c.drawString(PDF_SIDE_MARGIN, y, "地址：")
            y -= 14
            c.setFont(font_name, 10)
            c.setFillColorRGB(0, 0, 0.8)
            url_text = (url[:120] + "..." if len(url) > 120 else url) or "-"
            c.drawString(PDF_SIDE_MARGIN, y - 10, url_text)
            if url:
                rect = (PDF_SIDE_MARGIN, y - 12, PDF_PAGE_WIDTH - PDF_SIDE_MARGIN, y + 2)
                c.linkURL(url, rect)
            c.setFillColorRGB(0, 0, 0)
            y -= 24
        else:
            y -= PDF_TITLE_HEIGHT

        c.drawImage(
            img_path,
            PDF_SIDE_MARGIN,
            20,
            width=img_width_pt,
            height=img_height_pt,
            preserveAspectRatio=True,
            anchor="c",
        )
        c.showPage()

    c.save()
    logger.info("PDF 已生成: %s", out)
    return str(out)
