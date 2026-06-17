<template>
  <main class="app-shell">
    <header class="topbar">
      <div>
        <p class="eyebrow">Intelligent Diagnostic Assistant</p>
        <h1>诊前导诊工作台</h1>
      </div>
      <div class="topbar-status">
        <span class="status-chip">{{ sessionStatusLabel }}</span>
        <span v-if="currentRiskLevel" :class="['risk-chip', currentRiskLevel]">{{ currentRiskLevel }}</span>
      </div>
    </header>

    <section class="workspace">
      <aside class="intake-panel panel">
        <section class="panel-section">
          <div class="section-head">
            <p class="eyebrow">主诉</p>
            <h2>这次哪里不舒服</h2>
          </div>

          <label for="symptom">
            症状描述
            <textarea
              id="symptom"
              v-model="symptomText"
              rows="6"
              :disabled="hasActiveConversation"
              placeholder="例如：肚子疼从昨晚开始，主要在右下腹，疼痛 5 分，没有发热。"
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
        </section>

        <section class="panel-section">
          <div class="section-head compact">
            <p class="eyebrow">患者</p>
            <h2>基本信息</h2>
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
                <option value="female">女性</option>
                <option value="male">男性</option>
              </select>
            </label>
          </div>

          <label for="pregnancy-status">
            孕产状态
            <input
              id="pregnancy-status"
              v-model="pregnancyStatus"
              name="pregnancy_status"
              :disabled="hasActiveConversation || pregnancyDisabled"
              placeholder="例如：孕早期 / 产后"
            />
            <span v-if="pregnancyDisabled" class="field-note">男性患者不会采集孕产状态</span>
          </label>
        </section>

        <details class="optional-details">
          <summary>补充资料</summary>
          <div class="optional-grid">
            <label>
              城市
              <input v-model="city" :disabled="hasActiveConversation" placeholder="可留空" />
            </label>
            <label>
              既往史
              <input v-model="medicalHistoryText" :disabled="hasActiveConversation" placeholder="高血压，糖尿病" />
            </label>
            <label>
              过敏史
              <input v-model="allergiesText" :disabled="hasActiveConversation" placeholder="青霉素" />
            </label>
            <label>
              当前用药
              <input v-model="medicationsText" :disabled="hasActiveConversation" placeholder="布洛芬，氯雷他定" />
            </label>
          </div>
        </details>

        <div class="primary-actions">
          <button type="button" :disabled="submitting || hasActiveConversation" @click="submitInitial">
            {{ submitting ? '分析中...' : '开始导诊' }}
          </button>
          <button v-if="activeSessionId" type="button" class="secondary-button" :disabled="submitting" @click="resetConversation">
            新会话
          </button>
        </div>

        <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>

        <section class="session-card">
          <div>
            <p class="session-label">会话</p>
            <p class="session-value">{{ activeSessionId || '尚未创建' }}</p>
          </div>
          <p class="session-summary">{{ patientStarterSummary }}</p>
        </section>
      </aside>

      <section class="conversation-panel panel">
        <header class="conversation-toolbar">
          <div>
            <p class="eyebrow">导诊过程</p>
            <h2>当前判断</h2>
          </div>
          <div class="stage-strip">
            <span :class="{ active: Boolean(activeSessionId) }">安全排查</span>
            <span :class="{ active: Boolean(followUpQuestion || completedResult) }">症状整理</span>
            <span :class="{ active: Boolean(completedResult) }">分科建议</span>
          </div>
        </header>

        <section v-if="followUpSummary || latestResponse?.status === 'needs_follow_up'" class="assistant-summary">
          <p class="summary-label">已理解的信息</p>
          <p>{{ followUpSummary || '已收到初始描述，正在补齐导诊所需信息。' }}</p>
        </section>

        <section v-if="followUpQuestion && knowledgeHighlight" class="assistant-summary knowledge-brief">
          <p class="summary-label">本轮导诊要点</p>
          <p>{{ knowledgeHighlight }}</p>
        </section>

        <section class="timeline">
          <div v-if="messages.length === 0" class="empty-state">
            <h3>等待开始导诊</h3>
            <p>填写左侧信息后，系统会在这里显示追问和结果。</p>
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
              <p class="eyebrow">追问</p>
              <h3>{{ followUpQuestion }}</h3>
            </div>
          </div>

          <label for="follow-up-answer" class="composer-label">
            回复
            <textarea
              id="follow-up-answer"
              v-model="answerText"
              rows="4"
              :disabled="submitting"
              placeholder="例如：改成脑袋疼，两天了，疼痛 6 分，没有发热呕吐。"
            />
          </label>

          <div class="composer-actions">
            <button type="button" :disabled="submitting || !answerText.trim()" @click="submitAnswer">
              {{ submitting ? '提交中...' : '发送回答' }}
            </button>
          </div>
        </section>

        <section v-if="completedResult" class="result-panel">
          <header class="result-header">
            <div>
              <p class="eyebrow">导诊建议</p>
              <h2>{{ completedResult.recommended_departments[0]?.name || '就医建议' }}</h2>
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
              <h3>依据</h3>
              <p>{{ completedResult.report_summary }}</p>
            </section>

            <section class="result-card">
              <h3>下一步</h3>
              <p>{{ completedResult.care_path }}</p>
            </section>

            <section class="result-card">
              <h3>就诊前准备</h3>
              <ul>
                <li v-for="item in completedResult.preparation_checklist" :key="item">{{ item }}</li>
              </ul>
            </section>
          </div>

          <section v-if="knowledgeHighlight" class="result-card knowledge-card">
            <h3>导诊要点</h3>
            <p>{{ knowledgeHighlight }}</p>
          </section>

          <div class="primary-actions">
            <button type="button" :disabled="reportLoading" @click="generateReport">
              {{ reportLoading ? '整理报告中...' : activeReportId ? '重新读取导诊报告' : '生成导诊报告' }}
            </button>
            <p v-if="reportError" class="error-text">{{ reportError }}</p>
          </div>

          <section class="follow-up-panel result-follow-up-panel">
            <div class="follow-up-head">
              <div>
                <p class="eyebrow">继续追问</p>
                <h3>结果出来后也可以继续问</h3>
              </div>
            </div>

            <div class="example-row">
              <button
                v-for="prompt in resultFollowUpPrompts"
                :key="prompt.label"
                type="button"
                class="example-chip"
                @click="useResultFollowUpPrompt(prompt.text)"
              >
                {{ prompt.label }}
              </button>
            </div>

            <label for="result-follow-up-answer" class="composer-label">
              继续提问
              <textarea
                id="result-follow-up-answer"
                v-model="answerText"
                rows="3"
                :disabled="submitting"
                placeholder="例如：为什么建议这个科？我现在要不要马上去医院？"
              />
            </label>

            <div class="composer-actions">
              <button type="button" :disabled="submitting || !answerText.trim()" @click="submitAnswer">
                {{ submitting ? '提交中...' : '继续对话' }}
              </button>
            </div>
          </section>

          <section class="disclaimer-card">
            <h3>说明</h3>
            <p>{{ completedResult.disclaimer }}</p>
          </section>
        </section>

        <section v-if="report" class="report-panel">
          <header class="result-header">
            <div>
              <p class="eyebrow">导诊报告</p>
              <h2>医生和患者共用摘要</h2>
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
              <p><strong>何时尽快就医：</strong>{{ report.patient_view.when_to_seek_urgent_care }}</p>
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
      <div>
        <p class="eyebrow">恢复会话</p>
        <h2>继续上次导诊</h2>
      </div>
      <div class="resume-actions">
        <input v-model="lookupSessionId" class="session-input" placeholder="粘贴 session id" />
        <button type="button" :disabled="loadingSession || !lookupSessionId.trim()" @click="loadSession">
          {{ loadingSession ? '加载中...' : '加载会话' }}
        </button>
      </div>
      <p v-if="sessionError" class="error-text">{{ sessionError }}</p>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';

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
    text: '喉咙痛三天，吞咽时更明显，疼痛 4 分，没有发热咳嗽。',
  },
  {
    label: '眼睛不舒服',
    text: '右眼发红发痒两天，有异物感，疼痛大概 2 分，没有视物模糊。',
  },
  {
    label: '肚子痛',
    text: '肚子疼，从昨晚开始，主要在右下腹，疼痛 5 分，没有发热呕吐。',
  },
  {
    label: '头痛',
    text: '头痛两天，主要在太阳穴附近，疼痛 6 分，没有发热呕吐。',
  },
];

const resultFollowUpPrompts = [
  { label: '为什么这个科', text: '为什么建议这个科？' },
  { label: '要不要快去医院', text: '我现在要不要马上去医院？' },
  { label: '先做什么', text: '那我现在最该先做什么？' },
  { label: '怎么准备', text: '去医院前我需要准备什么？' },
  { label: '能先线上问诊吗', text: '我可以先线上问诊吗？' },
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
const sex = ref<Sex>('unknown');
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
const pregnancyDisabled = computed(() => sex.value !== 'female');
const currentRiskLevel = computed<RiskLevel | ''>(() => latestResponse.value?.risk_level ?? '');
const knowledgeHighlight = computed(() => {
  const summary = knowledgeSummary.value.trim();
  if (!summary || summary === '未命中本地导诊知识卡。' || summary === 'No knowledge hits retrieved for the current triage turn.') {
    return '';
  }
  return summary;
});
const patientStarterSummary = computed(() => {
  const sexLabel = sex.value === 'female' ? '女性' : sex.value === 'male' ? '男性' : '性别未说明';
  const items = [`${age.value} 岁`, sexLabel];
  if (city.value.trim()) {
    items.push(city.value.trim());
  }
  return items.join(' / ');
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
    return '追问中';
  }
  return sessionStatus.value;
});

watch(sex, (value) => {
  if (value !== 'female') {
    pregnancyStatus.value = '';
  }
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

function useResultFollowUpPrompt(text: string) {
  answerText.value = text;
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
    errorMessage.value = '请先填写这次最主要的不舒服。';
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
        pregnancy_status: sex.value === 'female' ? pregnancyStatus.value.trim() || null : null,
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
