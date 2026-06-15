# Muse 2 Real-time EEG Dashboard

แอป Python สำหรับเชื่อมต่อ Muse 2 ผ่าน Bluetooth โดยใช้ `muselsl` และ `pylsl` เพื่อรับข้อมูล Raw EEG แบบ real-time แสดงผลด้วย PyQtGraph และบันทึกข้อมูลเป็น CSV

## คุณสมบัติ

- ค้นหา Muse 2 ผ่าน Bluetooth
- เลือกอุปกรณ์ Muse จากรายการที่ scan เจอ
- รับข้อมูล EEG 4 ช่อง: `TP9`, `AF7`, `AF8`, `TP10`
- แสดงกราฟ EEG แบบ scrolling real-time
- แสดง sampling rate, สถานะการเชื่อมต่อ, ค่า EEG ปัจจุบัน และเวลาบันทึก
- แสดง signal quality ของแต่ละช่อง
- คำนวณ Band Power: Delta, Theta, Alpha, Beta, Gamma
- แสดง FFT Spectrum แบบ real-time
- บันทึกข้อมูล EEG พร้อม timestamp เป็นไฟล์ CSV

## ไฟล์หลัก

- `main.py` - หน้าจอ Dashboard และปุ่มควบคุม
- `muse_connector.py` - ค้นหาอุปกรณ์, เริ่ม/หยุด stream, รับข้อมูลจาก LSL
- `eeg_plot.py` - กราฟ EEG แบบ real-time
- `signal_processing.py` - FFT, Band Power, Signal Quality
- `recorder.py` - บันทึกข้อมูลเป็น CSV
- `requirements.txt` - รายการไลบรารีที่ต้องติดตั้ง

## สิ่งที่ต้องมี

- Windows 11
- Python 3.11 ขึ้นไป
- Bluetooth ที่ใช้งานได้
- อุปกรณ์ Muse 2

โปรเจกต์นี้ทดสอบกับ Python 3.13 ได้ แต่ถ้าติดปัญหา dependency แนะนำ Python 3.11 หรือ 3.12

## การติดตั้ง

เปิด PowerShell ที่โฟลเดอร์โปรเจกต์:

```powershell
cd "C:\comsci\EEG PRE"
```

ติดตั้งไลบรารี:

```powershell
pip install -r requirements.txt
```

ถ้าโหลดจาก PyPI หลักไม่สำเร็จหรือ connection ถูกตัด ให้ใช้ mirror:

```powershell
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
```

ตรวจว่าไลบรารี import ได้:

```powershell
python -c "import muselsl, pylsl, pyqtgraph, PyQt5, bleak; print('imports ok')"
```

## วิธีรันโปรแกรม

```powershell
python main.py
```

## วิธีใช้งาน

1. เปิด Bluetooth ใน Windows 11
2. เปิด Muse 2 และวางใกล้คอมพิวเตอร์
3. ปิดโปรแกรมอื่นที่อาจเชื่อม Muse อยู่ เช่น Muse Monitor หรือ BlueMuse
4. เปิดโปรแกรมด้วย `python main.py`
5. กด `Scan Devices`
6. เลือก Muse จาก dropdown เช่น `Muse-A9C7 (00:55:DA:B7:A9:C7)`
7. กด `Connect Selected`
8. กด `Start Stream`
9. รอจนสถานะขึ้นว่าเชื่อมต่อ EEG stream แล้ว กราฟจะเริ่มแสดงข้อมูล
10. กด `Start Recording` เมื่อต้องการบันทึกข้อมูล
11. กด `Stop Recording` เพื่อหยุดและบันทึกไฟล์ CSV

## ไฟล์ CSV

ไฟล์จะถูกบันทึกในโฟลเดอร์:

```text
recordings/
```

ชื่อไฟล์ตัวอย่าง:

```text
muse_eeg_20260615_205500.csv
```

คอลัมน์ในไฟล์:

```text
timestamp_lsl,timestamp_iso,TP9,AF7,AF8,TP10
```

## การแก้ปัญหาเบื้องต้น

### กด Scan แล้วไม่เจอ Muse

- ตรวจว่า Muse 2 เปิดอยู่และมีแบตเตอรี่
- วาง Muse ใกล้คอมพิวเตอร์
- ปิด Bluetooth แล้วเปิดใหม่
- ปิดแอปอื่นที่จับ Muse อยู่
- ถ้า Muse เคย pair กับมือถือ ให้ปิด Bluetooth มือถือก่อน

### โปรแกรมค้างตอน scan

การ scan Bluetooth บน Windows อาจใช้เวลาประมาณ 10 วินาที เป็นพฤติกรรมปกติของ `muselsl`/`bleak`

### Start Stream แล้วไม่ขึ้นกราฟ

- รอ 5-10 วินาทีให้ LSL stream พร้อม
- ตรวจว่าเลือก Muse แล้วกด `Connect Selected` ก่อน
- ลองกด `Stop Stream` แล้ว `Start Stream` ใหม่
- restart Muse 2 แล้ว scan ใหม่

### มี error เกี่ยวกับ PyQtGraph หรือ PyQt5

ติดตั้ง dependency ใหม่:

```powershell
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple PyQt5 pyqtgraph
```

### มี error เกี่ยวกับ muselsl หรือ pylsl

ติดตั้งใหม่:

```powershell
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple muselsl pylsl bleak
```

## หมายเหตุ

ค่าคุณภาพสัญญาณในแอปเป็น heuristic จากข้อมูล raw EEG ไม่ใช่ค่าคุณภาพอย่างเป็นทางการจาก Muse SDK โดยตรง เหมาะสำหรับช่วยดูแนวโน้มว่าสัญญาณนิ่งหรือมี noise มากเกินไป
