<template>
  <div class="p-card">
    <div class="p-meta">
      <span class="q-id">#{{ question.id }}</span>
      <span class="q-type" :class="'t' + question.type">{{ typeMap[question.type] || '未知' }}</span>
      <span class="p-count">被搜索 {{ question.search_count }} 次</span>
      <span class="p-time">首次: {{ formatTime(question.created_at) }}</span>
      <span class="p-time">最近: {{ formatTime(question.updated_at) }}</span>
    </div>
    <div class="q-text">{{ question.question }}</div>
    <div v-if="question.options && question.options.length" class="q-options">
      <span v-for="(opt, i) in question.options" :key="i" class="q-opt">
        <span class="q-opt-label">{{ String.fromCharCode(65 + i) }}.</span>{{ opt }}
      </span>
    </div>
    <div v-else class="p-empty">暂无选项数据</div>
    <div class="q-actions">
      <button class="q-act" @click="$emit('convert', question)">添加到题库</button>
      <button class="q-act danger" @click="$emit('delete', question.id)">删除</button>
    </div>
  </div>
</template>

<script setup>
defineProps({ question: Object })
defineEmits(['convert', 'delete'])

const typeMap = {
  '0': '单选题', '1': '多选题', '2': '填空题', '3': '判断题',
  '4': '简答题', '5': '名词解释', '6': '论述题', '7': '计算题'
}

const formatTime = (t) => {
  if (!t) return '-'
  const d = new Date(t + (t.includes('Z') || t.includes('+') ? '' : 'Z'))
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}
</script>
