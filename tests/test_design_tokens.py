"""DESIGN.md (nguồn sự thật) và web/src/theme.css (biến CSS) phải cùng giá trị token.

Phần đầu DESIGN.md là YAML đơn giản (khoá: giá trị, thụt lề 2 dấu cách), đọc bằng một parser
nhỏ ở đây để không thêm thư viện YAML chỉ cho một test.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "DESIGN.md"
THEME = ROOT / "web" / "src" / "theme.css"
WEB_SRC = ROOT / "web" / "src"

# Nhóm trong DESIGN.md → tiền tố biến CSS.
PREFIX = {
    "colors": "color",
    "font": "font",
    "text": "text",
    "radius": "radius",
    "space": "space",
    "size": "size",
}


def front_matter_tokens() -> dict[str, str]:
    """Phẳng hoá front matter: {"colors.light.bg": "#F5F5F3", "radius.card": "22px", ...}."""
    text = DESIGN.read_text(encoding="utf-8")
    match = re.match(r"---\n(.*?)\n---\n", text, re.S)
    assert match, "DESIGN.md phải mở đầu bằng khối --- ... ---"
    tokens: dict[str, str] = {}
    path: list[str] = []
    for raw in match.group(1).splitlines():
        line = raw.split(" #", 1)[0].rstrip() if not raw.lstrip().startswith("#") else ""
        if not line.strip():
            continue
        depth = (len(line) - len(line.lstrip())) // 2
        key, _, value = line.strip().partition(":")
        path = path[:depth] + [key]
        if value.strip():
            tokens[".".join(path)] = value.strip().strip('"')
    return tokens


def css_block(selector: str) -> dict[str, str]:
    """Các biến `--x: v;` trong khối CSS bắt đầu bằng `selector {` (khối không lồng nhau)."""
    css = THEME.read_text(encoding="utf-8")
    start = css.index(selector + " {")
    body = css[start : css.index("}", start)]
    return dict(re.findall(r"--([\w-]+):\s*([^;]+);", body))


def expected(theme: str) -> dict[str, str]:
    """Biến CSS mà DESIGN.md yêu cầu cho chế độ `theme` ('light' gồm cả token không phải màu)."""
    out: dict[str, str] = {}
    for key, value in front_matter_tokens().items():
        group, *rest = key.split(".")
        if group not in PREFIX:
            continue  # name, source
        if group == "colors":
            mode, name = rest
            if mode == theme or (theme == "light" and mode == "fixed"):
                out[f"color-{name}"] = value
        elif theme == "light":
            out[f"{PREFIX[group]}-{rest[0]}"] = value
    return out


def test_light_tokens_match() -> None:
    assert css_block(":root") == expected("light")


@pytest.mark.parametrize(
    "selector",
    [":root:not([data-theme='light'])", ":root[data-theme='dark']"],
)
def test_dark_tokens_match(selector: str) -> None:
    # Hai khối tối (theo máy / chọn tay) phải giống nhau và giống DESIGN.md.
    assert css_block(selector) == expected("dark")


def test_dark_overrides_every_themed_color() -> None:
    light = {k for k in expected("light") if k.startswith("color-")}
    fixed = {
        f"color-{k.split('.')[-1]}" for k in front_matter_tokens() if k.startswith("colors.fixed.")
    }
    assert set(expected("dark")) == light - fixed


def test_no_hex_colors_outside_theme() -> None:
    # Màu chỉ khai báo ở theme.css; component dùng var(--color-...) hoặc cssVar().
    offenders = []
    for path in WEB_SRC.rglob("*"):
        if path.suffix not in {".ts", ".tsx", ".css"} or path == THEME:
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?\b", line):
                offenders.append(f"{path.relative_to(ROOT)}:{n}")
    assert offenders == []
