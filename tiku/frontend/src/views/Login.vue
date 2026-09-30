<template>
  <div class="login-overlay">
    <div class="login-box">
      <div class="login-title">題庫</div>
      <div class="login-sub">QUESTION BANK SYSTEM</div>
      <input
        class="login-input"
        placeholder="用户名"
        v-model="username"
        @keyup.enter="handleLogin"
      />
      <input
        class="login-input"
        placeholder="密码"
        type="password"
        v-model="password"
        @keyup.enter="handleLogin"
      />
      <button class="login-btn" @click="handleLogin">进入</button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

const router = useRouter()
const username = ref('')
const password = ref('')

const handleLogin = () => {
  if (username.value === 'admin' && password.value === 'admin') {
    sessionStorage.setItem('isLoggedIn', 'true')
    router.push('/')
  } else {
    ElMessage.error('用户名或密码错误')
  }
}
</script>
