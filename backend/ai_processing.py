import cv2
import math
from typing import Tuple, Dict

try:
    from ultralytics import YOLO
    # Load the pre-trained YOLOv8 nano model for immediate use. 
    # For a real deployed scenario, this would load weights from train_model.py
    model = YOLO('yolov8n.pt') 
except ImportError:
    model = None

def calculate_distance(p1, p2):
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])

def process_video(video_path: str) -> Dict[str, any]:
    """
    Process a video to detect the number of vehicles, sudden stops, and accidents.
    Returns a dictionary with the results.
    """
    if model is None:
        return {
            "vehicle_count": 0,
            "sudden_stop": False,
            "accident": False,
            "error": "Ultralytics YOLO not installed"
        }

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {
            "vehicle_count": 0,
            "sudden_stop": False,
            "accident": False,
            "error": "Cannot open video"
        }

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps == 0:
        fps = 30  # fallback

    # Track history: {track_id: [(x, y, time_sec, speed), ...]}
    track_history = {}
    
    unique_vehicles = set()
    accident_detected = False
    sudden_stop_detected = False

    frame_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1
        current_time = frame_count / fps

        # Run tracking (persist=True ensures consistent IDs across frames)
        # We only track classes 2 (car), 3 (motorcycle), 5 (bus), 7 (truck) in COCO
        results = model.track(frame, persist=True, classes=[2, 3, 5, 7], verbose=False)

        if results and results[0].boxes and results[0].boxes.id is not None:
            boxes = results[0].boxes.xywh.cpu().numpy()
            track_ids = results[0].boxes.id.cpu().numpy()

            # For collision detection: store current frame boxes
            current_frame_boxes = []

            for box, track_id in zip(boxes, track_ids):
                unique_vehicles.add(track_id)
                x, y, w, h = box
                center = (float(x), float(y))
                current_frame_boxes.append((track_id, (x, y, w, h), center))

                if track_id not in track_history:
                    track_history[track_id] = []
                
                # Calculate speed from last point
                speed = 0.0
                if len(track_history[track_id]) > 0:
                    last_pt = track_history[track_id][-1]
                    dist = calculate_distance(center, last_pt[0])
                    time_diff = current_time - last_pt[1]
                    if time_diff > 0:
                        speed = dist / time_diff
                
                track_history[track_id].append((center, current_time, speed))

                # Keep history manageable (e.g. last 30 frames)
                if len(track_history[track_id]) > 30:
                    track_history[track_id].pop(0)

                # Sudden stop detection logic:
                # If a vehicle was moving fast but suddenly its speed drops near 0 
                # within a short time frame.
                history = track_history[track_id]
                if len(history) >= 15:
                    # avg speed of older half vs recent half
                    past_speeds = [h[2] for h in history[-15:-5]]
                    recent_speeds = [h[2] for h in history[-5:]]
                    
                    avg_past = sum(past_speeds) / len(past_speeds) if past_speeds else 0
                    avg_recent = sum(recent_speeds) / len(recent_speeds) if recent_speeds else 0
                    
                    if avg_past > 100 and avg_recent < 10:  # Thresholds (pixels/sec)
                        sudden_stop_detected = True

            # Collision Detection Logic:
            # Check for overlapping bounding boxes where both vehicles' speeds are now 0
            for i in range(len(current_frame_boxes)):
                for j in range(i + 1, len(current_frame_boxes)):
                    id1, box1, pt1 = current_frame_boxes[i]
                    id2, box2, pt2 = current_frame_boxes[j]

                    dist = calculate_distance(pt1, pt2)
                    
                    # Approximate radius based on width/height
                    r1 = max(box1[2], box1[3]) / 2.0
                    r2 = max(box2[2], box2[3]) / 2.0
                    
                    if dist < (r1 + r2) * 0.7:  # Bounding boxes significantly overlap
                        # Check speeds
                        if id1 in track_history and id2 in track_history:
                            v1 = track_history[id1][-1][2]
                            v2 = track_history[id2][-1][2]
                            
                            if v1 < 10 and v2 < 10:
                                accident_detected = True

        # Stop early if accident is found to save processing time
        # (in a real-time system it would continue, but for file uploads we can return fast)
        if accident_detected:
            break

    cap.release()

    return {
        "vehicle_count": len(unique_vehicles),
        "sudden_stop": sudden_stop_detected,
        "accident": accident_detected,
        "error": None
    }
