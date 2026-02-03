import os
import re
import json
import hashlib
from openai import OpenAI
import azure.cognitiveservices.speech as speechsdk
import genanki


# ==========================================
# 自定义稳定 GUID Note 类
# ==========================================
class StableGUIDNote(genanki.Note):
    """
    自定义 Note 类，使用单词的哈希值作为 GUID
    这样相同单词的卡片在重新导入时会被识别为更新，而不是创建副本
    复习进度会被保留
    """
    def __init__(self, model, fields, guid_field_index=0, **kwargs):
        super().__init__(model=model, fields=fields, **kwargs)
        self._guid_field_index = guid_field_index
    
    @property
    def guid(self):
        # 使用指定字段的哈希值作为 GUID
        # 这确保只要该字段不变，GUID 就永远不变
        return genanki.guid_for(self.fields[self._guid_field_index])

def generate_word_card(input_text: str, api_config: dict = None) -> dict:
    """
    输入一个单词或词组（可能包含上下文括号），通过 API 一次性生成音标、释义和例句（JSON模式）
    
    Args:
        input_text (str): 用户输入的单词，例如 "tear (crying)" 或 "bank"
        api_config (dict, optional): API 配置字典，包含 base_url, api_key, model_name
        
    Returns:
        dict: 包含 word, ipa, definitions, examples
    """
    
    # 1. 初始化客户端
    if api_config is None:
        api_config = {
            "base_url": "https://ark.cn-beijing.volces.com/api/v3",
            "api_key": "请在 config.yaml 中配置你的 API Key",
            "model_name": "deepseek-v3-2-251201"
        }
    
    client = OpenAI(
        base_url=api_config.get("base_url", "https://ark.cn-beijing.volces.com/api/v3"),
        api_key=api_config.get("api_key", ""),
    )
    
    MODEL_NAME = api_config.get("model_name", "deepseek-v3-2-251201")

    # 2. 清洗输入文本
    import json
    cleaned_word = re.sub(r'[\(\uff08].*?[\)\uff09]', '', input_text).strip()

    # 3. 定义统一的 Prompt（JSON 返回模式）
    vocab_prompt = """
You are an expert English teacher and IELTS preparation assistant.
Task: Generate complete vocabulary card data for the input word/phrase.

**Rules:**
1. **Input format:** May be a single word, phrase/idiom, or word/phrase with context in parentheses (e.g., "tear (crying)").
2. **Output:** JSON object ONLY.

3. **Field Requirements:**
   - **word**: Clean word/phrase (remove parentheses content).
   - **ipa**: British English IPA transcription (e.g., /ˈæpl/ or /lʊk ˈfɔːwəd tu/).
   - **definitions**: Numbered list of definitions (newline separated).
     * **Language Level:** Use clear, intermediate vocabulary (IELTS 5.5-6.5 level/CEFR B2).
     * **Structure Hints (Part of Speech):** Start the definition with a specific phrase to indicate the part of speech and countability:
       - **Noun (Countable):** Start with "A/An [word] is..." (e.g., "A wave is...").
       - **Noun (Uncountable):** Start with "[Word] is..." (NO "A/An") (e.g., "Pollution is...").
       - **Verb:** Start with "To [word] is to..." (e.g., "To behave is to...").
       - **Adjective (Person):** Start with "If you are [word]..." or "When a person is [word]...".
       - **Adjective (Thing/General):** Start with "If something is [word]..." or "It is [word] to...".
     * **Phrase/Idiom:** Define the WHOLE phrase.
     * **Context:** Definition 1 MUST match the context in parentheses (if provided).
   - **examples**: Numbered list of example sentences (newline separated).
     * One sentence per definition.
     * **Style:** Mimic formal IELTS Reading sentence structures (academic tone, passive voice).
     * **Length:** STRICTLY under 12 words per sentence (short and pithy).
     * **Vocabulary:** Keep context words simple so the target word stands out.
   - **word_cn**: Chinese translation of the word/phrase (简体中文).
   - **definitions_cn**: Chinese translation of the definitions.
   - **examples_cn**: Chinese translation of the examples.

**Output JSON:**
{
  "word": "...",
  "ipa": "/.../" ,
  "definitions": "1. ...\n2. ...\n3. ...",
  "examples": "1. ...\n2. ...\n3. ...",
  "word_cn": "...",
  "definitions_cn": "1. ...\n2. ...\n3. ...",
  "examples_cn": "1. ...\n2. ...\n3. ..."
}

**Examples:**

Input: apple
Output:
{
  "word": "apple",
  "ipa": "/ˈæpl/",
  "definitions": "1. An apple is a round fruit with red, green, or yellow skin.",
  "examples": "1. Fresh apples are often consumed for their health benefits.",
  "word_cn": "苹果",
  "definitions_cn": "1. 苹果是一种有红色、绿色或黄色外皮的圆形水果。",
  "examples_cn": "1. 新鲜的苹果通常因其健康益处而被食用。"
}

Input: pollution
Output:
{
  "word": "pollution",
  "ipa": "/pəˈluːʃn/",
  "definitions": "1. Pollution is damage caused to water, air, or land by waste.",
  "examples": "1. Strict laws are needed to reduce environmental pollution in cities.",
  "word_cn": "污染",
  "definitions_cn": "1. 污染是由废物对水、空气或土地造成的损害。",
  "examples_cn": "1. 需要严格的法律来减少城市的这种环境污染。"
}

Input: wave
Output:
{
  "word": "wave",
  "ipa": "/weɪv/",
  "definitions": "1. A wave is a line of water that moves higher than the rest of the water.\n2. To wave is to move your hand to say hello or goodbye.",
  "examples": "1. Huge waves crashed against the rocky coastline during the storm.\n2. The passengers waved to their families from the departing train.",
  "word_cn": "波浪；挥手",
  "definitions_cn": "1. 波浪是一排比其余水面更高的水。\n2. 挥手是移动你的手以打招呼或道别。",
  "examples_cn": "1. 暴风雨期间，巨大的海浪拍打着岩石海岸。\n2. 乘客们从开出的火车上向家人挥手。"
}

Input: behave
Output:
{
  "word": "behave",
  "ipa": "/bɪˈheɪv/",
  "definitions": "1. To behave is to act in a particular way, especially to be good.",
  "examples": "1. Students are expected to behave properly during the formal examination.",
  "word_cn": "表现；守规矩",
  "definitions_cn": "1. 表现是以特定的方式行事，特别是要表现得好。",
  "examples_cn": "1. 学生们被期望在正式考试期间表现得体。"
}

Input: appropriate
Output:
{
  "word": "appropriate",
  "ipa": "/əˈprəʊpriət/",
  "definitions": "1. It is appropriate to do something that is suitable for a situation.",
  "examples": "1. Dark clothing is considered appropriate for the funeral service.",
  "word_cn": "合适的",
  "definitions_cn": "1. 做适合某种情况的事情是恰当的。",
  "examples_cn": "1. 深色衣服被认为适合葬礼仪式。"
}

Input: give up
Output:
{
  "word": "give up",
  "ipa": "/ɡɪv ʌp/",
  "definitions": "1. To give up is to stop doing or having something (often a habit).\n2. To give up is to stop trying to guess or solve something.",
  "examples": "1. Many patients give up smoking to improve lung function.\n2. The student decided to give up on the difficult puzzle.",
  "word_cn": "放弃",
  "definitions_cn": "1. 放弃是停止做某事或拥有某物（通常是习惯）。\n2. 放弃是停止尝试猜测或解决某事。",
  "examples_cn": "1. 许多患者戒烟以改善肺功能。\n2. 这名学生决定放弃这个困难的谜题。"
}

Input: tear (crying)
Output:
{
  "word": "tear",
  "ipa": "/tɪə/",
  "definitions": "1. A tear is a drop of clear liquid from the eyes.\n2. To tear is to pull something apart with force.",
  "examples": "1. A single tear fell as she read the sad news.\n2. Care is needed not to tear the old documents.",
  "word_cn": "眼泪；撕裂",
  "definitions_cn": "1. 眼泪是从眼睛流出的一滴透明液体。\n2. 撕裂是用力将某物撕开。",
  "examples_cn": "1. 当她读到悲伤的消息时，一滴眼泪落下。\n2. 需要小心不要撕破旧文件。"
}
"""
    
    # 4. 调用 API（一次性获取所有数据）
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": vocab_prompt},
                {"role": "user", "content": f"Input: {input_text}"},
            ],
            temperature=0.1,
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # 5. 解析 JSON
        result_text = result_text.replace("```json", "").replace("```", "").strip()
        data = json.loads(result_text)
        
        # 6. 验证数据结构
        required_keys = ["word", "ipa", "definitions", "examples", "word_cn", "definitions_cn", "examples_cn"]
        for key in required_keys:
            if key not in data:
                raise ValueError(f"返回数据缺少必需字段: {key}")
        
        return data
        
    except json.JSONDecodeError as e:
        print(f"JSON 解析失败: {e}")
        print(f"原始返回内容: {result_text}")
        return {
            "word": cleaned_word,
            "ipa": "/error/",
            "definitions": "Error parsing response.",
            "examples": "Error parsing response."
        }
    except Exception as e:
        import ssl
        # 检测是否为 SSL 错误
        error_msg = str(e)
        if "SSL" in error_msg or "ssl" in error_msg.lower() or "CFNetwork" in error_msg:
            print(f"⚠️ SSL 连接错误 (可能是网络抖动): {e}")
            print(f"💡 建议: 重试通常可以解决此问题，或检查网络连接")
        else:
            print(f"API 调用出错: {e}")
        return {
            "word": cleaned_word,
            "ipa": "/error/",
            "definitions": "Error generating content.",
            "examples": "Error generating content."
        }



def generate_audio_files(word_card: dict, output_dir="media", speed_config=None, azure_config=None) -> dict:
    """
    接收 generate_word_card 的返回结果，利用 Azure TTS 生成 4 个音频文件。
    
    Args:
        word_card (dict): 包含 word, definitions, examples 的字典
        output_dir (str): 音频文件的保存目录，默认为 "media"
        speed_config (dict, optional): 自定义语速配置。
            默认值如下，你可以传入字典覆盖特定项：
            {
                "word_slow": "-30%",   # 单词慢读 (减慢30%)
                "word_fast": "0%",     # 单词快读 (原速)
                "definitions": "0%",   # 释义 (原速)
                "examples": "-5%"      # 例句 (稍慢)
            }
        azure_config (dict, optional): Azure TTS 配置，包含 speech_key, region, voice_name
        
    Returns:
        dict: 在原字典基础上增加了 audio_files 字段，包含具体的文件路径
    """
    
    # ==========================================
    # 0. 处理语速配置 (默认值 + 用户覆盖)
    # ==========================================
    # Azure rate 支持格式: "-30%"(减慢), "+20%"(加快), "0%"(原速)
    current_speeds = {
        "word_slow": "-30%",
        "word_fast": "0%",
        "definitions": "-10%",
        "examples": "-10%"
    }
    # 如果用户传了配置，则更新默认值
    if speed_config:
        current_speeds.update(speed_config)

    # 1. 检查 API Key (使用配置或默认值)
    if azure_config is None:
        azure_config = {
            "speech_key": "请在 config.yaml 中配置你的 Azure 语音服务订阅密钥",
            "region": "eastus",
            "voice_name": "en-GB-SoniaNeural"
        }
    
    speech_key = azure_config.get("speech_key", "")
    service_region = azure_config.get("region", "eastus") 

    if not speech_key or not service_region:
        raise ValueError("请设置环境变量 AZURE_SPEECH_KEY 和 AZURE_SPEECH_REGION")

    # 2. 确保输出目录存在
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    # 3. 初始化 Azure 合成器
    speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)
    voice_name = azure_config.get("voice_name", "en-GB-SoniaNeural")
    speech_config.speech_synthesis_voice_name = voice_name

    # 4. 定义辅助函数：执行合成并保存文件
    def synthesize_ssml_to_file(ssml_text, filename):
        file_path = os.path.join(output_dir, filename)
        audio_config = speechsdk.audio.AudioOutputConfig(filename=file_path)
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
        
        try:
            result = synthesizer.speak_ssml_async(ssml_text).get()
            
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                print(f"✅ 生成成功: {filename}")
                return file_path
            elif result.reason == speechsdk.ResultReason.Canceled:
                cancellation_details = result.cancellation_details
                print(f"❌ 生成取消: {filename}, 原因: {cancellation_details.reason}")
                if cancellation_details.reason == speechsdk.CancellationReason.Error:
                    error_msg = cancellation_details.error_details
                    # 检测 SSL 相关错误
                    if "SSL" in error_msg or "connection" in error_msg.lower() or "WS_OPEN_ERROR" in error_msg:
                        print(f"⚠️ Azure TTS SSL/连接错误: {error_msg}")
                        print(f"💡 这通常是网络抖动引起，重试即可解决")
                    else:
                        print(f"错误详情: {error_msg}")
                return None
        except Exception as e:
            print(f"⚠️ Azure TTS 异常: {filename} - {e}")
            return None

    # 5. 定义辅助函数：构建 SSML 框架
    def build_ssml(content):
        return f"""
        <speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="en-GB">
            <voice name="{voice_name}">
                {content}
            </voice>
        </speak>
        """

    # --- 准备文件名 (去除特殊字符) ---
    clean_word = re.sub(r'[\\/*?:"<>|]', "", word_card['word']).replace(" ", "_")
    paths = {}

    print(f"正在为单词 '{word_card['word']}' 生成音频...")

    # ==========================================
    # A. 单词慢速 (Word Slow)
    # ==========================================
    ssml_slow = build_ssml(f"""
        <prosody rate="{current_speeds['word_slow']}">
            {word_card['word']}
        </prosody>
    """)
    paths['word_slow'] = synthesize_ssml_to_file(ssml_slow, f"{clean_word}_slow.mp3")

    # ==========================================
    # B. 单词快速/正常 (Word Fast)
    # ==========================================
    ssml_fast = build_ssml(f"""
        <prosody rate="{current_speeds['word_fast']}">
            {word_card['word']}
        </prosody>
    """)
    paths['word_fast'] = synthesize_ssml_to_file(ssml_fast, f"{clean_word}_fast.mp3")

    # ==========================================
    # C. 释义朗读 (Definitions)
    # ==========================================
    def_lines = word_card['definitions'].split('\n')
    def_lines = [line.strip() for line in def_lines if line.strip()]
    
    def_content = ""
    for line in def_lines:
        # 这里给每一行都加上了语速控制
        def_content += f"<prosody rate='{current_speeds['definitions']}'>{line}</prosody> <break time='800ms'/> "
    
    ssml_defs = build_ssml(def_content)
    paths['definitions'] = synthesize_ssml_to_file(ssml_defs, f"{clean_word}_defs.mp3")

    # ==========================================
    # D. 例句朗读 (Examples)
    # ==========================================
    ex_lines = word_card['examples'].split('\n')
    ex_lines = [line.strip() for line in ex_lines if line.strip()]

    ex_content = ""
    for line in ex_lines:
        ex_content += f"<prosody rate='{current_speeds['examples']}'>{line}</prosody> <break time='1000ms'/> "

    ssml_examples = build_ssml(ex_content)
    paths['examples'] = synthesize_ssml_to_file(ssml_examples, f"{clean_word}_ex.mp3")

    return paths


# ==========================================
# 口语卡生成函数 (Speaking Card Functions)
# ==========================================

def get_speaking_data(input_text: str, api_config: dict = None) -> dict:
    """
    生成口语训练卡的数据：中文意图 + 英文短语 + 时态例句
    
    Args:
        input_text (str): 输入的英文短语，例如 "capture the moment"
        api_config (dict, optional): API 配置字典，包含 base_url, api_key, model_name
        
    Returns:
        dict: 包含 meaning_cn (中文释义), word_en (英文短语), examples (3个时态例句的列表)
    """
    
    # 1. 初始化客户端
    if api_config is None:
        api_config = {
            "base_url": "https://ark.cn-beijing.volces.com/api/v3",
            "api_key": "请在 config.yaml 中配置你的 API Key",
            "model_name": "deepseek-v3-2-251201"
        }
    
    client = OpenAI(
        base_url=api_config.get("base_url", "https://ark.cn-beijing.volces.com/api/v3"),
        api_key=api_config.get("api_key", ""),
    )
    
    MODEL_NAME = api_config.get("model_name", "deepseek-v3-2-251201")
    
    # 2. 清洗输入文本（只去除括号内容，保留短语内部的连字符等）
    import json
    cleaned_phrase = re.sub(r'[\(\uff08].*?[\)\uff09]', '', input_text)
    cleaned_phrase = cleaned_phrase.strip().strip('"').strip("'")  # 去除首尾可能的引号
    
    # 3. 定义 Prompt - 生成口语训练数据
    speaking_prompt = """
You are an English speaking coach.
Task: Generate speaking training materials based on the input phrase.

**Student Profile (Context):**
- **Background:** IT/Computer Science (Coding, Tech), but keep it simple.
- **Hometown:** Huainan, Anhui (Small city life, Beef soup).
- **Interests:** Gaming, Photography.

**Rules:**
1. **Input:** English phrase (Verb, Noun, Adjective, or Idiom).
2. **Output:** JSON object.

3. **CRITICAL: Context & Parentheses Handling**
   - **Case A: With Parentheses (Context provided)** 
     (e.g., "phrase (context/specific meaning)"):
     * **Meaning:** `meaning_cn` MUST reflect this specific context/nuance.
     * **Examples:** At least ONE example must implicitly demonstrate this specific usage scenario.
     * **Note:** You may use parentheses in Chinese translation if it helps align with the input.

   - **Case B: No Parentheses (Standard)**
     (e.g., "phrase"):
     * **Meaning:** **Keep `meaning_cn` EXTREMELY SHORT** (ideally 2-4 Chinese characters).
     * **Constraint:** Provide ONLY the most common/direct translation. **DO NOT** explain the word or add extra details. (e.g., use "放弃" instead of "放弃某种习惯或停止尝试").

4. **CRITICAL: Part-of-Speech Adaptation Strategy**
   Analyze the input and choose the strategy:
   * **STRATEGY A: Verb Phrase** -> Conjugate verbs naturally based on the sentence context.
     - *Priority:* If the verb has an **Irregular Past Tense** (e.g., catch->caught) or **Special 3rd Person form** (e.g., study->studies), look for opportunities to showcase these.
   * **STRATEGY B: Fixed Phrase** -> KEEP phrase exactly as is. Use helping verbs.

5. **Content Requirements (Grammar & Logic Balance):**
   - **meaning_cn**: Concise Chinese meaning.
   - **ipa**: British English IPA.
   - **examples**: Generate 3 examples with **Mixed Subjects**, **Gradual Depth**, and **Varied Tenses**:
   
     * **CRITICAL TENSE STRATEGY:** 1. **Analyze the Semantics:** Does the input phrase naturally fit a memory (Past), a habit (Present), or a plan (Future)? Use the most logical tense for the meaning.
       2. **Enforce Variety:** You MUST NOT use the same tense for all 3 examples. Ensure a mix (e.g., Past + Present + Modal/Future) across the three sentences.

     * **Example 1: Personal (Me/I).**
       - Context: Relate to the Student's life (Coding, Gaming, Huainan).
       - **Grammar:** Choose the tense that best fits the story you are telling. (e.g., If talking about a completed game level -> Past; If talking about a daily coding habit -> Present).
     
     * **Example 2: Specific Others (Vary the Subject!).**
       - Context: Describe diverse people (Parents, Boss, Gamers, Team). **DO NOT just use "My friend".**
       - **Grammar:** Use a subject other than "I" (Singular or Plural).
       - **Constraint:** If you use Present Tense with a **Singular** subject, you MUST show the 's/es' ending (e.g., fixes, tries).
     
     * **Example 3: General/Society (People/Technology/The World).**
       - Context: Part 3 style generalization or future trend.
       - *Goal:* Abstract thinking using simple words.
       - **Grammar:** Use a tense suitable for social commentary or prediction (often Present or Future).

   - **CRITICAL: Language Constraints:**
     * **Level:** IELTS 5.5 - 6.5.
     * **Vocabulary:** Simple & Natural. No academic jargon.
     * **Length:** Short and punchy (8-12 words).

   - **examples_cn**: Array of 3 Chinese translations.

6. **Output JSON:**
   {
     "meaning_cn": "...",
     "word_en": "...",
     "ipa": "/.../" ,
     "examples": ["...", "...", "..."],
     "examples_cn": ["...", "...", "..."]
   }
"""
    
    # 4. 调用 API
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": speaking_prompt},
                {"role": "user", "content": f"Input: {input_text}"},
            ],
            temperature=0.1,
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # 5. 解析 JSON 结果
        # 清理可能的 markdown 代码块标记
        result_text = result_text.replace("```json", "").replace("```", "").strip()
        
        data = json.loads(result_text)
        
        # 6. 验证数据结构
        required_keys = ["meaning_cn", "word_en", "ipa", "examples", "examples_cn"]
        for key in required_keys:
            if key not in data:
                raise ValueError(f"返回数据缺少必需字段: {key}")
        
        if not isinstance(data["examples"], list) or len(data["examples"]) != 3:
            raise ValueError("examples 必须是包含3个句子的列表")
        
        if not isinstance(data["examples_cn"], list) or len(data["examples_cn"]) != 3:
            raise ValueError("examples_cn 必须是包含3个中文翻译的列表")
        
        return data
        
    except json.JSONDecodeError as e:
        print(f"JSON 解析失败: {e}")
        print(f"原始返回内容: {result_text}")
        return {
            "meaning_cn": "解析失败",
            "word_en": cleaned_phrase,
            "ipa": "/error/",
            "examples": ["Error parsing response.", "Error parsing response.", "Error parsing response."]
        }
    except Exception as e:
        print(f"API 调用出错: {e}")
        return {
            "meaning_cn": "生成失败",
            "word_en": cleaned_phrase,
            "ipa": "/error/",
            "examples": ["Error generating content.", "Error generating content.", "Error generating content."]
        }


def get_speaking_audio(data: dict, output_dir="media_speaking", speed_config=None, azure_config=None) -> dict:
    """
    为口语卡生成音频文件（慢速、常速、每个例句独立文件）
    
    Args:
        data (dict): get_speaking_data 返回的数据，包含 word_en, examples
        output_dir (str): 音频文件保存目录
        speed_config (dict, optional): 语速配置
            默认值: {
                "word_slow": "-30%",
                "word_fast": "0%",
                "examples": "-10%"
            }
        azure_config (dict, optional): Azure TTS 配置
        
    Returns:
        dict: 包含音频文件路径的字典，包括 word_slow, word_fast, example_1, example_2, example_3
    """
    
    # 1. 处理语速配置
    current_speeds = {
        "word_slow": "-30%",
        "word_fast": "0%",
        "examples": "-10%"
    }
    if speed_config:
        current_speeds.update(speed_config)
    
    # 2. 处理 Azure 配置
    if azure_config is None:
        azure_config = {
            "speech_key": "请在 config.yaml 中配置你的 Azure 语音服务订阅密钥",
            "region": "eastus",
            "voice_name": "en-GB-SoniaNeural"
        }
    
    speech_key = azure_config.get("speech_key", "")
    service_region = azure_config.get("region", "eastus")
    
    if not speech_key or not service_region:
        raise ValueError("请配置 Azure 语音服务密钥和区域")
    
    # 3. 确保输出目录存在
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    
    # 4. 初始化 Azure 合成器
    speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)
    voice_name = azure_config.get("voice_name", "en-GB-SoniaNeural")
    speech_config.speech_synthesis_voice_name = voice_name
    
    # 5. 定义辅助函数：执行合成
    def synthesize_ssml_to_file(ssml_text, filename):
        file_path = os.path.join(output_dir, filename)
        audio_config = speechsdk.audio.AudioOutputConfig(filename=file_path)
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
        
        try:
            result = synthesizer.speak_ssml_async(ssml_text).get()
            
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                print(f"✅ 生成成功: {filename}")
                return file_path
            elif result.reason == speechsdk.ResultReason.Canceled:
                cancellation_details = result.cancellation_details
                print(f"❌ 生成取消: {filename}, 原因: {cancellation_details.reason}")
                if cancellation_details.reason == speechsdk.CancellationReason.Error:
                    error_msg = cancellation_details.error_details
                    # 检测 SSL 相关错误
                    if "SSL" in error_msg or "connection" in error_msg.lower() or "WS_OPEN_ERROR" in error_msg:
                        print(f"⚠️ Azure TTS SSL/连接错误: {error_msg}")
                        print(f"💡 这通常是网络抖动引起，重试即可解决")
                    else:
                        print(f"错误详情: {error_msg}")
                return None
        except Exception as e:
            print(f"⚠️ Azure TTS 异常: {filename} - {e}")
            return None
    
    # 6. 定义辅助函数：构建 SSML
    def build_ssml(content):
        return f"""
        <speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang="en-GB">
            <voice name="{voice_name}">
                {content}
            </voice>
        </speak>
        """
    
    # 7. 准备文本和文件名
    # 7.1 为 TTS 准备的"可读文本"（把 / 转换为 or，避免读错）
    # 例如: "read/write" -> "read or write"
    speakable_word = data['word_en'].replace("/", " or ")
    
    # 7.2 为文件名准备的"安全文本"（移除所有非法字符）
    clean_phrase = re.sub(r'[\\/*?:"<>|]', "", data['word_en']).replace(" ", "_")
    paths = {}
    
    print(f"正在为短语 '{data['word_en']}' 生成音频...")
    
    # ==========================================
    # A. 短语慢速 (Word Slow)
    # ==========================================
    ssml_slow = build_ssml(f"""
        <prosody rate="{current_speeds['word_slow']}">
            {speakable_word}
        </prosody>
    """)
    paths['word_slow'] = synthesize_ssml_to_file(ssml_slow, f"{clean_phrase}_slow.mp3")
    
    # ==========================================
    # B. 短语常速 (Word Fast)
    # ==========================================
    ssml_fast = build_ssml(f"""
        <prosody rate="{current_speeds['word_fast']}">
            {speakable_word}
        </prosody>
    """)
    paths['word_fast'] = synthesize_ssml_to_file(ssml_fast, f"{clean_phrase}_fast.mp3")
    
    # ==========================================
    # C. 例句朗读 (每个例句单独生成音频文件)
    # ==========================================
    examples = data.get('examples', [])
    for i, example in enumerate(examples, 1):
        ssml_example = build_ssml(f"""
            <prosody rate="{current_speeds['examples']}">
                {example}
            </prosody>
        """)
        paths[f'example_{i}'] = synthesize_ssml_to_file(ssml_example, f"{clean_phrase}_ex{i}.mp3")
    
    return paths


def create_anki_package(word_list: list, package_name="My_Vocabulary_Deck.apkg", media_output_dir="media_temp", 
                       api_config=None, azure_config=None, speed_config=None, deck_name="new words deck",
                       card_type="vocab", max_workers=10, max_retries=3, retry_delay=2,
                       error_log_file="errorword.txt"):
    """
    输入一个单词列表，自动完成：内容生成 -> 语音合成 -> 制卡 -> 打包 (.apkg)
    
    Args:
        word_list: 单词列表
        package_name: 输出的 apkg 文件名
        media_output_dir: 临时媒体文件目录
        api_config: OpenAI API 配置
        azure_config: Azure TTS 配置
        speed_config: 语速配置
        deck_name: Anki 卡组名称
        card_type: 卡片类型 - "vocab" (词汇卡), "dictation" (听写卡), "both" (两种都生成)
        max_workers: 并行处理的最大线程数，默认 10
        max_retries: 每张卡片失败后的最大重试次数，默认 3
        retry_delay: 重试间隔时间（秒），默认 2
        error_log_file: 失败单词日志文件路径，默认 "errorword.txt"
    """

    # =========================================================
    # 1. 定义 Anki 模板
    # =========================================================
    
    # =========================================================
    # 1.1 词汇卡模板 (Vocab Card)
    # =========================================================
    
    # 定义通用的缩放脚本，注入到所有卡片中
    zoom_script = """
    <script>
    // 快捷键缩放支持 (Cmd/Ctrl + +/-/0)
    document.addEventListener('keydown', function(e) {
        // 检查 Cmd(Mac) 或 Ctrl(Windows)
        if (e.metaKey || e.ctrlKey) {
            var key = e.key;
            // 兼容不同键盘布局的 +/= 键
            if (key === '=' || key === '+' || key === '-' || key === '0') {
                e.preventDefault();
                var root = document.documentElement;
                var style = window.getComputedStyle(root);
                var currentVal = style.getPropertyValue('--base-font-size').trim();
                var currentSize = parseFloat(currentVal) || 16;
                
                if (key === '=' || key === '+') {
                    currentSize += 2;
                } else if (key === '-') {
                    currentSize -= 2;
                } else if (key === '0') {
                    currentSize = 16;
                }
                
                // 限制范围
                if (currentSize < 10) currentSize = 10;
                if (currentSize > 60) currentSize = 60;
                
                root.style.setProperty('--base-font-size', currentSize + 'px');
            }
        }
    });
    </script>
    """

    vocab_css = """
    /* 可调节的字体大小变量 - 在 Anki 中可以修改这个值来缩放整个卡片 */
    :root {
        --base-font-size: 16px;  /* 修改这个值: 14px(小), 16px(默认), 18px(中), 20px(大), 24px(超大) */
        font-size: var(--base-font-size);
    }
    .card { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; font-size: var(--base-font-size); line-height: 1.6; color: #333; background-color: #f4f4f7; display: flex; justify-content: center; align-items: flex-start; height: 100%; margin: 0; padding: 20px; }
    
    /* 默认容器样式 (手机/窄屏) */
    .main-container { background-color: #fff; width: 100%; max-width: 600px; border-radius: 16px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08); padding: 30px; text-align: left; box-sizing: border-box; }
    
    /* 宽屏响应式布局 (电脑/平板) - 仅针对背面 (.back-mode) 生效 */
    @media (min-width: 800px) {
        .main-container.back-mode {
            max-width: 1100px; /* 允许更宽 */
            display: flex;
            flex-direction: row;
            align-items: flex-start;
            gap: 40px;
        }
        
        .content-column {
            flex: 1; /* 左侧占据剩余空间 */
            min-width: 0; /* 防止溢出 */
        }
        
        .translation-section {
            width: 320px; /* 右侧固定宽度 */
            flex-shrink: 0;
            margin-top: 0 !important;
            padding-left: 40px;
            border-left: 1px solid #eee;
            position: sticky;
            top: 20px;
        }
        
        /* 宽屏下隐藏原来底部的分割线 */
        .divider.bottom-divider {
            display: none;
        }
        
        /* 宽屏下保留按钮，用户点击才显示中文释义 */
    }

    .word-header { text-align: center; margin-bottom: 10px; }
    .word { font-size: 2.8rem; font-weight: 700; color: #2d3436; letter-spacing: -0.5px; margin-bottom: 5px; }
    .ipa { font-family: "Menlo", "Monaco", "Consolas", monospace; font-size: 1.1rem; color: #888; background-color: #f0f0f0; padding: 2px 8px; border-radius: 6px; display: inline-block; }
    .audio-bar { text-align: center; margin-top: 15px; margin-bottom: 25px; }
    hr.divider { border: 0; height: 1px; background: #eee; margin: 20px 0; }
    .section-title { font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px; font-weight: 600; color: #b2bec3; margin-bottom: 10px; display: flex; align-items: center; gap: 8px; }
    .content-box { padding: 12px 10px; border-radius: 8px; margin-bottom: 20px; white-space: pre-line; }
    .definition-box { background-color: #fbfbfb; border-left: 4px solid #0984e3; font-size: 1.45rem; color: #2d3436; }
    .example-box { background-color: #fbfbfb; border-left: 4px solid #00b894; font-size: 1.3rem; color: #555; font-style: italic; }
    .audio-tag { font-size: 0.8rem; color: #aaa; margin-top: 8px; text-align: right; display: flex; justify-content: flex-end; align-items: center; gap: 5px; }
    
    /* 中文释义按钮和内容区域 */
    .translation-section { margin-top: 20px; text-align: center; }
    .translation-btn {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 12px 24px;
        font-size: 0.95rem;
        font-weight: 600;
        border-radius: 8px;
        cursor: pointer;
        transition: all 0.3s;
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
    }
    .translation-btn:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(102, 126, 234, 0.4);
    }
    .translation-content {
        margin-top: 15px;
        padding: 20px;
        background-color: #fff9e6;
        border-radius: 12px;
        border-left: 4px solid #f39c12;
        text-align: left;
        animation: fadeIn 0.3s ease;
    }
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(-10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .translation-item {
        margin-bottom: 15px;
        line-height: 1.8;
    }
    .translation-label {
        font-weight: 700;
        color: #d35400;
        margin-right: 8px;
    }
    .translation-text {
        color: #555;
        white-space: pre-line;
    }
    /* 夜间模式 */
    .nightMode .card { background-color: #1e1e1e; color: #f5f6fa; }
    .nightMode .main-container { background-color: #2d2d2d; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4); }
    .nightMode .word { color: #f5f6fa; }
    .nightMode .ipa { background-color: #383838; color: #bbb; }
    .nightMode hr.divider { background: #444; }
    .nightMode .definition-box { background-color: #333; border-left-color: #74b9ff; color: #eee; }
    .nightMode .example-box { background-color: #333; border-left-color: #55efc4; color: #ccc; }
    .nightMode .translation-content {
        background-color: #2d2d44;
        border-left-color: #f39c12;
    }
    .nightMode .translation-label {
        color: #f39c12;
    }
    .nightMode .translation-text {
        color: #ccc;
    }
    /* 宽屏夜间模式边框适配 */
    @media (min-width: 800px) {
        .nightMode .translation-section {
            border-left-color: #444;
        }
    }
    """

    vocab_front_html = """
    <div class="main-container">
        <div class="word-header">
            <div class="word">{{Word}}</div>
            <div class="ipa">{{IPA}}</div>
        </div>
        <div class="audio-bar">{{WordAudio}}</div>
    </div>
    """

    vocab_back_html = """
    <div class="main-container back-mode">
        <div class="content-column">
            <div class="word-header">
                <div class="word">{{Word}}</div>
                <div class="ipa">{{IPA}}</div>
            </div>
            <div class="audio-bar">{{WordAudio}}</div>
            <hr class="divider">
            <div class="section-title"><span>📖 Definitions</span></div>
            <div class="content-box definition-box">{{Definitions}}<div class="audio-tag"><span>Listen</span> {{MeaningAudio}}</div></div>
            <div class="section-title"><span>🗣️ Examples</span></div>
            <div class="content-box example-box">{{Examples}}<div class="audio-tag"><span>Listen</span> {{ExampleAudio}}</div></div>
            <hr class="divider bottom-divider">
        </div>

        <div class="translation-section">
            <button id="toggle-translation" class="translation-btn">显示中文释义 (C)</button>
            <div id="translation-content" class="translation-content" style="display:none;">
                <div class="translation-item">
                    <span class="translation-label">单词:</span>
                    <span class="translation-text">{{WordCN}}</span>
                </div>
                <div class="translation-item">
                    <span class="translation-label">定义:</span>
                    <div class="translation-text">{{DefinitionsCN}}</div>
                </div>
                <div class="translation-item">
                    <span class="translation-label">例句:</span>
                    <div class="translation-text">{{ExamplesCN}}</div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
    // 中文释义切换功能
    (function() {
        var btn = document.getElementById('toggle-translation');
        var content = document.getElementById('translation-content');
        
        function toggleChinese() {
            if (content.style.display === 'none') {
                content.style.display = 'block';
                btn.textContent = '隐藏中文释义 (C)';
            } else {
                content.style.display = 'none';
                btn.textContent = '显示中文释义 (C)';
            }
        }
        
        if (btn && content) {
            btn.addEventListener('click', toggleChinese);
            
            // 快捷键 C 切换中文释义 (C = Chinese)
            document.addEventListener('keydown', function(e) {
                // 忽略在输入框中的按键
                if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
                if (e.key === 'c' || e.key === 'C') {
                    toggleChinese();
                }
            });
        }
    })();
    </script>
    """

    # =========================================================
    # 1.2 听写卡模板 (Dictation Card) - 三段式结构
    # =========================================================
    dictation_css = """
    /* 可调节的字体大小变量 - 在 Anki 中可以修改这个值来缩放整个卡片 */
    :root {
        --base-font-size: 16px;  /* 修改这个值: 14px(小), 16px(默认), 18px(中), 20px(大), 24px(超大) */
        font-size: var(--base-font-size);
    }
    .card { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; font-size: var(--base-font-size); line-height: 1.6; color: #333; background-color: #e8f4f8; display: flex; justify-content: center; align-items: flex-start; height: 100%; margin: 0; padding: 20px; }
    
    /* 默认容器样式 */
    .main-container { background-color: #fff; width: 100%; max-width: 600px; border-radius: 16px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08); padding: 30px; text-align: center; box-sizing: border-box; }
    
    /* 响应式显示/隐藏 */
    .desktop-only { display: none; }
    .mobile-only { display: block; }
    
    /* 移动端中文释义区域 */
    .mobile-chinese-section {
        margin: 20px 0;
        text-align: center;
    }
    
    /* 移动端校验区域 */
    .mobile-check-section {
        margin: 15px 0;
    }
    
    /* 英文释义区域 */
    .english-section {
        text-align: center;
    }
    
    /* 宽屏响应式布局 (电脑/平板) - 左右分栏 */
    @media (min-width: 800px) {
        .desktop-only { display: block; }
        .mobile-only { display: none !important; }
        
        .main-container.back-mode {
            max-width: 1100px;
            display: flex;
            flex-direction: row;
            align-items: flex-start;
            gap: 40px;
        }
        
        .content-column {
            flex: 1;
            min-width: 0;
        }
        
        .right-section {
            width: 350px;
            flex-shrink: 0;
            margin-top: 0 !important;
            padding-left: 40px;
            border-left: 1px solid #eee;
            position: sticky;
            top: 20px;
            text-align: center;
        }
        
        /* 宽屏下英文释义按钮居左 */
        .english-section {
            text-align: left;
        }
    }
    
    /* 夜间模式宽屏适配 */
    @media (min-width: 800px) {
        .nightMode .right-section {
            border-left-color: #444;
        }
    }

    /* 听写卡正面 - 音频区域 */
    .listen-prompt { font-size: 1.2rem; color: #636e72; margin-bottom: 20px; }
    .audio-play-area { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 50%; width: 120px; height: 120px; margin: 20px auto; display: flex; justify-content: center; align-items: center; box-shadow: 0 8px 25px rgba(102, 126, 234, 0.4); }
    .audio-play-area:hover { transform: scale(1.05); transition: transform 0.2s; }
    .audio-icon { font-size: 3rem; }
    .replay-hint { font-size: 0.85rem; color: #b2bec3; margin-top: 15px; }
    
    /* 输入区域样式 */
    .input-section { margin-top: 30px; text-align: center; }
    .input-label { font-size: 0.9rem; color: #636e72; margin-bottom: 15px; }
    
    /* Anki 原生输入框美化 */
    .input-section input[type="text"] {
        width: 80%;
        max-width: 300px;
        padding: 15px 20px;
        font-size: 1.5rem;
        border: 2px solid #dfe6e9;
        border-radius: 12px;
        text-align: center;
        outline: none;
        transition: all 0.3s;
        background-color: #fff;
        color: #2d3436;
    }
    .input-section input[type="text"]:focus {
        border-color: #667eea;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.2);
    }
    
    /* 背面校验结果区域 */
    .type-answer-section {
        margin-bottom: 20px;
        padding: 15px;
        background-color: #f8f9fa;
        border-radius: 12px;
    }
    
    /* Anki 原生校验结果样式覆盖 */
    code#typeans {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
        font-size: 1.3rem !important;
        padding: 10px 15px !important;
        border-radius: 8px !important;
        display: inline-block !important;
    }
    
    /* 按钮组 */
    .btn-group {
        display: flex;
        justify-content: center;
        gap: 15px;
        flex-wrap: wrap;
        margin: 20px 0;
    }
    
    /* 通用切换按钮 */
    .toggle-btn {
        padding: 12px 20px;
        font-size: 0.95rem;
        font-weight: 600;
        border: none;
        border-radius: 8px;
        cursor: pointer;
        transition: all 0.3s;
        box-shadow: 0 3px 10px rgba(0, 0, 0, 0.1);
    }
    .toggle-btn:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(0, 0, 0, 0.15);
    }
    .toggle-btn:active {
        transform: scale(0.98);
    }
    
    /* 英文释义按钮 */
    .btn-english {
        background: linear-gradient(135deg, #0984e3 0%, #74b9ff 100%);
        color: white;
    }
    .btn-english.active {
        background: linear-gradient(135deg, #74b9ff 0%, #0984e3 100%);
    }
    
    /* 中文释义按钮 */
    .btn-chinese {
        background: linear-gradient(135deg, #fdcb6e 0%, #f39c12 100%);
        color: #2d3436;
    }
    .btn-chinese.active {
        background: linear-gradient(135deg, #f39c12 0%, #fdcb6e 100%);
    }
    
    /* 可折叠内容区域 */
    .collapsible-content {
        animation: fadeIn 0.3s ease;
        margin-top: 15px;
    }
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(-10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    /* 校验结果区域 */
    .result-area { margin-top: 20px; animation: slideIn 0.3s ease; }
    @keyframes slideIn { from { opacity: 0; transform: translateY(-10px); } to { opacity: 1; transform: translateY(0); } }
    .result-box { padding: 20px; border-radius: 12px; margin: 15px 0; }
    .result-box.correct { background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%); border: 2px solid #00b894; }
    .result-box.wrong { background: linear-gradient(135deg, #f8d7da 0%, #f5c6cb 100%); border: 2px solid #e17055; }
    .result-correct { color: #00b894; font-size: 1.2rem; }
    .result-wrong { color: #d63031; font-size: 1.1rem; line-height: 1.8; }
    .answer-word { font-size: 1.8rem; font-weight: 700; color: #2d3436; display: block; margin-top: 10px; }
    .answer-label { color: #636e72; font-size: 0.9rem; }
    .user-wrong { color: #d63031; text-decoration: line-through; font-size: 1.3rem; }
    .flip-hint { font-size: 0.85rem; color: #b2bec3; margin-top: 15px; }
    
    /* 背面 - 答案展示 */
    .word-header { text-align: center; margin-bottom: 10px; }
    .word { font-size: 2.8rem; font-weight: 700; color: #2d3436; letter-spacing: -0.5px; margin-bottom: 5px; }
    .ipa { font-family: "Menlo", "Monaco", "Consolas", monospace; font-size: 1.1rem; color: #888; background-color: #f0f0f0; padding: 2px 8px; border-radius: 6px; display: inline-block; }
    .audio-bar { text-align: center; margin-top: 15px; margin-bottom: 25px; }
    hr.divider { border: 0; height: 1px; background: #eee; margin: 20px 0; }
    .section-title { font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px; font-weight: 600; color: #b2bec3; margin-bottom: 10px; display: flex; align-items: center; justify-content: center; gap: 8px; }
    .content-box { padding: 12px 10px; border-radius: 8px; margin-bottom: 20px; white-space: pre-line; text-align: left; }
    .definition-box { background-color: #fbfbfb; border-left: 4px solid #0984e3; font-size: 1.3rem; color: #2d3436; }
    .example-box { background-color: #fbfbfb; border-left: 4px solid #00b894; font-size: 1.15rem; color: #555; font-style: italic; }
    
    /* 背面音频区域 */
    .audio-section { text-align: center; margin-top: 20px; }
    .audio-label { font-size: 0.9rem; color: #636e72; margin-bottom: 10px; }
    .audio-row { display: flex; justify-content: center; gap: 20px; flex-wrap: wrap; }
    .audio-item { font-size: 0.85rem; color: #888; }
    
    /* 中文释义按钮和内容区域 */
    .translation-section { margin-top: 20px; text-align: center; }
    .translation-btn {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 12px 24px;
        font-size: 0.95rem;
        font-weight: 600;
        border-radius: 8px;
        cursor: pointer;
        transition: all 0.3s;
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
    }
    .translation-btn:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(102, 126, 234, 0.4);
    }
    .translation-content {
        margin-top: 15px;
        padding: 20px;
        background-color: #fff9e6;
        border-radius: 12px;
        border-left: 4px solid #f39c12;
        text-align: left;
        animation: fadeIn 0.3s ease;
    }
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(-10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .translation-item {
        margin-bottom: 15px;
        line-height: 1.8;
    }
    .translation-label {
        font-weight: 700;
        color: #d35400;
        margin-right: 8px;
    }
    .translation-text {
        color: #555;
        white-space: pre-line;
    }
    /* 夜间模式 */
    .nightMode .card { background-color: #1a1a2e; color: #f5f6fa; }
    .nightMode .main-container { background-color: #16213e; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4); }
    .nightMode .listen-prompt { color: #a0a0a0; }
    .nightMode .audio-play-area { background: linear-gradient(135deg, #4a69bd 0%, #6a5acd 100%); }
    .nightMode .input-section input[type="text"] { background-color: #2d2d44; border-color: #444; color: #f5f6fa; }
    .nightMode .input-section input[type="text"]:focus { border-color: #667eea; box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.3); }
    .nightMode .type-answer-section { background-color: #1e1e30; }
    .nightMode .word { color: #f5f6fa; }
    .nightMode .ipa { background-color: #383838; color: #bbb; }
    .nightMode hr.divider { background: #444; }
    .nightMode .definition-box { background-color: #1e1e30; border-left-color: #74b9ff; color: #eee; }
    .nightMode .example-box { background-color: #1e1e30; border-left-color: #55efc4; color: #ccc; }
    .nightMode .translation-content {
        background-color: #2d2d44;
        border-left-color: #f39c12;
    }
    .nightMode .translation-label {
        color: #f39c12;
    }
    .nightMode .translation-text {
        color: #ccc;
    }
    /* 夜间模式按钮 */
    .nightMode .btn-english {
        background: linear-gradient(135deg, #4a69bd 0%, #74b9ff 100%);
    }
    .nightMode .btn-chinese {
        background: linear-gradient(135deg, #d4a520 0%, #f39c12 100%);
        color: #fff;
    }
    .nightMode .toggle-btn {
        box-shadow: 0 3px 10px rgba(0, 0, 0, 0.3);
    }
    """

    # 听写卡正面 - 使用 Anki 原生 {{type:}} 功能，所有平台都能正常唤起键盘
    dictation_front_html = """
    <div class="main-container">
        <div class="listen-prompt">🎧 听写练习</div>
        <div class="audio-play-area">
            <span class="audio-icon">🔊</span>
        </div>
        <div class="audio-bar">{{WordAudio}}</div>
        <div class="replay-hint">点击播放按钮可重复播放</div>
        <hr class="divider">
        <div class="input-section">
            <div class="input-label">✏️ 输入你听到的单词，翻面查看结果</div>
            <!-- 使用 Anki 原生输入功能 -->
            {{type:Word}}
        </div>
    </div>
    """

    # 听写卡背面 - 释义内容显示在按钮上方
    # 手机端：单词 -> 英文内容+按钮 -> 中文内容+按钮 -> 校验结果
    # 电脑端：左侧=单词+英文，右侧=校验+中文
    dictation_back_html = """
    <div class="main-container back-mode">
        <!-- 左侧：单词信息 + 英文释义 -->
        <div class="content-column">
            <div class="word-header">
                <div class="word">{{Word}}</div>
                <div class="ipa">{{IPA}}</div>
            </div>
            <div class="audio-bar">{{WordAudio}}</div>
            
            <hr class="divider">
            
            <!-- 英文释义（内容在按钮上方） -->
            <div class="english-section">
                <div id="english-content" class="collapsible-content" style="display:none;">
                    <div class="section-title"><span>📖 Definitions</span></div>
                    <div class="content-box definition-box">{{Definitions}}<div class="audio-tag"><span>Listen</span> {{MeaningAudio}}</div></div>
                    <div class="section-title"><span>🗣️ Examples</span></div>
                    <div class="content-box example-box">{{Examples}}<div class="audio-tag"><span>Listen</span> {{ExampleAudio}}</div></div>
                </div>
                <button id="toggle-english" class="toggle-btn btn-english">📖 显示英文释义 (W)</button>
            </div>
            
            <!-- 移动端：中文释义区域（内容在按钮上方） -->
            <div class="mobile-chinese-section mobile-only">
                <div id="chinese-content-mobile" class="collapsible-content translation-content" style="display:none;">
                    <div class="translation-item">
                        <span class="translation-label">单词:</span>
                        <span class="translation-text">{{WordCN}}</span>
                    </div>
                    <div class="translation-item">
                        <span class="translation-label">定义:</span>
                        <div class="translation-text">{{DefinitionsCN}}</div>
                    </div>
                    <div class="translation-item">
                        <span class="translation-label">例句:</span>
                        <div class="translation-text">{{ExamplesCN}}</div>
                    </div>
                </div>
                <button id="toggle-chinese-mobile" class="toggle-btn btn-chinese">🈶 显示中文释义 (C)</button>
            </div>
            
            <!-- 移动端：校验结果（显示在最下面） -->
            <div class="mobile-check-section mobile-only">
                <hr class="divider">
                <div class="type-answer-section">
                    {{type:Word}}
                </div>
            </div>
        </div>
        
        <!-- 右侧：校验结果 + 中文释义（仅宽屏显示） -->
        <div class="right-section desktop-only">
            <!-- 校验结果 -->
            <div class="type-answer-section">
                {{type:Word}}
            </div>
            
            <hr class="divider">
            
            <!-- 中文释义（内容在按钮上方） -->
            <div id="chinese-content-desktop" class="collapsible-content translation-content" style="display:none;">
                <div class="translation-item">
                    <span class="translation-label">单词:</span>
                    <span class="translation-text">{{WordCN}}</span>
                </div>
                <div class="translation-item">
                    <span class="translation-label">定义:</span>
                    <div class="translation-text">{{DefinitionsCN}}</div>
                </div>
                <div class="translation-item">
                    <span class="translation-label">例句:</span>
                    <div class="translation-text">{{ExamplesCN}}</div>
                </div>
            </div>
            <button id="toggle-chinese-desktop" class="toggle-btn btn-chinese">🈶 显示中文释义 (C)</button>
        </div>
    </div>
    
    <script>
    // 翻面后自动播放第一个音频
    (function() {
        setTimeout(function() {
            var firstAudio = document.querySelector('audio');
            if (firstAudio) {
                firstAudio.play().catch(function(e) { console.log('Auto-play blocked'); });
            }
        }, 300);
    })();
    
    // 英文释义切换
    (function() {
        var btn = document.getElementById('toggle-english');
        var content = document.getElementById('english-content');
        
        function toggleEnglish() {
            if (content.style.display === 'none') {
                content.style.display = 'block';
                btn.textContent = '📖 隐藏英文释义 (W)';
                btn.classList.add('active');
            } else {
                content.style.display = 'none';
                btn.textContent = '📖 显示英文释义 (W)';
                btn.classList.remove('active');
            }
        }
        
        if (btn && content) {
            btn.addEventListener('click', toggleEnglish);
        }
        
        // 快捷键 W 切换英文释义 (W = Word)
        document.addEventListener('keydown', function(e) {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
            if (e.key === 'w' || e.key === 'W') {
                toggleEnglish();
            }
        });
    })();
    
    // 中文释义切换（移动端）
    (function() {
        var btnMobile = document.getElementById('toggle-chinese-mobile');
        var contentMobile = document.getElementById('chinese-content-mobile');
        var btnDesktop = document.getElementById('toggle-chinese-desktop');
        var contentDesktop = document.getElementById('chinese-content-desktop');
        
        function toggleChineseMobile() {
            if (contentMobile && contentMobile.style.display === 'none') {
                contentMobile.style.display = 'block';
                if (btnMobile) {
                    btnMobile.textContent = '🈶 隐藏中文释义 (C)';
                    btnMobile.classList.add('active');
                }
            } else if (contentMobile) {
                contentMobile.style.display = 'none';
                if (btnMobile) {
                    btnMobile.textContent = '🈶 显示中文释义 (C)';
                    btnMobile.classList.remove('active');
                }
            }
        }
        
        function toggleChineseDesktop() {
            if (contentDesktop && contentDesktop.style.display === 'none') {
                contentDesktop.style.display = 'block';
                if (btnDesktop) {
                    btnDesktop.textContent = '🈶 隐藏中文释义 (C)';
                    btnDesktop.classList.add('active');
                }
            } else if (contentDesktop) {
                contentDesktop.style.display = 'none';
                if (btnDesktop) {
                    btnDesktop.textContent = '🈶 显示中文释义 (C)';
                    btnDesktop.classList.remove('active');
                }
            }
        }
        
        if (btnMobile) btnMobile.addEventListener('click', toggleChineseMobile);
        if (btnDesktop) btnDesktop.addEventListener('click', toggleChineseDesktop);
        
        // 快捷键 C 切换中文释义 (C = Chinese)
        document.addEventListener('keydown', function(e) {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
            if (e.key === 'c' || e.key === 'C') {
                toggleChineseMobile();
                toggleChineseDesktop();
            }
        });
    })();
    </script>
    """

    # =========================================================
    # 1.3 口语卡模板 (Speaking Card) - 风格统一设计
    # =========================================================
    speaking_css = """
    /* 可调节的字体大小变量 - 在 Anki 中可以修改这个值来缩放整个卡片 */
    :root {
        --base-font-size: 16px;  /* 修改这个值: 14px(小), 16px(默认), 18px(中), 20px(大), 24px(超大) */
        font-size: var(--base-font-size);
    }
    /* 继承基础卡片容器风格 */
    .card { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; font-size: var(--base-font-size); line-height: 1.6; color: #333; background-color: #f4f4f7; display: flex; justify-content: center; align-items: flex-start; height: 100%; margin: 0; padding: 20px; }
    
    /* 默认容器 */
    .main-container { background-color: #fff; width: 100%; max-width: 600px; border-radius: 16px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08); padding: 30px; text-align: center; box-sizing: border-box; }
    
    /* 宽屏响应式布局 - 仅针对背面 (.back-mode) */
    @media (min-width: 800px) {
        .main-container.back-mode {
            max-width: 1100px;
            display: flex;
            flex-direction: row;
            align-items: flex-start;
            gap: 40px;
        }
        
        .content-column {
            flex: 1;
            min-width: 0;
        }
        
        .translation-section {
            width: 320px;
            flex-shrink: 0;
            margin-top: 0 !important;
            padding-left: 40px;
            border-left: 1px solid #eee;
            position: sticky;
            top: 20px;
        }
        
        .divider.bottom-divider {
            display: none;
        }
        
        /* 宽屏下保留按钮，用户点击才显示中文释义 */
    }

    /* 正面：中文触发器 (风格类似原版 .word 但更醒目) */
    .trigger-cn { font-size: 2.4rem; font-weight: 700; color: #2d3436; margin: 40px 0 20px 0; line-height: 1.3; }
    .hint { font-size: 0.9rem; color: #b2bec3; margin-bottom: 20px; text-transform: uppercase; letter-spacing: 1px; font-weight: 600; }
    
    /* 背面：英文答案 (使用原版主色调) */
    .answer-en { font-size: 2.0rem; font-weight: 700; color: #0984e3; margin-bottom: 10px; }
    .speaking-ipa { color: #2d3436; font-size: 1.15rem; margin-top: 8px; font-family: 'Menlo', 'Monaco', 'Consolas', monospace; font-weight: 600; }
    .speaking-meaning-hint { color: #b2bec3; font-size: 0.95rem; margin-top: 5px; }
    .audio-label-text { color: #888; font-size: 0.8rem; }
    .example-text { color: #555; }
    .audio-bar { text-align: center; margin-top: 15px; margin-bottom: 25px; }
    hr.divider { border: 0; height: 1px; background: #eee; margin: 20px 0; }
    .section-title { font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px; font-weight: 600; color: #b2bec3; margin-bottom: 10px; display: flex; align-items: center; justify-content: center; gap: 8px; }
    
    /* 背面：时态例句框 (继承 .example-box 风格但用新颜色区分) */
    .tense-box { 
        background-color: #fbfbfb; 
        border-left: 4px solid #e84393;
        padding: 15px; 
        border-radius: 8px; 
        margin-top: 20px; 
        text-align: left; 
    }
    
    /* 时态标签 (新增元素) */
    .tense-tag { 
        display: inline-block; 
        padding: 2px 6px; 
        border-radius: 4px; 
        font-size: 0.75rem; 
        font-weight: bold; 
        color: white; 
        background-color: #b2bec3; 
        margin-right: 8px; 
        text-transform: uppercase; 
        vertical-align: middle;
    }
    .tag-past { background-color: #e17055; }   /* 橙色代表过去 */
    .tag-present { background-color: #00b894; } /* 绿色代表现在 */
    .tag-future { background-color: #0984e3; }  /* 蓝色代表未来 */
    
    .audio-tag { font-size: 0.8rem; color: #aaa; margin-top: 5px; }
    
    /* 中文释义按钮和内容区域 */
    .translation-section { margin-top: 20px; text-align: center; }
    .translation-btn {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 12px 24px;
        font-size: 0.95rem;
        font-weight: 600;
        border-radius: 8px;
        cursor: pointer;
        transition: all 0.3s;
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
    }
    .translation-btn:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(102, 126, 234, 0.4);
    }
    .translation-content {
        margin-top: 15px;
        padding: 20px;
        background-color: #fff9e6;
        border-radius: 12px;
        border-left: 4px solid #f39c12;
        text-align: left;
        animation: fadeIn 0.3s ease;
    }
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(-10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .translation-item {
        margin-bottom: 15px;
        line-height: 1.8;
    }
    .translation-label {
        font-weight: 700;
        color: #d35400;
        margin-right: 8px;
    }
    .translation-text {
        color: #555;
        white-space: pre-line;
    }
    
    /* 夜间模式 */
    .nightMode .card { background-color: #1e1e1e; color: #f5f6fa; }
    .nightMode .main-container { background-color: #2d2d2d; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4); }
    .nightMode .trigger-cn { color: #f5f6fa; }
    .nightMode .answer-en { color: #74b9ff; }
    .nightMode .speaking-ipa { color: #e0e0e0; }  /* 音标在夜间模式下使用亮灰色 */
    .nightMode .speaking-meaning-hint { color: #b0b0b0; }  /* 提示文字稍暗一点 */
    .nightMode .audio-label-text { color: #a0a0a0; }  /* 音频标签文字 */
    .nightMode .example-text { color: #d0d0d0; }  /* 例句文字使用亮灰色，确保可读性 */
    .nightMode hr.divider { background: #444; }
    .nightMode .tense-box { background-color: #333; border-left-color: #fd79a8; }
    .nightMode .translation-content {
        background-color: #2d2d44;
        border-left-color: #f39c12;
    }
    .nightMode .translation-label {
        color: #f39c12;
    }
    .nightMode .translation-text {
        color: #ccc;
    }
    /* 宽屏夜间模式适配 */
    @media (min-width: 800px) {
        .nightMode .translation-section {
            border-left-color: #444;
        }
    }
    """

    # 口语卡正面 - 极简主义
    speaking_front_html = """
    <div class="main-container">
        <div class="hint">🎯 Speaking Challenge</div>
        <div class="trigger-cn">{{MeaningCN}}</div>
        <div class="hint" style="margin-top: 30px; font-size: 0.8rem;">(Click to reveal English & Examples)</div>
    </div>
    """

    # 口语卡背面 - 信息流
    speaking_back_html = """
    <div class="main-container back-mode">
        <div class="content-column">
            <div class="hint">Answer</div>
            <div class="answer-en">{{WordEN}}</div>
            <div class="speaking-ipa">{{IPA}}</div>
            <div class="speaking-meaning-hint">{{MeaningCN}}</div>

            <div class="audio-bar" style="margin: 10px 0;">
                <span class="audio-label-text">Slow</span> {{AudioSlow}} 
                <span class="audio-label-text" style="margin-left:10px;">Fast</span> {{AudioFast}}
            </div>

            <hr class="divider">

            <div class="section-title"><span>🗣️ Tense Practice</span></div>

            <div class="tense-box">
                <div style="margin-bottom: 12px;">
                    <span class="tense-tag tag-past">Example 1</span> 
                    <span class="example-text">{{Example1}}</span> 
                    <div class="audio-tag">{{Example1Audio}}</div>
                </div>

                <div style="margin-bottom: 12px;">
                    <span class="tense-tag tag-present">Example 2</span> 
                    <span class="example-text">{{Example2}}</span> 
                    <div class="audio-tag">{{Example2Audio}}</div>
                </div>

                <div>
                    <span class="tense-tag tag-future">Example 3</span> 
                    <span class="example-text">{{Example3}}</span> 
                    <div class="audio-tag">{{Example3Audio}}</div>
                </div>
            </div>
            
            <hr class="divider bottom-divider">
        </div>
        
        <!-- 中文释义区域：内容在按钮上方 -->
        <div class="translation-section">
            <div id="translation-content" class="translation-content" style="display:none;">
                <div class="translation-item">
                    <span class="translation-label">例句翻译:</span>
                    <div class="translation-text">{{ExamplesCN}}</div>
                </div>
            </div>
            <button id="toggle-translation" class="translation-btn">显示中文释义 (C)</button>
        </div>
    </div>
    
    <script>
    // 中文释义切换功能
    (function() {
        var btn = document.getElementById('toggle-translation');
        var content = document.getElementById('translation-content');
        
        function toggleChinese() {
            if (content.style.display === 'none') {
                content.style.display = 'block';
                btn.textContent = '隐藏中文释义 (C)';
            } else {
                content.style.display = 'none';
                btn.textContent = '显示中文释义 (C)';
            }
        }
        
        if (btn && content) {
            btn.addEventListener('click', toggleChinese);
            
            // 快捷键 C 切换中文释义
            document.addEventListener('keydown', function(e) {
                if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
                if (e.key === 'c' || e.key === 'C') {
                    toggleChinese();
                }
            });
        }
    })();
    </script>
    """

    # =========================================================
    # 1.4 根据 card_types 创建 Model
    # =========================================================
    
    # 词汇卡/听写卡共享的字段定义
    shared_fields = [
        {'name': 'Word'},
        {'name': 'IPA'},
        {'name': 'WordAudio'},
        {'name': 'Definitions'},
        {'name': 'Examples'},
        {'name': 'MeaningAudio'},
        {'name': 'ExampleAudio'},
        {'name': 'WordCN'},          # 单词中文释义
        {'name': 'DefinitionsCN'},   # 定义中文释义
        {'name': 'ExamplesCN'},      # 例句中文释义
    ]
    
    # 口语卡的字段定义（不同的结构）
    speaking_fields = [
        {'name': 'MeaningCN'},      # 正面：中文意图
        {'name': 'WordEN'},          # 背面：英文短语
        {'name': 'IPA'},             # 背面：音标
        {'name': 'AudioSlow'},       # 背面：慢速音频
        {'name': 'AudioFast'},       # 背面：常速音频
        {'name': 'Example1'},        # 背面：例句1（Past）
        {'name': 'Example1Audio'},   # 背面：例句1音频
        {'name': 'Example2'},        # 背面：例句2（Present）
        {'name': 'Example2Audio'},   # 背面：例句2音频
        {'name': 'Example3'},        # 背面：例句3（Future）
        {'name': 'Example3Audio'},   # 背面：例句3音频
        {'name': 'ExamplesCN'},      # 背面：例句中文释义
    ]
    
    # 词汇卡 Model
    vocab_model = genanki.Model(
        1683920450,
        'Modern Auto Vocab',
        fields=shared_fields,
        templates=[
            {
                'name': 'Vocab Card',
                'qfmt': vocab_front_html + zoom_script,
                'afmt': vocab_back_html + zoom_script,
            },
        ],
        css=vocab_css
    )
    
    # 听写卡 Model
    dictation_model = genanki.Model(
        1683920451,
        'Dictation Card',
        fields=shared_fields,
        templates=[
            {
                'name': 'Dictation Card',
                'qfmt': dictation_front_html + zoom_script,
                'afmt': dictation_back_html + zoom_script,
            },
        ],
        css=dictation_css
    )
    
    # 口语卡 Model
    speaking_model = genanki.Model(
        1683920452,
        'Speaking Card',
        fields=speaking_fields,
        templates=[
            {
                'name': 'Speaking Card',
                'qfmt': speaking_front_html + zoom_script,
                'afmt': speaking_back_html + zoom_script,
            },
        ],
        css=speaking_css
    )
    
    # 选择要使用的模型（支持旧版 card_type 和新版 card_types）
    models_to_use = []
    
    # 兼容处理：如果传入的是旧版字符串参数，转换为列表
    if isinstance(card_type, str):
        if card_type == "both":
            card_types_list = ["vocab", "dictation"]
        else:
            card_types_list = [card_type]
    else:
        # 新版：直接使用列表
        card_types_list = card_type if isinstance(card_type, list) else ["vocab"]
    
    # 根据列表构建 models_to_use
    if "vocab" in card_types_list:
        models_to_use.append(("vocab", vocab_model))
    if "dictation" in card_types_list:
        models_to_use.append(("dictation", dictation_model))
    if "speaking" in card_types_list:
        models_to_use.append(("speaking", speaking_model))
    
    # 如果没有任何有效类型，使用默认词汇卡
    if not models_to_use:
        print(f"⚠️ 未知的卡片类型，使用默认词汇卡")
        models_to_use = [("vocab", vocab_model)]
    
    print(f"📝 卡片类型: {', '.join([t for t, _ in models_to_use])}")

    # =========================================================
    # 2. 创建 Deck(s)
    # =========================================================
    import random
    decks = {}
    for model_type, model in models_to_use:
        if model_type == "vocab":
            # 使用随机 ID，让 Anki 导入时提示选择牌组
            deck_id = random.randrange(1 << 30, 1 << 31)
            d_name = deck_name
        elif model_type == "dictation":
            deck_id = random.randrange(1 << 30, 1 << 31)
            d_name = f"{deck_name} - 听写"
        elif model_type == "speaking":
            deck_id = random.randrange(1 << 30, 1 << 31)
            d_name = f"{deck_name} - 口语"
        decks[model_type] = genanki.Deck(deck_id, d_name)

    all_media_files = []

    # =========================================================
    # 3. 批量处理（并行模式：N张卡片并发处理 + 重试机制 + 进度条）
    # =========================================================
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from threading import Lock
    import time
    from tqdm import tqdm
    
    print(f"🚀 开始制作卡组，共 {len(word_list)} 个单词...")
    print(f"⚡ 并行处理模式：最多 {max_workers} 张卡片同时生成")
    print(f"🔄 重试机制：失败后最多重试 {max_retries} 次，间隔 {retry_delay} 秒\n")
    
    # 用于线程安全的锁
    media_lock = Lock()
    deck_lock = Lock()
    
    # 辅助函数：将音频路径转换为 Anki 标签（线程安全版）
    def get_sound_tag(audio_paths, key):
        path = audio_paths.get(key)
        if path and os.path.exists(path):
            with media_lock:
                all_media_files.append(path)
            return f"[sound:{os.path.basename(path)}]"
        return ""
    
    # 定义单个单词的处理函数
    def process_single_word(word_input, index, total, pbar=None):
        """处理单个单词，返回生成的 notes"""
        result = {
            'word_input': word_input,
            'index': index,
            'notes': {},  # {model_type: note}
            'success': False,
            'error': None
        }
        
        try:
            # ==========================================
            # 路径 A: 处理 vocab/dictation 卡
            # ==========================================
            if "vocab" in card_types_list or "dictation" in card_types_list:
                # Step A1: LLM 生成（现在是 JSON 模式，一次请求）
                text_data = generate_word_card(word_input, api_config=api_config)
                
                # Step A2: TTS 生成
                audio_paths = generate_audio_files(text_data, output_dir=media_output_dir, 
                                                 speed_config=speed_config, azure_config=azure_config)
                
                # 检查所有必需音频是否生成成功
                required_audio = ['word_slow', 'word_fast', 'definitions', 'examples']
                missing_audio = [key for key in required_audio if not audio_paths or not audio_paths.get(key)]
                
                if missing_audio:
                    raise RuntimeError(f"音频生成失败: {word_input}，缺失音频: {', '.join(missing_audio)}")
                
                # Step A3: 拼接单词音频 (先慢后快)
                combined_word_audio = get_sound_tag(audio_paths, 'word_slow') + " " + get_sound_tag(audio_paths, 'word_fast')

                # Step A4: 为 vocab/dictation 创建笔记（使用稳定 GUID）
                for model_type, model in models_to_use:
                    if model_type in ["vocab", "dictation"]:
                        note = StableGUIDNote(
                            model=model,
                            fields=[
                                text_data['word'],
                                text_data['ipa'],
                                combined_word_audio,
                                text_data['definitions'].strip(),
                                text_data['examples'].strip(),
                                get_sound_tag(audio_paths, 'definitions'),
                                get_sound_tag(audio_paths, 'examples'),
                                text_data.get('word_cn', ''),          # 单词中文释义
                                text_data.get('definitions_cn', ''),   # 定义中文释义
                                text_data.get('examples_cn', '')       # 例句中文释义
                            ]
                        )
                        result['notes'][model_type] = note

            # ==========================================
            # 路径 B: 处理 speaking 卡
            # ==========================================
            if "speaking" in card_types_list:
                # Step B1: LLM 生成（使用 speaking 专用函数）
                speaking_data = get_speaking_data(word_input, api_config=api_config)
                
                # Step B2: TTS 生成（使用 speaking 专用函数）
                speaking_audio_paths = get_speaking_audio(speaking_data, output_dir=media_output_dir, 
                                                        speed_config=speed_config, azure_config=azure_config)
                
                # 检查所有必需音频是否生成成功
                required_speaking_audio = ['word_slow', 'word_fast', 'example_1', 'example_2', 'example_3']
                missing_speaking_audio = [key for key in required_speaking_audio if not speaking_audio_paths or not speaking_audio_paths.get(key)]
                
                if missing_speaking_audio:
                    raise RuntimeError(f"口语卡音频生成失败: {word_input}，缺失音频: {', '.join(missing_speaking_audio)}")
                
                # Step B3: 为 speaking 创建笔记（使用稳定 GUID）
                # 注意：speaking 卡片使用 word_en（索引1）作为 GUID 基础
                for model_type, model in models_to_use:
                    if model_type == "speaking":
                        # 将中文例句列表转换为换行分隔的字符串
                        examples_cn_text = '\n'.join(speaking_data.get('examples_cn', ['', '', '']))
                        
                        fields = [
                            speaking_data['meaning_cn'],                          # MeaningCN (索引0)
                            speaking_data['word_en'],                             # WordEN (索引1, 用于GUID)
                            speaking_data.get('ipa', ''),                         # IPA
                            get_sound_tag(speaking_audio_paths, 'word_slow'),     # AudioSlow
                            get_sound_tag(speaking_audio_paths, 'word_fast'),     # AudioFast
                            speaking_data['examples'][0] if len(speaking_data['examples']) > 0 else '',  # Example1
                            get_sound_tag(speaking_audio_paths, 'example_1'),     # Example1Audio
                            speaking_data['examples'][1] if len(speaking_data['examples']) > 1 else '',  # Example2
                            get_sound_tag(speaking_audio_paths, 'example_2'),     # Example2Audio
                            speaking_data['examples'][2] if len(speaking_data['examples']) > 2 else '',  # Example3
                            get_sound_tag(speaking_audio_paths, 'example_3'),     # Example3Audio
                            examples_cn_text                                       # ExamplesCN
                        ]
                        note = StableGUIDNote(model=model, fields=fields, guid_field_index=1)
                        result['notes'][model_type] = note
            
            result['success'] = True

        except Exception as e:
            result['error'] = str(e)
            # 使用 tqdm.write 输出错误，避免破坏进度条
            if pbar:
                pbar.write(f"   [{index}] ❌ 处理失败: {word_input} - {e}")
            else:
                print(f"   [{index}] ❌ 处理失败: {word_input} - {e}")
            import traceback
            import sys
            # 将详细错误信息输出到 stderr
            traceback.print_exc(file=sys.stderr)
        
        return result
    
    # 定义带重试逻辑的包装函数
    def process_with_retry(word_input, index, total, pbar=None):
        """带重试逻辑的处理函数"""
        last_error = None
        
        for attempt in range(1, max_retries + 1):
            try:
                result = process_single_word(word_input, index, total, pbar)
                
                # 如果成功，直接返回
                if result['success']:
                    return result
                
                # 如果失败但还有重试次数
                if attempt < max_retries:
                    msg = f"   [{index}] ⚠️ {word_input} 尝试 {attempt}/{max_retries} 失败，{retry_delay}秒后重试..."
                    if pbar:
                        pbar.write(msg)
                    else:
                        print(msg)
                    time.sleep(retry_delay)
                else:
                    msg = f"   [{index}] ❌ {word_input} 已达到最大重试次数 ({max_retries})"
                    if pbar:
                        pbar.write(msg)
                    else:
                        print(msg)
                    return result
                    
            except Exception as e:
                last_error = str(e)
                if attempt < max_retries:
                    msg = f"   [{index}] ⚠️ {word_input} 尝试 {attempt}/{max_retries} 异常，{retry_delay}秒后重试: {e}"
                    if pbar:
                        pbar.write(msg)
                    else:
                        print(msg)
                    time.sleep(retry_delay)
                else:
                    msg = f"   [{index}] ❌ {word_input} 已达到最大重试次数 ({max_retries}): {e}"
                    if pbar:
                        pbar.write(msg)
                    else:
                        print(msg)
                    return {
                        'word_input': word_input,
                        'index': index,
                        'notes': {},
                        'success': False,
                        'error': last_error
                    }
        
        # 不应该到达这里，但以防万一
        return {
            'word_input': word_input,
            'index': index,
            'notes': {},
            'success': False,
            'error': last_error or 'Unknown error'
        }
    
    # 使用 ThreadPoolExecutor 并行处理（带进度条）
    failed_words = []  # 记录失败的单词（提升到外层作用域）
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 创建进度条
        with tqdm(total=len(word_list), desc="制卡进度", 
                 bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]',
                 ncols=100) as pbar:
            
            # 提交所有任务（使用带重试的包装函数）
            futures = {
                executor.submit(process_with_retry, word, i, len(word_list), pbar): (word, i)
                for i, word in enumerate(word_list, 1)
            }
            
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result['success'] and result['notes']:
                        # 使用线程锁安全地添加 notes 到 decks
                        with deck_lock:
                            for model_type, note in result['notes'].items():
                                decks[model_type].add_note(note)
                        # 成功时显示简短信息
                        pbar.write(f"✅ [{result['index']}] {result['word_input']}")
                    elif not result['success']:
                        # 记录失败的单词
                        failed_words.append({
                            'word': result['word_input'],
                            'index': result['index'],
                            'error': result.get('error', 'Unknown error')
                        })
                except Exception as e:
                    pbar.write(f"❌ 收集结果时出错: {e}")
                finally:
                    # 更新进度条
                    pbar.update(1)
        
        # 显示失败统计
        if failed_words:
            print("\n" + "=" * 70)
            print(f"⚠️ 有 {len(failed_words)} 个单词制作失败（已重试 {max_retries} 次）:")
            print("=" * 70)
            for item in failed_words:
                print(f"  [{item['index']}] {item['word']} - {item['error']}")
            print("=" * 70)

    # =========================================================
    # 4. 打包
    # =========================================================
    total_notes = sum(len(deck.notes) for deck in decks.values())
    if total_notes == 0:
        print("\n❌ 无卡片生成。")
        return

    print(f"\n📦 正在打包 {len(all_media_files)} 个媒体文件...")
    
    # 创建包含所有卡组的包
    all_decks = list(decks.values())
    my_package = genanki.Package(all_decks)
    my_package.media_files = all_media_files
    
    my_package.write_to_file(package_name)
    print(f"🎉 生成完毕: {os.path.abspath(package_name)}")
    print(f"📊 共生成 {total_notes} 张卡片 ({len(all_decks)} 个卡组)")
    print("👉 请双击该文件导入 Anki！")
    
    # =========================================================
    # 5. 保存失败单词日志
    # =========================================================
    if failed_words:
        try:
            with open(error_log_file, 'w', encoding='utf-8') as f:
                for item in failed_words:
                    f.write(f"{item['word']}\n")
            print(f"\n📝 失败单词已记录到: {os.path.abspath(error_log_file)}")
            print(f"   共 {len(failed_words)} 个单词，可稍后重新处理")
        except Exception as e:
            print(f"⚠️ 失败单词日志保存失败: {e}")
    else:
        # 如果没有失败单词，删除旧的错误日志文件（如果存在）
        if os.path.exists(error_log_file):
            try:
                os.remove(error_log_file)
                print("\n✅ 所有单词处理成功，旧错误日志已清理")
            except Exception as e:
                print(f"⚠️ 错误日志清理失败: {e}")
    
# ==========================================
# 调用示例
# ==========================================
# ==============================================================================
# 联动测试代码
# 假设你的两个函数 generate_word_card 和 generate_audio_files 都在当前脚本中定义好了
# ==============================================================================

if __name__ == "__main__":
    # 1. 准备测试列表：覆盖多义词、短语、单义词等不同情况
    test_inputs = [
        "tear (crying)",        # 测试语境优先 + 多音多义词 (Heteronym)
        "hold on",              # 测试动词短语 (Phrasal Verb)
        "content (happy)",      # 测试另一个多音多义词
        "kangaroo"              # 测试单义词
    ]

    # 2. 定义你喜欢的语速配置
    my_speed_settings = {
        "word_slow": "-35%",    # 单词读得再慢一点
        "word_fast": "0%",      # 单词常速
        "definitions": "0%",    # 释义常速
        "examples": "-10%"      # 例句稍微慢一点点，方便听清结构
    }

    # 3. 指定输出文件夹
    media_dir = "anki_media_output"

    print(f"🚀 开始批量制卡任务，共 {len(test_inputs)} 个目标...\n")
    print("-" * 60)

    for i, input_text in enumerate(test_inputs, 1):
        print(f"📍 [{i}/{len(test_inputs)}] 正在处理输入: '{input_text}'")

        try:
            # -------------------------------------------
            # 第一步：调用大模型生成文本内容 (LLM)
            # -------------------------------------------
            print("   [Step 1] 正在请求 AI 生成文本内容...")
            card_data = generate_word_card(input_text)
            
            # 简单展示一下生成了什么
            print(f"      -> 单词: {card_data['word']}")
            print(f"      -> 音标: {card_data['ipa']}")
            print(f"      -> 释义行数: {len(card_data['definitions'].splitlines())}")

            # -------------------------------------------
            # 第二步：调用 Azure 生成语音文件 (TTS)
            # -------------------------------------------
            print("   [Step 2] 正在请求 Azure 生成语音 (应用自定义语速)...")
            audio_paths = generate_audio_files(
                word_card=card_data,
                output_dir=media_dir,
                speed_config=my_speed_settings
            )

            # -------------------------------------------
            # 第三步：结果汇总
            # -------------------------------------------
            print("   ✅ 处理成功！生成素材如下:")
            if audio_paths:
                print(f"      🎵 慢速单词: {audio_paths.get('word_slow')}")
                print(f"      🎵 快速单词: {audio_paths.get('word_fast')}")
                print(f"      🎵 释义朗读: {audio_paths.get('definitions')}")
                print(f"      🎵 例句朗读: {audio_paths.get('examples')}")
            else:
                print("      ⚠️ 未生成音频 (可能 Key 错误或额度不足)")

        except Exception as e:
            print(f"   ❌ 当前条目处理失败: {e}")
            # 这里打印详细错误堆栈，方便你排查是 LLM 挂了还是 Azure 挂了
            import traceback
            traceback.print_exc()

        print("-" * 60)

    print(f"\n🎉 所有任务结束。请检查文件夹: {os.path.abspath(media_dir)}")