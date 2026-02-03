# Anki 自动制卡工具

这是一个自动化的 Anki 卡片生成工具，可以批量将单词/词组转换为精美的 Anki 卡片，包含音标、释义、例句和语音。

## 功能特性

- 🤖 **AI 驱动**：使用大语言模型自动生成音标、释义和例句
- 🔊 **语音合成**：使用 Azure TTS 生成高质量英式发音（慢速+快速）
- 📝 **批量处理**：从 txt 文件读取单词列表，一键生成卡组
- ⚙️ **灵活配置**：通过 YAML 配置文件自定义所有参数
- 🎨 **精美模板**：现代化的卡片设计，支持夜间模式
- 🧹 **自动清理**：生成完成后自动删除临时音频文件

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置参数

编辑 `config.yaml` 文件，填入你的 API 密钥和偏好设置：

```yaml
api_keys:
  openai_api_key: "你的密钥"
  azure_speech_key: "你的密钥"

speed_config:
  word_slow: "-30%"      # 单词慢读
  word_fast: "0%"        # 单词快读
  definitions: "0%"      # 释义语速
  examples: "-10%"       # 例句语速

paths:
  input_txt: "words.txt"           # 输入的单词列表
  output_package: "My_English_List.apkg"  # 输出的 Anki 包
```

### 3. 准备单词列表

在 `words.txt` 文件中添加你要学习的单词，每行一个：

```
tear (crying)
hold on
content (happy)
serendipity
a piece of cake
```

### 4. 运行程序

```bash
python main.py
```

程序将自动：
1. 读取配置文件
2. 加载单词列表
3. 为每个单词生成内容和语音
4. 打包成 Anki 卡组
5. 清理临时文件

### 5. 导入 Anki

双击生成的 `.apkg` 文件，即可导入到 Anki！

## 配置说明

### API 配置

- **openai_api_key**: DeepSeek/OpenAI API 密钥（用于生成释义和例句）
- **azure_speech_key**: Azure 语音服务密钥（用于 TTS 语音合成）

### 语速配置

语速采用百分比格式：
- `-30%`: 减慢 30%
- `0%`: 原速
- `+20%`: 加快 20%

### 单词格式说明

支持以下格式：
- **普通单词**: `apple`
- **词组**: `look forward to`
- **多义词（指定语境）**: `tear (crying)` - 括号内容用于确定发音和优先释义

## 文件说明

- `main.py`: 主程序入口
- `generate.py`: 核心生成逻辑（LLM + TTS + Anki）
- `config.yaml`: 配置文件
- `words.txt`: 单词列表（示例）
- `requirements.txt`: Python 依赖包

## 常见问题

### Q: 如何修改语音性别或口音？

编辑 `config.yaml` 中的 `azure_voice_name`，可选值：
- `en-GB-SoniaNeural` (英式女声)
- `en-GB-RyanNeural` (英式男声)
- `en-US-JennyNeural` (美式女声)
- 更多选项参考 [Azure 文档](https://learn.microsoft.com/zh-cn/azure/ai-services/speech-service/language-support?tabs=tts)

### Q: 临时音频文件会占用空间吗？

不会，程序执行完毕后会自动删除 `media_temp` 目录。

### Q: 可以自定义卡片样式吗？

可以，编辑 `generate.py` 中的 CSS 和 HTML 模板部分。

## 许可证

MIT License
