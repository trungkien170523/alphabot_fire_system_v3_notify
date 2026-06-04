import os
import cv2
import time
import json
import hashlib
import serial
import numpy as np
import requests
import smtplib
from email.message import EmailMessage
from datetime import datetime

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except Exception:
    YOLO_AVAILABLE = False


# ==================================================
# CONFIG
# ==================================================

CAMERA_SOURCE = 0

ARDUINO_PORT = "COM3"
BAUD_RATE = 9600

MODE = "agriculture"
# MODE = "smart_city"

FRAME_WIDTH = 960
FRAME_HEIGHT = 540

YOLO_MODEL_PATH = "fire_smoke.pt"
FALLBACK_MODEL_PATH = "yolo11n.pt"

CONF_THRESHOLD = 0.45

SEND_INTERVAL = 0.35
ALERT_INTERVAL = 10

CLOSE_FIRE_AREA_AGRICULTURE = 35000
CLOSE_FIRE_AREA_CITY = 45000

ALERT_FOLDER = "alerts"
BLOCKCHAIN_FILE = "blockchain_log.json"

MANUAL_MODE = False


# ==================================================
# TELEGRAM + EMAIL CONFIG
# ==================================================

ENABLE_TELEGRAM = True
ENABLE_EMAIL = False

# Telegram
TELEGRAM_BOT_TOKEN = "8738375015:AAGK6Qs_el7xYA85aCzHKm9i5R_L41ZVvhg"
TELEGRAM_CHAT_ID = "7377037240"

# Email Gmail SMTP
EMAIL_SENDER = "emailcuaban@gmail.com"
EMAIL_PASSWORD = "app_password_gmail"
EMAIL_RECEIVER = "emailnhan@gmail.com"

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587


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

        block_string = json.dumps(block_content, sort_keys=True)
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
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i - 1]

            if current.hash != current.calculate_hash():
                return False

            if current.previous_hash != previous.hash:
                return False

        return True


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
        except Exception as e:
            print("[SIMULATION] Arduino not connected.")
            print("[INFO] Robot commands will be printed only.")
            print(e)

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

        if TELEGRAM_BOT_TOKEN == "DAN_BOT_TOKEN_CUA_BAN_VAO_DAY":
            print("[TELEGRAM] Missing bot token.")
            return

        if TELEGRAM_CHAT_ID == "DAN_CHAT_ID_CUA_BAN_VAO_DAY":
            print("[TELEGRAM] Missing chat id.")
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
        self.use_yolo = False

        self.fire_confirm_count = 0
        self.smoke_confirm_count = 0
        self.confirm_threshold = 5

        if mode == "agriculture":
            self.title = "ALPHABOT FIRE ROBOT - SMART AGRICULTURE"
            self.close_fire_area = CLOSE_FIRE_AREA_AGRICULTURE
            self.location = "Farm / Greenhouse / Storage Area"
        else:
            self.title = "ALPHABOT FIRE ROBOT - SMART CITY"
            self.close_fire_area = CLOSE_FIRE_AREA_CITY
            self.location = "Parking / Factory / Urban Camera Zone"

        if YOLO_AVAILABLE and os.path.exists(YOLO_MODEL_PATH):
            try:
                self.model = YOLO(YOLO_MODEL_PATH)
                self.use_yolo = True
                self.use_custom_yolo = True
                print("[OK] Using custom fire/smoke YOLO model:", YOLO_MODEL_PATH)
            except Exception as e:
                print("[WARNING] Invalid fire_smoke.pt. Switching to HSV fallback.")
                print(e)
                self.model = None
                self.use_yolo = False
                self.use_custom_yolo = False

        elif YOLO_AVAILABLE and os.path.exists(FALLBACK_MODEL_PATH):
            print("[WARNING] fire_smoke.pt not found.")
            print("[INFO] Using HSV fallback for fire/smoke detection.")
        else:
            print("[INFO] YOLO not available. Using HSV fallback.")

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

        cv2.putText(frame, message, (20, 185),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

        cv2.putText(frame, "Alert: Telegram/Email enabled", (20, 210),
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

        with open("fire_alert_history.txt", "a", encoding="utf-8") as file:
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


# ==================================================
# KEYBOARD CONTROL
# ==================================================

def handle_keyboard(key, manual_mode, current_manual_command):
    if key == ord("m"):
        manual_mode = not manual_mode

        if manual_mode:
            current_manual_command = "STOP"
            print("[MODE] Manual control enabled")
        else:
            current_manual_command = "STOP"
            print("[MODE] Auto control enabled")

    if manual_mode:
        if key == ord("w"):
            current_manual_command = "FORWARD"
        elif key == ord("s"):
            current_manual_command = "BACKWARD"
        elif key == ord("a"):
            current_manual_command = "LEFT"
        elif key == ord("d"):
            current_manual_command = "RIGHT"
        elif key == ord("p"):
            current_manual_command = "PUMP"
        elif key == ord("x"):
            current_manual_command = "STOP"

    return manual_mode, current_manual_command


# ==================================================
# MAIN
# ==================================================

def main():
    global MANUAL_MODE

    print("===================================================")
    print("ALPHABOT FIREFIGHTING SYSTEM V3")
    print("Image Processing + YOLO/HSV + Blockchain + Telegram/Email")
    print("===================================================")
    print("Mode:", MODE)
    print("Camera:", CAMERA_SOURCE)
    print("Keys:")
    print("  M = Auto/Manual")
    print("  W = Forward")
    print("  S = Backward")
    print("  A = Left")
    print("  D = Right")
    print("  P = Pump")
    print("  X = Stop")
    print("  Q = Quit")
    print("===================================================")

    blockchain = FireBlockchain(BLOCKCHAIN_FILE)
    print("[BLOCKCHAIN VALID]", blockchain.validate_chain())

    detector = FireDetector(MODE)
    alphabot = AlphabotController(ARDUINO_PORT, BAUD_RATE)
    alert_manager = AlertManager(blockchain)

    cap = cv2.VideoCapture(CAMERA_SOURCE)

    if not cap.isOpened():
        print("[ERROR] Cannot open camera.")
        alphabot.close()
        return

    manual_command = "STOP"

    while True:
        ret, frame = cap.read()

        if not ret:
            print("[ERROR] Cannot read frame.")
            break

        frame = cv2.resize(frame, (FRAME_WIDTH, FRAME_HEIGHT))

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

        if MANUAL_MODE:
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
            MODE,
            danger_level,
            command,
            message,
            detections
        )

        cv2.imshow("Alphabot Firefighting System V3", result_frame)

        key = cv2.waitKey(1) & 0xFF

        MANUAL_MODE, manual_command = handle_keyboard(
            key,
            MANUAL_MODE,
            manual_command
        )

        if key == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    alphabot.close()

    print("[DONE] System stopped.")


if __name__ == "__main__":
    main()