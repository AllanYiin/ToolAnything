"""OpenCV MCP Web repository example: wrap OpenCV functions as ToolAnything tools."""
from __future__ import annotations

import argparse
import base64
import binascii
from typing import Any

import numpy as np

try:
    import cv2
except Exception as exc:  # pragma: no cover - depends on local OpenCV runtime
    raise RuntimeError(
        "OpenCV 載入失敗。請確認目前環境不要同時混用 opencv-python 與 "
        "opencv-python-headless，並使用與 NumPy 相容的 wheel；"
        "本專案建議 opencv-python-headless>=4.12.0.88。"
    ) from exc

from toolanything import ToolError, ToolRegistry, tool
from toolanything.server.mcp_tool_server import run_server
from toolanything.utils.logger import logger

# 這個範例同時支援：
# 1. `toolanything serve examples/opencv_mcp_web/server.py`
# 2. 直接呼叫 `start_server(...)`
# 因此要和 CLI 使用同一個全域 registry，避免 tools 載入後 server 仍看到空清單。
registry = ToolRegistry.global_instance()


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


def _ensure_color_image(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.ndim == 3 and image.shape[2] == 4:
        return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    return image


def _draw_demo_rectangle(
    canvas: np.ndarray,
    top_left: tuple[int, int],
    bottom_right: tuple[int, int],
    color: tuple[int, int, int],
    thickness: int,
) -> None:
    if hasattr(cv2, "rectangle"):
        cv2.rectangle(canvas, top_left, bottom_right, color, thickness)
        return

    x1, y1 = top_left
    x2, y2 = bottom_right
    canvas[y1 : y1 + thickness, x1:x2] = color
    canvas[y2 - thickness : y2, x1:x2] = color
    canvas[y1:y2, x1 : x1 + thickness] = color
    canvas[y1:y2, x2 - thickness : x2] = color


def _draw_demo_circle(
    canvas: np.ndarray,
    center: tuple[int, int],
    radius: int,
    color: tuple[int, int, int],
    thickness: int,
) -> None:
    if hasattr(cv2, "circle"):
        cv2.circle(canvas, center, radius, color, thickness)
        return

    yy, xx = np.ogrid[: canvas.shape[0], : canvas.shape[1]]
    distance = np.sqrt((xx - center[0]) ** 2 + (yy - center[1]) ** 2)
    ring = (radius - thickness <= distance) & (distance <= radius + thickness)
    canvas[ring] = color


def build_demo_image_base64(width: int = 320, height: int = 200) -> str:
    """Generate a small demo image so the example can be verified without files."""

    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    for row in range(height):
        blue = int(255 * (row / max(1, height - 1)))
        canvas[row, :, 0] = blue
        canvas[row, :, 1] = 80
        canvas[row, :, 2] = 255 - blue
    _draw_demo_rectangle(canvas, (20, 20), (width - 20, height - 20), (255, 255, 255), 3)
    _draw_demo_circle(canvas, (width // 2, height // 2), min(width, height) // 5, (40, 40, 40), 4)
    if all(hasattr(cv2, attr) for attr in ("putText", "FONT_HERSHEY_SIMPLEX", "LINE_AA")):
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


@tool(name="__ping__", description="Inspector/doctor 健康檢查工具", registry=registry)
def ping() -> dict[str, Any]:
    return {"ok": True, "message": "pong"}


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


@tool(name="opencv.clahe", description="使用 CLAHE 提升局部對比", registry=registry)
def opencv_clahe(
    image_base64: str,
    clip_limit: float = 2.0,
    tile_grid_size: int = 8,
) -> dict[str, Any]:
    if clip_limit <= 0:
        raise ToolError("clip_limit 必須大於 0", error_type="invalid_clahe")
    if tile_grid_size <= 0:
        raise ToolError("tile_grid_size 必須大於 0", error_type="invalid_clahe")

    image = _decode_image(image_base64)
    try:
        clahe = cv2.createCLAHE(clipLimit=float(clip_limit), tileGridSize=(tile_grid_size, tile_grid_size))
        if image.ndim == 2:
            processed = clahe.apply(image)
        else:
            color_image = _ensure_color_image(image)
            lab = cv2.cvtColor(color_image, cv2.COLOR_BGR2LAB)
            l_channel, a_channel, b_channel = cv2.split(lab)
            enhanced_l = clahe.apply(l_channel)
            merged = cv2.merge((enhanced_l, a_channel, b_channel))
            processed = cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)
    except Exception as exc:
        raise ToolError("CLAHE 處理失敗", error_type="clahe_failed") from exc

    return {
        "image_base64": _encode_image(processed),
        **_image_metadata(processed),
    }


@tool(name="opencv.adjust_color", description="調整亮度、飽和度與色相", registry=registry)
def opencv_adjust_color(
    image_base64: str,
    brightness: int = 0,
    saturation: int = 0,
    hue_shift: int = 0,
) -> dict[str, Any]:
    if not -100 <= brightness <= 100:
        raise ToolError("brightness 必須介於 -100 到 100", error_type="invalid_adjustment")
    if not -100 <= saturation <= 100:
        raise ToolError("saturation 必須介於 -100 到 100", error_type="invalid_adjustment")
    if not -90 <= hue_shift <= 90:
        raise ToolError("hue_shift 必須介於 -90 到 90", error_type="invalid_adjustment")

    image = _decode_image(image_base64)
    try:
        color_image = _ensure_color_image(image)
        hsv = cv2.cvtColor(color_image, cv2.COLOR_BGR2HSV).astype(np.float32)
        hsv[:, :, 0] = (hsv[:, :, 0] + hue_shift) % 180
        saturation_scale = 1.0 + (saturation / 100.0)
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] * saturation_scale, 0, 255)
        hsv[:, :, 2] = np.clip(hsv[:, :, 2] + (brightness * 2.55), 0, 255)
        adjusted = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
    except Exception as exc:
        raise ToolError("顏色調整失敗", error_type="adjust_color_failed") from exc

    return {
        "image_base64": _encode_image(adjusted),
        **_image_metadata(adjusted),
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
    print("[opencv_mcp_web] 專用 Web UI：python examples/opencv_mcp_web/web_server.py")

    try:
        start_server(port=args.port, host=args.host)
    except Exception:
        logger.exception("OpenCV 工具伺服器啟動失敗")
        print("[opencv_mcp_web] 啟動失敗，請查看 logs/toolanything.log")


if __name__ == "__main__":
    main()
