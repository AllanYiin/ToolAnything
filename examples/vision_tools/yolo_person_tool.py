from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, List, Optional

from toolanything import tool


@lru_cache(maxsize=2)
def _load_model(model_name: str):
    from ultralytics import YOLO

    return YOLO(model_name)


@tool(
    name="vision.detect_person",
    description="使用 YOLOv8 偵測影像中的人，回傳 bounding boxes 與信心分數",
    tags=["vision", "yolo", "person"],
    metadata={
        "cost": 0.02,
        "latency_hint_ms": 450,
        "side_effect": False,
        "category": "vision",
        "owner": "toolanything.examples",
    },
)
def detect_person(
    image_path: str,
    conf: float = 0.25,
    iou: float = 0.45,
    max_det: int = 300,
    model: str = "yolov8n.pt",
    device: Optional[str] = None,
) -> Dict[str, Any]:
    """使用 YOLOv8 偵測影像中的 person。

    Args:
        image_path: 影像檔案路徑。
        conf: 信心分數門檻（0~1）。
        iou: NMS IoU 門檻（0~1）。
        max_det: 最大偵測數量。
        model: YOLOv8 模型名稱或本機路徑（例如 yolov8n.pt）。
        device: 推論裝置（例如 "cpu", "0"），None 代表自動選擇。
    """
    yolo = _load_model(model)
    results = yolo.predict(
        source=image_path,
        conf=conf,
        iou=iou,
        max_det=max_det,
        device=device,
        verbose=False,
    )

    if not results:
        return {"count": 0, "detections": [], "image_path": image_path}

    result = results[0]
    names = result.names or {}
    detections: List[Dict[str, Any]] = []

    boxes = result.boxes
    if boxes is not None:
        for box in boxes:
            cls_id = int(box.cls[0]) if box.cls is not None else -1
            label = names.get(cls_id, str(cls_id))
            if label != "person" and cls_id != 0:
                continue

            xyxy = box.xyxy[0].tolist()
            detections.append(
                {
                    "label": label,
                    "class_id": cls_id,
                    "confidence": float(box.conf[0]) if box.conf is not None else None,
                    "bbox_xyxy": [float(coord) for coord in xyxy],
                }
            )

    width, height = result.orig_shape[::-1] if result.orig_shape else (None, None)

    return {
        "image_path": image_path,
        "image_width": width,
        "image_height": height,
        "count": len(detections),
        "detections": detections,
    }


if __name__ == "__main__":
    # 簡單示範：python examples/vision_tools/yolo_person_tool.py path/to/image.jpg
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python yolo_person_tool.py <image_path>")
        raise SystemExit(1)

    payload = detect_person(sys.argv[1])
    print(json.dumps(payload, ensure_ascii=False, indent=2))
