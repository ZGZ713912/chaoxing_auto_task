<template>
  <div class="q-card">
    <div class="q-head">
      <span class="q-id">#{{ question.id }}</span>
      <span class="q-type" :class="'t' + question.type">{{ typeMap[question.type] || '未知' }}</span>
    </div>
    <div class="q-text">{{ question.question }}</div>
    <div v-if="question.options && question.options.length" class="q-options">
      <span v-for="(opt, i) in question.options" :key="i" class="q-opt">
        <span class="q-opt-label">{{ String.fromCharCode(65 + i) }}.</span>{{ opt }}
      </span>
    </div>
    <div class="q-answer">答案: {{ question.answer }}</div>
    <div class="q-actions">
      <button class="q-act" @click="$emit('edit', question)">编辑</button>
      <button class="q-act danger" @click="$emit('delete', question.id)">删除</button>
    </div>
  </div>
</template>

<script setup>
defineProps({ question: Object })
defineEmits(['edit', 'delete'])

const typeMap = {
  '0': '单选题', '1': '多选题', '2': '填空题', '3': '判断题',
  '4': '简答题', '5': '名词解释', '6': '论述题', '7': '计算题'
}
</script>
