#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Zeabur启动脚本 - 提供更好的日志输出
"""
import os
import sys
import time

# 强制无缓冲输出
os.environ['PYTHONUNBUFFERED'] = '1'
sys.stdout.reconfigure(line_buffering=True) if hasattr(sys.stdout, 'reconfigure') else None

print("=" * 60, flush=True)
print("ZEABUR STARTUP SCRIPT", flush=True)
print("=" * 60, flush=True)
print(f"Python Version: {sys.version}", flush=True)
print(f"Python Executable: {sys.executable}", flush=True)
print(f"Current Directory: {os.getcwd()}", flush=True)
print(f"Files in directory:", flush=True)
for file in os.listdir('.'):
    print(f"  - {file}", flush=True)
print("=" * 60, flush=True)

# 检查环境变量
env_vars = {
    'DISCORD_TOKEN': os.getenv('DISCORD_TOKEN'),
    'NAI_API_KEY': os.getenv('NAI_API_KEY'),
    'ZEABUR': os.getenv('ZEABUR'),
    'PORT': os.getenv('PORT'),
    'PYTHONUNBUFFERED': os.getenv('PYTHONUNBUFFERED')
}

print("Environment Variables:", flush=True)
for key, value in env_vars.items():
    if key in ['DISCORD_TOKEN', 'NAI_API_KEY']:
        # 隐藏敏感信息
        display = '***' + value[-4:] if value and len(value) > 4 else 'NOT SET'
        print(f"  {key}: {display}", flush=True)
    else:
        print(f"  {key}: {value or 'NOT SET'}", flush=True)

print("=" * 60, flush=True)

# 检查必需的环境变量
missing = []
if not env_vars['DISCORD_TOKEN']:
    missing.append('DISCORD_TOKEN')
if not env_vars['NAI_API_KEY']:
    missing.append('NAI_API_KEY')

if missing:
    print(f"❌ ERROR: Missing required environment variables: {', '.join(missing)}", flush=True)
    print("Please configure these in Zeabur dashboard", flush=True)
    print("Keeping process alive for debugging...", flush=True)

    while True:
        time.sleep(30)
        print(f"Still waiting for: {', '.join(missing)}", flush=True)
else:
    print("✓ All required environment variables are set", flush=True)
    print("Starting main.py...", flush=True)
    print("=" * 60, flush=True)

    try:
        # 导入并运行主程序
        import subprocess
        import sys
        result = subprocess.run([sys.executable, 'main.py'], capture_output=False, text=True)
        sys.exit(result.returncode)
    except ImportError as e:
        print(f"❌ Failed to import main.py: {e}", flush=True)
        import traceback
        traceback.print_exc()

        # 保持进程运行以便查看错误
        while True:
            time.sleep(60)
            print("Process kept alive for debugging...", flush=True)
    except Exception as e:
        print(f"❌ Error starting bot: {e}", flush=True)
        import traceback
        traceback.print_exc()

        # 保持进程运行以便查看错误
        while True:
            time.sleep(60)
            print("Process kept alive for debugging...", flush=True)