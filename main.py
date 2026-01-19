#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Anki 自动制卡主程序
从配置文件读取参数，从 txt 文件批量读取单词，自动生成 Anki 卡组
"""

import os
import sys
import yaml
import shutil
import genanki
import certifi

# 修复 conda 环境的 SSL 证书路径问题
os.environ['SSL_CERT_FILE'] = certifi.where()

from generate import create_anki_package


def load_config(config_path="config.yaml"):
    """
    加载配置文件
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        dict: 配置字典
    """
    if not os.path.exists(config_path):
        print(f"❌ 配置文件不存在: {config_path}")
        print("请创建 config.yaml 文件")
        sys.exit(1)
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        print(f"✅ 成功加载配置文件: {config_path}")
        return config
    except Exception as e:
        print(f"❌ 读取配置文件失败: {e}")
        sys.exit(1)


def load_word_list(txt_path):
    """
    从 txt 文件读取单词列表
    
    Args:
        txt_path: txt 文件路径，每行一个单词或词组
        
    Returns:
        list: 单词列表
    """
    if not os.path.exists(txt_path):
        print(f"❌ 单词列表文件不存在: {txt_path}")
        sys.exit(1)
    
    try:
        with open(txt_path, 'r', encoding='utf-8') as f:
            # 读取所有行，去除空白行和首尾空格
            words = [line.strip() for line in f.readlines() if line.strip()]
        
        print(f"✅ 成功加载单词列表: {txt_path}")
        print(f"📝 共读取 {len(words)} 个单词/词组")
        return words
    except Exception as e:
        print(f"❌ 读取单词列表失败: {e}")
        sys.exit(1)


def clean_temp_files(temp_dir):
    """
    删除临时音频文件目录
    
    Args:
        temp_dir: 临时目录路径
    """
    if os.path.exists(temp_dir):
        try:
            shutil.rmtree(temp_dir)
            print(f"🧹 已清理临时文件目录: {temp_dir}")
        except Exception as e:
            print(f"⚠️ 清理临时文件失败: {e}")
    else:
        print(f"ℹ️ 临时目录不存在，无需清理: {temp_dir}")


def main():
    """
    主函数
    """
    print("=" * 70)
    print("🚀 Anki 自动制卡程序启动")
    print("=" * 70)
    print()
    
    # 1. 加载配置文件
    config = load_config("config.yaml")
    
    # 2. 提取配置信息
    api_config = {
        "base_url": config['api_keys']['openai_base_url'],
        "api_key": config['api_keys']['openai_api_key'],
        "model_name": config['api_keys']['openai_model']
    }
    
    azure_config = {
        "speech_key": config['api_keys']['azure_speech_key'],
        "region": config['api_keys']['azure_region'],
        "voice_name": config['api_keys']['azure_voice_name']
    }
    
    speed_config = config['speed_config']
    
    input_txt = config['paths']['input_txt']
    output_package = config['paths']['output_package']
    temp_media_dir = config['paths']['temp_media_dir']
    deck_name = config['anki']['deck_name']
    
    # 3. 加载单词列表
    word_list = load_word_list(input_txt)
    
    if not word_list:
        print("❌ 单词列表为空，程序退出")
        sys.exit(1)
    
    print()
    print("=" * 70)
    print("📚 开始批量制卡")
    print("=" * 70)
    print()
    
    # 4. 调用制卡函数
    try:
        create_anki_package(
            word_list=word_list,
            package_name=output_package,
            media_output_dir=temp_media_dir,
            api_config=api_config,
            azure_config=azure_config,
            speed_config=speed_config,
            deck_name=deck_name
        )
        
        print()
        print("=" * 70)
        print("🎉 制卡完成！")
        print("=" * 70)
        print(f"📦 输出文件: {os.path.abspath(output_package)}")
        print("👉 请双击该文件导入到 Anki")
        
    except Exception as e:
        print()
        print("=" * 70)
        print(f"❌ 制卡过程出错: {e}")
        print("=" * 70)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    finally:
        # 5. 清理临时文件（无论成功失败都执行）
        print()
        print("=" * 70)
        print("🧹 清理临时文件")
        print("=" * 70)
        clean_temp_files(temp_media_dir)
    
    print()
    print("=" * 70)
    print("✨ 程序执行完毕")
    print("=" * 70)


if __name__ == "__main__":
    main()
