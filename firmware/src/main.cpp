// M5Stack CoreS3 + ENV III ミニ気象観測（Phase 1: 取得・表示・SD保存）
// ※ 実機未確認。I2Cピン・SDピンは公式情報に基づく暫定値。
#include <M5Unified.h>
#include <M5UnitENV.h>
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

SHT3X sht3x;
QMP6988 qmp;
static bool sdOk = false;
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
  }
  delay(100);
}
