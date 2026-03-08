"""OpenCV MCP Web example: wrap OpenCV functions as ToolAnything tools."""
from __future__ import annotations

import argparse
import base64
import binascii
from typing import Any

import cv2
import numpy as np

from toolanything import ToolError, ToolRegistry, tool
from toolanything.server.mcp_tool_server import run_server
from toolanything.utils.logger import logger

registry = ToolRegistry()


def _decode_image(image_base64: str) -> np.ndarray:
    if not image_base64:
        raise ToolError("未收到圖片內容", error_type="missing_image")

    if image_base64.startswith("data:"):
        _, _, payload = image_base64.partition(",")
        image_base64 = payload

    try:
        binary = base64.b64decode(image_base64, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ToolError("圖片內容無法解碼", error_type="invalid_base64") from exc

    try:
        array = np.frombuffer(binary, dtype=np.uint8)
        image = cv2.imdecode(array, cv2.IMREAD_UNCHANGED)
    except Exception as exc:
        raise ToolError("圖片解析失敗", error_type="decode_failed") from exc

    if image is None:
        raise ToolError("圖片格式不支援或內容損壞", error_type="decode_failed")

    return image


def _encode_image(image: np.ndarray) -> str:
    try:
        success, buffer = cv2.imencode(".png", image)
    except Exception as exc:
        raise ToolError("圖片轉碼失敗", error_type="encode_failed") from exc

    if not success:
        raise ToolError("圖片轉碼失敗", error_type="encode_failed")

    encoded = base64.b64encode(buffer).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


def _image_metadata(image: np.ndarray) -> dict[str, Any]:
    height, width = image.shape[:2]
    channels = 1 if image.ndim == 2 else image.shape[2]
    return {"width": width, "height": height, "channels": channels}


def build_demo_image_base64(width: int = 320, height: int = 200) -> str:
    """Generate a small demo image so the example can be verified without files."""

    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    for row in range(height):
        blue = int(255 * (row / max(1, height - 1)))
        canvas[row, :, 0] = blue
        canvas[row, :, 1] = 80
        canvas[row, :, 2] = 255 - blue
    cv2.rectangle(canvas, (20, 20), (width - 20, height - 20), (255, 255, 255), 3)
    cv2.circle(canvas, (width // 2, height // 2), min(width, height) // 5, (40, 40, 40), 4)
    cv2.putText(
        canvas,
        "ToolAnything",
        (20, height // 2 + 50),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    return _encode_image(canvas)


@tool(name="opencv.info", description="取得圖片尺寸與通道數", registry=registry)
def opencv_info(image_base64: str) -> dict[str, Any]:
    image = _decode_image(image_base64)
    return _image_metadata(image)


@tool(name="opencv.resize", description="依照指定尺寸縮放圖片（保持比例）", registry=registry)
def opencv_resize(
    image_base64: str,
    target_width: int | None = None,
    target_height: int | None = None,
) -> dict[str, Any]:
    image = _decode_image(image_base64)
    original_height, original_width = image.shape[:2]

    if target_width is None and target_height is None:
        raise ToolError("請至少提供寬度或高度", error_type="missing_dimension")
    if target_width is not None and target_width <= 0:
        raise ToolError("寬度必須大於 0", error_type="invalid_dimension")
    if target_height is not None and target_height <= 0:
        raise ToolError("高度必須大於 0", error_type="invalid_dimension")

    if target_width is None:
        scale = target_height / original_height
    elif target_height is None:
        scale = target_width / original_width
    else:
        scale = min(target_width / original_width, target_height / original_height)

    new_width = max(1, int(original_width * scale))
    new_height = max(1, int(original_height * scale))
    resized = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
    return {
        "image_base64": _encode_image(resized),
        "width": new_width,
        "height": new_height,
    }


@tool(name="opencv.canny", description="Canny 邊緣偵測", registry=registry)
def opencv_canny(
    image_base64: str,
    threshold1: int = 50,
    threshold2: int = 150,
) -> dict[str, Any]:
    if threshold1 < 0 or threshold2 < 0:
        raise ToolError("閾值必須為非負整數", error_type="invalid_threshold")

    image = _decode_image(image_base64)
    try:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        edges = cv2.Canny(gray, threshold1, threshold2)
    except Exception as exc:
        raise ToolError("邊緣偵測失敗", error_type="canny_failed") from exc

    return {
        "image_base64": _encode_image(edges),
        **_image_metadata(edges),
    }


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
    print("[opencv_mcp_web] Web UI 請開 examples/opencv_mcp_web/web/index.html")

    try:
        start_server(port=args.port, host=args.host)
    except Exception:
        logger.exception("OpenCV 工具伺服器啟動失敗")
        print("[opencv_mcp_web] 啟動失敗，請查看 logs/toolanything.log")


if __name__ == "__main__":
    main()
