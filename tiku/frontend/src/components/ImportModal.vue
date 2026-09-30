<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    title="导入题库"
    width="500px"
    :close-on-click-modal="false"
  >
    <div class="deco-line"></div>
    <div class="upload-zone" @click="$refs.fileInput.click()" @dragover.prevent @drop.prevent="handleDrop">
      <div style="font-family:var(--brush);font-size:36px;color:var(--text-muted);opacity:0.4;">↑</div>
      <p>点击或拖拽 JSON 文件到这里</p>
      <p style="margin-top:4px;font-size:11px;">最大 10MB</p>
    </div>
    <input ref="fileInput" type="file" accept=".json" style="display:none;" @change="handleSelect" />
    <div v-if="preview" class="import-info">
      <div>文件: {{ preview.name }}</div>
      <div><span class="ok">有效: {{ preview.valid }} 道</span></div>
      <div v-if="preview.invalid > 0"><span class="err">无效: {{ preview.invalid }} 道</span></div>
    </div>
    <template #footer>
      <button class="dlg-btn cancel" @click="$emit('update:visible', false)">取消</button>
      <button class="dlg-btn confirm" :disabled="!preview" @click="doImport">导入</button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { importJson } from '../api'

const props = defineProps({ visible: Boolean })
const emit = defineEmits(['update:visible', 'imported'])

const preview = ref(null)
const file = ref(null)

watch(() => props.visible, (v) => {
  if (v) { preview.value = null; file.value = null }
})

const validate = (f) => {
  if (f.size > 10 * 1024 * 1024) return ElMessage.error('文件过大')
  file.value = f
  const reader = new FileReader()
  reader.onload = (e) => {
    try {
      const d = JSON.parse(e.target.result)
      if (!Array.isArray(d)) return ElMessage.error('JSON 根元素必须是数组')
      let v = 0, inv = 0
      d.forEach(q => { if (q.question && q.type && q.answer) v++; else inv++ })
      preview.value = { name: f.name, valid: v, invalid: inv }
    } catch (err) {
      ElMessage.error('JSON 解析失败')
    }
  }
  reader.readAsText(f)
}

const handleSelect = (e) => { const f = e.target.files[0]; if (f) validate(f) }
const handleDrop = (e) => { const f = e.dataTransfer.files[0]; if (f) validate(f) }

const doImport = async () => {
  if (!file.value) return
  const fd = new FormData()
  fd.append('file', file.value)
  try {
    const res = await importJson(fd)
    if (res.code === 1) {
      ElMessage.success('导入成功，共 ' + res.total + ' 道题目')
      emit('update:visible', false)
      emit('imported')
    } else {
      ElMessage.error(res.detail || '导入失败')
    }
  } catch (e) {
    ElMessage.error('导入请求失败')
  }
}
</script>
