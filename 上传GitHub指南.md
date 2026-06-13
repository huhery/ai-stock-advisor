# 上传项目到GitHub指南

## 当前状态
- 本地已有Git仓库（master分支）
- 已创建GitHub仓库：`huhery/ai-stock-advisor`
- 遇到代理连接问题

## 解决方案

### 方案1: 配置代理（推荐）
如果你使用代理工具（如Clash、v2rayN等）：

1. **找到代理端口**：
   - 打开代理工具设置
   - 查看HTTP代理端口（通常是7890或10809）

2. **配置Git代理**：
```bash
# 配置HTTP代理（如果代理端口是7890）
git config --global http.proxy http://127.0.0.1:7890
git config --global https.proxy http://127.0.0.1:7890

# 测试连接
git config --global --get http.proxy
```

3. **推送代码**：
```bash
# 添加远程仓库
git remote add origin https://github.com/huhery/ai-stock-advisor.git

# 推送代码
git push -u origin master
```

### 方案2: 使用SSH方式
如果代理配置仍不成功，改用SSH：

1. **生成SSH密钥**（如果还没有）：
```bash
ssh-keygen -t rsa -b 4096 -C "your-email@example.com"
```

2. **添加SSH公钥到GitHub**：
   - 查看公钥：`cat ~/.ssh/id_rsa.pub`
   - 登录GitHub → Settings → SSH and GPG keys → New SSH key
   - 粘贴公钥内容

3. **测试SSH连接**：
```bash
ssh -T git@github.com
# 应该看到：Hi huhery! You've successfully authenticated...
```

4. **使用SSH地址**：
```bash
# 设置SSH远程地址
git remote set-url origin git@github.com:huhery/ai-stock-advisor.git

# 或删除后重新添加
git remote remove origin
git remote add origin git@github.com:huhery/ai-stock-advisor.git

# 推送代码
git push -u origin master
```

### 方案3: 使用GitHub CLI工具
```bash
# 安装GitHub CLI
# Windows: winget install --id GitHub.cli

# 登录GitHub
gh auth login

# 推送代码
git push -u origin master
```

### 方案4: 临时禁用代理
如果代理导致问题：
```bash
# 取消代理设置
git config --global --unset http.proxy
git config --global --unset https.proxy

# 直接推送（可能会慢，但能成功）
git push -u origin master
```

## 验证步骤

1. **检查远程仓库**：
```bash
git remote -v
# 应该显示：
# origin  https://github.com/huhery/ai-stock-advisor.git (fetch)
# origin  https://github.com/huhery/ai-stock-advisor.git (push)
```

2. **拉取测试**：
```bash
git pull origin master
```

3. **推送测试**：
```bash
# 添加测试文件
echo "# AI Stock Advisor" > README.md
git add README.md
git commit -m "test: add README"
git push origin master
```

## 常见错误解决

### 错误1: Connection refused
```
fatal: unable to access 'https://github.com/huhery/ai-stock-advisor.git/': 
Failed to connect to 127.0.0.1 port 7890 after 2055 ms: Connection refused
```
**解决**: 代理端口错误或代理服务未启动。检查代理设置或改用SSH。

### 错误2: Timed out
```
unable to access 'https://github.com/huhery/ai-stock-advisor.git/': 
Failed to connect to github.com port 443 after 22164 ms: Timed out
```
**解决**: 网络问题。尝试：
- 配置正确代理
- 使用SSH方式
- 切换网络环境

### 错误3: Permission denied
```
remote: Permission to huhery/ai-stock-advisor.git denied to <username>.
fatal: unable to access 'https://github.com/huhery/ai-stock-advisor.git/': 
The requested URL returned error: 403
```
**解决**: SSH密钥权限问题。检查：
- SSH密钥是否正确添加到GitHub
- SSH密钥文件权限：`chmod 600 ~/.ssh/id_rsa`

## 完整推送命令（推荐使用SSH）
```bash
# 如果已配置代理，先取消
git config --global --unset http.proxy
git config --global --unset https.proxy

# 使用SSH地址
git remote remove origin
git remote add origin git@github.com:huhery/ai-stock-advisor.git

# 验证SSH连接
ssh -T git@github.com

# 添加所有文件
git add .

# 提交代码（使用中文commit信息）
git commit -m "feat: 完成全A股选股、国际新闻分析、Kronos预测集成"

# 推送到GitHub
git push -u origin master
```

## 扩展功能已全部完成
你的项目现在已经具备：
1. ✅ 全A股选股范围（从105只扩展到全A股）
2. ✅ 国际新闻分析集成（8个数据源）
3. ✅ Kronos AI价格预测模型集成

所有代码已修改完成，测试通过，随时可以部署使用！