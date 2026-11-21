# firmware

CoreS3 + ENV III のファームウェア（PlatformIO / Arduino framework / M5Unified）。

> 状態: ビルド成功のみ確認。**実機未確認**（I2Cピン・SDピンは暫定）。

## 機能（Phase 1）

- 1分ごとに温度・湿度・気圧を読み取り、画面とシリアルに表示
- SDカードに `/YYYYMMDD.csv` として追記（[データ仕様](../docs/data_format.md)）。読み取り失敗時は値を空欄で行を残す
- 時刻: 起動時にRTCから復元。無効ならWi-Fi+NTPで同期してRTCへ保存し、Wi-Fiを切る

- BLE（NimBLE）: 現在値の通知と、日単位のログ取得（`DATE,YYYYMMDD`）。仕様は [data_format.md](../docs/data_format.md)

## 準備（macOS）

```bash
cd firmware
python3 -m venv ../.venv && ../.venv/bin/pip install platformio   # 初回のみ
cp include/secrets.example.h include/secrets.h                     # 任意（NTP用Wi-Fi。コミット禁止）
../.venv/bin/pio run                    # ビルド（初回はツールチェーン取得で10分超・約5GB）
../.venv/bin/pio run -t upload          # 書き込み（実機接続後）
../.venv/bin/pio device monitor         # シリアル確認
```

書き込みで認識されない場合は、リセットボタン長押しでブートモードにする。

## 実機が来たら最初に確認すること

1. I2Cスキャンで 0x44（SHT30）・0x70（QMP6988）が見えるか
2. `M5.Ex_I2C.getSDA()/getSCL()` でENV IIIが読めるか（読めなければ SDA=2, SCL=1 を直指定）
3. SDカード（FAT32）への書き込み・ピン（SCK36/MISO35/MOSI37/CS4）
4. 温度の自己加熱（本体を離したときとの差）
5. BLE: nRF Connect で `M5MiniWeather` が見え、Current が1分ごとに通知されるか。次に `web/index.html`（Bluefy）でログ取得
