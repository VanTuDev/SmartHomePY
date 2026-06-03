"""
app.py - Smarthome AI Desktop (Module 1: Cong nhan khuon mat)
Chay: python app.py
"""
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

import cv2
from dotenv import load_dotenv
from PIL import Image, ImageTk

import database as db
import face_engine as fe
import telegram_service as tg
from camera_thread import CameraThread

load_dotenv()

# ── Hang so giao dien ─────────────────────────────────────────────────────────
BG    = "#1a1a2e"
PANEL = "#16213e"
CARD  = "#0f3460"
GREEN = "#00b894"
RED   = "#e74c3c"
BLUE  = "#0984e3"
TEXT  = "#dfe6e9"
MUTED = "#636e72"
WHITE = "#ffffff"

_G = dict(bg=GREEN,      fg=WHITE, activebackground="#00a381", activeforeground=WHITE, relief="flat", cursor="hand2")
_R = dict(bg=RED,        fg=WHITE, activebackground="#c0392b", activeforeground=WHITE, relief="flat", cursor="hand2")
_B = dict(bg=BLUE,       fg=WHITE, activebackground="#0773c5", activeforeground=WHITE, relief="flat", cursor="hand2")
_X = dict(bg="#4a4a6a",  fg=TEXT,  activebackground="#5a5a7a", activeforeground=WHITE, relief="flat", cursor="hand2")

DOOR_OPEN_SEC = 5          # so giay tu dong dong cua
ANNOTATED_SEC = 3          # so giay hien frame co bbox sau khi quet

_pool = ThreadPoolExecutor(max_workers=2)


# ── Tab 1: Camera + Dieu khien cua ───────────────────────────────────────────

class DoorTab(tk.Frame):

    def __init__(self, parent, camera: CameraThread, on_alert, **kw):
        super().__init__(parent, bg=BG, **kw)
        self._cam       = camera
        self._on_alert  = on_alert
        self._scanning  = False
        self._door_open = False
        self._snap_frame: cv2.typing.MatLike = None  # frame co bbox, hien tam thoi
        self._snap_until = 0.0                        # timestamp het hien snap

        self._build()
        self._refresh_display()

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build(self):
        # Cot trai: camera
        left = tk.Frame(self, bg=BG)
        left.pack(side="left", fill="both", expand=True, padx=(10, 4), pady=10)

        self._canvas = tk.Canvas(left, width=640, height=480, bg="#000", highlightthickness=0)
        self._canvas.pack()
        self._canvas_img = self._canvas.create_image(0, 0, anchor="nw")

        self._cam_hint = tk.Label(left, text="Dang khoi dong camera...",
                                   bg=BG, fg=MUTED, font=("Segoe UI", 9))
        self._cam_hint.pack(pady=(4, 0))

        # Cot phai: dieu khien
        right = tk.Frame(self, bg=PANEL, width=290)
        right.pack(side="right", fill="y", padx=(4, 10), pady=10)
        right.pack_propagate(False)

        tk.Label(right, text="TRANG THAI CUA", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(pady=(24, 2))

        self._door_lbl = tk.Label(right, text="CUA DONG",
                                   bg=PANEL, fg=RED, font=("Segoe UI", 22, "bold"))
        self._door_lbl.pack()

        self._action_lbl = tk.Label(right, text="Chua co hoat dong",
                                     bg=PANEL, fg=MUTED, font=("Segoe UI", 9))
        self._action_lbl.pack(pady=(2, 20))

        tk.Frame(right, bg=MUTED, height=1).pack(fill="x", padx=18, pady=(0, 20))

        self._btn = tk.Button(right, text="MO CUA", height=2,
                               font=("Segoe UI", 15, "bold"),
                               command=self._on_click, **_G)
        self._btn.pack(fill="x", padx=18, pady=(0, 8))

        self._bell_btn = tk.Button(right, text="BAM CHUONG", height=2,
                                    font=("Segoe UI", 12, "bold"),
                                    command=self._on_doorbell, **_B)
        self._bell_btn.pack(fill="x", padx=18, pady=(0, 14))

        # Khung ket qua
        res = tk.Frame(right, bg=CARD, pady=14, padx=12)
        res.pack(fill="x", padx=18)
        tk.Label(res, text="KET QUA", bg=CARD, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack()
        self._res_lbl = tk.Label(res, text="Chua quet",
                                  bg=CARD, fg=TEXT, font=("Segoe UI", 11, "bold"),
                                  wraplength=230, justify="center")
        self._res_lbl.pack(pady=(6, 0))

    # ── Display loop (~30 fps) ────────────────────────────────────────────────

    def _refresh_display(self):
        now = time.time()

        # Hien frame co bbox trong ANNOTATED_SEC giay sau khi quet
        if self._snap_frame is not None and now < self._snap_until:
            frame = self._snap_frame
        else:
            self._snap_frame = None
            frame = self._cam.get_frame()

        if frame is not None:
            frame_rgb = cv2.cvtColor(cv2.resize(frame, (640, 480)), cv2.COLOR_BGR2RGB)
            img = ImageTk.PhotoImage(Image.fromarray(frame_rgb))
            self._canvas._photo = img
            self._canvas.itemconfig(self._canvas_img, image=img)
            self._cam_hint.config(text="")

        self.after(33, self._refresh_display)

    # ── Nut MO CUA ────────────────────────────────────────────────────────────

    def _on_click(self):
        if self._scanning:
            return
        frame = self._cam.get_frame()
        if frame is None:
            messagebox.showwarning("Camera", "Camera chua san sang, thu lai sau!")
            return

        self._scanning = True
        self._btn.config(state="disabled", text="Dang quet...")
        self._res_lbl.config(text="Dang quet khuon mat...", fg=MUTED)

        _pool.submit(self._do_scan, frame)

    def _do_scan(self, frame):
        try:
            users               = db.get_users_with_features()
            name, is_known, ann = fe.recognize(frame, users)
            snapshot            = fe.frame_to_b64(ann)

            if is_known:
                db.create_access_log(name, "mo_khoa_khuon_mat", snapshot, True)
                self.after(0, lambda: self._show_result(True, name, ann))
            else:
                db.create_access_log("Nguoi la", "tu_choi_khuon_mat", snapshot, False)
                # Gui Telegram anh khuon mat nguoi la
                tg.alert_stranger(snapshot)
                self.after(0, lambda: self._show_result(False, name, ann))

        except Exception as e:
            print(f"Scan error: {e}")
            self.after(0, self._reset_btn)

    def _show_result(self, is_known: bool, name: str, ann_frame):
        # Hien frame co bbox trong ANNOTATED_SEC giay
        self._snap_frame = ann_frame
        self._snap_until = time.time() + ANNOTATED_SEC

        if is_known:
            self._door_open = True
            self._door_lbl.config(text="CUA MO", fg=GREEN)
            self._action_lbl.config(text=f"Mo khoa: {name}")
            self._res_lbl.config(
                text=f"Xin chao, {name}!\nCua da mo.",
                fg=GREEN)
            self._on_alert(f"Mo cua thanh cong: {name}")
            self.after(DOOR_OPEN_SEC * 1000, self._auto_close)
        else:
            self._door_lbl.config(text="CUA DONG", fg=RED)
            self._action_lbl.config(text="Tu choi: khong nhan dien duoc")
            self._res_lbl.config(
                text=f"{name}\nDa canh bao qua Telegram!",
                fg=RED)
            self._on_alert("Nguoi la bi tu choi - da gui Telegram")

        self._reset_btn()

    def _reset_btn(self):
        self._scanning = False
        self._btn.config(state="normal", text="MO CUA")
        self._bell_btn.config(state="normal", text="BAM CHUONG")

    # ── Nut BAM CHUONG ────────────────────────────────────────────────────────

    def _on_doorbell(self):
        if self._scanning:
            return
        frame = self._cam.get_frame()
        if frame is None:
            messagebox.showwarning("Camera", "Camera chua san sang, thu lai sau!")
            return

        self._scanning = True
        self._btn.config(state="disabled")
        self._bell_btn.config(state="disabled", text="Dang quet...")
        self._res_lbl.config(text="Dang nhan dien nguoi bam chuong...", fg=MUTED)

        _pool.submit(self._do_doorbell, frame)

    def _do_doorbell(self, frame):
        try:
            users               = db.get_users_with_features()
            name, is_known, ann = fe.recognize(frame, users)
            snapshot            = fe.frame_to_b64(ann)

            if is_known:
                db.create_access_log(name, "bam_chuong_nguoi_quen", snapshot, True)
                tg.alert_doorbell_known(name, snapshot)
                self.after(0, lambda: self._show_doorbell_result(True, name, ann))
            else:
                db.create_access_log("Nguoi la", "bam_chuong_nguoi_la", snapshot, False)
                tg.alert_doorbell_stranger(snapshot)
                self.after(0, lambda: self._show_doorbell_result(False, name, ann))

        except Exception as e:
            print(f"Doorbell error: {e}")
            self.after(0, self._reset_btn)

    def _show_doorbell_result(self, is_known: bool, name: str, ann_frame):
        self._snap_frame = ann_frame
        self._snap_until = time.time() + ANNOTATED_SEC

        if is_known:
            self._res_lbl.config(
                text=f"{name} dang o truoc cua!\nDa thong bao Telegram.",
                fg=BLUE)
            self._action_lbl.config(text=f"Chuong: {name}")
            self._on_alert(f"Chuong cua: {name} - da gui Telegram")
        else:
            self._res_lbl.config(
                text="Nguoi la bam chuong!\nDa canh bao Telegram.",
                fg=RED)
            self._action_lbl.config(text="Chuong: Nguoi la")
            self._on_alert("Nguoi la bam chuong - da gui Telegram")

        self._reset_btn()

    def _auto_close(self):
        if self._door_open:
            self._door_open = False
            self._door_lbl.config(text="CUA DONG", fg=RED)
            self._action_lbl.config(text="Cua da tu dong dong")


# ── Tab 2: Quan ly thanh vien ─────────────────────────────────────────────────

class MembersTab(tk.Frame):

    def __init__(self, parent, camera: CameraThread, **kw):
        super().__init__(parent, bg=BG, **kw)
        self._cam            = camera
        self._captured_frame = None
        self._build()

    def _build(self):
        # Form them thanh vien
        form = tk.Frame(self, bg=CARD, padx=18, pady=16)
        form.pack(fill="x", padx=14, pady=(14, 6))

        tk.Label(form, text="THEM THANH VIEN MOI", bg=CARD, fg=TEXT,
                 font=("Segoe UI", 11, "bold")).grid(
                     row=0, column=0, columnspan=3, sticky="w", pady=(0, 14))

        # Ten
        tk.Label(form, text="Ho va Ten:", bg=CARD, fg=MUTED,
                 font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w", pady=5)
        self._name_var = tk.StringVar()
        tk.Entry(form, textvariable=self._name_var, width=26,
                 bg="#243b55", fg=WHITE, insertbackground=WHITE,
                 relief="flat", font=("Segoe UI", 10)).grid(row=1, column=1, padx=10, sticky="ew")

        # Anh khuon mat
        tk.Label(form, text="Anh mat:", bg=CARD, fg=MUTED,
                 font=("Segoe UI", 9)).grid(row=2, column=0, sticky="w", pady=5)

        img_row = tk.Frame(form, bg=CARD)
        img_row.grid(row=2, column=1, padx=10, sticky="w")
        tk.Button(img_row, text="Chup Webcam", font=("Segoe UI", 9),
                  command=self._capture, **_B).pack(side="left", padx=(0, 8))
        tk.Button(img_row, text="Upload Anh", font=("Segoe UI", 9),
                  command=self._upload, **_X).pack(side="left")

        # Nut them + status
        self._add_btn = tk.Button(form, text="THEM THANH VIEN",
                                   font=("Segoe UI", 10, "bold"), height=1,
                                   command=self._add, **_G)
        self._add_btn.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(16, 0))

        self._status_var = tk.StringVar()
        self._status_lbl = tk.Label(form, textvariable=self._status_var,
                                     bg=CARD, fg=MUTED, font=("Segoe UI", 9))
        self._status_lbl.grid(row=4, column=0, columnspan=2, pady=(5, 0))

        form.columnconfigure(1, weight=1)

        # Preview anh lon - Canvas pixel chinh xac
        preview_frame = tk.Frame(self, bg=CARD, padx=8, pady=8)
        preview_frame.pack(fill="x", padx=14, pady=(0, 6))
        tk.Label(preview_frame, text="ANH KHUON MAT DA CHON:", bg=CARD, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 6))
        self._preview_canvas = tk.Canvas(preview_frame, width=320, height=240,
                                          bg="#0a0a1a", highlightthickness=0)
        self._preview_canvas.pack()
        self._preview_text = self._preview_canvas.create_text(
            160, 120, text="Chua co anh\n\nHay chup webcam hoac upload",
            fill=MUTED, font=("Segoe UI", 11), justify="center"
        )
        self._preview_img_item = self._preview_canvas.create_image(0, 0, anchor="nw")

        # Danh sach thanh vien
        lst = tk.Frame(self, bg=CARD, padx=14, pady=12)
        lst.pack(fill="both", expand=True, padx=14, pady=6)

        hdr = tk.Frame(lst, bg=CARD)
        hdr.pack(fill="x", pady=(0, 8))
        tk.Label(hdr, text="DANH SACH THANH VIEN", bg=CARD, fg=TEXT,
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        tk.Button(hdr, text="Tai lai", font=("Segoe UI", 9),
                  command=self.load, **_X).pack(side="right")

        self._tree = ttk.Treeview(lst, columns=("Ten", "Vai tro"), show="headings", height=10)
        for col, w in [("Ten", 240), ("Vai tro", 120)]:
            self._tree.heading(col, text=col)
            self._tree.column(col, width=w, anchor="center")
        self._tree.pack(fill="both", expand=True)
        self._tree.bind("<Double-1>", lambda _: self._delete())

        tk.Label(lst, text="Double-click de xoa thanh vien",
                 bg=CARD, fg=MUTED, font=("Segoe UI", 8)).pack(pady=(4, 0))

        self.load()

    # ── Chon anh ──────────────────────────────────────────────────────────────

    def _set_preview(self, frame_bgr):
        self._captured_frame = frame_bgr
        rgb = cv2.cvtColor(cv2.resize(frame_bgr, (320, 240)), cv2.COLOR_BGR2RGB)
        img = ImageTk.PhotoImage(Image.fromarray(rgb))
        self._preview_canvas._photo = img  # giu reference tranh garbage collect
        self._preview_canvas.itemconfig(self._preview_img_item, image=img)
        self._preview_canvas.itemconfig(self._preview_text, state="hidden")

    def _capture(self):
        frame = self._cam.get_frame()
        if frame is None:
            messagebox.showwarning("Camera", "Camera chua san sang!")
            return
        self._set_preview(frame)
        self._status_var.set("Da chup anh tu webcam")
        self._status_lbl.config(fg=GREEN)

    def _upload(self):
        path = filedialog.askopenfilename(
            title="Chon anh khuon mat",
            filetypes=[("Anh", "*.jpg *.jpeg *.png *.bmp")])
        if not path:
            return
        frame = cv2.imread(path)
        if frame is None:
            messagebox.showerror("Loi", "Khong doc duoc file anh!")
            return
        self._set_preview(frame)
        short = path.replace("\\", "/").split("/")[-1]
        self._status_var.set(f"Da chon: {short}")
        self._status_lbl.config(fg=GREEN)

    # ── Them thanh vien ───────────────────────────────────────────────────────

    def _add(self):
        import face_recognition as fr
        name = self._name_var.get().strip()
        if not name:
            messagebox.showwarning("Thieu thong tin", "Vui long nhap ho va ten!")
            return
        if self._captured_frame is None:
            messagebox.showwarning("Thieu anh", "Vui long chup hoac upload anh khuon mat!")
            return

        self._add_btn.config(state="disabled", text="Dang xu ly...")
        self._status_var.set("Dang trich xuat khuon mat, vui long cho...")
        self._status_lbl.config(fg=MUTED)

        frame = self._captured_frame.copy()

        def worker():
            try:
                rgb  = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                locs = fr.face_locations(rgb, model="hog")
                if not locs:
                    self.after(0, lambda: self._done_add(None,
                        "Khong tim thay khuon mat! Dung anh chup ro mat, nhin thang."))
                    return
                encs = fr.face_encodings(rgb, locs)
                if not encs:
                    self.after(0, lambda: self._done_add(None,
                        "Khong trich xuat duoc dac trung khuon mat!"))
                    return
                db.create_user(name, "nguoi_nha", encs[0].tolist())
                self.after(0, lambda: self._done_add(name, None))
            except Exception as e:
                err = str(e)
                self.after(0, lambda: self._done_add(None, f"Loi: {err}"))

        threading.Thread(target=worker, daemon=True).start()

    def _done_add(self, name, error):
        self._add_btn.config(state="normal", text="THEM THANH VIEN")
        if error:
            self._status_var.set(error)
            self._status_lbl.config(fg=RED)
        else:
            self._status_var.set(f"Da them thanh vien: {name}")
            self._status_lbl.config(fg=GREEN)
            self._name_var.set("")
            self._captured_frame = None
            self._preview.config(image="", text="Chua co\nanh")
            self.load()

    # ── Danh sach ─────────────────────────────────────────────────────────────

    def load(self):
        for r in self._tree.get_children():
            self._tree.delete(r)
        try:
            for u in db.get_all_users():
                role = "Nguoi nha" if u.get("role") == "nguoi_nha" else "Khach"
                self._tree.insert("", "end", iid=u["_id"], values=(u["name"], role))
        except Exception as e:
            print(f"Load members error: {e}")

    def _delete(self):
        sel = self._tree.selection()
        if not sel:
            return
        uid  = sel[0]
        name = self._tree.item(uid)["values"][0]
        if not messagebox.askyesno("Xac nhan", f'Xoa thanh vien "{name}"?'):
            return
        try:
            db.delete_user(uid)
            self._tree.delete(uid)
        except Exception as e:
            messagebox.showerror("Loi", str(e))


# ── Tab 3: Phat hien te nga ──────────────────────────────────────────────────

class FallTab(tk.Frame):
    """
    Tab giam sat phat hien te nga bang YOLOv8 Pose.
    Detection thread chay ~6fps (YOLO nang).
    Display loop chay 30fps luon muot.
    """

    COOLDOWN_SEC = 30  # giay giua 2 lan canh bao

    def __init__(self, parent, camera: CameraThread, on_alert, **kw):
        super().__init__(parent, bg=BG, **kw)
        self._cam      = camera
        self._on_alert = on_alert
        self._running  = True
        self._lock     = threading.Lock()

        # Shared state (detection thread -> display loop)
        self._annotated: cv2.typing.MatLike = None
        self._is_falling = False
        self._fall_secs  = 0.0

        self._build()
        self._start_detection_thread()
        self._refresh_display()

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build(self):
        # Cot trai: camera canvas
        left = tk.Frame(self, bg=BG)
        left.pack(side="left", fill="both", expand=True, padx=(10, 4), pady=10)

        self._canvas = tk.Canvas(left, width=640, height=480, bg="#000", highlightthickness=0)
        self._canvas.pack()
        self._canvas_img = self._canvas.create_image(0, 0, anchor="nw")

        self._cam_hint = tk.Label(left, text="Dang khoi dong YOLO...",
                                   bg=BG, fg=MUTED, font=("Segoe UI", 9))
        self._cam_hint.pack(pady=(4, 0))

        # Cot phai: trang thai
        right = tk.Frame(self, bg=PANEL, width=290)
        right.pack(side="right", fill="y", padx=(4, 10), pady=10)
        right.pack_propagate(False)

        tk.Label(right, text="TRANG THAI", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9, "bold")).pack(pady=(24, 4))

        self._status_lbl = tk.Label(right, text="BINH THUONG",
                                     bg=PANEL, fg=GREEN, font=("Segoe UI", 18, "bold"))
        self._status_lbl.pack()

        self._timer_lbl = tk.Label(right, text="",
                                    bg=PANEL, fg=MUTED, font=("Segoe UI", 13))
        self._timer_lbl.pack(pady=(6, 0))

        tk.Frame(right, bg=MUTED, height=1).pack(fill="x", padx=18, pady=20)

        threshold = int(os.getenv("FALL_DETECTION_SECONDS", "5"))
        tk.Label(right, text="CAU HINH", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(pady=(0, 6))
        tk.Label(right, text=f"Nguong canh bao: {threshold}s",
                 bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).pack()
        tk.Label(right, text=f"Cooldown: {self.COOLDOWN_SEC}s",
                 bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).pack(pady=(2, 0))

        tk.Frame(right, bg=MUTED, height=1).pack(fill="x", padx=18, pady=20)

        tk.Label(right, text="CANH BAO CUOI", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack()
        self._last_alert_lbl = tk.Label(right, text="Chua co canh bao",
                                         bg=PANEL, fg=MUTED, font=("Segoe UI", 9),
                                         wraplength=230, justify="center")
        self._last_alert_lbl.pack(pady=(6, 0))

    # ── Detection thread ──────────────────────────────────────────────────────

    def _start_detection_thread(self):
        t = threading.Thread(target=self._detection_loop, daemon=True, name="FallDetect")
        t.start()

    def _detection_loop(self):
        from fall_detector import FallDetector
        detector   = FallDetector()
        threshold  = int(os.getenv("FALL_DETECTION_SECONDS", "5"))
        fall_start = None
        last_alert = 0.0
        alerted    = False

        self.after(0, lambda: self._cam_hint.config(text=""))

        while self._running:
            frame = self._cam.get_frame()
            if frame is None:
                time.sleep(0.1)
                continue

            frame = cv2.resize(frame, (640, 480))
            annotated, is_falling = detector.detect(frame)

            now = time.time()

            # Tinh thoi gian te nga lien tuc
            if is_falling:
                if fall_start is None:
                    fall_start = now
                    alerted    = False
                fall_secs = now - fall_start
            else:
                fall_start = None
                alerted    = False
                fall_secs  = 0.0

            # Kiem tra co nen canh bao khong
            should_alert = (
                is_falling
                and fall_secs >= threshold
                and not alerted
                and now - last_alert > self.COOLDOWN_SEC
            )

            if should_alert:
                alerted    = True
                last_alert = now
                snapshot   = fe.frame_to_b64(annotated)
                ts         = datetime.now().strftime("%H:%M:%S %d/%m/%Y")
                # Gui vao main thread de update UI va chay Telegram/DB
                self.after(0, lambda s=snapshot, t=ts: self._do_alert(s, t))

            # Cap nhat shared state
            with self._lock:
                self._annotated  = annotated
                self._is_falling = is_falling
                self._fall_secs  = fall_secs

            time.sleep(0.15)  # ~6fps YOLO

    def _do_alert(self, snapshot: str, ts: str):
        """Goi tu main thread: update UI + chay Telegram+DB o background."""
        self._last_alert_lbl.config(text=f"Da canh bao luc\n{ts}", fg=RED)
        self._on_alert(f"PHAT HIEN TE NGA! - {ts}")
        _pool.submit(self._send_alert_bg, snapshot, ts)

    def _send_alert_bg(self, snapshot: str, ts: str):
        """Chay o thread pool: gui Telegram + luu DB."""
        tg.alert_fall(snapshot, ts)
        try:
            db.create_fall_log(snapshot, ts)
        except Exception as e:
            print(f"Luu fall log loi: {e}")

    # ── Display loop (30fps) ──────────────────────────────────────────────────

    def _refresh_display(self):
        with self._lock:
            annotated  = self._annotated
            is_falling = self._is_falling
            fall_secs  = self._fall_secs

        if annotated is not None:
            display = annotated.copy()

            # Overlay trang thai
            if is_falling:
                label = f"PHAT HIEN TE NGA! ({fall_secs:.1f}s)"
                color = (0, 0, 220)
                cv2.rectangle(display, (0, 0), (640, 50), (0, 0, 180), -1)
            else:
                label = "BINH THUONG"
                color = (0, 200, 0)

            cv2.putText(display, label, (10, 36),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255) if is_falling else color, 2)
            cv2.putText(display, datetime.now().strftime("%H:%M:%S %d/%m/%Y"),
                        (10, 468), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)

            rgb = cv2.cvtColor(cv2.resize(display, (640, 480)), cv2.COLOR_BGR2RGB)
            img = ImageTk.PhotoImage(Image.fromarray(rgb))
            self._canvas._photo = img
            self._canvas.itemconfig(self._canvas_img, image=img)

            # Cap nhat panel trang thai
            if is_falling:
                self._status_lbl.config(text="PHAT HIEN TE NGA!", fg=RED)
                self._timer_lbl.config(text=f"Da nga: {fall_secs:.1f}s", fg=RED)
            else:
                self._status_lbl.config(text="BINH THUONG", fg=GREEN)
                self._timer_lbl.config(text="")

        self.after(33, self._refresh_display)

    def stop(self):
        self._running = False


# ── Tab 4: Nhat ky ────────────────────────────────────────────────────────────

class LogsTab(tk.Frame):
    """Tab nhat ky: chia doi - ben trai ra vao cua, ben phai te nga."""

    _ACTION_MAP = {
        "mo_khoa_khuon_mat":     "Mo khoa khuon mat",
        "tu_choi_khuon_mat":     "Tu choi - nguoi la",
        "bam_chuong_nguoi_quen": "Chuong - nguoi quen",
        "bam_chuong_nguoi_la":   "Chuong - nguoi la",
    }

    def __init__(self, parent, **kw):
        super().__init__(parent, bg=BG, **kw)
        self._build()

    def _build(self):
        paned = tk.PanedWindow(self, orient="horizontal", bg=BG,
                               sashwidth=6, sashrelief="flat")
        paned.pack(fill="both", expand=True, padx=10, pady=10)

        # ── Ben trai: Nhat ky ra vao ──
        left = tk.Frame(paned, bg=CARD, padx=12, pady=10)
        paned.add(left, stretch="always")

        hdr_l = tk.Frame(left, bg=CARD)
        hdr_l.pack(fill="x", pady=(0, 8))
        tk.Label(hdr_l, text="NHAT KY RA VAO CUA", bg=CARD, fg=TEXT,
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        tk.Button(hdr_l, text="Tai lai", font=("Segoe UI", 9),
                  command=self._load_access, **_X).pack(side="right")

        cols_a = ("Thoi gian", "Nguoi", "Hanh dong", "KQ")
        widths_a = (130, 120, 180, 70)
        self._access_tree = ttk.Treeview(left, columns=cols_a, show="headings")
        for c, w in zip(cols_a, widths_a):
            self._access_tree.heading(c, text=c)
            self._access_tree.column(c, width=w, anchor="center")
        sb1 = ttk.Scrollbar(left, orient="vertical", command=self._access_tree.yview)
        self._access_tree.configure(yscrollcommand=sb1.set)
        self._access_tree.pack(side="left", fill="both", expand=True)
        sb1.pack(side="right", fill="y")

        # ── Ben phai: Nhat ky te nga ──
        right = tk.Frame(paned, bg=CARD, padx=12, pady=10)
        paned.add(right, stretch="always")

        hdr_r = tk.Frame(right, bg=CARD)
        hdr_r.pack(fill="x", pady=(0, 8))
        tk.Label(hdr_r, text="NHAT KY TE NGA", bg=CARD, fg=RED,
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        tk.Button(hdr_r, text="Tai lai", font=("Segoe UI", 9),
                  command=self._load_fall, **_X).pack(side="right")

        cols_f = ("Thoi gian", "Trang thai")
        self._fall_tree = ttk.Treeview(right, columns=cols_f, show="headings")
        for c, w in zip(cols_f, (160, 140)):
            self._fall_tree.heading(c, text=c)
            self._fall_tree.column(c, width=w, anchor="center")
        sb2 = ttk.Scrollbar(right, orient="vertical", command=self._fall_tree.yview)
        self._fall_tree.configure(yscrollcommand=sb2.set)
        self._fall_tree.pack(side="left", fill="both", expand=True)
        sb2.pack(side="right", fill="y")

        self._load_access()
        self._load_fall()

    def _fmt(self, iso: str) -> str:
        try:
            return datetime.fromisoformat(iso).strftime("%H:%M:%S %d/%m/%y")
        except Exception:
            return str(iso)[:19]

    def _load_access(self):
        for r in self._access_tree.get_children():
            self._access_tree.delete(r)
        try:
            for lg in db.get_access_logs(50):
                action = self._ACTION_MAP.get(lg.get("action", ""), lg.get("action", ""))
                kq     = "OK" if lg.get("is_allowed") else "TU CHOI"
                self._access_tree.insert("", "end", values=(
                    self._fmt(lg.get("timestamp", "")),
                    lg.get("person_name", ""), action, kq))
        except Exception as e:
            print(f"Load access logs error: {e}")

    def _load_fall(self):
        for r in self._fall_tree.get_children():
            self._fall_tree.delete(r)
        try:
            for lg in db.get_fall_logs(50):
                self._fall_tree.insert("", "end", values=(
                    self._fmt(lg.get("timestamp", "")),
                    lg.get("status", "")))
        except Exception as e:
            print(f"Load fall logs error: {e}")

    def load(self):
        self._load_access()
        self._load_fall()


# ── Main App ──────────────────────────────────────────────────────────────────

class SmarthomeApp:

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Smarthome AI")
        self.root.geometry("1060x640")
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        door_src = os.getenv("DOOR_SOURCE", "0")
        door_src = int(door_src) if door_src.isdigit() else door_src
        self._cam = CameraThread(door_src)

        lr_src = os.getenv("LIVING_ROOM_SOURCE", "0")
        lr_src = int(lr_src) if lr_src.isdigit() else lr_src
        # Neu cung source thi dung chung camera thread, tranh xung dot Windows
        self._fall_cam = self._cam if lr_src == door_src else CameraThread(lr_src)

        self._apply_style()
        self._build()
        self._connect_db()

    def _apply_style(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("TNotebook",      background=BG,    borderwidth=0)
        s.configure("TNotebook.Tab",  background=PANEL, foreground=MUTED,
                    padding=[16, 8],  font=("Segoe UI", 10))
        s.map("TNotebook.Tab",
              background=[("selected", CARD)],
              foreground=[("selected", TEXT)])
        s.configure("Treeview",
                    background=PANEL, foreground=TEXT, fieldbackground=PANEL,
                    rowheight=26,     font=("Segoe UI", 9))
        s.configure("Treeview.Heading", background=CARD, foreground=TEXT,
                    font=("Segoe UI", 9, "bold"))
        s.map("Treeview", background=[("selected", BLUE)])
        s.configure("Vertical.TScrollbar",
                    background=CARD, troughcolor=PANEL, arrowcolor=TEXT)

    def _build(self):
        # Header
        hdr = tk.Frame(self.root, bg=PANEL, height=50)
        hdr.pack(fill="x")
        tk.Label(hdr, text="SMARTHOME AI", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 14, "bold")).pack(side="left", padx=18, pady=10)
        self._banner = tk.StringVar(value="He thong san sang.")
        tk.Label(hdr, textvariable=self._banner, bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 9)).pack(side="right", padx=18)

        # Tabs
        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True)

        self._door_tab = DoorTab(nb, self._cam, on_alert=self._push)
        nb.add(self._door_tab, text="  NHAN DIEN KHUON MAT  ")

        self._fall_tab = FallTab(nb, self._fall_cam, on_alert=self._push)
        nb.add(self._fall_tab, text="  PHAT HIEN TE NGA  ")

        self._members_tab = MembersTab(nb, self._cam)
        nb.add(self._members_tab, text="  THANH VIEN  ")

        self._logs_tab = LogsTab(nb)
        nb.add(self._logs_tab, text="  NHAT KY  ")

    def _connect_db(self):
        try:
            db.connect()
            self._push("Ket noi MongoDB thanh cong.")
            self._members_tab.load()
            self._logs_tab.load()
        except Exception as e:
            messagebox.showerror(
                "Loi ket noi MongoDB",
                f"Khong ket noi duoc MongoDB Atlas!\n\n"
                f"Vui long:\n"
                f"1. Vao cloud.mongodb.com\n"
                f"2. Network Access -> Add IP -> Allow from Anywhere\n"
                f"3. Khoi dong lai ung dung\n\n"
                f"Chi tiet loi:\n{e}"
            )

    def _push(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self._banner.set(f"[{ts}]  {msg}")

    def _on_close(self):
        self._fall_tab.stop()
        self._cam.stop()
        if self._fall_cam is not self._cam:
            self._fall_cam.stop()
        db.close()
        self.root.destroy()

    def run(self):
        self._cam.start()
        if self._fall_cam is not self._cam:
            self._fall_cam.start()
        self.root.mainloop()


if __name__ == "__main__":
    SmarthomeApp().run()
