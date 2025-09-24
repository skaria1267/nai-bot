# -*- coding: utf-8 -*-
import os
import sys

# 确保输出不被缓冲
os.environ['PYTHONUNBUFFERED'] = '1'
import json
import random
import io
import zipfile
from typing import Dict, Optional, Any
from collections import deque
import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
from dotenv import load_dotenv
from utils import load_presets, save_presets, load_user_settings, save_user_settings
from image_processor import process_image_metadata

# 配置日志 - 直接输出到stdout，无缓冲
print("=" * 50, flush=True)
print("Discord NovelAI Bot (Python Version)", flush=True)
print(f"Python: {sys.version}", flush=True)
print(f"Discord.py: {discord.__version__}", flush=True)
print(f"Platform: {sys.platform}", flush=True)
print(f"Working Dir: {os.getcwd()}", flush=True)
print("=" * 50, flush=True)

load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
NAI_API_KEY = os.getenv('NAI_API_KEY')
NAI_API_BASE = 'https://image.novelai.net'

# 检查环境变量
print(f"Discord Token: {'✓ Found' if DISCORD_TOKEN else '✗ Missing'}", flush=True)
print(f"NAI API Key: {'✓ Found' if NAI_API_KEY else '✗ Missing'}", flush=True)
print(f"Environment: {'Zeabur' if os.getenv('ZEABUR') else 'Local/Docker'}", flush=True)

if not DISCORD_TOKEN:
    print("ERROR: DISCORD_TOKEN not found!", flush=True)
    print("Please set DISCORD_TOKEN in environment variables", flush=True)
    # 保持进程运行以便查看日志
    import time
    while True:
        time.sleep(60)
        print("Waiting for DISCORD_TOKEN...", flush=True)

if not NAI_API_KEY:
    print("ERROR: NAI_API_KEY not found!", flush=True)
    print("Please set NAI_API_KEY in environment variables", flush=True)
    # 保持进程运行以便查看日志
    import time
    while True:
        time.sleep(60)
        print("Waiting for NAI_API_KEY...", flush=True)

print("Configuration OK, starting bot...", flush=True)

# 任务队列
task_queue = deque()
is_generating = False

# 面板状态缓存
panel_states = {}

# 尺寸步进值
SIZE_STEP = 64

# 尺寸限制
SIZE_LIMITS = {
    'maxPixels': 832 * 1216,
    'maxWidth': 1216,
    'maxHeight': 1216
}

# 尺寸预设
SIZE_PRESETS = {
    'portrait_s': {'width': 512, 'height': 768},
    'portrait_m': {'width': 832, 'height': 1216},
    'landscape_s': {'width': 768, 'height': 512},
    'landscape_m': {'width': 1216, 'height': 832},
    'square_s': {'width': 512, 'height': 512},
    'square_m': {'width': 768, 'height': 768},
    'square_l': {'width': 832, 'height': 832}
}

# 模型列表
MODELS = {
    'nai-diffusion-4-5-full': '🌟 V4.5 Full',
    'nai-diffusion-4-5-curated': '✨ V4.5 Curated',
    'nai-diffusion-4-full': '🎯 V4 Full',
    'nai-diffusion-4-curated': '📌 V4 Curated',
    'nai-diffusion-4-curated-preview': '👁️ V4 Preview',
    'nai-diffusion-3': '🎨 V3 Anime',
    'nai-diffusion-3-inpainting': '🔧 V3 Inpainting',
    'nai-diffusion-2': '🌸 V2 Anime',
    'nai-diffusion': '🎯 V1 Anime',
    'safe-diffusion': '✅ V1 Curated',
    'nai-diffusion-furry': '🦊 V1 Furry',
    'nai-diffusion-furry-v3': '🐺 V3 Furry'
}

class NovelAIBot(commands.Bot):
    def __init__(self):
        print("Initializing NovelAIBot...", flush=True)
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='!', intents=intents)
        print("NovelAIBot initialized", flush=True)

    async def setup_hook(self):
        print("Setting up bot commands...", flush=True)
        try:
            # 添加预设命令组
            self.tree.add_command(PresetGroup())
            print("Added PresetGroup command", flush=True)
            # 同步命令
            synced = await self.tree.sync()
            print(f'Commands synced successfully! Synced {len(synced)} commands', flush=True)
        except Exception as e:
            print(f"Error in setup_hook: {e}", flush=True)
            import traceback
            traceback.print_exc()

bot = NovelAIBot()

def get_model_defaults(model: str) -> Dict[str, Any]:
    """获取模型默认参数"""
    base = {
        'width': 832,
        'height': 1216,
        'scale': 5,
        'sampler': 'k_euler_ancestral',
        'steps': 28,
        'n_samples': 1,
        'ucPreset': 0,
        'qualityToggle': False,
        'negative_prompt': 'lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry'
    }

    if model.startswith('nai-diffusion-4'):
        base.update({
            'params_version': 3,
            'use_coords': True,
            'sm': False,
            'sm_dyn': False,
            'noise_schedule': 'karras',
            'scale': 7.0
        })
    else:
        base.update({
            'sm': True,
            'sm_dyn': True
        })

    return base

def build_v4_prompt(prompt: str, is_negative: bool = False) -> Dict:
    """构建V4模型提示词格式"""
    return {
        'caption': {
            'base_caption': prompt,
            'char_captions': []
        },
        'use_coords': True,
        'use_order': True
    }

async def generate_image(params: Dict[str, Any]) -> tuple[bytes, int]:
    """调用NovelAI API生成图片"""
    import zipfile
    import io

    prompt = params['prompt']
    negative_prompt = params.get('negative_prompt', '')
    model = params['model']
    width = params['width']
    height = params['height']
    steps = params.get('steps', 28)
    cfg = params.get('cfg', 5)
    sampler = params.get('sampler', 'k_euler_ancestral')
    seed = params.get('seed', -1)
    smea = params.get('smea', False)
    dyn = params.get('dyn', False)
    remove_metadata = params.get('remove_metadata', False)

    actual_seed = seed if seed != -1 else random.randint(0, 2147483647)
    defaults = get_model_defaults(model)

    final_prompt = prompt
    final_negative = negative_prompt or defaults['negative_prompt']

    # 非V4模型添加质量标签
    if not model.startswith('nai-diffusion-4'):
        final_prompt = 'masterpiece, best quality, ' + prompt

    # 构建参数
    base_params = {
        'width': width,
        'height': height,
        'scale': cfg if cfg else defaults['scale'],
        'sampler': sampler if sampler else defaults['sampler'],
        'steps': steps if steps else defaults['steps'],
        'seed': actual_seed,
        'n_samples': 1,
        'ucPreset': 0,
        'qualityToggle': False,
        'dynamic_thresholding': False,
        'controlnet_strength': 1,
        'legacy': False,
        'add_original_image': False,
        'negative_prompt': final_negative
    }

    # 构建请求体
    payload = {
        'input': final_prompt,  # input总是使用字符串
        'model': model,
        'action': 'generate',
        'parameters': base_params
    }

    # V4模型特殊处理
    if model.startswith('nai-diffusion-4'):
        base_params['params_version'] = 3
        base_params['use_coords'] = True
        base_params['sm'] = False
        base_params['sm_dyn'] = False
        base_params['noise_schedule'] = 'karras'

        # V4使用特殊格式
        base_params['v4_prompt'] = build_v4_prompt(final_prompt)
        base_params['v4_negative_prompt'] = build_v4_prompt(final_negative, True)
    else:
        # 非V4模型
        base_params['sm'] = smea if smea is not None else defaults.get('sm', True)
        base_params['sm_dyn'] = dyn if dyn is not None else defaults.get('sm_dyn', True)

    headers = {
        'Authorization': f'Bearer {NAI_API_KEY}',
        'Content-Type': 'application/json',
        'Accept': 'application/zip'  # 期望返回ZIP文件
    }

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f'{NAI_API_BASE}/ai/generate-image',
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                if response.status == 200:
                    zip_data = await response.read()

                    # 解压ZIP文件
                    with zipfile.ZipFile(io.BytesIO(zip_data)) as zip_file:
                        # 找到PNG文件
                        for filename in zip_file.namelist():
                            if filename.endswith('.png'):
                                image_data = zip_file.read(filename)

                                # 如果需要清除元数据
                                if remove_metadata:
                                    image_data = process_image_metadata(image_data)

                                return image_data, actual_seed

                    raise Exception('No image found in ZIP')

                # V4模型500错误时重试
                elif response.status == 500 and model.startswith('nai-diffusion-4'):
                    print(f"V4 model 500 error, retrying with simplified params", flush=True)

                    # 移除V4特殊字段重试
                    if 'v4_prompt' in base_params:
                        del base_params['v4_prompt']
                    if 'v4_negative_prompt' in base_params:
                        del base_params['v4_negative_prompt']

                    async with session.post(
                        f'{NAI_API_BASE}/ai/generate-image',
                        json=payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=60)
                    ) as retry_response:
                        if retry_response.status == 200:
                            zip_data = await retry_response.read()

                            with zipfile.ZipFile(io.BytesIO(zip_data)) as zip_file:
                                for filename in zip_file.namelist():
                                    if filename.endswith('.png'):
                                        image_data = zip_file.read(filename)
                                        if remove_metadata:
                                            image_data = process_image_metadata(image_data)
                                        return image_data, actual_seed
                        else:
                            error_text = await retry_response.text()
                            raise Exception(f'API Error: {retry_response.status} - {error_text}')
                else:
                    error_text = await response.text()
                    raise Exception(f'API Error: {response.status} - {error_text}')

        except aiohttp.ClientError as e:
            raise Exception(f'Network error: {str(e)}')
        except Exception as e:
            raise e

async def process_queue():
    """处理任务队列"""
    global is_generating

    while task_queue:
        if not is_generating:
            is_generating = True
            try:
                task = task_queue.popleft()
                interaction = task['interaction']
                params = task['params']

                # 生成图片
                image_data, seed = await generate_image(params)

                # 发送图片
                file = discord.File(
                    fp=io.BytesIO(image_data),
                    filename=f'nai_{seed}.png'
                )

                embed = discord.Embed(
                    title='✅ 生成完成',
                    color=discord.Color.green()
                )
                embed.add_field(name='Seed', value=str(seed), inline=True)
                embed.add_field(name='Model', value=MODELS.get(params['model'], params['model']), inline=True)
                embed.add_field(name='Size', value=f"{params['width']}x{params['height']}", inline=True)
                if params.get('remove_metadata'):
                    embed.add_field(name='元数据', value='已清除', inline=True)

                await interaction.followup.send(embed=embed, file=file)

            except Exception as e:
                if 'interaction' in locals():
                    error_embed = discord.Embed(
                        title='❌ 生成失败',
                        description=str(e),
                        color=discord.Color.red()
                    )
                    await interaction.followup.send(embed=error_embed)
            finally:
                is_generating = False

@bot.tree.command(name='nai', description='使用NovelAI生成图片')
@app_commands.describe(
    prompt='正向提示词',
    model='选择模型',
    negative='负向提示词',
    size='尺寸预设',
    width='自定义宽度',
    height='自定义高度',
    steps='采样步数',
    cfg='CFG/Guidance',
    sampler='采样器',
    seed='种子',
    smea='SMEA',
    dyn='SMEA DYN',
    remove_metadata='清除元数据'
)
@app_commands.choices(
    model=[
        app_commands.Choice(name=name, value=value)
        for value, name in MODELS.items()
    ],
    size=[
        app_commands.Choice(name='📱 竖图 832×1216', value='portrait_m'),
        app_commands.Choice(name='📱 竖图小 512×768', value='portrait_s'),
        app_commands.Choice(name='🖼️ 横图 1216×832', value='landscape_m'),
        app_commands.Choice(name='🖼️ 横图小 768×512', value='landscape_s'),
        app_commands.Choice(name='⬜ 方图 512×512', value='square_s'),
        app_commands.Choice(name='◻️ 方图 768×768', value='square_m'),
        app_commands.Choice(name='◼ 方图 832×832', value='square_l')
    ],
    sampler=[
        app_commands.Choice(name='Euler Ancestral', value='k_euler_ancestral'),
        app_commands.Choice(name='Euler', value='k_euler'),
        app_commands.Choice(name='DPM++ 2M', value='k_dpmpp_2m'),
        app_commands.Choice(name='DPM++ 2S Ancestral', value='k_dpmpp_2s_ancestral'),
        app_commands.Choice(name='DPM++ SDE', value='k_dpmpp_sde'),
        app_commands.Choice(name='DDIM V3', value='ddim_v3')
    ]
)
async def nai_command(
    interaction: discord.Interaction,
    prompt: str,
    model: str = 'nai-diffusion-3',
    negative: Optional[str] = None,
    size: Optional[str] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    steps: Optional[int] = None,
    cfg: Optional[float] = None,
    sampler: Optional[str] = None,
    seed: Optional[int] = None,
    smea: Optional[bool] = None,
    dyn: Optional[bool] = None,
    remove_metadata: Optional[bool] = False
):
    # 确定尺寸
    if size and size in SIZE_PRESETS:
        final_width = SIZE_PRESETS[size]['width']
        final_height = SIZE_PRESETS[size]['height']
    elif width and height:
        final_width = width
        final_height = height
    else:
        defaults = get_model_defaults(model)
        final_width = defaults['width']
        final_height = defaults['height']

    # 验证尺寸
    if (final_width * final_height > SIZE_LIMITS['maxPixels'] or
        final_width > SIZE_LIMITS['maxWidth'] or
        final_height > SIZE_LIMITS['maxHeight']):
        await interaction.response.send_message(
            '❌ 尺寸超限！最大832×1216',
            ephemeral=True
        )
        return

    # 准备任务
    task = {
        'interaction': interaction,
        'params': {
            'prompt': prompt,
            'negative_prompt': negative,
            'model': model,
            'width': final_width,
            'height': final_height,
            'steps': steps or 28,
            'cfg': cfg or 5,
            'sampler': sampler or 'k_euler_ancestral',
            'seed': seed or -1,
            'smea': smea or False,
            'dyn': dyn or False,
            'remove_metadata': remove_metadata
        }
    }

    # 加入队列
    task_queue.append(task)
    queue_position = len(task_queue)

    await interaction.response.send_message(
        f'✅ 您的请求已加入队列，当前排在第 {queue_position} 位。',
        ephemeral=True
    )

    # 处理队列
    asyncio.create_task(process_queue())

@bot.tree.command(name='panel', description='打开一个交互式绘图面板')
async def panel_command(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    user_settings = load_user_settings()

    # 获取或创建用户设置
    if user_id not in user_settings:
        user_settings[user_id] = {
            'model': 'nai-diffusion-3',
            'size': 'portrait_s',
            'sampler': 'k_euler_ancestral',
            'preset': None,
            'remove_metadata': False
        }
        save_user_settings(user_settings)

    state = user_settings[user_id]
    # 确保有自定义尺寸的默认值
    if 'custom_width' not in state:
        state['custom_width'] = 512
    if 'custom_height' not in state:
        state['custom_height'] = 768
    panel_states[user_id] = state

    # 构建面板
    embed = discord.Embed(
        title='🎨 NovelAI 绘图面板',
        description='使用下方的菜单和按钮来配置您的图片生成参数',
        color=discord.Color.blue()
    )

    embed.add_field(name='模型', value=MODELS.get(state['model'], state['model']), inline=True)

    # 显示尺寸信息
    if state['size'] == 'custom':
        size_display = f"自定义: {state.get('custom_width', 512)}×{state.get('custom_height', 768)}"
    else:
        size_preset = SIZE_PRESETS.get(state['size'], {'width': 512, 'height': 768})
        size_display = f"{state['size']} ({size_preset['width']}×{size_preset['height']})"

    embed.add_field(name='尺寸', value=size_display, inline=True)
    embed.add_field(name='采样器', value=state['sampler'], inline=True)
    embed.add_field(name='预设', value=state.get('preset', '未选择'), inline=True)
    embed.add_field(name='清除元数据', value='✅ 开启' if state.get('remove_metadata', False) else '❌ 关闭', inline=True)

    # 显示当前自定义尺寸
    if state['size'] == 'custom':
        pixels = state.get('custom_width', 512) * state.get('custom_height', 768)
        embed.add_field(
            name='📏 当前自定义尺寸',
            value=f"宽度: {state.get('custom_width', 512)} | 高度: {state.get('custom_height', 768)} | 总像素: {pixels:,}",
            inline=False
        )

    # 创建选择菜单 - 每个Select占整行
    model_select = discord.ui.Select(
        placeholder='选择模型',
        options=[
            discord.SelectOption(label=name, value=value, default=value==state['model'])
            for value, name in MODELS.items()
        ],
        custom_id='model_select',
        row=0
    )

    size_select = discord.ui.Select(
        placeholder='选择尺寸',
        options=[
            discord.SelectOption(label='📱 竖图 832×1216', value='portrait_m', default='portrait_m'==state['size']),
            discord.SelectOption(label='📱 竖图小 512×768', value='portrait_s', default='portrait_s'==state['size']),
            discord.SelectOption(label='🖼️ 横图 1216×832', value='landscape_m', default='landscape_m'==state['size']),
            discord.SelectOption(label='🖼️ 横图小 768×512', value='landscape_s', default='landscape_s'==state['size']),
            discord.SelectOption(label='⬜ 方图 512×512', value='square_s', default='square_s'==state['size']),
            discord.SelectOption(label='◻️ 方图 768×768', value='square_m', default='square_m'==state['size']),
            discord.SelectOption(label='◼ 方图 832×832', value='square_l', default='square_l'==state['size']),
            discord.SelectOption(label='🔧 自定义尺寸', value='custom', default='custom'==state['size'])
        ],
        custom_id='size_select',
        row=1
    )

    sampler_select = discord.ui.Select(
        placeholder='选择采样器',
        options=[
            discord.SelectOption(label='Euler Ancestral', value='k_euler_ancestral', default='k_euler_ancestral'==state['sampler']),
            discord.SelectOption(label='Euler', value='k_euler', default='k_euler'==state['sampler']),
            discord.SelectOption(label='DPM++ 2M', value='k_dpmpp_2m', default='k_dpmpp_2m'==state['sampler']),
            discord.SelectOption(label='DPM++ 2S Ancestral', value='k_dpmpp_2s_ancestral', default='k_dpmpp_2s_ancestral'==state['sampler']),
            discord.SelectOption(label='DPM++ SDE', value='k_dpmpp_sde', default='k_dpmpp_sde'==state['sampler']),
            discord.SelectOption(label='DDIM V3', value='ddim_v3', default='ddim_v3'==state['sampler'])
        ],
        custom_id='sampler_select',
        row=2
    )

    # 创建预设选择菜单
    presets = load_presets()
    user_presets = presets.get(user_id, {})

    preset_options = [discord.SelectOption(label='不使用预设', value='none', default=state.get('preset') is None)]
    preset_options.extend([
        discord.SelectOption(label=name, value=name, default=name==state.get('preset'))
        for name in user_presets.keys()
    ])

    preset_select = discord.ui.Select(
        placeholder='选择预设',
        options=preset_options,
        custom_id='preset_select',
        row=3
    )

    # 创建按钮 - 第4行：主要操作和尺寸调整
    generate_button = discord.ui.Button(
        label='🎨 生成图片',
        style=discord.ButtonStyle.primary,
        custom_id='generate_button',
        row=4
    )

    metadata_button = discord.ui.Button(
        label='🔄 元数据清除',
        style=discord.ButtonStyle.secondary,
        custom_id='metadata_button',
        row=4
    )

    save_button = discord.ui.Button(
        label='💾 保存设置',
        style=discord.ButtonStyle.success,
        custom_id='save_button',
        row=4
    )

    custom_size_button = discord.ui.Button(
        label='📐 自定义尺寸',
        style=discord.ButtonStyle.secondary,
        custom_id='custom_size_input',
        row=4
    )

    # 创建视图
    view = discord.ui.View(timeout=300)
    # 添加Select菜单
    view.add_item(model_select)    # row 0
    view.add_item(size_select)     # row 1
    view.add_item(sampler_select)  # row 2
    view.add_item(preset_select)   # row 3
    # 添加按钮 - 第4行
    view.add_item(generate_button)
    view.add_item(metadata_button)
    view.add_item(save_button)
    view.add_item(custom_size_button)

    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# 创建预设命令组
class PresetGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name='preset', description='管理你的个人提示词预设')

    @app_commands.command(name='save', description='保存一个新的预设')
    async def save_preset(
        self,
        interaction: discord.Interaction,
        name: str,
        prompt: str,
        negative: Optional[str] = None
    ):
        user_id = str(interaction.user.id)
        presets = load_presets()

        if user_id not in presets:
            presets[user_id] = {}

        presets[user_id][name] = {
            'prompt': prompt,
            'negative': negative or ''
        }

        save_presets(presets)
        await interaction.response.send_message(
            f"✅ 预设 '{name}' 已保存！",
            ephemeral=True
        )

    @app_commands.command(name='list', description='查看你所有的预设')
    async def list_presets(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        presets = load_presets()
        user_presets = presets.get(user_id, {})

        if not user_presets:
            await interaction.response.send_message(
                '你还没有保存任何预设。',
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title='你的预设',
            color=discord.Color.blue()
        )

        for name, data in user_presets.items():
            value = f"**正面:** {data['prompt'][:100]}..."
            if data.get('negative'):
                value += f"\n**负面:** {data['negative'][:100]}..."
            embed.add_field(name=name, value=value, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name='delete', description='删除一个预设')
    async def delete_preset(self, interaction: discord.Interaction, name: str):
        user_id = str(interaction.user.id)
        presets = load_presets()

        if user_id in presets and name in presets[user_id]:
            del presets[user_id][name]
            save_presets(presets)
            await interaction.response.send_message(
                f"🗑️ 预设 '{name}' 已删除。",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ 未找到名为 '{name}' 的预设。",
                ephemeral=True
            )

    @delete_preset.autocomplete('name')
    async def delete_preset_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> list[app_commands.Choice[str]]:
        user_id = str(interaction.user.id)
        presets = load_presets()
        user_presets = presets.get(user_id, {})

        return [
            app_commands.Choice(name=name, value=name)
            for name in user_presets.keys()
            if current.lower() in name.lower()
        ][:25]



@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type != discord.InteractionType.component:
        return

    custom_id = interaction.data.get('custom_id', '')
    user_id = str(interaction.user.id)

    if user_id not in panel_states:
        await interaction.response.send_message('会话已过期，请重新打开面板', ephemeral=True)
        return

    state = panel_states[user_id]

    # 处理选择菜单
    if custom_id.endswith('_select'):
        field = custom_id.replace('_select', '')
        value = interaction.data['values'][0]

        if field == 'model':
            state['model'] = value
        elif field == 'size':
            state['size'] = value
            # 如果选择了预设尺寸，更新自定义尺寸值
            if value != 'custom' and value in SIZE_PRESETS:
                state['custom_width'] = SIZE_PRESETS[value]['width']
                state['custom_height'] = SIZE_PRESETS[value]['height']
        elif field == 'sampler':
            state['sampler'] = value
        elif field == 'preset':
            if value == 'none':
                state['preset'] = None
            else:
                state['preset'] = value

        # 更新面板
        await update_panel(interaction, state)

    # 处理按钮
    elif custom_id == 'metadata_button':
        state['remove_metadata'] = not state.get('remove_metadata', False)
        await update_panel(interaction, state)

    # 处理自定义尺寸输入按钮
    elif custom_id == 'custom_size_input':
        # 弹出模态框输入自定义尺寸
        modal = discord.ui.Modal(title='输入自定义尺寸')

        width_input = discord.ui.TextInput(
            label='宽度',
            placeholder=f'输入宽度 (320-{SIZE_LIMITS["maxWidth"]})',
            default=str(state.get('custom_width', 512)),
            required=True,
            max_length=4
        )

        height_input = discord.ui.TextInput(
            label='高度',
            placeholder=f'输入高度 (320-{SIZE_LIMITS["maxHeight"]})',
            default=str(state.get('custom_height', 768)),
            required=True,
            max_length=4
        )

        modal.add_item(width_input)
        modal.add_item(height_input)

        async def size_modal_submit(modal_interaction: discord.Interaction):
            try:
                new_width = int(width_input.value)
                new_height = int(height_input.value)

                # 验证尺寸
                if new_width < 320 or new_width > SIZE_LIMITS['maxWidth']:
                    await modal_interaction.response.send_message(
                        f"❌ 宽度必须在 320 到 {SIZE_LIMITS['maxWidth']} 之间",
                        ephemeral=True
                    )
                    return

                if new_height < 320 or new_height > SIZE_LIMITS['maxHeight']:
                    await modal_interaction.response.send_message(
                        f"❌ 高度必须在 320 到 {SIZE_LIMITS['maxHeight']} 之间",
                        ephemeral=True
                    )
                    return

                if new_width * new_height > SIZE_LIMITS['maxPixels']:
                    await modal_interaction.response.send_message(
                        f"❌ 总像素数不能超过 {SIZE_LIMITS['maxPixels']:,} ({SIZE_LIMITS['maxWidth']}×{SIZE_LIMITS['maxHeight']})",
                        ephemeral=True
                    )
                    return

                # 确保尺寸是64的倍数
                new_width = (new_width // 64) * 64
                new_height = (new_height // 64) * 64

                state['size'] = 'custom'
                state['custom_width'] = new_width
                state['custom_height'] = new_height

                await update_panel(modal_interaction, state)

            except ValueError:
                await modal_interaction.response.send_message(
                    '❌ 请输入有效的数字',
                    ephemeral=True
                )

        modal.on_submit = size_modal_submit
        await interaction.response.send_modal(modal)

    elif custom_id == 'save_button':
        user_settings = load_user_settings()
        user_settings[user_id] = state
        save_user_settings(user_settings)
        await interaction.response.send_message('✅ 设置已保存！', ephemeral=True)

    elif custom_id == 'generate_button':
        # 创建模态框
        modal = discord.ui.Modal(title='输入提示词')

        prompt_input = discord.ui.TextInput(
            label='正面提示词',
            placeholder='输入您想要生成的图片描述...',
            required=True,
            style=discord.TextStyle.paragraph
        )

        negative_input = discord.ui.TextInput(
            label='负面提示词',
            placeholder='输入您不想要的元素...',
            required=False,
            style=discord.TextStyle.paragraph
        )

        modal.add_item(prompt_input)
        modal.add_item(negative_input)

        async def modal_submit(modal_interaction: discord.Interaction):
            prompt = prompt_input.value
            negative = negative_input.value

            # 如果选择了预设，合并提示词
            if state.get('preset'):
                presets = load_presets()
                user_presets = presets.get(user_id, {})
                if state['preset'] in user_presets:
                    preset_data = user_presets[state['preset']]
                    prompt = f"{preset_data['prompt']}, {prompt}"
                    if preset_data.get('negative'):
                        negative = f"{preset_data['negative']}, {negative}" if negative else preset_data['negative']

            # 获取尺寸
            if state['size'] == 'custom':
                width = state.get('custom_width', 512)
                height = state.get('custom_height', 768)
            else:
                size_data = SIZE_PRESETS.get(state['size'], SIZE_PRESETS['portrait_s'])
                width = size_data['width']
                height = size_data['height']

            # 准备任务
            task = {
                'interaction': modal_interaction,
                'params': {
                    'prompt': prompt,
                    'negative_prompt': negative,
                    'model': state['model'],
                    'width': width,
                    'height': height,
                    'sampler': state['sampler'],
                    'steps': 28,
                    'cfg': 5,
                    'seed': -1,
                    'smea': False,
                    'dyn': False,
                    'remove_metadata': state.get('remove_metadata', False)
                }
            }

            task_queue.append(task)
            queue_position = len(task_queue)

            await modal_interaction.response.send_message(
                f'✅ 您的请求已加入队列，当前排在第 {queue_position} 位。',
                ephemeral=True
            )

            asyncio.create_task(process_queue())

        modal.on_submit = modal_submit
        await interaction.response.send_modal(modal)

async def update_panel(interaction: discord.Interaction, state: Dict):
    """更新面板显示"""
    embed = discord.Embed(
        title='🎨 NovelAI 绘图面板',
        description='使用下方的菜单和按钮来配置您的图片生成参数',
        color=discord.Color.blue()
    )

    embed.add_field(name='模型', value=MODELS.get(state['model'], state['model']), inline=True)

    # 显示尺寸信息
    if state['size'] == 'custom':
        size_display = f"自定义: {state.get('custom_width', 512)}×{state.get('custom_height', 768)}"
    else:
        size_preset = SIZE_PRESETS.get(state['size'], {'width': 512, 'height': 768})
        size_display = f"{state['size']} ({size_preset['width']}×{size_preset['height']})"

    embed.add_field(name='尺寸', value=size_display, inline=True)
    embed.add_field(name='采样器', value=state['sampler'], inline=True)
    embed.add_field(name='预设', value=state.get('preset', '未选择'), inline=True)
    embed.add_field(name='清除元数据', value='✅ 开启' if state.get('remove_metadata', False) else '❌ 关闭', inline=True)

    # 显示当前自定义尺寸
    if state['size'] == 'custom':
        pixels = state.get('custom_width', 512) * state.get('custom_height', 768)
        embed.add_field(
            name='📏 当前自定义尺寸',
            value=f"宽度: {state.get('custom_width', 512)} | 高度: {state.get('custom_height', 768)} | 总像素: {pixels:,}",
            inline=False
        )

    await interaction.response.edit_message(embed=embed)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})', flush=True)
    print(f'Connected to {len(bot.guilds)} guilds', flush=True)
    print('Bot is ready!', flush=True)

    # 设置状态
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="/nai | /panel | /preset"
        )
    )

# 处理错误
@bot.event
async def on_error(event, *args, **kwargs):
    print(f'Error in {event}:', sys.exc_info(), flush=True)

async def main_async():
    """异步主函数"""
    async with bot:
        await bot.start(DISCORD_TOKEN)

if __name__ == '__main__':
    print("Starting bot...", flush=True)
    print(f"Token length: {len(DISCORD_TOKEN) if DISCORD_TOKEN else 0}", flush=True)

    try:
        import asyncio
        # Windows 环境特殊处理
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        # 直接运行 bot
        bot.run(DISCORD_TOKEN)
    except KeyboardInterrupt:
        print("Bot stopped by user", flush=True)
    except Exception as e:
        print(f"Failed to start bot: {e}", flush=True)
        import traceback
        traceback.print_exc()
        # 在 Zeabur 环境中保持进程运行以查看错误
        if os.getenv('ZEABUR'):
            import time
            while True:
                time.sleep(60)
                print(f"Waiting after error: {e}", flush=True)
        sys.exit(1)