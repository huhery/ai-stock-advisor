<template>
  <el-container style="height: 100vh">
    <el-aside width="200px" style="background: #304156">
      <div class="logo">AI 股票助手</div>
      <el-menu
        :default-active="$route.path"
        router
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409EFF"
      >
        <el-menu-item index="/">
          <span>首页</span>
        </el-menu-item>
        <el-menu-item index="/chat">
          <span>智能对话</span>
        </el-menu-item>
        <el-menu-item index="/screening">
          <span>每日选股</span>
        </el-menu-item>
        <el-menu-item index="/dashboard">
          <span>回测看板</span>
        </el-menu-item>
        <el-menu-item index="/backtest">
          <span>策略进化</span>
        </el-menu-item>
        <el-menu-item index="/rules">
          <span>规则管理</span>
        </el-menu-item>
        <el-menu-item index="/news">
          <span>资讯中心</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-main style="padding: 20px; background: #f0f2f5">
      <router-view />
    </el-main>
  </el-container>
</template>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
.logo {
  color: #fff;
  font-size: 18px;
  font-weight: bold;
  text-align: center;
  padding: 20px 0;
  border-bottom: 1px solid #3d4d5f;
}
</style>
