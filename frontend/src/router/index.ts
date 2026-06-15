import { createRouter, createWebHistory } from 'vue-router';

import Triage from '../views/Triage.vue';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'triage',
      component: Triage,
    },
  ],
});

export default router;

