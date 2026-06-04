import os
import cv2
import time
import json
import hashlib
import serial
import numpy as np
import requests
import smtplib
import threading
from email.message import EmailMessage
from datetime import datetime
from flask import Flask, Response, jsonify, render_template, request

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except Exception:
    YOLO_AVAILABLE = False


# ==================================================
# CONFIG
# ==================================================

CAMERA_SOURCE = int(os.getenv("CAMERA_SOURCE", "0"))

ARDUINO_PORT = os.getenv("ARDUINO_PORT", "COM3")
BAUD_RATE = int(os.getenv("BAUD_RATE", "9600"))

MODE = os.getenv("MODE", "agriculture")
# MODE = "smart_city"

FRAME_WIDTH = int(os.getenv("FRAME_WIDTH", "960"))
FRAME_HEIGHT = int(os.getenv("FRAME_HEIGHT", "540"))

YOLO_MODEL_PATH = os.getenv("YOLO_MODEL_PATH", "fire_smoke.pt")
CONF_THRESHOLD = float(os.getenv("CONF_THRESHOLD", "0.45"))

SEND_INTERVAL = float(os.getenv("SEND_INTERVAL", "0.35"))
ALERT_INTERVAL = float(os.getenv("ALERT_INTERVAL", "10"))

CLOSE_FIRE_AREA_AGRICULTURE = int(os.getenv("CLOSE_FIRE_AREA_AGRICULTURE", "35000"))
CLOSE_FIRE_AREA_CITY = int(os.getenv("CLOSE_FIRE_AREA_CITY", "45000"))

ALERT_FOLDER = os.getenv("ALERT_FOLDER", "alerts")
BLOCKCHAIN_FILE = os.getenv("BLOCKCHAIN_FILE", "blockchain_log.json")
ALERT_HISTORY_FILE = os.getenv("ALERT_HISTORY_FILE", "fire_alert_history.txt")

ENABLE_TELEGRAM = os.getenv("ENABLE_TELEGRAM", "false").lower() == "true"
ENABLE_EMAIL = os.getenv("ENABLE_EMAIL", "false").lower() == "true"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

EMAIL_SENDER = os.getenv("EMAIL_SENDER", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER", "")

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))


# ==================================================
# FLASK APP + SYSTEM STATE
# ==================================================

app = Flask(__name__)

state_lock = threading.Lock()

system_state = {
    "mode": MODE,
    "manual_mode": False,
    "command": "STOP",
    "danger_level": "NORMAL",
    "message": "System starting...",
    "control_mode": "AUTO",
    "detections": [],
    "camera_ok": False,
    "arduino_ok": False,
    "blockchain_valid": False,
    "last_update": None,
    "alert_count": 0,
    "model": "HSV fallback",
}


def set_state(**kwargs):
    with state_lock:
        system_state.update(kwargs)
        system_state["last_update"] = str(datetime.now())


def get_state():
    with state_lock:
        return dict(system_state)


def get_current_mode():
    with state_lock:
        return system_state["mode"]


# ==================================================
# BLOCKCHAIN
# ==================================================

class Block:
    def __init__(self, index, timestamp, data, previous_hash, nonce=0):
        self.index = index
        self.timestamp = timestamp
        self.data = data
        self.previous_hash = previous_hash
        self.nonce = nonce
        self.hash = self.calculate_hash()

    def calculate_hash(self):
        block_content = {
            "index": self.index,
            "timestamp": self.timestamp,
            "data": self.data,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce
        }

        block_string = json.dumps(block_content, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(block_string.encode("utf-8")).hexdigest()

    def mine_block(self, difficulty=3):
        target = "0" * difficulty

        while self.hash[:difficulty] != target:
            self.nonce += 1
            self.hash = self.calculate_hash()

    def to_dict(self):
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "data": self.data,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
            "hash": self.hash
        }


class FireBlockchain:
    def __init__(self, file_path):
        self.file_path = file_path
        self.lock = threading.Lock()

        if os.path.exists(file_path):
            self.chain = self.load_chain()
        else:
            self.chain = [self.create_genesis_block()]
            self.save_chain()

    def create_genesis_block(self):
        return Block(
            index=0,
            timestamp=str(datetime.now()),
            data={
                "system": "Alphabot Firefighting Blockchain",
                "message": "Genesis Block"
            },
            previous_hash="0"
        )

    def get_latest_block(self):
        return self.chain[-1]

    def add_alert(self, alert_data):
        with self.lock:
            latest_block = self.get_latest_block()

            new_block = Block(
                index=len(self.chain),
                timestamp=str(datetime.now()),
                data=alert_data,
                previous_hash=latest_block.hash
            )

            new_block.mine_block(difficulty=3)
            self.chain.append(new_block)
            self.save_chain()

            print("[BLOCKCHAIN] Alert saved. Block hash:", new_block.hash)
            return new_block

    def save_chain(self):
        data = [block.to_dict() for block in self.chain]

        with open(self.file_path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4, ensure_ascii=False)

    def load_chain(self):
        with open(self.file_path, "r", encoding="utf-8") as file:
            raw_chain = json.load(file)

        chain = []

        for item in raw_chain:
            block = Block(
                index=item["index"],
                timestamp=item["timestamp"],
                data=item["data"],
                previous_hash=item["previous_hash"],
                nonce=item["nonce"]
            )

            block.hash = item["hash"]
            chain.append(block)

        return chain

    def validate_chain(self):
        with self.lock:
            for i in range(1, len(self.chain)):
                current = self.chain[i]
                previous = self.chain[i - 1]

                if current.hash != current.calculate_hash():
                    return False

                if current.previous_hash != previous.hash:
                    return False

            return True

    def to_list(self):
        with self.lock:
            return [block.to_dict() for block in self.chain]


# ==================================================
# ALPHABOT CONTROLLER
# ==================================================

class AlphabotController:
    def __init__(self, port, baud_rate):
        self.serial = None
        self.last_command = ""
        self.last_send_time = 0

        try:
            self.serial = serial.Serial(port, baud_rate, timeout=1)
            time.sleep(2)
            print("[OK] Connected to Alphabot Arduino:", port)
            set_state(arduino_ok=True)
        except Exception as e:
            print("[SIMULATION] Arduino not connected.")
            print("[INFO] Robot commands will be printed only.")
            print(e)
            set_state(arduino_ok=False)

    def send_command(self, command):
        now = time.time()

        if now - self.last_send_time < SEND_INTERVAL:
            return

        if command != self.last_command:
            if self.serial is not None:
                self.serial.write((command + "\n").encode("utf-8"))

            print("[ALPHABOT COMMAND]", command)

            self.last_command = command
            self.last_send_time = now

    def close(self):
        self.send_command("STOP")
        time.sleep(0.2)

        if self.serial is not None:
            self.serial.close()


# ==================================================
# NOTIFICATION MANAGER
# ==================================================

class NotificationManager:
    def send_telegram(self, message, image_path=None):
        if not ENABLE_TELEGRAM:
            return

        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            print("[TELEGRAM] Missing bot token or chat id.")
            return

        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

            data = {
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message
            }

            requests.post(url, data=data, timeout=10)

            if image_path and os.path.exists(image_path):
                photo_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"

                with open(image_path, "rb") as photo:
                    files = {"photo": photo}
                    photo_data = {
                        "chat_id": TELEGRAM_CHAT_ID,
                        "caption": "Ảnh cảnh báo cháy từ Alphabot"
                    }

                    requests.post(photo_url, data=photo_data, files=files, timeout=10)

            print("[TELEGRAM] Alert sent.")

        except Exception as e:
            print("[TELEGRAM ERROR]", e)

    def send_email(self, subject, body, image_path=None):
        if not ENABLE_EMAIL:
            return

        if not EMAIL_SENDER or not EMAIL_PASSWORD or not EMAIL_RECEIVER:
            print("[EMAIL] Missing SMTP credentials.")
            return

        try:
            msg = EmailMessage()
            msg["From"] = EMAIL_SENDER
            msg["To"] = EMAIL_RECEIVER
            msg["Subject"] = subject
            msg.set_content(body)

            if image_path and os.path.exists(image_path):
                with open(image_path, "rb") as file:
                    image_data = file.read()

                msg.add_attachment(
                    image_data,
                    maintype="image",
                    subtype="jpeg",
                    filename=os.path.basename(image_path)
                )

            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as smtp:
                smtp.starttls()
                smtp.login(EMAIL_SENDER, EMAIL_PASSWORD)
                smtp.send_message(msg)

            print("[EMAIL] Alert sent.")

        except Exception as e:
            print("[EMAIL ERROR]", e)


# ==================================================
# FIRE DETECTOR
# ==================================================

class FireDetector:
    def __init__(self, mode):
        self.mode = mode
        self.model = None
        self.use_custom_yolo = False

        self.fire_confirm_count = 0
        self.smoke_confirm_count = 0
        self.confirm_threshold = 5

        self.update_mode(mode)

        if YOLO_AVAILABLE and os.path.exists(YOLO_MODEL_PATH):
            try:
                self.model = YOLO(YOLO_MODEL_PATH)
                self.use_custom_yolo = True
                print("[OK] Using custom fire/smoke YOLO model:", YOLO_MODEL_PATH)
                set_state(model=f"YOLO custom: {YOLO_MODEL_PATH}")
            except Exception as e:
                print("[WARNING] Invalid fire_smoke.pt. Switching to HSV fallback.")
                print(e)
                self.model = None
                self.use_custom_yolo = False
                set_state(model="HSV fallback")
        else:
            print("[INFO] YOLO custom model not available. Using HSV fallback.")
            set_state(model="HSV fallback")

    def update_mode(self, mode):
        self.mode = mode

        if mode == "agriculture":
            self.title = "ALPHABOT FIRE ROBOT - SMART AGRICULTURE"
            self.close_fire_area = CLOSE_FIRE_AREA_AGRICULTURE
            self.location = "Farm / Greenhouse / Storage Area"
        else:
            self.title = "ALPHABOT FIRE ROBOT - SMART CITY"
            self.close_fire_area = CLOSE_FIRE_AREA_CITY
            self.location = "Parking / Factory / Urban Camera Zone"

    def detect(self, frame):
        if self.use_custom_yolo:
            return self.detect_by_yolo(frame)

        return self.detect_by_hsv(frame)

    def detect_by_yolo(self, frame):
        results = self.model.predict(
            source=frame,
            conf=CONF_THRESHOLD,
            imgsz=640,
            verbose=False
        )

        detections = []
        result = results[0]
        names = result.names

        if result.boxes is None:
            return detections

        for box in result.boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            class_name = names[cls_id].lower()

            if class_name not in ["fire", "smoke"]:
                continue

            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
            x1 = int(x1)
            y1 = int(y1)
            x2 = int(x2)
            y2 = int(y2)

            w = x2 - x1
            h = y2 - y1
            area = w * h

            detections.append({
                "class_name": class_name,
                "confidence": conf,
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
                "w": w,
                "h": h,
                "cx": x1 + w // 2,
                "cy": y1 + h // 2,
                "area": area,
                "method": "YOLO"
            })

        return detections

    def detect_by_hsv(self, frame):
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        height, width = frame.shape[:2]

        roi_mask = np.zeros((height, width), dtype=np.uint8)
        roi_mask[int(height * 0.35):height, :] = 255

        lower_fire_1 = np.array([0, 120, 160])
        upper_fire_1 = np.array([30, 255, 255])

        lower_fire_2 = np.array([170, 120, 160])
        upper_fire_2 = np.array([179, 255, 255])

        fire_mask_1 = cv2.inRange(hsv, lower_fire_1, upper_fire_1)
        fire_mask_2 = cv2.inRange(hsv, lower_fire_2, upper_fire_2)
        fire_mask = cv2.bitwise_or(fire_mask_1, fire_mask_2)
        fire_mask = cv2.bitwise_and(fire_mask, roi_mask)

        lower_smoke = np.array([0, 0, 100])
        upper_smoke = np.array([180, 55, 235])

        smoke_mask = cv2.inRange(hsv, lower_smoke, upper_smoke)
        smoke_mask = cv2.bitwise_and(smoke_mask, roi_mask)

        kernel_fire = np.ones((5, 5), np.uint8)
        kernel_smoke = np.ones((9, 9), np.uint8)

        fire_mask = cv2.morphologyEx(fire_mask, cv2.MORPH_OPEN, kernel_fire)
        fire_mask = cv2.morphologyEx(fire_mask, cv2.MORPH_CLOSE, kernel_fire)
        fire_mask = cv2.dilate(fire_mask, kernel_fire, iterations=2)

        smoke_mask = cv2.morphologyEx(smoke_mask, cv2.MORPH_OPEN, kernel_smoke)
        smoke_mask = cv2.morphologyEx(smoke_mask, cv2.MORPH_CLOSE, kernel_smoke)
        smoke_mask = cv2.dilate(smoke_mask, kernel_smoke, iterations=2)

        detections = []

        fire_contours, _ = cv2.findContours(
            fire_mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        for contour in fire_contours:
            area = cv2.contourArea(contour)

            if area < 3000:
                continue

            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = w / float(h + 1)

            if aspect_ratio < 0.25 or aspect_ratio > 3.5:
                continue

            detections.append({
                "class_name": "fire",
                "confidence": 0.75,
                "x1": x,
                "y1": y,
                "x2": x + w,
                "y2": y + h,
                "w": w,
                "h": h,
                "cx": x + w // 2,
                "cy": y + h // 2,
                "area": area,
                "method": "HSV+ROI"
            })

        smoke_contours, _ = cv2.findContours(
            smoke_mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        for contour in smoke_contours:
            area = cv2.contourArea(contour)

            if area < 5000:
                continue

            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = w / float(h + 1)

            if aspect_ratio < 0.4 or aspect_ratio > 5.0:
                continue

            detections.append({
                "class_name": "smoke",
                "confidence": 0.60,
                "x1": x,
                "y1": y,
                "x2": x + w,
                "y2": y + h,
                "w": w,
                "h": h,
                "cx": x + w // 2,
                "cy": y + h // 2,
                "area": area,
                "method": "HSV+ROI"
            })

        return detections

    def split_detections(self, detections):
        fires = [d for d in detections if d["class_name"] == "fire"]
        smokes = [d for d in detections if d["class_name"] == "smoke"]

        return fires, smokes

    def confirm_detection(self, fires, smokes):
        if len(fires) > 0:
            self.fire_confirm_count += 1
        else:
            self.fire_confirm_count = 0

        if len(smokes) > 0:
            self.smoke_confirm_count += 1
        else:
            self.smoke_confirm_count = 0

        confirmed_fire = self.fire_confirm_count >= self.confirm_threshold
        confirmed_smoke = self.smoke_confirm_count >= self.confirm_threshold

        return confirmed_fire, confirmed_smoke

    def estimate_danger_level(self, fires, smokes):
        fire_score = sum(d["area"] * d["confidence"] for d in fires)
        smoke_score = sum(d["area"] * d["confidence"] for d in smokes)

        total_score = fire_score * 1.8 + smoke_score * 0.8

        if total_score >= 90000:
            return "HIGH"
        elif total_score >= 40000:
            return "MEDIUM"
        elif total_score >= 8000:
            return "LOW"
        else:
            return "NORMAL"

    def decide_robot_command(self, fires, smokes, frame_width):
        if len(fires) > 0:
            main_fire = max(fires, key=lambda d: d["area"] * d["confidence"])
            cx = main_fire["cx"]

            if cx < frame_width // 3:
                return "LEFT"

            if cx > frame_width * 2 // 3:
                return "RIGHT"

            if main_fire["area"] >= self.close_fire_area:
                return "PUMP"

            return "FORWARD"

        if len(smokes) > 0:
            return "SEARCH"

        return "STOP"

    def make_message(self, fires, smokes):
        if self.mode == "agriculture":
            if len(fires) > 0:
                return "Fire detected in farm area. Alphabot approaches and activates water pump."
            if len(smokes) > 0:
                return "Smoke detected in farm area. Alphabot searches for fire source."
            return "Farm area is safe."

        if len(fires) > 0:
            return "Fire detected in smart city area. Alert and robot response activated."
        if len(smokes) > 0:
            return "Smoke detected in smart city camera zone."
        return "Smart city area is safe."

    def draw_result(self, frame, detections, danger_level, command, message, control_mode):
        height, width, _ = frame.shape

        cv2.line(frame, (width // 3, 0), (width // 3, height), (255, 255, 255), 1)
        cv2.line(frame, (width * 2 // 3, 0), (width * 2 // 3, height), (255, 255, 255), 1)

        for d in detections:
            color = (0, 0, 255) if d["class_name"] == "fire" else (160, 160, 160)

            cv2.rectangle(frame, (d["x1"], d["y1"]), (d["x2"], d["y2"]), color, 2)
            cv2.circle(frame, (d["cx"], d["cy"]), 5, color, -1)

            label = f'{d["class_name"].upper()} {d["confidence"]:.2f} {d["method"]}'

            cv2.putText(
                frame,
                label,
                (d["x1"], max(25, d["y1"] - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                color,
                2
            )

        cv2.rectangle(frame, (0, 0), (width, 220), (0, 0, 0), -1)

        cv2.putText(frame, self.title, (20, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2)

        cv2.putText(frame, f"Location: {self.location}", (20, 65),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 2)

        cv2.putText(frame, f"Control Mode: {control_mode}", (20, 95),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        cv2.putText(frame, f"Danger Level: {danger_level}", (20, 125),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, self.level_color(danger_level), 2)

        cv2.putText(frame, f"Robot Command: {command}", (20, 155),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

        cv2.putText(frame, message[:95], (20, 185),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

        cv2.putText(frame, "Web dashboard: http://127.0.0.1:5000", (20, 210),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

        return frame

    def level_color(self, level):
        if level == "HIGH":
            return (0, 0, 255)
        if level == "MEDIUM":
            return (0, 165, 255)
        if level == "LOW":
            return (0, 255, 255)
        return (0, 255, 0)


# ==================================================
# ALERT MANAGER
# ==================================================

class AlertManager:
    def __init__(self, blockchain):
        self.blockchain = blockchain
        self.last_alert_time = 0
        self.notification = NotificationManager()

        if not os.path.exists(ALERT_FOLDER):
            os.makedirs(ALERT_FOLDER)

    def handle_alert(self, frame, mode, danger_level, command, message, detections):
        if danger_level == "NORMAL":
            return

        now = time.time()

        if now - self.last_alert_time < ALERT_INTERVAL:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        image_path = os.path.join(ALERT_FOLDER, f"alert_{timestamp}.jpg")

        cv2.imwrite(image_path, frame)

        alert_data = {
            "time": str(datetime.now()),
            "mode": mode,
            "danger_level": danger_level,
            "robot_command": command,
            "message": message,
            "image_path": image_path,
            "detections": [
                {
                    "class_name": d["class_name"],
                    "confidence": round(float(d["confidence"]), 3),
                    "area": int(d["area"]),
                    "method": d["method"]
                }
                for d in detections
            ]
        }

        self.blockchain.add_alert(alert_data)

        with open(ALERT_HISTORY_FILE, "a", encoding="utf-8") as file:
            file.write(json.dumps(alert_data, ensure_ascii=False) + "\n")

        alert_text = (
            "CẢNH BÁO CHÁY TỪ ALPHABOT\n"
            f"Thời gian: {datetime.now()}\n"
            f"Chế độ: {mode}\n"
            f"Mức nguy hiểm: {danger_level}\n"
            f"Lệnh robot: {command}\n"
            f"Nội dung: {message}\n"
            f"Ảnh: {image_path}"
        )

        self.notification.send_telegram(alert_text, image_path)

        self.notification.send_email(
            subject="CẢNH BÁO CHÁY TỪ ALPHABOT",
            body=alert_text,
            image_path=image_path
        )

        print("[ALERT]", message)
        print("[ALERT IMAGE]", image_path)

        self.last_alert_time = now

        current_state = get_state()
        set_state(alert_count=current_state["alert_count"] + 1)


# ==================================================
# INIT OBJECTS
# ==================================================

blockchain = FireBlockchain(BLOCKCHAIN_FILE)
detector = FireDetector(MODE)
alphabot = AlphabotController(ARDUINO_PORT, BAUD_RATE)
alert_manager = AlertManager(blockchain)

set_state(blockchain_valid=blockchain.validate_chain())


# ==================================================
# VIDEO STREAM
# ==================================================

def generate_frames():
    cap = cv2.VideoCapture(CAMERA_SOURCE)

    if not cap.isOpened():
        set_state(
            camera_ok=False,
            danger_level="ERROR",
            message="Cannot open camera. Check CAMERA_SOURCE or webcam permission.",
            command="STOP"
        )

        blank = np.zeros((FRAME_HEIGHT, FRAME_WIDTH, 3), dtype=np.uint8)

        cv2.putText(blank, "Cannot open camera", (60, 240),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)

        cv2.putText(blank, "Check CAMERA_SOURCE / USB camera / permission", (60, 290),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        while True:
            ok, buffer = cv2.imencode(".jpg", blank)

            if ok:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n"
                )

            time.sleep(1)

    set_state(camera_ok=True)

    while True:
        ret, frame = cap.read()

        if not ret:
            set_state(camera_ok=False, message="Cannot read frame.")
            time.sleep(0.2)
            continue

        frame = cv2.resize(frame, (FRAME_WIDTH, FRAME_HEIGHT))

        mode = get_current_mode()
        detector.update_mode(mode)

        detections = detector.detect(frame)
        fires, smokes = detector.split_detections(detections)

        confirmed_fire, confirmed_smoke = detector.confirm_detection(fires, smokes)

        if not confirmed_fire:
            fires = []

        if not confirmed_smoke:
            smokes = []

        danger_level = detector.estimate_danger_level(fires, smokes)
        auto_command = detector.decide_robot_command(fires, smokes, FRAME_WIDTH)
        message = detector.make_message(fires, smokes)

        current_state = get_state()
        manual_mode = current_state["manual_mode"]
        manual_command = current_state["command"]

        if manual_mode:
            command = manual_command
            control_mode = "MANUAL"
        else:
            command = auto_command
            control_mode = "AUTO"

        alphabot.send_command(command)

        result_frame = detector.draw_result(
            frame,
            detections,
            danger_level,
            command,
            message,
            control_mode
        )

        alert_manager.handle_alert(
            result_frame,
            mode,
            danger_level,
            command,
            message,
            detections
        )

        set_state(
            mode=mode,
            command=command,
            danger_level=danger_level,
            message=message,
            control_mode=control_mode,
            detections=[
                {
                    "class_name": d["class_name"],
                    "confidence": round(float(d["confidence"]), 3),
                    "area": int(d["area"]),
                    "method": d["method"],
                    "x1": int(d["x1"]),
                    "y1": int(d["y1"]),
                    "x2": int(d["x2"]),
                    "y2": int(d["y2"])
                }
                for d in detections
            ],
            camera_ok=True,
            blockchain_valid=blockchain.validate_chain()
        )

        ok, buffer = cv2.imencode(".jpg", result_frame)

        if not ok:
            continue

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n"
        )


# ==================================================
# ROUTES
# ==================================================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/video_feed")
def video_feed():
    return Response(
        generate_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@app.route("/api/status")
def api_status():
    payload = get_state()
    payload["chain_length"] = len(blockchain.to_list())
    return jsonify(payload)


@app.route("/api/blockchain")
def api_blockchain():
    return jsonify(blockchain.to_list())


@app.route("/api/alerts")
def api_alerts():
    alerts = []

    if os.path.exists(ALERT_HISTORY_FILE):
        with open(ALERT_HISTORY_FILE, "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()

                if not line:
                    continue

                try:
                    alerts.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    alerts.reverse()

    return jsonify(alerts[:100])


@app.route("/api/command", methods=["POST"])
def api_command():
    data = request.get_json(force=True) or {}

    command = str(data.get("command", "STOP")).upper()

    allowed = {
        "FORWARD",
        "BACKWARD",
        "LEFT",
        "RIGHT",
        "PUMP",
        "SEARCH",
        "STOP"
    }

    if command not in allowed:
        return jsonify({"ok": False, "error": "Invalid command"}), 400

    set_state(
        command=command,
        manual_mode=True,
        control_mode="MANUAL"
    )

    alphabot.send_command(command)

    return jsonify({
        "ok": True,
        "command": command,
        "manual_mode": True
    })


@app.route("/api/auto", methods=["POST"])
def api_auto():
    set_state(
        manual_mode=False,
        control_mode="AUTO"
    )

    return jsonify({
        "ok": True,
        "manual_mode": False
    })


@app.route("/api/mode", methods=["POST"])
def api_mode():
    data = request.get_json(force=True) or {}

    mode = str(data.get("mode", "agriculture")).lower()

    if mode not in {"agriculture", "smart_city"}:
        return jsonify({"ok": False, "error": "Invalid mode"}), 400

    detector.update_mode(mode)
    set_state(mode=mode)

    return jsonify({
        "ok": True,
        "mode": mode
    })


@app.route("/api/simulate_alert", methods=["POST"])
def api_simulate_alert():
    mode = get_current_mode()

    blank = np.zeros((FRAME_HEIGHT, FRAME_WIDTH, 3), dtype=np.uint8)

    cv2.putText(blank, "SIMULATED FIRE ALERT", (60, 240),
                cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)

    detections = [
        {
            "class_name": "fire",
            "confidence": 0.95,
            "area": 100000,
            "method": "WEB-SIMULATION",
            "x1": 100,
            "y1": 100,
            "x2": 500,
            "y2": 400
        }
    ]

    message = "Fire detected from web simulation. Alphabot activates water pump."

    alert_manager.handle_alert(
        blank,
        mode,
        "HIGH",
        "PUMP",
        message,
        detections
    )

    set_state(
        danger_level="HIGH",
        command="PUMP",
        message=message
    )

    return jsonify({"ok": True})


@app.route("/api/shutdown_robot", methods=["POST"])
def api_shutdown_robot():
    alphabot.send_command("STOP")

    set_state(
        command="STOP",
        manual_mode=True,
        control_mode="MANUAL"
    )

    return jsonify({
        "ok": True,
        "command": "STOP"
    })


# ==================================================
# MAIN
# ==================================================

if __name__ == "__main__":
    print("===================================================")
    print("ALPHABOT FIREFIGHTING WEB SYSTEM")
    print("Open: http://127.0.0.1:5000")
    print("Camera source:", CAMERA_SOURCE)
    print("Arduino port:", ARDUINO_PORT)
    print("Mode:", MODE)
    print("===================================================")

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=False,
        threaded=True
    )