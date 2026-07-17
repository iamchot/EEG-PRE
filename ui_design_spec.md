# Dream Comicverse — UI Screen Design Specification

**Version:** 1.0  
**Updated:** July 2026  
**Based on:** PRD v2.0 §11 + Prototype screenshots  
**Color System:** Dark Navy–Purple (`#080D21` bg / `#7C3AED` primary)

---

## สารบัญ

| # | หน้า | Role |
|---|------|------|
| 0 | [Login / Register](#0-login--register) | Guest |
| 1 | [Dashboard (User)](#1-dashboard-user) | User |
| 2 | [Create Dream — Story Setup](#2-create-dream--story-setup) | User |
| 3 | [EEG Session — Device & Sensor](#3-eeg-session--device--sensor) | User |
| 4 | [EEG Session — Baseline & Recording](#4-eeg-session--baseline--recording) | User |
| 5 | [Emotion Confirmation](#5-emotion-confirmation) | User |
| 6 | [Comic Generation (Loading)](#6-comic-generation-loading) | User |
| 7 | [Comic View](#7-comic-view) | User |
| 8 | [Rating & Feedback](#8-rating--feedback) | User |
| 9 | [Timeline / History](#9-timeline--history) | User |
| 10 | [Personas](#10-personas) | User |
| 11 | [Admin — Dashboard](#11-admin--dashboard) | Admin |
| 12 | [Admin — User Management](#12-admin--user-management) | Admin |
| 13 | [Admin — EEG Dataset](#13-admin--eeg-dataset) | Admin |

---

## Layout Shell

### Sidebar (ทุกหน้าที่ Login แล้ว)
```
┌────────────────────┐
│  🧠 Dream          │
│     Comicverse     │
├────────────────────┤
│                    │
│  ■ Dashboard       │  ← User & Admin
│  ✦ Create Dream    │  ← User only
│  ◎ Personas        │  ← User only
│  ◷ Timeline        │  ← User only
│  ─────────────     │
│  ⚙ Admin Panel    │  ← Admin only (conditional)
│                    │
├────────────────────┤
│  ● CONNECTED DEV.  │
│  Mock EEG Headset  │
│  ─────────────     │
│  [A] Username      │
│      role          │
│  [ออกจากระบบ]      │
└────────────────────┘
```

**Design Notes:**
- Sidebar width: 240 px, `bg: #0F172A`, border-right: `#334155`
- Active nav: `bg: rgba(124,58,237,0.15)`, `color: #7C3AED`, font-weight 600
- Device indicator: green dot (`#22C55E`) + device name in small text
- Bottom avatar: gradient circle with first letter of username

---

## 0. Login / Register

### Layout
```
┌──────────────────────────────────────┐
│            (full-screen dark bg)      │
│                                       │
│          🧠                           │
│     Dream Comicverse                  │
│  เข้าสู่ระบบเพื่อสร้างการ์ตูน...      │
│                                       │
│  ┌─────────────────────────────────┐ │
│  │  อีเมล                          │ │
│  │  [_____________________________]│ │
│  │  รหัสผ่าน                       │ │
│  │  [_____________________________]│ │
│  │                                 │ │
│  │  [     เข้าสู่ระบบ      ]       │ │
│  │                                 │ │
│  │  ยังไม่มีบัญชี? สมัครสมาชิก     │ │
│  └─────────────────────────────────┘ │
└──────────────────────────────────────┘
```

**Components:**
- Card: `bg: #151D35`, border: `#334155`, border-radius: 16px, padding 40px
- Input: `bg: #0F172A`, border: `#334155`, focus-ring: `#C4B5FD`
- Button Primary: `bg: #7C3AED`, hover: `#6D28D9`, width: 100%
- Error message: red icon + text (not color alone)

---

## 1. Dashboard (User)

> อ้างอิง screenshot: "Welcome back, Traveler." ทั้ง 2 แบบ

### Layout
```
┌──────────┬─────────────────────────────────────────────┐
│ SIDEBAR  │  Welcome back, [username]. 👋                │
│          │  Ready to visualize your subconscious?       │
│          │                                              │
│          │  ┌─────────────────────────────────────────┐│
│          │  │  Create a New Dream Comic                ││
│          │  │  Connect your thoughts and emotions...   ││
│          │  │  [🧠 Start Dreaming]                     ││
│          │  └────────────────┬────────────────────────┘│
│          │                   │ Latest Generated Comic  ││
│          │                   │ [comic thumbnail 4-panel]│
│          │                   │ ⭐⭐⭐⭐ Rate satisfaction│
│          │                   │ [View Details]           │
│          │                   └────────────────────────┘│
│          │                                              │
│          │  ┌──────────────┬──────────────┬───────────┐│
│          │  │ EEG Sessions │Emotion Dist. │Comic Styles││
│          │  │    🧠 24     │  🍩 Donut    │ Bar chart ││
│          │  │  Total sess. │ Chart        │           ││
│          │  └──────────────┴──────────────┴───────────┘│
│          │                                              │
│          │  Recent Dream Comics                         │
│          │  ┌──────┬──────┬──────┬──────┐             │
│          │  │Comic1│Comic2│Comic3│Comic4│             │
│          │  │Excited│Sad  │Happy │Curious│            │
│          │  └──────┴──────┴──────┴──────┘             │
└──────────┴─────────────────────────────────────────────┘
```

**Stat Cards (3 cards row):**

| Card | Icon | Content |
|------|------|---------|
| EEG Sessions | 🧠 | จำนวน session ที่บันทึก (number large) |
| Emotion Distribution | 🍩 | Donut chart: Happy/Sad/Stressed/Excited |
| Comic Style Popularity | 📊 | Bar list: Manga, Webtoon, Comic, American Comic |

**Hero CTA Banner:**
- Gradient bg: `linear-gradient(135deg, #7C3AED 0%, #A78BFA 100%)`
- Button: white on purple, icon 🧠
- Right column: thumbnail of latest comic + star rating

**Recent Comics Strip:**
- 4-column grid, each card: thumbnail + emotion tag badge + style + title
- Hover: scale + border glow

---

## 2. Create Dream — Story Setup

> อ้างอิง screenshot: form มี emotion selector + story fields + art style

### Layout
```
┌──────────┬─────────────────────────────────────────────┐
│ SIDEBAR  │  Create Dream                                │
│          │  ─────────────────────────────────────────  │
│          │                                              │
│          │  1. เลือกสภาวะอารมณ์ที่คุณต้องการถ่ายทอด   │
│          │  ┌─────────┐┌─────────┐┌────────┐┌───────┐ │
│          │  │😊 มีความ ││😢 เศร้า ││😤 ตื่น ││😰 เค  │ │
│          │  │   สุข    ││         ││  เต้น  ││  รียด │ │
│          │  └─────────┘└─────────┘└────────┘└───────┘ │
│          │                                              │
│          │  2. Tell your story (เรื่องราวของคุณ)       │
│          │  ┌── ตัวละครหลัก (MAIN CHARACTER) ─────────┐│
│          │  │  [ก้อง (ชาย Male), 20   ▾]              ││
│          │  └──────────────────────────────────────────┘│
│          │  ┌── ตัวละครรอง 1 ──┐  ┌── ตัวละครรอง 2 ──┐│
│          │  │  [โอม         ▾] │  │ [ไม่มี (None)  ▾]││
│          │  └──────────────────┘  └──────────────────┘ │
│          │  ┌── เหตุการณ์หลัก ─────────────────────────┐│
│          │  │  เช่น กำลังเล่นเกมในบ้ากรอบจก...        ││
│          │  └──────────────────────────────────────────┘│
│          │  [จุดพีค] ________________  [บทสรุป] ______  │
│          │                                              │
│          │  3. Choose Art Style                         │
│          │  [Manga] [Webtoon ✓] [Comic] [American Comic] │
│          │                                              │
│          │          [Next to Brain Scan  →]             │
└──────────┴─────────────────────────────────────────────┘
```

**Step Indicator (top of page):**
```
1 Story Setup  ──  2 Brain Scan  ──  3 Confirm Emotion  ──  4 Comic
```

**Emotion Buttons (Step 1):**
- 4 pill buttons, unselected: `border: #334155, bg: #151D35`
- Selected: `border: #7C3AED, bg: rgba(124,58,237,0.15), font-weight: 600`

**Story Fields (Step 2):**
- Main character dropdown → loads from Personas list
- Supporting 1 & 2 dropdowns
- Textarea fields: เหตุการณ์หลัก (Main Event), จุดพีค (Peak), บทสรุป (Ending)
- "จัดการตัวละคร" link top-right → goes to Personas page

**Art Style (Step 3):**
- Toggle buttons: Manga, Webtoon, Comic, American Comic
- Selected: `bg: #7C3AED`, unselected: `bg: #151D35 border: #334155`

**CTA:** `[Next to Brain Scan →]` — primary button, full-width bottom, disabled until all required fields filled

---

## 3. EEG Session — Device & Sensor

### Phase: DISCOVERING → DEVICE_CONFIRMATION → FITTING

```
┌──────────┬─────────────────────────────────────────────┐
│ SIDEBAR  │  EEG Session                                 │
│          │  ─────────────────────────────────────────  │
│          │  Step: 1 Device  2 Sensor  3 Baseline  4 Rec │
│          │                                              │
│          │  ┌─────────────────┐  ┌──────────────────┐  │
│          │  │  Horseshoe UI   │  │  Stage Panel     │  │
│          │  │                 │  │                  │  │
│          │  │    TP9   TP10   │  │  Connect Muse 2  │  │
│          │  │   [?]     [?]   │  │                  │  │
│          │  │  AF7     AF8    │  │  ค้นหาอุปกรณ์... │  │
│          │  │  [?]     [?]    │  │                  │  │
│          │  │                 │  │  [Scan Device]   │  │
│          │  │  Signal: 0%     │  │                  │  │
│          │  │  ยังไม่มีข้อมูล │  │  (Found devices) │  │
│          │  └─────────────────┘  │  □ Muse-A9C7     │  │
│          │                       │  [Connect Device]│  │
│          │                       └──────────────────┘  │
└──────────┴─────────────────────────────────────────────┘
```

**Horseshoe UI (Left Panel):**
- Helmet shape showing TP9 (left ear), AF7 (left forehead), AF8 (right forehead), TP10 (right ear)
- Each sensor node: circle with color + icon + state text
- Progress bar: "สัญญาณรวม: 0%" + descriptive text
- States: unknown=gray`?`, poor=yellow`!`, good=green`✓`, stale=red`×`

**Stage Panel (Right Panel):**
- Changes content based on EEG session phase
- Device list: card-style selectable rows, selected = purple border
- Hair prep tips: checklist with icons

---

## 4. EEG Session — Baseline & Recording

### Phase: BASELINE → READY → RECORDING → PAUSED_SIGNAL_QUALITY

```
┌──────────┬─────────────────────────────────────────────┐
│ SIDEBAR  │  EEG Session                    [WS Online] │
│          │  ─────────────────────────────────────────  │
│          │                                              │
│          │  ┌─────────────────┐  ┌──────────────────┐  │
│          │  │  Horseshoe UI   │  │  🧠 Baseline     │  │
│          │  │  (all green ✓)  │  │                  │  │
│          │  │                 │  │  เก็บ Resting     │  │
│          │  │  TP9 ✓  TP10 ✓  │  │  State 20 วินาที │  │
│          │  │  AF7 ✓  AF8 ✓  │  │                  │  │
│          │  │                 │  │  ██████░░░░ 11s  │  │
│          │  │  Signal: 97%    │  │  ผ่อนคลาย...     │  │
│          │  │  พร้อมเริ่มวัด  │  │                  │  │
│          │  └─────────────────┘  └──────────────────┘  │
│          │                                              │
│          │  (Recording phase)                           │
│          │  ┌─────────────────┐  ┌──────────────────┐  │
│          │  │  Horseshoe UI   │  │  ⏺ Recording     │  │
│          │  │  (some poor!)   │  │                  │  │
│          │  │  TP9 ! TP10 ✓  │  │  ██████████░ 18s │  │
│          │  │  AF7 ✓  AF8 ✓  │  │  Accepted: 18s   │  │
│          │  │  Signal: 74%    │  │  Wall clock: 24s │  │
│          │  │  ⚠ TP9 ปรับ    │  │                  │  │
│          │  └─────────────────┘  │  ⏸ PAUSED        │  │
│          │                       │  TP9 ต้องเป็น good│  │
│          │                       └──────────────────┘  │
└──────────┴─────────────────────────────────────────────┘
```

**Progress Bar States:**
- Baseline: purple fill, text "กำลังเก็บ Baseline..."
- Recording active: purple fill animated, "Accepted: Xs / 30s"
- Paused: orange fill, "⏸ หยุดชั่วคราว — รอสัญญาณดี"
- Timeout warning: red border on card

---

## 5. Emotion Confirmation

### Phase: EMOTION_CONFIRMATION

```
┌──────────┬─────────────────────────────────────────────┐
│ SIDEBAR  │  ผลการวิเคราะห์อารมณ์                       │
│          │  ─────────────────────────────────────────  │
│          │                                              │
│          │  ┌──────────────────────────────────────┐   │
│          │  │  🧠 ระบบตรวจพบ...                   │   │
│          │  │                                       │   │
│          │  │      😤 เครียด (Stressed)             │   │
│          │  │                                       │   │
│          │  │  Valence : -0.42  Arousal : +1.18     │   │
│          │  │  delta_faa: -0.31  delta_arous: +0.76 │   │
│          │  │  Quality: 87% (26.1s clean / 30s)    │   │
│          │  │                                       │   │
│          │  │  ──────────────────────────────────── │   │
│          │  │  ระบบจะใช้อารมณ์นี้สร้างการ์ตูน     │   │
│          │  │                                       │   │
│          │  │  [✓ ยืนยัน — สร้างการ์ตูน]           │   │
│          │  │  [↺ วัดใหม่]                          │   │
│          │  └──────────────────────────────────────┘   │
└──────────┴─────────────────────────────────────────────┘
```

**Emotion Display:**
- Large emoji + Thai name + English name
- Valence/Arousal values with sign and 2 decimals
- Quality summary bar (% of 30s accepted)
- Two CTA buttons: Confirm (primary) + Remeasure (secondary/destructive)

---

## 6. Comic Generation (Loading)

```
┌──────────┬─────────────────────────────────────────────┐
│ SIDEBAR  │  กำลังสร้างการ์ตูน...                       │
│          │  ─────────────────────────────────────────  │
│          │                                              │
│          │  ┌──────────────────────────────────────┐   │
│          │  │                                       │   │
│          │  │     🧠 ─────── ✍️ ─────── 🎨          │   │
│          │  │  อารมณ์    สร้างบท    วาดภาพ          │   │
│          │  │                                       │   │
│          │  │   ████████████░░░░░░░░░  Step 2/3    │   │
│          │  │   กำลังแต่งบทสนทนา 4 ช่อง...         │   │
│          │  │                                       │   │
│          │  │   Panel 1 ✓  Panel 2 ⏳  Panel 3 ○  Panel 4 ○│
│          │  │                                       │   │
│          │  └──────────────────────────────────────┘   │
└──────────┴─────────────────────────────────────────────┘
```

**Progress Steps:**
1. ส่งอารมณ์และ Prompt ไป Gemini ✓
2. Gemini สร้างบทสนทนา 4 ช่อง ⏳
3. ComfyUI วาดภาพ Panel 1–4 ○

**Panel Status Grid:** 4 cells, each: loading spinner / checkmark / placeholder

---

## 7. Comic View

> อ้างอิง screenshot: "Level Up: Reality Glitch" page

```
┌──────────┬─────────────────────────────────────────────┐
│ SIDEBAR  │  ← Level Up: Reality Glitch                 │
│          │     3/16/2026, 12:27:30 AM                   │
│          │                              [+ สร้างใหม่]  │
│          │  ┌──────────────┐  ┌──────────────────────┐ │
│          │  │ 🧠 สภาวะอารมณ์│  │ 🎨 สไตล์ภาพ         │ │
│          │  │   เครียด      │  │  Webtoon             │ │
│          │  └──────────────┘  └──────────────────────┘ │
│          │                                              │
│          │  ┌──────────────────────────────────────┐   │
│          │  │  [1]                                  │   │
│          │  │  "Just one more combo and this        │   │
│          │  │   legendary loot is mine!"            │   │
│          │  │                                       │   │
│          │  │   [Comic Panel Image — large]         │   │
│          │  │                                       │   │
│          │  └──────────────────────────────────────┘   │
│          │  ┌──────────────────────────────────────┐   │
│          │  │  [2]  [Panel 2 Image]                 │   │
│          │  │  "..."                                 │   │
│          │  └──────────────────────────────────────┘   │
│          │  (panels 3, 4 below...)                      │
│          │                                              │
│          │  [↓ ส่วนประเมินความพึงพอใจ ↓]              │
└──────────┴─────────────────────────────────────────────┘
```

**Comic Panel Layout:**
- Each panel: numbered badge + dialogue text box (speech bubble style) + full-width image
- Panels stacked vertically (Webtoon style) or 2×2 grid (Manga style) based on art_style
- Image: rounded corners, `object-fit: cover`, dark background while loading

**Meta Cards (top):**
- Left: Emotion card (icon + Thai name)  
- Right: Art style card (icon + style name)

**Header:**
- Back arrow (`←`) + comic title (generated from story)
- Timestamp
- `[+ สร้างการ์ตูนเรื่องใหม่]` button top-right

---

## 8. Rating & Feedback

> อ้างอิง screenshot: "ส่วนการประเมินความพึงพอใจ" below comic view

```
┌──────────┬─────────────────────────────────────────────┐
│ SIDEBAR  │  (below comic panels)                       │
│          │                                              │
│          │  ┌──────────────────────────────────────┐   │
│          │  │  ส่วนการประเมินความพึงพอใจ            │   │
│          │  │  ช่วยเราพัฒนาการประสบการณ์ให้ดีขึ้น  │   │
│          │  │                                       │   │
│          │  │  คะแนนความพึงพอใจ (1-5 ดาว)          │   │
│          │  │  ★ ★ ★ ★ ★                            │   │
│          │  │  (interactive star rating)             │   │
│          │  │                                       │   │
│          │  │  ข้อเสนอแนะเพิ่มเติม                  │   │
│          │  │  ┌─────────────────────────────────┐  │   │
│          │  │  │ บอกเราว่าคุณชอบอะไร หรือ...     │  │   │
│          │  │  └─────────────────────────────────┘  │   │
│          │  │                                       │   │
│          │  │  [✉ ส่งแบบประเมิน]                   │   │
│          │  └──────────────────────────────────────┘   │
│          │                                              │
│          │  [+ สร้างการ์ตูนเรื่องใหม่] (bottom link)   │
└──────────┴─────────────────────────────────────────────┘
```

**Star Rating:**
- 5 stars, interactive hover effect
- Selected stars: `#F59E0B` (amber/gold)
- Unselected: `#334155`

**Submit Button:** Primary purple, with send icon ✉

---

## 9. Timeline / History

```
┌──────────┬─────────────────────────────────────────────┐
│ SIDEBAR  │  ประวัติผลงาน                                │
│          │  ─────────────────────────────────────────  │
│          │                                              │
│          │  ┌─────────┐  ┌─────────┐  ┌─────────┐     │
│          │  │ [4-panel │  │ [4-panel │  │ [4-panel│     │
│          │  │  thumb]  │  │  thumb]  │  │  thumb] │     │
│          │  │          │  │          │  │         │     │
│          │  │Title...  │  │Title...  │  │Title... │     │
│          │  │😤 เครียด │  │😊 มีความ │  │😢 เศร้า │     │
│          │  │Webtoon   │  │สุข Manga │  │Comic    │     │
│          │  │3/16/2026 │  │3/10/2026 │  │3/5/2026 │     │
│          │  └─────────┘  └─────────┘  └─────────┘     │
│          │                                              │
│          │  (more rows...)                              │
└──────────┴─────────────────────────────────────────────┘
```

**Grid Layout:** 3-column masonry/equal grid  
**Comic Card:**
- Thumbnail: 2×2 mini panel grid preview
- Emotion badge: colored pill (`happy`=green, `stressed`=red, etc.)
- Art style text, date
- Hover → scale + border glow, click → `/comic/:id`

**Empty State:** illustration + "ยังไม่มีผลงาน กด Create Dream เพื่อเริ่ม"

---

## 10. Personas

```
┌──────────┬─────────────────────────────────────────────┐
│ SIDEBAR  │  Personas                     [+ Add Persona]│
│          │  ─────────────────────────────────────────  │
│          │                                              │
│          │  ┌──────────────────────────────────────┐   │
│          │  │ [G] ก้อง (ชาย, 20)    [Manga] [Edit] │   │
│          │  │     เสื้อยืดดำ ผมสั้น บุคลิกขี้เล่น│   │
│          │  └──────────────────────────────────────┘   │
│          │  ┌──────────────────────────────────────┐   │
│          │  │ [O] โอม                [Webtoon][Edit]│   │
│          │  │     ตัวละครสนับสนุน...                │   │
│          │  └──────────────────────────────────────┘   │
│          │                                              │
│          │  (Add Form — slide down)                     │
│          │  ┌──────────────────────────────────────┐   │
│          │  │  ชื่อตัวละคร: [____________]          │   │
│          │  │  รายละเอียด: [textarea____________]   │   │
│          │  │  สไตล์:      [Manga ▾]               │   │
│          │  │  [Save Persona] [Cancel]              │   │
│          │  └──────────────────────────────────────┘   │
└──────────┴─────────────────────────────────────────────┘
```

---

## 11. Admin — Dashboard

> Role: Admin only

```
┌──────────┬─────────────────────────────────────────────┐
│ SIDEBAR  │  ⚙️ Admin Panel                              │
│ (admin   │  ─────────────────────────────────────────  │
│  view)   │  [📊 สถิติ] [👥 ผู้ใช้] [🧠 Dataset]        │
│          │                                              │
│          │  ┌────────┐  ┌────────┐  ┌────────┐         │
│          │  │  👥    │  │  🎨    │  │  ⭐    │         │
│          │  │  1     │  │  0     │  │  0.0   │         │
│          │  │ผู้ใช้  │  │การ์ตูน │  │Rating  │         │
│          │  └────────┘  └────────┘  └────────┘         │
│          │                                              │
│          │  ┌──────────────────────────────────────┐   │
│          │  │  การกระจายอารมณ์ (Emotion Distribution)│   │
│          │  │                                       │   │
│          │  │  😊 มีความสุข  ████████████░░  48    │   │
│          │  │  😤 เครียด     ████████░░░░░░  32    │   │
│          │  │  😢 เศร้า      █████░░░░░░░░░  20    │   │
│          │  │  🎉 ตื่นเต้น   ███░░░░░░░░░░░  12    │   │
│          │  └──────────────────────────────────────┘   │
└──────────┴─────────────────────────────────────────────┘
```

**Stat Cards:** 3-column grid, gradient number text, icon  
**Emotion Distribution:** horizontal bar chart, purple fill  
**Future:** Line chart for sessions over time (weekly/monthly)

---

## 12. Admin — User Management

```
┌──────────┬─────────────────────────────────────────────┐
│ SIDEBAR  │  ⚙️ Admin Panel                              │
│          │  [📊 สถิติ] [👥 ผู้ใช้] [🧠 Dataset]        │
│          │                                              │
│          │  ┌─────────────────────────────────────────┐│
│          │  │ ID │ Username │ Email │ Role │สถานะ│วันที่│จัดการ││
│          │  ├────┼──────────┼───────┼──────┼─────┼─────┼──────┤│
│          │  │  1 │ admin    │ admin │[admin]│[✓]  │01/07│ -    ││
│          │  │  2 │ user1    │ u1@.. │[user] │[✓]  │05/07│[ระงับ][ลบ]││
│          │  │  3 │ user2    │ u2@.. │[user] │[✕]  │06/07│[เปิด][ลบ] ││
│          │  └─────────────────────────────────────────┘│
└──────────┴─────────────────────────────────────────────┘
```

**Table Columns:** ID, Username, Email, Role (badge), Status (active/suspended badge), Date joined, Actions  
**Actions:** Suspend / Activate (toggle), Delete (destructive red)  
**Badges:** admin=purple, user=neutral, active=green, suspended=red

---

## 13. Admin — EEG Dataset

```
┌──────────┬─────────────────────────────────────────────┐
│ SIDEBAR  │  ⚙️ Admin Panel                              │
│          │  [📊 สถิติ] [👥 ผู้ใช้] [🧠 Dataset]        │
│          │                                              │
│          │  ┌─────────────────────────────────────────┐│
│          │  │ Session │ User │ Device  │ Status │ Time │ Date │ Action││
│          │  ├─────────┼──────┼─────────┼────────┼──────┼──────┼───────┤│
│          │  │   1     │  1   │ Muse-A9 │[compl] │ 89s  │07/07 │ [ลบ] ││
│          │  │   2     │  2   │ Muse-B3 │[timeout│ 120s │08/07 │ [ลบ] ││
│          │  └─────────────────────────────────────────┘│
│          │                                              │
│          │  [📥 Export CSV]  [📥 Export JSON]           │
└──────────┴─────────────────────────────────────────────┘
```

**Status Badges:** `completed`=green, `timeout`=red, `failed`=red, `cancelled`=neutral  
**Export Buttons:** CSV and JSON download, secondary button style  
**Note:** Links to raw_data_path file path (not inline data)

---

## Design Tokens Summary

```css
/* Colors */
--color-bg-primary:       #080D21;
--color-bg-secondary:     #0F172A;
--color-surface:          #151D35;
--color-surface-elevated: #1E293B;
--color-primary:          #7C3AED;
--color-primary-hover:    #6D28D9;
--color-secondary:        #A78BFA;
--color-text-primary:     #F8FAFC;
--color-text-secondary:   #CBD5E1;
--color-text-muted:       #94A3B8;
--color-border:           #334155;
--color-success:          #22C55E;
--color-warning:          #F59E0B;
--color-error:            #EF4444;
--color-neutral:          #64748B;

/* Typography */
--font-thai: 'Noto Sans Thai', 'IBM Plex Sans Thai', sans-serif;
--font-en:   'Inter', sans-serif;
/* min body text: 16px, line-height ≥ 1.5 */

/* Radius */
--radius-sm:  8px;
--radius-md:  12px;
--radius-lg:  16px;
--radius-xl:  24px;

/* Animation */
--transition-fast: 150ms ease;
--transition-base: 250ms ease;
```

---

## Accessibility Checklist

- [ ] All color states have icon + text (not color alone)
- [ ] Contrast ratio ≥ 4.5:1 for body text, ≥ 3:1 for large text/UI
- [ ] All interactive elements keyboard-accessible with visible focus ring (`#C4B5FD`)
- [ ] Touch targets ≥ 44×44 px
- [ ] Horseshoe UI tested for color-blindness (deuteranopia, protanopia)
- [ ] Error messages explain cause + fix, not just red color
- [ ] Text resizable to 200% without content clipping
- [ ] ARIA roles and labels on tabs, tables, sensor UI
