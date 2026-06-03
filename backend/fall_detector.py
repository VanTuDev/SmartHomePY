"""
fall_detector.py - Phat hien te nga bang YOLOv8n-pose
"""
import cv2
import numpy as np
from ultralytics import YOLO


class FallDetector:
    """
    Phat hien te nga qua phan tich keypoints YOLO Pose.
    Logic: neu vector vai->hong nghieng ngang (dx > dy * 1.2) -> te nga.
    Chay YOLO o input 320x320 de tang toc, tra ve frame goc da co annotation.
    """

    def __init__(self, model_path: str = "yolov8n-pose.pt"):
        print("Dang tai mo hinh YOLO Pose...")
        self.model = YOLO(model_path)
        print("Mo hinh YOLO Pose da san sang.")

    def detect(self, frame: np.ndarray) -> tuple:
        """
        Chay YOLO Pose tren frame.
        Returns: (annotated_frame, is_falling)
        """
        h, w = frame.shape[:2]
        small   = cv2.resize(frame, (320, 320))
        results = self.model(small, imgsz=320, verbose=False)
        annotated = cv2.resize(results[0].plot(), (w, h))

        is_falling = False
        for result in results:
            if result.keypoints is None:
                continue
            for kp_data in result.keypoints.data:
                if _is_fallen(kp_data.cpu().numpy()):
                    is_falling = True
                    break
            if is_falling:
                break

        return annotated, is_falling


def _is_fallen(kp: np.ndarray) -> bool:
    """
    Phan tich keypoints de xac dinh nguoi co dang nam ngang hay khong.
    Dung vai (5,6) va hong (11,12) de tinh goc than nguoi.
    """
    if kp is None or len(kp) < 13:
        return False

    shoulders = kp[[5, 6], :2]
    hips      = kp[[11, 12], :2]
    valid_s   = shoulders[kp[[5, 6], 2] > 0.3]
    valid_h   = hips[kp[[11, 12], 2] > 0.3]

    if len(valid_s) == 0 or len(valid_h) == 0:
        return False

    dy = abs(valid_s[:, 1].mean() - valid_h[:, 1].mean())
    dx = abs(valid_s[:, 0].mean() - valid_h[:, 0].mean())

    # Than nguoi nam ngang: chieu ngang lon hon chieu doc
    return dx > dy * 1.2
