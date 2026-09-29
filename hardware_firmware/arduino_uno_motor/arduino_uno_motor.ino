/**
 * @file arduino_uno_motor.ino
 * @brief 아두이노 우노(Arduino Uno) + L298N 모터 드라이버 시리얼 제어 펌웨어
 * @details 
 *  - PC / 라즈베리파이 / ESP32와 USB 시리얼(115200 bps)로 연결
 *  - 단일 문자 제어 ('F', 'B', 'L', 'R', 'S') 및 가변 속도 제어 ("V,left,right\n")
 *  - 워치독 타임아웃: 1초 이상 명령 수신 없을 시 자동 정지
 */

// L298N 핀 설정
const int ENA = 5;   // 좌측 모터 속도 (PWM)
const int IN1 = 6;   // 좌측 정회전
const int IN2 = 7;   // 좌측 역회전
const int IN3 = 8;   // 우측 정회전
const int IN4 = 9;   // 우측 역회전
const int ENB = 10;  // 우측 모터 속도 (PWM)

unsigned long lastCmdTime = 0;
const unsigned long CMD_TIMEOUT = 1000; // 1초 타임아웃

void setLeftMotor(int speed) {
  if (speed > 0) {
    digitalWrite(IN1, HIGH);
    digitalWrite(IN2, LOW);
    analogWrite(ENA, constrain(speed, 0, 255));
  } else if (speed < 0) {
    digitalWrite(IN1, LOW);
    digitalWrite(IN2, HIGH);
    analogWrite(ENA, constrain(-speed, 0, 255));
  } else {
    digitalWrite(IN1, LOW);
    digitalWrite(IN2, LOW);
    analogWrite(ENA, 0);
  }
}

void setRightMotor(int speed) {
  if (speed > 0) {
    digitalWrite(IN3, HIGH);
    digitalWrite(IN4, LOW);
    analogWrite(ENB, constrain(speed, 0, 255));
  } else if (speed < 0) {
    digitalWrite(IN3, LOW);
    digitalWrite(IN4, HIGH);
    analogWrite(ENB, constrain(-speed, 0, 255));
  } else {
    digitalWrite(IN3, LOW);
    digitalWrite(IN4, LOW);
    analogWrite(ENB, 0);
  }
}

void drive(int left, int right) {
  setLeftMotor(left);
  setRightMotor(right);
  lastCmdTime = millis();
}

void stopAll() {
  drive(0, 0);
}

void setup() {
  Serial.begin(115200);
  pinMode(ENA, OUTPUT);
  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  pinMode(IN3, OUTPUT);
  pinMode(IN4, OUTPUT);
  pinMode(ENB, OUTPUT);

  stopAll();
  Serial.println("ARDUINO_UNO_L298N_READY");
}

void loop() {
  // 타임아웃 감지 시 긴급 정지
  if (millis() - lastCmdTime > CMD_TIMEOUT) {
    stopAll();
  }

  if (Serial.available() > 0) {
    String input = Serial.readStringUntil('\n');
    input.trim();
    if (input.length() == 0) return;

    char cmd = input.charAt(0);

    if (cmd == 'F') {
      drive(200, 200);
    } else if (cmd == 'B') {
      drive(-200, -200);
    } else if (cmd == 'L') {
      drive(-180, 180);
    } else if (cmd == 'R') {
      drive(180, -180);
    } else if (cmd == 'S') {
      stopAll();
    } else if (cmd == 'V') {
      // 포맷: V,left,right (예: V,150,150)
      int comma1 = input.indexOf(',');
      int comma2 = input.indexOf(',', comma1 + 1);
      if (comma1 > 0 && comma2 > 0) {
        int l = input.substring(comma1 + 1, comma2).toInt();
        int r = input.substring(comma2 + 1).toInt();
        drive(l, r);
      }
    }
  }
}
