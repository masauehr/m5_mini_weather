# m5_mini_weather

> 詳しくは [docs/manual.md](docs/manual.md) を参照。

M5Stack **CoreS3** と **ENV III** センサーで作る、ミニ気象観測所。
気温・湿度・気圧を測り、**スマホへ転送**して**データ解析**に使う。まずは**移動式（持ち歩き）**で測り、将来**防水仕様**の固定観測機に拡張する。

> 状態: Phase 1〜3 のコードを実装（ファームはビルド成功、解析はダミーデータで動作確認）。**実機・実測データは未確認**（実機待ち）。
> 計画の詳細は [plan.md](plan.md)、機材は [docs/hardware.md](docs/hardware.md) を参照。

## 目的

1. まず **データ取得** を確実に実現する（CoreS3 + ENV III → SD保存 + スマホ転送）
2. 取得データを **解析** する（気圧変化・日変化・気象庁/AMeDAS との比較）
3. 将来、**防水・日射遮蔽** を施した屋外設置機へ拡張する

## 構成（予定）

```text
CoreS3 + ENV III ──(BLE)──▶ スマホ ──▶ CSV ──▶ 解析（Python）
        │
        └─ SDカード（1分ごとにCSV保存・転送が切れても欠測しない）
```

| ディレクトリ / ファイル | 内容 |
|---|---|
| [plan.md](plan.md) | フェーズ別ロードマップ・完了条件 |
| [docs/hardware.md](docs/hardware.md) | 機材・配線・I2Cアドレス・ライブラリ |
| [docs/data_format.md](docs/data_format.md) | 測定値・CSV・BLEの仕様 |
| [docs/portable.md](docs/portable.md) | 移動式（持ち歩き）運用の注意と課題（最初の運用形態） |
| [docs/waterproof.md](docs/waterproof.md) | 防水・日射対策の設計メモ（将来の固定設置用） |
| [docs/references.md](docs/references.md) | 参考記事・公式資料 |
| `firmware/` | CoreS3 のファームウェア（PlatformIO。取得・SD保存・BLE） |
| `web/` | iPhone（Bluefy）用のBLE受信ページ。公開URL: <https://masauehr.github.io/m5_mini_weather/web/> |
| `analysis/` | 解析スクリプト（品質チェック・日別統計・グラフ。ダミーデータで動作確認済み） |
| `data/` | 実測データ置き場（**git除外**） |

## 参考

- note「『いま、ここ』の天気を測る——第2層ポータブル気象観測所をつくっています」（M5Stack Core2 + BLE + SD の構成例）
- IIJ Engineers Blog「水田センサーを簡易百葉箱で気温センサーにしてみた」（日射対策・屋外設置の知見）

詳細は [docs/references.md](docs/references.md)。

## 方針

- 実測データ・位置情報は公開しない（`data/` は `.gitignore`）。自宅位置が特定できる記録をコミットしない。
- 外部サービスのキー・Wi-Fiパスワードは `.env` / `secrets.h`（コミット禁止）に分離。
- 気圧変化などの判定基準は暫定値として扱い、**医療・防災の判断には使わない**。

## ライセンス

未設定（決定したら LICENSE を追加する）。
