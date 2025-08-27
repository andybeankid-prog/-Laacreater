# FB Lookalike Audience Tool

這是一個使用 Streamlit 建立的批量 Facebook 類似受眾建立工具。

## 使用方式

### 安裝套件
```bash
pip install -r requirements.txt
```

### 執行
```bash
streamlit run app.py
```

### 設定 Secrets
在專案根目錄建立 `.streamlit/secrets.toml` 檔案，內容如下：
```toml
[secrets]
fb_access_token = "YOUR_FACEBOOK_ACCESS_TOKEN"
```

## GitHub Actions
此專案內建 GitHub Actions workflow，會在 push 時自動檢查 Streamlit 是否可正確執行。
