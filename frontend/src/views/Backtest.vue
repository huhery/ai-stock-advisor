<template>
  <div>
    <!-- 启动回测 -->
    <el-card header="策略进化优化" style="margin-bottom: 20px">
      <el-form :inline="true">
        <el-form-item label="迭代代数">
          <el-input-number v-model="config.generations" :min="5" :max="100" :step="5" />
        </el-form-item>
        <el-form-item label="目标胜率(%)">
          <el-input-number v-model="config.targetWinRate" :min="50" :max="90" :step="5" />
        </el-form-item>
        <el-form-item label="目标收益(%)">
          <el-input-number v-model="config.targetAvgReturn" :min="2" :max="20" :step="1" />
        </el-form-item>
      </el-form>

      <div style="margin: 16px 0">
        <span style="margin-right: 12px; font-weight: bold">选择回测时期：</span>
        <el-checkbox-group v-model="selectedPeriods">
          <el-checkbox v-for="(info, name) in periods" :key="name" :label="name">
            {{ name }}
            <el-tag :type="info.type === 'bull' ? 'danger' : info.type === 'bear' ? 'success' : 'warning'"
                    size="small" style="margin-left:4px">
              {{ info.type === 'bull' ? '牛市' : info.type === 'bear' ? '熊市' : '震荡' }}
            </el-tag>
          </el-checkbox>
        </el-checkbox-group>
      </div>

      <el-button type="primary" @click="startBacktest" :loading="running" size="large">
        {{ running ? '进化中...' : '开始进化优化' }}
      </el-button>
      <el-text type="info" style="margin-left: 16px">
        提示：进化优化需要较长时间（10-30分钟），请耐心等待
      </el-text>
    </el-card>

    <!-- 最新结果 -->
    <el-card v-if="latestResult" header="最新进化结果" style="margin-bottom: 20px">
      <el-row :gutter="20">
        <el-col :span="6">
          <el-statistic title="最优胜率" :value="latestResult.win_rate" suffix="%" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="平均收益" :value="latestResult.avg_return" suffix="%" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="模拟交易数" :value="latestResult.total_trades" />
        </el-col>
        <el-col :span="6">
          <el-button type="success" @click="applyResult" :disabled="latestApplied">
            {{ latestApplied ? '已应用' : '应用到当前策略' }}
          </el-button>
        </el-col>
      </el-row>

      <el-divider>最优权重</el-divider>
      <el-table :data="weightsTable" stripe size="small">
        <el-table-column prop="name" label="规则" />
        <el-table-column prop="weight" label="优化后权重" width="120" />
      </el-table>

      <el-divider>最优参数</el-divider>
      <el-descriptions :column="4" border>
        <el-descriptions-item label="止盈">{{ latestResult.params?.take_profit_pct }}%</el-descriptions-item>
        <el-descriptions-item label="止损">{{ latestResult.params?.stop_loss_pct }}%</el-descriptions-item>
        <el-descriptions-item label="最大持有天数">{{ latestResult.params?.max_hold_days }}</el-descriptions-item>
        <el-descriptions-item label="最低评分">{{ latestResult.params?.min_score_threshold }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- 历史记录 -->
    <el-card header="回测历史">
      <el-table :data="history" stripe>
        <el-table-column prop="created_at" label="时间" width="170" />
        <el-table-column prop="win_rate" label="胜率" width="80">
          <template #default="{ row }">{{ row.win_rate }}%</template>
        </el-table-column>
        <el-table-column prop="avg_return" label="平均收益" width="90">
          <template #default="{ row }">
            <span :style="{ color: row.avg_return > 0 ? 'red' : 'green' }">
              {{ row.avg_return }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="total_trades" label="交易数" width="80" />
        <el-table-column prop="applied" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.applied ? 'success' : 'info'" size="small">
              {{ row.applied ? '已应用' : '未应用' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const config = ref({
  generations: 20,
  targetWinRate: 65,
  targetAvgReturn: 5,
})
const selectedPeriods = ref([])
const periods = ref({})
const running = ref(false)
const latestResult = ref(null)
const latestApplied = ref(false)
const history = ref([])

const weightsTable = computed(() => {
  if (!latestResult.value?.weights) return []
  return Object.entries(latestResult.value.weights).map(([name, weight]) => ({
    name, weight: weight.toFixed(2)
  }))
})

const loadPeriods = async () => {
  try {
    const res = await axios.get('/api/backtest/periods')
    const raw = res.data
    // Python 直接返回 {code: 0, data: {...}}
    periods.value = raw?.data || {}
    selectedPeriods.value = Object.keys(periods.value)
  } catch (e) { console.error('loadPeriods error:', e) }
}

const loadHistory = async () => {
  try {
    const res = await axios.get('/api/backtest/history')
    let raw = res.data?.data
    if (raw && raw.code !== undefined && raw.data !== undefined) {
      raw = raw.data
    }
    history.value = Array.isArray(raw) ? raw : []
    if (history.value.length > 0) {
      const latest = history.value[0]
      latestResult.value = {
        win_rate: latest.win_rate,
        avg_return: latest.avg_return,
        total_trades: latest.total_trades,
        weights: typeof latest.best_weights === 'string'
          ? JSON.parse(latest.best_weights) : latest.best_weights,
        params: typeof latest.best_params === 'string'
          ? JSON.parse(latest.best_params) : latest.best_params,
      }
      latestApplied.value = !!latest.applied
    }
  } catch (e) { console.error(e) }
}

const startBacktest = async () => {
  if (selectedPeriods.value.length === 0) {
    ElMessage.warning('请至少选择一个回测时期')
    return
  }
  running.value = true
  try {
    const res = await axios.post('/api/backtest/run', null, {
      params: {
        generations: config.value.generations,
        target_win_rate: config.value.targetWinRate,
        target_avg_return: config.value.targetAvgReturn,
        periods: selectedPeriods.value.join(','),
      },
      timeout: 30000
    })
    if (res.data?.code === 0) {
      ElMessage.success('回测任务已启动，正在后台运行...')
      pollProgress()
    } else {
      ElMessage.error(res.data?.message || '启动失败')
      running.value = false
    }
  } catch (e) {
    ElMessage.error('启动请求失败')
    running.value = false
  }
}

const pollProgress = () => {
  const timer = setInterval(async () => {
    try {
      const res = await axios.get('/api/backtest/status')
      let progress = res.data?.data
      if (progress && progress.code !== undefined && progress.data !== undefined) {
        progress = progress.data
      }

      if (progress?.status === 'completed') {
        clearInterval(timer)
        running.value = false
        latestResult.value = progress.result
        latestApplied.value = false
        ElMessage.success('进化优化完成！')
        loadHistory()
      } else if (progress?.status === 'failed') {
        clearInterval(timer)
        running.value = false
        ElMessage.error('回测失败: ' + (progress.error || '未知错误'))
      } else if (progress?.status === 'running') {
        // 更新进度显示
        const gen = progress.generation || 0
        const total = progress.total || config.value.generations
        ElMessage.info({ message: `进化中... 第 ${gen}/${total} 代`, duration: 3000, showClose: false })
      }
    } catch (e) {
      // 网络错误不停止轮询
    }
  }, 5000)  // 每 5 秒轮询一次
}

const applyResult = async () => {
  try {
    await axios.post('/api/backtest/apply')
    latestApplied.value = true
    ElMessage.success('已应用最优策略到当前规则')
    loadHistory()
  } catch (e) {
    ElMessage.error('应用失败')
  }
}

onMounted(() => {
  loadPeriods()
  loadHistory()
})
</script>
