<template>
  <el-card style="height: calc(100vh - 80px); display: flex; flex-direction: column">
    <template #header>智能对话 — 资深A股投资顾问</template>

    <!-- 消息列表 -->
    <div class="messages" ref="messagesRef">
      <div v-for="msg in messages" :key="msg.id" :class="['message', msg.role]">
        <div class="message-bubble">
          <div class="message-role">{{ msg.role === 'user' ? '我' : 'AI 顾问' }}</div>
          <div class="message-content" v-html="renderMarkdown(msg.content)"></div>
        </div>
      </div>
      <div v-if="loading" class="message assistant">
        <div class="message-bubble">
          <div class="message-role">AI 顾问</div>
          <div class="message-content">思考中...</div>
        </div>
      </div>
    </div>

    <!-- 输入框 -->
    <div class="input-area">
      <el-input
        v-model="inputText"
        placeholder="输入你的投资问题..."
        @keyup.enter="send"
        :disabled="loading"
      />
      <el-button type="primary" @click="send" :loading="loading">发送</el-button>
    </div>
  </el-card>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { sendChat, getChatHistory } from '../api'
import { marked } from 'marked'

const messages = ref([])
const inputText = ref('')
const loading = ref(false)
const messagesRef = ref(null)

const renderMarkdown = (text) => {
  try { return marked(text || '') } catch { return text }
}

const scrollToBottom = () => {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

const send = async () => {
  const text = inputText.value.trim()
  if (!text || loading.value) return

  messages.value.push({ id: Date.now(), role: 'user', content: text })
  inputText.value = ''
  loading.value = true
  scrollToBottom()

  try {
    const res = await sendChat(text)
    const reply = res.data?.data || '无法获取回复'
    messages.value.push({ id: Date.now() + 1, role: 'assistant', content: reply })
  } catch (e) {
    messages.value.push({ id: Date.now() + 1, role: 'assistant', content: '请求失败，请重试' })
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

onMounted(async () => {
  try {
    const res = await getChatHistory(30)
    messages.value = (res.data?.data || []).map((m, i) => ({ id: i, ...m }))
    scrollToBottom()
  } catch (e) { console.error(e) }
})
</script>

<style scoped>
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  background: #fafafa;
  border-radius: 8px;
  margin-bottom: 16px;
}
.message { margin-bottom: 16px; display: flex; }
.message.user { justify-content: flex-end; }
.message-bubble {
  max-width: 70%;
  padding: 12px 16px;
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}
.message.user .message-bubble { background: #ecf5ff; }
.message-role { font-size: 12px; color: #999; margin-bottom: 4px; }
.message-content { font-size: 14px; line-height: 1.6; }
.input-area { display: flex; gap: 12px; }
.input-area .el-input { flex: 1; }
</style>
