"""Shared OpenCV image operations for MCP/Web and CLI examples."""
from __future__ import annotations

import base64
import binascii
from pathlib import Path
from typing import Any

import numpy as np

try:
    import cv2
except Exception as exc:  # pragma: no cover - depends on local OpenCV runtime
    raise RuntimeError(
        "OpenCV 載入失敗。請確認目前環境不要同時混用 opencv-python 與 "
        "opencv-python，並使用與 NumPy 相容的 wheel；"
        "本專案建議 opencv-python>=4.12.0.88。"
    ) from exc

from toolanything import ToolError


def decode_image_base64(image_base64: str) -> np.ndarray:
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


def encode_image_base64(image: np.ndarray) -> str:
    try:
        success, buffer = cv2.imencode(".png", image)
    except Exception as exc:
        raise ToolError("圖片轉碼失敗", error_type="encode_failed") from exc

    if not success:
        raise ToolError("圖片轉碼失敗", error_type="encode_failed")

    encoded = base64.b64encode(buffer).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


def read_image_file(input_path: str | Path) -> np.ndarray:
    path = Path(input_path)
    if not path.exists() or not path.is_file():
        raise ToolError(f"找不到輸入圖片：{path}", error_type="missing_image")

    try:
        image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    except Exception as exc:
        raise ToolError("圖片讀取失敗", error_type="decode_failed") from exc

    if image is None:
        raise ToolError("圖片格式不支援或內容損壞", error_type="decode_failed")
    return image


def write_image_file(image: np.ndarray, output_path: str | Path) -> str:
    path = Path(output_path)
    if not path.suffix:
        raise ToolError("save_as 必須包含副檔名，例如 .png 或 .jpg", error_type="invalid_output_path")

    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        success = cv2.imwrite(str(path), image)
    except Exception as exc:
        raise ToolError("圖片寫出失敗", error_type="encode_failed") from exc

    if not success:
        raise ToolError("圖片寫出失敗", error_type="encode_failed")
    return str(path.resolve())


def image_metadata(image: np.ndarray) -> dict[str, Any]:
    height, width = image.shape[:2]
    channels = 1 if image.ndim == 2 else image.shape[2]
    return {"width": width, "height": height, "channels": channels}


def ensure_color_image(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.ndim == 3 and image.shape[2] == 4:
        return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
    return image


def resize_image(
    image: np.ndarray,
    target_width: int | None = None,
    target_height: int | None = None,
) -> np.ndarray:
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
    return cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)


def canny_image(
    image: np.ndarray,
    threshold1: int = 50,
    threshold2: int = 150,
) -> np.ndarray:
    if threshold1 < 0 or threshold2 < 0:
        raise ToolError("閾值必須為非負整數", error_type="invalid_threshold")

    try:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        return cv2.Canny(gray, threshold1, threshold2)
    except Exception as exc:
        raise ToolError("邊緣偵測失敗", error_type="canny_failed") from exc


def clahe_image(
    image: np.ndarray,
    clip_limit: float = 2.0,
    tile_grid_size: int = 8,
) -> np.ndarray:
    if clip_limit <= 0:
        raise ToolError("clip_limit 必須大於 0", error_type="invalid_clahe")
    if tile_grid_size <= 0:
        raise ToolError("tile_grid_size 必須大於 0", error_type="invalid_clahe")

    try:
        clahe = cv2.createCLAHE(clipLimit=float(clip_limit), tileGridSize=(tile_grid_size, tile_grid_size))
        if image.ndim == 2:
            return clahe.apply(image)

        color_image = ensure_color_image(image)
        lab = cv2.cvtColor(color_image, cv2.COLOR_BGR2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)
        enhanced_l = clahe.apply(l_channel)
        merged = cv2.merge((enhanced_l, a_channel, b_channel))
        return cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)
    except Exception as exc:
        raise ToolError("CLAHE 處理失敗", error_type="clahe_failed") from exc


def adjust_color_image(
    image: np.ndarray,
    brightness: int = 0,
    saturation: int = 0,
    hue_shift: int = 0,
) -> np.ndarray:
    if not -100 <= brightness <= 100:
        raise ToolError("brightness 必須介於 -100 到 100", error_type="invalid_adjustment")
    if not -100 <= saturation <= 100:
        raise ToolError("saturation 必須介於 -100 到 100", error_type="invalid_adjustment")
    if not -90 <= hue_shift <= 90:
        raise ToolError("hue_shift 必須介於 -90 到 90", error_type="invalid_adjustment")

    try:
        color_image = ensure_color_image(image)
        hsv = cv2.cvtColor(color_image, cv2.COLOR_BGR2HSV).astype(np.float32)
        hsv[:, :, 0] = (hsv[:, :, 0] + hue_shift) % 180
        saturation_scale = 1.0 + (saturation / 100.0)
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] * saturation_scale, 0, 255)
        hsv[:, :, 2] = np.clip(hsv[:, :, 2] + (brightness * 2.55), 0, 255)
        return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
    except Exception as exc:
        raise ToolError("顏色調整失敗", error_type="adjust_color_failed") from exc


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


def build_demo_image(width: int = 320, height: int = 200) -> np.ndarray:
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
    return canvas


def build_demo_image_base64(width: int = 320, height: int = 200) -> str:
    return encode_image_base64(build_demo_image(width=width, height=height))
