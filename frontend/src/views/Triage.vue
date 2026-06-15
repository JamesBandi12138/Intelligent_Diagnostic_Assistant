<template>
  <main class="layout">
    <section class="workspace">
      <header class="topbar">
        <div>
          <p class="eyebrow">Pre-Consultation Triage</p>
          <h1>智能导诊与就医助手</h1>
        </div>
        <span class="badge">非诊断 · 仅导诊参考</span>
      </header>

      <section class="panel input-panel">
        <label for="symptom">症状描述</label>
        <textarea
          id="symptom"
          v-model="symptomText"
          rows="7"
          placeholder="例如：喉咙痛三天，有点发热，吞咽疼，不知道挂什么科"
        />
        <div class="form-grid">
          <label>
            年龄
            <input v-model.number="age" type="number" min="0" max="130" />
          </label>
          <label>
            性别
            <select v-model="sex">
              <option value="unknown">未说明</option>
              <option value="female">女</option>
              <option value="male">男</option>
            </select>
          </label>
          <label>
            城市
            <input v-model="city" placeholder="北京" />
          </label>
        </div>
        <button type="button" @click="submit">生成导诊建议</button>
      </section>

      <section v-if="result" class="panel result-panel">
        <div class="result-header">
          <h2>导诊建议</h2>
          <span :class="['risk', result.risk_level]">{{ result.risk_level }}</span>
        </div>
        <p v-if="result.emergency_advice" class="emergency">{{ result.emergency_advice }}</p>
        <h3>推荐科室</h3>
        <ul>
          <li v-for="department in result.recommended_departments" :key="department.name">
            <strong>{{ department.name }}</strong>：{{ department.reason }}
          </li>
        </ul>
        <h3>就医路径</h3>
        <p>{{ result.care_path }}</p>
        <h3>准备清单</h3>
        <ul>
          <li v-for="item in result.preparation_checklist" :key="item">{{ item }}</li>
        </ul>
        <p class="disclaimer">{{ result.disclaimer }}</p>
      </section>
    </section>
  </main>
</template>

<script setup lang="ts">
import { ref } from 'vue';

import { analyzeTriage } from '../api';

const symptomText = ref('喉咙痛三天，有点发热，吞咽疼，不知道挂什么科');
const age = ref(32);
const sex = ref<'male' | 'female' | 'unknown'>('female');
const city = ref('北京');
const result = ref<any>(null);

async function submit() {
  result.value = await analyzeTriage({
    patient: {
      age: age.value,
      sex: sex.value,
      medical_history: [],
      allergies: [],
      medications: [],
    },
    symptom_text: symptomText.value,
    city: city.value,
  });
}
</script>

