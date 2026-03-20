"""OpenCV MCP Web repository example: wrap OpenCV functions as ToolAnything tools."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from toolanything import ToolError, ToolRegistry, tool
from toolanything.server.mcp_streamable_http import run_server
from toolanything.utils.logger import logger

if __package__ in (None, ""):
    example_dir = Path(__file__).resolve().parent
    if str(example_dir) not in sys.path:
        sys.path.insert(0, str(example_dir))
    from image_ops import (
        adjust_color_image,
        build_demo_image,
        build_demo_image_base64,
        canny_image,
        clahe_image,
        cv2,
        decode_image_base64,
        encode_image_base64,
        image_metadata,
        read_image_file,
        resize_image,
        write_image_file,
    )
else:
    from .image_ops import (
        adjust_color_image,
        build_demo_image,
        build_demo_image_base64,
        canny_image,
        clahe_image,
        cv2,
        decode_image_base64,
        encode_image_base64,
        image_metadata,
        read_image_file,
        resize_image,
        write_image_file,
    )

# 這個範例同時支援：
# 1. `toolanything serve examples/opencv_mcp_web/server.py`
# 2. `toolanything cli ... --module examples/opencv_mcp_web/server.py`
# 3. 直接呼叫 `start_server(...)`
# 因此維持模組自己的 registry，避免 CLI / 測試重複載入時污染全域 registry。
registry = ToolRegistry()

_decode_image = decode_image_base64
_encode_image = encode_image_base64
_image_metadata = image_metadata


def _load_image(
    *,
    image_base64: str | None = None,
    input_path: str | None = None,
):
    if bool(image_base64) == bool(input_path):
        raise ToolError(
            "請提供 image_base64 或 input_path 其中之一",
            error_type="validation_error",
        )
    if input_path:
        return read_image_file(input_path)
    return _decode_image(image_base64 or "")


def _render_image_result(image, *, save_as: str | None = None) -> dict[str, Any]:
    payload = {
        **_image_metadata(image),
    }
    if save_as:
        payload["output_path"] = write_image_file(image, save_as)
        return payload
    payload["image_base64"] = _encode_image(image)
    return payload


@tool(name="opencv.demo_image", description="產生示範圖片，可回傳 base64 或直接寫入檔案", registry=registry)
def opencv_demo_image(
    width: int = 320,
    height: int = 200,
    save_as: str | None = None,
) -> dict[str, Any]:
    image = build_demo_image(width=width, height=height)
    return _render_image_result(image, save_as=save_as)


@tool(name="opencv.info", description="取得圖片尺寸與通道數", registry=registry)
def opencv_info(
    image_base64: str | None = None,
    input_path: str | None = None,
) -> dict[str, Any]:
    image = _load_image(image_base64=image_base64, input_path=input_path)
    return _image_metadata(image)


@tool(name="__ping__", description="Inspector/doctor 健康檢查工具", registry=registry)
def ping() -> dict[str, Any]:
    return {"ok": True, "message": "pong"}


@tool(name="opencv.resize", description="依照指定尺寸縮放圖片（保持比例）", registry=registry)
def opencv_resize(
    image_base64: str | None = None,
    input_path: str | None = None,
    target_width: int | None = None,
    target_height: int | None = None,
    save_as: str | None = None,
) -> dict[str, Any]:
    image = _load_image(image_base64=image_base64, input_path=input_path)
    resized = resize_image(image, target_width=target_width, target_height=target_height)
    return _render_image_result(resized, save_as=save_as)


@tool(name="opencv.canny", description="Canny 邊緣偵測", registry=registry)
def opencv_canny(
    image_base64: str | None = None,
    input_path: str | None = None,
    threshold1: int = 50,
    threshold2: int = 150,
    save_as: str | None = None,
) -> dict[str, Any]:
    image = _load_image(image_base64=image_base64, input_path=input_path)
    edges = canny_image(image, threshold1=threshold1, threshold2=threshold2)
    return _render_image_result(edges, save_as=save_as)


@tool(name="opencv.clahe", description="使用 CLAHE 提升局部對比", registry=registry)
def opencv_clahe(
    image_base64: str | None = None,
    input_path: str | None = None,
    clip_limit: float = 2.0,
    tile_grid_size: int = 8,
    save_as: str | None = None,
) -> dict[str, Any]:
    image = _load_image(image_base64=image_base64, input_path=input_path)
    processed = clahe_image(image, clip_limit=clip_limit, tile_grid_size=tile_grid_size)
    return _render_image_result(processed, save_as=save_as)


@tool(name="opencv.adjust_color", description="調整亮度、飽和度與色相", registry=registry)
def opencv_adjust_color(
    image_base64: str | None = None,
    input_path: str | None = None,
    brightness: int = 0,
    saturation: int = 0,
    hue_shift: int = 0,
    save_as: str | None = None,
) -> dict[str, Any]:
    image = _load_image(image_base64=image_base64, input_path=input_path)
    adjusted = adjust_color_image(
        image,
        brightness=brightness,
        saturation=saturation,
        hue_shift=hue_shift,
    )
    return _render_image_result(adjusted, save_as=save_as)


def start_server(port: int = 9091, host: str = "127.0.0.1") -> None:
    """Start an MCP HTTP server exposing the OpenCV tools."""

    run_server(port=port, host=host, registry=registry)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="啟動 OpenCV MCP Web 範例")
    parser.add_argument("--port", type=int, default=9091, help="監聽 port，預設 9091")
    parser.add_argument("--host", default="127.0.0.1", help="監聽 host，預設 127.0.0.1")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    print("[opencv_mcp_web] 已註冊工具：")
    for tool_info in registry.to_mcp_tools():
        print(f" - {tool_info['name']}: {tool_info['description']}")

    print("[opencv_mcp_web] 內建 inspect 驗證：toolanything inspect")
    print("[opencv_mcp_web] 專用 Web UI：python examples/opencv_mcp_web/web_server.py")

    try:
        start_server(port=args.port, host=args.host)
    except Exception:
        logger.exception("OpenCV 工具伺服器啟動失敗")
        print("[opencv_mcp_web] 啟動失敗，請查看 logs/toolanything.log")


if __name__ == "__main__":
    main()
