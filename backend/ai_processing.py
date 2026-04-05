import cv2
import math
import random
from typing import Tuple, Dict, Optional, Any
from .anpr import process_vehicle_anpr

try:
    from ultralytics import YOLO
    model = YOLO('yolov8n.pt') 
except ImportError:
    model = None

def calculate_distance(p1, p2):
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])

def process_video(file_path: str, intersection_id: str = "I1", direction: str = "north") -> Dict[str, Any]:
    if model is None:
        return {
            "vehicle_count": 0, "sudden_stop": False, "accident": False,
            "anpr_events": [], "vehicles": [], "alerts": [], "error": "Ultralytics YOLO not installed"
        }

    cap = cv2.VideoCapture(file_path)
    if not cap.isOpened():
        return {
            "vehicle_count": 0, "sudden_stop": False, "accident": False,
            "anpr_events": [], "vehicles": [], "alerts": [], "error": "Cannot open video"
        }

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps == 0:
        fps = 30  # fallback
    
    stationary_frame_threshold = int(fps * 2) # stops for more than 2 seconds

    track_history = {}
    accident_detected = False
    sudden_stop_detected = False
    anpr_events = []
    anpr_checked_ids = set()
    collision_logged_ids = set()

    frame_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1
        current_time = frame_count / fps

        # Native ByteTrack Integration + Confidence filter
        results = model.track(frame, persist=True, tracker="bytetrack.yaml", conf=0.5, classes=[2, 3, 5, 7], verbose=False)

        if results and results[0].boxes and results[0].boxes.id is not None:
            boxes = results[0].boxes.xywh.cpu().numpy()
            track_ids = results[0].boxes.id.cpu().numpy()
            confs = results[0].boxes.conf.cpu().numpy()

            current_frame_boxes = []

            for box, track_id, conf in zip(boxes, track_ids, confs):
                x, y, w, h = box
                center = (float(x), float(y))
                current_frame_boxes.append((track_id, (x, y, w, h), center, conf))

                if track_id not in track_history:
                    track_history[track_id] = {
                        "centers": [], "speeds": [], "times": [],
                        "violating": False, "accident": False, 
                        "frames_stationary": 0, "max_speed": 0.0,
                        "last_box": (0, 0, 0, 0)
                    }
                
                hist = track_history[track_id]
                hist["centers"].append(center)
                hist["times"].append(current_time)
                hist["last_box"] = (x, y, w, h)

                if len(hist["centers"]) > 20:
                    hist["centers"].pop(0)
                    hist["times"].pop(0)
                
                # 10-Frame Temporal Smoothing
                n_frames = min(10, len(hist["centers"]))
                if n_frames > 1:
                    dist = calculate_distance(center, hist["centers"][-n_frames])
                    td = current_time - hist["times"][-n_frames]
                    speed = dist / td if td > 0 else 0.0
                else:
                    speed = 0.0

                hist["speeds"].append(speed)
                if len(hist["speeds"]) > 20:
                    hist["speeds"].pop(0)

                hist["max_speed"] = max(hist["max_speed"], speed)

                # Ignore stationary vehicles at signals (or general stagnation)
                if speed < 10:
                    hist["frames_stationary"] += 1
                else:
                    hist["frames_stationary"] = 0

                # Sudden speed drop (>70%)
                if len(hist["speeds"]) >= 10:
                    past_speed = hist["speeds"][-10]
                    # ensure it was actually moving
                    if past_speed > 100:
                        if speed < past_speed * 0.3:
                            sudden_stop_detected = True
                            hist["violating"] = True
                
                # Fast speeding
                if speed > 600:
                    hist["violating"] = True

                # Random ANPR checks for rule violators (or randomly for demonstration)
                if track_id not in anpr_checked_ids and (hist["violating"] or random.random() < 0.1):
                    # Do not check if they have been completely stationary since they appeared (e.g. parked at lights)
                    if hist["max_speed"] > 10:
                        anpr_checked_ids.add(track_id)
                        cx, cy, cw, ch = int(x), int(y), int(w), int(h)
                        y1, y2 = max(0, int(cy - ch/2)), int(cy + ch/2)
                        x1, x2 = max(0, int(cx - cw/2)), int(cx + cw/2)
                        cropped_frame = frame[y1:y2, x1:x2]
                        if cropped_frame.size > 0:
                            res = process_vehicle_anpr(cropped_frame, intersection_id, "Rule Violator" if hist["violating"] else "None")
                            if res.get("detected") and res.get("challan"):
                                anpr_events.append(res["challan"])

            # Accident Detection logic
            for i in range(len(current_frame_boxes)):
                for j in range(i + 1, len(current_frame_boxes)):
                    id1, box1, pt1, conf1 = current_frame_boxes[i]
                    id2, box2, pt2, conf2 = current_frame_boxes[j]

                    dist = calculate_distance(pt1, pt2)
                    r1 = max(box1[2], box1[3]) / 2.0
                    r2 = max(box2[2], box2[3]) / 2.0
                    
                    # 1. Two vehicles overlap or collide in bounding boxes
                    if dist < (r1 + r2) * 0.7:
                        hist1 = track_history[id1]
                        hist2 = track_history[id2]
                        # 4. Detection confidence > 0.6
                        if conf1 > 0.6 and conf2 > 0.6:
                            # 3. Vehicle stops for more than 2 seconds
                            if hist1["frames_stationary"] > stationary_frame_threshold and hist2["frames_stationary"] > stationary_frame_threshold:
                                # 2. Sudden speed drop (>70%) is inherently satisfied if they historically dropped from a moving speed down to stationary
                                if hist1["max_speed"] > 50 and hist2["max_speed"] > 50:
                                    accident_detected = True
                                    hist1["accident"] = True
                                    hist2["accident"] = True
                                    
                                    # ANPR snapshot of the accident
                                    if id1 not in collision_logged_ids:
                                        collision_logged_ids.add(id1)
                                        cx, cy, cw, ch = int(box1[0]), int(box1[1]), int(box1[2]), int(box1[3])
                                        y1, y2 = max(0, int(cy - ch/2)), int(cy + ch/2)
                                        x1, x2 = max(0, int(cx - cw/2)), int(cx + cw/2)
                                        cr1 = frame[y1:y2, x1:x2]
                                        if cr1.size > 0:
                                            res = process_vehicle_anpr(cr1, intersection_id, "Involved in Collision")
                                            if res.get("detected") and res.get("challan"):
                                                anpr_events.append(res["challan"])

    cap.release()

    structured_vehicles = []
    for tid, h in track_history.items():
        status = "fair"
        if h["accident"]:
            status = "accident"
        elif h["violating"]:
            status = "violator"
            
        current_speed = round(h["speeds"][-1] if h["speeds"] else 0, 1)
        
        # Output structured results for each vehicle
        structured_vehicles.append({
            "vehicle_id": int(tid),
            "speed": current_speed,
            "status": status,
            "accident": h["accident"]
        })

    alerts = []
    if accident_detected:
        alerts.append({
            "type": "accident",
            "location": intersection_id,
            "severity": "medium"
        })

    return {
        "vehicle_count": len(track_history),
        "sudden_stop": sudden_stop_detected,
        "accident": accident_detected,
        "anpr_events": anpr_events,
        "vehicles": structured_vehicles,
        "alerts": alerts,
        "error": None
    }


def detect_emergency_vehicle(file_path: str) -> Optional[str]:
    """
    Detect emergency vehicle in an image or video file.
    Returns the direction ('north', 'south', 'east', 'west') based on its bounding box,
    or None if no emergency vehicle is detected.
    """
    if model is None:
        return None

    # Try reading as an image
    frame = cv2.imread(file_path)
    if frame is None:
        # Try video reading
        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            return None
        ret, frame = cap.read()
        cap.release()
        if not ret or frame is None:
            return None

    results = model(frame, verbose=False)
    if not results or not results[0].boxes:
        return None

    names = results[0].names
    boxes = results[0].boxes.xywh.cpu().numpy()
    classes = results[0].boxes.cls.cpu().numpy()

    height, width = frame.shape[:2]

    for box, cls_id in zip(boxes, classes):
        class_name = names[int(cls_id)].lower()
        if class_name in ["ambulance", "fire truck", "fire_truck"]:
            print("Emergency vehicle detected")
            
            # Simple quadrant mapping: determine which border the center is closest to
            cx, cy = box[0], box[1]
            d_top = cy
            d_bottom = height - cy
            d_left = cx
            d_right = width - cx
            
            min_d = min(d_top, d_bottom, d_left, d_right)
            if min_d == d_top:
                return "north"
            elif min_d == d_bottom:
                return "south"
            elif min_d == d_right:
                return "east"
            else:
                return "west"

    return None
