import cv2
import pytesseract
import numpy as np
import google.generativeai as genai
import os
import json
from dotenv import load_dotenv
import time
import logging

logger = logging.getLogger("JarvesScannerTool")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('✨ %(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
if not logger.handlers:
    logger.addHandler(handler)

load_dotenv()
google_api_key = os.getenv("GOOGLE_API_KEY")
if google_api_key:
    genai.configure(api_key=google_api_key)
else:
    logger.warning("⚠️ GOOGLE_API_KEY environment variable not set. LLM functions will fail if called.")

COLOR_BRIGHT_GREEN = (0, 255, 0)
COLOR_NEON_CYAN = (255, 255, 0)
COLOR_HOT_PINK = (180, 105, 255)
COLOR_DARK_GRAY_BG = (50, 50, 50)
COLOR_VIBRANT_YELLOW = (0, 255, 255)

def put_text_with_bg(img, text, org, font_face, font_scale, text_color, bg_color, thickness=1, line_type=cv2.LINE_AA, padding=5):
    (text_width, text_height), baseline = cv2.getTextSize(text, font_face, font_scale, thickness)
    bg_tl_x = org[0] - padding; bg_tl_y = org[1] - text_height - baseline - padding
    bg_br_x = org[0] + text_width + padding; bg_br_y = org[1] + baseline + padding
    img_h, img_w = img.shape[:2]
    bg_tl_x = max(0, bg_tl_x); bg_tl_y = max(0, bg_tl_y)
    bg_br_x = min(img_w -1 , bg_br_x); bg_br_y = min(img_h -1 , bg_br_y)
    if bg_br_x > bg_tl_x and bg_br_y > bg_tl_y:
        sub_img = img[bg_tl_y:bg_br_y, bg_tl_x:bg_br_x]
        bg_rect_color_np = np.array(bg_color, dtype=np.uint8)
        if bg_rect_color_np.size == 1: bg_rect_color_np = np.array([bg_color, bg_color, bg_color], dtype=np.uint8)
        if sub_img.size > 0:
            bg_rect = np.full(sub_img.shape, bg_rect_color_np, dtype=np.uint8)
            res = cv2.addWeighted(sub_img, 0.5, bg_rect, 0.5, 1.0)
            img[bg_tl_y:bg_br_y, bg_tl_x:bg_br_x] = res
    cv2.putText(img, text, org, font_face, font_scale, text_color, thickness, line_type)

def find_document_contours(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(blurred, 50, 150)
    contours, _ = cv2.findContours(edged.copy(), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]
    doc_contour = None
    for c in contours:
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) == 4:
            if cv2.contourArea(approx) > (image.shape[0] * image.shape[1] * 0.05):
                doc_contour = approx; break
    return doc_contour

def apply_brightness_contrast(input_img, brightness=0, contrast=0):
    if brightness != 0:
        if brightness > 0: shadow = brightness; highlight = 255
        else: shadow = 0; highlight = 255 + brightness
        alpha_b = (highlight - shadow) / 255; gamma_b = shadow
        buf = cv2.addWeighted(input_img, alpha_b, input_img, 0, gamma_b)
    else: buf = input_img.copy()
    if contrast != 0:
        f = 131 * (contrast + 127) / (127 * (131 - contrast))
        alpha_c = f; gamma_c = 127 * (1 - f)
        buf = cv2.addWeighted(buf, alpha_c, buf, 0, gamma_c)
    return buf

roi_start_point_g = (-1, -1); roi_end_point_g = (-1, -1)
roi_drawing_g = False; roi_defined_g = False

def roi_mouse_callback(event, x, y, flags, param):
    global roi_start_point_g, roi_end_point_g, roi_drawing_g, roi_defined_g
    if event == cv2.EVENT_LBUTTONDOWN:
        roi_start_point_g = (x, y); roi_end_point_g = (x, y)
        roi_drawing_g = True; roi_defined_g = False
    elif event == cv2.EVENT_MOUSEMOVE:
        if roi_drawing_g: roi_end_point_g = (x, y)
    elif event == cv2.EVENT_LBUTTONUP:
        roi_end_point_g = (x, y); roi_drawing_g = False
        x1_temp, y1_temp = roi_start_point_g; x2_temp, y2_temp = roi_end_point_g
        final_x1 = min(x1_temp, x2_temp); final_y1 = min(y1_temp, y2_temp)
        final_x2 = max(x1_temp, x2_temp); final_y2 = max(y1_temp, y2_temp)
        if abs(final_x1 - final_x2) > 5 and abs(final_y1 - final_y2) > 5:
            roi_start_point_g = (final_x1, final_y1); roi_end_point_g = (final_x2, final_y2)
            roi_defined_g = True
        else:
            roi_defined_g = False; roi_start_point_g = (-1, -1); roi_end_point_g = (-1, -1)

def interactive_roi_selection(input_image, window_name="Select ROI - Jarvis"):
    global roi_start_point_g, roi_end_point_g, roi_drawing_g, roi_defined_g
    roi_start_point_g = (-1, -1); roi_end_point_g = (-1, -1)
    roi_drawing_g = False; roi_defined_g = False
    clone_for_roi = input_image.copy()
    cv2.namedWindow(window_name); cv2.setMouseCallback(window_name, roi_mouse_callback)
    font_roi, font_scale_roi, text_color_roi, bg_color_roi = cv2.FONT_HERSHEY_SIMPLEX, 0.7, COLOR_NEON_CYAN, COLOR_DARK_GRAY_BG
    while True:
        display_roi_frame = clone_for_roi.copy()
        if roi_drawing_g or roi_defined_g:
            if roi_start_point_g != (-1,-1) and roi_end_point_g != (-1,-1):
                 cv2.rectangle(display_roi_frame, roi_start_point_g, roi_end_point_g, COLOR_BRIGHT_GREEN, 2)
        put_text_with_bg(display_roi_frame, "Drag ROI. 'C':Crop, 'S':Skip, 'R':Reset", (10,50), font_roi, font_scale_roi, text_color_roi, bg_color_roi, thickness=2)
        cv2.imshow(window_name, display_roi_frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord('r') or key == ord('R'):
            roi_start_point_g = (-1, -1); roi_end_point_g = (-1, -1)
            roi_drawing_g = False; roi_defined_g = False
        elif key == ord('s') or key == ord('S'):
            cv2.destroyWindow(window_name); return input_image
        elif key == ord('c') or key == ord('C'):
            if roi_defined_g:
                x1, y1 = roi_start_point_g; x2, y2 = roi_end_point_g
                h_img, w_img = input_image.shape[:2]
                x1_c, y1_c = max(0, x1), max(0, y1); x2_c, y2_c = min(w_img, x2), min(h_img, y2)
                if x1_c < x2_c and y1_c < y2_c:
                    cropped_image = input_image[y1_c:y2_c, x1_c:x2_c]
                    cv2.destroyWindow(window_name); return cropped_image
                else:
                    roi_defined_g = False; roi_start_point_g = (-1, -1); roi_end_point_g = (-1, -1)
            else: pass
    cv2.destroyWindow(window_name); return input_image

def capture_image_from_camera(camera_index=0, target_width=1280, target_height=720):
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened(): logger.error(f"📸❌ Error: Could not open camera at index {camera_index}."); return None
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, target_width); cap.set(cv2.CAP_PROP_FRAME_HEIGHT, target_height)
    actual_width, actual_height = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    logger.info(f"📷 Camera activated. Res: {actual_width}x{actual_height}. 'S' to Scan, 'Q' to Quit.")
    brightness, contrast, show_grayscale = 0, 0, False
    captured_image_full = None
    help_text_y_start, help_text_dy = 50, 30
    font_feed, font_scale_feed, text_color_feed, bg_color_feed, line_thickness_feed = cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLOR_BRIGHT_GREEN, COLOR_DARK_GRAY_BG, 2
    countdown_font_color, countdown_font_scale, countdown_thickness = COLOR_HOT_PINK, 5, 7
    while True:
        ret, frame = cap.read()
        if not ret: logger.warning("⚠️ Error: Can't receive frame from camera."); break
        display_frame = frame.copy()
        if brightness != 0 or contrast != 0: display_frame = apply_brightness_contrast(display_frame, brightness, contrast)
        doc_contour = find_document_contours(display_frame)
        if doc_contour is not None: cv2.drawContours(display_frame, [doc_contour], -1, COLOR_NEON_CYAN, 3)
        if show_grayscale:
            display_frame_gs = cv2.cvtColor(display_frame, cv2.COLOR_BGR2GRAY)
            display_frame = cv2.cvtColor(display_frame_gs, cv2.COLOR_GRAY2BGR)
        y = help_text_y_start
        put_text_with_bg(display_frame, "'S': Scan | 'Q': Quit", (10, y), font_feed, font_scale_feed, text_color_feed, bg_color_feed, line_thickness_feed); y += help_text_dy
        put_text_with_bg(display_frame, "'G': Grayscale | ROI: 'C'", (10, y), font_feed, font_scale_feed, text_color_feed, bg_color_feed, line_thickness_feed); y += help_text_dy
        put_text_with_bg(display_frame, f"Brightness (W/X): {brightness}", (10, y), font_feed, font_scale_feed, text_color_feed, bg_color_feed, line_thickness_feed); y += help_text_dy
        put_text_with_bg(display_frame, f"Contrast (A/D): {contrast}", (10, y), font_feed, font_scale_feed, text_color_feed, bg_color_feed, line_thickness_feed)
        cv2.imshow('Jarves Scanner - Capture Mode', display_frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == ord('Q'): logger.info("🛑 Capture cancelled by user."); break
        elif key == ord('s') or key == ord('S'):
            for i in range(3, 0, -1):
                countdown_display = display_frame.copy()
                text_size_countdown, _ = cv2.getTextSize(str(i), font_feed, countdown_font_scale, countdown_thickness)
                text_x_countdown = int((actual_width - text_size_countdown[0]) / 2)
                text_y_countdown = int((actual_height + text_size_countdown[1]) / 2)
                cv2.putText(countdown_display, str(i), (text_x_countdown, text_y_countdown), font_feed, countdown_font_scale, countdown_font_color, countdown_thickness, cv2.LINE_AA)
                cv2.imshow('Jarves Scanner - Capture Mode', countdown_display); cv2.waitKey(1000)
            captured_image_full = frame.copy()
            if brightness != 0 or contrast != 0:
                captured_image_full = apply_brightness_contrast(captured_image_full, brightness, contrast)
            logger.info("🎯 Frame captured for ROI selection/confirmation."); break
        elif key == ord('g') or key == ord('G'): show_grayscale = not show_grayscale
        elif key == ord('c') or key == ord('C'):
            logger.info("✂️ ROI selection initiated on current preview.")
            temp_frame_for_roi = display_frame.copy()
            cv2.destroyWindow('Jarves Scanner - Capture Mode')
            roi_selected_frame = interactive_roi_selection(temp_frame_for_roi, "Select ROI on Preview")
            if roi_selected_frame is not None and roi_selected_frame.size != temp_frame_for_roi.size :
                 logger.info("✂️ ROI drawn on preview. Press 'S' to capture and then select ROI on the *captured* image.")
            else:
                logger.info("✂️ ROI selection skipped or no change.")
        elif key == ord('w'): brightness = min(255, brightness + 10)
        elif key == ord('x'): brightness = max(-255, brightness - 10)
        elif key == ord('d'): contrast = min(127, contrast + 10)
        elif key == ord('a'): contrast = max(-127, contrast - 10)
    cap.release(); cv2.destroyAllWindows()
    
    final_image_to_confirm = None
    if captured_image_full is not None:
        logger.info("🖼️ Proceeding to ROI selection on captured image.")
        final_image_to_confirm = interactive_roi_selection(captured_image_full, "Confirm ROI on Captured Image")

    if final_image_to_confirm is not None:
        font_confirm, font_scale_confirm, text_color_confirm, bg_color_confirm, line_thickness_confirm = cv2.FONT_HERSHEY_SIMPLEX, 0.7, COLOR_VIBRANT_YELLOW, COLOR_DARK_GRAY_BG, 2
        while True:
            preview_copy = final_image_to_confirm.copy()
            preview_height, preview_width = preview_copy.shape[:2]
            max_preview_dim = 800; scale_factor = 1.0
            if preview_height > max_preview_dim or preview_width > max_preview_dim:
                if preview_height > preview_width: scale_factor = max_preview_dim / preview_height
                else: scale_factor = max_preview_dim / preview_width
                if scale_factor > 0 : preview_copy = cv2.resize(preview_copy, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_AREA)
            put_text_with_bg(preview_copy, "Use this image? (Y/N) | Retake (R)", (10, 50), font_confirm, font_scale_confirm, text_color_confirm, bg_color_confirm, line_thickness_confirm)
            cv2.imshow("Confirm Final Image", preview_copy)
            key_confirm = cv2.waitKey(0) & 0xFF
            if key_confirm == ord('y') or key_confirm == ord('Y'): cv2.destroyWindow("Confirm Final Image"); return final_image_to_confirm
            elif key_confirm == ord('r') or key_confirm == ord('R'): cv2.destroyWindow("Confirm Final Image"); return capture_image_from_camera(camera_index, target_width, target_height)
            elif key_confirm == ord('n') or key_confirm == ord('N'): cv2.destroyWindow("Confirm Final Image"); return None
    return None

