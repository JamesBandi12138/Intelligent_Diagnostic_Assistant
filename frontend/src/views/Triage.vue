<template>
  <main class="layout">
    <section class="workspace">
      <header class="topbar hero">
        <div>
          <p class="eyebrow">Pre-Consultation Triage</p>
          <h1>智能导诊与就医助手</h1>
          <p class="lead">
            先整理症状，再按需要逐条追问，最后给出更稳妥的就医路径建议。
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
          </div>
        </article>

        <article class="panel conversation-panel">
          <div class="section-title">
            <div class="conversation-head">
              <div>
                <h2>导诊对话</h2>
                <p>系统一次只会问一个最关键的问题，避免把用户问乱。</p>
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

            <section class="result-card summary-card">
              <h3>免责声明</h3>
              <p class="disclaimer">{{ completedResult.disclaimer }}</p>
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
          <input
            v-model="lookupSessionId"
            class="session-input"
            placeholder="粘贴 session id"
          />
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
  createTriageSession,
  getTriageSession,
  type AnalyzeTriageResponse,
  type CompletedTriageResponse,
  type RiskLevel,
  type Sex,
  type TriageMessage,
  type TriageSessionDetailResponse,
} from '../api';

const SESSION_STORAGE_KEY = 'ida-active-session-id';

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
const lookupSessionId = ref('');
const sessionStatus = ref('created');
const messages = ref<TriageMessage[]>([]);
const followUpQuestion = ref('');
const followUpSummary = ref('');
const completedResult = ref<CompletedTriageResponse | null>(null);
const latestResponse = ref<AnalyzeTriageResponse | null>(null);

const submitting = ref(false);
const loadingSession = ref(false);
const errorMessage = ref('');
const sessionError = ref('');

const hasActiveConversation = computed(() => Boolean(activeSessionId.value) && sessionStatus.value !== 'completed');
const currentRiskLevel = computed<RiskLevel | ''>(() => {
  if (!latestResponse.value) {
    return '';
  }
  return latestResponse.value.risk_level;
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

function persistSessionId(sessionId: string | null) {
  if (sessionId) {
    localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
    return;
  }
  localStorage.removeItem(SESSION_STORAGE_KEY);
}

function applySessionState(session: TriageSessionDetailResponse) {
  activeSessionId.value = session.session_id;
  lookupSessionId.value = session.session_id;
  sessionStatus.value = session.status;
  messages.value = session.messages;
  followUpQuestion.value = session.current_question || '';
  latestResponse.value = session.latest_result;
  if (session.latest_result?.status === 'needs_follow_up') {
    followUpSummary.value = session.latest_result.known_facts_summary;
    completedResult.value = null;
  } else {
    followUpSummary.value = '';
    completedResult.value = session.latest_result ?? null;
  }
  persistSessionId(session.session_id);
}

async function syncSession(sessionId: string) {
  const session = await getTriageSession(sessionId);
  applySessionState(session);
}

async function submitInitial() {
  if (!symptomText.value.trim()) {
    errorMessage.value = '请先填写症状描述。';
    return;
  }

  submitting.value = true;
  errorMessage.value = '';

  try {
    const createdSession = await createTriageSession();
    activeSessionId.value = createdSession.session_id;
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
  sessionStatus.value = 'created';
  messages.value = [];
  followUpQuestion.value = '';
  followUpSummary.value = '';
  completedResult.value = null;
  latestResponse.value = null;
  answerText.value = '';
  lookupSessionId.value = '';
  errorMessage.value = '';
  sessionError.value = '';
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
