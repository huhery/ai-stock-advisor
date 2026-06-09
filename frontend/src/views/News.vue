<template>
  <el-card>
    <template #header>
      <div style="display: flex; justify-content: space-between; align-items: center">
        <span>政策资讯中心</span>
        <el-input v-model="keyword" placeholder="搜索资讯..." style="width: 300px"
          @keyup.enter="search" clearable @clear="loadLatest">
          <template #append>
            <el-button @click="search">搜索</el-button>
          </template>
        </el-input>
      </div>
    </template>

    <div v-for="item in newsList" :key="item.id" class="news-item">
      <div class="news-header">
        <el-tag size="small">{{ item.source }}</el-tag>
        <span class="news-time">{{ item.publish_time || item.created_at }}</span>
      </div>
      <a :href="item.url" target="_blank" class="news-title">{{ item.title }}</a>
      <p v-if="item.summary" class="news-summary">{{ item.summary }}</p>
    </div>

    <el-empty v-if="!newsList.length" description="暂无资讯" />
  </el-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getLatestNews, searchNews } from '../api'

const newsList = ref([])
const keyword = ref('')

const loadLatest = async () => {
  try {
    const res = await getLatestNews(50)
    newsList.value = res.data?.data || []
  } catch (e) { console.error(e) }
}

const search = async () => {
  if (!keyword.value.trim()) { loadLatest(); return }
  try {
    const res = await searchNews(keyword.value.trim())
    newsList.value = res.data?.data || []
  } catch (e) { console.error(e) }
}

onMounted(loadLatest)
</script>

<style scoped>
.news-item { padding: 16px 0; border-bottom: 1px solid #f0f0f0; }
.news-header { margin-bottom: 8px; display: flex; align-items: center; gap: 12px; }
.news-time { color: #999; font-size: 12px; }
.news-title { font-size: 15px; color: #333; text-decoration: none; font-weight: 500; }
.news-title:hover { color: #409EFF; }
.news-summary { margin-top: 6px; color: #666; font-size: 13px; line-height: 1.5; }
</style>
