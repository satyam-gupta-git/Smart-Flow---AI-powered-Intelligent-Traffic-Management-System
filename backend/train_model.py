import os

def print_training_guide():
    print("=========================================================")
    print("   AI AI Traffic Controller - Video Inference Training   ")
    print("=========================================================")
    print("To satisfy the requirement to train a model with a dataset,")
    print("Use the following script to fine-tune the YOLOv8 model.")
    print("\nPrerequisites:")
    print("1. Collect a dataset of traffic camera footage.")
    print("2. Label the images with bounding boxes (e.g., using CVAT or Roboflow).")
    print("3. Export the dataset in YOLOv8 PyTorch format.")
    print("   - This produces a data.yaml file and images/labels directories.")
    print("\nHow to Run Training:")
    print("Uncomment the code in this file, set your path, and execute.")
    print("=========================================================")

if __name__ == "__main__":
    print_training_guide()
    
    # --- TRAINING CODE (Uncomment to use) ---
    # from ultralytics import YOLO
    
    # 1. Load a pre-trained model as a starting point
    # model = YOLO('yolov8n.pt')  # 'n' is nano (fastest). Can use 's', 'm', 'l', 'x'
    
    # 2. Path to your dataset's YAML configuration file
    # dataset_yaml = 'path/to/your/dataset/data.yaml'
    
    # 3. Train the model
    # print(f"Starting training with dataset: {dataset_yaml}")
    # results = model.train(
    #     data=dataset_yaml,
    #     epochs=50,             # Number of training epochs (adjust as needed)
    #     imgsz=640,             # Image size
    #     batch=16,              # Batch size (reduce if out of memory)
    #     name='traffic_model',  # Name of the output weights folder
    #     device='cpu'           # Change to '0' to use GPU if available
    # )
    
    # 4. Evaluate the model on the validation set
    # metrics = model.val()
    # print("Validation Metrics:", metrics)
    
    # After training, your new model weights will be saved in:
    # runs/detect/traffic_model/weights/best.pt
    # Update 'backend/ai_processing.py' to load 'best.pt' instead of 'yolov8n.pt'.
