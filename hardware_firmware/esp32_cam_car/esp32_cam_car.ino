/**
 * @file esp32_cam_car.ino
 * @brief ESP32-CAM (AI-Thinker) 기반 Wi-Fi 영상 스트리밍 및 모터 제어 펌웨어
 * @details 
 *  - MJPEG 영상 스트리밍 서버 (Port 81: /stream)
 *  - WebSocket 기반 실시간 양방향 모터 제어 (Port 82: ws://<IP>:82/)
 *  - L9110S / L298N 모터 드라이버 2WD 차동 제어 지원
 */

#include "esp_camera.h"
#include <WiFi.h>
#include <AsyncTCP.h>
#include <ESPAsyncWebServer.h>

// ==========================================
// 1. Wi-Fi 설정 (AP 모드 또는 공유기 연결)
// ==========================================
// STA 모드 (공유기 연결 시)
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// AP 모드 (공유기 없을 때 자체 핫스팟 생성)
const bool USE_AP_MODE = true;
const char* ap_ssid = "PhysicalAI_AGV_AP";
const char* ap_password = "password1234";

// ==========================================
// 2. 모터 제어 핀 매핑 (AI-Thinker ESP32-CAM 기준)
// 주의: SD 카드를 사용하지 않을 때 안전하게 사용 가능한 GPIO
// ==========================================
#define MOTOR_LEFT_F   12  // 좌측 모터 전진 (IN1)
#define MOTOR_LEFT_B   13  // 좌측 모터 후진 (IN2)
#define MOTOR_RIGHT_F  14  // 우측 모터 전진 (IN3)
#define MOTOR_RIGHT_B  15  // 우측 모터 후진 (IN4)

// PWM 채널 설정
#define PWM_FREQ       1000
#define PWM_RES        8
#define PWM_CH_LF      0
#define PWM_CH_LB      1
#define PWM_CH_RF      2
#define PWM_CH_RB      3

// ==========================================
// 3. AI-Thinker ESP32-CAM 핀맵 정의
// ==========================================
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27

#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

// 서버 객체 선언
AsyncWebServer server(80);
AsyncWebSocket ws("/ws");
WiFiServer streamServer(81);

// 모터 속도 변수 (-255 ~ 255)
int targetSpeedL = 0;
int targetSpeedR = 0;

void setMotorPWM(int pinForward, int pinBackward, int chF, int chB, int speed) {
  if (speed > 0) {
    ledcWrite(chF, speed);
    ledcWrite(chB, 0);
  } else if (speed < 0) {
    ledcWrite(chF, 0);
    ledcWrite(chB, -speed);
  } else {
    ledcWrite(chF, 0);
    ledcWrite(chB, 0);
  }
}

void applyMotorSpeeds(int speedL, int speedR) {
  speedL = constrain(speedL, -255, 255);
  speedR = constrain(speedR, -255, 255);
  setMotorPWM(MOTOR_LEFT_F, MOTOR_LEFT_B, PWM_CH_LF, PWM_CH_LB, speedL);
  setMotorPWM(MOTOR_RIGHT_F, MOTOR_RIGHT_B, PWM_CH_RF, PWM_CH_RB, speedR);
}

void stopMotors() {
  applyMotorSpeeds(0, 0);
}

// WebSocket 이벤트 핸들러
void onWsEvent(AsyncWebSocket *server, AsyncWebSocketClient *client, AwsEventType type, void *arg, uint8_t *data, size_t len) {
  if (type == WS_EVT_CONNECT) {
    Serial.printf("WS Client connected: %u\n", client->id());
  } else if (type == WS_EVT_DISCONNECT) {
    Serial.printf("WS Client disconnected: %u\n", client->id());
    stopMotors(); // 연결 끊김 시 비상 정지 (Fail-Safe)
  } else if (type == WS_EVT_DATA) {
    AwsFrameInfo *info = (AwsFrameInfo*)arg;
    if (info->final && info->index == 0 && info->len == len && info->opcode == WS_TEXT) {
      data[len] = 0;
      char* msg = (char*)data;
      
      // 포맷 1: 단축 명령 ("F", "B", "L", "R", "S")
      if (strcmp(msg, "F") == 0) {
        applyMotorSpeeds(220, 220);
      } else if (strcmp(msg, "B") == 0) {
        applyMotorSpeeds(-220, -220);
      } else if (strcmp(msg, "L") == 0) {
        applyMotorSpeeds(-180, 180);
      } else if (strcmp(msg, "R") == 0) {
        applyMotorSpeeds(180, -180);
      } else if (strcmp(msg, "S") == 0) {
        stopMotors();
      } 
      // 포맷 2: 정밀 속도 제어 ("SPEED,left,right", 예: "SPEED,200,200")
      else if (strncmp(msg, "SPEED,", 6) == 0) {
        int l = 0, r = 0;
        if (sscanf(msg + 6, "%d,%d", &l, &r) == 2) {
          applyMotorSpeeds(l, r);
        }
      }
    }
  }
}

void initCamera() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;

  if (psramFound()) {
    config.frame_size = FRAMESIZE_VGA; // 640x480
    config.jpeg_quality = 12;          // 0-63 낮을수록 고화질
    config.fb_count = 2;
  } else {
    config.frame_size = FRAMESIZE_QVGA; // 320x240
    config.jpeg_quality = 15;
    config.fb_count = 1;
  }

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x\n", err);
    return;
  }
  Serial.println("Camera Init Success.");
}

void handleStream() {
  WiFiClient client = streamServer.available();
  if (!client) return;

  client.print("HTTP/1.1 200 OK\r\n"
               "Content-Type: multipart/x-mixed-replace; boundary=frame\r\n\r\n");

  while (client.connected()) {
    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb) {
      Serial.println("Camera capture failed");
      break;
    }

    client.print("--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + String(fb->len) + "\r\n\r\n");
    client.write(fb->buf, fb->len);
    client.print("\r\n");

    esp_camera_fb_return(fb);
    yield();
  }
  client.stop();
}

void setup() {
  Serial.begin(115200);
  Serial.println("\n=== Physical AI AGV Firmware Starting ===");

  // 모터 핀 및 PWM 설정
  ledcSetup(PWM_CH_LF, PWM_FREQ, PWM_RES);
  ledcSetup(PWM_CH_LB, PWM_FREQ, PWM_RES);
  ledcSetup(PWM_CH_RF, PWM_FREQ, PWM_RES);
  ledcSetup(PWM_CH_RB, PWM_FREQ, PWM_RES);

  ledcAttachPin(MOTOR_LEFT_F, PWM_CH_LF);
  ledcAttachPin(MOTOR_LEFT_B, PWM_CH_LB);
  ledcAttachPin(MOTOR_RIGHT_F, PWM_CH_RF);
  ledcAttachPin(MOTOR_RIGHT_B, PWM_CH_RB);
  stopMotors();

  // 카메라 초기화
  initCamera();

  // Wi-Fi 연결 또는 핫스팟 가동
  if (USE_AP_MODE) {
    WiFi.softAP(ap_ssid, ap_password);
    Serial.print("AP Mode Started! SSID: ");
    Serial.println(ap_ssid);
    Serial.print("IP Address: ");
    Serial.println(WiFi.softAPIP());
  } else {
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) {
      delay(500);
      Serial.print(".");
    }
    Serial.println("\nWiFi Connected!");
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());
  }

  // WebSocket 핸들러 등록
  ws.onEvent(onWsEvent);
  server.addHandler(&ws);
  server.begin();

  // 스트리밍 소켓 서버 시작
  streamServer.begin();

  Serial.println("Server ready.");
  Serial.println("Stream URL: http://<IP>:81/stream");
  Serial.println("WebSocket:  ws://<IP>/ws");
}

void loop() {
  handleStream();
  ws.cleanupClients();
}
