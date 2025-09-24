# -*- coding: utf-8 -*-
import io
from PIL import Image
from typing import Optional

def process_image_metadata(image_data: bytes) -> bytes:
    """
    处理图像：移除元数据和Alpha通道

    Args:
        image_data: 原始图片的二进制数据

    Returns:
        处理后的图片二进制数据
    """
    try:
        # 将二进制数据转换为PIL Image对象
        with io.BytesIO(image_data) as input_buffer:
            img = Image.open(input_buffer)
            original_format = img.format or 'PNG'

            # 如果图片有透明通道，转换为RGB
            if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                # 创建一个白色背景
                background = Image.new('RGB', img.size, (255, 255, 255))

                # 如果有alpha通道，使用它作为mask进行合成
                if img.mode == 'RGBA' or img.mode == 'LA':
                    background.paste(img, mask=img.split()[-1])
                else:
                    background.paste(img)

                img = background
            elif img.mode not in ('RGB', 'L'):
                # 确保图片是RGB或灰度模式
                img = img.convert('RGB')

            # 创建输出缓冲区
            output_buffer = io.BytesIO()

            # 根据原始格式保存，移除所有元数据
            if original_format in ('JPEG', 'JPG'):
                # JPEG格式，保持较高质量
                img.save(
                    output_buffer,
                    format='JPEG',
                    quality=95,
                    optimize=True,
                    exif=b"",  # 移除EXIF数据
                    icc_profile=None,  # 移除ICC配置文件
                    subsampling=0,  # 最高质量的色彩子采样
                    qtables='keep'  # 保持量化表
                )
            elif original_format == 'WEBP':
                # WebP格式
                img.save(
                    output_buffer,
                    format='WEBP',
                    quality=95,
                    method=6,  # 最慢但最好的压缩
                    exif=b"",
                    icc_profile=None
                )
            else:
                # 默认使用PNG格式（包括原本就是PNG的情况）
                img.save(
                    output_buffer,
                    format='PNG',
                    optimize=True,
                    compress_level=9,  # 最大压缩
                    icc_profile=None
                )

            # 获取处理后的二进制数据
            output_buffer.seek(0)
            return output_buffer.read()

    except Exception as e:
        print(f"Error processing image metadata: {e}")
        # 如果处理失败，返回原始数据
        return image_data

def remove_metadata_batch(image_list: list) -> list:
    """
    批量处理多张图片的元数据

    Args:
        image_list: 包含图片二进制数据的列表

    Returns:
        处理后的图片二进制数据列表
    """
    processed_images = []
    for image_data in image_list:
        processed = process_image_metadata(image_data)
        processed_images.append(processed)
    return processed_images

def get_image_info(image_data: bytes) -> dict:
    """
    获取图片的基本信息

    Args:
        image_data: 图片二进制数据

    Returns:
        包含图片信息的字典
    """
    try:
        with io.BytesIO(image_data) as input_buffer:
            img = Image.open(input_buffer)
            info = {
                'format': img.format,
                'mode': img.mode,
                'size': img.size,
                'width': img.width,
                'height': img.height,
                'has_transparency': img.mode in ('RGBA', 'LA', 'P'),
                'has_exif': bool(img.info.get('exif')),
                'has_icc_profile': bool(img.info.get('icc_profile'))
            }
            return info
    except Exception as e:
        print(f"Error getting image info: {e}")
        return {}