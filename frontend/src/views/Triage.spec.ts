import { beforeEach, describe, expect, it, vi } from 'vitest';
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils';

import Triage from './Triage.vue';

const {
  createTriageSession,
  analyzeTriage,
  getTriageSession,
  createTriageReport,
  getTriageReport,
} = vi.hoisted(() => ({
  createTriageSession: vi.fn(),
  analyzeTriage: vi.fn(),
  getTriageSession: vi.fn(),
  createTriageReport: vi.fn(),
  getTriageReport: vi.fn(),
}));

vi.mock('../api', () => ({
  createTriageSession,
  analyzeTriage,
  getTriageSession,
  createTriageReport,
  getTriageReport,
}));

const completedResult = {
  session_id: 'session-1',
  status: 'completed' as const,
  risk_level: 'medium' as const,
  emergency_advice: null,
  recommended_departments: [
    {
      name: '耳鼻喉科',
      reason: '症状集中在咽喉、鼻腔或耳部区域，适合优先由耳鼻喉科评估。',
      priority: 1,
    },
  ],
  care_path: '建议尽快安排线下门诊评估。',
  preparation_checklist: ['记录症状变化'],
  report_summary: '主诉为喉咙不适，当前信息补全后建议优先咨询耳鼻喉科。',
  disclaimer: '本结果仅用于诊前导诊参考，不能替代医生诊断、检查或治疗决策。',
};

const report = {
  report_id: 'report-1',
  session_id: 'session-1',
  status: 'ready',
  created_at: '2026-06-16T12:00:00Z',
  patient_snapshot: {
    age: 32,
    sex: 'female' as const,
    pregnancy_status: null,
    medical_history: [],
    allergies: [],
    medications: [],
  },
  triage_summary: {
    chief_complaint: '喉咙不舒服',
    risk_level: 'medium' as const,
    recommended_departments: completedResult.recommended_departments,
    care_path: completedResult.care_path,
    generated_from_session_status: 'completed',
  },
  doctor_view: {
    chief_complaint: '喉咙不舒服',
    key_facts: {
      duration: '三天',
      severity: '4分（10分制）',
    },
    risk_notes: '当前导诊风险等级为 medium，建议结合线下面诊进一步确认。',
    recommended_department_summary: '建议优先就诊：耳鼻喉科',
    preparation_checklist: ['记录症状变化'],
  },
  patient_view: {
    what_this_means: '这份报告是根据你当前补充的症状信息整理出的诊前摘要。',
    why_this_department: '症状集中在咽喉、鼻腔或耳部区域，适合优先由耳鼻喉科评估。',
    what_to_prepare: ['记录症状变化'],
    when_to_seek_urgent_care: '如果症状明显加重，请及时急诊就医。',
  },
  disclaimer: '本结果仅用于诊前导诊参考，不能替代医生诊断、检查或治疗决策。',
};

function mountView() {
  return mount(Triage, {
    global: {
      stubs: {
        transition: false,
      },
    },
  });
}

async function clickButtonByText(wrapper: VueWrapper, label: string) {
  const target = wrapper
    .findAll('button')
    .find((button) => button.text().includes(label));

  expect(target, `button "${label}" should exist`).toBeTruthy();
  await target!.trigger('click');
}

describe('Triage view', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('shows the report generation action after triage completes', async () => {
    createTriageSession.mockResolvedValue({ session_id: 'session-1', status: 'created' });
    analyzeTriage.mockResolvedValue(completedResult);
    getTriageSession.mockResolvedValue({
      session_id: 'session-1',
      status: 'completed',
      latest_request: null,
      latest_result: completedResult,
      current_question: null,
      report_id: null,
      messages: [],
    });

    const wrapper = mountView();

    await clickButtonByText(wrapper, '开始导诊');
    await flushPromises();

    expect(wrapper.text()).toContain('生成导诊报告');
  });

  it('renders doctor and patient report sections after generating a report', async () => {
    createTriageSession.mockResolvedValue({ session_id: 'session-1', status: 'created' });
    analyzeTriage.mockResolvedValue(completedResult);
    getTriageSession
      .mockResolvedValueOnce({
        session_id: 'session-1',
        status: 'completed',
        latest_request: null,
        latest_result: completedResult,
        current_question: null,
        report_id: null,
        messages: [],
      })
      .mockResolvedValueOnce({
        session_id: 'session-1',
        status: 'completed',
        latest_request: null,
        latest_result: completedResult,
        current_question: null,
        report_id: 'report-1',
        messages: [],
      });
    createTriageReport.mockResolvedValue(report);
    getTriageReport.mockResolvedValue(report);

    const wrapper = mountView();

    await clickButtonByText(wrapper, '开始导诊');
    await flushPromises();
    await clickButtonByText(wrapper, '生成导诊报告');
    await flushPromises();

    expect(wrapper.text()).toContain('医生速览');
    expect(wrapper.text()).toContain('患者说明');
    expect(wrapper.text()).toContain('建议优先就诊：耳鼻喉科');
  });
});
