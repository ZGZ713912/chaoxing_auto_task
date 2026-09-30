<template>
  <div>
    <div class="toolbar">
      <input
        class="search-input"
        placeholder="搜索待处理题目..."
        v-model="searchText"
        @input="debounceSearch"
      />
      <div style="display:flex;gap:4px;">
        <button class="tool-btn" :class="{ primary: sortBy === 'count' }" @click="sortBy = 'count'; loadPending()">按搜索次数</button>
        <button class="tool-btn" :class="{ primary: sortBy === 'time' }" @click="sortBy = 'time'; loadPending()">按时间</button>
        <button class="tool-btn" :class="{ primary: sortBy === 'time_asc' }" @click="sortBy = 'time_asc'; loadPending()">按时间正序</button>
      </div>
    </div>

    <div v-if="list.length === 0" class="empty">
      <div class="empty-icon">净</div>
      <div class="empty-text">暂无待处理题目</div>
    </div>

    <div class="card-list">
      <PendingCard
        v-for="p in list"
        :key="p.id"
        :question="p"
        @convert="convertToQuestion"
        @delete="deleteItem"
      />
    </div>

    <QuestionForm
      v-model:visible="formVisible"
      :question="formQuestion"
      @saved="onSaved"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getPending, deletePending } from '../api'
import PendingCard from '../components/PendingCard.vue'
import QuestionForm from '../components/QuestionForm.vue'

const list = ref([])
const searchText = ref('')
const sortBy = ref('count')
const formVisible = ref(false)
const formQuestion = ref(null)

const loadPending = async () => {
  try {
    const params = { limit: 200, sort: sortBy.value }
    if (searchText.value) params.search = searchText.value
    const res = await getPending(params)
    if (res.code === 1) list.value = res.data
  } catch (e) {}
}

let timer = null
const debounceSearch = () => {
  clearTimeout(timer)
  timer = setTimeout(loadPending, 300)
}

const convertToQuestion = (p) => {
  formQuestion.value = {
    question: p.question,
    type: p.type,
    options: [...(p.options || [])],
    answer: '',
    _pendingId: p.id
  }
  formVisible.value = true
}

const deleteItem = async (id) => {
  try {
    await ElMessageBox.confirm('确定删除?', '确认', { type: 'warning' })
    const res = await deletePending(id)
    if (res.code === 1) {
      ElMessage.success('已删除')
      loadPending()
    }
  } catch (e) {}
}

const onSaved = () => { loadPending() }

onMounted(loadPending)
</script>
