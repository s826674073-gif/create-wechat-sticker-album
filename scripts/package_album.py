#!/usr/bin/env python3
"""Normalize, validate, preview, and package a static WeChat sticker album."""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import shutil
import sys
import tempfile
import unicodedata
import zipfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps


MAIN_SIZE = (240, 240)
COVER_SIZE = (240, 240)
ICON_SIZE = (50, 50)
BANNER_SIZE = (750, 400)
MAIN_LIMIT = 500 * 1024
COVER_LIMIT = 500 * 1024
ICON_LIMIT = 100 * 1024
BANNER_LIMIT = 500 * 1024
ALPHA_THRESHOLD = 16


class AlbumError(Exception):
    """A user-correctable album input or packaging error."""


def require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AlbumError(f"{field} must be a non-empty string")
    return value.strip()


def load_plan(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AlbumError(f"plan file does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise AlbumError(f"plan is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise AlbumError("plan root must be a JSON object")

    require_text(data.get("album_name"), "album_name")
    require_text(data.get("theme"), "theme")
    require_text(data.get("character_lock"), "character_lock")

    count = data.get("count")
    if isinstance(count, bool) or not isinstance(count, int) or not 8 <= count <= 24:
        raise AlbumError("count must be an integer from 8 through 24")

    items = data.get("items")
    if not isinstance(items, list) or len(items) != count:
        raise AlbumError(f"items must contain exactly {count} entries")

    expected_ids = [f"{number:02d}" for number in range(1, count + 1)]
    actual_ids: list[str] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise AlbumError(f"items[{index}] must be an object")
        actual_ids.append(require_text(item.get("id"), f"items[{index}].id"))
        require_text(item.get("meaning"), f"items[{index}].meaning")
        require_text(item.get("visual"), f"items[{index}].visual")
    if actual_ids != expected_ids:
        raise AlbumError(f"item ids must be contiguous and zero-padded: {expected_ids}")

    copy_block = data.get("copy", {})
    if copy_block is not None and not isinstance(copy_block, dict):
        raise AlbumError("copy must be an object when provided")
    return data


def safe_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    normalized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", normalized)
    normalized = re.sub(r"\s+", "-", normalized).strip(" .-")
    return normalized or "wechat-sticker-album"


def open_png(path: Path, label: str, minimum_size: tuple[int, int]) -> Image.Image:
    if not path.is_file():
        raise AlbumError(f"missing {label}: {path}")
    try:
        with Image.open(path) as image:
            image.load()
            if image.format != "PNG":
                raise AlbumError(f"{label} must be a decoded PNG file: {path.name}")
            if image.width < minimum_size[0] or image.height < minimum_size[1]:
                raise AlbumError(
                    f"{label} source is too small: {image.width}x{image.height}; "
                    f"minimum is {minimum_size[0]}x{minimum_size[1]}"
                )
            return image.copy()
    except AlbumError:
        raise
    except Exception as exc:
        raise AlbumError(f"cannot decode {label} PNG {path}: {exc}") from exc


def require_transparency(image: Image.Image, label: str) -> Image.Image:
    rgba = image.convert("RGBA")
    minimum_alpha, maximum_alpha = rgba.getchannel("A").getextrema()
    if minimum_alpha == 255 or maximum_alpha == 0:
        raise AlbumError(f"{label} must contain both visible pixels and transparency")
    return rgba


def alpha_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    alpha = image.getchannel("A")
    mask = alpha.point(lambda value: 255 if value > ALPHA_THRESHOLD else 0)
    bbox = mask.getbbox()
    if bbox is None:
        raise AlbumError("transparent asset contains no visible subject")
    return bbox


def fit_transparent(image: Image.Image, size: tuple[int, int], occupancy: float) -> Image.Image:
    rgba = require_transparency(image, "transparent asset")
    subject = rgba.crop(alpha_bbox(rgba))
    maximum = (max(1, round(size[0] * occupancy)), max(1, round(size[1] * occupancy)))
    scale = min(maximum[0] / subject.width, maximum[1] / subject.height)
    resized_size = (max(1, round(subject.width * scale)), max(1, round(subject.height * scale)))
    subject = subject.resize(resized_size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    position = ((size[0] - subject.width) // 2, (size[1] - subject.height) // 2)
    canvas.alpha_composite(subject, position)
    return canvas


def has_partial_alpha(image: Image.Image) -> bool:
    if image.mode not in {"RGBA", "LA"} and "transparency" not in image.info:
        return False
    return image.convert("RGBA").getchannel("A").getextrema()[0] < 255


def banner_white_score(image: Image.Image) -> float:
    rgb = image.convert("RGB")
    border = max(1, min(rgb.size) // 30)
    pixels: list[tuple[int, int, int]] = []
    pixels.extend(rgb.crop((0, 0, rgb.width, border)).getdata())
    pixels.extend(rgb.crop((0, rgb.height - border, rgb.width, rgb.height)).getdata())
    pixels.extend(rgb.crop((0, border, border, rgb.height - border)).getdata())
    pixels.extend(rgb.crop((rgb.width - border, border, rgb.width, rgb.height - border)).getdata())
    white = sum(1 for red, green, blue in pixels if red >= 245 and green >= 245 and blue >= 245)
    return white / max(1, len(pixels))


def encode_png(image: Image.Image, colors: int | None = None) -> bytes:
    candidate = image
    if colors is not None:
        if image.mode == "RGBA":
            candidate = image.quantize(
                colors=colors,
                method=Image.Quantize.FASTOCTREE,
                dither=Image.Dither.FLOYDSTEINBERG,
            )
        else:
            candidate = image.convert("RGB").quantize(
                colors=colors,
                method=Image.Quantize.MEDIANCUT,
                dither=Image.Dither.FLOYDSTEINBERG,
            )
    buffer = io.BytesIO()
    candidate.save(buffer, format="PNG", optimize=True, compress_level=9)
    return buffer.getvalue()


def save_under_limit(image: Image.Image, path: Path, byte_limit: int, label: str) -> int:
    attempts = [None, 256, 128, 64, 32]
    for colors in attempts:
        payload = encode_png(image, colors)
        if len(payload) <= byte_limit:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
            return len(payload)
    raise AlbumError(f"{label} cannot be compressed below {byte_limit} bytes without stronger loss")


def transparent_metrics(image: Image.Image) -> dict[str, float]:
    rgba = image.convert("RGBA")
    bbox = alpha_bbox(rgba)
    bbox_area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
    visible = sum(1 for value in rgba.getchannel("A").getdata() if value > 32)
    total = rgba.width * rgba.height
    return {
        "bbox_fraction": round(bbox_area / total, 4),
        "visible_fraction": round(visible / total, 4),
    }


def verify_output(
    path: Path,
    expected_size: tuple[int, int],
    byte_limit: int,
    transparent: bool,
    label: str,
) -> dict[str, Any]:
    with Image.open(path) as image:
        image.load()
        if image.format != "PNG":
            raise AlbumError(f"packaged {label} is not PNG")
        if image.size != expected_size:
            raise AlbumError(f"packaged {label} has wrong size: {image.size}")
        if path.stat().st_size > byte_limit:
            raise AlbumError(f"packaged {label} exceeds its byte limit")
        rgba = image.convert("RGBA")
        alpha = rgba.getchannel("A")
        if transparent:
            if alpha.getextrema()[0] == 255:
                raise AlbumError(f"packaged {label} lacks transparency")
            corners = [
                alpha.getpixel((0, 0)),
                alpha.getpixel((expected_size[0] - 1, 0)),
                alpha.getpixel((0, expected_size[1] - 1)),
                alpha.getpixel((expected_size[0] - 1, expected_size[1] - 1)),
            ]
            if any(value > ALPHA_THRESHOLD for value in corners):
                raise AlbumError(f"packaged {label} must have transparent corners")
        elif alpha.getextrema()[0] < 255:
            raise AlbumError(f"packaged {label} must be fully opaque")
        result: dict[str, Any] = {
            "file": path.name,
            "format": image.format,
            "width": image.width,
            "height": image.height,
            "bytes": path.stat().st_size,
            "transparent": transparent,
        }
        if transparent:
            result.update(transparent_metrics(rgba))
        return result


def composite_on_checker(image: Image.Image, box: tuple[int, int]) -> Image.Image:
    width, height = box
    tile = 12
    board = Image.new("RGB", box, "white")
    draw = ImageDraw.Draw(board)
    for y in range(0, height, tile):
        for x in range(0, width, tile):
            color = (224, 224, 224) if (x // tile + y // tile) % 2 else (248, 248, 248)
            draw.rectangle((x, y, min(x + tile - 1, width - 1), min(y + tile - 1, height - 1)), fill=color)
    rgba = image.convert("RGBA")
    scale = min(width / rgba.width, height / rgba.height)
    preview_size = (max(1, round(rgba.width * scale)), max(1, round(rgba.height * scale)))
    rgba = rgba.resize(preview_size, Image.Resampling.LANCZOS)
    position = ((width - rgba.width) // 2, (height - rgba.height) // 2)
    board.paste(rgba, position, rgba)
    return board


def make_contact_sheet(entries: list[tuple[str, Path]], output: Path) -> None:
    columns = 4
    cell_width, cell_height = 280, 300
    rows = (len(entries) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * cell_width, rows * cell_height), (238, 238, 238))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, (label, path) in enumerate(entries):
        row, column = divmod(index, columns)
        left, top = column * cell_width, row * cell_height
        with Image.open(path) as image:
            image.load()
            preview = composite_on_checker(image, (250, 250))
        sheet.paste(preview, (left + 15, top + 30))
        draw.text((left + 15, top + 8), label, fill=(20, 20, 20), font=font)
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, format="PNG", optimize=True)


def difference_hash(path: Path) -> int:
    with Image.open(path) as image:
        rgba = image.convert("RGBA")
        white = Image.new("RGBA", rgba.size, "white")
        white.alpha_composite(rgba)
        small = white.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
        pixels = list(small.getdata())
    value = 0
    for row in range(8):
        for column in range(8):
            left = pixels[row * 9 + column]
            right = pixels[row * 9 + column + 1]
            value = (value << 1) | int(left > right)
    return value


def near_duplicate_warnings(paths: list[Path]) -> list[str]:
    hashes = {path.stem: difference_hash(path) for path in paths}
    warnings: list[str] = []
    names = sorted(hashes)
    for index, first in enumerate(names):
        for second in names[index + 1 :]:
            distance = bin(hashes[first] ^ hashes[second]).count("1")
            if distance <= 4:
                warnings.append(
                    f"Expressions {first} and {second} are visually similar by dHash "
                    f"(distance {distance}); inspect them manually."
                )
    return warnings


def markdown_escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def write_review_files(review_dir: Path, plan: dict[str, Any]) -> None:
    review_dir.mkdir(parents=True, exist_ok=True)
    (review_dir / "album-plan.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    lines = [
        f"# {plan['album_name']}",
        "",
        f"- 主题：{plan['theme']}",
        f"- 数量：{plan['count']}",
        f"- 角色与画风锁定：{plan['character_lock']}",
        "",
        "| 编号 | 含义 | 无字画面 |",
        "|---|---|---|",
    ]
    for item in plan["items"]:
        lines.append(
            f"| {item['id']} | {markdown_escape(item['meaning'])} | "
            f"{markdown_escape(item['visual'])} |"
        )
    (review_dir / "album-plan.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    copy_block = plan.get("copy") or {}
    title = str(copy_block.get("title") or plan["album_name"])
    introduction = str(copy_block.get("introduction") or f"围绕“{plan['theme']}”创作的静态表情专辑。")
    copyright_text = str(copy_block.get("copyright") or "请在提交前填写真实版权信息。")
    copy_text = (
        "# 专辑文案建议\n\n"
        f"- 标题：{title}\n"
        f"- 简介：{introduction}\n"
        f"- 版权：{copyright_text}\n"
    )
    (review_dir / "album-copy.md").write_text(copy_text, encoding="utf-8")

    with (review_dir / "item-manifest.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=["id", "meaning", "visual", "filename"])
        writer.writeheader()
        for item in plan["items"]:
            writer.writerow(
                {
                    "id": item["id"],
                    "meaning": item["meaning"],
                    "visual": item["visual"],
                    "filename": f"{item['id']}.png",
                }
            )


def validate_raw_contract(raw_dir: Path, plan: dict[str, Any]) -> list[Path]:
    expressions_dir = raw_dir / "expressions"
    if not expressions_dir.is_dir():
        raise AlbumError(f"missing expressions directory: {expressions_dir}")
    expected = [expressions_dir / f"{number:02d}.png" for number in range(1, plan["count"] + 1)]
    expected_names = {path.name for path in expected}
    actual_files = {path.name for path in expressions_dir.iterdir() if path.is_file()}
    missing = sorted(expected_names - actual_files)
    unexpected = sorted(actual_files - expected_names)
    if missing:
        raise AlbumError(f"missing expression files: {', '.join(missing)}")
    if unexpected:
        raise AlbumError(f"unexpected expression files: {', '.join(unexpected)}")
    return expected


def build_album(raw_dir: Path, plan_path: Path, out_dir: Path) -> dict[str, Any]:
    plan = load_plan(plan_path)
    expression_sources = validate_raw_contract(raw_dir, plan)
    if out_dir.exists():
        raise AlbumError(f"output directory already exists; choose a new versioned path: {out_dir}")

    out_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f"{out_dir.name}.tmp-", dir=out_dir.parent))
    try:
        upload = temporary / "upload"
        expression_output_dir = upload / "expressions"
        review = temporary / "review"
        expression_output_dir.mkdir(parents=True)

        checks: list[dict[str, Any]] = []
        warnings: list[str] = []
        output_expression_paths: list[Path] = []

        for source in expression_sources:
            image = open_png(source, f"expression {source.stem}", MAIN_SIZE)
            image = require_transparency(image, f"expression {source.stem}")
            processed = fit_transparent(image, MAIN_SIZE, 0.86)
            destination = expression_output_dir / source.name
            save_under_limit(processed, destination, MAIN_LIMIT, f"expression {source.stem}")
            result = verify_output(destination, MAIN_SIZE, MAIN_LIMIT, True, f"expression {source.stem}")
            if result["visible_fraction"] < 0.05 or result["bbox_fraction"] < 0.18:
                warnings.append(f"Expression {source.stem} has a thin or sparse silhouette; inspect readability.")
            checks.append(result)
            output_expression_paths.append(destination)

        cover_source = open_png(raw_dir / "cover.png", "cover", COVER_SIZE)
        cover = fit_transparent(require_transparency(cover_source, "cover"), COVER_SIZE, 0.86)
        cover_path = upload / "cover.png"
        save_under_limit(cover, cover_path, COVER_LIMIT, "cover")
        checks.append(verify_output(cover_path, COVER_SIZE, COVER_LIMIT, True, "cover"))

        icon_source = open_png(raw_dir / "icon.png", "icon", ICON_SIZE)
        icon = fit_transparent(require_transparency(icon_source, "icon"), ICON_SIZE, 0.90)
        icon_path = upload / "icon.png"
        save_under_limit(icon, icon_path, ICON_LIMIT, "icon")
        checks.append(verify_output(icon_path, ICON_SIZE, ICON_LIMIT, True, "icon"))

        banner_source = open_png(raw_dir / "banner.png", "banner", BANNER_SIZE)
        if has_partial_alpha(banner_source):
            raise AlbumError("banner source must be fully opaque")
        banner_rgb = banner_source.convert("RGB")
        if banner_white_score(banner_rgb) >= 0.65:
            raise AlbumError("banner border is predominantly white; use a bright non-white background")
        banner = ImageOps.fit(banner_rgb, BANNER_SIZE, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        banner_path = upload / "banner.png"
        save_under_limit(banner, banner_path, BANNER_LIMIT, "banner")
        checks.append(verify_output(banner_path, BANNER_SIZE, BANNER_LIMIT, False, "banner"))

        warnings.extend(near_duplicate_warnings(output_expression_paths))
        write_review_files(review, plan)
        contact_entries = [(path.stem, path) for path in output_expression_paths]
        contact_entries.extend([("cover", cover_path), ("icon", icon_path), ("banner", banner_path)])
        make_contact_sheet(contact_entries, review / "contact-sheet.png")

        report = {
            "automated_status": "passed",
            "album_name": plan["album_name"],
            "count": plan["count"],
            "checks": checks,
            "warnings": warnings,
            "manual_review_required": [
                "character identity and style consistency",
                "absence of accidental text, logos, signatures, and watermarks",
                "clean edges without halos or jaggies",
                "correct anatomy and unclipped poses or props",
                "meaningful differences between expressions",
                "banner storytelling and crop safety",
            ],
        }
        (review / "qa-report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        archive_name = f"{safe_name(plan['album_name'])}-package.zip"
        archive_path = temporary / archive_name
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for folder_name in ("upload", "review"):
                for file_path in sorted((temporary / folder_name).rglob("*")):
                    if file_path.is_file():
                        archive.write(file_path, file_path.relative_to(temporary).as_posix())

        os.replace(temporary, out_dir)
        return {
            "automated_status": "passed",
            "output_dir": str(out_dir.resolve()),
            "upload_dir": str((out_dir / "upload").resolve()),
            "review_dir": str((out_dir / "review").resolve()),
            "archive": str((out_dir / archive_name).resolve()),
            "warnings": warnings,
        }
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Normalize, validate, preview, and package a static WeChat sticker album."
    )
    parser.add_argument("--raw-dir", required=True, type=Path, help="Raw asset directory")
    parser.add_argument("--plan", required=True, type=Path, help="Approved album-plan.json")
    parser.add_argument("--out-dir", required=True, type=Path, help="New output directory")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        summary = build_album(args.raw_dir.resolve(), args.plan.resolve(), args.out_dir.resolve())
    except AlbumError as exc:
        print(json.dumps({"automated_status": "failed", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    except Exception as exc:
        print(
            json.dumps(
                {"automated_status": "failed", "error": f"unexpected error: {exc}"},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
