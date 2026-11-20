# CLAUDE.md — m5_mini_weather

M5Stack CoreS3 + ENV III のミニ気象観測 → スマホ転送 → 解析。GitHub **公開**リポジトリ。

## ルール

- 日本語で会話・コメント記述。インデントは C++/JS: スペース2、Python: スペース4。
- 実測データ（`data/`）、Wi-Fi/APIの認証情報、設置場所が分かる情報は **コミット禁止**。
- 認証情報は `secrets.h` / `.env`（`.gitignore` 済み）に分離し、`secrets.example.h` を雛形として置く。
- フェーズ順（取得 → 転送 → 解析 → 防水）を守る。範囲外の機能を先取りしない。plan.md を更新しながら進める。
- 仕様を決めたら [docs/data_format.md](docs/data_format.md) を更新する。
- 気圧変化などの判定は暫定値。医療・防災の判断用途として書かない。
- 変更したら `git add` → `git commit` → `git push`。あわせて `~/projects/pc_docs/manuals/automation/m5_mini_weather.md` と、リポジトリ内のコピー（`docs/manual.md`）を更新する。

## 構成

- `firmware/` ファームウェア（PlatformIO or Arduino、M5Unified）
- `analysis/` Python 解析（Phase 3）
- `docs/` 機材・データ仕様・防水・参考資料
