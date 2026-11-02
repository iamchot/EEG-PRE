# โครงสร้างไฟล์ CSV และการเก็บข้อมูล Muse

## 1. รูปแบบ CSV (ทุกไฟล์เหมือนกัน)

```
timestamp, tp9, af7, af8, tp10, tp9_quality, af7_quality, af8_quality, tp10_quality, marker
```

| Column | ประเภท | ความหมาย |
|---|---|---|
| `timestamp` | Unix epoch (วินาที) | เวลาจาก browser `performance.now()` (แถวแรก) หรือ `Date.now()/1000` |
| `tp9` | float (µV) | แรงดันไฟฟ้า EEG ขั้ว **TP9** (หลังหูซ้าย) |
| `af7` | float (µV) | แรงดันไฟฟ้า EEG ขั้ว **AF7** (หน้าผากซ้าย) |
| `af8` | float (µV) | แรงดันไฟฟ้า EEG ขั้ว **AF8** (หน้าผากขวา) |
| `tp10` | float (µV) | แรงดันไฟฟ้า EEG ขั้ว **TP10** (หลังหูขวา) |
| `tp9_quality` | float (0–100) | คะแนนสัมผัสอิเล็กโทรดหู-ซ้าย |
| `af7_quality` | float (0–100) | คะแนนสัมผัสอิเล็กโทรดหน้าผาก-ซ้าย |
| `af8_quality` | float (0–100) | คะแนนสัมผัสอิเล็กโทรดหน้าผาก-ขวา |
| `tp10_quality` | float (0–100) | คะแนนสัมผัสอิเล็กโทรดหู-ขวา |
| `marker` | string | เหตุการณ์ (ส่วนใหญ่ว่าง ยกเว้นแถว Event) |

> **อัตราตัวอย่าง**: ~22 Hz (Muse ส่ง 256 Hz → browser average เป็น packet ทุก ~45 ms)

---

## 2. ตัวอย่างไฟล์ที่ 1: `P004/4/trial-37.csv` (Trial ปกติ)

**ขนาด**: 337 KB | **แถวข้อมูล**: 2,250 แถว | **ช่วงเวลา**: ~108 วินาทีรวม

```
row,timestamp,event
2,18824.44         ← marker: rest_start        ← เริ่มช่วง REST (แสดงจุดกลางจอ)
3–213,(1790429735.75 – 1790429745.83)          ← ~212 แถว ≈ 10 วิ ข้อมูล EEG ช่วง rest
214,1790429745.83  ← marker: rest_end
215,1790429745.83  ← marker: stimulus_start    ← เริ่มเล่นคลิปวิดีโอสิ่งเร้า
216–1443,(~1230 แถว ≈ 59.5 วิ)                ← บันทึก EEG ขณะดูคลิป
1444,1790429805.26 ← marker: stimulus_end
1445,1790429805.26 ← marker: rating_start      ← เริ่มแบบประเมิน SAM
1446–2250,(~807 แถว ≈ 38.9 วิ)               ← บันทึก EEG ขณะประเมินอารมณ์
2251,1790429844.09 ← marker: rating_end
```

**Trial Flow**:
```
[REST ~10s] → [STIMULUS ~60s คลิปวิดีโอ] → [RATING ~39s ประเมิน Valence/Arousal]
```

**สังเกต**: `rest_start` มี timestamp = `18824` (คือ `performance.now()` ms ที่นับจาก browser boot)  
ไม่ใช่ Unix epoch — แถวนี้เป็น marker row พิเศษ ค่า EEG ว่างทั้งหมด

---

## 3. ตัวอย่างไฟล์ที่ 2: `P001/2/trial-2-recovery-b5b6bb41004b.csv` (Trial หลัง Recovery)

**ขนาด**: 312 KB | **แถวข้อมูล**: 2,000 แถว

```
row 2:    4167.47      ← rest_start  (บันทึก timestamp ตอน marker)
row 304:  1790415092.8 ← rest_end    (~302 แถว ≈ 14.5 วิ rest)
row 305:  1790415092.8 ← stimulus_start
row 1644: 1790415155.5 ← stimulus_end (~1340 แถว ≈ 62.7 วิ)
row 1645: 1790415155.5 ← rating_start
row 2001: 1790415172.2 ← rating_end  (~357 แถว ≈ 16.6 วิ)
```

**สังเกตชื่อไฟล์**: `trial-2-recovery-b5b6bb41004b`  
- ต่อท้าย `-recovery-{MAC}` หมายถึง session ถูกสร้างใหม่ต่อจากที่ขาดหายระหว่างกลาง  
- `b5b6bb41004b` คือ Bluetooth MAC ของ Muse ที่ใช้ (ถูก hash/ย่อ)

---

## 4. ตัวอย่างไฟล์ที่ 3: `P001/2/baseline-eyes_open.csv` (Baseline ลืมตา)

**ขนาด**: 203 KB | **แถวข้อมูล**: 1,284 แถว

```
row 2:    50558.70       ← baseline_eyes_open_start
row 1285: 1790263575.52  ← baseline_eyes_open_end
```

**ช่วงเวลา**: ~60 วินาที (1,283 แถว ÷ ~22 Hz ≈ 58 วิ)  
ไม่มีช่วง rest/stimulus/rating — เป็นแค่ข้อมูล EEG ต่อเนื่องของ Resting State

**Structure**:
```
[header]
[marker: baseline_eyes_open_start]   ← ว่าง tp9/af7/af8/tp10
[~1283 แถวข้อมูล EEG ต่อเนื่อง]
[marker: baseline_eyes_open_end]
```

---

## 5. วิธีเขียนไฟล์ (raw_eeg_writer.py)

```
AtomicEEGWriter
├── start(["P004", "4", "trial-37"])  → สร้าง trial-37.partial ก่อน
├── mark("rest_start")                → เขียน row: timestamp, "", "", "", "", marker
├── append(EEGSample)                 → เขียน row: ts, tp9, af7, af8, tp10, q×4, ""
│   (วนซ้ำทุก ~45 ms ตลอด trial)
├── mark("rest_end") + mark("stimulus_start") + ...
└── finalize()                        → sha256 → os.replace(.partial → .csv)
```

> **ความปลอดภัย**: ใช้ `.partial` ไฟล์ระหว่างเขียน → atomic rename เมื่อเสร็จ → ไม่มี CSV ที่เขียนค้าง

---

## 6. สิ่งที่เก็บลง Database

### ตาราง `collection_sessions` (ต่อ session)
| Column | ค่าจาก CSV | ความหมาย |
|---|---|---|
| `eyes_open_baseline_path` | `P001/2/baseline-eyes_open.csv` | path สัมพัทธ์ใน `collection_data/` |
| `eyes_open_baseline_checksum` | SHA-256 ของไฟล์ | ป้องกัน tamper |
| `eyes_open_accepted_clean_seconds` | วินาทีที่สัญญาณสะอาด | คำนวณ real-time ขณะบันทึก |
| `eyes_open_wall_clock_seconds` | เวลาจริงทั้งหมด | จาก timestamp แรก/สุดท้าย |

### ตาราง `collection_trials` (ต่อ trial)
| Column | ค่าจาก CSV | ความหมาย |
|---|---|---|
| `eeg_file_path` | `P004/4/trial-37.csv` | path ไฟล์ |
| `eeg_checksum` | SHA-256 | integrity check |
| `raw_size_bytes` | 337,106 bytes | ขนาดไฟล์ |
| `accepted_clean_seconds` | float | วิที่สัญญาณผ่าน QC |
| `wall_clock_seconds` | float | เวลาบันทึกทั้งหมด |
| `valence_rating` | 1–9 | ประเมิน SAM หลัง rating_end |
| `arousal_rating` | 1–9 | ประเมิน SAM |
| `state` | completed | สถานะ trial |

> **ข้อมูล EEG ดิบ ไม่เก็บลง DB ทั้งหมด** — เก็บแค่ **path + checksum + สถิติ** ไว้ใน DB  
> ตัวไฟล์ CSV จริงเก็บอยู่ที่ `backend/collection_data/{participant}/{session}/`
