# Subject-Independent EEG Emotion Dataset Collection System

**Project:** การพัฒนาต้นแบบการสร้างการ์ตูนคอมิกด้วยการเรียนรู้ของเครื่อง  
**Purpose:** เก็บชุดข้อมูล EEG สำหรับประมาณ Valence และ Arousal เพื่อควบคุมโทนการ์ตูนคอมิก  
**Scope statement:** ระบบนี้ใช้เพื่อความบันเทิงและงานต้นแบบ ไม่ใช่การตรวจ วินิจฉัย หรือรักษาทางการแพทย์

## 1. Goal and Success Criteria

สร้างระบบสำหรับ Admin เพื่อเก็บ ตรวจสอบ ส่งออก และนำข้อมูล Muse 2 ไปฝึกโมเดลที่ใช้กับผู้ใช้ใหม่ซึ่งไม่อยู่ในชุดฝึก โดยแยก workflow นี้ออกจาก workflow สร้างคอมิกของผู้ใช้ทั่วไป

เกณฑ์ความสำเร็จของระบบเก็บข้อมูล:

- เก็บ Pilot 5 คนก่อน Main collection และไม่นำ Pilot มารวมเมื่อ protocol เปลี่ยนอย่างมีนัยสำคัญ
- Main collection ขั้นต่ำ 30 คน เป้าหมาย 40–50 คน
- ผู้เข้าร่วมแต่ละคนมี Baseline สองแบบและ Trial เป้าหมาย 12 รอบ
- ทุก Trial มี Raw EEG 4 ช่อง, marker, quality, self-rating และ provenance ครบ
- Dataset split ใช้ `participant_id` เป็น group เสมอ ไม่มีคนเดียวกันอยู่ทั้ง train และ test
- ระบบ train โมเดล Binary แยก Valence และ Arousal และเก็บ pipeline เป็น artifact ที่มี version
- UI และรายงานทุกจุดระบุว่าเป็นการประมาณเพื่อความบันเทิง ไม่ใช่การแพทย์

## 2. Recommended Modeling Strategy

ใช้โมเดล Binary สองตัวเป็นแกนหลัก:

1. `valence_model`: Negative หรือ Positive
2. `arousal_model`: Low หรือ High

ระบบเก็บคะแนน Valence และ Arousal ดิบแบบ 1–9 ไว้เสมอ เพื่อรองรับการทดลอง Regression ในอนาคต แต่ไม่ใช้ Regression เป็นโมเดลหลักในรุ่นแรก

การ map ผลสำหรับสร้างคอมิก:

| Valence | Arousal | Comic tone |
|---|---|---|
| Positive | Low | Happy / อบอุ่น ผ่อนคลาย |
| Positive | High | Excited / สนุก มีพลัง |
| Negative | Low | Sad / เศร้า เงียบ |
| Negative | High | Stressed / ตึงเครียด เร่งด่วน |

Mapping นี้แทนที่ rule mapping เดิมที่จัด Excited เป็น Negative–High และ Sad เป็น Positive–Low

## 3. Collection Protocol

### 3.1 Participants

- อายุอย่างน้อย 18 ปี
- ให้ความยินยอมก่อนเริ่มและถอนตัวได้ทุกเวลา
- ใช้รหัสนามแฝง เช่น `P001`; ห้ามใช้ชื่อจริงในไฟล์ EEG
- นัดหมาย 60 นาทีต่อคนและเผื่อทำความสะอาดอุปกรณ์ 10 นาที

### 3.2 Stimuli

- ใช้คลิปภาพและเสียงความยาว 45–60 วินาที
- มีคลิปอย่างน้อย 3 คลิปต่อ quadrant รวม 12 Trial ต่อคน
- เก็บ `target_quadrant` เพื่อประเมินประสิทธิภาพคลิปเท่านั้น ห้ามใช้แทน self-rating ตอน train
- Admin ต้องอนุมัติคลิปก่อนนำมาใช้และต้องบันทึก version ของชุดคลิป
- ระบบสุ่มลำดับคลิปแยกต่อ participant โดยรักษาจำนวนแต่ละ quadrant ให้สมดุล

### 3.3 Per-participant flow

1. อธิบายโครงการและยืนยัน consent
2. สร้าง participant code
3. สวม Muse 2 และผ่าน quality gate ที่ TP9, AF7, AF8, TP10
4. บันทึก Baseline ลืมตา 60 วินาที
5. บันทึก Baseline หลับตา 60 วินาที
6. ทำ Trial 6 รอบ
7. พักกลาง 3–5 นาที
8. ทำ Trial อีก 6 รอบ
9. ตรวจความครบถ้วน สำรองไฟล์ และจบ session

### 3.4 Per-trial flow

1. Rest/fixation 10–15 วินาที
2. ตรวจ signal quality และเพิ่ม `rest_end`
3. เพิ่ม `stimulus_start` พร้อมเริ่มคลิปและ Raw EEG
4. บันทึก artifact marker ระหว่างคลิป
5. เพิ่ม `stimulus_end` และหยุด recording เมื่อคลิปจบ
6. เก็บ Valence 1–9, Arousal 1–9 และ Confidence 1–5
7. พัก 20–30 วินาที แล้วจึงเริ่ม Trial ถัดไป

เวลารวมต่อ participant โดยประมาณ 41–61 นาที

## 4. Label Contract

Ground truth มาจาก self-rating ของ participant ไม่ใช่อารมณ์เป้าหมายของคลิป

| Score | Valence label | Arousal label |
|---:|---|---|
| 1–4 | Negative | Low |
| 5 | Ambiguous | Ambiguous |
| 6–9 | Positive | High |

กติกา:

- ถ้า Valence เท่ากับ 5 ให้ `valid_valence_label=false`; ยังใช้ Arousal ได้ถ้าไม่กำกวม
- ถ้า Arousal เท่ากับ 5 ให้ `valid_arousal_label=false`; ยังใช้ Valence ได้ถ้าไม่กำกวม
- ถ้า Confidence ต่ำกว่า 3 ให้ทั้งสอง label ไม่ผ่านชุดฝึกหลัก
- Raw EEG และ rating ที่ไม่ผ่านยังเก็บเพื่อ audit แต่ไม่เข้า primary training set
- ห้ามแก้ self-rating ให้ตรงกับ target quadrant ภายหลัง

## 5. Signal Quality Contract

Trial จะมี `valid_signal=true` เมื่อผ่านทุกข้อ:

- มี TP9, AF7, AF8, TP10 และ timestamp ครบ
- Sampling rate ใกล้ 256 Hz ตาม tolerance ที่ Backend กำหนดและมี version
- Clean EEG ไม่น้อยกว่า 80% ของช่วง stimulus
- AF7 และ AF8 ผ่าน quality gate ไม่น้อยกว่า 80% เพราะต้องใช้ FAA
- ไม่มี data gap ต่อเนื่องเกิน 2 วินาที
- มี marker อย่างน้อย `rest_start`, `rest_end`, `stimulus_start`, `stimulus_end`, `rating_start`
- Artifact เช่น ไอ พูด กะพริบตาถี่ ขยับศีรษะ สัมผัสอุปกรณ์ และอุปกรณ์หลุดถูกระบุ

Baseline แต่ละแบบต้องเหลือ clean data อย่างน้อย 30 วินาทีจากการบันทึก 60 วินาที

สถานะ review ของ Trial คือ `pending`, `accepted`, `rejected` โดย Admin เป็นผู้ตัดสินสุดท้ายและต้องเก็บเหตุผลเมื่อ reject

## 6. Admin Screens

### 6.1 Dataset Overview

- จำนวน participant, session และ trial
- จำนวน accepted, pending, rejected และ failed
- การกระจายของสี่ Valence/Arousal quadrants
- signal-quality summary และจำนวน missing trials
- ปุ่มเริ่มเก็บ participant ใหม่

### 6.2 Participant Registration

- สร้าง code อัตโนมัติแบบไม่ซ้ำ
- บันทึกเฉพาะข้อมูลที่จำเป็น
- ยืนยัน consent และเวลาที่ consent
- ไม่มีชื่อ อีเมล หรือเบอร์โทรใน dataset database

### 6.3 Device Preparation

- ใช้ Creative Headset Setup เดิมเป็น visual language
- เลือก Muse และแสดง TP9, AF7, AF8, TP10 แบบ real-time
- ปุ่มเริ่ม Baseline เปิดตาและปิดตาเปิดได้เมื่อ quality gate ผ่าน
- แสดง progress, reset reason และไฟล์ที่บันทึกสำเร็จ

### 6.4 Trial Runner

- แสดง Trial ปัจจุบันจาก 12 และสถานะ rest/stimulus/rating
- เล่นคลิปและสร้าง marker จาก Backend clock
- แสดง sensor quality แบบไม่บดบังคลิป
- ปุ่ม Artifact marker และ Emergency stop
- หลังคลิปแสดง Valence, Arousal และ Confidence form ก่อนเดินหน้าต่อ

### 6.5 Dataset Review

- กรองตาม participant, session, quadrant และ review status
- แสดง rating, clean ratio, sensor summary, artifacts และ raw file checksum
- Accept, reject หรือส่งกลับไปตรวจใหม่
- Export metadata, feature dataset และ manifest ตาม dataset version

## 7. Data Model

เพิ่ม entity ต่อไปนี้โดยทำ migration อย่างชัดเจน:

- `DatasetParticipant`: participant code, consent state/time, collection state, withdrawal time
- `EmotionStimulus`: file path, checksum, duration, target quadrant, approval state, stimulus-set version
- `CollectionSession`: participant, device, baseline paths/checksums, progress, status, timestamps
- `CollectionTrial`: session, stimulus, randomized order, ratings, derived labels, QC summary, raw path/checksum, review state
- `ArtifactEvent`: trial, event type, timestamp, note
- `DatasetVersion`: immutable manifest ของ accepted trials และ preprocessing version
- `ModelVersion`: model paths, feature order, label thresholds, training participant IDs, metrics และ deployment state

Raw EEG และคลิปเก็บเป็นไฟล์ใน Server ไม่เก็บเป็น BLOB ใน MySQL ฐานข้อมูลเก็บ path, checksum, size และ provenance

## 8. File and Export Schema

```text
dataset/
├── participants/P001/
│   ├── baseline/eyes_open.csv
│   ├── baseline/eyes_closed.csv
│   └── trials/T001.csv
├── metadata/participants.csv
├── metadata/trials.csv
├── metadata/stimuli.csv
├── features/features_v1.parquet
└── manifests/dataset_v1.json
```

Raw EEG columns:

```text
timestamp,tp9,af7,af8,tp10,tp9_quality,af7_quality,af8_quality,tp10_quality,marker
```

Trial metadata fields:

```text
participant_id,session_id,trial_id,stimulus_id,trial_order,target_quadrant,
valence,arousal,confidence,valence_label,arousal_label,
valid_valence_label,valid_arousal_label,artifact_count,clean_ratio,
valid_signal,review_status,raw_data_path,raw_checksum,collected_at
```

## 9. Failure and Recovery

- Muse หลุดระหว่างคลิป: หยุด Trial, บันทึกเหตุผล, mark `failed`, และให้เริ่ม Trial เดิมใหม่
- Signal quality ต่ำ: pause accepted-time accumulation; Raw clock และ marker ยังต้องตรวจย้อนหลังได้
- Browser หรือ Backend restart: resume จาก committed Trial ล่าสุด; Trial ที่กำลังทำต้องเป็น interrupted และห้ามถือว่าสำเร็จ
- คลิปโหลดไม่ได้: ห้ามเริ่ม EEG recording
- Participant ถอนตัว: ปิด session เป็น `withdrawn`; dataset version ใหม่ห้ามรวมข้อมูลนั้น
- Rating ไม่ครบ: Trial เป็น `incomplete`
- เขียน Raw file หรือ checksum ไม่สำเร็จ: Trial เป็น `failed`
- การลบใช้ soft delete และ audit log; การลบไฟล์จริงต้องเป็นกระบวนการแยกที่มีสิทธิ์และ confirmation

## 10. Preprocessing and Features

Pipeline รุ่นแรก:

1. ตรวจ schema, timestamp, sampling rate และ checksum
2. Band-pass 1–45 Hz
3. Notch 50 Hz
4. ตัด artifact และช่วง quality ไม่ผ่าน
5. แบ่ง Epoch 2 วินาที overlap 50%
6. คำนวณ absolute/relative Delta, Theta, Alpha, Beta ต่อ channel
7. คำนวณ FAA จาก AF7/AF8 และ Arousal index จาก Beta/Alpha
8. คำนวณ mean, SD และ quality summary
9. ปรับเทียบ feature เทียบกับ baseline ของ participant
10. เขียน Parquet พร้อม `feature_version` และ `preprocessing_version`

ห้ามทำ FFT ข้ามช่วง pause, gap หรือ artifact boundary

## 11. Training and Evaluation

- กัน participant 20% เป็น final test ตั้งแต่ต้น
- Participant ที่เหลือใช้ GroupKFold โดย group คือ `participant_id`
- Epoch หรือ Trial ของ participant เดียวกันห้ามข้าม fold
- Scaling, feature selection และ hyperparameter tuning fit เฉพาะ training fold
- เปรียบเทียบ Logistic Regression, SVM และ Random Forest
- เลือกด้วย Macro F1 แยก Valence และ Arousal
- รายงาน Accuracy, per-class Precision/Recall/F1, Macro F1, confusion matrix และผลราย participant
- Aggregate epoch probabilities เป็น trial probability ก่อนรายงาน trial-level result
- เป้าหมายต้นแบบ: Macro F1 ของทั้ง Valence และ Arousal ไม่น้อยกว่า 0.60 และดีกว่า majority baseline
- ถ้ายังไม่ผ่าน ให้ production ใช้ rule-based fallback และห้ามกล่าวอ้างว่าโมเดลผ่านเกณฑ์

Model artifact ต้องรวม `preprocessor`, `feature_order`, `valence_model`, `arousal_model`, `label_thresholds`, `training_participants`, metrics และ `model_version`

## 12. Privacy and Authorization

- หน้า collection, review, export และ model registry ใช้ Admin authorization
- Dataset ใช้ participant code เท่านั้น
- Consent document ที่มีตัวตนเก็บแยกและไม่อยู่ใน dataset export
- Export ต้องมี audit record ว่าใคร export dataset version ใดเมื่อใด
- Cloud รับเฉพาะผลที่ประมวลผลแล้ว; Raw EEG อยู่ในขอบเขต Local/Server ที่ได้รับอนุญาต
- UI, consent และรายงานระบุว่าเป็นระบบเพื่อความบันเทิงและงานต้นแบบ ไม่ใช่การแพทย์

## 13. Testing and Acceptance

- Participant code สร้างไม่ซ้ำภายใต้ concurrent requests
- Session/Trial state transition ปฏิเสธลำดับที่ไม่ถูกต้อง
- Backend เป็นเจ้าของ marker time และ accepted-time calculation
- Resume ไม่เปลี่ยน interrupted Trial เป็น completed
- Raw checksum และ schema ตรวจได้ก่อน accept
- Label tests ครอบคลุม score 1, 4, 5, 6, 9 และ Confidence ต่ำกว่า 3
- QC tests ครอบคลุม sensor loss, data gap, artifact และ baseline clean-time
- Export schema ครบและ dataset manifest immutable
- Training test ยืนยัน participant IDs ระหว่าง train/test ไม่ทับกัน
- Model loader ปฏิเสธ preprocessor/feature/model version ที่ไม่ตรงกัน
- Admin endpoints ปฏิเสธ User accounts
- Withdrawal ทำให้ dataset version ถัดไปไม่รวม participant นั้น

## 14. Implementation Sequence

1. Database migrations and Stimulus Library
2. Participant registration and collection-session state machine
3. Muse quality and dual-baseline integration
4. Trial player, marker recording and self-rating
5. Dataset review, QC and versioned export
6. Offline preprocessing and feature pipeline
7. Valence/Arousal training and evaluation pipeline
8. Model registry and comic-generation integration with rule-based fallback

แต่ละ phase ต้องมี automated tests และ review checkpoint ก่อนเริ่ม phase ถัดไป

## 15. Research Basis

- DREAMER ใช้ audio-visual stimuli พร้อม participant self-assessment ของ Valence, Arousal และ Dominance: https://pubmed.ncbi.nlm.nih.gov/28368836/
- DEAP ใช้มิวสิกวิดีโอหนึ่งนาทีและ self-rating หลายมิติจากผู้เข้าร่วม 32 คน: https://yonsei.elsevierpure.com/en/publications/deap-a-database-for-emotion-analysis-using-physiological-signals/
- แนวทาง subject-independent ต้องประเมินด้วย participant-level holdout/LOSO ไม่ใช่สุ่ม Epoch ข้าม participant
