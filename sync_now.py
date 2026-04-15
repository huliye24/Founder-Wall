#!/usr/bin/env python3
"""
AI创业者联盟 - Notion 一键同步脚本

用法:
    python sync_now.py              # 双向同步
    python sync_now.py --upload    # 仅上传到 Notion
    python sync_now.py --download  # 仅下载到本地
    python sync_now.py --status    # 查看同步状态
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

# 简化输出，避免 Windows 编码问题
def log(msg):
    print(msg)

def check_env():
    """检查环境配置"""
    token = os.getenv("NOTION_API_TOKEN")
    db_id = os.getenv("NOTION_DATABASE_DEFAULT")
    
    if not token:
        log("X 未找到 NOTION_API_TOKEN，请检查 .env 文件")
        return False
    if not db_id:
        log("X 未找到 NOTION_DATABASE_DEFAULT，请检查 .env 文件")
        return False
    
    log("OK 环境配置检查通过")
    return True

def get_status():
    """获取本地文档状态"""
    root = Path(__file__).parent / "AI创业者联盟"
    if not root.exists():
        return 0, [], root
    
    md_files = list(root.glob("**/*.md"))
    md_files = [f for f in md_files if f.name != "README.md"]
    return len(md_files), md_files, root

def main():
    parser = argparse.ArgumentParser(description="Notion 一键同步")
    parser.add_argument("--upload", action="store_true", help="仅上传到 Notion")
    parser.add_argument("--download", action="store_true", help="仅下载到本地")
    parser.add_argument("--status", action="store_true", help="查看状态")
    args = parser.parse_args()
    
    print("\n" + "=" * 50)
    print("AI创业者联盟 - Notion 同步工具")
    print("=" * 50 + "\n")
    
    # 状态查看
    if args.status:
        count, files, root = get_status()
        log(f"文档数量: {count}")
        if files:
            print("\n文档列表:")
            for f in files[:10]:
                print(f"  - {f.relative_to(root)}")
            if len(files) > 10:
                print(f"  ... 还有 {len(files) - 10} 个文件")
        return
    
    # 检查环境
    if not check_env():
        sys.exit(1)
    
    # 获取文档数量
    count, _, root = get_status()
    log(f"检测到 {count} 个本地文档")
    
    # 执行同步
    script = Path(__file__).parent / "sync_to_notion.py"
    
    if args.download:
        log("\n开始从 Notion 下载...")
        cmd = f'python "{script}" --download'
    elif args.upload:
        log("\n开始上传到 Notion...")
        cmd = f'python "{script}"'
    else:
        log("\n开始双向同步...")
        cmd = f'python "{script}" --bidirectional'
    
    log("-" * 50)
    
    # 执行命令
    result = subprocess.run(cmd, shell=True)
    
    if result.returncode == 0:
        log("\n同步完成!")
    else:
        log("\n同步失败，请检查错误信息")
    
    print("\n" + "=" * 50 + "\n")

if __name__ == "__main__":
    main()
