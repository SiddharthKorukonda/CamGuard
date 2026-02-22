"""Computer vision pipeline for fall detection using OpenCV + YOLO.
Inspired by SurveiLens approach: OpenCV for camera capture, YOLO for detection."""

from __future__ import annotations

import asyncio
import base64
import logging
import platform
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger("camguard.vision")

_cameras: dict[str, dict] = {}
_detection_tasks: dict[str, asyncio.Task] = {}
_latest_frames: dict[str, bytes] = {}
_yolo_model = None

_person_tracker: dict[str, list[dict]] = {}

_executor = ThreadPoolExecutor(max_workers=4)

UPLOAD_DIR = Path(__file__).parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


def _get_yolo():
    global _yolo_model
    if _yolo_model is not None:
        return _yolo_model
    try:
        from ultralytics import YOLO
        model_path = Path(__file__).parent.parent / "yolov8n.pt"
        if model_path.exists():
            _yolo_model = YOLO(str(model_path))
        else:
            _yolo_model = YOLO("yolov8n.pt")
        logger.info("YOLO model loaded successfully")
        return _yolo_model
    except ImportError:
        logger.warning("ultralytics not installed – using mock detection")
        return None
    except Exception as e:
        logger.error("YOLO load error: %s", e)
        return None


def start_camera(camera_id: str, device: int = 0) -> bool:
    """Open a camera device via OpenCV."""
    if camera_id in _cameras and _cameras[camera_id].get("cap"):
        return True
    try:
        cap = None
        if platform.system() == "Darwin":
            cap = cv2.VideoCapture(device, cv2.CAP_AVFOUNDATION)
        if cap is None or not cap.isOpened():
            cap = cv2.VideoCapture(device)
        if not cap.isOpened():
            cap = cv2.VideoCapture(device, cv2.CAP_ANY)
        if not cap.isOpened():
            logger.error(
                "Cannot open camera device %d. "
                "If running in Docker on macOS, camera access is not available. "
                "Use 'Add Video' to upload a video file instead.",
                device,
            )
            return False
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 15)
        _cameras[camera_id] = {
            "cap": cap,
            "device": device,
            "type": "live",
            "running": True,
        }
        logger.info("Camera %s opened on device %d", camera_id, device)
        return True
    except Exception as e:
        logger.error("Camera open error: %s", e)
        return False


def _convert_video_if_needed(video_path: str) -> str:
    """Convert video to H.264 MP4 if OpenCV can't open it directly."""
    import subprocess
    import shutil

    if shutil.which("ffmpeg") is None:
        logger.warning("ffmpeg not found – cannot convert video")
        return video_path

    out_path = str(Path(video_path).with_suffix(".converted.mp4"))
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", video_path,
                "-c:v", "libx264", "-preset", "fast",
                "-crf", "23", "-an", out_path,
            ],
            capture_output=True, timeout=120,
        )
        if Path(out_path).exists() and Path(out_path).stat().st_size > 0:
            logger.info("Converted video: %s -> %s", video_path, out_path)
            return out_path
    except Exception as e:
        logger.warning("Video conversion failed: %s", e)
    return video_path


def start_video(camera_id: str, video_path: str) -> bool:
    """Open a video file via OpenCV."""
    if not Path(video_path).exists():
        logger.error("Video file not found: %s", video_path)
        return False
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            cap = cv2.VideoCapture(video_path, cv2.CAP_FFMPEG)
        if not cap.isOpened():
            converted = _convert_video_if_needed(video_path)
            if converted != video_path:
                cap = cv2.VideoCapture(converted)
                video_path = converted
        if not cap.isOpened():
            logger.error("Cannot open video: %s", video_path)
            return False

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        logger.info(
            "Video opened: %s (%dx%d, %.1f FPS, %d frames)",
            video_path, width, height, fps, total_frames,
        )

        _cameras[camera_id] = {
            "cap": cap,
            "path": video_path,
            "type": "video",
            "running": True,
            "fps": fps,
            "total_frames": total_frames,
        }
        _person_tracker[camera_id] = []
        return True
    except Exception as e:
        logger.error("Video open error: %s", e)
        return False


def stop_camera(camera_id: str):
    """Release camera resources."""
    cam = _cameras.pop(camera_id, None)
    if cam and cam.get("cap"):
        cam["cap"].release()
    task = _detection_tasks.pop(camera_id, None)
    if task:
        task.cancel()
    _latest_frames.pop(camera_id, None)
    _person_tracker.pop(camera_id, None)
    logger.info("Camera %s stopped", camera_id)


def stop_all():
    for cid in list(_cameras.keys()):
        stop_camera(cid)


def get_frame_jpeg(camera_id: str) -> Optional[bytes]:
    """Get the latest JPEG frame for a camera."""
    return _latest_frames.get(camera_id)


def _read_frame_blocking(camera_id: str) -> Optional[np.ndarray]:
    """Read a single frame from camera (blocking, meant for executor)."""
    cam = _cameras.get(camera_id)
    if not cam or not cam.get("cap"):
        return None
    ret, frame = cam["cap"].read()
    if not ret:
        if cam.get("type") == "video":
            cam["cap"].set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = cam["cap"].read()
            if not ret:
                return None
            logger.info("Video %s looped back to start", camera_id)
        else:
            return None
    return frame


def _run_yolo_blocking(frame: np.ndarray, bed_polygon=None) -> dict:
    """Run YOLO + fall heuristics on a frame (blocking, meant for executor)."""
    return detect_fall(frame, bed_polygon)


def detect_fall(frame: np.ndarray, bed_polygon: list[list[float]] | None = None) -> dict:
    """Run fall detection on a frame using YOLO person detection + position heuristics.

    The detection uses multiple complementary criteria to catch different
    types of falls:
      - Aspect-ratio based: a person whose bounding box is wider than tall
        is likely lying down.
      - Position based: a person low in the frame is likely on the floor.
      - Compactness: a fallen person occupies less vertical space.
    """
    yolo = _get_yolo()
    result = {
        "persons": [],
        "fall_detected": False,
        "edge_warning": False,
        "annotated_frame": frame.copy(),
        "labels": [],
    }

    if yolo is None:
        return result

    h_input, w_input = frame.shape[:2]
    infer_size = 640
    if w_input > 2000 or h_input > 1500:
        infer_size = 1280

    try:
        detections = yolo.predict(
            frame, imgsz=infer_size, conf=0.20, verbose=False, classes=[0]
        )[0]
    except Exception as e:
        logger.error("YOLO predict error: %s", e)
        return result

    h, w = frame.shape[:2]
    annotated = frame.copy()

    bed_poly = None
    if bed_polygon and len(bed_polygon) >= 3:
        bed_poly = np.array(bed_polygon, dtype=np.int32)
        cv2.polylines(annotated, [bed_poly], True, (0, 255, 255), 2)

    num_boxes = len(detections.boxes)
    if num_boxes > 0:
        logger.debug("YOLO found %d person(s) in frame (%dx%d)", num_boxes, w, h)

    for box in detections.boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
        conf = float(box.conf.item())
        person_h = y2 - y1
        person_w = x2 - x1
        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2
        aspect_ratio = person_w / max(person_h, 1)

        h_ratio = person_h / h
        y2_ratio = y2 / h
        cy_ratio = center_y / h

        is_horizontal = aspect_ratio > 0.9
        is_very_horizontal = aspect_ratio > 1.3
        is_compact = h_ratio < 0.50
        is_very_compact = h_ratio < 0.25
        is_low_in_frame = y2_ratio > 0.65
        center_in_lower_half = cy_ratio > 0.50

        is_fallen = (
            is_very_horizontal
            or (is_horizontal and is_compact)
            or (is_low_in_frame and aspect_ratio > 0.80 and is_compact)
            or (center_in_lower_half and is_horizontal and h_ratio < 0.45)
            or (aspect_ratio > 0.75 and is_very_compact)
        )

        is_on_floor = is_low_in_frame and center_in_lower_half and is_compact

        logger.debug(
            "Person: ar=%.2f h_ratio=%.2f y2_ratio=%.2f cy_ratio=%.2f "
            "conf=%.2f fallen=%s on_floor=%s",
            aspect_ratio, h_ratio, y2_ratio, cy_ratio,
            conf, is_fallen, is_on_floor,
        )

        at_edge = False
        if bed_poly is not None:
            dist = cv2.pointPolygonTest(
                bed_poly, (float(center_x), float(center_y)), True
            )
            at_edge = -50 < dist < 20 and dist < 0

        person_info = {
            "bbox": [x1, y1, x2, y2],
            "confidence": conf,
            "aspect_ratio": round(aspect_ratio, 2),
            "center": [center_x, center_y],
            "fallen": is_fallen or is_on_floor,
            "at_edge": at_edge,
        }
        result["persons"].append(person_info)

        if is_fallen or is_on_floor:
            result["fall_detected"] = True
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 0, 255), 3)
            label = f"FALL DETECTED {conf:.0%}"
            cv2.putText(
                annotated, label, (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2,
            )
            result["labels"].append("FALL_DETECTED")
            logger.info(
                "Fall detected: ar=%.2f h_ratio=%.2f y2_ratio=%.2f conf=%.2f",
                aspect_ratio, person_h / h, y2 / h, conf,
            )
        elif at_edge:
            result["edge_warning"] = True
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 165, 255), 3)
            cv2.putText(
                annotated, f"AT EDGE {conf:.0%}", (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2,
            )
            result["labels"].append("AT_EDGE")
        else:
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(
                annotated, f"Person {conf:.0%}", (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2,
            )

    result["annotated_frame"] = annotated
    return result


async def run_detection_loop(
    camera_id: str,
    bed_polygon: list[list[float]] | None = None,
    on_fall=None,
    on_edge=None,
    monitoring_type: str = "old_people",
):
    """Continuous detection loop for a camera.

    Blocking OpenCV reads and YOLO inference are offloaded to a thread pool
    so the asyncio event loop stays responsive for WebSocket and API traffic.
    """
    logger.info("Starting detection loop for camera %s", camera_id)
    last_fall_time = 0
    last_edge_time = 0
    FALL_COOLDOWN = 30
    EDGE_COOLDOWN = 15

    loop = asyncio.get_event_loop()
    frame_count = 0
    detection_count = 0
    fall_count = 0
    start_ts = time.time()

    while camera_id in _cameras and _cameras[camera_id].get("running"):
        try:
            frame = await loop.run_in_executor(
                _executor, _read_frame_blocking, camera_id
            )
        except Exception as e:
            logger.error("Frame read error for %s: %s", camera_id, e)
            await asyncio.sleep(0.5)
            continue

        if frame is None:
            await asyncio.sleep(0.1)
            continue

        frame_count += 1

        if frame_count % 3 != 0:
            _, jpeg = cv2.imencode(
                ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70]
            )
            _latest_frames[camera_id] = jpeg.tobytes()
            await asyncio.sleep(1.0 / 30)
            continue

        try:
            det = await loop.run_in_executor(
                _executor, _run_yolo_blocking, frame, bed_polygon
            )
        except Exception as e:
            logger.error("Detection error for %s: %s", camera_id, e)
            await asyncio.sleep(0.5)
            continue

        detection_count += 1
        annotated = det["annotated_frame"]

        _, jpeg = cv2.imencode(
            ".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 70]
        )
        _latest_frames[camera_id] = jpeg.tobytes()

        now = time.time()

        if det["fall_detected"] and (now - last_fall_time) > FALL_COOLDOWN:
            last_fall_time = now
            fall_count += 1
            logger.warning(
                "FALL #%d on camera %s (frame %d, %d persons detected)",
                fall_count, camera_id, frame_count, len(det["persons"]),
            )
            if on_fall:
                _, raw_jpeg = cv2.imencode(
                    ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80]
                )
                frame_b64 = base64.b64encode(raw_jpeg.tobytes()).decode()
                try:
                    await on_fall(camera_id, frame_b64, monitoring_type)
                except Exception as e:
                    logger.error("on_fall callback error: %s", e)

        elif det["edge_warning"] and (now - last_edge_time) > EDGE_COOLDOWN:
            last_edge_time = now
            logger.warning(
                "EDGE warning on camera %s (frame %d)", camera_id, frame_count,
            )
            if on_edge:
                _, raw_jpeg = cv2.imencode(
                    ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80]
                )
                frame_b64 = base64.b64encode(raw_jpeg.tobytes()).decode()
                try:
                    await on_edge(camera_id, frame_b64, monitoring_type)
                except Exception as e:
                    logger.error("on_edge callback error: %s", e)

        if detection_count % 100 == 0:
            elapsed = time.time() - start_ts
            logger.info(
                "Camera %s stats: %d frames, %d detections, %d falls in %.0fs",
                camera_id, frame_count, detection_count, fall_count, elapsed,
            )

        await asyncio.sleep(1.0 / 15)

    elapsed = time.time() - start_ts
    logger.info(
        "Detection loop ended for %s: %d frames, %d detections, %d falls in %.0fs",
        camera_id, frame_count, detection_count, fall_count, elapsed,
    )


def start_detection_task(
    camera_id: str,
    bed_polygon: list[list[float]] | None = None,
    on_fall=None,
    on_edge=None,
    monitoring_type: str = "old_people",
):
    """Start detection as an asyncio task."""
    if camera_id in _detection_tasks:
        _detection_tasks[camera_id].cancel()

    task = asyncio.create_task(
        run_detection_loop(camera_id, bed_polygon, on_fall, on_edge, monitoring_type)
    )
    _detection_tasks[camera_id] = task
    return task


def list_active_cameras() -> list[str]:
    return list(_cameras.keys())
