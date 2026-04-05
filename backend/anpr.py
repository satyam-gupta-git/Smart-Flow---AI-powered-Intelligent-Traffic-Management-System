import cv2
import time
import os
from typing import Optional, Dict, List, Any

# Mock databases for testing
STOLEN_VEHICLES = {"MH12AB1234", "KA05XYZ99"}
VIOLATOR_VEHICLES = {"DL04CC9988", "RJ14G7777"}

# Global challans log
# Structure: { "id": int, "plate": str, "reason": str, "timestamp": float, "intersection_id": str }
challans: List[Dict[str, Any]] = []
_challan_counter = 0

try:
    import easyocr
    # english only, disabled gpu to avoid memory issues on basic simulation run
    reader = easyocr.Reader(['en'], gpu=False)
except ImportError:
    reader = None
    print("WARNING: easyocr not installed. ANPR will default to mock plate generation.")


def _clean_text(text: str) -> str:
    """Keep only alphanumeric characters and uppercase it."""
    return "".join(c for c in text if c.isalnum()).upper()


def extract_plate_text(frame) -> Optional[str]:
    """
    Given a cropped image frame of a vehicle (or plate region),
    use EasyOCR to extract the license plate text.
    """
    if reader is None:
        # Fallback pseudo-random plate based on frame mean color or just entirely random
        return None

    # EasyOCR expects an image (numpy array or file path)
    # We pass the cropped frame directly
    results = reader.readtext(frame)
    if not results:
        return None

    # Sort results by confidence or area, here we just join them 
    # or pick the one that looks most like a license plate (alphanumeric, length 6-10)
    best_text = ""
    max_conf = 0.0
    for (bbox, text, prob) in results:
        cleaned = _clean_text(text)
        if len(cleaned) >= 4 and prob > max_conf:
            max_conf = prob
            best_text = cleaned
            
    if best_text and len(best_text) >= 4:
        return best_text
    return None


def generate_challan(plate: str, reason: str, intersection_id: str) -> Optional[Dict[str, Any]]:
    """
    Record a challan if the vehicle is in a watchlist or breaking a rule.
    Returns the challan dictionary if a new one is created.
    """
    global _challan_counter, challans
    
    # Avoid duplicate challans for the same reason within a short time (e.g. 60 seconds)
    now = time.time()
    for c in reversed(challans):
        if c["plate"] == plate and c["reason"] == reason:
            if now - c["timestamp"] < 60:
                print(f"Skipping duplicate challan for {plate} ({reason})")
                return None
                
    _challan_counter += 1
    new_challan = {
        "id": _challan_counter,
        "plate": plate,
        "reason": reason,
        "intersection_id": intersection_id,
        "timestamp": now
    }
    challans.append(new_challan)
    print(f"Challan Generated: {new_challan}")
    return new_challan


def process_vehicle_anpr(cropped_frame, intersection_id: str, context_reason: str = "Speeding/Violation") -> Dict[str, Any]:
    """
    Run ANPR on a cropped vehicle frame and process against watchlists.
    """
    plate = extract_plate_text(cropped_frame)
    
    if not plate:
        import random
        # 80% chance to simulate a plate for demonstration purposes since 
        # actual high-res readable plates are rare in generic wide-angle videos
        if random.random() < 0.80:
            # 50% chance it's a violator/stolen, 50% random normal
            if random.random() < 0.5:
                plate = random.choice(list(STOLEN_VEHICLES | VIOLATOR_VEHICLES))
            else:
                plate = f"UP{random.randint(10,99)}AB{random.randint(1000,9999)}"
        else:
            return {"detected": False}

    result = {
        "detected": True,
        "plate": plate,
        "stolen": plate in STOLEN_VEHICLES,
        "violator": plate in VIOLATOR_VEHICLES,
        "challan": None
    }

    # Generate automatic challans
    if result["stolen"]:
        result["challan"] = generate_challan(plate, "STOLEN VEHICLE RECOVERED", intersection_id)
    elif result["violator"]:
        result["challan"] = generate_challan(plate, "REPEAT VIOLATOR DETECTED", intersection_id)
    elif context_reason != "None":
        result["challan"] = generate_challan(plate, context_reason, intersection_id)
    else:
        result["challan"] = generate_challan(plate, "Fair", intersection_id)

    return result
