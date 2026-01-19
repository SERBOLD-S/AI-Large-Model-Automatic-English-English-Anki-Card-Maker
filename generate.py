import os
import re
from openai import OpenAI
import azure.cognitiveservices.speech as speechsdk
import genanki

def generate_word_card(input_text: str, api_config: dict = None) -> dict:
    """
    输入一个单词或词组（可能包含上下文括号），通过 API 调用生成音标、释义和例句。
    
    Args:
        input_text (str): 用户输入的单词，例如 "tear (crying)" 或 "bank"
        api_config (dict, optional): API 配置字典，包含 base_url, api_key, model_name
        
    Returns:
        dict: 包含清洗后的单词、音标、释义列表字符串、例句列表字符串
    """
    
    # 1. 初始化客户端 (使用配置或默认值)
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
    
    # 模型名称
    MODEL_NAME = api_config.get("model_name", "deepseek-v3-2-251201")

    # 2. 辅助函数：处理括号，获取纯单词
    # 正则匹配中文括号 （） 或英文括号 () 及其内部内容，并去除
    cleaned_word = re.sub(r'[\(\uff08].*?[\)\uff09]', '', input_text).strip()

    # 3. 辅助函数：通用 API 调用
    def get_completion(system_prompt, user_content):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.1, # 降低随机性，保证输出格式稳定
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"API调用出错: {e}")
            return "Error generating content"

    # ==========================================
    # 步骤 1: 获取音标 (IPA)
    # ==========================================
    ipa_prompt = """
You are an expert phonetician specializing in British English pronunciation.
Your task is to provide the International Phonetic Alphabet (IPA) transcription for the input text.

**Rules:**
1.  **Input format:** The input may be a single word, a phrase/idiom, or a word/phrase followed by a context in parentheses.
2.  **Phrases:** If the input is a phrase (e.g., "give up"), provide the IPA for each word in the phrase, separated by spaces.
3.  **Context:** If parentheses are present, use them to determine pronunciation (e.g., tear), but DO NOT transcribe the content inside parentheses.
4.  **Constraints:** Output ONLY the IPA symbols. No labels, no explanations.

**Examples:**

Input: apple
Output: /ˈæpl/

Input: look forward to
Output: /lʊk ˈfɔːwəd tu/

Input: a piece of cake
Output: /ə piːs əv keɪk/

Input: tear (crying)
Output: /tɪə/

Input: tear (rip paper)
Output: /teə/

Input: present (gift)
Output: /ˈpreznt/
"""
    # 注意：Prompts 里的 {{INPUT}} 在这里通过 user message 传递，或者直接 f-string 替换
    # 这里我们选择将 system prompt 保持静态，用户输入作为 user message 传入，效果更佳
    
    ipa_result = get_completion(ipa_prompt, f"Input: {input_text}")
    # 有时候模型会重复 "Output: " 前缀，这里做一个简单的清洗
    ipa_result = ipa_result.replace("Output:", "").strip()

    # ==========================================
    # 步骤 2: 获取释义 (Definitions)
    # ==========================================
    def_prompt = """
You are an expert English Dictionary assistant.
Your task is to provide clear, numbered English definitions for the input.

**Rules:**
1.  **Analyze Input Type:**
    * **Single Word:** Provide the most common, high-frequency meanings.
    * **Phrase / Idiom:** If the input is a phrase (e.g., "look after", "piece of cake"), define the **idiomatic meaning of the whole phrase**, NOT the individual words.

2.  **Frequency Judgement:**
    * If a word/phrase has only **one** common meaning (e.g., "kangaroo"), output **ONLY** that one definition.
    * If a word has **multiple** common meanings (e.g., "bank", "tear"), provide 2-3 definitions.

3.  **Handling Context (Parentheses) - PRIORITY RULE:**
    * If parentheses are present (e.g., "tear (crying)"), they determine the **ORDER**, not the exclusion.
    * **Definition 1** MUST be the specific meaning described in the parentheses.
    * **Definition 2, 3...** MUST list other high-frequency meanings of the word, **even if they have different pronunciations (heteronyms)**. Do not omit other common meanings.

4.  **Format:** Always use a numbered list (1., 2....).

**Examples:**

Input: kangaroo
Output:
1. A large Australian animal with a strong tail and back legs, which moves by jumping.

Input: give up
Output:
1. To stop doing or having something (often a habit).
2. To stop trying to guess or solve something.

Input: once in a blue moon
Output:
1. Very rarely.

Input: bank
Output:
1. An organization where people and businesses can invest or borrow money.
2. The land alongside or sloping down to a river or lake.

Input: date (fruit)
Output:
1. A sweet, dark brown oval fruit containing a hard stone.
2. A particular day of the month or year.
3. A romantic meeting or social engagement.

Input: tear (crying)
Output:
1. A drop of clear salty liquid secreted by glands in your eyes.
2. To pull or rip something apart or to pieces with force.
"""
    definitions_result = get_completion(def_prompt, f"Input: {input_text}")
    definitions_result = definitions_result.replace("Output:", "").strip()

    # ==========================================
    # 步骤 3: 获取例句 (Examples)
    # ==========================================
    # 这一步依赖于【清洗后的单词】和【上一步生成的释义】
    
    ex_prompt = """
You are an English teacher.
Your task is to write example sentences corresponding to a provided list of numbered definitions.

**Rules:**
1.  **Input:** You will receive a target Word/Phrase and a Numbered List of Definitions.
2.  **Output Format:** Provide a numbered list of example sentences that strictly matches the order and quantity of the provided definitions.
3.  **Content:**
    * The sentence must clearly illustrate the specific meaning of that definition.
    * **Phrases:** If the input is a phrase, the sentence must include the phrase naturally.
    * Keep the sentences natural and suitable for an English learner.

**Examples:**

Input Word: kangaroo
Input Definitions:
1. A large Australian animal with a strong tail and back legs, which moves by jumping.

Output:
1. We saw a kangaroo jumping across the field during our trip to Australia.

Input Word: give up
Input Definitions:
1. To stop doing or having something (often a habit).
2. To stop trying to guess or solve something.

Output:
1. I decided to give up smoking last year for my health.
2. I give up; tell me the answer to the riddle.

Input Word: bank
Input Definitions:
1. An organization where people and businesses can invest or borrow money.
2. The land alongside or sloping down to a river or lake.

Output:
1. I need to stop by the bank to withdraw some cash.
2. They sat on the river bank and fished all afternoon.
"""
    
    # 构建 Step 3 的用户输入
    step3_user_input = f"""**Current Input Word:**
{cleaned_word}

**Current Input Definitions:**
{definitions_result}"""

    examples_result = get_completion(ex_prompt, step3_user_input)
    examples_result = examples_result.replace("Output:", "").strip()

    # ==========================================
    # 构造返回值
    # ==========================================
    return {
        "word": cleaned_word,
        "ipa": ipa_result,
        "definitions": definitions_result,
        "examples": examples_result
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
        os.makedirs(output_dir)

    # 3. 初始化 Azure 合成器
    speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)
    voice_name = azure_config.get("voice_name", "en-GB-SoniaNeural")
    speech_config.speech_synthesis_voice_name = voice_name

    # 4. 定义辅助函数：执行合成并保存文件
    def synthesize_ssml_to_file(ssml_text, filename):
        file_path = os.path.join(output_dir, filename)
        audio_config = speechsdk.audio.AudioOutputConfig(filename=file_path)
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)
        
        result = synthesizer.speak_ssml_async(ssml_text).get()
        
        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            print(f"✅ 生成成功: {filename}")
            return file_path
        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation_details = result.cancellation_details
            print(f"❌ 生成取消: {filename}, 原因: {cancellation_details.reason}")
            if cancellation_details.reason == speechsdk.CancellationReason.Error:
                print(f"错误详情: {cancellation_details.error_details}")
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


def create_anki_package(word_list: list, package_name="My_Vocabulary_Deck.apkg", media_output_dir="media_temp", 
                       api_config=None, azure_config=None, speed_config=None, deck_name="new words deck"):
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
    """

    # =========================================================
    # 1. 定义 Anki 模板 (Modern Typography Style - 最终完美版)
    # =========================================================
    
    modern_css = """
    .card { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; font-size: 16px; line-height: 1.6; color: #333; background-color: #f4f4f7; display: flex; justify-content: center; align-items: flex-start; height: 100%; margin: 0; padding: 20px; }
    .main-container { background-color: #fff; width: 100%; max-width: 600px; border-radius: 16px; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08); padding: 30px; text-align: left; box-sizing: border-box; }
    .word-header { text-align: center; margin-bottom: 10px; }
    .word { font-size: 2.8rem; font-weight: 700; color: #2d3436; letter-spacing: -0.5px; margin-bottom: 5px; }
    .ipa { font-family: "Menlo", "Monaco", "Consolas", monospace; font-size: 1.1rem; color: #888; background-color: #f0f0f0; padding: 2px 8px; border-radius: 6px; display: inline-block; }
    .audio-bar { text-align: center; margin-top: 15px; margin-bottom: 25px; }
    hr.divider { border: 0; height: 1px; background: #eee; margin: 20px 0; }
    .section-title { font-size: 0.8rem; text-transform: uppercase; letter-spacing: 1px; font-weight: 600; color: #b2bec3; margin-bottom: 10px; display: flex; align-items: center; gap: 8px; }
    
    /* 【修复点 1】white-space 改为 pre-line
       pre-wrap 会把代码里的缩进也显示出来，导致前面空两格。
       pre-line 会合并空白，但保留换行符，完美解决问题。
    */
    .content-box { padding: 12px 10px; border-radius: 8px; margin-bottom: 20px; white-space: pre-line; }

    /* 【修复点 2】字号已放大 1.3 倍 */
    .definition-box { background-color: #fbfbfb; border-left: 4px solid #0984e3; font-size: 1.45rem; color: #2d3436; }
    .example-box { background-color: #fbfbfb; border-left: 4px solid #00b894; font-size: 1.3rem; color: #555; font-style: italic; }
    
    .audio-tag { font-size: 0.8rem; color: #aaa; margin-top: 8px; text-align: right; display: flex; justify-content: flex-end; align-items: center; gap: 5px; }
    
    /* 夜间模式 */
    .nightMode .card { background-color: #1e1e1e; color: #f5f6fa; }
    .nightMode .main-container { background-color: #2d2d2d; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4); }
    .nightMode .word { color: #f5f6fa; }
    .nightMode .ipa { background-color: #383838; color: #bbb; }
    .nightMode hr.divider { background: #444; }
    .nightMode .definition-box { background-color: #333; border-left-color: #74b9ff; color: #eee; }
    .nightMode .example-box { background-color: #333; border-left-color: #55efc4; color: #ccc; }
    """

    # 正面 HTML (保持代码整洁)
    front_html = """
    <div class="main-container">
        <div class="word-header">
            <div class="word">{{Word}}</div>
            <div class="ipa">{{IPA}}</div>
        </div>
        <div class="audio-bar">{{WordAudio}}</div>
    </div>
    """

    # 背面 HTML
    # 【修复点 3】这里我把 {{Definitions}} 紧紧贴在 class="..." 后面，物理上消除空格
    back_html = """
    <div class="main-container">
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
    </div>
    """

    # 定义 Model (固定ID)
    model_id = 1683920450
    
    my_model = genanki.Model(
        model_id,
        'Modern Auto Vocab',
        fields=[
            {'name': 'Word'},
            {'name': 'IPA'},
            {'name': 'WordAudio'},
            {'name': 'Definitions'},
            {'name': 'Examples'},
            {'name': 'MeaningAudio'},
            {'name': 'ExampleAudio'},
        ],
        templates=[
            {
                'name': 'Card 1',
                'qfmt': front_html,
                'afmt': back_html,
            },
        ],
        css=modern_css
    )

    # =========================================================
    # 2. 创建 Deck
    # =========================================================
    deck_id = 2059400110
    my_deck = genanki.Deck(deck_id, deck_name)

    all_media_files = []

    # =========================================================
    # 3. 批量处理
    # =========================================================
    print(f"🚀 开始制作卡组，共 {len(word_list)} 个单词...")
    
    for i, word_input in enumerate(word_list, 1):
        print(f"\n[{i}/{len(word_list)}] 正在处理: {word_input}")
        
        try:
            # Step A: LLM 生成
            text_data = generate_word_card(word_input, api_config=api_config)
            
            # Step B: TTS 生成
            audio_paths = generate_audio_files(text_data, output_dir=media_output_dir, 
                                             speed_config=speed_config, azure_config=azure_config)
            
            if not audio_paths:
                print("   ⚠️ 音频生成失败，跳过。")
                continue

            # Step C: 准备数据
            def get_sound_tag(key):
                path = audio_paths.get(key)
                if path and os.path.exists(path):
                    all_media_files.append(path)
                    return f"[sound:{os.path.basename(path)}]"
                return ""

            # 拼接单词音频 (先慢后快)
            combined_word_audio = get_sound_tag('word_slow') + " " + get_sound_tag('word_fast')

            # 填充字段 (使用 strip 去除数据本身的空格)
            note = genanki.Note(
                model=my_model,
                fields=[
                    text_data['word'],
                    text_data['ipa'],
                    combined_word_audio,
                    text_data['definitions'].strip(),
                    text_data['examples'].strip(),
                    get_sound_tag('definitions'),
                    get_sound_tag('examples')
                ]
            )
            
            my_deck.add_note(note)
            print(f"   ✅ 添加成功: {text_data['word']}")

        except Exception as e:
            print(f"   ❌ 处理失败: {e}")
            import traceback
            traceback.print_exc()

    # =========================================================
    # 4. 打包
    # =========================================================
    if len(my_deck.notes) == 0:
        print("\n❌ 无卡片生成。")
        return

    print(f"\n📦 正在打包 {len(all_media_files)} 个媒体文件...")
    
    my_package = genanki.Package(my_deck)
    my_package.media_files = all_media_files
    
    my_package.write_to_file(package_name)
    print(f"🎉 生成完毕: {os.path.abspath(package_name)}")
    print("👉 请双击该文件导入 Anki！")

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