# Agent Guidelines & Repo Context

This file contains critical system-specific knowledge, architecture choices, configuration rules, and setup instructions for AI coding assistants working on the **Dream Comicverse** repository.

---

## 🚀 Quick Commands

### 1. Database (MySQL via Docker)
```powershell
docker-compose up -d
```

### 2. Backend (FastAPI)
```powershell
cd backend
.\venv\Scripts\Activate.ps1
python seed.py          # Admin: admin@dreamcomic.local / Admin1234!
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Frontend (Angular 19)
```powershell
cd frontend
$env:PATH = "C:\Users\sirik\AppData\Local\nvm\v24.11.1\;" + $env:PATH
ng serve --host 0.0.0.0 --port 4200
```

---

## 🧠 Architecture & Gotchas

### Library Compatibility
- **Bcrypt & Passlib:** Pin `bcrypt>=4.0.1,<4.1.0`. `passlib 1.7.4` is incompatible with `bcrypt >= 4.1.0` due to removed `__about__` attribute.
- **Pydantic Settings Extra Fields:** Set `extra="ignore"` in `SettingsConfigDict` inside `app/config.py`. Any `.env` variable not declared as a class property causes `extra_forbidden` validation error on startup.
- **EmailStr & Local TLDs:** Replace `pydantic.networks.EmailStr` with plain `str` + regex `^[^@\s]+@[^@\s]+\.[^@\s]+$` in auth schemas to allow `.local` / `.dev` development domains.

### Angular 19 Auth & State
- **APP_INITIALIZER for Reload Fix:** Route guards run before `AuthService` finishes async `/auth/me`. Add `APP_INITIALIZER` in `app.config.ts` to block routing until user fetch resolves when `access_token` exists in `localStorage`.
- **Signal-based EEG State:** Share Muse 2 sensor states via Angular Signals in `EegWsService`. Use `computed()` signals for derived states (e.g., `allSensorsGood`, phase transitions).

### EEG Signal Processing Rules
- Never compute FFT/PSD across Pause/Resume epoch boundaries.
- Baseline requires continuous 20 seconds of clean data from all 4 sensors (`good` state). Reset entirely on any `poor`/`stale` or artifact.
- Recording accepts 30 seconds of clean accepted data. Wall-clock timeout is 120 seconds total.
- Emotion classification is Rule-based v1.0 using `delta_faa` and `delta_arousal` relative to baseline — NOT ML classification.

---

## 📂 Key Files

| File | Purpose |
|------|---------|
| `backend/app/config.py` | Pydantic Settings — must have `extra="ignore"` |
| `backend/app/services/signal_processor.py` | EEG Epoch processing, FAA, Arousal |
| `backend/app/services/eeg_service.py` | 10-state machine for EEG session flow |
| `backend/app/services/gemini_service.py` | Story prompt → 4-panel dialogue |
| `backend/app/services/diffusion_service.py` | ComfyUI polling → comic panel images |
| `frontend/src/app/app.config.ts` | APP_INITIALIZER for auth persistence |
| `frontend/src/app/core/guards/auth.guard.ts` | authGuard / adminGuard / guestGuard |
| `frontend/src/app/shared/components/horseshoe-sensor/` | Muse 2 sensor status UI |

---

## 🗺️ Route Map

| Route | Guard | Component |
|-------|-------|-----------|
| `/login` | guestGuard | LoginComponent |
| `/register` | guestGuard | RegisterComponent |
| `/dashboard` | authGuard | DashboardComponent |
| `/eeg-session` | authGuard | EegSessionComponent |
| `/comic/:id` | authGuard | ComicViewComponent |
| `/history` | authGuard | HistoryComponent |
| `/admin` | authGuard + adminGuard | AdminComponent |

---

## 🎨 UI Design System (PRD §11)

**Color Tokens** — Dark Navy–Purple palette:

| Token | Value | Usage |
|-------|-------|-------|
| `--color-bg-primary` | `#080D21` | Page background |
| `--color-bg-secondary` | `#0F172A` | Sidebar, secondary |
| `--color-surface` | `#151D35` | Cards, modals |
| `--color-surface-elevated` | `#1E293B` | Hover states |
| `--color-primary` | `#7C3AED` | Primary buttons, active |
| `--color-secondary` | `#A78BFA` | Accent, badges |
| `--color-success` | `#22C55E` | Good sensor, success |
| `--color-warning` | `#F59E0B` | Poor sensor, caution |
| `--color-error` | `#EF4444` | Stale sensor, error |

**Horseshoe Sensor States:**

| State | Color | Icon | Text |
|-------|-------|------|------|
| `unknown` | `#64748B` | `?` | กำลังรอข้อมูล |
| `poor` | `#F59E0B` | `!` | ต้องปรับตำแหน่ง |
| `good` | `#22C55E` | `✓` | สัญญาณดี |
| `stale` | `#EF4444` | `×` | สัญญาณขาดหาย |

---

## 🧪 EEG Research Protocol

- **30 participants** target (5-participant pilot first).
- 60 s eyes-open + 60 s eyes-closed baseline per participant.
- 12 labelled trials per participant: 3 trials × 4 emotions (`happy`, `sad`, `stressed`, `excited`), each 60 seconds.
- Ground truth = post-trial **self-report** (discrete emotion + valence 1–9 + arousal 1–9 + confidence 1–5).
- Never put participant name in EEG filenames — use pseudonymous IDs (`P001`, `P002`, …).

```
data/eeg/
├── raw/P001/session_YYYYMMDD/*.csv
├── metadata/participants.csv
├── metadata/trials.csv
├── processed/epochs_v1.parquet
├── features/features_v1.parquet
└── manifests/dataset_v1.json
```

---

## 🤖 Emotion Classifier Contract

- Preprocess: 1–40 Hz band-pass + 50 Hz notch.
- Features: absolute/relative Alpha & Beta power (4 channels), `faa = ln(α_AF8) - ln(α_AF7)`, `arousal_index = ln(β/α)`.
- Validation: GroupKFold or LOSO by `participant_id`. **Never split epochs from the same participant across train/test.**
- Metric: Macro F1, with per-class precision/recall/F1 and confusion matrix.
- Save: preprocessing pipeline + classifier + feature order + label mapping + version together.

---

## ✅ Pre-Change Checklist

1. MySQL Docker container running: `docker ps`
2. Node version correct: `node --version` → `v24.11.1`
3. `GEMINI_API_KEY` set in `backend/.env`
4. `bcrypt` pinned to `>=4.0.1,<4.1.0` in `requirements_backend.txt`
