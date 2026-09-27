import { Injectable, signal } from '@angular/core';

export type Language = 'th' | 'en';

interface Dictionary {
  [key: string]: {
    th: string;
    en: string;
  };
}

export const TRANSLATIONS: Dictionary = {
  // Navigation & Shell
  'nav.admin': { th: 'แผงควบคุมระบบแอดมิน', en: 'Admin Dashboard' },
  'nav.dashboard': { th: 'แผงควบคุม', en: 'Dashboard' },
  'nav.personas': { th: 'ตัวละคร & สไตล์', en: 'Personas' },
  'nav.create': { th: 'สร้างเรื่องราวคลื่นสมอง', en: 'Create Dream' },
  'nav.history': { th: 'ประวัติเรื่องราว', en: 'Timeline' },
  'nav.logout': { th: 'ออกจากระบบ', en: 'Logout' },
  'muse.status': { th: 'สถานะเครื่อง MUSE', en: 'MUSE STATUS' },

  // User Dashboard
  'dashboard.kicker': {
    th: 'DREAM LAB / COMIC STUDIO',
    en: 'DREAM LAB / COMIC STUDIO',
  },
  'dashboard.title': {
    th: 'Brainwave to Comic Studio',
    en: 'Brainwave to Comic Studio',
  },
  'dashboard.welcome': {
    th: 'สร้างคอมิก 4 ช่องจากอารมณ์ที่วิเคราะห์ผ่านคลื่นสมอง โดยคุมทุกขั้นตอนผ่าน Local FastAPI, Muse 2 และ ComfyUI',
    en: 'Generate 4-panel AI comics from brainwave emotion analysis, controlled via FastAPI, Muse 2, and ComfyUI.',
  },
  'dashboard.create_new': { th: 'Start EEG Session', en: 'Start EEG Session' },
  'dashboard.view_history': { th: 'View History', en: 'View History' },
  'dashboard.available': { th: 'บริการพร้อมใช้งาน', en: 'Service Available' },
  'dashboard.unavailable': {
    th: 'บริการไม่พร้อมใช้งาน',
    en: 'Service Unavailable',
  },
  'dashboard.checked': { th: 'Checked', en: 'Checked' },
  'dashboard.not_checked': { th: 'ยังไม่ได้ตรวจสอบ', en: 'Not checked yet' },
  'dashboard.char_studio': { th: 'Character Studio', en: 'Character Studio' },
  'dashboard.add_persona': { th: '+ Add Persona', en: '+ Add Persona' },
  'dashboard.recent_results': { th: 'Recent Results', en: 'Recent Results' },
  'dashboard.all_comics': { th: 'All comics', en: 'All comics' },
  'dashboard.no_comics_yet': {
    th: 'ยังไม่มีผลงานล่าสุด กด Start EEG Session เพื่อสร้างคอมิกแรก',
    en: 'No recent comics yet. Click Start EEG Session to generate your first comic.',
  },
  'dashboard.no_personas_yet': {
    th: 'ยังไม่มีตัวละคร — เพิ่ม Persona เพื่อให้คอมิกคุมหน้าตาและชุดได้สม่ำเสมอ',
    en: 'No personas yet — add a Persona to keep character design consistent across panels.',
  },
  'dashboard.persona_name': { th: 'Character name', en: 'Character name' },
  'dashboard.persona_detail': { th: 'Persona detail', en: 'Persona detail' },
  'dashboard.art_style': { th: 'Art style', en: 'Art style' },
  'dashboard.save_persona': { th: 'Save Persona', en: 'Save Persona' },
  'dashboard.cancel': { th: 'Cancel', en: 'Cancel' },
  'dashboard.edit': { th: 'Edit', en: 'Edit' },

  // Persona Page
  'persona.title': {
    th: 'จัดการตัวละคร (Persona Manager)',
    en: 'Persona Manager',
  },
  'persona.add_new': { th: '+ สร้างตัวละครใหม่', en: '+ Add New Persona' },
  'persona.edit': { th: 'แก้ไขตัวละคร', en: 'Edit Persona' },
  'persona.create_title': { th: 'สร้างตัวละครใหม่', en: 'Create New Persona' },
  'persona.name': { th: 'ชื่อตัวละคร', en: 'Character Name' },
  'persona.appearance': { th: 'รูปลักษณ์ภายนอก', en: 'Appearance Details' },
  'persona.basic_info': { th: 'ข้อมูลพื้นฐาน', en: 'Basic Info' },
  'persona.age': { th: 'อายุ', en: 'Age' },
  'persona.gender': { th: 'เพศ', en: 'Gender' },
  'persona.outfit': { th: 'สไตล์การแต่งตัว', en: 'Outfit Style' },
  'persona.distinctive': { th: 'จุดเด่นเฉพาะตัว', en: 'Distinctive Features' },
  'persona.face': { th: 'ลักษณะหน้าตา', en: 'Face Features' },
  'persona.hair': { th: 'ทรงผม', en: 'Hairstyle' },
  'persona.style': { th: 'สไตล์ภาพ (Art Style)', en: 'Art Style' },
  'persona.save': { th: 'บันทึกตัวละคร', en: 'Save Persona' },
  'persona.cancel': { th: 'ยกเลิก', en: 'Cancel' },
  'persona.delete': { th: 'ลบ', en: 'Delete' },
  'persona.no_personas': {
    th: 'ยังไม่มีตัวละคร',
    en: 'No Personas Registered',
  },
  'persona.no_personas_desc': {
    th: 'สร้างตัวละครเพื่อให้คอมิกมีหน้าตาสม่ำเสมอทุกช่อง',
    en: 'Create a persona to keep your comic characters consistent across panels.',
  },
  'persona.create_first': {
    th: '+ สร้างตัวละครแรก',
    en: '+ Create First Persona',
  },
  'persona.no_detail': { th: 'ยังไม่มีรายละเอียด', en: 'No details added yet' },

  // History Page
  'history.title': { th: 'ประวัติผลงาน', en: 'Comic History' },
  'history.new_comic': { th: '+ สร้างการ์ตูนใหม่', en: '+ New Comic' },
  'history.no_comics': { th: 'ยังไม่มีผลงาน', en: 'No Comics Yet' },
  'history.no_comics_desc': {
    th: 'เริ่มสร้างการ์ตูนจากคลื่นสมองของคุณ',
    en: 'Start generating comics from your EEG brainwaves.',
  },
  'history.start_now': { th: 'เริ่มเลย!', en: 'Start Now!' },
  'history.load_more': { th: 'โหลดเพิ่มเติม', en: 'Load More' },

  // Admin Dashboard
  'admin.title': { th: 'แผงควบคุมระบบแอดมิน', en: 'Admin Dashboard' },
  'admin.subtitle': {
    th: 'การจัดการระบบและวิเคราะห์ข้อมูลอารมณ์คลื่นสมอง',
    en: 'System management and subconscious data analytics',
  },
  'admin.tab_stats': { th: 'ตรวจสอบสถิติ', en: 'Check Statistics' },
  'admin.tab_users': { th: 'จัดการผู้ใช้งาน', en: 'Manage Users' },
  'admin.tab_dataset': { th: 'จัดการชุดข้อมูล EEG', en: 'Manage EEG Dataset' },
  'admin.total_comics': { th: 'จำนวนคอมิกทั้งหมด', en: 'Total Comics' },
  'admin.avg_rating': { th: 'ความพึงพอใจเฉลี่ย', en: 'Avg Satisfaction' },
  'admin.active_users': { th: 'ผู้ใช้งานที่มีกิจกรรม', en: 'Active Users' },
  'admin.eeg_samples': { th: 'ตัวอย่างชุดข้อมูล EEG', en: 'EEG Samples' },
  'admin.ready_training': {
    th: 'พร้อมสำหรับการเทรน',
    en: 'Ready for training',
  },
  'admin.emotion_dist': {
    th: 'สัดส่วนกระจายอารมณ์',
    en: 'Emotion Distribution',
  },
  'admin.sys_activity': {
    th: 'กิจกรรมในระบบ (7 วัน)',
    en: 'System Activity (7 Days)',
  },
  'admin.manage_users': { th: 'จัดการผู้ใช้งาน', en: 'Manage Users' },
  'admin.add_user': { th: 'เพิ่มผู้ใช้งาน', en: 'Add User' },
  'admin.col_user': { th: 'ผู้ใช้งาน', en: 'USER' },
  'admin.col_role': { th: 'บทบาท', en: 'ROLE' },
  'admin.col_status': { th: 'สถานะ', en: 'STATUS' },
  'admin.col_status_val': { th: 'ใช้งาน', en: 'ACTIVE' },
  'admin.col_joined': { th: 'วันที่เข้าร่วม', en: 'JOINED' },
  'admin.col_actions': { th: 'การจัดการ', en: 'ACTIONS' },
  'admin.dataset_mgmt': {
    th: 'การจัดการชุดข้อมูล EEG (EEG Dataset Management)',
    en: 'EEG Dataset Management',
  },
  'admin.dataset_desc': {
    th: 'จัดการผู้เข้าร่วมทดลองแบบไม่ระบุชื่อ, สื่อกระตุ้นที่อนุมัติแล้ว และรอบการเก็บข้อมูลคลื่นสมอง',
    en: 'Manage pseudonymous participants, approved stimuli, and collection sessions.',
  },
  'admin.open_dataset': {
    th: 'เปิดระบบรวบรวมชุดข้อมูล EEG (Open Dataset Collection)',
    en: 'Open Dataset Collection',
  },

  // Dataset Collection
  'dataset.title': {
    th: 'ระบบรวบรวมข้อมูลคลื่นสมอง (EEG Dataset)',
    en: 'EEG Dataset Collection',
  },
  'dataset.subtitle': {
    th: 'เตรียมผู้เข้าร่วมการทดลอง สื่อกระตุ้น และรอบการเก็บข้อมูลคลื่นสมองสำหรับวิจัย',
    en: 'Prepare pseudonymous participants, stimuli, and collection sessions.',
  },
  'dataset.notice': {
    th: 'สำหรับการวิจัยและต้นแบบเพื่อความบันเทิง (Entertainment only — Not medical)',
    en: 'Entertainment and prototype research only — not medical diagnosis or treatment.',
  },
  'dataset.summary_title': {
    th: 'สรุปภาพรวมการเก็บข้อมูล',
    en: 'Collection Summary Overview',
  },
  'dataset.tab_overview': { th: 'ภาพรวม (Overview)', en: 'Overview' },
  'dataset.tab_participants': {
    th: 'ผู้เข้าร่วมทดลอง (Participants)',
    en: 'Participants',
  },
  'dataset.tab_stimuli': { th: 'สื่อกระตุ้น (Stimuli)', en: 'Stimuli' },
  'dataset.tab_sessions': { th: 'รอบการเก็บข้อมูล (Sessions)', en: 'Sessions' },
  'dataset.overview': { th: 'ภาพรวม (Overview)', en: 'Overview' },
  'dataset.participants': {
    th: 'ผู้เข้าร่วมทดลอง (Participants)',
    en: 'Participants',
  },
  'dataset.stimuli': { th: 'สื่อกระตุ้น (Stimuli)', en: 'Stimuli' },
  'dataset.sessions': { th: 'รอบการเก็บข้อมูล (Sessions)', en: 'Sessions' },
  'dataset.trials': { th: 'รอบทดสอบ (Trials)', en: 'Trials' },
  'dataset.pending': { th: 'รอการตรวจสอบ (Pending)', en: 'Pending Review' },
  'dataset.register_participant': {
    th: 'ลงทะเบียนผู้เข้าร่วม',
    en: 'Register Participant',
  },
  'dataset.register_new_participant': {
    th: 'ลงทะเบียนผู้เข้าร่วมทดลองใหม่',
    en: 'Register New Participant',
  },
  'dataset.auto_code_notice': {
    th: 'ระบบจะสร้างรหัสระบุตัวตนแบบไม่ระบุชื่อ (เช่น P001, P002) ให้อัตโนมัติ',
    en: 'The system automatically generates pseudonymous participant IDs (e.g. P001, P002).',
  },
  'dataset.consent_checkbox': {
    th: 'ผู้เข้าร่วมได้รับการยืนยันและยินยอมให้บันทึกข้อมูลแล้ว',
    en: 'Participant has confirmed consent for research data collection.',
  },
  'dataset.participant_list': {
    th: 'รายชื่อผู้เข้าร่วมทดลอง',
    en: 'Participant List',
  },
  'dataset.register_stimulus': {
    th: 'ลงทะเบียนสื่อกระตุ้น',
    en: 'Register Stimulus',
  },
  'dataset.register_stimulus_title': {
    th: 'ลงทะเบียนสื่อกระตุ้น (Stimulus)',
    en: 'Register Stimulus',
  },
  'dataset.stimulus_title_label': {
    th: 'ชื่อสื่อกระตุ้น (Title)',
    en: 'Stimulus Title',
  },
  'dataset.media_path_label': {
    th: 'ไฟล์สื่อ / URL (Media reference)',
    en: 'Media File / URL',
  },
  'dataset.checksum_label': {
    th: 'SHA-256 Checksum (64 ตัวอักษร)',
    en: 'SHA-256 Checksum (64 chars)',
  },
  'dataset.duration_label': {
    th: 'ระยะเวลาคลิป (45–60 วินาที)',
    en: 'Clip Duration (45–60s)',
  },
  'dataset.target_quadrant_label': {
    th: 'เป้าหมายอารมณ์ (Quadrant)',
    en: 'Target Emotion Quadrant',
  },
  'dataset.approval_state_label': {
    th: 'สถานะอนุมัติ (Approval state)',
    en: 'Approval State',
  },
  'dataset.version_label': {
    th: 'เวอร์ชันชุดสื่อกระตุ้น (Version)',
    en: 'Stimulus Set Version',
  },
  'dataset.all_stimuli_list': {
    th: 'รายการสื่อกระตุ้นทั้งหมด',
    en: 'All Stimuli List',
  },
  'dataset.no_stimuli': {
    th: 'ยังไม่มีสื่อกระตุ้นในระบบ',
    en: 'No stimuli registered yet',
  },
  'dataset.create_session': {
    th: 'สร้างรอบการเก็บข้อมูลใหม่',
    en: 'Create Collection Session',
  },
  'dataset.start_resume': { th: 'เริ่ม / ดำเนินการต่อ', en: 'Start / Resume' },

  // EEG Session
  'session.step1': { th: '1. เชื่อมต่ออุปกรณ์', en: '1. Device Connection' },
  'session.step2': { th: '2. ตรวจสัญญาณ & สวมใส่', en: '2. Signal & Fitting' },
  'session.step3': { th: '3. บันทึกอารมณ์', en: '3. Emotion Recording' },
  'session.step4': { th: '4. สร้างการ์ตูนคอมิก', en: '4. Generate Comic' },
  'session.kicker': { th: 'ระบบสร้างการ์ตูนคลื่นสมอง', en: 'Create Dream' },
  'session.connect_title': {
    th: 'เชื่อมต่ออุปกรณ์ Muse 2',
    en: 'Connect Muse 2 Headset',
  },
  'session.connect_subtitle': {
    th: 'เตรียมอุปกรณ์ให้พร้อมก่อนเริ่มสร้างเรื่องราว',
    en: 'Prepare your headset before starting story generation.',
  },
  'session.scan_btn': { th: 'ค้นหาอุปกรณ์ Muse', en: 'Scan for Muse' },
  'session.scanning': { th: 'กำลังค้นหา Muse…', en: 'Scanning for Muse…' },
  'session.connect_btn': {
    th: 'เชื่อมต่ออุปกรณ์ที่เลือก',
    en: 'Connect Selected Headset',
  },
  'session.fitting_guide': {
    th: 'ปรับสายคาดให้พอดี',
    en: 'Adjust Headband Fitting',
  },
  'session.fitting_desc': {
    th: 'ขยับสายคาด Muse 2 ให้เซนเซอร์ทั้ง 4 จุดสัมผัสผิวแน่นสนิท',
    en: 'Position Muse 2 headband so all 4 sensors make solid skin contact.',
  },
  'session.fit_tip1': {
    th: 'เปิดบริเวณหน้าผากและหลังหูไม่ให้เส้นผมบัง',
    en: 'Clear hair from forehead and behind ears.',
  },
  'session.fit_tip2': {
    th: 'วางสายคาดให้กระชับแต่ไม่แน่นจนเกินไป',
    en: 'Position headband snugly but comfortably.',
  },
  'session.fit_tip3': {
    th: 'นั่งนิ่งและผ่อนคลายขณะตรวจสัญญาณ',
    en: 'Remain calm and relaxed during signal check.',
  },
  'session.start_baseline': {
    th: 'เริ่มบันทึกค่าพื้นฐาน (Baseline 20s)',
    en: 'Start Baseline Recording (20s)',
  },
  'session.waiting_sensors': {
    th: 'รอสัญญาณให้พร้อมครบ 4 จุด',
    en: 'Waiting for all 4 sensors',
  },

  // Dataset Collection Runner
  'runner.back': {
    th: 'ระบบรวบรวมข้อมูลคลื่นสมอง',
    en: 'EEG Dataset Collection',
  },
  'runner.eyebrow': {
    th: 'พื้นที่รวบรวมข้อมูลระดับแอดมิน (Admin Collection Workspace)',
    en: 'Admin collection workspace',
  },
  'runner.title': {
    th: 'การตั้งค่าสายคาดคลื่นสมองสร้างสรรค์ (Creative Headset Setup)',
    en: 'Creative Headset Setup',
  },
  'runner.live_connected': {
    th: 'เชื่อมต่อสถานะ Live เรียบร้อย',
    en: 'Live state connected',
  },
  'runner.persisted_state': {
    th: 'ใช้งานสถานะ Runner ปัจจุบัน',
    en: 'Using persisted runner state',
  },
  'runner.signal_quality': {
    th: 'คุณภาพสัญญาณ: derived EEG window',
    en: 'Signal quality: derived EEG window',
  },
  'runner.progress': { th: 'ความคืบหน้าการทดลอง (Progress)', en: 'Progress' },
  'runner.schedule_not_prepared': {
    th: 'ยังไม่ได้เตรียม Schedule',
    en: 'Schedule not prepared',
  },
  'runner.scan_select_muse': {
    th: 'ค้นหาและเลือกอุปกรณ์ Muse 2',
    en: 'Scan & Select Muse 2',
  },
  'runner.scan_desc': {
    th: 'ค้นหา Muse 2 ใกล้เครื่องคอมพิวเตอร์ แล้วเชื่อมต่ออุปกรณ์ที่พบสำหรับ Session นี้',
    en: 'Scan for Muse 2 near this computer and connect the detected headset for this session.',
  },
  'runner.prepare_schedule_btn': {
    th: 'เตรียม Schedule 12 Trial',
    en: 'Prepare 12-Trial Schedule',
  },
  'runner.admin_contact_confirm': {
    th: 'การยืนยันการสัมผัสโดย Admin',
    en: 'Admin Contact Confirmation',
  },
  'runner.confirm_all_contacts': {
    th: 'ยืนยันสัมผัสผิวครบ 4 จุด',
    en: 'Confirm all 4 contacts',
  },
  'runner.admin_contact_desc': {
    th: 'เป็นการยืนยันว่าเซนเซอร์แตะผิวเท่านั้น ไม่ใช่ค่าคุณภาพสัญญาณแบบ live',
    en: 'Confirms physical skin contact only, not live signal quality.',
  },
  'runner.start_baseline_open': {
    th: 'เริ่ม Baseline ลืมตา',
    en: 'Start Eyes Open Baseline',
  },
  'runner.start_baseline_closed': {
    th: 'เริ่ม Baseline หลับตา',
    en: 'Start Eyes Closed Baseline',
  },
  'runner.clean_gate_hint': {
    th: 'Backend จะตรวจ clean-signal gate จริงระหว่าง Baseline',
    en: 'Backend verifies clean-signal gate during Baseline.',
  },
  'runner.open_before_closed_hint': {
    th: 'Baseline ลืมตาต้องมาก่อน Baseline หลับตาเสมอ',
    en: 'Eyes-open baseline must always precede eyes-closed baseline.',
  },

  // Sensor Fitting Component
  'sensor.fitting_status': { th: 'สถานะการสวมใส่', en: 'Fitting Status' },
  'sensor.your_muse': { th: 'Muse 2 ของคุณ', en: 'Your Muse 2 Headset' },
  'sensor.fit_instruction': {
    th: 'ตรวจให้เซนเซอร์ทั้ง 4 จุดแนบสนิทก่อนเริ่มบันทึก',
    en: 'Ensure all 4 sensors make solid skin contact before recording',
  },
  'sensor.waiting_signal': { th: 'กำลังรอสัญญาณ', en: 'Waiting for signal' },
  'sensor.adjust_guidance': {
    th: 'ขยับสายคาดตามตำแหน่งด้านล่าง',
    en: 'Adjust headband placement according to diagram below',
  },
  'sensor.tp9_label': { th: 'หลังหูซ้าย (TP9)', en: 'Left Ear (TP9)' },
  'sensor.af7_label': { th: 'หน้าผากซ้าย (AF7)', en: 'Left Forehead (AF7)' },
  'sensor.af8_label': { th: 'หน้าผากขวา (AF8)', en: 'Right Forehead (AF8)' },
  'sensor.tp10_label': { th: 'หลังหูขวา (TP10)', en: 'Right Ear (TP10)' },
  'sensor.waiting': { th: 'รอสัญญาณ', en: 'Waiting for signal' },
  'sensor.good': { th: 'สัญญาณดี', en: 'Good signal' },
  'sensor.poor': { th: 'สัญญาณอ่อน', en: 'Poor signal' },
};

@Injectable({
  providedIn: 'root',
})
export class LanguageService {
  readonly currentLang = signal<Language>(
    (localStorage.getItem('app_lang') as Language) || 'th',
  );

  setLanguage(lang: Language): void {
    this.currentLang.set(lang);
    localStorage.setItem('app_lang', lang);
  }

  toggleLanguage(): void {
    const next = this.currentLang() === 'th' ? 'en' : 'th';
    this.setLanguage(next);
  }

  translate(key: string): string {
    const lang = this.currentLang(); // Read signal for reactivity
    const entry = TRANSLATIONS[key];
    if (!entry) return key;
    return entry[lang] || entry['th'] || key;
  }

  t(key: string): string {
    return this.translate(key);
  }

  translateError(err: unknown): string {
    return toThaiError(err);
  }
}

export function toThaiError(err: unknown): string {
  if (!err) return '';
  let msg = '';
  if (typeof err === 'string') {
    msg = err;
  } else if (err instanceof Error) {
    msg = err.message;
  } else if (typeof err === 'object' && err !== null) {
    const obj = err as {
      error?: string | { detail?: string };
      message?: string;
      statusText?: string;
    };
    if (typeof obj.error === 'string') {
      msg = obj.error;
    } else if (obj.error?.detail && typeof obj.error.detail === 'string') {
      msg = obj.error.detail;
    } else if (obj.message) {
      msg = obj.message;
    } else if (obj.statusText) {
      msg = obj.statusText;
    }
  }

  msg = (msg || '').trim();
  if (!msg) return 'เกิดข้อผิดพลาดที่ไม่ทราบสาเหตุ';

  const lower = msg.toLowerCase();

  if (lower.includes('invalid email or password')) {
    return 'อีเมลหรือรหัสผ่านไม่ถูกต้อง กรุณาลองใหม่อีกครั้ง';
  }
  if (lower.includes('email already registered')) {
    return 'อีเมลนี้ถูกลงทะเบียนในระบบแล้ว กรุณาใช้อีเมลอื่น';
  }
  if (
    lower.includes('invalid or expired token') ||
    lower.includes('token expired')
  ) {
    return 'เซสชันหมดอายุหรือไม่ถูกต้อง กรุณาเข้าสู่ระบบใหม่อีกครั้ง';
  }
  if (lower.includes('not authenticated')) {
    return 'ยังไม่ได้เข้าสู่ระบบ กรุณาเข้าสู่ระบบก่อนใช้งาน';
  }
  if (lower.includes('admin access required')) {
    return 'ต้องใช้สิทธิ์ผู้ดูแลระบบ (Admin) ในการเข้าถึง';
  }
  if (lower.includes('user access required')) {
    return 'ต้องใช้สิทธิ์ผู้ใช้งานทั่วไปในการเข้าถึง';
  }
  if (lower.includes('user not found or inactive')) {
    return 'ไม่พบข้อมูลผู้ใช้ หรือบัญชีถูกระงับการใช้งาน';
  }
  if (
    lower.includes('session not found') ||
    lower.includes('active session not found')
  ) {
    return 'ไม่พบเซสชันการทดสอบในระบบ';
  }
  if (lower.includes('collection session not found')) {
    return 'ไม่พบเซสชันการเก็บข้อมูลคลื่นสมอง';
  }
  if (lower.includes('collection session is terminal')) {
    return 'เซสชันการเก็บข้อมูลนี้เสร็จสิ้นหรือปิดไปแล้ว ไม่สามารถดำเนินการต่อได้';
  }
  if (lower.includes('trial not found')) {
    return 'ไม่พบข้อมูลรอบทดสอบ (Trial) สำหรับเซสชันนี้';
  }
  if (lower.includes('trial is not next in schedule')) {
    return 'รอบทดสอบนี้ไม่ตรงกับลำดับถัดไปในตาราง';
  }
  if (lower.includes('stimulus media not found')) {
    return 'ไม่พบไฟล์วิดีโอสื่อกระตุ้นในโฟลเดอร์ระบบ';
  }
  if (
    lower.includes('stimulus media verification failed') ||
    lower.includes('checksum mismatch')
  ) {
    return 'ตรวจสอบไฟล์วิดีโอล้มเหลว: ค่า Checksum ไม่ตรงกับที่บันทึกไว้ในระบบ';
  }
  if (lower.includes('stimulus media is not a video')) {
    return 'ไฟล์สื่อกระตุ้นไม่ใช่วิดีโอที่ถูกต้อง';
  }
  if (lower.includes('stimulus playback failed')) {
    return 'การเล่นวิดีโอคลิปล้มเหลว (Stimulus playback failed; collection was interrupted for recovery)';
  }
  if (lower.includes('stimulus content duration')) {
    return 'ความยาวคลิปต้องอยู่ระหว่าง 45 ถึง 60 วินาทีตามข้อกำหนดการทดลอง';
  }
  if (lower.includes('all four live sensors good') || lower.includes('require_live_sensor_ready')) {
    return 'สัญญาณ Muse ต้องแตะผิวดีทั้ง 4 จุดก่อนเริ่มคลิป';
  }
  if (lower.includes('rest requires at least') || lower.includes('rest not ready')) {
    return 'ต้องพักสายตาให้นิ่งอย่างน้อย 10 วินาทีก่อนเริ่มคลิป';
  }
  if (lower.includes('muse scan not found')) {
    return 'ไม่พบข้อมูลผลการค้นหาอุปกรณ์ Muse (Muse scan not found)';
  }
  if (
    lower.includes('muse disconnected') ||
    lower.includes('muse connection could not be established')
  ) {
    return 'อุปกรณ์ Muse หลุดการเชื่อมต่อ (Muse disconnected)';
  }
  if (lower.includes('a live muse connection is required')) {
    return 'ต้องเชื่อมต่ออุปกรณ์ Muse ก่อนเริ่มบันทึกข้อมูล';
  }
  if (lower.includes('baseline requires exactly 12 persisted schedule rows')) {
    return 'ต้องมีตารางรอบทดลองครบ 12 รอบก่อนเริ่ม Baseline';
  }
  if (lower.includes('baseline requires participant consent')) {
    return 'ต้องได้รับการยืนยันความยินยอมจากผู้เข้าร่วมทดลองก่อนเริ่ม Baseline';
  }
  if (lower.includes('capture requires all four live sensors good')) {
    return 'ต้องการสัญญาณเซนเซอร์ทั้ง 4 จุดที่ดีและคงที่ 256 Hz ก่อนเริ่มบันทึก';
  }
  if (
    lower.includes('eyes-closed baseline requires completed eyes-open baseline')
  ) {
    return 'ต้องผ่าน Baseline ลืมตาก่อนเริ่ม Baseline หลับตา';
  }
  if (lower.includes('user cancelled') || lower.includes('user canceled')) {
    return 'ยกเลิกการเลือกอุปกรณ์บลูทูธ';
  }
  if (lower.includes('bluetooth') && lower.includes('not available')) {
    return 'ไม่พบตัวรับสัญญาณบลูทูธ หรือไม่ได้เปิดใช้งานบลูทูธในคอมพิวเตอร์';
  }
  if (
    lower.includes('gatt server is disconnected') ||
    lower.includes('device is disconnected')
  ) {
    return 'การเชื่อมต่อบลูทูธกับ Muse หลุดหาย กรุณาเชื่อมต่อใหม่';
  }
  if (
    lower.includes('queuepool limit') ||
    lower.includes('connection timed out')
  ) {
    return 'การเชื่อมต่อฐานข้อมูลล่าช้าหรือหมดเวลา กรุณาลองใหม่อีกครั้ง';
  }
  if (
    lower.includes('networkerror') ||
    lower.includes('failed to fetch') ||
    lower.includes('http failure response')
  ) {
    return 'ไม่สามารถเชื่อมต่อกับเซิร์ฟเวอร์ Backend ได้ (กรุณาตรวจสอบว่า Backend กำลังทำงาน)';
  }
  if (
    lower.includes('not in ready state') ||
    lower.includes('not in emotion_confirmation state')
  ) {
    return 'สถานะของเซสชันไม่ถูกต้องสำหรับการดำเนินการนี้';
  }
  if (lower.includes('request failed') || lower.includes('an error occurred')) {
    return 'เกิดข้อผิดพลาดในการดำเนินการ กรุณาลองใหม่อีกครั้ง';
  }

  // If already in Thai, return as is
  if (/[\u0E00-\u0E7F]/.test(msg)) return msg;

  return `เกิดข้อผิดพลาด: ${msg}`;
}
