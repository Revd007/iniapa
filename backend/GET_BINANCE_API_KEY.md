# Cara Mendapatkan Binance Testnet API Key

## Langkah-langkah:

### 1. **Buka Binance Testnet**
   - **Spot Testnet**: https://testnet.binance.vision/
   - **Futures Testnet**: https://testnet.binancefuture.com/

### 2. **Login dengan GitHub atau Email**
   - Klik tombol "Log In" di pojok kanan atas
   - Pilih login dengan GitHub atau buat akun baru

### 3. **Generate API Key**
   - Setelah login, klik **"Generate HMAC_SHA256 Key"** atau **"API Key"**
   - Sistem akan generate:
     - `API Key` (64 karakter huruf & angka)
     - `Secret Key` (64 karakter huruf & angka)
   - **PENTING**: Simpan Secret Key karena hanya ditampilkan sekali!

### 4. **Copy API Keys ke File `.env`**
   - Buka file `backend/.env`
   - Paste API key Anda:

```env
# Binance Testnet API (FREE - No Real Money)
BINANCE_API_KEY=your_64_character_api_key_here
BINANCE_API_SECRET=your_64_character_secret_key_here
BINANCE_TESTNET=true
```

### 5. **Contoh Format yang Benar:**
```env
BINANCE_API_KEY=abc123def456ghi789jkl012mno345pqr678stu901vwx234yz567890abcdef12
BINANCE_API_SECRET=123abc456def789ghi012jkl345mno678pqr901stu234vwx567yz890123abcdef
BINANCE_TESTNET=true
```

---

## ⚠️ **PENTING:**

1. **Testnet = Gratis & Aman**
   - Tidak menggunakan uang asli
   - Untuk testing dan development
   - API Key gratis, unlimited

2. **Jangan Gunakan Production API** (untuk sekarang)
   - Production API butuh KYC verification
   - Menggunakan uang asli
   - Berbahaya jika salah konfigurasi

3. **Jangan Share API Secret Key**
   - Secret key seperti password
   - Jangan commit ke Git
   - Jangan share ke orang lain

---

## 🔧 **Setelah Mendapatkan API Key:**

1. **Update file `backend/.env`**
2. **Restart backend server:**
   ```bash
   cd backend
   # Stop server (Ctrl+C)
   # Start server again
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```
3. **Test order execution** dari frontend

---

## ✅ **Cek Apakah API Key Valid:**

Setelah restart backend, coba execute trade dari frontend. Jika berhasil, Anda akan melihat:
- ✅ Order ID muncul
- ✅ Stop Loss & Take Profit tercatat
- ✅ Log backend: "Order created successfully"

Jika masih error:
- ❌ Cek apakah API key 64 karakter
- ❌ Cek tidak ada spasi atau newline
- ❌ Cek BINANCE_TESTNET=true

---

## 📚 **Link Dokumentasi:**
- Binance Spot Testnet: https://testnet.binance.vision/
- Binance Spot API Docs: https://developers.binance.com/docs/binance-spot-api-docs/
- Binance Futures Testnet: https://testnet.binancefuture.com/

