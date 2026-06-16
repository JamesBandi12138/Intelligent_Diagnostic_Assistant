<template>
  <main class="app-shell">
    <section class="hero-band">
      <div class="hero-copy">
        <p class="hero-kicker">Patient-First Triage</p>
        <h1>先把不舒服说清楚，再决定该去哪里看</h1>
        <p class="hero-lead">
          这是一个诊前导诊助手。你只需要先告诉我哪里不舒服、年龄和性别，我会像门诊分诊台一样，一次只问一个真正有必要的问题。
        </p>
      </div>
      <div class="hero-note">
        <span class="hero-badge">仅供导诊参考</span>
        <p>如果你上一句说错了，直接改口就行，比如“刚才说错了，不是发烧，是咳嗽三天”。</p>
      </div>
    </section>

    <section class="workspace">
      <aside class="intake-panel panel">
        <div class="panel-intro">
          <p class="panel-kicker">第一步</p>
          <h2>先告诉我这次最主要的不舒服</h2>
          <p>首轮只需要症状、年龄和性别。其他信息我会在需要时再问，不让你一上来就填一堆表。</p>
        </div>

        <label for="symptom">
          这次哪里不舒服
          <textarea
            id="symptom"
            v-model="symptomText"
            rows="6"
            :disabled="hasActiveConversation"
            placeholder="例如：喉咙痛三天，吞咽时更明显，不知道该挂什么科。"
          />
        </label>

        <div class="example-row" v-if="!hasActiveConversation">
          <button
            v-for="example in symptomExamples"
            :key="example.label"
            type="button"
            class="example-chip"
            @click="useSymptomExample(example.text)"
          >
            {{ example.label }}
          </button>
        </div>

        <div class="starter-grid">
          <label>
            年龄
            <input v-model.number="age" type="number" min="0" max="130" :disabled="hasActiveConversation" />
          </label>
          <label>
            性别
            <select v-model="sex" :disabled="hasActiveConversation">
              <option value="unknown">未说明</option>
              <option value="female">女</option>
              <option value="male">男</option>
            </select>
          </label>
        </div>

        <details class="optional-details">
          <summary>补充信息（可选）</summary>
          <div class="optional-grid">
            <label>
              城市
              <input v-model="city" :disabled="hasActiveConversation" placeholder="北京" />
            </label>
            <label>
              孕产状态
              <input v-model="pregnancyStatus" :disabled="hasActiveConversation" placeholder="例如：孕早期 / 产后 / 不适用" />
            </label>
            <label>
              既往史
              <input v-model="medicalHistoryText" :disabled="hasActiveConversation" placeholder="逗号分隔，例如：高血压，鼻炎" />
            </label>
            <label>
              过敏史
              <input v-model="allergiesText" :disabled="hasActiveConversation" placeholder="逗号分隔，例如：青霉素" />
            </label>
            <label class="optional-wide">
              当前用药
              <input v-model="medicationsText" :disabled="hasActiveConversation" placeholder="逗号分隔，例如：布洛芬，氯雷他定" />
            </label>
          </div>
        </details>

        <div class="primary-actions">
          <button type="button" :disabled="submitting || hasActiveConversation" @click="submitInitial">
            {{ submitting ? '正在发起导诊...' : '开始导诊' }}
          </button>
          <button v-if="activeSessionId" type="button" class="secondary-button" :disabled="submitting" @click="resetConversation">
            开始新会话
          </button>
        </div>

        <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>

        <section class="session-panel">
          <div>
            <p class="session-label">当前会话</p>
            <p class="session-value">{{ activeSessionId || '尚未创建' }}</p>
          </div>
          <div class="session-meta">
            <span class="status-chip">{{ sessionStatusLabel }}</span>
            <span v-if="currentRiskLevel" :class="['risk-chip', currentRiskLevel]">{{ currentRiskLevel }}</span>
          </div>
          <p class="session-summary">{{ patientStarterSummary }}</p>
        </section>

        <section class="tip-panel">
          <h3>对话提示</h3>
          <ul>
            <li>如果我理解错了，直接改口，不用从头开始。</li>
            <li>如果有危险信号，比如胸痛、呼吸困难、持续高热，请直接说明。</li>
            <li>如果你不知道怎么描述，可以用“轻微 / 中等 / 严重”或 0 到 10 分来形容。</li>
          </ul>
        </section>
      </aside>

      <section class="conversation-panel panel">
        <header class="conversation-header">
          <div>
            <p class="panel-kicker">第二步</p>
            <h2>像和分诊护士说话一样告诉我情况</h2>
            <p>我会先整理已经知道的重点，再继续追问真正影响分诊判断的那一项。</p>
          </div>
          <div class="conversation-status">
            <span class="status-chip">{{ sessionStatusLabel }}</span>
            <span v-if="currentRiskLevel" :class="['risk-chip', currentRiskLevel]">{{ currentRiskLevel }}</span>
          </div>
        </header>

        <section class="assistant-summary" v-if="followUpSummary || latestResponse?.status === 'needs_follow_up'">
          <p class="assistant-summary-label">我目前的理解</p>
          <p>{{ followUpSummary || '我已经收到你的初步描述，接下来会继续确认最关键的信息。' }}</p>
        </section>

        <section class="timeline">
          <div v-if="messages.length === 0" class="empty-state">
            <h3>你可以这样开始</h3>
            <p>“喉咙痛三天，吞咽时更明显，没有发热。”</p>
            <p>“肚子痛，主要在右下腹，从昨晚开始。”</p>
            <p>“咳嗽一周，晚上更明显，担心是不是该去医院。”</p>
          </div>

          <article
            v-for="(message, index) in messages"
            :key="`${message.role}-${index}`"
            :class="['message-card', message.role, message.kind]"
          >
            <p class="message-role">{{ message.role === 'assistant' ? '导诊助手' : '你' }}</p>
            <p class="message-content">{{ message.content }}</p>
          </article>
        </section>

        <section v-if="followUpQuestion" class="follow-up-panel">
          <div class="follow-up-head">
            <div>
              <p class="panel-kicker">当前问题</p>
              <h3>{{ followUpQuestion }}</h3>
            </div>
            <p class="follow-up-tip">如果你上一句说错了，可以直接改口，我会按你更正后的内容继续判断。</p>
          </div>

          <label for="follow-up-answer" class="composer-label">
            继续补充
            <textarea
              id="follow-up-answer"
              v-model="answerText"
              rows="4"
              :disabled="submitting"
              placeholder="直接回复这一问即可，例如：喉咙痛三天，疼痛 4 分，没有发热咳嗽。"
            />
          </label>

          <div class="composer-actions">
            <button type="button" :disabled="submitting || !answerText.trim()" @click="submitAnswer">
              {{ submitting ? '正在提交...' : '发送回答' }}
            </button>
          </div>
        </section>

        <section v-if="completedResult" class="result-panel">
          <header class="result-header">
            <div>
              <p class="panel-kicker">导诊建议</p>
              <h2>先给你一个清楚的就医建议</h2>
            </div>
            <span :class="['risk-chip', completedResult.risk_level]">{{ completedResult.risk_level }}</span>
          </header>

          <p v-if="completedResult.emergency_advice" class="emergency-banner">{{ completedResult.emergency_advice }}</p>

          <div class="result-grid">
            <section class="result-card focus">
              <h3>建议优先就诊</h3>
              <ul>
                <li v-for="department in completedResult.recommended_departments" :key="department.name">
                  <strong>{{ department.name }}</strong>
                  <span>{{ department.reason }}</span>
                </li>
              </ul>
            </section>

            <section class="result-card">
              <h3>为什么这样建议</h3>
              <p>{{ completedResult.report_summary }}</p>
            </section>

            <section class="result-card">
              <h3>接下来怎么做</h3>
              <p>{{ completedResult.care_path }}</p>
            </section>

            <section class="result-card">
              <h3>去之前准备什么</h3>
              <ul>
                <li v-for="item in completedResult.preparation_checklist" :key="item">{{ item }}</li>
              </ul>
            </section>
          </div>

          <div class="primary-actions">
            <button type="button" :disabled="reportLoading" @click="generateReport">
              {{ reportLoading ? '正在整理报告...' : activeReportId ? '重新读取导诊报告' : '生成导诊报告' }}
            </button>
            <p v-if="reportError" class="error-text">{{ reportError }}</p>
          </div>

          <section class="disclaimer-card">
            <h3>说明</h3>
            <p>{{ completedResult.disclaimer }}</p>
          </section>
        </section>

        <section v-if="report" class="report-panel">
          <header class="result-header">
            <div>
              <p class="panel-kicker">导诊报告</p>
              <h2>给患者和医生都能看懂的一份摘要</h2>
            </div>
            <span :class="['risk-chip', report.triage_summary.risk_level]">{{ report.triage_summary.risk_level }}</span>
          </header>

          <div class="result-grid">
            <section class="result-card">
              <h3>报告概览</h3>
              <p><strong>主诉：</strong>{{ report.triage_summary.chief_complaint }}</p>
              <p><strong>建议科室：</strong>{{ departmentSummary }}</p>
              <p><strong>就医路径：</strong>{{ report.triage_summary.care_path }}</p>
            </section>

            <section class="result-card">
              <h3>患者快照</h3>
              <ul>
                <li>年龄：{{ report.patient_snapshot.age }}</li>
                <li>性别：{{ report.patient_snapshot.sex }}</li>
                <li>孕产状态：{{ report.patient_snapshot.pregnancy_status || '无' }}</li>
                <li>既往史：{{ joinList(report.patient_snapshot.medical_history) }}</li>
                <li>过敏史：{{ joinList(report.patient_snapshot.allergies) }}</li>
                <li>当前用药：{{ joinList(report.patient_snapshot.medications) }}</li>
              </ul>
            </section>
          </div>

          <div class="result-grid">
            <section class="result-card">
              <h3>医生速览</h3>
              <p><strong>主诉：</strong>{{ report.doctor_view.chief_complaint }}</p>
              <ul>
                <li v-for="(value, key) in report.doctor_view.key_facts" :key="key">
                  {{ factLabels[key] || key }}：{{ value }}
                </li>
              </ul>
              <p><strong>风险提示：</strong>{{ report.doctor_view.risk_notes }}</p>
              <p><strong>科室建议：</strong>{{ report.doctor_view.recommended_department_summary }}</p>
            </section>

            <section class="result-card">
              <h3>患者说明</h3>
              <p>{{ report.patient_view.what_this_means }}</p>
              <p><strong>为什么建议这个科：</strong>{{ report.patient_view.why_this_department }}</p>
              <p><strong>什么时候尽快就医：</strong>{{ report.patient_view.when_to_seek_urgent_care }}</p>
            </section>
          </div>

          <div class="result-grid">
            <section class="result-card">
              <h3>医生建议携带</h3>
              <ul>
                <li v-for="item in report.doctor_view.preparation_checklist" :key="item">{{ item }}</li>
              </ul>
            </section>

            <section class="result-card">
              <h3>患者准备清单</h3>
              <ul>
                <li v-for="item in report.patient_view.what_to_prepare" :key="item">{{ item }}</li>
              </ul>
            </section>
          </div>
        </section>

        <div v-if="hasDiagnostics" class="diagnostic-toggle-row">
          <button type="button" class="secondary-button diagnostic-toggle" @click="toggleDebugMode">
            {{ debugMode ? '隐藏开发诊断' : '显示开发诊断' }}
          </button>
        </div>

        <details v-if="debugMode && hasDiagnostics" class="diagnostic-drawer" open>
          <summary>开发调试信息</summary>

          <section v-if="hasDebugPanel" class="diagnostic-block">
            <h3>LangGraph 编排</h3>
            <p v-if="currentAgent"><strong>current_agent:</strong> {{ currentAgent }}</p>
            <p v-if="routeReason"><strong>route_reason:</strong> {{ routeReason }}</p>
            <p v-if="knowledgeSummary"><strong>knowledge_summary:</strong> {{ knowledgeSummary }}</p>
            <p v-if="nodeTrace.length"><strong>node_trace:</strong> {{ nodeTrace.join(' -> ') }}</p>
            <ul v-if="agentTrace.length" class="debug-list">
              <li v-for="(item, index) in agentTrace" :key="`${item.agent}-${index}`">
                {{ item.agent }} | {{ item.summary }}
              </li>
            </ul>
          </section>

          <section v-if="hasLlmDiagnostics" class="diagnostic-block llm-block">
            <h3>LLM 运行状态 / 配置诊断</h3>
            <div class="diagnostic-grid">
              <div>
                <p><strong>status:</strong> {{ llmStatusLabel }}</p>
                <p><strong>enabled:</strong> {{ llmEnabled }}</p>
                <p v-if="llmProvider"><strong>provider:</strong> {{ llmProvider }}</p>
                <p v-if="llmModel"><strong>model:</strong> {{ llmModel }}</p>
                <p v-if="llmBaseUrl"><strong>base_url:</strong> {{ llmBaseUrl }}</p>
              </div>
              <div>
                <p v-if="llmUsed !== null"><strong>llm_used:</strong> {{ llmUsed }}</p>
                <p><strong>fallback:</strong> {{ llmFallback }}</p>
                <p v-if="llmError"><strong>error_code:</strong> {{ llmError }}</p>
                <p v-if="llmErrorLabel"><strong>error_meaning:</strong> {{ llmErrorLabel }}</p>
                <p v-if="lastLlmTraceEntry"><strong>last_agent:</strong> {{ lastLlmTraceEntry.agent }}</p>
                <p v-if="lastLlmTraceEntry"><strong>last_task:</strong> {{ lastLlmTraceEntry.task }}</p>
              </div>
            </div>
            <div class="diagnostic-grid">
              <div v-if="rawFollowUpQuestion || llmFollowUpQuestion">
                <p v-if="rawFollowUpQuestion"><strong>follow_up_raw:</strong> {{ rawFollowUpQuestion }}</p>
                <p v-if="llmFollowUpQuestion"><strong>follow_up_llm:</strong> {{ llmFollowUpQuestion }}</p>
              </div>
              <div v-if="rawReportSummary || llmReportSummary">
                <p v-if="rawReportSummary"><strong>summary_raw:</strong> {{ rawReportSummary }}</p>
                <p v-if="llmReportSummary"><strong>summary_llm:</strong> {{ llmReportSummary }}</p>
              </div>
            </div>
            <ul v-if="llmTrace.length" class="debug-list">
              <li v-for="(item, index) in llmTrace" :key="`${item.agent}-${item.task}-diagnostic-${index}`">
                {{ item.agent }} | {{ item.task }} | used={{ item.used }} | fallback={{ item.fallback }}<span v-if="item.error"> | error={{ item.error }}</span>
              </li>
            </ul>
          </section>
        </details>
      </section>
    </section>

    <section class="resume-panel panel">
      <div class="panel-intro">
        <p class="panel-kicker">继续上次会话</p>
        <h2>如果你刷新了页面，可以把会话拉回来</h2>
        <p>系统会优先恢复最近一次本地会话，你也可以手动输入会话 ID。</p>
      </div>
      <div class="resume-actions">
        <input v-model="lookupSessionId" class="session-input" placeholder="粘贴 session id" />
        <button type="button" :disabled="loadingSession || !lookupSessionId.trim()" @click="loadSession">
          {{ loadingSession ? '正在加载...' : '加载会话' }}
        </button>
      </div>
      <p v-if="sessionError" class="error-text">{{ sessionError }}</p>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';

import {
  analyzeTriage,
  type AgentTraceEntry,
  createTriageReport,
  createTriageSession,
  getTriageReport,
  getTriageSession,
  type AnalyzeTriageResponse,
  type CompletedTriageResponse,
  type LlmTraceEntry,
  type ReportResponse,
  type RiskLevel,
  type Sex,
  type TriageMessage,
  type TriageSessionDetailResponse,
} from '../api';

const SESSION_STORAGE_KEY = 'ida-active-session-id';
const DEBUG_STORAGE_KEY = 'ida-debug-diagnostics';

const symptomExamples = [
  {
    label: '喉咙痛',
    text: '喉咙痛三天，吞咽时更明显，没有发热。',
  },
  {
    label: '眼睛不舒服',
    text: '右眼发红发痒两天，有异物感，疼痛大概 2 分，没有视物模糊。',
  },
  {
    label: '肚子痛',
    text: '肚子痛，从昨晚开始，主要在右下腹，不确定该挂什么科。',
  },
];

const factLabels: Record<string, string> = {
  location: '症状部位',
  duration: '持续时间',
  severity: '严重程度',
  accompanying_symptoms: '伴随症状',
  special_context: '特殊背景',
};

const symptomText = ref('');
const age = ref(32);
const sex = ref<Sex>('female');
const pregnancyStatus = ref('');
const city = ref('');
const medicalHistoryText = ref('');
const allergiesText = ref('');
const medicationsText = ref('');
const answerText = ref('');

const activeSessionId = ref('');
const activeReportId = ref('');
const lookupSessionId = ref('');
const sessionStatus = ref('created');
const messages = ref<TriageMessage[]>([]);
const followUpQuestion = ref('');
const followUpSummary = ref('');
const completedResult = ref<CompletedTriageResponse | null>(null);
const latestResponse = ref<AnalyzeTriageResponse | null>(null);
const report = ref<ReportResponse | null>(null);
const currentAgent = ref('');
const nodeTrace = ref<string[]>([]);
const agentTrace = ref<AgentTraceEntry[]>([]);
const routeReason = ref('');
const knowledgeSummary = ref('');
const rawFollowUpQuestion = ref('');
const llmFollowUpQuestion = ref('');
const rawReportSummary = ref('');
const llmReportSummary = ref('');
const llmEnabled = ref(false);
const llmProvider = ref('');
const llmModel = ref('');
const llmBaseUrl = ref('');
const llmUsed = ref<boolean | null>(null);
const llmError = ref('');
const llmTrace = ref<LlmTraceEntry[]>([]);

const submitting = ref(false);
const loadingSession = ref(false);
const reportLoading = ref(false);
const errorMessage = ref('');
const sessionError = ref('');
const reportError = ref('');
const debugMode = ref(false);

const hasActiveConversation = computed(() => Boolean(activeSessionId.value) && sessionStatus.value !== 'completed');
const currentRiskLevel = computed<RiskLevel | ''>(() => latestResponse.value?.risk_level ?? '');
const patientStarterSummary = computed(() => {
  const items = [`${age.value} 岁`, sex.value === 'female' ? '女性' : sex.value === 'male' ? '男性' : '性别未说明'];
  if (city.value.trim()) {
    items.push(city.value.trim());
  }
  return items.join(' · ');
});
const hasDebugPanel = computed(
  () =>
    Boolean(currentAgent.value) ||
    nodeTrace.value.length > 0 ||
    agentTrace.value.length > 0 ||
    Boolean(routeReason.value) ||
    Boolean(knowledgeSummary.value),
);
const hasLlmDiagnostics = computed(
  () =>
    llmEnabled.value ||
    Boolean(llmProvider.value) ||
    Boolean(llmModel.value) ||
    Boolean(llmBaseUrl.value) ||
    llmUsed.value !== null ||
    Boolean(llmError.value) ||
    llmTrace.value.length > 0 ||
    Boolean(rawFollowUpQuestion.value) ||
    Boolean(llmFollowUpQuestion.value) ||
    Boolean(rawReportSummary.value) ||
    Boolean(llmReportSummary.value),
);
const hasDiagnostics = computed(() => hasDebugPanel.value || hasLlmDiagnostics.value);
const lastLlmTraceEntry = computed(() => llmTrace.value[llmTrace.value.length - 1] || null);
const llmFallback = computed(() => Boolean(lastLlmTraceEntry.value?.fallback));
const llmStatusLabel = computed(() => {
  if (!llmEnabled.value) {
    return 'LLM 未启用';
  }
  if (llmUsed.value) {
    return 'LLM 已生效';
  }
  if (llmFallback.value) {
    return '已回退到规则结果';
  }
  return '本轮未调用 LLM';
});
const llmErrorLabel = computed(() => {
  if (!llmError.value) {
    return '';
  }
  if (llmError.value === 'transport_error') {
    return '供应商 / 网络 / 鉴权 / 额度异常';
  }
  if (llmError.value === 'format_error') {
    return '模型输出格式不可解析';
  }
  if (llmError.value === 'safety_reject') {
    return '模型输出未通过安全约束';
  }
  return llmError.value;
});
const departmentSummary = computed(() => {
  if (!report.value) {
    return '';
  }
  return report.value.triage_summary.recommended_departments.map((item) => item.name).join('、');
});

const sessionStatusLabel = computed(() => {
  if (!activeSessionId.value) {
    return '尚未开始';
  }
  if (sessionStatus.value === 'completed') {
    return '已完成';
  }
  if (sessionStatus.value === 'needs_follow_up' || sessionStatus.value === 'collecting') {
    return '继续追问中';
  }
  return sessionStatus.value;
});

function splitList(value: string): string[] {
  return value
    .split(/[,\n，、]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function joinList(items: string[]): string {
  return items.length ? items.join('、') : '无';
}

function useSymptomExample(text: string) {
  symptomText.value = text;
}

function toggleDebugMode() {
  debugMode.value = !debugMode.value;
  if (debugMode.value) {
    localStorage.setItem(DEBUG_STORAGE_KEY, 'true');
    return;
  }
  localStorage.removeItem(DEBUG_STORAGE_KEY);
}

function persistSessionId(sessionId: string | null) {
  if (sessionId) {
    localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
    return;
  }
  localStorage.removeItem(SESSION_STORAGE_KEY);
}

async function loadReportById(reportId: string) {
  reportLoading.value = true;
  reportError.value = '';
  try {
    report.value = await getTriageReport(reportId);
    activeReportId.value = reportId;
  } catch (error) {
    reportError.value = error instanceof Error ? error.message : '报告加载失败，请稍后再试。';
  } finally {
    reportLoading.value = false;
  }
}

async function applySessionState(session: TriageSessionDetailResponse) {
  activeSessionId.value = session.session_id;
  activeReportId.value = session.report_id || '';
  lookupSessionId.value = session.session_id;
  sessionStatus.value = session.status;
  messages.value = session.messages;
  followUpQuestion.value = session.current_question || '';
  latestResponse.value = session.latest_result;
  currentAgent.value = session.current_agent || '';
  nodeTrace.value = session.node_trace || [];
  agentTrace.value = session.agent_trace || [];
  routeReason.value = session.route_reason || '';
  knowledgeSummary.value = session.knowledge_summary || '';
  rawFollowUpQuestion.value = session.raw_follow_up_question || '';
  llmFollowUpQuestion.value = session.llm_follow_up_question || '';
  rawReportSummary.value = session.raw_report_summary || '';
  llmReportSummary.value = session.llm_report_summary || '';
  llmEnabled.value = Boolean(session.llm_enabled);
  llmProvider.value = session.llm_provider || '';
  llmModel.value = session.llm_model || '';
  llmBaseUrl.value = session.llm_base_url || '';
  llmUsed.value = typeof session.llm_used === 'boolean' ? session.llm_used : null;
  llmError.value = session.llm_error || '';
  llmTrace.value = session.llm_trace || [];

  if (session.latest_result?.status === 'needs_follow_up') {
    followUpSummary.value = session.latest_result.known_facts_summary;
    completedResult.value = null;
  } else {
    followUpSummary.value = '';
    completedResult.value = session.latest_result ?? null;
  }

  if (session.report_id) {
    await loadReportById(session.report_id);
  } else {
    report.value = null;
  }

  persistSessionId(session.session_id);
}

async function syncSession(sessionId: string) {
  const session = await getTriageSession(sessionId);
  await applySessionState(session);
}

async function submitInitial() {
  if (!symptomText.value.trim()) {
    errorMessage.value = '请先告诉我这次哪里不舒服。';
    return;
  }

  submitting.value = true;
  errorMessage.value = '';
  reportError.value = '';

  try {
    const createdSession = await createTriageSession();
    activeSessionId.value = createdSession.session_id;
    activeReportId.value = '';
    lookupSessionId.value = createdSession.session_id;
    sessionStatus.value = createdSession.status;

    const response = await analyzeTriage({
      session_id: createdSession.session_id,
      patient: {
        age: age.value,
        sex: sex.value,
        pregnancy_status: pregnancyStatus.value.trim() || null,
        medical_history: splitList(medicalHistoryText.value),
        allergies: splitList(allergiesText.value),
        medications: splitList(medicationsText.value),
      },
      symptom_text: symptomText.value.trim(),
      city: city.value.trim() || undefined,
    });

    latestResponse.value = response;
    await syncSession(response.session_id);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '导诊发起失败，请稍后再试。';
  } finally {
    submitting.value = false;
  }
}

async function submitAnswer() {
  if (!activeSessionId.value || !answerText.value.trim()) {
    return;
  }

  submitting.value = true;
  errorMessage.value = '';
  reportError.value = '';

  try {
    const response = await analyzeTriage({
      session_id: activeSessionId.value,
      answer: answerText.value.trim(),
    });
    latestResponse.value = response;
    answerText.value = '';
    await syncSession(response.session_id);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '回答提交失败，请稍后再试。';
  } finally {
    submitting.value = false;
  }
}

async function generateReport() {
  if (!activeSessionId.value) {
    return;
  }

  reportLoading.value = true;
  reportError.value = '';

  try {
    const generated = await createTriageReport({ session_id: activeSessionId.value });
    report.value = generated;
    activeReportId.value = generated.report_id;
    await syncSession(activeSessionId.value);
  } catch (error) {
    reportError.value = error instanceof Error ? error.message : '报告生成失败，请稍后再试。';
  } finally {
    reportLoading.value = false;
  }
}

async function loadSession() {
  if (!lookupSessionId.value.trim()) {
    return;
  }

  loadingSession.value = true;
  sessionError.value = '';

  try {
    await syncSession(lookupSessionId.value.trim());
  } catch (error) {
    sessionError.value = error instanceof Error ? error.message : '会话加载失败，请稍后再试。';
  } finally {
    loadingSession.value = false;
  }
}

function resetConversation() {
  activeSessionId.value = '';
  activeReportId.value = '';
  sessionStatus.value = 'created';
  messages.value = [];
  followUpQuestion.value = '';
  followUpSummary.value = '';
  completedResult.value = null;
  latestResponse.value = null;
  report.value = null;
  currentAgent.value = '';
  nodeTrace.value = [];
  agentTrace.value = [];
  routeReason.value = '';
  knowledgeSummary.value = '';
  rawFollowUpQuestion.value = '';
  llmFollowUpQuestion.value = '';
  rawReportSummary.value = '';
  llmReportSummary.value = '';
  llmEnabled.value = false;
  llmProvider.value = '';
  llmModel.value = '';
  llmBaseUrl.value = '';
  llmUsed.value = null;
  llmError.value = '';
  llmTrace.value = [];
  answerText.value = '';
  lookupSessionId.value = '';
  errorMessage.value = '';
  sessionError.value = '';
  reportError.value = '';
  debugMode.value = false;
  localStorage.removeItem(DEBUG_STORAGE_KEY);
  persistSessionId(null);
}

onMounted(async () => {
  debugMode.value = localStorage.getItem(DEBUG_STORAGE_KEY) === 'true';
  const storedSessionId = localStorage.getItem(SESSION_STORAGE_KEY);
  if (!storedSessionId) {
    return;
  }

  loadingSession.value = true;
  try {
    await syncSession(storedSessionId);
  } catch {
    persistSessionId(null);
  } finally {
    loadingSession.value = false;
  }
});
</script>
