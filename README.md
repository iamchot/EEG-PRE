# Dream Comicverse

> **หมายเหตุสำคัญ (Product Disclaimer):**  
> ระบบนี้เป็นระบบต้นแบบเพื่อความบันเทิงและการวิจัย (Entertainment & Research Prototype)  
> **ไม่ใช่เครื่องมือหรืออุปกรณ์ทางการแพทย์ (Not a medical device)** และห้ามนำไปใช้ในการตรวจ วินิจฉัย บำบัด หรือรักษาโรคทางการแพทย์  
> ข้อมูลและขั้นตอนการจัดเก็บชุดข้อมูล Muse 2 ให้อ้างอิงตามเอกสาร [`backend/COLLECTION_OPERATIONS.md`](backend/COLLECTION_OPERATIONS.md)

ระบบต้นแบบสร้างการ์ตูนคอมิก 4 ช่องจากสัญญาณคลื่นสมอง (EEG) ด้วย Generative AI (Gemini + ComfyUI) พร้อมระบบจัดเก็บชุดข้อมูลคลื่นสมองมาตรฐานสำหรับการทดลอง (Dataset Collection Protocol) ด้วยชุดอุปกรณ์ Muse 2

---

## บัญชีสำหรับเข้าสู่ระบบ (Single Entry Point)

ระบบใช้หน้า Login เดียวกันที่ `/login` โดยจะตรวจสอบ Role จากฐานข้อมูลและเปลี่ยนเส้นทางอัตโนมัติ:

| Role | Email | Password | เส้นทางหลัง Login | สิทธิ์การใช้งาน |
|------|-------|----------|-------------------|-----------------|
| Admin | `admin@dreamcomic.local` | `Admin1234!` | `/admin` | จัดการผู้ใช้, ดูสถิติระบบ, จัดเก็บชุดข้อมูล (Dataset Collection) |
| User | สมัครใหม่ที่ `/register` | (กำหนดเอง) | `/dashboard` | จัดการตัวละคร (Persona), บันทึกคลื่นสมอง, สร้างการ์ตูนคอมิก |

---

## วิธีรันระบบสำหรับการพัฒนา (Development)

### ขั้นตอนที่ 1 — เริ่มต้นฐานข้อมูล MySQL (Docker)

```powershell
docker-compose up -d
```

> ตรวจสอบสถานะ: `docker ps` ต้องมี container `dreamcomic_mysql` ทำงานอยู่ที่พอร์ต 3306

---

### ขั้นตอนที่ 2 — เริ่มต้น Backend (FastAPI)

**โหมด Development ทั่วไป:**
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
*(หรือรันผ่านสคริปต์ `.\start_backend.ps1`)*

- Backend API: `http://localhost:8000`
- Swagger Interactive Documentation: `http://localhost:8000/docs`

> **คำเตือนสำหรับการจัดเก็บข้อมูลจริง (Active Collection):**  
> ห้ามใช้โหมด `--reload` ขณะบันทึกข้อมูลคลื่นสมอง ให้รันด้วย:  
> `.\start_collection_backend.ps1` (รันแบบ Single Process Worker เพื่อความถูกต้องของสัญญาณ)

---

### ขั้นตอนที่ 3 — เริ่มต้น Frontend (Angular 19)

```powershell
cd frontend
npm start
```

- Web Application: `http://localhost:4200`
- รองรับการสลับภาษาไทย (TH) และอังกฤษ (EN)

---

### ขั้นตอนที่ 4 — เปิดใช้งาน ComfyUI (สำหรับการ Generate ภาพการ์ตูน)

1. เปิดโปรแกรม ComfyUI ตามปกติที่ `http://localhost:8188`
2. ตรวจสอบว่ามี Checkpoint Model: `Counterfeit-V3.0_fix_fp16.safetensors` ในโฟลเดอร์ `models/checkpoints/` ของ ComfyUI

---

## ขั้นตอนการจัดเก็บข้อมูลคลื่นสมอง (Dataset Collection Runner)

ระบบจัดเก็บข้อมูลคลื่นสมองมาตรฐาน Muse 2 สำหรับผู้ดูแลระบบ เข้าใช้งานที่เมนู **Dataset Collection** (`/admin/dataset-collection`):

1. **Step 1: เชื่อมต่อและเตรียมการ (Device & Schedule):**
   - ค้นหาและเชื่อมต่ออุปกรณ์ Muse 2 ผ่าน Bluetooth/LSL
   - ตรวจสอบสถานะการแนบสนิทของเซนเซอร์ 4 จุด (TP9, AF7, AF8, TP10) บน Horseshoe Display
   - ยืนยันการสัมผัสผิว และสร้างตารางสุ่มสิ่งเร้า (Schedule 12 Trials) แบบละ 3 คลิปต่อ 4 สภาวะอารมณ์
2. **Baseline 1: ลืมตาและมองจุดกึ่งกลาง (Eyes Open):**
   - ระยะเวลา 60 วินาที โดยต้องมีสัญญาณสะอาดผ่านเกณฑ์ (Clean signal gate) อย่างน้อย 30 วินาที
3. **Baseline 2: หลับตาและอยู่นิ่ง (Eyes Closed):**
   - ระยะเวลา 60 วินาที โดยต้องมีสัญญาณสะอาดผ่านเกณฑ์อย่างน้อย 30 วินาที
4. **การทดลองสิ่งเร้า 12 Trials (Trial Loop):**
   - **Rest / Fixation (10–15 วินาที):** ผู้เข้าร่วมนั่งพักมองจุดกึ่งกลาง (+) เพื่อปรับสัญญาณให้คงที่
   - **Stimulus Playback:** เล่นวิดีโอคลิปกระตุ้นอารมณ์ที่ผ่านการตรวจสอบ Checksum
   - **Artifact Markers:** Admin บันทึกสิ่งรบกวนสัญญาณแบบ Real-time (กะพริบตาถี่, ไอ, พูด, ขยับศีรษะ, สัมผัสอุปกรณ์, อุปกรณ์หลุด)
   - **Self-Assessment Rating (SAM):** ผู้เข้าร่วมประเมินความรู้สึก (Valence 1–9, Arousal 1–9, Confidence 1–5)
   - **Mid-session Break:** ระบบหยุดพักครึ่งทาง 3–5 นาที หลังจบ Trial ที่ 6
5. **ความปลอดภัยและการกู้คืน (Safety & Recovery):**
   - มีปุ่ม Emergency Stop ขัดจังหวะทันทีเมื่อเกิดเหตุฉุกเฉิน
   - รองรับการ Resume ต่อจาก Step ล่าสุดที่ค้างไว้โดยไม่สูญเสียลำดับ Trial
   - ส่งออกข้อมูลสัญญาณดิบ (CSV) พร้อม Metadata สำหรับนำไปเทรนโมเดล

---

## กระบวนการสร้างการ์ตูนคอมิก (EEG to Comic Flow)

1. **บันทึกคลื่นสมอง (10-State EEG Machine):**
   - `DISCOVERING -> DEVICE_CONFIRMATION -> CONNECTING -> PREPARATION -> FITTING -> BASELINE -> READY -> RECORDING -> PAUSED_SIGNAL_QUALITY -> EMOTION_CONFIRMATION -> COMPLETED`
2. **ประมวลผลและจำแนกอารมณ์ (Emotion Classification Rule-based v1.0):**
   - คำนวณ Frontal Alpha Asymmetry (FAA) จากคู่ช่องสัญญาณ AF7/AF8 และระดับ Arousal จากอัตราส่วนคลื่นสมอง
   
   | อารมณ์ที่ได้ | delta_faa | delta_arousal | คำอธิบาย |
   |-------------|-----------|---------------|----------|
   | Happy | > 0 | > 0 | อารมณ์เชิงบวกและมีความตื่นตัว |
   | Excited | <= 0 | > 0 | ความตื่นเต้นและมีพลัง |
   | Sad | > 0 | <= 0 | ความรู้สึกสงบนิ่งหรือเศร้า |
   | Stressed | <= 0 | <= 0 | ความตึงเครียดหรือกดดัน |

3. **สร้างเนื้อเรื่องด้วย Gemini:**
   - นำ Persona ของตัวละครและอารมณ์ที่วัดได้ไปให้ Gemini 2.0 Flash สร้างบทบรรยายและการกระทำ 4 ช่อง
4. **สร้างภาพการ์ตูนด้วย ComfyUI:**
   - ส่ง Prompt จาก Gemini เข้า ComfyUI API เพื่อ Render ภาพการ์ตูนทีละช่องตามลักษณะตัวละครและอารมณ์

---

## การติดตั้งระบบครั้งแรก (First-time Setup)

### 1. ติดตั้ง Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements_backend.txt

# สร้างไฟล์คอนฟิก .env
Copy-Item .env.example .env
# (แก้ไขค่า SECRET_KEY และ GEMINI_API_KEY ในไฟล์ .env)

# รัน Database Migrations และสร้างข้อมูลเริ่มต้น
alembic upgrade head
python seed.py
```

### 2. ติดตั้ง Frontend

```powershell
cd frontend
npm install
```

---

## โครงสร้างโปรเจกต์ (Project Structure)

```
EEG-PRE/
├── backend/                              - FastAPI Backend Service
│   ├── alembic/                          - Database Schema Migrations
│   ├── app/
│   │   ├── main.py                       - Application Entry Point
│   │   ├── config.py                     - Application Configuration & Settings
│   │   ├── database.py                   - SQLAlchemy Database Engine & Session
│   │   ├── models/                       - Database Models (User, Persona, Comic, Dataset)
│   │   ├── schemas/                      - Pydantic Validation Schemas
│   │   ├── routers/                      - API Endpoints (Auth, Comic, Dataset, Muse, etc.)
│   │   ├── services/                     - Core Business Logic & State Machines
│   │   │   ├── collection_state_machine.py - Muse 2 Dataset Collection State Machine
│   │   │   ├── muse_bridge_manager.py    - Muse Bridge Process & Lease Management
│   │   │   ├── muse_stream.py            - Muse LSL Pull & Ring Buffer
│   │   │   ├── signal_processor.py       - EEG Signal Processing & Bandpower
│   │   │   ├── gemini_service.py         - Gemini Story Prompting
│   │   │   └── diffusion_service.py      - ComfyUI Integration
│   │   └── ws/                           - WebSocket Connection Managers
│   ├── collection_data/                  - บันทึกไฟล์ CSV สัญญาณดิบของ Dataset
│   ├── collection_stimuli/               - วิดีโอสิ่งเร้าสำหรับจัดเก็บ Dataset
│   ├── COLLECTION_OPERATIONS.md          - คู่มือปฏิบัติการเก็บข้อมูล Muse 2
│   ├── start_backend.ps1                 - สคริปต์รัน Backend สำหรับโหมด Dev
│   ├── start_collection_backend.ps1      - สคริปต์รัน Backend สำหรับโหมด Collection
│   └── seed.py                           - สคริปต์สร้างตารางและบัญชี Admin เริ่มต้น
├── frontend/                             - Angular 19 Frontend Web Application
│   └── src/app/
│       ├── core/                         - Core Services, Guards, Interceptors, Pipes
│       │   ├── guards/                   - Auth, Admin, Guest Route Guards
│       │   ├── services/                 - Auth, Muse Device, Dataset Collection, Language
│       │   └── pipes/                    - Translate Pipe (TH/EN)
│       ├── features/                     - Feature Modules & Components
│       │   ├── auth/                     - Login, Register (Single Login Entry)
│       │   ├── dashboard/                - User Dashboard
│       │   ├── persona/                  - Persona Creation & Management
│       │   ├── eeg-session/              - Live EEG Recording Flow
│       │   ├── comic-generation/         - Comic Display, Download, Rating
│       │   ├── history/                  - User Creation History
│       │   ├── admin/                    - Admin Dashboard
│       │   ├── dataset-collection/       - Dataset Collection Overview & Sessions
│       │   └── dataset-collection-runner/ - Dataset Trial Runner & Muse Controls
│       └── shared/                       - Reusable Components (Horseshoe Sensor, Waveform)
├── docker-compose.yml                    - MySQL 8 Container Configuration
└── docs/                                 - ข้อกำหนดและเอกสารการออกแบบ
```

---

## รายการ API Endpoints หลัก

| หมวดหมู่ | Method | Endpoint | คำอธิบาย |
|----------|--------|----------|----------|
| **Auth** | POST | `/api/v1/auth/register` | สมัครสมาชิกผู้ใช้ใหม่ |
| | POST | `/api/v1/auth/login` | เข้าสู่ระบบและรับ JWT Token |
| | GET | `/api/v1/auth/me` | ข้อมูลบัญชีผู้ใช้ปัจจุบัน |
| **Persona** | GET/POST | `/api/v1/personas` | ดึงรายการ / สร้างตัวละคร Persona |
| | PUT/DELETE | `/api/v1/personas/{id}` | แก้ไข / ลบตัวละคร |
| **EEG Session** | POST | `/api/v1/sessions` | เริ่มต้น EEG Recording Session |
| | WS | `/api/v1/sessions/ws/{id}` | WebSocket รับส่งข้อมูล EEG แบบเรียลไทม์ |
| | POST | `/api/v1/sessions/{id}/confirm-emotion` | ยืนยันผลอารมณ์จากคลื่นสมอง |
| **Comic** | POST | `/api/v1/comics/generate` | ส่งคำขอสร้างการ์ตูน 4 ช่อง |
| | GET | `/api/v1/comics` | ประวัติการ์ตูนของผู้ใช้ |
| **Admin** | GET | `/api/v1/admin/stats` | สถิติระบบสำหรับผู้ดูแล |
| **Dataset** | GET/POST | `/api/v1/dataset-collection/sessions` | รายการ / สร้าง Session การเก็บข้อมูล |
| | GET | `/api/v1/dataset-collection/sessions/{id}/runner` | ดึงสถานะปัจจุบันของ Runner |
| | POST | `/api/v1/dataset-collection/sessions/{id}/device` | เลือกอุปกรณ์ Muse |
| | POST | `/api/v1/dataset-collection/sessions/{id}/schedule` | สร้างตารางสุ่มสิ่งเร้า 12 Trials |
| | POST | `/api/v1/dataset-collection/sessions/{id}/baseline` | เริ่มต้น Baseline (Eyes Open / Closed) |
| | POST | `/api/v1/dataset-collection/sessions/{id}/trials/{t_id}/rest` | เริ่มช่วงพักก่อนคลิป |
| | POST | `/api/v1/dataset-collection/sessions/{id}/trials/{t_id}/stimulus/start` | เริ่มบันทึกและเล่นคลิป |
| | POST | `/api/v1/dataset-collection/sessions/{id}/trials/{t_id}/stimulus/finish` | จบการเล่นคลิป |
| | POST | `/api/v1/dataset-collection/sessions/{id}/trials/{t_id}/rating` | บันทึกคะแนน SAM Rating |
| | POST | `/api/v1/dataset-collection/sessions/{id}/interrupt` | ขัดจังหวะฉุกเฉิน (Emergency Stop) |
| | POST | `/api/v1/dataset-collection/sessions/{id}/resume` | ดำเนินการต่อจากจุดเดิม |
| | GET | `/api/v1/dataset-collection/stimuli/{id}/media` | สตรีมวิดีโอคลิปสิ่งเร้า |
| | GET | `/api/v1/dataset-collection/sessions/{id}/export` | ดาวน์โหลดไฟล์ข้อมูลสรุป |
| **Muse** | GET | `/api/v1/muse/scan` | สแกนหาอุปกรณ์ Muse ในบริเวณใกล้เคียง |
| | POST | `/api/v1/muse/connect` | เชื่อมต่ออุปกรณ์ Muse ผ่าน LSL Bridge |

---

## สถาปัตยกรรมและข้อควรระวัง (Architecture & Gotchas)

### Library Compatibility
- **Bcrypt & Passlib:** Pin `bcrypt>=4.0.1,<4.1.0` — `passlib 1.7.4` ไม่ compatible กับ `bcrypt >= 4.1.0` (removed `__about__`)
- **Pydantic Settings:** ตั้ง `extra="ignore"` ใน `SettingsConfigDict` ใน `app/config.py` — ตัวแปรใน `.env` ที่ไม่ได้ declare จะ error
- **EmailStr & Local TLDs:** ใช้ `str` + regex แทน `pydantic.networks.EmailStr` เพื่อรองรับ `.local` / `.dev`
- **MySQL Auth Plugin:** user `dreamcomic` ต้องใช้ `mysql_native_password` — PyMySQL มีปัญหากับ `caching_sha2_password` บน Docker bridge IP; แก้ด้วย:
  ```
  ALTER USER 'dreamcomic'@'%' IDENTIFIED WITH mysql_native_password BY 'dreamcomic_pass';
  FLUSH PRIVILEGES;
  ```

### Angular 19 Auth & State
- **APP_INITIALIZER for Reload Fix:** Route guards รันก่อน `AuthService` fetch `/auth/me` เสร็จ — ต้องมี `APP_INITIALIZER` ใน `app.config.ts` เพื่อ block routing จนกว่า user fetch จะเสร็จ
- **Signal-based EEG State:** ใช้ Angular Signals ใน `EegWsService` — share sensor states ผ่าน `computed()` signals

### EEG Signal Processing Rules
- **ห้าม FFT ข้าม Pause/Resume boundary** — คำนวณ PSD ราย Epoch เสมอ
- **Baseline (User Flow):** สะสม clean signal ≥ 20 วินาที — quality-based accumulation (ไม่ reset เมื่อสัญญาณตก)
- **Baseline (Dataset Collection):** Eyes Open 60s / clean ≥ 30s + Eyes Closed 60s / clean ≥ 30s
- **Recording:** accepted data ≥ 30 วินาที; wall-clock สูงสุด 120 วินาที
- **Emotion Classifier:** Rule-based v1.0 ใช้ `delta_faa` และ `delta_arousal` — ยังไม่มี ML model

### Muse 2 / Web Bluetooth
- อัตราการรับข้อมูล: ~22 Hz (browser average 12 samples ต่อ packet ทุก ~45 ms)
- ข้อมูล EEG ดิบเก็บใน `backend/collection_data/{participant}/{session_id}/{trial}.csv`
- DB เก็บเฉพาะ path + SHA-256 checksum + metadata

---

## ไฟล์สำคัญ (Key Files)

| ไฟล์ | หน้าที่ |
|------|--------|
| `backend/app/config.py` | Pydantic Settings — ต้องมี `extra="ignore"` |
| `backend/app/services/signal_processor.py` | EEG Epoch, FFT, FAA, Arousal index |
| `backend/app/services/eeg_service.py` | 10-state machine สำหรับ User EEG Session |
| `backend/app/services/collection_state_machine.py` | State machine สำหรับ Dataset Collection |
| `backend/app/services/raw_eeg_writer.py` | Atomic CSV writer (partial → sha256 → rename) |
| `backend/app/services/muse_bridge_manager.py` | BLE scan, muselsl bridge, LSL verification |
| `backend/app/services/gemini_service.py` | Story prompt → 4-panel dialogue |
| `backend/app/services/diffusion_service.py` | ComfyUI polling → comic panel images |
| `frontend/src/app/app.config.ts` | APP_INITIALIZER สำหรับ auth persistence |
| `frontend/src/app/core/guards/auth.guard.ts` | authGuard / adminGuard / guestGuard |
| `frontend/src/app/shared/components/horseshoe-sensor/` | Muse 2 sensor status UI |

---

## Route Map

| Route | Guard | Component |
|-------|-------|-----------|
| `/login` | guestGuard | LoginComponent |
| `/register` | guestGuard | RegisterComponent |
| `/dashboard` | authGuard | DashboardComponent |
| `/eeg-session` | authGuard | EegSessionComponent |
| `/comic/:id` | authGuard | ComicViewComponent |
| `/history` | authGuard | HistoryComponent |
| `/admin` | authGuard + adminGuard | AdminComponent |
| `/admin/dataset-collection` | authGuard + adminGuard | DatasetCollectionComponent |
| `/admin/dataset-collection/:id/runner` | authGuard + adminGuard | DatasetCollectionRunnerComponent |

---

## Pre-Change Checklist (สำหรับนักพัฒนา)

1. MySQL Docker container รัน: `docker ps` — ต้องมี `dreamcomic_mysql` ที่ port 3306
2. Node version: `node --version` → v24.x
3. `GEMINI_API_KEY` set ใน `backend/.env`
4. `bcrypt` pinned ที่ `>=4.0.1,<4.1.0` ใน `requirements_backend.txt`
5. ห้ามรัน `--reload` ขณะ Active Collection

---

## การแก้ปัญหาที่พบบ่อย (Troubleshooting)

| อาการที่พบ | สาเหตุที่เป็นไปได้ | แนวทางแก้ไข |
|------------|-------------------|-------------|
| เข้าสู่ระบบหรือสมัครสมาชิกไม่สำเร็จ | Backend ไม่ได้ทำงาน | ตรวจสอบการรัน Uvicorn ใน Terminal Backend |
| Backend เชื่อมต่อ Database ไม่ได้ | Docker Container หยุดทำงาน | รันคำสั่ง `docker-compose up -d` และตรวจพอร์ต 3306 |
| `seed.py` แจ้งเตือนข้อผิดพลาด | MySQL ยังเริ่มต้นระบบไม่เสร็จ | รอประมาณ 10–15 วินาทีให้ MySQL พร้อมทำงานแล้วรันใหม่ |
| ไม่พบคลิปวิดีโอใน Dataset Collection | ยังไม่ได้วางไฟล์หรือคำนวณ Checksum | วางไฟล์วิดีโอใน `backend/collection_stimuli/` และตรวจสอบฟิลด์ `checksum` ในตาราง `emotion_stimuli` |
| Muse ไม่แสดงในรายการค้นหา | Bluetooth ปิดอยู่ หรือ Muse ดับ | เปิด Bluetooth บนเครื่องคอมพิวเตอร์ และกดปุ่มเปิดที่แถบคาดศีรษะ Muse 2 |
| สัญญาณเซนเซอร์ขึ้นสีแดง (ไม่ถึง 100%) | เซนเซอร์ยังไม่แนบสนิทกับผิว | ขยับตำแหน่งแถบคาดศีรษะให้สัมผัสผิวหน้าผากและหลังใบหูโดยไม่มีเส้นผมคั่น |
| คอมิกไม่ขึ้นรูปภาพ | ComfyUI ไม่ได้เปิด หรือไม่มี Checkpoint | ตรวจสอบว่า ComfyUI รันอยู่ที่พอร์ต 8188 และมีโมเดล `Counterfeit-V3.0_fix_fp16.safetensors` |
