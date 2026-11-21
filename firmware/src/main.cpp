// M5Stack CoreS3 + ENV III ミニ気象観測（Phase 1: 取得・表示・SD保存）
// ※ 実機未確認。I2Cピン・SDピンは公式情報に基づく暫定値。
#include <M5Unified.h>
#include <M5UnitENV.h>
#include <NimBLEDevice.h>
#include <SD.h>
#include <SPI.h>
#include <WiFi.h>
#include <time.h>

#if __has_include("secrets.h")
#include "secrets.h"
#define HAS_WIFI_SECRETS 1
#endif

// ---- 設定 ----
static const uint32_t INTERVAL_MS = 60 * 1000;  // 記録周期（1分）
static const char *TZ_JST = "JST-9";
static const int SD_SCK = 36, SD_MISO = 35, SD_MOSI = 37, SD_CS = 4;  // CoreS3 のSDスロット

static bool sdOk = false;

// ---- BLE（仕様は docs/data_format.md）----
#define SVC_UUID "b5dcd81f-8818-4a59-8055-4be29e1ab1ab"
#define CUR_UUID "93201d96-eec6-4b2f-a728-2fd5f41d8512"
#define CTL_UUID "cfb36b51-d385-497f-ad44-3f4b9bf0e9b6"
#define LOG_UUID "d6ee814f-18a7-4682-9420-06a34fc0a78a"

static NimBLECharacteristic *chCur = nullptr;
static NimBLECharacteristic *chLog = nullptr;
static volatile bool logRequested = false;  // コールバック内では重い処理をせずloopで実行
static char logDate[9] = "";

class CtlCallbacks : public NimBLECharacteristicCallbacks {
  void onWrite(NimBLECharacteristic *c, NimBLEConnInfo &) override {
    std::string v = c->getValue();
    // "DATE,YYYYMMDD" のみ受け付ける
    if (v.size() == 13 && v.compare(0, 5, "DATE,") == 0) {
      strncpy(logDate, v.c_str() + 5, 8);
      logDate[8] = '\0';
      logRequested = true;
    }
  }
};

class ServerCallbacks : public NimBLEServerCallbacks {
  void onDisconnect(NimBLEServer *, NimBLEConnInfo &, int) override {
    NimBLEDevice::startAdvertising();  // 切断後に再アドバタイズ
  }
};

static void setupBle() {
  NimBLEDevice::init("M5MiniWeather");
  NimBLEDevice::setMTU(185);
  NimBLEServer *server = NimBLEDevice::createServer();
  server->setCallbacks(new ServerCallbacks());
  NimBLEService *svc = server->createService(SVC_UUID);
  chCur = svc->createCharacteristic(CUR_UUID, NIMBLE_PROPERTY::READ | NIMBLE_PROPERTY::NOTIFY);
  NimBLECharacteristic *ctl = svc->createCharacteristic(CTL_UUID, NIMBLE_PROPERTY::WRITE);
  ctl->setCallbacks(new CtlCallbacks());
  chLog = svc->createCharacteristic(LOG_UUID, NIMBLE_PROPERTY::NOTIFY);
  svc->start();
  NimBLEAdvertising *adv = NimBLEDevice::getAdvertising();
  adv->addServiceUUID(SVC_UUID);
  adv->start();
}

// 指定日のCSVを1行ずつ通知し、最後に END（ファイルなしは NOFILE）
static void streamLog(const char *date) {
  char path[24];
  snprintf(path, sizeof(path), "/%s.csv", date);
  if (!sdOk || !SD.exists(path)) {
    chLog->setValue("NOFILE");
    chLog->notify();
    return;
  }
  File f = SD.open(path, FILE_READ);
  while (f && f.available()) {
    String line = f.readStringUntil('\n');
    line.trim();
    if (line.length() == 0) continue;
    chLog->setValue(std::string(line.c_str()));
    chLog->notify();
    delay(15);  // 通知の取りこぼし防止
  }
  if (f) f.close();
  chLog->setValue("END");
  chLog->notify();
}

SHT3X sht3x;
QMP6988 qmp;
static uint32_t lastMs = 0;

// 時刻が有効か（RTC未設定だと2000年付近になる）
static bool timeValid() {
  time_t t = time(nullptr);
  return t > 1700000000;  // 2023-11 以降
}

// Wi-Fi + NTP で時刻合わせし、成功したらRTCに保存する
static void syncTimeByNtp() {
#ifdef HAS_WIFI_SECRETS
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 15000) delay(200);
  if (WiFi.status() == WL_CONNECTED) {
    configTzTime(TZ_JST, "ntp.nict.jp", "pool.ntp.org");
    start = millis();
    while (!timeValid() && millis() - start < 10000) delay(200);
    if (timeValid()) {
      time_t t = time(nullptr);
      struct tm tmv;
      gmtime_r(&t, &tmv);  // RTCはUTCで保持
      M5.Rtc.setDateTime(&tmv);
      Serial.println("NTP同期OK");
    }
  }
  WiFi.disconnect(true);
  WiFi.mode(WIFI_OFF);  // 消費電力と発熱を抑えるため切る
#endif
}

// RTC の時刻をシステム時刻へ反映
static void loadTimeFromRtc() {
  if (timeValid()) return;
  auto dt = M5.Rtc.getDateTime();
  if (dt.date.year >= 2024) {
    struct tm tmv = {};
    tmv.tm_year = dt.date.year - 1900;
    tmv.tm_mon = dt.date.month - 1;
    tmv.tm_mday = dt.date.date;
    tmv.tm_hour = dt.time.hours;
    tmv.tm_min = dt.time.minutes;
    tmv.tm_sec = dt.time.seconds;
    setenv("TZ", "UTC0", 1);
    tzset();
    time_t t = mktime(&tmv);
    struct timeval tv = {t, 0};
    settimeofday(&tv, nullptr);
  }
  setenv("TZ", TZ_JST, 1);
  tzset();
}

// ISO 8601（+09:00）形式の時刻文字列
static void isoNow(char *buf, size_t n) {
  time_t t = time(nullptr);
  struct tm tmv;
  localtime_r(&t, &tmv);
  snprintf(buf, n, "%04d-%02d-%02dT%02d:%02d:%02d+09:00", tmv.tm_year + 1900, tmv.tm_mon + 1,
           tmv.tm_mday, tmv.tm_hour, tmv.tm_min, tmv.tm_sec);
}

// SD に1行追記（日付ごとのファイル）。読み取り失敗時は値を空欄にして行を残す
static void appendCsv(const char *ts, bool ok, float temp, float hum, float pres) {
  if (!sdOk) return;
  time_t t = time(nullptr);
  struct tm tmv;
  localtime_r(&t, &tmv);
  char path[24];
  snprintf(path, sizeof(path), "/%04d%02d%02d.csv", tmv.tm_year + 1900, tmv.tm_mon + 1, tmv.tm_mday);
  bool isNew = !SD.exists(path);
  File f = SD.open(path, FILE_APPEND);
  if (!f) return;
  if (isNew) f.println("timestamp,temp_c,humidity_pct,pressure_hpa,battery_pct");
  if (ok) {
    f.printf("%s,%.2f,%.1f,%.2f,%d\n", ts, temp, hum, pres, (int)M5.Power.getBatteryLevel());
  } else {
    f.printf("%s,,,,%d\n", ts, (int)M5.Power.getBatteryLevel());
  }
  f.close();
}

static void draw(const char *ts, bool ok, float temp, float hum, float pres) {
  M5.Display.fillScreen(BLACK);
  M5.Display.setTextColor(WHITE);
  M5.Display.setTextSize(2);
  M5.Display.setCursor(8, 8);
  M5.Display.println(ts);
  M5.Display.setTextSize(3);
  M5.Display.setCursor(8, 50);
  if (ok) {
    M5.Display.printf("%.1f C\n", temp);
    M5.Display.setCursor(8, 90);
    M5.Display.printf("%.1f %%\n", hum);
    M5.Display.setCursor(8, 130);
    M5.Display.printf("%.1f hPa\n", pres);
  } else {
    M5.Display.println("sensor error");
  }
  M5.Display.setTextSize(2);
  M5.Display.setCursor(8, 200);
  M5.Display.printf("SD:%s BAT:%d%%", sdOk ? "OK" : "NG", (int)M5.Power.getBatteryLevel());
}

void setup() {
  auto cfg = M5.config();
  M5.begin(cfg);
  Serial.begin(115200);

  // ENV III は Port A（I2C）
  Wire.begin(M5.Ex_I2C.getSDA(), M5.Ex_I2C.getSCL());
  sht3x.begin(&Wire, SHT3X_I2C_ADDR, M5.Ex_I2C.getSDA(), M5.Ex_I2C.getSCL(), 400000U);
  qmp.begin(&Wire, QMP6988_SLAVE_ADDRESS_L, M5.Ex_I2C.getSDA(), M5.Ex_I2C.getSCL(), 400000U);

  SPI.begin(SD_SCK, SD_MISO, SD_MOSI, SD_CS);
  sdOk = SD.begin(SD_CS, SPI, 25000000);

  loadTimeFromRtc();
  if (!timeValid()) syncTimeByNtp();
  loadTimeFromRtc();

  setupBle();
}

void loop() {
  M5.update();
  uint32_t now = millis();
  if (lastMs == 0 || now - lastMs >= INTERVAL_MS) {
    lastMs = now;
    bool ok = sht3x.update() && qmp.update();
    float temp = sht3x.cTemp, hum = sht3x.humidity, pres = qmp.pressure / 100.0f;  // Pa → hPa
    char ts[32];
    isoNow(ts, sizeof(ts));
    Serial.printf("%s,%.2f,%.1f,%.2f ok=%d\n", ts, temp, hum, pres, ok);
    draw(ts, ok, temp, hum, pres);
    appendCsv(ts, ok, temp, hum, pres);

    // 現在値をBLEで通知（ヘッダーと同じ列順のCSV 1行）
    char row[96];
    if (ok) {
      snprintf(row, sizeof(row), "%s,%.2f,%.1f,%.2f,%d", ts, temp, hum, pres, (int)M5.Power.getBatteryLevel());
    } else {
      snprintf(row, sizeof(row), "%s,,,,%d", ts, (int)M5.Power.getBatteryLevel());
    }
    chCur->setValue(row);
    chCur->notify();
  }
  if (logRequested) {
    logRequested = false;
    streamLog(logDate);
  }
  delay(100);
}
