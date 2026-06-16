<template>
  <main class="layout">
    <section class="workspace">
      <header class="topbar hero">
        <div>
          <p class="eyebrow">Pre-Consultation Triage</p>
          <h1>智能导诊与就医助手</h1>
          <p class="lead">
            先整理症状，再按需要逐条追问，最后给出就医建议，并生成一份便于患者和医生查看的导诊报告。
          </p>
        </div>
        <span class="badge">非诊断 · 仅导诊参考</span>
      </header>

      <section class="workspace-grid">
        <article class="panel input-panel">
          <div class="section-title">
            <h2>首轮信息</h2>
            <p>首次提交时尽量说明主要不适和患者基础情况，系统会在信息不足时继续追问。</p>
          </div>

          <label for="symptom">
            症状描述
            <textarea
              id="symptom"
              v-model="symptomText"
              rows="7"
              :disabled="hasActiveConversation"
              placeholder="例如：喉咙痛三天，吞咽时更明显，不知道该挂什么科。"
            />
          </label>

          <div class="form-grid">
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
            <label>
              孕产状态
              <input v-model="pregnancyStatus" :disabled="hasActiveConversation" placeholder="例如：孕早期 / 产后 / 不适用" />
            </label>
            <label>
              城市
              <input v-model="city" :disabled="hasActiveConversation" placeholder="北京" />
            </label>
            <label>
              既往史
              <input v-model="medicalHistoryText" :disabled="hasActiveConversation" placeholder="逗号分隔，例如：高血压, 过敏性鼻炎" />
            </label>
            <label>
              过敏史
              <input v-model="allergiesText" :disabled="hasActiveConversation" placeholder="逗号分隔，例如：青霉素" />
            </label>
            <label class="wide">
              当前用药
              <input v-model="medicationsText" :disabled="hasActiveConversation" placeholder="逗号分隔，例如：布洛芬, 氯雷他定" />
            </label>
          </div>

          <div class="actions">
            <button type="button" :disabled="submitting || hasActiveConversation" @click="submitInitial">
              {{ submitting ? '提交中...' : '开始导诊' }}
            </button>
            <button v-if="activeSessionId" type="button" class="ghost-button" :disabled="submitting" @click="resetConversation">
              开始新会话
            </button>
          </div>

          <p v-if="errorMessage" class="error">{{ errorMessage }}</p>

          <div class="result-card session-card">
            <p class="subtle">当前会话：{{ activeSessionId || '尚未创建' }}</p>
            <p class="subtle">当前状态：{{ sessionStatusLabel }}</p>
            <p class="subtle">当前报告：{{ activeReportId || '尚未生成' }}</p>
          </div>
          <section
            v-if="showDebugPanel"
            class="result-card debug-card"
          >
            <h3>编排调试</h3>
            <p v-if="currentAgent"><strong>current_agent:</strong> {{ currentAgent }}</p>
            <p v-if="routeReason"><strong>route_reason:</strong> {{ routeReason }}</p>
            <p v-if="knowledgeSummary"><strong>knowledge_summary:</strong> {{ knowledgeSummary }}</p>
            <p v-if="nodeTrace.length"><strong>node_trace:</strong> {{ nodeTrace.join(' -> ') }}</p>
            <p v-if="llmUsed !== null"><strong>llm_used:</strong> {{ llmUsed }}</p>
            <p v-if="llmError"><strong>llm_error:</strong> {{ llmError }}</p>
            <p v-if="rawFollowUpQuestion"><strong>raw_follow_up_question:</strong> {{ rawFollowUpQuestion }}</p>
            <p v-if="llmFollowUpQuestion"><strong>llm_follow_up_question:</strong> {{ llmFollowUpQuestion }}</p>
            <p v-if="rawReportSummary"><strong>raw_report_summary:</strong> {{ rawReportSummary }}</p>
            <p v-if="llmReportSummary"><strong>llm_report_summary:</strong> {{ llmReportSummary }}</p>
            <ul v-if="agentTrace.length" class="debug-list">
              <li v-for="(item, index) in agentTrace" :key="`${item.agent}-${index}`">
                {{ item.agent }} | {{ item.summary }}
              </li>
            </ul>
            <ul v-if="llmTrace.length" class="debug-list">
              <li v-for="(item, index) in llmTrace" :key="`${item.agent}-${item.task}-${index}`">
                {{ item.agent }} | {{ item.task }} | used={{ item.used }} | fallback={{ item.fallback }}<span v-if="item.error"> | error={{ item.error }}</span>
              </li>
            </ul>
          </section>
          <section v-if="showLlmDiagnostics" class="result-card llm-diagnostic-card">
            <h3>LLM 运行状态 / 配置诊断</h3>
            <div class="llm-diagnostic-grid">
              <div>
                <p><strong>status:</strong> {{ llmStatusLabel }}</p>
                <p><strong>enabled:</strong> {{ llmEnabled }}</p>
                <p v-if="llmProvider"><strong>provider:</strong> {{ llmProvider }}</p>
                <p v-if="llmModel"><strong>model:</strong> {{ llmModel }}</p>
                <p v-if="llmBaseUrl"><strong>base_url:</strong> {{ llmBaseUrl }}</p>
                <p v-if="currentAgent"><strong>current_agent:</strong> {{ currentAgent }}</p>
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
            <div class="llm-diagnostic-grid">
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
        </article>

        <article class="panel conversation-panel">
          <div class="section-title">
            <div class="conversation-head">
              <div>
                <h2>导诊对话</h2>
                <p>系统一次只问一个最关键的问题，避免把用户问乱。</p>
              </div>
              <span v-if="currentRiskLevel" :class="['risk', currentRiskLevel]">{{ currentRiskLevel }}</span>
            </div>
          </div>

          <div class="timeline">
            <div v-if="messages.length === 0" class="empty-state">
              还没有会话内容。提交首轮症状后，这里会显示系统追问和最终结果。
            </div>

            <article
              v-for="(message, index) in messages"
              :key="`${message.role}-${index}`"
              :class="['message-card', message.role, message.kind]"
            >
              <p class="message-role">{{ message.role === 'assistant' ? '系统' : '用户' }}</p>
              <p class="message-content">{{ message.content }}</p>
            </article>
          </div>

          <section v-if="followUpQuestion" class="follow-up-box">
            <div class="section-title compact">
              <h3>继续补充</h3>
              <p>{{ followUpSummary || '系统正在根据已有信息继续收集关键字段。' }}</p>
            </div>
            <label for="follow-up-answer">
              当前问题
              <div class="question-chip">{{ followUpQuestion }}</div>
              <textarea
                id="follow-up-answer"
                v-model="answerText"
                rows="4"
                :disabled="submitting"
                placeholder="直接回答这一个问题即可，例如：喉咙痛三天，疼痛约 4 分，没有发烧咳嗽。"
              />
            </label>
            <div class="actions">
              <button type="button" :disabled="submitting || !answerText.trim()" @click="submitAnswer">
                {{ submitting ? '提交中...' : '提交回答' }}
              </button>
            </div>
          </section>

          <section v-if="completedResult" class="result-stack">
            <div class="result-header">
              <div>
                <h2>导诊结果</h2>
                <p class="subtle">会话 ID：{{ completedResult.session_id }}</p>
              </div>
              <span :class="['risk', completedResult.risk_level]">{{ completedResult.risk_level }}</span>
            </div>

            <p v-if="completedResult.emergency_advice" class="emergency">{{ completedResult.emergency_advice }}</p>

            <div class="result-grid">
              <section class="result-card">
                <h3>推荐科室</h3>
                <ul>
                  <li v-for="department in completedResult.recommended_departments" :key="department.name">
                    <strong>{{ department.name }}</strong>
                    <span> · {{ department.reason }}</span>
                  </li>
                </ul>
              </section>

              <section class="result-card">
                <h3>就医路径</h3>
                <p>{{ completedResult.care_path }}</p>
              </section>

              <section class="result-card">
                <h3>就诊准备</h3>
                <ul>
                  <li v-for="item in completedResult.preparation_checklist" :key="item">{{ item }}</li>
                </ul>
              </section>

              <section class="result-card">
                <h3>结果摘要</h3>
                <p>{{ completedResult.report_summary }}</p>
              </section>
            </div>

            <div class="actions report-actions">
              <button type="button" :disabled="reportLoading" @click="generateReport">
                {{ reportLoading ? '处理中...' : activeReportId ? '重新读取报告' : '生成导诊报告' }}
              </button>
              <p v-if="reportError" class="error">{{ reportError }}</p>
            </div>

            <section class="result-card summary-card">
              <h3>免责声明</h3>
              <p class="disclaimer">{{ completedResult.disclaimer }}</p>
            </section>
          </section>

          <section v-if="report" class="report-stack">
            <div class="result-header">
              <div>
                <h2>导诊报告</h2>
                <p class="subtle">报告 ID：{{ report.report_id }}</p>
              </div>
              <span :class="['risk', report.triage_summary.risk_level]">{{ report.triage_summary.risk_level }}</span>
            </div>

            <div class="report-grid">
              <section class="result-card">
                <h3>报告概览</h3>
                <p><strong>主诉：</strong>{{ report.triage_summary.chief_complaint }}</p>
                <p><strong>推荐科室：</strong>{{ departmentSummary }}</p>
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

            <div class="report-grid">
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
                <p><strong>为什么建议这个科室：</strong>{{ report.patient_view.why_this_department }}</p>
                <p><strong>什么时候尽快就医：</strong>{{ report.patient_view.when_to_seek_urgent_care }}</p>
              </section>
            </div>

            <div class="report-grid">
              <section class="result-card">
                <h3>医生查看时建议携带</h3>
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

            <section class="result-card summary-card">
              <h3>报告免责声明</h3>
              <p class="disclaimer">{{ report.disclaimer }}</p>
            </section>
          </section>
        </article>
      </section>

      <section class="panel input-panel">
        <div class="section-title">
          <h2>按会话恢复</h2>
          <p>刷新后会优先恢复本地最近一次会话，也可以手动输入会话 ID 拉回状态。</p>
        </div>
        <div class="actions">
          <input v-model="lookupSessionId" class="session-input" placeholder="粘贴 session id" />
          <button type="button" :disabled="loadingSession || !lookupSessionId.trim()" @click="loadSession">
            {{ loadingSession ? '加载中...' : '加载会话' }}
          </button>
        </div>
        <p v-if="sessionError" class="error">{{ sessionError }}</p>
      </section>
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

const factLabels: Record<string, string> = {
  location: '症状部位',
  duration: '持续时间',
  severity: '严重程度',
  accompanying_symptoms: '伴随症状',
  special_context: '特殊背景',
};

const symptomText = ref('喉咙不舒服');
const age = ref(32);
const sex = ref<Sex>('female');
const pregnancyStatus = ref('');
const city = ref('北京');
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

const hasActiveConversation = computed(() => Boolean(activeSessionId.value) && sessionStatus.value !== 'completed');
const currentRiskLevel = computed<RiskLevel | ''>(() => latestResponse.value?.risk_level ?? '');
const showDebugPanel = computed(
  () =>
    Boolean(currentAgent.value) ||
    nodeTrace.value.length > 0 ||
    agentTrace.value.length > 0 ||
    Boolean(routeReason.value) ||
    Boolean(knowledgeSummary.value) ||
    llmUsed.value !== null ||
    Boolean(llmError.value) ||
    Boolean(rawFollowUpQuestion.value) ||
    Boolean(llmFollowUpQuestion.value) ||
    Boolean(rawReportSummary.value) ||
    Boolean(llmReportSummary.value) ||
    llmTrace.value.length > 0,
);
const showLlmDiagnostics = computed(
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
    return '未开始';
  }
  if (sessionStatus.value === 'completed') {
    return '已完成';
  }
  if (sessionStatus.value === 'needs_follow_up' || sessionStatus.value === 'collecting') {
    return '追问中';
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
    reportError.value = error instanceof Error ? error.message : '报告加载失败，请稍后重试。';
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
    errorMessage.value = '请先填写症状描述。';
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
    errorMessage.value = error instanceof Error ? error.message : '导诊发起失败，请稍后重试。';
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
    errorMessage.value = error instanceof Error ? error.message : '回答提交失败，请稍后重试。';
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
    reportError.value = error instanceof Error ? error.message : '报告生成失败，请稍后重试。';
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
    sessionError.value = error instanceof Error ? error.message : '会话加载失败，请稍后重试。';
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
  persistSessionId(null);
}

onMounted(async () => {
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
