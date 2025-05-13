from ultralytics import YOLO
from deepface import DeepFace
import cv2
import numpy as np
import os
import pyttsx3
from .face_detector import load_yolo_model_and_check_known_face,detect_persons_yolo,verify_if_me_with_deepface

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

MAX_DETECTION_ATTEMPTS = 150

tts_engine = None
try:
    tts_engine = pyttsx3.init()
except Exception as e_tts:
    print(f"Warning: TTS engine initialization failed: {e_tts}. Speech will be disabled.")

def speak(text_to_speak):
    if tts_engine:
        try:
            print(f"JARVIS SPEAKS: {text_to_speak}")
            tts_engine.say(text_to_speak)
            tts_engine.runAndWait()
        except Exception as e_speak:
            print(f"Error during speech: {e_speak}")
    else:
        print(f"JARVIS (TTS disabled): {text_to_speak}")


def run_jarvis_vision_deepface():
    yolo_model = load_yolo_model_and_check_known_face()
    if not yolo_model:
        print("Exiting visual detection: issues loading YOLO model or checking known face path.")
        return False

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open webcam for visual detection.")
        return False

    print(f"Starting Jarvis visual detection with DeepFace ({DEEPFACE_MODEL_NAME})... Max attempts: {MAX_DETECTION_ATTEMPTS}. Press 'q' to quit early.")

    attempt_count = 0

    while attempt_count < MAX_DETECTION_ATTEMPTS:
        ret, frame = cap.read()
        
        if not ret:
            print("Error: Failed to grab frame from webcam.")
            break

        attempt_count += 1

        all_detected_person_boxes, annotated_frame = detect_persons_yolo(frame, yolo_model)
        num_total_persons_detected = len(all_detected_person_boxes)
        num_persons_recognized_as_me = 0
        my_recognized_boxes_coords = []

        if num_total_persons_detected > 0:
            for (x1, y1, x2, y2) in all_detected_person_boxes:
                h_frame, w_frame = frame.shape[:2]
                x1_c, y1_c = max(0, x1), max(0, y1)
                x2_c, y2_c = min(w_frame, x2), min(h_frame, y2)

                if x1_c >= x2_c or y1_c >= y2_c:
                    continue
                person_roi_bgr = frame[y1_c:y2_c, x1_c:x2_c]

                if verify_if_me_with_deepface(person_roi_bgr, KNOWN_FACE_IMAGE_PATH):
                    num_persons_recognized_as_me += 1
                    my_recognized_boxes_coords.append((x1, y1, x2, y2))

        jarvis_is_online_for_me = (num_total_persons_detected == 1 and num_persons_recognized_as_me == 1)

        if jarvis_is_online_for_me:
            speak("Hello Master, Jarvis is online.")
            print(f"JARVIS {JARVIS_ONLINE_SYMBOL}: Online for Master! Visual detection successful.")
            cv2.putText(annotated_frame, f"{JARVIS_ONLINE_SYMBOL} JARVIS: Online", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, MASTER_BOX_COLOR, 2, cv2.LINE_AA)
            
            if my_recognized_boxes_coords:
                mx1, my1, mx2, my2 = my_recognized_boxes_coords[0]
                cv2.rectangle(annotated_frame, (mx1, my1), (mx2, my2), MASTER_BOX_COLOR, BOX_THICKNESS)
                cv2.putText(annotated_frame, f"{MASTER_SYMBOL} MASTER", (mx1, my1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, MASTER_BOX_COLOR, 2, cv2.LINE_AA)
            
            cv2.imshow("Jarvis Cam - Success", annotated_frame)
            cv2.waitKey(1500)

            cap.release()
            cv2.destroyAllWindows()
            return True
        
        else:
            if num_total_persons_detected > 0:
                status_text = f"{PERSON_SYMBOL} Persons: {num_total_persons_detected} (Attempt: {attempt_count}/{MAX_DETECTION_ATTEMPTS})"
                cv2.putText(annotated_frame, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,255), 2, cv2.LINE_AA)
                
                if num_persons_recognized_as_me > 0:
                    status_me_text = f"{MASTER_SYMBOL} You: {num_persons_recognized_as_me}"
                    cv2.putText(annotated_frame, status_me_text, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, ME_BOX_COLOR, 2, cv2.LINE_AA)
                    
                    for mx1, my1, mx2, my2 in my_recognized_boxes_coords:
                        cv2.rectangle(annotated_frame, (mx1, my1), (mx2, my2), ME_BOX_COLOR, BOX_THICKNESS)
                        cv2.putText(annotated_frame, f"{MASTER_SYMBOL} ME", (mx1, my1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, ME_BOX_COLOR, 2, cv2.LINE_AA)
            
            elif num_total_persons_detected == 0:
                cv2.putText(annotated_frame, f"No persons detected (Attempt: {attempt_count}/{MAX_DETECTION_ATTEMPTS})", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,100,0), 2, cv2.LINE_AA)

            cv2.imshow("Jarvis Cam - Detecting", annotated_frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            print("Visual detection stopped by user ('q' pressed).")
            speak("Visual detection cancelled.")
            break

    cap.release()
    cv2.destroyAllWindows()

    if attempt_count >= MAX_DETECTION_ATTEMPTS and not (num_total_persons_detected == 1 and num_persons_recognized_as_me == 1):
        print("Max detection attempts reached. Master not detected under required conditions.")
        speak("Visual detection timed out. Master not confirmed.")

    print("Jarvis visual detection routine finished.")
    return False

