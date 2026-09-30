<template>
  <div>
    <div class="toolbar">
      <input
        class="search-input"
        placeholder="搜索题目..."
        v-model="searchText"
        @input="debounceSearch"
      />
      <button class="tool-btn primary" @click="openCreateModal">新增</button>
      <button class="tool-btn" @click="showImportModal">导入</button>
      <button class="tool-btn" @click="handleExport">导出</button>
    </div>

    <div class="card-list">
      <div v-if="questions.length === 0" class="empty">
        <div class="empty-icon">空</div>
        <div class="empty-text">暂无题目数据</div>
      </div>
      <QuestionCard
        v-for="q in questions"
        :key="q.id"
        :question="q"
        @edit="editQuestion"
        @delete="deleteQuestion"
      />
    </div>

    <div v-if="total > 20" class="pager">
      <button class="pg-btn" :disabled="page <= 1" @click="page--; loadQuestions()">上一页</button>
      <span class="pg-info">{{ page }} / {{ Math.ceil(total / 20) }}</span>
      <button class="pg-btn" :disabled="page >= Math.ceil(total / 20)" @click="page++; loadQuestions()">下一页</button>
    </div>

    <QuestionForm
      v-model:visible="formVisible"
      :question="editingQuestion"
      @saved="onSaved"
    />

    <ImportModal
      v-model:visible="importVisible"
      @imported="onImported"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getQuestions, deleteQuestion as apiDelete, exportJson } from '../api'
import QuestionCard from '../components/QuestionCard.vue'
import QuestionForm from '../components/QuestionForm.vue'
import ImportModal from '../components/ImportModal.vue'

const questions = ref([])
const total = ref(0)
const page = ref(1)
const searchText = ref('')
const formVisible = ref(false)
const editingQuestion = ref(null)
const importVisible = ref(false)

const loadQuestions = async () => {
  try {
    const off = (page.value - 1) * 20
    const params = { limit: 20, offset: off }
    if (searchText.value) params.search = searchText.value
    const res = await getQuestions(params)
    if (res.code === 1) {
      questions.value = res.data
      total.value = res.total
    }
  } catch (e) {}
}

let timer = null
const debounceSearch = () => {
  clearTimeout(timer)
  timer = setTimeout(() => { page.value = 1; loadQuestions() }, 300)
}

const openCreateModal = () => {
  editingQuestion.value = null
  formVisible.value = true
}

const editQuestion = (q) => {
  editingQuestion.value = { ...q }
  formVisible.value = true
}

const deleteQuestion = async (id) => {
  try {
    await ElMessageBox.confirm('确定删除该题目?', '确认', { type: 'warning' })
    const res = await apiDelete(id)
    if (res.code === 1) {
      ElMessage.success('已删除')
      loadQuestions()
    }
  } catch (e) {}
}

const onSaved = () => { loadQuestions() }

const showImportModal = () => { importVisible.value = true }
const onImported = () => { loadQuestions() }

const handleExport = () => { window.location.href = exportJson() }

onMounted(loadQuestions)
</script>
