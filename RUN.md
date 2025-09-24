# 快速运行指南

## 📋 前置要求

1. **Discord Bot Token**
   - 访问 https://discord.com/developers/applications
   - 创建应用 → Bot → Reset Token → 复制

2. **NovelAI API Key**
   - 登录 https://novelai.net
   - Account Settings → API → 复制密钥

## 🚀 最快启动方法

### 方法1：本地运行（最简单）
```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 创建.env文件
echo "DISCORD_TOKEN=你的token" > .env
echo "NAI_API_KEY=你的api_key" >> .env

# 3. 运行
python start.py
```

### 方法2：Zeabur部署（推荐）
1. Fork这个仓库到你的GitHub
2. 登录 https://zeabur.com
3. 创建项目 → 从GitHub导入
4. 添加环境变量：
   - `DISCORD_TOKEN`
   - `NAI_API_KEY`
5. 部署完成！

### 方法3：Docker运行
```bash
# 创建.env文件后
docker build -t nai-bot .
docker run -d --env-file .env nai-bot
```

## ❓ 常见问题

### 看不到日志？
- Zeabur：查看 "Runtime Logs" 选项卡
- Docker：运行 `docker logs <container-id>`
- 本地：确保使用 `start.py` 而不是 `main.py`

### Bot不上线？
1. 检查Token是否正确（不要包含引号）
2. 确认Bot已邀请到服务器
3. 查看错误日志

### API报错？
- 检查NAI_API_KEY是否有效
- 确认NovelAI账户有足够的Anlas

## 📦 文件说明

| 文件 | 用途 |
|------|------|
| `start.py` | 启动脚本（推荐使用，有详细日志）|
| `main.py` | 主程序 |
| `Procfile` | Zeabur启动配置 |
| `requirements.txt` | Python依赖 |
| `.env.example` | 环境变量示例 |

## 🔧 调试模式

如果遇到问题，使用 `start.py` 启动，它会显示：
- Python版本信息
- 文件列表
- 环境变量状态
- 详细的错误信息

即使启动失败，进程也会保持运行，方便查看日志。