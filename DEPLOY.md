# แผนการ Deploy ระบบ Dream Comicverse (แบบไม่เสียค่าใช้จ่าย)

> เอกสารนี้จัดทำขึ้นเพื่อเป็นแนวทางและ Checklist สำหรับการนำระบบขึ้นใช้งานจริง (Production / Demo) โดยยังไม่แก้ไขโค้ดระบบในปัจจุบัน

---

## 1. ภาพรวมสถาปัตยกรรม (Free Tier Architecture)

```text
[Browser: Chrome / Edge (HTTPS)]
   ├── Web Bluetooth (Muse 2, 256 Hz) ──┐
   └── Angular Frontend                 │
         (Cloudflare Pages / Vercel)    │
                │                       │
                ▼ (HTTPS REST + WSS) ───┘
         [FastAPI Backend + WebSocket]
                │
                ├──► MySQL Database
                ├──► Gemini REST API (สร้างบท 4 ช่อง)
                └──► Image Generation:
                       ├── 1) ComfyUI (เครื่องตัวเองผ่าน Cloudflare Tunnel)
                       └── 2) Cloudflare Workers AI (Free Tier: FLUX.1-schnell)
```

---

## 2. ฝั่ง Frontend (Angular)

- **ผู้ให้บริการแนะนำ (ฟรี)**: **Cloudflare Pages** หรือ **Vercel** หรือ **Netlify**
- **ข้อกำหนดสำคัญ (Muse 2 Web Bluetooth)**:
  - API `navigator.bluetooth` ทำงานได้เฉพาะบน `http://localhost` หรือ **`https://`** เท่านั้น
  - แพลตฟอร์มข้างต้นให้ `HTTPS` ฟรีอัตโนมัติ
- **สิ่งที่ต้องเตรียมเมื่อถึงเวลา Deploy**:
  - ตั้งค่า `environment.prod.ts` ให้ชี้ `apiUrl` เป็น `https://<backend-domain>/api/v1` และ `wsUrl` เป็น `wss://<backend-domain>/api/v1` (ห้ามใช้ `ws://` บนเว็บ `https://` เพราะเบราว์เซอร์จะบล็อก Mixed Content)

---

## 3. ฝั่ง Backend (FastAPI + WebSocket) และ Database (MySQL)

### แนวทาง A: รันบนเครื่องตัวเอง / เซิร์ฟเวอร์มหาลัย + Cloudflare Tunnel *(แนะนำสำหรับเดโมและเก็บ Dataset)*
- **วิธีทำ**:
  1. รัน MySQL และ FastAPI (`uvicorn app.main:app --host 0.0.0.0 --port 8000`)
  2. เปิด `cloudflared tunnel --url http://localhost:8000` (หรือผูกโดเมนถาวรฟรีบน Cloudflare)
- **ข้อดี**:
  - ฟรี 100% ไม่มี Sleep timeout
  - รองรับทั้ง `https://` และ `wss://` (WebSocket)
  - ไฟล์ภาพ `.png` (`comfyui_outputs/`) และไฟล์คลื่น `.csv` (`collection_data/`) **ไม่สูญหาย**

### แนวทาง B: รัน Backend บน Cloud ฟรี + Cloud MySQL ฟรี
- **Backend**: Render (Free Web Service) / Koyeb / Fly.io
- **Database**: Aiven for MySQL (Free Tier) หรือ TiDB Cloud Serverless (Free)
- **ข้อควรระวังของ Free Tier**:
  - Render Free จะเข้าสู่โหมด Sleep หากไม่มีการใช้งาน 15 นาที (ตื่นช้า ~30 วินาทีในการเปิดครั้งแรก)
  - พื้นที่เก็บไฟล์ใน Container เป็นแบบชั่วคราว (Ephemeral) หากเครื่องรีสตาร์ท ไฟล์ `.png` และ `.csv` บนดิสก์จะหาย → หากใช้แนวทางนี้จริงจัง ควรย้ายการจัดเก็บไฟล์ไปไว้ที่ **Cloudflare R2 (Free 10 GB/เดือน)**

---

## 4. แผนการเชื่อมต่อการสร้างภาพ (Image Generation)

### รูปแบบที่ 1: ยังใช้ ComfyUI (ฟรี 100% — ตรงตามขอบเขตโครงงานที่ระบุ ComfyUI)
- เปิด ComfyUI (`127.0.0.1:8188`) บนเครื่องที่มีการ์ดจอ NVIDIA
- เปิด Cloudflare Tunnel ชี้มาที่พอร์ต `8188`:
  ```bash
  cloudflared tunnel --url http://localhost:8188
  ```
- นำ Public URL ที่ได้ไปใส่ใน `backend/.env`:
  ```env
  COMFYUI_URL=https://xxxx.trycloudflare.com
  ```
- **จุดเด่น**: ฟรี ไม่จำกัดจำนวนภาพ ไม่ต้องแก้โค้ดระบบ (Backend จะยิง `/prompt` และดึงภาพจาก `/view` มาเก็บเอง)

### รูปแบบที่ 2: ไม่ใช้ ComfyUI — ใช้ Cloudflare Workers AI (Free Tier)
- **เหมาะสำหรับ**: กรณีต้องการให้เว็บสร้างภาพได้ 24 ชม. โดยไม่ต้องเปิดเครื่องคอมพิวเตอร์ที่มี GPU ทิ้งไว้
- **โมเดลที่มีให้ใช้งานบน Server Cloudflare ทันที (ไม่ต้องโหลดลงเครื่อง)**:
  - `@cf/black-forest-labs/flux-1-schnell` (สร้างภาพฉาก, สัตว์ และองค์ประกอบตรง Prompt ได้ดีกว่า SD 1.5)
  - `@cf/stabilityai/stable-diffusion-xl-base-1.0`
- **โควตาฟรี**: 10,000 Neurons/วัน (รีเซ็ตทุกวัน) เพียงพอสำหรับสร้างภาพทดสอบและเดโมหลายสิบภาพต่อวันโดยไม่ต้องเสียค่าใช้จ่าย

### แผนปรับปรุงโค้ดในอนาคต (เมื่อพร้อมใช้งาน)
- เพิ่มตัวแปร `IMAGE_PROVIDER=comfyui | cloudflare | auto` ใน `backend/app/config.py` และ `backend/app/services/diffusion_service.py`:
  - `comfyui`: ใช้ `COMFYUI_URL` อย่างเดียว
  - `cloudflare`: ใช้ Cloudflare Workers AI อย่างเดียว
  - `auto`: ลองส่งไปที่ `COMFYUI_URL` ก่อน หากไม่ได้เปิด ComfyUI ไว้ ให้สลับไปใช้ Cloudflare Workers AI อัตโนมัติ

---

## 5. Checklist ก่อนขึ้น Production จริง

- [ ] อัปเดต `CORSMiddleware` ใน `backend/app/main.py` ให้ `allow_origins` อนุญาตโดเมน Frontend จริง (`https://...`)
- [ ] ตั้งค่า `SECRET_KEY` และ `APP_ENV=production` ใน `backend/.env`
- [ ] ตั้งค่า `environment.prod.ts` ของ Angular (`apiUrl` เป็น `https://...`, `wsUrl` เป็น `wss://...`)
- [ ] ตั้งค่า Reverse Proxy Timeout (ถ้าใช้ Nginx/Cloudflare) ให้ `proxy_read_timeout` >= `300s` เพื่อรองรับการสร้างภาพ 4 ช่อง
- [ ] ทดสอบ flow เต็มบน `https://`: Login → ต่อ Muse 2 (Web Bluetooth) → วัด Baseline → สร้างการ์ตูน 4 ช่อง → ให้คะแนนความพึงพอใจ
