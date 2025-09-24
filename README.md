# Discord NovelAI Bot (Python Version)

一个功能丰富的Discord机器人，用于通过NovelAI API生成图片，支持交互式面板、预设管理和元数据清除功能。

## 🎨 功能特性

### 核心功能
- **图片生成** (`/nai` 命令) - 使用NovelAI API生成高质量图片
- **交互式面板** (`/panel` 命令) - 图形化界面配置生成参数
- **预设管理** (`/preset` 命令) - 保存和管理常用提示词组合
- **元数据清除** - 可选的图片元数据和透明通道移除功能

### 支持的模型
- V4.5 Full/Curated
- V4 Full/Curated/Preview
- V3 Anime/Furry/Inpainting
- V2 Anime
- V1 Anime/Curated/Furry

### 高级特性
- 任务队列系统，防止API请求冲突
- 数据持久化存储
- 自动完成功能
- 多种采样器选择
- 自定义尺寸设置

## 🚀 快速开始

### 环境要求
- Python 3.10+
- Discord Bot Token
- NovelAI API Key

### 本地运行

1. **克隆仓库**
```bash
git clone <repository-url>
cd nai
```

2. **安装依赖**
```bash
pip install -r requirements.txt
```

3. **配置环境变量**
```bash
cp .env.example .env
# 编辑 .env 文件，填入你的配置信息
```

4. **运行机器人**
```bash
python main.py
# 或使用启动脚本（更详细的日志）
python start.py
```

### Docker 部署

```bash
# 配置环境变量
cp .env.example .env
# 编辑 .env 填入配置

# 构建镜像
docker build -t nai-bot .

# 运行容器
docker run -d \
  --name nai-bot \
  --env-file .env \
  --restart unless-stopped \
  nai-bot
```

### Zeabur 部署

1. Fork或上传代码到GitHub
2. 在Zeabur控制台导入项目
3. 配置环境变量：
   - `DISCORD_TOKEN` - Discord机器人令牌
   - `NAI_API_KEY` - NovelAI API密钥
4. 部署

## 📝 命令使用

### /nai - 生成图片
```
/nai prompt:"beautiful anime girl" model:"nai-diffusion-3" size:"portrait_m"
```

可选参数：
- `prompt`: 正向提示词（必需）
- `model`: 选择AI模型
- `negative`: 负向提示词
- `size`: 预设尺寸
- `width/height`: 自定义尺寸
- `steps`: 采样步数 (1-50)
- `cfg`: CFG/Guidance (0-20)
- `sampler`: 采样器类型
- `seed`: 随机种子
- `smea`: 启用SMEA
- `dyn`: 启用SMEA DYN
- `remove_metadata`: 清除元数据

### /panel - 交互式面板
打开一个图形化界面，通过下拉菜单和按钮配置参数：
- 选择模型、尺寸、采样器
- 选择预设提示词
- 切换元数据清除选项
- 保存个人设置

### /preset - 预设管理
```
/preset save name:"my_style" prompt:"masterpiece, best quality" negative:"lowres"
/preset list
/preset delete name:"my_style"
```

## 🔧 元数据清除功能

新增的元数据清除功能可以：
- 移除图片的EXIF和其他元数据
- 移除透明通道（Alpha channel）
- 保持高质量的图片输出

在生成图片时勾选"清除元数据"选项或在面板中切换此功能。

## 📂 项目结构

```
nai/
├── main.py              # 主程序文件
├── utils.py             # 工具函数（数据持久化）
├── image_processor.py   # 图片处理模块（元数据清除）
├── requirements.txt     # Python依赖
├── Dockerfile          # Docker配置
├── .env.example        # 环境变量示例
└── data/               # 数据存储目录
    ├── user_presets.json    # 用户预设
    └── user_settings.json   # 用户设置
```

## 🛠️ 配置说明

### 环境变量
- `DISCORD_TOKEN`: Discord机器人令牌
- `NAI_API_KEY`: NovelAI API密钥
- `DATA_DIR`: 数据存储路径（可选，默认为当前目录）
- `ZEABUR`: 设置为true时使用Zeabur部署模式

### 数据持久化
- 用户预设和设置保存在JSON文件中
- Docker部署时使用挂载卷保持数据持久化
- Zeabur部署时自动使用`/data`目录

## 📊 性能优化

- 使用异步编程提高响应速度
- 任务队列系统防止并发冲突
- PIL库优化图片处理性能
- 智能缓存减少重复API调用

## 🔍 故障排查

### 常见问题

1. **命令不显示**
   - 确保Bot有正确的权限
   - 尝试重新邀请Bot到服务器

2. **生成失败**
   - 检查API Key是否有效
   - 确认网络连接正常
   - 查看控制台错误信息

3. **元数据清除不工作**
   - 确保安装了Pillow库
   - 检查图片格式是否支持

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 🙏 致谢

- [cetaceang](https://github.com/cetaceang) - 根据[原始项目](https://github.com/skaria1267/discord-nai-bot)编写的最初的增强版bot
- NovelAI 提供的优秀图像生成API
- Discord.py 社区
- 所有贡献者和用户
