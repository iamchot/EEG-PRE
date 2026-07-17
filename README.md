# Dream Comicverse 🧠🎨

> ระบบต้นแบบสร้างการ์ตูนคอมิกจากสัญญาณคลื่นสมอง (EEG) ด้วย Generative AI  
> **Login:** `admin@dreamcomic.local` / `Admin1234!`

---

## 🚀 วิธีรันระบบ (ทุกครั้งที่เปิดเครื่อง)

### ขั้นตอนที่ 1 — เริ่ม MySQL (Docker)

```powershell
docker-compose up -d
```

> ตรวจสอบ: `docker ps` → ต้องเห็น `dreamcomic_mysql` running

---

### ขั้นตอนที่ 2 — เริ่ม Backend (FastAPI)

เปิด Terminal ใหม่แล้วรัน:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

> ✅ สำเร็จเมื่อเห็น: `Uvicorn running on http://0.0.0.0:8000`  
> 📖 Swagger UI: http://localhost:8000/docs

---

### ขั้นตอนที่ 3 — เริ่ม Frontend (Angular)

เปิด Terminal ใหม่อีกอัน:

```powershell
cd frontend
npm start
```

> ✅ สำเร็จเมื่อเห็น: `Local: http://localhost:4200/`

---

### ขั้นตอนที่ 4 — เปิด ComfyUI (ถ้าจะสร้างการ์ตูน)

```powershell
# เปิด ComfyUI ตามปกติ → http://localhost:8188
# ตรวจสอบว่ามี checkpoint: Counterfeit-V3.0_fix_fp16.safetensors
```

---

## 🔑 Account สำหรับทดสอบ

| Role | Email | Password |
|------|-------|----------|
| Admin | `admin@dreamcomic.local` | `Admin1234!` |
| User | สมัครใหม่ที่ `/register` | — |

---

## 🛠️ ติดตั้งครั้งแรก (ทำครั้งเดียว)

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements_backend.txt

# Seed database (ต้องให้ Docker MySQL รันก่อน)
python seed.py
```

### Frontend

```powershell
cd frontend
$env:PATH = "C:\Users\sirik\AppData\Local\nvm\v24.11.1\;" + $env:PATH
npm install
```

---

## 🩺 แก้ปัญหาที่พบบ่อย

| อาการ | สาเหตุ | วิธีแก้ |
|-------|--------|---------|
| Register/Login ไม่สำเร็จ (0 B transferred) | Backend ไม่รัน | รัน `uvicorn` ตามขั้นที่ 2 |
| `seed.py` crash | MySQL ยังไม่ ready | รอ 10 วิแล้วลองใหม่ |
| "Public Key Retrieval is not allowed" | DB tool ไม่รองรับ MySQL 8 auth | ใช้ connection string ปกติ (ไม่ต้องเพิ่ม parameter) |
| Angular ไม่เจอ `ng` | PATH ของ nvm ไม่ set | เพิ่ม `$env:PATH = "C:\Users\sirik\AppData\Local\nvm\v24.11.1\;" + $env:PATH` |
| Backend ต่อ DB ไม่ได้ | Docker หยุดรัน | `docker-compose up -d` |

---

## 🗂️ โครงสร้างโปรเจกต์

```
EEG-PRE/
├── backend/                    ← FastAPI + Python
│   ├── app/
│   │   ├── main.py             ← Entry point
│   │   ├── config.py           ← Settings (Pydantic)
│   │   ├── models/             ← SQLAlchemy ORM
│   │   ├── schemas/            ← Pydantic Schemas
│   │   ├── routers/            ← API endpoints
│   │   └── services/
│   │       ├── signal_processor.py   ← EEG + FAA/Arousal
│   │       ├── eeg_service.py        ← 10-State Machine
│   │       ├── gemini_service.py     ← Story Generation
│   │       └── diffusion_service.py  ← ComfyUI
│   ├── .env                    ← ใส่ GEMINI_API_KEY ที่นี่
│   └── seed.py                 ← สร้าง tables + admin user
├── frontend/                   ← Angular 19
│   └── src/app/
│       ├── features/
│       │   ├── auth/           ← Login, Register
│       │   ├── dashboard/      ← Dashboard หลัก
│       │   ├── persona/        ← จัดการตัวละคร
│       │   ├── eeg-session/    ← EEG recording flow
│       │   ├── comic-generation/ ← ดูการ์ตูน + Rating
│       │   ├── history/        ← ประวัติผลงาน
│       │   └── admin/          ← Admin panel
│       └── core/
│           ├── services/       ← Auth, EEG WS, Persona, Comic
│           ├── interceptors/   ← JWT auto-attach
│           └── guards/         ← auth / admin / guest
├── docker-compose.yml          ← MySQL 8 via Docker
├── AGENT.md                    ← คู่มือสำหรับ AI agents
├── ui_design_spec.md           ← UI Wireframes ทุกหน้า
└── eeg_collection_protocal.md  ← Protocol เก็บข้อมูล EEG
```

---

## 📡 API Endpoints หลัก

| Method | Endpoint | คำอธิบาย |
|--------|----------|----------|
| POST | `/api/v1/auth/register` | สมัครสมาชิก |
| POST | `/api/v1/auth/login` | Login → JWT |
| GET  | `/api/v1/auth/me` | ข้อมูลผู้ใช้ปัจจุบัน |
| CRUD | `/api/v1/personas` | จัดการตัวละคร |
| POST | `/api/v1/sessions` | เริ่ม EEG Session |
| WS   | `/api/v1/sessions/ws/{id}` | Real-time EEG data |
| POST | `/api/v1/sessions/{id}/confirm-emotion` | ยืนยันอารมณ์ |
| POST | `/api/v1/comics/generate` | สร้างการ์ตูน |
| GET  | `/api/v1/comics` | ประวัติการ์ตูน |
| GET  | `/api/v1/admin/stats` | สถิติ (Admin) |
| GET  | `/docs` | Swagger UI |

---

## 🧠 EEG State Machine

```
DISCOVERING → DEVICE_CONFIRMATION → CONNECTING → PREPARATION → FITTING
→ BASELINE (20s clean) → READY → RECORDING (30s accepted / 120s timeout)
→ PAUSED_SIGNAL_QUALITY (resume เมื่อ good 2s ต่อเนื่อง)
→ EMOTION_CONFIRMATION → COMPLETED
```

## 🎭 Emotion Classification (Rule-based v1.0)

| Emotion | delta_faa | delta_arousal |
|---------|-----------|---------------|
| 😊 Happy | > 0 | > 0 |
| 🎉 Excited | ≤ 0 | > 0 |
| 😢 Sad | > 0 | ≤ 0 |
| 😤 Stressed | ≤ 0 | ≤ 0 |
