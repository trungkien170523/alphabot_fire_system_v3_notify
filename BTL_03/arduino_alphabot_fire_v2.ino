#include <Servo.h>
#include <SoftwareSerial.h>

// ================= BLUETOOTH =================
SoftwareSerial bluetooth(2, 4); 
// D2 RX, D4 TX

// ================= MOTOR =================
const int ENA = 5;
const int IN1 = 8;
const int IN2 = 9;

const int ENB = 6;
const int IN3 = 10;
const int IN4 = 11;

// ================= PUMP =================
const int PUMP_PIN = 7;

// ================= SERVO =================
const int SERVO_PIN = 3;
Servo nozzleServo;

// ================= SENSOR =================
const int TRIG_PIN = 12;
const int ECHO_PIN = 13;
const int OBSTACLE_DISTANCE = 18;

// ================= SPEED =================
int motorSpeed = 165;
int turnSpeed = 130;

// ================= COMMAND =================
String command = "STOP";
String lastCommand = "";

unsigned long lastCommandTime = 0;
const unsigned long commandTimeout = 1500;

// ================= SETUP =================
void setup() {
  Serial.begin(9600);
  bluetooth.begin(9600);

  pinMode(ENA, OUTPUT);
  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);

  pinMode(ENB, OUTPUT);
  pinMode(IN3, OUTPUT);
  pinMode(IN4, OUTPUT);

  pinMode(PUMP_PIN, OUTPUT);

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);

  nozzleServo.attach(SERVO_PIN);
  nozzleServo.write(90);

  stopCar();
  pumpOff();

  Serial.println("Robot Ready");
  bluetooth.println("Bluetooth Ready");
}

// ================= LOOP =================
void loop() {

  readSerialCommand();     // từ Python
  readBluetoothCommand();  // từ điện thoại

  if (millis() - lastCommandTime > commandTimeout) {
    command = "STOP";
  }

  executeCommand();
}

// ================= SERIAL (AI) =================
void readSerialCommand() {
  if (Serial.available()) {
    String received = Serial.readStringUntil('\n');
    received.trim();

    if (received.length() > 0) {
      command = received;
      lastCommandTime = millis();
    }
  }
}

// ================= BLUETOOTH =================
void readBluetoothCommand() {
  if (bluetooth.available()) {
    char c = bluetooth.read();

    lastCommandTime = millis();

    if (c == 'F') command = "FORWARD";
    else if (c == 'B') command = "BACKWARD";
    else if (c == 'L') command = "LEFT";
    else if (c == 'R') command = "RIGHT";
    else if (c == 'S') command = "STOP";
    else if (c == 'P') command = "PUMP";
    else if (c == 'O') command = "STOP";
  }
}

// ================= EXECUTE =================
void executeCommand() {

  if (command == "FORWARD") {
    if (isObstacleAhead()) {
      stopCar();
    } else {
      forward();
    }
  }
  else if (command == "BACKWARD") backward();
  else if (command == "LEFT") turnLeft();
  else if (command == "RIGHT") turnRight();
  else if (command == "PUMP") {
    stopCar();
    pumpOn();
  }
  else if (command == "STOP") {
    stopCar();
    pumpOff();
  }
}

// ================= MOTOR =================
void forward() {
  analogWrite(ENA, motorSpeed);
  analogWrite(ENB, motorSpeed);

  digitalWrite(IN1, HIGH);
  digitalWrite(IN2, LOW);

  digitalWrite(IN3, HIGH);
  digitalWrite(IN4, LOW);
}

void backward() {
  analogWrite(ENA, motorSpeed);
  analogWrite(ENB, motorSpeed);

  digitalWrite(IN1, LOW);
  digitalWrite(IN2, HIGH);

  digitalWrite(IN3, LOW);
  digitalWrite(IN4, HIGH);
}

void turnLeft() {
  analogWrite(ENA, turnSpeed);
  analogWrite(ENB, turnSpeed);

  digitalWrite(IN1, LOW);
  digitalWrite(IN2, HIGH);

  digitalWrite(IN3, HIGH);
  digitalWrite(IN4, LOW);
}

void turnRight() {
  analogWrite(ENA, turnSpeed);
  analogWrite(ENB, turnSpeed);

  digitalWrite(IN1, HIGH);
  digitalWrite(IN2, LOW);

  digitalWrite(IN3, LOW);
  digitalWrite(IN4, HIGH);
}

void stopCar() {
  analogWrite(ENA, 0);
  analogWrite(ENB, 0);

  digitalWrite(IN1, LOW);
  digitalWrite(IN2, LOW);

  digitalWrite(IN3, LOW);
  digitalWrite(IN4, LOW);
}

// ================= PUMP =================
void pumpOn() {
  digitalWrite(PUMP_PIN, HIGH);
}

void pumpOff() {
  digitalWrite(PUMP_PIN, LOW);
}

// ================= SENSOR =================
long getDistanceCM() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);

  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);

  digitalWrite(TRIG_PIN, LOW);

  long duration = pulseIn(ECHO_PIN, HIGH, 25000);

  return duration * 0.034 / 2;
}

bool isObstacleAhead() {
  long d = getDistanceCM();
  return (d > 0 && d < OBSTACLE_DISTANCE);
}