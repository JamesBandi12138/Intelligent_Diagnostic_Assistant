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

async function startTriage(wrapper: VueWrapper, symptom = '喉咙痛三天，吞咽时更明显，没有发热。') {
  await wrapper.find<HTMLTextAreaElement>('#symptom').setValue(symptom);
  await clickButtonByText(wrapper, '开始导诊');
}

describe('Triage view', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('starts with an empty symptom box and lets patients use a quick example', async () => {
    const wrapper = mountView();

    expect(wrapper.find<HTMLTextAreaElement>('#symptom').element.value).toBe('');

    await clickButtonByText(wrapper, '喉咙痛');

    expect(wrapper.find<HTMLTextAreaElement>('#symptom').element.value).toContain('喉咙痛三天');
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
      current_agent: 'result_agent',
      node_trace: ['bootstrap_context', 'supervisor_route', 'safety_agent', 'triage_agent', 'result_agent'],
      agent_trace: [{ agent: 'result_agent', summary: 'status=completed risk=medium' }],
      route_reason: 'all core fields are ready for final triage result',
      knowledge_summary: 'No knowledge hits retrieved for the current triage turn.',
      raw_report_summary: '主诉：喉咙不舒服。目前信息补全后，建议优先咨询耳鼻喉科。',
      llm_report_summary: '根据你补充的情况，目前更建议优先到耳鼻喉科门诊评估喉咙不适。',
      llm_used: true,
      llm_error: null,
      llm_trace: [{ agent: 'result_agent', task: 'rewrite_report_summary', used: true, fallback: false, error: null }],
    });

    const wrapper = mountView();

    await startTriage(wrapper);
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
        current_agent: 'result_agent',
        node_trace: ['bootstrap_context', 'supervisor_route', 'safety_agent', 'triage_agent', 'result_agent'],
        agent_trace: [{ agent: 'result_agent', summary: 'status=completed risk=medium' }],
        route_reason: 'all core fields are ready for final triage result',
        knowledge_summary: 'No knowledge hits retrieved for the current triage turn.',
        raw_report_summary: '主诉：喉咙不舒服。目前信息补全后，建议优先咨询耳鼻喉科。',
        llm_report_summary: '根据你补充的情况，目前更建议优先到耳鼻喉科门诊评估喉咙不适。',
        llm_used: true,
        llm_error: null,
        llm_trace: [{ agent: 'result_agent', task: 'rewrite_report_summary', used: true, fallback: false, error: null }],
      })
      .mockResolvedValueOnce({
        session_id: 'session-1',
        status: 'completed',
        latest_request: null,
        latest_result: completedResult,
        current_question: null,
        report_id: 'report-1',
        messages: [],
        current_agent: 'result_agent',
        node_trace: ['bootstrap_context', 'supervisor_route', 'safety_agent', 'triage_agent', 'result_agent'],
        agent_trace: [{ agent: 'result_agent', summary: 'status=completed risk=medium' }],
        route_reason: 'all core fields are ready for final triage result',
        knowledge_summary: 'No knowledge hits retrieved for the current triage turn.',
        raw_report_summary: '主诉：喉咙不舒服。目前信息补全后，建议优先咨询耳鼻喉科。',
        llm_report_summary: '根据你补充的情况，目前更建议优先到耳鼻喉科门诊评估喉咙不适。',
        llm_used: true,
        llm_error: null,
        llm_trace: [{ agent: 'result_agent', task: 'rewrite_report_summary', used: true, fallback: false, error: null }],
      });
    createTriageReport.mockResolvedValue(report);
    getTriageReport.mockResolvedValue(report);

    const wrapper = mountView();

    await startTriage(wrapper);
    await flushPromises();
    await clickButtonByText(wrapper, '生成导诊报告');
    await flushPromises();

    expect(wrapper.text()).toContain('医生速览');
    expect(wrapper.text()).toContain('患者说明');
    expect(wrapper.text()).toContain('建议优先就诊：耳鼻喉科');
  });

  it('keeps orchestration debug details hidden until explicitly enabled', async () => {
    createTriageSession.mockResolvedValue({ session_id: 'session-1', status: 'created' });
    analyzeTriage.mockResolvedValue({
      session_id: 'session-1',
      status: 'needs_follow_up' as const,
      risk_level: 'medium' as const,
      question: '这种不舒服持续多久了？',
      known_facts_summary: '部位：咽喉',
      missing_fields: ['duration'],
    });
    getTriageSession.mockResolvedValue({
      session_id: 'session-1',
      status: 'needs_follow_up',
      latest_request: null,
      latest_result: {
        session_id: 'session-1',
        status: 'needs_follow_up' as const,
        risk_level: 'medium' as const,
        question: '这种不舒服持续多久了？',
        known_facts_summary: '部位：咽喉',
        missing_fields: ['duration'],
      },
      current_question: '这种不舒服持续多久了？',
      report_id: null,
      messages: [],
      current_agent: 'follow_up_agent',
      node_trace: ['bootstrap_context', 'supervisor_route', 'safety_agent', 'triage_agent', 'knowledge_agent', 'follow_up_agent'],
      agent_trace: [
        { agent: 'safety_agent', summary: 'risk=medium decision=continue' },
        { agent: 'knowledge_agent', summary: 'hits=0' },
      ],
      route_reason: 'missing core fields require one follow-up question',
      knowledge_summary: 'No knowledge hits retrieved for the current triage turn.',
      raw_follow_up_question: '这种不舒服持续多久了？',
      llm_follow_up_question: '这种不舒服大概持续多久了，是突然开始还是慢慢加重的？',
      llm_used: true,
      llm_error: null,
      llm_trace: [{ agent: 'follow_up_agent', task: 'rewrite_follow_up_question', used: true, fallback: false, error: null }],
    });

    const wrapper = mountView();

    await startTriage(wrapper);
    await flushPromises();

    expect(wrapper.text()).not.toContain('follow_up_agent');
    expect(wrapper.text()).not.toContain('No knowledge hits retrieved for the current triage turn.');

    await clickButtonByText(wrapper, '显示开发诊断');

    expect(wrapper.text()).toContain('follow_up_agent');
    expect(wrapper.text()).toContain('knowledge_agent');
    expect(wrapper.text()).toContain('No knowledge hits retrieved for the current triage turn.');
    expect(wrapper.text()).toContain('follow_up_raw');
    expect(wrapper.text()).toContain('follow_up_llm');
    expect(wrapper.text()).toContain('rewrite_follow_up_question');
    expect(wrapper.text()).toContain('llm_used: true');
    expect(wrapper.text()).toContain('如果你上一句说错了，可以直接改口');
  });

  it('shows llm summary trace after loading a completed session', async () => {
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
      current_agent: 'result_agent',
      node_trace: ['bootstrap_context', 'supervisor_route', 'safety_agent', 'triage_agent', 'result_agent'],
      agent_trace: [{ agent: 'result_agent', summary: 'status=completed risk=medium' }],
      route_reason: 'all core fields are ready for final triage result',
      knowledge_summary: 'No knowledge hits retrieved for the current triage turn.',
      llm_enabled: true,
      llm_provider: 'qwen',
      llm_model: 'qwen-plus',
      llm_base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
      raw_report_summary: '主诉：喉咙不舒服。目前信息补全后，建议优先咨询耳鼻喉科。',
      llm_report_summary: '根据你补充的情况，目前更建议优先到耳鼻喉科门诊评估喉咙不适。',
      llm_used: true,
      llm_error: null,
      llm_trace: [{ agent: 'result_agent', task: 'rewrite_report_summary', used: true, fallback: false, error: null }],
    });

    const wrapper = mountView();

    await startTriage(wrapper);
    await flushPromises();

    await clickButtonByText(wrapper, '显示开发诊断');

    expect(wrapper.text()).toContain('summary_raw');
    expect(wrapper.text()).toContain('summary_llm');
    expect(wrapper.text()).toContain('rewrite_report_summary');
    expect(wrapper.text()).toContain('llm_used: true');
  });

  it('shows fallback diagnosis details when llm provider fails', async () => {
    createTriageSession.mockResolvedValue({ session_id: 'session-1', status: 'created' });
    analyzeTriage.mockResolvedValue({
      session_id: 'session-1',
      status: 'needs_follow_up' as const,
      risk_level: 'medium' as const,
      question: '这种不舒服持续多久了？',
      known_facts_summary: '部位：咽喉',
      missing_fields: ['duration'],
    });
    getTriageSession.mockResolvedValue({
      session_id: 'session-1',
      status: 'needs_follow_up',
      latest_request: null,
      latest_result: {
        session_id: 'session-1',
        status: 'needs_follow_up' as const,
        risk_level: 'medium' as const,
        question: '这种不舒服持续多久了？',
        known_facts_summary: '部位：咽喉',
        missing_fields: ['duration'],
      },
      current_question: '这种不舒服持续多久了？',
      report_id: null,
      messages: [],
      current_agent: 'follow_up_agent',
      node_trace: ['bootstrap_context', 'supervisor_route', 'follow_up_agent'],
      agent_trace: [{ agent: 'follow_up_agent', summary: 'question=duration' }],
      route_reason: 'missing core fields require one follow-up question',
      knowledge_summary: 'No knowledge hits retrieved for the current triage turn.',
      llm_enabled: true,
      llm_provider: 'qwen',
      llm_model: 'qwen-plus',
      llm_base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
      raw_follow_up_question: '这种不舒服持续多久了？',
      llm_follow_up_question: null,
      llm_used: false,
      llm_error: 'transport_error',
      llm_trace: [{ agent: 'follow_up_agent', task: 'rewrite_follow_up_question', used: false, fallback: true, error: 'transport_error' }],
    });

    const wrapper = mountView();

    await startTriage(wrapper);
    await flushPromises();

    await clickButtonByText(wrapper, '显示开发诊断');

    expect(wrapper.text()).toContain('LLM 运行状态 / 配置诊断');
    expect(wrapper.text()).toContain('已回退到规则结果');
    expect(wrapper.text()).toContain('供应商 / 网络 / 鉴权 / 额度异常');
    expect(wrapper.text()).toContain('qwen-plus');
  });

  it('shows llm active status when rewritten output is used', async () => {
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
      current_agent: 'result_agent',
      node_trace: ['bootstrap_context', 'supervisor_route', 'result_agent'],
      agent_trace: [{ agent: 'result_agent', summary: 'status=completed risk=medium' }],
      route_reason: 'all core fields are ready for final triage result',
      knowledge_summary: 'No knowledge hits retrieved for the current triage turn.',
      llm_enabled: true,
      llm_provider: 'qwen',
      llm_model: 'qwen-plus',
      llm_base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
      raw_report_summary: '主诉：喉咙不舒服。目前信息补全后，建议优先咨询耳鼻喉科。',
      llm_report_summary: '根据你补充的情况，目前更建议优先到耳鼻喉科门诊评估喉咙不适。',
      llm_used: true,
      llm_error: null,
      llm_trace: [{ agent: 'result_agent', task: 'rewrite_report_summary', used: true, fallback: false, error: null }],
    });

    const wrapper = mountView();

    await startTriage(wrapper);
    await flushPromises();

    await clickButtonByText(wrapper, '显示开发诊断');

    expect(wrapper.text()).toContain('LLM 运行状态 / 配置诊断');
    expect(wrapper.text()).toContain('LLM 已生效');
    expect(wrapper.text()).toContain('result_agent');
    expect(wrapper.text()).toContain('rewrite_report_summary');
  });
});
