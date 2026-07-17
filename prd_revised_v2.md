# Product Requirements Document (PRD)

**ชื่อโครงการ:** Dream Comicverse (การพัฒนาต้นแบบการสร้างการ์ตูนคอมิกจากสัญญาณคลื่นสมองด้วยการเรียนรู้ของเครื่อง)
**ผู้พัฒนา:** นายพร้อมพงศ์ รังสรรค์ปรีชา
**แพลตฟอร์ม:** Web Application
**เวอร์ชันเอกสาร:** 2.0 (ปรับปรุงขั้นตอน Muse 2, Baseline และ Real-time Sensor Check)
**วันที่ปรับปรุง:** 30 มิถุนายน 2569

---

## 1. ภาพรวมผลิตภัณฑ์ (Product Overview)

ระบบต้นแบบเว็บแอปพลิเคชันที่ผสานเทคโนโลยีส่วนต่อประสานสมอง-คอมพิวเตอร์ (BCI) ร่วมกับปัญญาประดิษฐ์เชิงรู้สร้าง (Generative AI) เพื่อช่วยเหลือผู้ใช้งานทั่วไปที่ขาดทักษะด้านการวาดภาพ ให้สามารถถ่ายทอดจินตนาการและสร้างสรรค์ผลงานการ์ตูนคอมิกความยาว 4 ช่องจบได้อย่างเป็นรูปธรรม ระบบจะทำการดึงข้อมูลคลื่นไฟฟ้าสมอง (EEG) เพื่อวิเคราะห์สภาวะอารมณ์แบบเรียลไทม์ และนำผลลัพธ์ที่ได้ไปเป็นพารามิเตอร์หลักในการควบคุมทิศทางของเนื้อเรื่อง โทนสี และบรรยากาศของภาพการ์ตูน

---

## 2. วัตถุประสงค์ (Objectives)

- พัฒนาโมดูลเชื่อมต่อและประมวลผลสัญญาณคลื่นสมองจากอุปกรณ์ฮาร์ดแวร์ เพื่อจำแนกสภาวะอารมณ์ของผู้ใช้งาน
- สร้างกระบวนการแปลงค่าอารมณ์เป็นชุดคำสั่ง (Prompt) สำหรับควบคุมแบบจำลอง AI
- ประเมินประสิทธิภาพความแม่นยำของระบบและความพึงพอใจด้านการใช้งาน

---

## 3. สถาปัตยกรรมและเทคโนโลยี (System Architecture & Tech Stack)

- **Frontend:** Angular, HTML, CSS, TypeScript
- **Backend:** Python + FastAPI
- **Database:** MySQL
- **Security & Auth:** JWT (JSON Web Token) สำหรับการยืนยันตัวตน (Authentication) และการจัดการสิทธิ์ (Authorization)
- **Hardware:** อุปกรณ์วัดคลื่นสมอง Muse 2 Headband ส่งข้อมูลผ่าน Bluetooth Low Energy (BLE) ไปยังโปรแกรมตัวกลางในเครื่อง Local ซึ่งเผยแพร่ข้อมูลเป็น LSL stream
- **Edge Processing:** FastAPI และตัวรับ LSL ต้องรันบนคอมพิวเตอร์ Local เครื่องเดียวกับที่เชื่อมต่อ Muse 2 เพื่อทำ Signal Quality Check, Artifact Rejection, Baseline Calibration, FFT/PSD, Feature Extraction และ Machine-learning Emotion Classification
- **Cloud Boundary:** ส่งขึ้น Cloud เฉพาะผลลัพธ์ที่ผ่านการประมวลผลแล้ว เช่น Final Emotion, Confidence/Quality Summary, ค่า Valence/Arousal, Persona, Story และ Prompt โดยไม่สตรีม Raw EEG ไปประมวลผลบน Cloud
- **AI Models:**
  - **Gemini API:** ประมวลผลภาษาธรรมชาติ แต่งบทสนทนาและคำบรรยาย
  - **Stable Diffusion:** สร้างภาพวาดการ์ตูนคอมิกตามสไตล์ที่กำหนด

---

## 4. กระบวนการทำงานเชิงวิชาการ (Core Workflow)

### ส่วนนำเข้าข้อมูล (Input)

- ข้อมูลตัวละคร (Persona) เช่น รูปลักษณ์ เครื่องแต่งกาย จุดเด่น
- โครงเรื่องตั้งต้น (Story Prompt) และตัวละครที่ต้องการให้ปรากฏในเรื่อง
- สไตล์ภาพการ์ตูน ได้แก่ Webtoon, Manga, American Comic, และ Comic
- ข้อมูลสัญญาณคลื่นสมองดิบ (Raw Data) จากเซนเซอร์ตำแหน่ง AF7, AF8, TP9, TP10 ด้วยอัตราการสุ่ม 256 Hz

### ส่วนประมวลผล (Process)

- **Signal Quality Gate:** รับข้อมูลเมื่อเซนเซอร์ TP9, AF7, AF8 และ TP10 มีสถานะ `good` ครบทั้ง 4 จุดเท่านั้น ช่วงที่เป็น `poor`, `unknown` หรือ `stale` จะไม่ถูกนำไปคำนวณ
- **Artifact Rejection:** ตรวจและตัด Epoch ที่มีสัญญาณรบกวนจากการกะพริบตา การเกร็งใบหน้า/ขากรรไกร การเคลื่อนไหว หรือค่าผิดปกติตามเกณฑ์ที่ Backend กำหนด
- **Data Filtering:** กรองสัญญาณและแยกย่าน Alpha (8-13 Hz) และ Beta (13-30 Hz) บริเวณ AF7/AF8
- **Feature Extraction:** แบ่งข้อมูลเป็น Epoch ขนาด 2 วินาที ซ้อนทับ 50% คำนวณ FFT/PSD ราย Epoch และเฉลี่ยเฉพาะ Epoch ที่ผ่าน Quality Gate เพื่อหลีกเลี่ยงการทำ FFT ข้ามรอยต่อของข้อมูลหลัง Pause/Resume
- **Baseline Calibration:** เก็บ Resting State แบบลืมตาและผ่อนคลายให้ได้ข้อมูลสะอาดต่อเนื่อง 20 วินาที หากเซนเซอร์จุดใดไม่เป็น `good` หรือพบ Artifact ให้ Reset Baseline และเริ่มสะสมใหม่
- **Emotion Mapping:**
  - คำนวณคุณลักษณะความไม่สมมาตรของสมองส่วนหน้า: $FAA = \ln(P_{\alpha,AF8}) - \ln(P_{\alpha,AF7})$
  - คำนวณ Arousal index จาก $\ln(P_{\beta}/P_{\alpha})$ และใช้เป็น Feature ไม่ใช้เป็นคำตอบอารมณ์โดยตรง
  - ทาบพิกัดลงบนตารางมิติอารมณ์ 2 มิติ (Circumplex Model) เพื่อจำแนกเป็น 1 ใน 4 สภาวะอารมณ์: **มีความสุข (Happy), เศร้า (Sad), เครียด (Stressed), ตื่นเต้น (Excited)**
- **Prompt Engineering:** ผสมเนื้อเรื่อง อารมณ์ และสไตล์ภาพ เพื่อส่งให้ AI ประมวลผล

### ส่วนแสดงผลลัพธ์ (Output)

- การ์ตูนคอมิก 4 ช่องจบ พร้อมบทบรรยายที่สอดคล้องกับอารมณ์ผู้ใช้งาน
- ข้อมูลสรุปสภาวะอารมณ์ที่ระบบตรวจจับได้

---

## 5. ข้อกำหนดด้านฟังก์ชันการทำงาน (Functional Requirements)

### 5.1 ระบบจัดการผู้ใช้งานและความปลอดภัย (User Management & Security)

- รองรับการสมัครสมาชิก เข้าสู่ระบบ และแบ่งสิทธิ์การเข้าถึงระหว่าง User และ Admin (Role-based Access Control)
- **การยืนยันตัวตนด้วย JWT:** เมื่อผู้ใช้งานเข้าสู่ระบบสำเร็จ ระบบจะสร้าง JWT Token ส่งกลับไปให้ Frontend เพื่อใช้แนบใน Authorization Header สำหรับการเรียกใช้งาน API ป้องกันการเข้าถึงข้อมูลข้ามสิทธิ์
- มีระบบสร้างและแก้ไข Persona เพื่อบันทึกลักษณะตัวละครโปรดเก็บไว้ในฐานข้อมูล

### 5.2 ระบบเตรียมความพร้อมก่อนวัดสัญญาณ (Onboarding & Sensor Check)

- **Local Service Check:** ตรวจว่า FastAPI, LSL receiver และโปรแกรมตัวกลาง Muse 2 บนเครื่อง Local พร้อมทำงาน หากไม่พร้อมต้องแจ้งวิธีเปิดบริการก่อนค้นหาอุปกรณ์
- **Device Discovery & Confirmation:** ค้นหา Muse 2 ผ่าน Bluetooth แสดงชื่ออุปกรณ์ เช่น `Muse-A9C7` และรหัสภายใน ผู้ใช้ต้องเลือกและกดยืนยันก่อนระบบเชื่อมต่อ ห้ามเชื่อมต่ออัตโนมัติเมื่อมีหลายอุปกรณ์
- **Hair & Skin Preparation:** ให้ผู้ใช้เลือกหนึ่งตัวเลือก ได้แก่ “ไม่มีผม/ผมสั้นมาก” หรือ “ผมสั้นถึงผมยาว” และแสดงคำแนะนำที่เหมาะสม เช่น มัดผมไม่ให้ขวางเซนเซอร์ ถอดแว่น และเตรียมผิวบริเวณหน้าผาก/หลังหูตามคำแนะนำการใช้งานที่ผ่านการตรวจสอบกับคู่มืออุปกรณ์
- **Horseshoe UI:** แสดงตำแหน่ง TP9, AF7, AF8 และ TP10 แยกรายจุด พร้อมสถานะ `unknown`, `poor`, `good`, `stale` และ Quality Score 0-100% โดยต้องมีข้อความหรือไอคอนร่วมกับสี
- **Readiness Rule:** ระบบจะถือว่าพร้อมเฉพาะเมื่อเซนเซอร์ทั้ง 4 จุดเป็น `good` เท่านั้น ค่าเฉลี่ยคุณภาพรวมใช้เพื่อสื่อสารกับผู้ใช้ แต่ห้ามใช้แทนเงื่อนไขรายเซนเซอร์
- **Signal Check Tips:** หาก TP9/TP10 มีปัญหา ให้แนะนำปรับสายและตรวจเส้นผมหรือสิ่งกีดขวาง หาก AF7/AF8 มีสัญญาณรบกวน ให้แนะนำลดการขยับ ผ่อนคลายใบหน้าและขากรรไกร
- **Baseline 20 Seconds:** เมื่อทั้ง 4 จุดเป็น `good` ให้เริ่มเก็บ Resting-state Baseline ต่อเนื่อง 20 วินาที หากจุดใดตกเป็น `poor`/`stale` หรือพบ Artifact ให้ Reset เป็น 20 วินาทีใหม่
- **Baseline Output:** คำนวณค่า Baseline ของ Log Alpha, Log Beta, FAA และ Log Beta/Alpha เพื่อใช้หาค่าเปลี่ยนแปลงสัมพัทธ์ในช่วง Recording จริง

### 5.3 ระบบวัดคลื่นสมองและการจำแนกอารมณ์ (EEG Recording)

- เริ่ม Recording ได้เมื่อ Baseline 20 วินาทีสำเร็จและเซนเซอร์ TP9, AF7, AF8, TP10 เป็น `good` ครบทุกจุด
- เก็บข้อมูลสะอาดที่ยอมรับได้เป็นระยะเวลา **30 วินาทีตายตัว** พร้อม Progress Bar ซึ่งอ้างอิงจำนวนวินาทีของข้อมูลที่ผ่านเกณฑ์จาก Backend
- หากเซนเซอร์จุดใดเปลี่ยนเป็น `poor`, `unknown` หรือ `stale` ให้ Pause Countdown อัตโนมัติ แสดงคำแนะนำ และ Reject ข้อมูลในช่วงดังกล่าว ห้ามนำไปรวมใน Buffer
- เมื่อเซนเซอร์กลับเป็น `good` ครบ 4 จุดต่อเนื่องอย่างน้อย **2 วินาที** ให้ Resume การเก็บข้อมูลจากเวลาที่ค้างไว้ โดยไม่ Reset Recording ทั้งหมด
- จำกัดเวลารวมตั้งแต่เริ่ม Recording ไม่เกิน **120 วินาที** หากยังสะสมข้อมูลที่ผ่านเกณฑ์ไม่ครบ 30 วินาที ให้ยกเลิก Session และเสนอให้ผู้ใช้วัดใหม่
- ห้ามนำข้อมูลคนละช่วงหลัง Pause/Resume มาต่อกันแล้วทำ FFT ทั้งก้อน ต้องคำนวณ PSD ราย Epoch ขนาด 2 วินาที ซ้อนทับ 50% และเฉลี่ยเฉพาะ Epoch ที่ผ่านเกณฑ์
- จำแนกอารมณ์ด้วยแบบจำลองที่ผ่านการคัดเลือกจาก Logistic Regression, SVM และ Random Forest โดยใช้ `delta_faa`, `delta_arousal` และคุณลักษณะ Alpha/Beta อื่นร่วมกัน พร้อมระบุ Model version และ Confidence
- แสดงผลลัพธ์อารมณ์และค่า Quality Summary ให้ผู้ใช้กด “ยืนยัน” หรือ “วัดใหม่” ก่อนส่งข้อมูลไปสร้างการ์ตูน

### 5.4 ระบบสร้างภาพการ์ตูน (Comic Generation)

- ส่งคำสั่งและเนื้อเรื่องให้ Gemini ประมวลผลบทสนทนา 4 ช่อง
- ประยุกต์ใช้โทนสีและแสงผ่าน Stable Diffusion ตามอารมณ์ที่วิเคราะห์ได้จากสมอง
- แสดงผลลัพธ์ในรูปแบบ Layout การ์ตูนบนหน้า Web Application

### 5.5 ระบบประเมินและประวัติการใช้งาน (Evaluation & Dashboard)

- ผู้ใช้สามารถดูประวัติการ์ตูนย้อนหลังที่ตนเองเคยสร้างได้ (Timeline/Recent Activity)
- มีฟอร์มประเมินความพึงพอใจ (ให้คะแนน 1-5 ดาว พร้อมข้อเสนอแนะ) ทุกครั้งที่สร้างการ์ตูนเสร็จ

### 5.6 ระบบสำหรับผู้ดูแลระบบ (Admin Panel)

- **Check Statistics:** แสดงหน้า Dashboard สรุปข้อมูลเชิงสถิติ เช่น สัดส่วนอารมณ์ (Emotion Distribution) และกิจกรรมการใช้งานระบบ
- **Manage Users:** จัดการระงับ ลบ หรือแก้ไขข้อมูลผู้ใช้ในระบบ
- **Manage EEG Dataset:** สามารถเรียกดู ลบ หรือส่งออกข้อมูลคลื่นสมอง (Export JSON/CSV) สำหรับนำไปใช้พัฒนางานวิจัยในอนาคต

---

## 6. ข้อกำหนดด้านการจัดการข้อมูล (Data Management Requirements)

เพื่ออ้างอิงตามโครงสร้าง Entity-Relationship Diagram (ERD) ระบบมีการจัดการการรับ-ส่งและจัดเก็บข้อมูลในแต่ละส่วนดังนี้:

### 6.1 ข้อมูลที่ระบบต้องรับเข้ามา (Data Inputs)

- **ข้อมูลจากผู้ใช้งาน (User Inputs):**
  - ข้อมูลบัญชี: `username`, `email`, `password_hash`, `role_id` (รับตอนสมัครสมาชิก)
  - ข้อมูลตัวละคร: `persona_name`, `appearance`, `art_style` (รับตอนสร้าง Persona)
  - ข้อมูลตั้งต้นสำหรับการ์ตูน: `input_story`, `persona_id` (รับตอนกดเริ่มสร้างการ์ตูน)
- **ข้อมูลจากอุปกรณ์และเซนเซอร์ (Hardware Inputs):**
  - ข้อมูลสถานะเครื่อง: `device_id`, `device_name`, `connection_state` และเวลาที่อัปเดตล่าสุด
  - ข้อมูลสถานะรายเซนเซอร์: TP9, AF7, AF8, TP10 โดยแต่ละจุดมี `state`, `quality_score`, `timestamp` และ `sequence`
  - ข้อมูล Onboarding: ประเภทเส้นผมที่ผู้ใช้เลือกและสถานะการยอมรับคำแนะนำ (บันทึกเมื่อได้รับความยินยอมและจำเป็นต่อการวิจัย)
  - ข้อมูลสัญญาณสมอง: Raw EEG Data จาก 4 เซนเซอร์ โดยสะสมเฉพาะข้อมูลที่ผ่าน Quality Gate ให้ครบ 30 วินาที (ข้อมูลดิบส่วนนี้ **จะไม่บันทึกลง Database โดยตรง** แต่จะถูกบันทึกเป็นไฟล์ `.csv` ไว้ที่ Server และเก็บเฉพาะที่อยู่ไฟล์ หรือ `raw_data_path` ลงในฐานข้อมูล)

### 6.2 ข้อมูลที่ต้องประมวลผลและจัดเก็บ (Processed Data Storage)

เมื่อระบบได้รับข้อมูลตั้งต้น จะทำการประมวลผลผ่าน Backend และ AI จากนั้นจะบันทึกผลลัพธ์ลงฐานข้อมูลดังนี้:

- **ข้อมูลรอบการวัด (ตาราง `EEGSession`):** `session_id`, `device_id`, `baseline_duration=20`, `accepted_recording_duration=30`, `wall_clock_duration`, `rejected_epoch_count`, `pause_count`, `raw_data_path`, `started_at`, `completed_at`, `status`
- **ข้อมูล Baseline และ Feature (ตาราง `EEGFeature`):** ค่า Log Alpha/Log Beta ราย AF7/AF8, `baseline_faa`, `baseline_arousal`, `recording_faa`, `recording_arousal`, `delta_faa`, `delta_arousal`, Epoch configuration และ feature version
- **ข้อมูลผลลัพธ์อารมณ์ (ตาราง `EmotionResult`):** `final_emotion`, `confidence`, `model_version`, `feature_version`, Valence/Arousal summary และ Quality Summary
- **ข้อมูลผลลัพธ์จาก AI (บันทึกลงตาราง `Comic`):**
  - ชุดคำสั่งสมบูรณ์: `generated_prompt` (เนื้อเรื่อง + อารมณ์ + สไตล์ ที่ผสมและทำ Prompt Engineering แล้ว)
  - ภาพผลงาน: `panel_1_url` ถึง `panel_4_url` (ลิงก์ไฟล์รูปภาพการ์ตูน 4 ช่อง)

### 6.3 ข้อมูลที่ต้องดึงไปแสดงผล (Data Retrieval & Outputs)

ในการแสดงผลบนหน้า Web Application ระบบจะ Query ข้อมูลผ่าน API Endpoint โดยมี Token (JWT) กำกับ:

- **หน้า Login / Auth:** ดึง `password_hash` มาตรวจสอบ หากถูกต้องระบบจะส่ง JWT Token พร้อมระบุ `role` ให้ Frontend
- **หน้า Dashboard / Onboarding:**
  - ดึงรายชื่อ `Persona` ทั้งหมดของ `user_id` นั้นๆ มาแสดงเป็นตัวเลือก
  - รับสถานะ Device และสถานะ TP9/AF7/AF8/TP10 แบบ Real-time เพื่อวาด Horseshoe UI พร้อมตรวจข้อมูล `stale` จาก timestamp/sequence
- **หน้าประวัติผลงาน (History/Gallery):**
  - ดึงข้อมูลจากตาราง `Comic` โชว์รูปภาพทั้ง 4 ช่อง (`panel_urls`) และเรื่องราว (`input_story`)
  - ทำ Table JOIN โดยนำ `session_id` ไปเชื่อมกับตาราง `Session` เพื่อดึง `final_emotion` มาแสดงเป็น Tag กำกับว่าภาพนี้สร้างขึ้นในอารมณ์ใด
  - ทำ Table JOIN โดยนำ `persona_id` ไปเชื่อมเพื่อแสดงคาแรคเตอร์ที่ใช้

---

## 7. ข้อกำหนด Real-time API ระหว่าง Angular และ FastAPI

- ใช้ **WebSocket** สำหรับส่งสถานะอุปกรณ์ เซนเซอร์ Phase และ Progress จาก Local FastAPI ไปยัง Angular แบบ Real-time
- Backend เป็นผู้ตัดสินสถานะ `ready`, Baseline reset, Recording pause/resume และจำนวนวินาทีของข้อมูลที่ยอมรับได้ Frontend ทำหน้าที่แสดงผลและส่งคำสั่งผู้ใช้เท่านั้น
- ทุกข้อความต้องมี `session_id`, `phase`, `sequence`, `timestamp`, Device state, สถานะเซนเซอร์ทั้ง 4 จุด, Quality Score, `accepted_seconds`, `wall_clock_seconds`, `ready` และ Reason/Error code
- Sensor state ประกอบด้วย `unknown` (ยังไม่มีข้อมูล), `poor` (คุณภาพไม่ผ่าน), `good` (ผ่านเกณฑ์) และ `stale` (ไม่มีข้อมูลใหม่ภายในเวลาที่กำหนด) ส่วนการหลุดของอุปกรณ์ให้รายงานแยกใน Device state เป็น `disconnected`
- ต้องป้องกันข้อความเก่าหรือเรียงผิดด้วย `sequence` และห้ามแสดง `good` ค้างเมื่อข้อมูลหมดอายุ
- ค่า Threshold และสูตร Quality Score ต้องกำหนดใน Backend แบบมีเวอร์ชันและทดสอบกับอุปกรณ์จริง ห้ามให้ Angular คำนวณเอง

## 8. State Machine ของ EEG Session

`DISCOVERING → DEVICE_CONFIRMATION → CONNECTING → PREPARATION → FITTING → BASELINE → READY → RECORDING → EMOTION_CONFIRMATION → COMPLETED`

สถานะผิดปกติประกอบด้วย `PAUSED_SIGNAL_QUALITY`, `DISCONNECTED`, `TIMEOUT`, `CANCELLED` และ `FAILED`

กติกาหลัก:

1. Baseline สัญญาณตกหรือพบ Artifact: Reset กลับไป 20 วินาที
2. Recording สัญญาณตก: เข้า `PAUSED_SIGNAL_QUALITY`, หยุดเวลาเก็บข้อมูล และ Reject Epoch
3. กลับมา `good` ครบ 4 จุดต่อเนื่อง 2 วินาที: Resume Recording
4. Wall-clock เกิน 120 วินาทีแต่ข้อมูลสะอาดไม่ครบ 30 วินาที: `TIMEOUT` และวัดใหม่
5. ครบข้อมูลที่ยอมรับได้ 30 วินาที: คำนวณ Feature/Emotion แล้วเข้าสู่ `EMOTION_CONFIRMATION`

## 9. Acceptance Criteria สำคัญ

- **AC-EEG-01:** ระบบไม่เชื่อมต่อ Muse จนกว่าผู้ใช้เลือกและยืนยันอุปกรณ์
- **AC-EEG-02:** Horseshoe UI ต้องแสดง TP9, AF7, AF8, TP10 ถูกตำแหน่งและไม่ใช้สีเป็นตัวสื่อความหมายเพียงอย่างเดียว
- **AC-EEG-03:** เริ่ม Baseline/Recording ได้เมื่อทั้ง 4 จุดเป็น `good` เท่านั้น
- **AC-EEG-04:** Baseline ต้องได้ข้อมูลสะอาดต่อเนื่อง 20 วินาทีและ Reset เมื่อคุณภาพตกหรือพบ Artifact
- **AC-EEG-05:** Recording ต้องสะสม accepted data ครบ 30 วินาที โดยช่วงที่คุณภาพไม่ผ่านไม่เพิ่ม Progress และไม่ถูกนำไปคำนวณ
- **AC-EEG-06:** หลัง Pause ต้อง `good` ครบ 4 จุดต่อเนื่อง 2 วินาทีก่อน Resume
- **AC-EEG-07:** Session ต้อง Timeout เมื่อ wall-clock เกิน 120 วินาทีและข้อมูลสะอาดยังไม่ครบ
- **AC-EEG-08:** PSD ต้องคำนวณเป็น Epoch 2 วินาที ซ้อนทับ 50% และไม่ทำ FFT ข้ามรอยต่อ Pause/Resume
- **AC-EEG-09:** ข้อมูลที่หมดอายุต้องเปลี่ยนเป็น `stale`; Device ที่หลุดต้องเป็น `disconnected`
- **AC-EEG-10:** ผลอารมณ์ต้องระบุ Model version, Feature version, Confidence และค่าเปลี่ยนแปลงเทียบ Baseline

## 10. ข้อกำหนดวิธีจำแนกอารมณ์

ระบบใช้ Feature Extraction ทางประสาทวิทยาศาสตร์ร่วมกับการเรียนรู้แบบมีผู้สอน โดยเปรียบเทียบ Logistic Regression, Support Vector Machine และ Random Forest จากข้อมูล Muse 2 ที่เก็บจากกลุ่มตัวอย่าง แบบจำลองที่มี Macro F1-score จากการประเมินแบบแยกผู้เข้าร่วมสูงที่สุดจึงถูกเลือกใช้งาน ส่วน Gemini และ Stable Diffusion เป็น Generative AI ขั้นปลายและไม่ใช่ตัวจำแนก EEG

ค่าที่ใช้ควบคุมการจำแนก:

- `FAA = logAlpha(AF8) - logAlpha(AF7)`
- `delta_faa = FAA_recording - FAA_baseline`
- `Arousal = log(BetaPower / AlphaPower)`
- `delta_arousal = Arousal_recording - Arousal_baseline`

### 10.1.1 กติกาการฝึกและประเมินโมเดล

- แบ่งข้อมูลตาม `participant_id` ด้วย GroupKFold หรือ Leave-One-Subject-Out เท่านั้น
- ห้ามให้ Epoch ของบุคคลเดียวกันอยู่ทั้ง Train และ Test
- Scaling, feature selection และการปรับค่าพารามิเตอร์ต้องทำภายใน Training fold
- เลือกโมเดลด้วย Macro F1 พร้อมรายงาน Accuracy, Precision, Recall, F1 รายคลาส และ Confusion Matrix
- จัดเก็บ Pipeline, Feature order, Label mapping และ Model metadata เป็น Artifact เวอร์ชันเดียวกัน

ต้องกำหนด Threshold สำหรับ Happy, Sad, Stressed และ Excited ให้ไม่ซ้อนกัน พร้อมระบุ Rule version และวิธี Validation ก่อนใช้งานจริง

## 11. ระบบภาพและโทนสีส่วนติดต่อผู้ใช้ (UI Design System)

### 11.1 แนวทางภาพรวม

ระบบใช้โทน **Dark Navy–Purple** ให้สอดคล้องกับ Prototype เดิม สื่อถึงเทคโนโลยี ความฝัน และจินตนาการ โดยต้องรักษาความอ่านง่าย โดยเฉพาะขั้นตอนเชื่อมต่ออุปกรณ์ ตรวจสัญญาณ และบันทึก EEG

### 11.2 Color Tokens

| Token                      |    รหัสสี | การใช้งาน                       |
| -------------------------- | --------: | ------------------------------- |
| `--color-bg-primary`       | `#080D21` | พื้นหลังหลัก                    |
| `--color-bg-secondary`     | `#0F172A` | พื้นหลังรองและ Sidebar          |
| `--color-surface`          | `#151D35` | Card, Modal และ Panel           |
| `--color-surface-elevated` | `#1E293B` | Hover และพื้นผิวยกระดับ         |
| `--color-primary`          | `#7C3AED` | ปุ่มหลัก ลิงก์ และ Active state |
| `--color-primary-hover`    | `#6D28D9` | Hover ของปุ่มหลัก               |
| `--color-secondary`        | `#A78BFA` | Accent, Badge และข้อมูลรอง      |
| `--color-text-primary`     | `#F8FAFC` | ข้อความหลัก                     |
| `--color-text-secondary`   | `#CBD5E1` | ข้อความอธิบาย                   |
| `--color-text-muted`       | `#94A3B8` | Placeholder และข้อมูลไม่สำคัญ   |
| `--color-border`           | `#334155` | เส้นขอบและ Divider              |
| `--color-focus`            | `#C4B5FD` | Keyboard focus ring             |
| `--color-success`          | `#22C55E` | สำเร็จและพร้อมใช้งาน            |
| `--color-warning`          | `#F59E0B` | ต้องปรับหรือควรระวัง            |
| `--color-error`            | `#EF4444` | ข้อผิดพลาดและสัญญาณขาด          |
| `--color-neutral`          | `#64748B` | ยังไม่ทราบหรือยังไม่มีข้อมูล    |

### 11.3 สีสถานะ Horseshoe UI

| Sensor state |        สี | Icon/ข้อความ            | พฤติกรรม                          |
| ------------ | --------: | ----------------------- | --------------------------------- |
| `unknown`    | `#64748B` | `?` / “กำลังรอข้อมูล”   | ยังไม่ได้รับข้อมูลเซนเซอร์        |
| `poor`       | `#F59E0B` | `!` / “ต้องปรับตำแหน่ง” | แสดงคำแนะนำตามตำแหน่ง             |
| `good`       | `#22C55E` | `✓` / “สัญญาณดี”        | อนุญาตเมื่อครบทั้ง 4 จุด          |
| `stale`      | `#EF4444` | `×` / “สัญญาณขาดหาย”    | Pause หรือยกเลิกตาม State machine |

ข้อกำหนด:

- ห้ามใช้สีบอกสถานะเพียงอย่างเดียว ต้องมี Icon, Label และข้อความช่วยเหลือ
- ใช้ Transition 150–250 มิลลิวินาที และห้ามใช้แสงกระพริบเร็ว
- Quality Score รวมต้องแสดงเปอร์เซ็นต์และข้อความ เช่น “85% — พร้อมเริ่มวัด”
- ห้ามแสดง “พร้อมเริ่มวัด” หากมีเซนเซอร์ใดไม่เป็น `good` แม้คะแนนรวมจะสูง

### 11.4 Component Styling

- **Primary Button:** พื้น `#7C3AED`, ตัวอักษร `#FFFFFF`; Hover ใช้ `#6D28D9`
- **Secondary Button:** พื้นโปร่งใส ขอบ `#A78BFA`, ตัวอักษร `#EDE9FE`
- **Destructive Button:** พื้น `#EF4444`, ตัวอักษร `#FFFFFF`
- **Disabled Button:** พื้น `#334155`, ตัวอักษร `#94A3B8` และต้องกดไม่ได้
- **Card/Modal:** พื้น `#151D35`, ขอบ `#334155`, มุมโค้ง 12–16 px
- **Input:** พื้น `#0F172A`, ขอบ `#334155`, Focus ring `#C4B5FD`
- **Progress Bar:** Track `#334155`, Progress `#7C3AED`; เมื่อ Pause ใช้ `#F59E0B`
- **Success/Warning/Error:** ต้องมี Icon และข้อความร่วมกับสีทุกครั้ง

### 11.5 Typography

- ภาษาไทยใช้ **Noto Sans Thai** หรือ **IBM Plex Sans Thai**
- ภาษาอังกฤษและตัวเลขใช้ฟอนต์เดียวกันหรือ **Inter**
- Body text และข้อความคำแนะนำ/Error ต้องมีขนาดไม่น้อยกว่า 16 px
- Line height อย่างน้อย 1.5 และห้ามใช้ข้อความสีเทาอ่อนมากบนพื้น Dark Navy

### 11.6 Accessibility และ Acceptance Criteria

- ข้อความปกติต้องมี Contrast ratio อย่างน้อย **4.5:1**
- ข้อความขนาดใหญ่และองค์ประกอบ UI ต้องมี Contrast ratio อย่างน้อย **3:1**
- ทุกปุ่มและ Input ต้องใช้ Keyboard ได้และมี Focus indicator ชัดเจน
- พื้นที่กดต้องมีขนาดอย่างน้อย 44 × 44 px
- Error message ต้องบอกทั้งสาเหตุและวิธีแก้ ไม่แสดงเพียงสีแดง
- รองรับการขยายข้อความอย่างน้อย 200% โดยข้อมูลสำคัญไม่ถูกตัด
- ต้องทดสอบ Horseshoe UI สำหรับภาวะตาบอดสี และต้องเข้าใจสถานะได้โดยไม่พึ่งสี

### 11.7 Responsive Layout

- Desktop: แสดง Horseshoe UI และคำแนะนำแบบสองคอลัมน์
- Tablet/Mobile: เรียง Horseshoe UI เหนือคำแนะนำเป็นคอลัมน์เดียว
- ห้ามย่อ Horseshoe UI จน Label ของ TP9, AF7, AF8 และ TP10 อ่านไม่ชัด
- Modal เชื่อมต่ออุปกรณ์ต้องไม่เกินความสูงหน้าจอและเลื่อนเนื้อหาได้

---

## 12. บันทึกความสำเร็จของการพัฒนาและทดสอบระบบ (Final Implementation & Verification Status)

ระบบพัฒนาเสร็จสิ้นสมบูรณ์และผ่านการตรวจจับคุณสมบัติตามมาตรฐานการออกแบบ (PRD v2.0) ทุกข้อดังนี้:

### 12.1 การจัดการ Backend & Database (สำเร็จ 100%)

- **MySQL Integration:** เชื่อมต่อกับ MySQL Container ได้สมบูรณ์
- **Database Seeding:** สคริปต์ `seed.py` สร้างโครงสร้างตารางข้อมูลและผู้ใช้/สิทธิ์ระบบ (admin/user) ได้อย่างสมบูรณ์
- **Auth Flow:** เข้าสู่ระบบและลงทะเบียนผ่าน API `/auth/login` และ `/auth/register` ได้รับ JWT Tokens และจำแนกผู้ใช้ได้ถูกต้อง
- **Pydantic Config:** เปิดใช้ `extra="ignore"` ในการตั้งค่าเพื่อรองรับค่า `.env` ที่กำหนดเพิ่มเติมนอกคลาส
- **Bcrypt Fix:** แก้ไขปัญหาการเข้ารหัสรหัสผ่านให้เข้ากันได้ระหว่าง `passlib` และ `bcrypt` ในระดับระบบจำลอง

### 12.2 การจัดการ Frontend (สำเร็จ 100%)

- **Angular 19 Build:** แอปพลิเคชันผ่านการคอมไพล์สำเร็จ (0 errors) พร้อมการใช้ HMR
- **JWT Persistence & Reload Fix:** เพิ่ม `APP_INITIALIZER` ใน `app.config.ts` เพื่อป้องกันหน้าเว็บของ Admin ถูกส่งกลับไปยังหน้า Login ขณะทำการดึงข้อมูลใหม่หลัง Refresh หน้าจอ
- **Horseshoe Sensor UI:** รองรับการดึงสถานะเซนเซอร์ 4 จุด (TP9, AF7, AF8, TP10) แบบ Real-time ครบถ้วนตามมาตรฐานการออกแบบสีสถานะและไอคอนนำทาง
- **Unified Navigation:** แผงควบคุม (Dashboard) และหน้าจัดการประวัติการ์ตูน (History Gallery) สามารถดึงข้อมูลผ่าน API Interceptor โดยอัตโนมัติ

---

## 13. โหมดเก็บข้อมูลวิจัย EEG และ Machine Learning

โหมดเก็บข้อมูลวิจัยแยกจากโหมดสร้างการ์ตูนสำหรับผู้ใช้ทั่วไป โหมดใช้งานจริงยังสามารถใช้ Baseline 20 วินาทีและสะสมสัญญาณสะอาด 30 วินาทีตาม State Machine เดิมได้ แต่โหมดวิจัยต้องบันทึกตามระเบียบวิธีต่อไปนี้เพื่อสร้างชุดข้อมูลฝึกที่ตรวจสอบย้อนกลับได้

### 13.1 กลุ่มตัวอย่างและจำนวนข้อมูล

- เป้าหมาย 30 คน ทดลองนำร่อง 5 คนก่อนเก็บจริง และใช้ขั้นต่ำ 20 คนได้เฉพาะเมื่อรายงานข้อจำกัด
- Baseline ลืมตา 60 วินาทีและหลับตา 60 วินาทีต่อคน
- อารมณ์ 4 ประเภท ได้แก่ `happy`, `sad`, `stressed`, `excited`
- อารมณ์ละ 3 รอบ รอบละ 60 วินาที รวม 12 รอบต่อคน
- พักระหว่างรอบ 30–45 วินาที และสลับลำดับสิ่งกระตุ้นระหว่างผู้เข้าร่วม
- เป้าหมายรวม 360 Trial หรืออารมณ์ละ 90 Trial เมื่อเก็บครบ 30 คน

### 13.2 Ground Truth และคุณภาพข้อมูล

- หลังแต่ละ Trial ต้องเก็บ `self_report_emotion`, Valence 1–9, Arousal 1–9 และ Confidence 1–5
- ใช้ `self_report_emotion` เป็น Label หลัก สิ่งกระตุ้นทำหน้าที่เป็น `target_emotion` เท่านั้น
- ถ้า Self-report ไม่ตรง Target แต่ Confidence ≥ 3 ให้ใช้ Self-report และบันทึก mismatch
- ถ้า Confidence < 3 ให้ตั้ง `valid_label=false` และไม่นำ Trial เข้าชุดฝึกหลัก
- ต้องบันทึก Sensor quality และ Artifact เช่น การกะพริบตา พูด ไอ ขยับศีรษะ หรืออุปกรณ์หลุด
- ห้ามบันทึกชื่อผู้เข้าร่วมในไฟล์ EEG ใช้รหัส `P001` เป็นต้น

### 13.3 Dataset Schema

| กลุ่ม      | Required fields                                                                              |
| ---------- | -------------------------------------------------------------------------------------------- |
| Identity   | `participant_id`, `session_id`, `trial_id`, `stimulus_id`                                    |
| Raw EEG    | `timestamp`, `tp9`, `af7`, `af8`, `tp10`, `sampling_rate=256`                                |
| Markers    | `phase`, `stimulus_start`, `stimulus_end`, `rest_start`, `rest_end`                          |
| Quality    | `tp9_quality`, `af7_quality`, `af8_quality`, `tp10_quality`, `artifact_note`, `valid_signal` |
| Labels     | `target_emotion`, `self_report_emotion`, `valence`, `arousal`, `confidence`, `valid_label`   |
| Provenance | `feature_version`, `preprocessing_version`, `collected_at`                                   |

### 13.4 Preprocessing และ Feature Schema

- Band-pass 1–40 Hz และ Notch filter 50 Hz
- Epoch 2 วินาที ซ้อนทับ 50% โดยไม่ข้าม Trial หรือ Pause/Resume boundary
- Absolute และ Relative Alpha/Beta power ของ TP9, AF7, AF8, TP10
- `faa = ln(alpha_af8) - ln(alpha_af7)`
- `arousal_index = ln(beta_power / alpha_power)`
- ค่าเฉลี่ย ส่วนเบี่ยงเบนมาตรฐาน และ Quality summary ต่อ Epoch/Trial
- ทุกแถว Feature ต้องมี `participant_id`, `trial_id`, `label` และ `feature_version`

### 13.5 Training Pipeline และ Model Registry

1. ตรวจ Schema และคัด Trial ที่ `valid_signal=true` และ `valid_label=true`
2. แบ่ง Fold ตาม `participant_id`
3. เปรียบเทียบ Logistic Regression, SVM และ Random Forest
4. ทำ Scaling และ Hyperparameter tuning ภายใน Training fold เท่านั้น
5. เลือกจาก Macro F1 และตรวจ Accuracy, Precision, Recall, F1 รายคลาส และ Confusion Matrix
6. บันทึก `preprocessor`, `classifier`, `feature_order`, `label_mapping`, `training_participants`, metrics และ version เป็น Artifact เดียวกัน
7. Endpoint สำหรับ Inference ต้องปฏิเสธ Feature schema หรือ Model version ที่ไม่ตรงกัน

### 13.6 Acceptance Criteria สำหรับงานวิจัยและ ML

- **AC-ML-01:** เก็บ Pilot ครบ 5 คนและบันทึกปัญหาก่อนเริ่ม Main collection
- **AC-ML-02:** Participant หนึ่งคนต้องมี Baseline สองแบบและ Trial เป้าหมาย 12 รอบ เว้นแต่มีเหตุถอนตัวหรือข้อมูลเสียที่บันทึกไว้
- **AC-ML-03:** ทุก Raw EEG file มี 4 Channel, timestamp, marker และ quality field
- **AC-ML-04:** ทุก Trial ที่ใช้ฝึกมี Self-report และ Confidence
- **AC-ML-05:** ไม่มี `participant_id` ซ้ำระหว่าง Train และ Test ในแต่ละ Fold
- **AC-ML-06:** รายงานผลครบ Accuracy, per-class Precision/Recall/F1, Macro F1 และ Confusion Matrix
- **AC-ML-07:** โมเดลใช้งานจริงโหลดพร้อม Preprocessor, Feature order, Label mapping และ Version ที่ตรงกัน
- **AC-ML-08:** UI และรายงานระบุว่าผลอารมณ์เป็นการประมาณเพื่อการสร้างสรรค์ ไม่ใช่การวินิจฉัยทางการแพทย์
