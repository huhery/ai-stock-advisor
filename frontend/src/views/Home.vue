<template>
  <div>
    <el-row :gutter="20">
      <!-- 今日推荐 -->
      <el-col :span="16">
        <el-card header="今日推荐">
          <el-table :data="recommendations" stripe>
            <el-table-column prop="stock_code" label="代码" width="80" />
            <el-table-column prop="stock_name" label="名称" width="100" />
            <el-table-column prop="sector" label="板块" width="120" />
            <el-table-column prop="total_score" label="评分" width="80" />
            <el-table-column prop="reason" label="筛选理由" />
          </el-table>
          <el-empty v-if="!recommendations.length" description="今日暂无推荐" />
        </el-card>
      </el-col>

      <!-- 最新资讯 -->
      <el-col :span="8">
        <el-card header="最新政策">
          <div v-for="item in news" :key="item.id" class="news-item">
            <el-tag size="small" type="info">{{ item.source }}</el-tag>
            <a :href="item.url" target="_blank" class="news-title">{{ item.title }}</a>
          </div>
          <el-empty v-if="!news.length" description="暂无资讯" />
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getTodayScreening, getLatestNews } from '../api'

const recommendations = ref([])
const news = ref([])

onMounted(async () => {
  try {
    const res1 = await getTodayScreening()
    recommendations.value = res1.data?.data || []
  } catch (e) { console.error(e) }

  try {
    const res2 = await getLatestNews(10)
    news.value = res2.data?.data || []
  } catch (e) { console.error(e) }
})
</script>

<style scoped>
.news-item { margin-bottom: 12px; line-height: 1.6; }
.news-title { margin-left: 8px; color: #333; text-decoration: none; font-size: 14px; }
.news-title:hover { color: #409EFF; }
</style>
