# AgentRouter Qwen Setup Guide

## Masalah
AI recommendation tidak bisa konek ke AgentRouter Qwen CLI.

## Solusi

### 1. Environment Variables

Tambahkan ke file `.env` di folder `backend/`:

```bash
# AgentRouter Fallback Settings (untuk Qwen)
AGENTROUTER_API_KEY=your_agentrouter_api_key_here
AGENTROUTER_BASE_URL=https://agentrouter.org/v1
AGENTROUTER_MODEL=qwen
```

**Atau** jika sudah punya `OPENAI_API_KEY`:
```bash
OPENAI_API_KEY=your_agentrouter_api_key_here
OPENAI_BASE_URL=https://agentrouter.org/v1
OPENAI_MODEL=qwen
```

### 2. Model Options untuk AgentRouter

AgentRouter mendukung model berikut:
- `qwen` - Qwen model (recommended, default sekarang)
- `qwen/qwen-code` - Qwen code model
- `qwen/qwen-max` - Qwen max model
- `deepseek-v3.1` - DeepSeek v3.1
- `deepseek-v3.2` - DeepSeek v3.2
- `gpt-5` - GPT-5 (jika tersedia)

**Default sekarang:** `qwen` (untuk konsistensi dengan OpenRouter)

### 3. Cara Mendapatkan API Key

1. Kunjungi https://agentrouter.org/console/token
2. Login atau daftar akun
3. Generate API key baru
4. Copy API key dan paste ke environment variable

### 4. Verifikasi Setup

Setelah set environment variables, restart backend dan cek log:

```
✅ AgentRouter fallback configured and ready!
   API Key: sk-xxx... (length: XX)
   Base URL: https://agentrouter.org/v1
   Model: qwen
   → Will be used automatically when OpenRouter fails
```

### 5. Testing

Untuk test AgentRouter langsung (bypass OpenRouter), set:
```bash
OPENROUTER_API_KEY=""  # Kosongkan untuk force fallback
```

Atau test via API:
```bash
curl -X GET "http://localhost:8743/api/ai/recommendations?mode=normal&asset_class=crypto&limit=6&ai_model=qwen"
```

### 6. Troubleshooting

#### Error: "AgentRouter API key not configured"
**Solusi:** Pastikan `AGENTROUTER_API_KEY` atau `OPENAI_API_KEY` sudah di-set di `.env`

#### Error: "HTTP 401" atau "HTTP 403"
**Solusi:** 
- Cek apakah API key valid
- Pastikan API key tidak expired
- Generate API key baru di https://agentrouter.org/console/token

#### Error: "Model not found" atau "Invalid model"
**Solusi:**
- Pastikan model name benar: `qwen`, `qwen/qwen-code`, atau `qwen/qwen-max`
- Cek dokumentasi AgentRouter untuk model yang tersedia

#### Error: "Failed to parse JSON"
**Solusi:**
- Cek log untuk melihat response dari AgentRouter
- Pastikan model mendukung format JSON yang diharapkan
- Coba model lain seperti `deepseek-v3.2`

### 7. Logging

Sistem sekarang memiliki logging yang lebih detail:
- ✅ Log saat AgentRouter dipanggil
- ✅ Log model yang digunakan
- ✅ Log response status
- ✅ Log error detail jika gagal

Cek log backend untuk melihat detail koneksi AgentRouter.

### 8. Default Configuration

Sekarang default model adalah `qwen` (bukan `deepseek-v3.2` lagi) untuk konsistensi dengan OpenRouter.

Jika ingin menggunakan model lain, set `AGENTROUTER_MODEL` di `.env`:
```bash
AGENTROUTER_MODEL=deepseek-v3.2  # atau model lain
```

