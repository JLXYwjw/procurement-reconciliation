# -*- coding: utf-8 -*-
"""
仓库质量门禁 —— 基础可读版（quality_check_simple.py）
=====================================================

  1. 英文命名的 .md / .html 文档不能含中文字符
  2. 中文命名的文档（.zh-CN 后缀或文件名含中文）必须有中文内容
  3. README / index 引用的每个图片资源都必须真实存在
  4. 中英文双语 README 和 index 都必须齐全

通过时退出码 0，有问题时退出码 1。

运行方式：
    python scripts/quality_check_simple.py [项目根目录]

English:
Repository quality gate (plain, readable version).

Checks:
  1. English-named .md / .html documents must not contain CJK characters
  2. Chinese-named documents (.zh-CN suffix or Chinese in the filename)
     must contain Chinese content
  3. Every image referenced by README / index must actually exist
  4. Bilingual README and index must all be present

Exit code 0 on pass, 1 on failure.

Run:
    python scripts/quality_check_simple.py [project root]
"""

import re
import subprocess
import sys
from pathlib import Path

# ------------------------------------------------------------------
# 0. 配置
# ------------------------------------------------------------------
# 项目根目录：命令行第一个参数，或默认当前目录
root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")

# 中文字符匹配：Unicode 范围 4E00~9FFF（常用汉字区）
CJK_PATTERN = re.compile(r"[\u4e00-\u9fff]")

# 图片资源引用匹配：assets/ 开头，png/jpg/jpeg/gif/svg 结尾
ASSET_PATTERN = re.compile(r"assets/[\w\-.]+\.(?:png|jpg|jpeg|gif|svg)")

# 必须存在的双语文件清单
REQUIRED_FILES = [
    "README.md",
    "README.zh-CN.md",
    "index.html",
    "index.zh-CN.html",
]


# ------------------------------------------------------------------
# 工具函数
# ------------------------------------------------------------------
def count_cjk(text):
    """统计一段文本里有多少个中文字符。"""
    matches = CJK_PATTERN.findall(text)
    return len(matches)


def is_zh_name(filename):
    """判断一个文件名是不是"中文名"（文件名里含中文，或带 .zh-CN 后缀）。"""
    basename = Path(filename).name
    if CJK_PATTERN.search(basename):
        return True
    if ".zh-CN" in basename:
        return True
    return False


# ------------------------------------------------------------------
# 主流程
# ------------------------------------------------------------------
def main():
    errors = []

    # ---- 1/2. 文档语言一致性检查 ----
    # 只检查 git 跟踪的 .md 和 .html 文件（本地未跟踪的文件不算）
    # 这样门禁反映的是"真正会被发布"的内容
    result = subprocess.run(
        ["git", "ls-files", "*.md", "*.html"],
        cwd=str(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    file_list = result.stdout.splitlines()
    doc_files = []
    for f in file_list:
        if f:
            doc_files.append(root / f)

    seen = set()
    for fp in doc_files:
        p = fp.resolve()
        # 跳过重复文件和隐藏文件
        if p in seen:
            continue
        if fp.name.startswith("."):
            continue
        seen.add(p)

        # 读文件内容，读不了就跳过
        try:
            text = fp.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        cjk_count = count_cjk(text)

        if is_zh_name(fp.name):
            # 中文名的文档必须有中文内容
            if cjk_count == 0:
                errors.append(f"[{fp.name}] Chinese-named doc has no Chinese content")
        else:
            # 英文名的文档不能有中文内容
            if cjk_count > 0:
                errors.append(f"[{fp.name}] English-named doc contains {cjk_count} CJK chars")

    # ---- 3. 图片资源引用检查 ----
    # 对每个必需文件，检查它引用的 assets/ 图片是否真实存在
    for fname in REQUIRED_FILES:
        fp = root / fname
        if not fp.is_file():
            errors.append(f"missing {fname}")
            continue
        text = fp.read_text(encoding="utf-8", errors="replace")
        refs = ASSET_PATTERN.findall(text)
        for ref in refs:
            if not (root / ref).is_file():
                errors.append(f"missing asset referenced in {fname}: {ref}")

    # ---- 4. 双语文件齐全检查 ----
    for fname in REQUIRED_FILES:
        if not (root / fname).is_file():
            errors.append(f"missing {fname}")

    # ---- 输出结果 ----
    if errors:
        print("QUALITY FAIL")
        # 去重后排序输出
        unique_errors = sorted(set(errors))
        for e in unique_errors:
            print(" -", e)
        return 1

    print("QUALITY OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
