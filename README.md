
# Anki 自动制卡工具 (Anki Auto Card Generator)

这是一个自动化的 Anki 卡片生成工具，可以批量将单词/词组转换为精美的 Anki 卡片。它结合了大语言模型（LLM）的智能理解和 Azure TTS 的高质量语音合成，特别针对英语学习中的“多音多义词”做了深度优化。

## ✨ 功能特性

- 🤖 **AI 驱动**：使用 DeepSeek/OpenAI 自动生成精准的音标、释义和地道的例句。
- 🔊 **语音合成**：集成 Azure TTS，生成媲美真人的英式/美式发音（包含慢速+快速两种版本）。
- 🎯 **语境感知**：**独家功能！** 支持通过括号指定单词语境（如 `tear (crying)` vs `tear (rip)`），自动匹配正确的发音和释义。
- 📝 **批量处理**：支持从 TXT 文件读取列表，一键生成 `.apkg` 卡组包。
- ⚙️ **灵活配置**：所有参数（API Key、语速、口音、路径）均可通过 YAML 文件配置。
- 🎨 **精美模板**：内置“现代排版”风格模板，支持夜间模式，视觉体验极佳。
- 🧹 **自动清理**：制卡完成后自动清理临时音频文件，保持目录整洁。

---

## 🚀 快速开始

### 1. 安装依赖

确保你已经安装了 Python 3.8+，然后运行：

```bash
pip install -r requirements.txt

```

### 2. 配置参数

在项目根目录下创建一个 `config.yaml` 文件，填入你的 API 密钥和偏好设置：

```yaml
api_keys:
  openai_api_key: "sk-xxxxxx"       # 你的 DeepSeek 或 OpenAI Key
  azure_speech_key: "xxxxxx"        # 你的 Azure Speech Key (申请教程见下文)
  azure_region: "eastus"            # Azure 服务区域 (如 eastus, japaneast)

speed_config:
  word_slow: "-30%"      # 单词慢读 (减慢30%，适合听音辨位)
  word_fast: "0%"        # 单词快读 (正常语速)
  definitions: "0%"      # 释义语速
  examples: "-10%"       # 例句语速 (稍慢，方便模仿)

paths:
  input_txt: "words.txt"            # 输入的单词列表文件
  output_package: "My_English_List.apkg"  # 输出的 Anki 包文件名

```

### 3. 准备单词列表

创建 `words.txt` 文件，每行输入一个单词或词组。

**🔥 高级用法：括号语境指定**
本工具支持处理多音多义词。你可以在括号内指定语境，AI 会自动调整发音和释义优先级。

```text
# --- 普通单词 ---
serendipity

# --- 词组/习语 ---
a piece of cake
look forward to

# --- 多音多义词 (Heteronyms) ---
# 指定为“眼泪”：发音 /tɪə/，释义优先展示“泪水”
tear (crying)

# 指定为“撕碎”：发音 /teə/，释义优先展示“撕开”
tear (rip)

# --- 多义词 (Polysemes) ---
# 指定为“满意的”：重音在后 /kənˈtent/
content (happy)

# 指定为“内容”：重音在前 /ˈkɒntent/
content (list)

```

### 4. 运行程序

```bash
python main.py

```

程序将自动执行以下流程：

1. 读取 `words.txt`。
2. 调用 LLM 生成文本内容。
3. 调用 Azure 生成慢速/快速音频。
4. 打包生成 `My_English_List.apkg`。

### 5. 导入 Anki

双击生成的 `.apkg` 文件，即可直接导入到 Anki 桌面版或手机版中开始学习！

---

## 🛠️ 常见问题 (FAQ)

### Q: 如何修改语音的性别或口音？

您可以修改代码中的 `voice_name` 变量（未来版本将支持在 yaml 中配置）。常用的 Azure 声音代码：

* `en-GB-SoniaNeural` (英式女声 - 推荐)
* `en-GB-RyanNeural` (英式男声)
* `en-US-JennyNeural` (美式女声)
* `en-US-GuyNeural` (美式男声)

### Q: 临时音频文件占用空间吗？

不会。程序运行结束后，会自动删除 `media_temp` 文件夹，只保留打包好的 `.apkg` 文件。

### Q: 如果单词拼写错误会怎样？

AI 通常会自动纠正或报错。建议在 `words.txt` 中仔细检查拼写。

---

## 📚 附录：如何申请 Azure Speech 服务 (免费)

Azure 提供每月 **50万字符的免费额度 (Free Tier)**，对于个人制作单词卡片完全够用（大约可以制作 2000-5000 张卡片/月）。

### 第一步：注册/登录 Azure

1. 访问 [Azure 门户 (portal.azure.com)](https://www.google.com/search?q=https://portal.azure.com/)。
2. 登录你的 Microsoft 账户。

### 第二步：创建语音资源

1. 在顶部搜索栏输入 **"Speech services"** (或“语音服务”) 并进入。
2. 点击左上角的 **"Create"** (创建)。
3. 填写表单：
* **Resource Group**: 点击 "Create new"，随便起名（如 `anki-group`）。
* **Region**: 推荐选 **`East US`** (美国东部) 或 **`Japan East`** (日本东部)。**请记住这个选择，需填入 config.yaml。**
* **Name**: 随便起名（如 `my-anki-tts`）。
* **Pricing tier (关键)**: **请务必选择 `Free F0**`。
* *注意：如果你看不到 F0 选项，说明该订阅下已经有一个免费资源了，只能选 Standard S0（需付费）。*





### 第三步：获取 Key

1. 资源部署完成后，点击 **"Go to resource"**。
2. 在左侧菜单点击 **"Keys and Endpoint"**。
3. 复制 **KEY 1**，填入 `config.yaml` 的 `azure_speech_key`。
4. 确认 **Location/Region** (如 `eastus`)，填入 `config.yaml` 的 `azure_region`。

---

## 📄 许可证

MIT License

