"""
camera_thread.py - Doc frame webcam lien tuc trong thread rieng, khong lag
"""
import threading
from typing import Optional

import cv2
import numpy as np


class CameraThread:
    """
    Doc frame tu webcam lien tuc o background thread.
    Display chi lay frame moi nhat -> khong bao gio hien frame cu trong buffer.
    """

    def __init__(self, source):
        self._source = source
        self._cap: Optional[cv2.VideoCapture] = None
        self._frame: Optional[np.ndarray] = None
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        backend = cv2.CAP_DSHOW if isinstance(self._source, int) else cv2.CAP_ANY
        self._cap = cv2.VideoCapture(self._source, backend)
        if not self._cap.isOpened():
            raise RuntimeError(f"Khong mo duoc camera: {self._source}")

        # Buffer size = 1: luon doc frame moi nhat, khong giu frame cu
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="CameraThread")
        self._thread.start()
        print("Camera thread da khoi dong.")

    def _loop(self):
        while self._running:
            ret, frame = self._cap.read()
            if ret:
                with self._lock:
                    self._frame = frame
            # Khong sleep: doc nhanh nhat co the de xoa buffer lien tuc

    def get_frame(self) -> Optional[np.ndarray]:
        """Tra ve ban sao cua frame moi nhat. None neu chua co frame."""
        with self._lock:
            return self._frame.copy() if self._frame is not None else None

    def stop(self):
        self._running = False
        if self._cap:
            self._cap.release()
        print("Camera da dong.")
