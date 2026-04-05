"""
Smart Flow – Custom Dataset Training Script
===========================================
Run this script to fine-tune YOLOv8 on your own traffic dataset.

Usage:
  1. Put your images inside:     dataset/images/train/  and  dataset/images/val/
  2. Put your label files inside: dataset/labels/train/  and  dataset/labels/val/
  3. Edit dataset/data.yaml to match your class names.
  4. Run:  python backend/train_model.py

After training finishes, the best model will be saved to:
  runs/detect/traffic_model/weights/best.pt

The script will automatically copy best.pt to the project root
so ai_processing.py picks it up immediately.
"""

import os
import shutil
import sys

# ─────────────────────────────────────────────
# CONFIG  ← edit these if needed
# ─────────────────────────────────────────────
DATASET_YAML     = "dataset/data.yaml"   # path to your data.yaml
BASE_MODEL       = "yolov8n.pt"          # starting weights (n / s / m / l / x)
EPOCHS           = 50                    # increase for better accuracy
IMAGE_SIZE       = 640                   # 640 recommended for YOLOv8
BATCH_SIZE       = 8                     # reduce to 4 if you run out of memory
DEVICE           = "cpu"                 # "cpu" or "0" for GPU
RUN_NAME         = "traffic_model"       # name of the training run folder
# ─────────────────────────────────────────────


def validate_dataset():
    """Check that the required dataset folders and yaml exist before training."""
    required = [
        "dataset/images/train",
        "dataset/images/val",
        "dataset/labels/train",
        "dataset/labels/val",
        DATASET_YAML,
    ]
    missing = [p for p in required if not os.path.exists(p)]
    if missing:
        print("\n❌  Missing required paths:")
        for m in missing:
            print(f"    • {m}")
        print("\nPlease create these directories and add your images/labels.")
        print("See the README section on Dataset Format for details.\n")
        sys.exit(1)

    train_images = os.listdir("dataset/images/train")
    val_images   = os.listdir("dataset/images/val")
    train_labels = os.listdir("dataset/labels/train")

    if not train_images:
        print("❌  dataset/images/train/ is empty. Add your training images.")
        sys.exit(1)
    if not val_images:
        print("❌  dataset/images/val/ is empty. Add your validation images.")
        sys.exit(1)
    if not train_labels:
        print("❌  dataset/labels/train/ is empty. Add your YOLO label .txt files.")
        sys.exit(1)

    print(f"✅  Dataset validated:")
    print(f"    Train images : {len(train_images)}")
    print(f"    Val   images : {len(val_images)}")
    print(f"    Train labels : {len(train_labels)}")


def train():
    try:
        from ultralytics import YOLO
    except ImportError:
        print("❌  ultralytics is not installed.")
        print("    Run:  pip install ultralytics")
        sys.exit(1)

    validate_dataset()

    print(f"\n🚀  Starting training")
    print(f"    Base model   : {BASE_MODEL}")
    print(f"    Dataset      : {DATASET_YAML}")
    print(f"    Epochs       : {EPOCHS}")
    print(f"    Image size   : {IMAGE_SIZE}")
    print(f"    Batch size   : {BATCH_SIZE}")
    print(f"    Device       : {DEVICE}\n")

    model = YOLO(BASE_MODEL)

    results = model.train(
        data=DATASET_YAML,
        epochs=EPOCHS,
        imgsz=IMAGE_SIZE,
        batch=BATCH_SIZE,
        name=RUN_NAME,
        device=DEVICE,
        patience=15,         # early stopping patience
        save_period=10,      # save checkpoint every 10 epochs
        verbose=True,
    )

    # ── Evaluate on validation set ──
    print("\n📊  Running validation…")
    metrics = model.val()
    print(f"    mAP50      : {metrics.box.map50:.4f}")
    print(f"    mAP50-95   : {metrics.box.map:.4f}")

    # ── Copy best.pt to project root so ai_processing.py uses it ──
    best_pt = f"runs/detect/{RUN_NAME}/weights/best.pt"
    if os.path.exists(best_pt):
        dest = "traffic_model_best.pt"
        shutil.copy2(best_pt, dest)
        print(f"\n✅  Custom model saved → {dest}")
        print("    To use this model in the live system, open backend/ai_processing.py")
        print(f"    and change:  model = YOLO('yolov8n.pt')")
        print(f"    to:          model = YOLO('{dest}')")
    else:
        print(f"\n⚠️   best.pt not found at {best_pt}. Check the runs/ folder manually.")

    print("\n🎉  Training complete!\n")


if __name__ == "__main__":
    train()
