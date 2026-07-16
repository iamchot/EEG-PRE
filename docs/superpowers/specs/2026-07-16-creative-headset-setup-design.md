# Creative Headset Setup - Design Specification

**Project:** Dream Comicverse
**Screen:** EEG Session - Device Connection and Sensor Check
**Approved direction:** Creative Headset Setup
**Date:** 2026-07-16

## 1. Purpose

Redesign the Muse 2 connection and sensor-check experience to feel simple, polished, and consistent with the dark Navy-Purple interface shown in the Chapter 3 PDF. The screen must communicate that Dream Comicverse is a creative entertainment product, not a medical application.

The redesign changes presentation and interaction hierarchy only. It does not change the existing EEG state machine, API contract, sensor-quality rules, or data processing.

## 2. Design Principles

- Present Muse 2 as a creative input device used to shape a comic.
- Use a restrained dark Navy-Purple visual language consistent with the PDF.
- Prefer clear Thai copy; retain Muse 2 and sensor identifiers in English.
- Show only information users need to complete the current step.
- Avoid clinical language, laboratory imagery, excessive metrics, glowing effects, and decorative gradients.
- Never communicate sensor status through color alone.

## 3. Page Structure

### 3.1 Header

The compact header contains:

- Title: `เชื่อมต่อ Muse 2`
- Supporting text: `เตรียมอุปกรณ์ให้พร้อมก่อนเริ่มสร้างเรื่องราว`
- A small local-service status at the right:
  - `ระบบพร้อม` when the local connection is available
  - `ยังไม่เชื่อมต่อ` when the local connection is unavailable

Do not use `Dream Lab Recording`, `WebSocket Online`, or other developer-facing terminology.

### 3.2 Progress

Replace the six dense progress items with four user-oriented steps:

1. `เชื่อมต่อ`
2. `ตรวจสัญญาณ`
3. `บันทึกอารมณ์`
4. `สร้างคอมิก`

The current step uses the primary purple color. Completed steps use a check mark and subdued green. Future steps remain neutral. Step labels must remain readable without relying on color.

### 3.3 Main Card

Use one primary card divided into two columns on desktop:

- Left: Muse 2 illustration and four sensor positions
- Right: current action, discovered devices, and concise guidance

The card becomes a single column on narrow screens, with the headset illustration above the controls.

## 4. Headset and Sensor Visualization

Use a simple SVG line illustration of a Muse-style headband rather than a realistic product image. The illustration remains visually quiet and uses neutral border colors.

Show the four required sensor locations:

- TP9 - หลังหูซ้าย
- AF7 - หน้าผากซ้าย
- AF8 - หน้าผากขวา
- TP10 - หลังหูขวา

Each sensor point includes:

- Sensor identifier
- Thai location
- State icon
- State label

State mapping:

| State | Color | Icon | User-facing label |
|---|---|---|---|
| `unknown` | Neutral gray | `…` | รอสัญญาณ |
| `poor` | Amber | `!` | ปรับตำแหน่ง |
| `good` | Green | `✓` | พร้อม |
| `stale` | Red | `×` | ขาดการเชื่อมต่อ |

Remove the large average-quality percentage. Replace it with a single summary:

- `พร้อมเริ่ม` when all four sensors are good
- `ปรับเซนเซอร์อีก N จุด` when one or more sensors require attention
- `กำลังรอสัญญาณ` before sensor data arrives

## 5. Device Connection States

### 5.1 Before Scan

Display:

- Heading: `ค้นหาอุปกรณ์ใกล้เคียง`
- One short instruction to turn on Muse 2 and Bluetooth
- Primary action: `ค้นหา Muse 2`

### 5.2 Scanning

Keep the layout stable. Replace the button content with a small spinner and `กำลังค้นหา…`. Do not add an animated background or full-page loading state.

### 5.3 Device Found

Display discovered devices as calm selectable rows containing:

- Device name
- Short connection hint or address in muted text
- Radio/check indicator

The selected device uses a purple border and a subtle tinted background. The primary action becomes `เชื่อมต่ออุปกรณ์`.

### 5.4 No Device Found

Display an inline, non-alarming message:

`ยังไม่พบ Muse 2 ลองตรวจสอบว่าอุปกรณ์เปิดอยู่และ Bluetooth พร้อมใช้งาน`

Provide `ค้นหาอีกครั้ง` as the primary action.

### 5.5 Local Service Unavailable

Display a compact warning explaining that the local connection service must be started before scanning. Do not expose internal API or WebSocket terminology.

## 6. Fitting and Signal Guidance

After connection, keep the same primary card and transition its right column to fitting guidance. Avoid opening a modal or replacing the entire page.

Show no more than three instructions at once:

1. เปิดบริเวณหน้าผากและหลังหูไม่ให้เส้นผมบัง
2. วางสายคาดให้กระชับแต่ไม่แน่นเกินไป
3. นั่งนิ่งและผ่อนคลายใบหน้าเมื่อเริ่มตรวจสัญญาณ

When a sensor is not good, show one contextual tip based on the affected location. Enable the Baseline action only when all four sensor states are `good`.

Primary action:

- Disabled: `รอสัญญาณให้พร้อมครบ 4 จุด`
- Enabled: `เริ่มบันทึกค่าพื้นฐาน`

## 7. Visual Language

- Background and surfaces follow the existing dark Navy palette.
- Purple is reserved for the current step, selected device, focus state, and primary action.
- Use flat surfaces with a subtle border and soft shadow.
- Avoid purple-to-pink button gradients, strong glows, glass effects, decorative orbs, and excessive rounded cards.
- Use one main card and small supporting status elements instead of multiple nested cards.
- Maintain at least 4.5:1 contrast for body text.
- Interactive targets must be at least 44 by 44 pixels.
- Keyboard focus must remain clearly visible.

## 8. Entertainment Positioning

Place a quiet note below the main card:

`ข้อมูลอารมณ์ใช้เพื่อสร้างสรรค์คอมิกและความบันเทิง ไม่ใช่การวินิจฉัยทางการแพทย์`

Do not use medical symbols, diagnostic language, health scores, patient terminology, or claims about mental-health accuracy.

## 9. Responsive Behavior

- Desktop: two-column main card, with the headset visualization occupying approximately 42 percent of the width.
- Tablet: retain two columns when space permits; reduce padding and step-label spacing.
- Mobile: stack the visualization above the controls, allow the progress row to scroll or simplify labels without hiding the current step, and make primary actions full width.
- No content may clip at 200 percent browser zoom.

## 10. Component Boundaries

### `EegSessionComponent`

Responsible for:

- Page header and four-step progress
- Current phase and device actions
- Connection, fitting, and Baseline call-to-action content
- Existing API and WebSocket interactions

### `HorseshoeSensorComponent`

Responsible for:

- Headset SVG
- Four sensor markers
- Accessible sensor-state labels
- Readiness summary
- Contextual fitting tip

The components continue receiving and using the existing sensor state values. No backend changes are required.

## 11. Error Handling

- Failed scan: show a retryable inline message without clearing the page.
- Failed connection: keep the selected device and allow retry.
- Lost sensor data: change the affected state to `ขาดการเชื่อมต่อ` and show a corrective tip.
- Local service unavailable: explain the user action required without exposing implementation details.
- All errors must state both what happened and what the user can do next.

## 12. Verification and Acceptance Criteria

- The Angular production build passes.
- Existing device scan, selection, connection, fitting, and Baseline actions retain their behavior.
- All four sensor states render the correct icon, text, and color.
- The Baseline action is enabled only when TP9, AF7, AF8, and TP10 are all `good`.
- The screen is usable with keyboard navigation and has visible focus states.
- The layout works at desktop, tablet, mobile, and 200 percent zoom widths.
- The page contains the entertainment-use note and no medical positioning.
- A visual review confirms alignment, spacing, legibility, and consistency with the PDF's Navy-Purple interface.
