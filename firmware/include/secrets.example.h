// 認証情報の雛形。secrets.h にコピーして値を入れる（secrets.h はコミット禁止）
// Wi-Fi は起動時の時刻合わせ（NTP）にのみ使う。未設定でもRTCで動作する。
#pragma once

#define WIFI_SSID "your-ssid"
#define WIFI_PASS "your-password"
