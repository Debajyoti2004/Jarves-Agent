from ultralytics import YOLO
from deepface import DeepFace
import cv2
import numpy as np
import os

YOLO_MODEL_PATH = "yolov8n.pt"
KNOWN_FACE_IMAGE_PATH = "C:/Users/Debajyoti/OneDrive/Desktop/Jarves full agent/Authentication/master_image.jpg"
DEEPFACE_MODEL_NAME = 'VGG-Face'
DEEPFACE_DISTANCE_METRIC = 'cosine'
YOLO_CONFIDENCE_THRESHOLD = 0.4
PERSON_CLASS_ID = 0

MASTER_BOX_COLOR = (0, 255, 0)
ME_BOX_COLOR = (0, 255, 255)
BOX_THICKNESS = 2

MASTER_SYMBOL = "★"
PERSON_SYMBOL = "👤"
JARVIS_ONLINE_SYMBOL = "💡"

def load_yolo_model_and_check_known_face():
    print("Loading YOLO model...")
    try:
        yolo_model = YOLO(YOLO_MODEL_PATH)
    except Exception as e:
        print(f"Error loading YOLO model: {e}")
        return None
    print("YOLO model loaded.")

    print(f"Checking known face image path: {KNOWN_FACE_IMAGE_PATH}")
    if not os.path.exists(KNOWN_FACE_IMAGE_PATH):
        print(f"Error: Known face image file not found at '{KNOWN_FACE_IMAGE_PATH}'. Please update the path.")
        return None
    print("Known face image path is valid.")
    return yolo_model

def detect_persons_yolo(frame, yolo_model):
    person_boxes_coords = []
    annotated_frame_by_yolo = frame.copy()

    yolo_results_list = yolo_model.predict(frame, classes=[PERSON_CLASS_ID], verbose=False, conf=YOLO_CONFIDENCE_THRESHOLD)

    if yolo_results_list:
        res = yolo_results_list[0]
        annotated_frame_by_yolo = res.plot()

        detected_person_boxes_data = res.boxes[res.boxes.cls == PERSON_CLASS_ID]
        for box_data in detected_person_boxes_data:
            person_boxes_coords.append(list(map(int, box_data.xyxy[0].tolist())))
    return person_boxes_coords, annotated_frame_by_yolo

def verify_if_me_with_deepface(person_roi_bgr, known_face_img_path):
    if person_roi_bgr.size == 0:
        return False
    try:
        result = DeepFace.verify(img1_path=known_face_img_path,
                                 img2_path=person_roi_bgr,
                                 model_name=DEEPFACE_MODEL_NAME,
                                 distance_metric=DEEPFACE_DISTANCE_METRIC,
                                 enforce_detection=True,
                                 detector_backend='opencv')
        return result['verified']
    except ValueError as ve:
        return False
    except Exception as e:
        print(f"Error during DeepFace verification: {e}")
        return False