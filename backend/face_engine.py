"""
face_engine.py - Nhan dien khuon mat va trich xuat encoding
"""
import base64
import os
from typing import Optional

import cv2
import face_recognition
import numpy as np

THRESHOLD = float(os.getenv("FACE_RECOGNITION_THRESHOLD", "0.5"))


def frame_to_b64(frame: np.ndarray) -> str:
    """Chuyen frame OpenCV sang Base64 JPEG."""
    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.b64encode(buf).decode()


def encode_face(frame: np.ndarray) -> Optional[np.ndarray]:
    """
    Trich xuat face encoding tu frame.
    Tra ve encoding (128 chieu) hoac None neu khong tim thay mat.
    """
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    locs = face_recognition.face_locations(rgb, model="hog")
    if not locs:
        return None
    encs = face_recognition.face_encodings(rgb, locs)
    return encs[0] if encs else None


def recognize(frame: np.ndarray, known_users: list) -> tuple:
    """
    So khop tat ca khuon mat trong frame voi danh sach users tu DB.

    Returns:
        (person_name, is_known, annotated_frame)
        - person_name: ten nguoi khop tot nhat (hoac "Nguoi la" / "Khong tim thay mat")
        - is_known: True neu khop voi user da dang ky
        - annotated_frame: frame da ve bounding box + ten
    """
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    locs = face_recognition.face_locations(rgb, model="hog")
    annotated = frame.copy()

    if not locs:
        cv2.putText(annotated, "Khong tim thay khuon mat",
                    (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 100, 255), 2)
        return "Khong tim thay khuon mat", False, annotated

    encs = face_recognition.face_encodings(rgb, locs)

    known_encs  = [np.array(u["face_features"]) for u in known_users if u.get("face_features")]
    known_names = [u["name"]                    for u in known_users if u.get("face_features")]

    best_name = "Nguoi la"
    is_known  = False

    for enc, (top, right, bottom, left) in zip(encs, locs):
        name  = "Nguoi la"
        known = False

        if known_encs:
            dists   = face_recognition.face_distance(known_encs, enc)
            best_i  = int(np.argmin(dists))
            if dists[best_i] < THRESHOLD:
                name      = known_names[best_i]
                known     = True
                is_known  = True
                best_name = name

        # Ve bounding box
        color = (0, 210, 0) if known else (0, 0, 220)
        cv2.rectangle(annotated, (left, top), (right, bottom), color, 2)

        # Ve label co nen
        label     = name
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.65, 2)
        label_y   = max(top - 6, th + 4)
        cv2.rectangle(annotated, (left, label_y - th - 4), (left + tw + 6, label_y + 2), color, -1)
        cv2.putText(annotated, label, (left + 3, label_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)

    return best_name, is_known, annotated
