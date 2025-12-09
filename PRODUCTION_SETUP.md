# Production Setup Guide

## Masalah yang Ditemukan

Website production di `https://tradanalisa.dutatravel.net/` masih menggunakan `http://localhost:8743` untuk API calls karena environment variable `NEXT_PUBLIC_API_URL` tidak diset dengan benar saat build.

## Solusi

### 1. Setup Environment Variables di Coolify Dashboard

#### Untuk Frontend Service:

**Build Arguments (Build Time):**
```
NEXT_PUBLIC_API_URL=https://api.tradanalisa.dutatravel.net
NODE_ENV=production
```

**Environment Variables (Runtime):**
```
NODE_ENV=production
PORT=5237
```

**PENTING:** 
- `NEXT_PUBLIC_API_URL` HARUS diset sebagai **Build Argument** (bukan runtime env var)
- Next.js membutuhkan `NEXT_PUBLIC_*` variables saat **build time**, bukan runtime
- URL harus menggunakan HTTPS untuk production: `https://api.tradanalisa.dutatravel.net`

#### Untuk Backend Service:

**Environment Variables:**
```
DATABASE_URL=postgresql://user:pass@host:5432/dbname
NODE_ENV=production
OPENROUTER_API_KEY=sk-or-v1-...
BINANCE_DEMO_API_KEY=...
BINANCE_DEMO_API_SECRET=...
SECRET_KEY=...
```

### 2. CORS Configuration

Backend sudah dikonfigurasi untuk mengizinkan:
- `https://tradanalisa.dutatravel.net`
- `https://www.tradanalisa.dutatravel.net`
- Localhost untuk development

Jika backend di domain berbeda, tambahkan domain backend ke CORS di `backend/main.py`:

```python
allow_origins=[
    "https://tradanalisa.dutatravel.net",
    "https://www.tradanalisa.dutatravel.net",
    "https://api.tradanalisa.dutatravel.net",  # Jika backend di subdomain
    # ... lainnya
]
```

### 3. Setup di Coolify Dashboard

#### Frontend Service:
1. **Build Settings:**
   - Dockerfile Path: `frontend/Dockerfile`
   - Build Context: `frontend/`
   - **Build Arguments:**
     - `NEXT_PUBLIC_API_URL=https://api.tradanalisa.dutatravel.net` ⚠️ PENTING!
     - `NODE_ENV=production`

2. **Port:** `5237`

#### Backend Service:
1. **Build Settings:**
   - Dockerfile Path: `backend/Dockerfile`
   - Build Context: `backend/`
   
2. **Port:** `8743`

3. **Environment Variables:** (semua backend env vars)

### 4. Verifikasi Setup

Setelah deploy, cek di browser console:
- ✅ Tidak ada error CORS
- ✅ API calls menggunakan URL production (bukan localhost)
- ✅ Data loading dengan benar

### 5. Troubleshooting

#### Masalah: API calls masih ke localhost
**Solusi:** Pastikan `NEXT_PUBLIC_API_URL` diset sebagai **Build Argument**, bukan runtime environment variable. Rebuild frontend setelah set.

#### Masalah: CORS error
**Solusi:** 
1. Pastikan domain frontend sudah ditambahkan ke `allow_origins` di backend
2. Restart backend setelah perubahan CORS
3. Cek apakah backend accessible dari frontend domain

#### Masalah: 404 untuk static files
**Solusi:** Pastikan Next.js build menggunakan `output: 'standalone'` di `next.config.js`

## Quick Checklist

- [ ] `NEXT_PUBLIC_API_URL` diset sebagai Build Argument di Coolify
- [ ] URL menggunakan HTTPS untuk production
- [ ] Backend CORS mengizinkan domain production
- [ ] Backend accessible dari frontend domain
- [ ] Rebuild frontend setelah set environment variables
- [ ] Restart backend setelah perubahan CORS
- [ ] Test di browser console - tidak ada error

