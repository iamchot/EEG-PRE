# Product Requirements Document (PRD)

**ชื่อโครงการ:** Dream Comicverse (การพัฒนาต้นแบบการสร้างการ์ตูนคอมิกจากสัญญาณคลื่นสมองด้วยการเรียนรู้ของเครื่อง)  
**ผู้พัฒนา:** นายพร้อมพงศ์ รังสรรค์ปรีชา  
**แพลตฟอร์ม:** Web Application  
**เวอร์ชันเอกสาร:** 3.0 (ปรับปรุงให้ตรงกับ implementation จริง)  
**วันที่ปรับปรุง:** 28 ตุลาคม 2569

---

## 1. ภาพรวมผลิตภัณฑ์ (Product Overview)

ระบบต้นแบบเว็บแอปพลิเคชันที่ผสานเทคโนโลยีส่วนต่อประสานสมอง-คอมพิวเตอร์ (BCI) ร่วมกับปัญญาประดิษฐ์เชิงสร้างสรรค์ (Generative AI) เพื่อช่วยเหลือผู้ใช้งานทั่วไปให้สามารถถ่ายทอดจินตนาการและสร้างสรรค์ผลงานการ์ตูนคอมิกความยาว 4 ช่องจบได้ ระบบวิเคราะห์สภาวะอารมณ์จากคลื่นสมอง EEG และนำผลลัพธ์ไปควบคุมทิศทางเนื้อเรื่อง โทนสี และบรรยากาศของการ์ตูน

> **ข้อจำกัดสำคัญ:** ระบบนี้เป็น **Entertainment & Research Prototype** เท่านั้น ไม่ใช่เครื่องมือทางการแพทย์ ผลการวิเคราะห์อารมณ์เป็นการประมาณเพื่อการสร้างสรรค์ ไม่ใช่การวินิจฉัยทางคลินิก

---

## 2. วัตถุประสงค์ (Objectives)

- พัฒนาโมดูลเชื่อมต่อและประมวลผลสัญญาณคลื่นสมองจาก Muse 2 เพื่อจำแนกสภาวะอารมณ์
- สร้างกระบวนการแปลงค่าอารมณ์เป็นชุดคำสั่ง (Prompt) สำหรับควบคุม Gemini + ComfyUI
- จัดเก็บชุดข้อมูล EEG มาตรฐาน (Dataset Collection) เพื่อนำไปฝึก ML Classifier ในอนาคต
- ประเมินประสิทธิภาพความแม่นยำของระบบและความพึงพอใจด้านการใช้งาน

---

## 3. สถาปัตยกรรมและเทคโนโลยี (System Architecture & Tech Stack)

| ส่วน | เทคโนโลยี |
|------|-----------|
| Frontend | Angular 19 (Standalone Components, Signals, RxJS) |
| Backend | Python 3.x + FastAPI + SQLAlchemy 2 |
| Database | MySQL 8.0 (via Docker) |
| Auth | JWT (JSON Web Token) — Access + Refresh Token |
| Hardware | Muse 2 Headband → Bluetooth LE → muselsl bridge → LSL stream |
| EEG Processing | FastAPI backend: Signal Quality, Artifact Rejection, FFT/PSD, Feature Extraction |
| Story Generation | Gemini 2.0 Flash API |
| Image Generation | ComfyUI + Stable Diffusion (Counterfeit-V3.0) |

**Cloud Boundary:** ส่งขึ้น Cloud เฉพาะ Final Emotion, Persona, Story และ Prompt เท่านั้น — ไม่สตรีม Raw EEG ไป Cloud

---

## 4. โครงสร้างระบบ (System Modules)

ระบบแบ่งออกเป็น 2 โหมดหลัก:

### 4.1 โหมดสร้างการ์ตูน (User Comic Flow)
ผู้ใช้ทั่วไป → เชื่อมต่อ Muse 2 → Baseline → Record → จำแนกอารมณ์ → สร้างการ์ตูน

### 4.2 โหมดเก็บข้อมูลวิจัย (Admin Dataset Collection)
ผู้ดูแลระบบ → เก็บ EEG ตาม Protocol มาตรฐาน → Raw CSV → label → train ML

---

## 5. ข้อกำหนดด้านฟังก์ชันการทำงาน (Functional Requirements)

### 5.1 ระบบจัดการผู้ใช้งานและความปลอดภัย

- Single Login Entry Point ที่ `/login` แยก Role อัตโนมัติ (User → `/dashboard`, Admin → `/admin`)
- JWT Authentication สำหรับทุก API endpoint
- ระบบสร้างและแก้ไข Persona ตัวละคร

### 5.2 ระบบเตรียมความพร้อมก่อนวัดสัญญาณ (Onboarding & Sensor Check)

- **BLE Scan & Device Selection:** ค้นหา Muse 2 ผ่าน Windows BLE ผ่าน ManagedMuseBridgeManager — ผู้ใช้ต้องเลือกและยืนยันก่อนเชื่อมต่อ
- **Horseshoe UI:** แสดงสถานะ TP9, AF7, AF8, TP10 แยกรายจุด พร้อมสถานะ `unknown`/`poor`/`good`/`stale` — ต้องมีไอคอนและข้อความร่วมกับสีเสมอ
- **Hair & Skin Preparation:** แสดงคำแนะนำตามประเภทผม (สั้น/ยาว) ก่อนเริ่มวัด
- **Readiness Gate:** เริ่ม Baseline ได้เมื่อเซนเซอร์ทั้ง 4 จุดเป็น `good` เท่านั้น

### 5.3 EEG Baseline (User Comic Flow)

> **หมายเหตุ:** User Comic Flow ใช้ Baseline แบบ Single Phase

- เก็บ Resting-state Baseline ต่อเนื่อง โดยต้องสะสม **clean signal ≥ 20 วินาที** (wall-clock สูงสุด 120 วินาที)
- คำนวณ: `baseline_faa`, `baseline_arousal`, `baseline_log_alpha`, `baseline_log_beta`
- หากพบ Artifact ให้ Reject epoch นั้น แต่ไม่ Reset counter ทั้งหมด (quality-based accumulation)

### 5.4 EEG Recording (User Comic Flow)

- เริ่ม Recording ได้หลัง Baseline สำเร็จและเซนเซอร์ครบ `good`
- สะสม **accepted clean data ≥ 30 วินาที** (wall-clock สูงสุด 120 วินาที)
- สัญญาณตก → `PAUSED_SIGNAL_QUALITY` → หยุดนับ → กลับ `good` ครบ 4 จุดต่อเนื่อง 2 วินาที → Resume
- ห้าม FFT ข้าม Pause/Resume boundary — คำนวณ PSD ราย Epoch 2 วินาที ซ้อนทับ 50%

### 5.5 Emotion Classification (Rule-based v1.0)

> **ปัจจุบัน:** ระบบใช้ Rule-based threshold v1.0 — ML Classifier ยังไม่ implement รอชุดข้อมูลจาก Dataset Collection ก่อน

```
FAA  = ln(α_AF8) − ln(α_AF7)
delta_faa     = FAA_recording − FAA_baseline
delta_arousal = Arousal_recording − Arousal_baseline

delta_faa > 0  + delta_arousal > 0  → Happy
delta_faa > 0  + delta_arousal ≤ 0  → Sad
delta_faa ≤ 0  + delta_arousal > 0  → Excited
delta_faa ≤ 0  + delta_arousal ≤ 0  → Stressed
```

ผู้ใช้ยืนยันหรือวัดใหม่ก่อนสร้างการ์ตูน

### 5.6 ระบบสร้างภาพการ์ตูน (Comic Generation)

1. Gemini 2.0 Flash สร้างบทสนทนา 4 ช่อง จาก Persona + Emotion + Story Prompt
2. ComfyUI Render ภาพการ์ตูนทีละ Panel ตาม Art Style ที่เลือก (Manga / Webtoon / Comic / American Comic)
3. แสดงผลพร้อมระบบ Rating ความพึงพอใจ (1–5 ดาว)

### 5.7 Admin Dataset Collection Protocol

Admin ใช้ `/admin/dataset-collection` เก็บข้อมูล EEG มาตรฐาน:

#### Baseline Protocol (2 Phase)
- **Eyes Open Baseline:** wall-clock 60 วินาที / ต้องสะสม clean signal ≥ **30 วินาที**
- **Eyes Closed Baseline:** wall-clock 60 วินาที / ต้องสะสม clean signal ≥ **30 วินาที**
- ผ่านด้วย quality-based accumulation — ไม่ Reset counter เมื่อสัญญาณตกชั่วคราว

#### Trial Protocol (12 Trials ต่อคน)
- 3 คลิปต่ออารมณ์ × 4 อารมณ์ = 12 Trials
- แต่ละ Trial: Rest/Fixation (10–15 วิ) → Stimulus Playback (45–60 วิ) → SAM Rating
- SAM Rating: Valence 1–9, Arousal 1–9, Confidence 1–5
- พักครึ่งทาง 3–5 นาที หลัง Trial ที่ 6

#### Label Derivation
```
valence ≤ 4 → label = "negative" (0)
valence = 5 → label = NULL (ตัดทิ้ง — ก้ำกึ่ง)
valence ≥ 6 → label = "positive" (1)

arousal ≤ 4 → label = "low" (0)
arousal = 5 → label = NULL
arousal ≥ 6 → label = "high" (1)

valid_label = True  ถ้า confidence ≥ 3  AND  rating ≠ 5
```

#### Raw EEG File Storage
```
backend/collection_data/{participant_code}/{session_id}/{capture_id}.csv
```
- เขียนแบบ Atomic: `.partial` ก่อน → sha256 → `os.replace` → `.csv`
- DB เก็บเฉพาะ: `eeg_file_path`, `eeg_checksum`, `raw_size_bytes`, `accepted_clean_seconds`

### 5.8 Admin Panel

- **Dashboard:** สถิติผู้ใช้, อารมณ์ distribution, กิจกรรมระบบ
- **User Management:** ระงับ/เปิด/ลบผู้ใช้
- **Dataset Collection:** ดู, จัดการ, Export ข้อมูล EEG Dataset

---

## 6. EEG State Machine (User Comic Flow)

```
DISCOVERING
  → DEVICE_CONFIRMATION
  → CONNECTING
  → PREPARATION
  → FITTING
  → BASELINE
  → READY
  → RECORDING  ←→  PAUSED_SIGNAL_QUALITY
  → EMOTION_CONFIRMATION
  → COMPLETED
```

สถานะผิดปกติ: `DISCONNECTED`, `TIMEOUT`, `CANCELLED`, `FAILED`

**กติกาหลัก:**
1. Baseline: quality-based accumulation — reject artifact epoch แต่ไม่ reset counter
2. Recording สัญญาณตก → PAUSED; กลับ good ครบ 4 จุด × 2 วินาที → Resume
3. Wall-clock เกิน 120 วินาที ยังไม่ครบ → TIMEOUT → วัดใหม่
4. ห้าม FFT ข้าม Pause/Resume boundary

---

## 7. WebSocket API (Real-time EEG)

- **Protocol:** WebSocket — Backend เป็น Source of Truth ทั้งหมด
- **Path:** `/api/v1/sessions/ws/{session_id}` (User) / `/api/v1/dataset-collection/sessions/{id}/ws` (Admin)
- **ทุกข้อความต้องมี:** `session_id`, `phase`, `sequence`, `timestamp`, device state, sensor states (4 จุด), `quality_score`, `accepted_seconds`, `wall_clock_seconds`, `ready`
- ป้องกันข้อความเก่าด้วย `sequence`
- ห้าม Frontend คำนวณ Quality Score หรือ Phase เอง

---

## 8. Acceptance Criteria หลัก

| ID | Criteria |
|----|----------|
| AC-EEG-01 | ไม่เชื่อมต่อ Muse จนผู้ใช้เลือกและยืนยันอุปกรณ์ |
| AC-EEG-02 | Horseshoe UI แสดง TP9/AF7/AF8/TP10 ถูกตำแหน่ง ไม่ใช้สีอย่างเดียว |
| AC-EEG-03 | เริ่ม Baseline/Recording ได้เมื่อทั้ง 4 จุดเป็น `good` เท่านั้น |
| AC-EEG-04 | Baseline (User): สะสม clean ≥ 20 วินาที — quality-based |
| AC-EEG-04b | Baseline (Dataset): สะสม clean ≥ 30 วินาที ต่อ phase × 2 phases |
| AC-EEG-05 | Recording สะสม accepted data ≥ 30 วินาที — ช่วงที่ไม่ผ่านไม่นับ |
| AC-EEG-06 | หลัง Pause ต้อง good ครบ 4 จุดต่อเนื่อง 2 วินาทีก่อน Resume |
| AC-EEG-07 | Timeout เมื่อ wall-clock เกิน 120 วินาที |
| AC-EEG-08 | PSD คำนวณ Epoch 2 วินาที ซ้อนทับ 50% ไม่ข้าม Pause/Resume |
| AC-EEG-09 | ข้อมูลหมดอายุ → `stale`; Device หลุด → `disconnected` |
| AC-EEG-10 | ผลอารมณ์ระบุ Rule version, Feature version และค่าเทียบ Baseline |
| AC-DS-01 | ผู้เข้าร่วมมี pseudonymous code (P001, P002, ...) — ห้ามใส่ชื่อในไฟล์ EEG |
| AC-DS-02 | Baseline Eyes Open + Eyes Closed ครบทั้งสอง phase ก่อนเริ่ม Trial |
| AC-DS-03 | Raw EEG files เขียน Atomic (partial → sha256 → rename) |
| AC-DS-04 | valid_label = True เมื่อ confidence ≥ 3 และ rating ≠ 5 เท่านั้น |

---

## 9. ข้อกำหนดด้านการจัดเก็บข้อมูล (Data Management)

### ข้อมูลที่เก็บใน Database (ไม่มี Raw EEG ในตาราง)

**ตาราง `eeg_sessions` (User Comic):**
- `device_id`, `device_name`, `baseline_duration`, `accepted_recording_duration`
- `wall_clock_duration`, `rejected_epoch_count`, `pause_count`, `raw_data_path`

**ตาราง `eeg_features` (User Comic):**
- `baseline_log_alpha_af7/af8`, `baseline_log_beta_af7/af8`, `baseline_faa`, `baseline_arousal`
- `recording_faa`, `recording_arousal`, `delta_faa`, `delta_arousal`

**ตาราง `emotion_results` (User Comic):**
- `final_emotion` (happy/sad/stressed/excited), `rule_version`, `valence`, `arousal`
- `quality_score_avg`, `accepted_epochs`, `rejected_epochs`

**ตาราง `collection_sessions` (Dataset):**
- `eyes_open_baseline_path`, `eyes_open_baseline_checksum`
- `eyes_open_accepted_clean_seconds`, `eyes_open_wall_clock_seconds`
- (เช่นเดียวกันสำหรับ eyes_closed)

**ตาราง `collection_trials` (Dataset):**
- `eeg_file_path`, `eeg_checksum`, `raw_size_bytes`
- `valence_rating`, `arousal_rating`, `confidence`
- `valence_label` (bool/NULL), `arousal_label` (bool/NULL)
- `valid_valence_label`, `valid_arousal_label`
- `accepted_clean_seconds`, `wall_clock_seconds`

---

## 10. ข้อกำหนดวิธีจำแนกอารมณ์และ ML Pipeline

### 10.1 สถานะปัจจุบัน: Rule-based Classifier v1.0

ระบบ Production ปัจจุบันใช้ Rule-based threshold ตาม `delta_faa` และ `delta_arousal` เทียบ Baseline ยังไม่มี ML Classifier รอชุดข้อมูลจาก Dataset Collection

### 10.2 แผน ML Pipeline (อนาคต)

เมื่อเก็บข้อมูลครบ:

1. Filter 1–40 Hz + Notch 50 Hz
2. Epoch 2 วินาที ซ้อนทับ 50% — ไม่ข้าม Trial/Pause boundary
3. Feature: Absolute/Relative Alpha/Beta (4 channels), FAA, Arousal Index
4. แบ่ง Fold ตาม `participant_id` (GroupKFold หรือ LOSO)
5. เปรียบเทียบ: Logistic Regression, SVM, Random Forest
6. เลือกจาก Macro F1 + per-class Precision/Recall/F1 + Confusion Matrix
7. บันทึก: preprocessor + classifier + feature_order + label_mapping + version เป็น Artifact เดียว

**กติกา:** ห้ามให้ Epoch ของบุคคลเดียวกันอยู่ทั้ง Train และ Test

### 10.3 Dataset Target

| รายการ | เป้าหมาย |
|--------|----------|
| กลุ่มนำร่อง | 5 คน |
| กลุ่มหลัก | 30 คน |
| อารมณ์ | 4 ประเภท (happy, sad, stressed, excited) |
| Trials ต่อคน | 12 รอบ (3 รอบ × 4 อารมณ์) |
| Trials รวม | 360 Trial (90 ต่ออารมณ์) |

---

## 11. ระบบภาพและโทนสีส่วนติดต่อผู้ใช้ (UI Design System)

> รายละเอียดเต็มดูที่ [`UI_DESIGN.md`](UI_DESIGN.md)

### Color Tokens (Dark Navy–Purple)

| Token | รหัสสี | การใช้งาน |
|-------|--------|-----------|
| `--color-bg-primary` | `#080D21` | พื้นหลังหลัก |
| `--color-bg-secondary` | `#0F172A` | Sidebar, พื้นหลังรอง |
| `--color-surface` | `#151D35` | Card, Modal |
| `--color-primary` | `#7C3AED` | ปุ่มหลัก, Active state |
| `--color-secondary` | `#A78BFA` | Accent, Badge |
| `--color-success` | `#22C55E` | Good sensor, สำเร็จ |
| `--color-warning` | `#F59E0B` | Poor sensor, เตือน |
| `--color-error` | `#EF4444` | Stale sensor, ผิดพลาด |

### Horseshoe Sensor States

| State | สี | Icon | ความหมาย |
|-------|----|------|-----------|
| `unknown` | `#64748B` | `?` | ยังไม่มีข้อมูล |
| `poor` | `#F59E0B` | `!` | ต้องปรับตำแหน่ง |
| `good` | `#22C55E` | `✓` | สัญญาณดี |
| `stale` | `#EF4444` | `×` | สัญญาณขาดหาย |

---

## 12. บันทึกการเปลี่ยนแปลง (Changelog)

| เวอร์ชัน | วันที่ | การเปลี่ยนแปลง |
|---------|-------|----------------|
| 1.0 | ก.ค. 2569 | PRD ฉบับแรก |
| 2.0 | ก.ค. 2569 | เพิ่ม Muse 2 Protocol, Baseline spec, Dataset Collection |
| 3.0 | ต.ค. 2569 | อัปเดตให้ตรงกับ implementation จริง: Baseline 60s/30s (Dataset), 20s (User); Rule-based v1.0 classifier; collection_data path; atomic CSV writer; label derivation logic |

