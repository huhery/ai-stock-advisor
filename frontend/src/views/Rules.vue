<template>
  <div>
    <!-- 活跃规则 -->
    <el-card header="筛选规则" style="margin-bottom: 20px">
      <el-table :data="rules" stripe>
        <el-table-column prop="name" label="规则名称" width="150" />
        <el-table-column prop="category" label="分类" width="80">
          <template #default="{ row }">
            <el-tag size="small">{{ row.category }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="200" />
        <el-table-column prop="weight" label="权重" width="80" />
        <el-table-column prop="win_rate" label="胜率" width="80">
          <template #default="{ row }">{{ row.win_rate }}%</template>
        </el-table-column>
        <el-table-column prop="total_used" label="使用次数" width="90" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'warning'" size="small">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- AI 建议的规则 -->
    <el-card header="AI 建议的新规则（待审批）">
      <div v-for="item in suggestions" :key="item.id" class="suggestion-card">
        <div class="suggestion-info">
          <strong>{{ item.name }}</strong>
          <el-tag size="small" style="margin-left: 8px">{{ item.category }}</el-tag>
          <p>{{ item.description }}</p>
        </div>
        <div class="suggestion-actions">
          <el-button type="primary" size="small" @click="handleApprove(item.id)">采纳</el-button>
          <el-button size="small" @click="handleReject(item.id)">忽略</el-button>
        </div>
      </div>
      <el-empty v-if="!suggestions.length" description="暂无待审批规则" />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getScreeningRules, getSuggestions, approveRule, rejectRule } from '../api'
import { ElMessage } from 'element-plus'

const rules = ref([])
const suggestions = ref([])

const loadData = async () => {
  try {
    const res1 = await getScreeningRules()
    rules.value = res1.data?.data || []
    const res2 = await getSuggestions()
    suggestions.value = res2.data?.data || []
  } catch (e) { console.error(e) }
}

const handleApprove = async (id) => {
  await approveRule(id)
  ElMessage.success('规则已激活')
  loadData()
}

const handleReject = async (id) => {
  await rejectRule(id)
  ElMessage.info('规则已忽略')
  loadData()
}

onMounted(loadData)
</script>

<style scoped>
.suggestion-card {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px; border-bottom: 1px solid #eee;
}
.suggestion-info p { margin-top: 4px; color: #666; font-size: 13px; }
</style>
