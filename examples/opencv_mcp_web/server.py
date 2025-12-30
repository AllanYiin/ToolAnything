"""OpenCV 工具示範（最小化 ToolAnything 使用方式）。"""
from __future__ import annotations

import base64
import binascii
from typing import Any

import cv2
import numpy as np

from toolanything import run, tool
from toolanything.exceptions import ToolError
from toolanything.utils.logger import logger


def _decode_image(image_base64: str) -> np.ndarray:
    if not image_base64:
        raise ToolError("未收到圖片內容", error_type="missing_image")

    if image_base64.startswith("data:"):
        _, _, payload = image_base64.partition(",")
        image_base64 = payload

    try:
        binary = base64.b64decode(image_base64, validate=True)
    except (ValueError, binascii.Error) as exc:  # type: ignore[name-defined]
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


@tool(name="opencv.info", description="取得圖片尺寸與通道數")
def opencv_info(image_base64: str) -> dict[str, Any]:
    image = _decode_image(image_base64)
    return _image_metadata(image)


@tool(name="opencv.resize", description="依照指定尺寸縮放圖片（保持比例）")
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


@tool(name="opencv.canny", description="Canny 邊緣偵測")
def opencv_canny(
    image_base64: str,
    threshold1: int = 50,
    threshold2: int = 150,
) -> dict[str, Any]:
    if threshold1 < 0 or threshold2 < 0:
        raise ToolError("閾值必須為非負整數", error_type="invalid_threshold")

    image = _decode_image(image_base64)
    try:
        if image.ndim == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        edges = cv2.Canny(gray, threshold1, threshold2)
    except Exception as exc:
        raise ToolError("邊緣偵測失敗", error_type="canny_failed") from exc

    return {
        "image_base64": _encode_image(edges),
        **_image_metadata(edges),
    }


def main() -> None:
    try:
        run()
    except Exception:
        logger.exception("OpenCV 工具伺服器啟動失敗")
        print("[opencv_mcp_web] 啟動失敗，請查看 logs/toolanything.log")


if __name__ == "__main__":
    main()
