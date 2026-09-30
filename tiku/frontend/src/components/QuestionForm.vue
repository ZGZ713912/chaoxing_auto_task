<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    :title="isEdit ? '编辑题目' : '新增题目'"
    width="600px"
    :close-on-click-modal="false"
  >
    <div class="deco-line"></div>
    <el-form :model="form" label-position="top">
      <el-form-item label="题目类型">
        <el-select v-model="form.type" style="width:100%;">
          <el-option v-for="(label, code) in typeMap" :key="code" :label="label" :value="code" />
        </el-select>
      </el-form-item>
      <el-form-item label="题目内容">
        <el-input v-model="form.question" type="textarea" :rows="3" placeholder="输入题目内容" />
      </el-form-item>
      <el-form-item v-if="form.type === '0' || form.type === '1'" label="选项">
        <div v-for="(opt, i) in form.options" :key="i" class="opt-row">
          <span class="opt-label">{{ String.fromCharCode(65 + i) }}.</span>
          <el-input :model-value="opt" @update:model-value="form.options[i] = $event" />
          <div class="opt-rm" @click="form.options.splice(i, 1)">×</div>
        </div>
        <button class="opt-add" @click="form.options.push('')">+ 添加选项</button>
      </el-form-item>
      <el-form-item label="答案">
        <el-input v-model="form.answer" :placeholder="answerPlaceholder" />
        <div class="answer-hint">{{ answerHint }}</div>
      </el-form-item>
    </el-form>
    <template #footer>
      <button class="dlg-btn cancel" @click="$emit('update:visible', false)">取消</button>
      <button class="dlg-btn confirm" @click="handleSave">保存</button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { createQuestion, updateQuestion, pendingToQuestion } from '../api'

const props = defineProps({ visible: Boolean, question: Object })
const emit = defineEmits(['update:visible', 'saved'])

const typeMap = {
  '0': '单选题', '1': '多选题', '2': '填空题', '3': '判断题',
  '4': '简答题', '5': '名词解释', '6': '论述题', '7': '计算题'
}

const isEdit = computed(() => props.question && props.question.id)

const form = ref({ question: '', type: '0', options: [], answer: '' })

watch(() => props.visible, (v) => {
  if (v && props.question) {
    form.value = {
      question: props.question.question || '',
      type: props.question.type || '0',
      options: [...(props.question.options || [])],
      answer: props.question.answer || '',
      _pendingId: props.question._pendingId
    }
  } else if (v) {
    form.value = { question: '', type: '0', options: [], answer: '' }
  }
})

const answerHint = computed(() => ({
  '0': '单选题答案为单个选项，如: A',
  '1': '多选题答案用 # 分隔，如: A#B#C',
  '2': '填空题多个空用 | 分隔',
  '3': '判断题答案为: 正确 或 错误',
  '4': '简答题直接填写答案内容',
  '5': '名词解释填写解释内容',
  '6': '论述题填写论述内容',
  '7': '计算题填写计算结果'
}[form.value.type] || ''))

const answerPlaceholder = computed(() => ({
  '0': '如: A', '1': '如: A#B#C', '2': '如: 答案1|答案2',
  '3': '正确', '4': '简答内容', '5': '名词解释', '6': '论述内容', '7': '计算结果'
}[form.value.type] || '输入答案'))

const handleSave = async () => {
  if (!form.value.question.trim()) return ElMessage.warning('请输入题目内容')
  if (!form.value.answer.trim()) return ElMessage.warning('请输入答案')

  const body = {
    question: form.value.question.trim(),
    type: form.value.type,
    options: form.value.options.filter(o => o.trim()),
    answer: form.value.answer.trim()
  }

  try {
    let res
    if (form.value._pendingId) {
      res = await pendingToQuestion(form.value._pendingId, body)
    } else if (isEdit.value) {
      res = await updateQuestion(props.question.id, body)
    } else {
      res = await createQuestion(body)
    }

    if (res.code === 1) {
      ElMessage.success(isEdit.value ? '更新成功' : '创建成功')
      emit('update:visible', false)
      emit('saved')
    } else {
      ElMessage.error(res.msg || '操作失败')
    }
  } catch (e) {
    ElMessage.error('请求失败')
  }
}
</script>
