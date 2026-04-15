#!/usr/bin/env python3
"""
AI联盟 Notion 同步脚本
Markdown 文件同步到 Notion Database

功能：
- 读取本地 Markdown 文件
- 解析 frontmatter 元数据
- 创建/更新 Notion 页面
- 支持 GitHub Action 自动运行
"""

import os
import re
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

# ============================================================
# 配置区域 - 请根据实际情况修改
# ============================================================

# 文档类型映射到 Notion Database ID
DATABASE_MAPPING = {
    "memory": os.getenv("NOTION_DATABASE_MEMORY", ""),
    "agents": os.getenv("NOTION_DATABASE_AGENTS", ""),
    "projects": os.getenv("NOTION_DATABASE_PROJECTS", ""),
    "flows": os.getenv("NOTION_DATABASE_FLOWS", ""),
    "knowledge": os.getenv("NOTION_DATABASE_KNOWLEDGE", ""),
    "default": os.getenv("NOTION_DATABASE_DEFAULT", ""),
}

# 默认 Database ID（用于未分类文档）
DEFAULT_DATABASE_ID = os.getenv("NOTION_DATABASE_DEFAULT", "")

# ============================================================
# 日志配置
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('sync.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# ============================================================
# 数据结构
# ============================================================

@dataclass
class MarkdownDoc:
    """Markdown 文档结构"""
    file_path: Path
    title: str
    content: str
    metadata: Dict[str, any] = field(default_factory=dict)
    doc_type: str = "default"
    tags: List[str] = field(default_factory=list)
    importance: int = 3
    source: str = "local"
    status: str = "未处理"

@dataclass
class NotionPage:
    """Notion 页面结构"""
    page_id: Optional[str] = None
    title: str = ""
    content: str = ""
    properties: Dict[str, any] = field(default_factory=dict)
    database_id: str = ""

# ============================================================
# Markdown 解析器
# ============================================================

class MarkdownParser:
    """Markdown 文件解析器"""
    
    # 支持的文档类型
    DOC_TYPES = {
        "系统架构": "knowledge",
        "记忆库": "memory",
        "节点库": "agents",
        "项目系统": "projects",
        "流程系统": "flows",
        "知识库": "knowledge",
        "仪表盘": "knowledge",
        "README": "knowledge",
    }
    
    # 重要性映射
    IMPORTANCE_MAP = {
        "MVP": 5,
        "关键": 5,
        "重要": 4,
        "一般": 3,
        "普通": 2,
        "实验": 1,
    }
    
    @staticmethod
    def parse_frontmatter(content: str) -> Tuple[Dict, str]:
        """解析 YAML frontmatter"""
        frontmatter_pattern = r'^---\s*\n([\s\S]*?)\n---\s*\n'
        match = re.match(frontmatter_pattern, content)
        
        if match:
            yaml_content = match.group(1)
            body = content[match.end():]
            
            # 简单 YAML 解析
            metadata = {}
            for line in yaml_content.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    metadata[key.strip()] = value.strip().strip('"\'')
            
            return metadata, body
        
        return {}, content
    
    @staticmethod
    def extract_title(content: str) -> str:
        """提取文档标题"""
        # 尝试从第一行 # 标题
        match = re.match(r'^#\s+(.+)$', content, re.MULTILINE)
        if match:
            return match.group(1).strip()
        
        # 如果没有标题，使用文件名
        return "Untitled"
    
    @staticmethod
    def extract_tags(content: str) -> List[str]:
        """提取文档中的标签"""
        tags = []
        
        # 匹配 #标签 格式
        tag_pattern = r'#(\w+)'
        tags.extend(re.findall(tag_pattern, content))
        
        return list(set(tags))  # 去重
    
    @staticmethod
    def determine_doc_type(file_path: Path, content: str, metadata: Dict) -> str:
        """确定文档类型"""
        # 优先使用 frontmatter 中的 type
        if 'type' in metadata:
            return metadata['type']
        
        # 根据文件路径判断
        filename = file_path.stem
        for keyword, doc_type in MarkdownParser.DOC_TYPES.items():
            if keyword in filename or keyword in content[:500]:
                return doc_type
        
        return "default"
    
    @staticmethod
    def parse_importance(metadata: Dict) -> int:
        """解析重要性"""
        if 'importance' in metadata:
            value = metadata['importance']
            if isinstance(value, int):
                return value
            if isinstance(value, str) and value.isdigit():
                return int(value)
            return MarkdownParser.IMPORTANCE_MAP.get(value, 3)
        
        return 3
    
    def parse(self, file_path: Path) -> MarkdownDoc:
        """解析单个 Markdown 文件"""
        logger.info(f"解析文件: {file_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 解析 frontmatter
            metadata, body = self.parse_frontmatter(content)
            
            # 提取标题
            title = metadata.get('title', '') or self.extract_title(body)
            
            # 确定文档类型
            doc_type = self.determine_doc_type(file_path, body, metadata)
            
            # 提取标签
            tags = self.extract_tags(body)
            if 'tags' in metadata:
                if isinstance(metadata['tags'], str):
                    tags.extend(metadata['tags'].split(','))
                else:
                    tags.extend(metadata['tags'])
            
            # 解析重要性
            importance = self.parse_importance(metadata)
            
            # 来源
            source = metadata.get('source', 'local')
            
            # 状态
            status = metadata.get('status', '未处理')
            
            return MarkdownDoc(
                file_path=file_path,
                title=title,
                content=body,
                metadata=metadata,
                doc_type=doc_type,
                tags=tags,
                importance=importance,
                source=source,
                status=status
            )
            
        except Exception as e:
            logger.error(f"解析失败 {file_path}: {e}")
            raise

# ============================================================
# Notion API 客户端
# ============================================================

class NotionClient:
    """Notion API 客户端"""
    
    API_URL = "https://api.notion.com/v1"
    API_VERSION = "2022-06-30"
    
    def __init__(self, token: str):
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Notion-Version": self.API_VERSION
        }
    
    def _request(self, method: str, endpoint: str, data: dict = None) -> dict:
        """发送 API 请求"""
        import urllib.request
        
        url = f"{self.API_URL}{endpoint}"
        request = urllib.request.Request(
            url,
            method=method,
            headers=self.headers
        )
        
        if data:
            request.data = json.dumps(data).encode('utf-8')
        
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            logger.error(f"API 请求失败: {e.code} - {error_body}")
            raise
    
    def get_database(self, database_id: str) -> dict:
        """获取 Database 信息"""
        return self._request("GET", f"/databases/{database_id}")
    
    def query_database(
        self, 
        database_id: str, 
        filter_cond: dict = None,
        sort: dict = None,
        page_size: int = 100
    ) -> List[dict]:
        """查询 Database"""
        data = {"page_size": page_size}
        
        if filter_cond:
            data["filter"] = filter_cond
        
        if sort:
            data["sorts"] = [sort]
        
        results = []
        response = self._request("POST", f"/databases/{database_id}/query", data)
        results.extend(response.get("results", []))
        
        # 处理分页
        while response.get("has_more"):
            data["start_cursor"] = response["next_cursor"]
            response = self._request("POST", f"/databases/{database_id}/query", data)
            results.extend(response.get("results", []))
        
        return results
    
    def create_page(self, database_id: str, properties: dict, children: List[dict] = None) -> dict:
        """创建页面"""
        data = {
            "parent": {"database_id": database_id},
            "properties": properties,
        }
        
        if children:
            data["children"] = children
        
        return self._request("POST", "/pages", data)
    
    def update_page(self, page_id: str, properties: dict, children: List[dict] = None) -> dict:
        """更新页面"""
        data = {"properties": properties}
        
        if children is not None:
            if children:
                data["children"] = children
            else:
                # 清空子内容需要特殊处理
                pass
        
        return self._request("PATCH", f"/pages/{page_id}", data)
    
    def archive_page(self, page_id: str) -> dict:
        """归档页面"""
        return self._request("PATCH", f"/pages/{page_id}", {"archived": True})

# ============================================================
# Markdown 转 Notion 转换器
# ============================================================

class MarkdownToNotionConverter:
    """Markdown 到 Notion 的转换器"""
    
    def __init__(self, notion_client: NotionClient):
        self.notion = notion_client
    
    def markdown_to_blocks(self, markdown: str) -> List[dict]:
        """将 Markdown ���容转换为 Notion blocks"""
        blocks = []
        lines = markdown.split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # 跳过空行
            if not line.strip():
                i += 1
                continue
            
            # 标题
            if line.startswith('# '):
                blocks.append({
                    "object": "block",
                    "type": "heading_1",
                    "heading_1": {"rich_text": [{"type": "text", "text": {"content": line[2:]}}]}
                })
            elif line.startswith('## '):
                blocks.append({
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {"rich_text": [{"type": "text", "text": {"content": line[3:]}}]}
                })
            elif line.startswith('### '):
                blocks.append({
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {"rich_text": [{"type": "text", "text": {"content": line[4:]}}]}
                })
            
            # 列表
            elif line.strip().startswith('- ') or line.strip().startswith('* '):
                blocks.append({
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": line.strip()[2:]}}]}
                })
            
            # 数字列表
            elif re.match(r'^\d+\.\s+', line.strip()):
                match = re.match(r'^(\d+)\.\s+(.*)', line.strip())
                if match:
                    blocks.append({
                        "object": "block",
                        "type": "numbered_list_item",
                        "numbered_list_item": {"rich_text": [{"type": "text", "text": {"content": match.group(2)}}]}
                    })
            
            # 代码块
            elif line.strip().startswith('```'):
                code_content = []
                i += 1
                while i < len(lines) and not lines[i].strip().startswith('```'):
                    code_content.append(lines[i])
                    i += 1
                blocks.append({
                    "object": "block",
                    "type": "code",
                    "code": {
                        "rich_text": [{"type": "text", "text": {"content": '\n'.join(code_content)}}],
                        "language": "markdown"
                    }
                })
            
            # 分割线
            elif line.strip() == '---':
                blocks.append({
                    "object": "block",
                    "type": "divider",
                    "divider": {}
                })
            
            # 引用
            elif line.strip().startswith('>'):
                blocks.append({
                    "object": "block",
                    "type": "quote",
                    "quote": {"rich_text": [{"type": "text", "text": {"content": line.strip()[1:].strip()}}]}
                })
            
            # 普通段落
            else:
                # 处理内联格式
                text = line
                rich_text = self._parse_inline_formatting(text)
                if rich_text:
                    blocks.append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {"rich_text": rich_text}
                    })
            
            i += 1
        
        return blocks
    
    def _parse_inline_formatting(self, text: str) -> List[dict]:
        """解析行内格式（粗体、斜体、代码）"""
        if not text.strip():
            return []
        
        rich_text = []
        
        # 分割代码块
        parts = re.split(r'(`[^`]+`)', text)
        
        for part in parts:
            if part.startswith('`') and part.endswith('`'):
                # 代码格式
                rich_text.append({
                    "type": "text",
                    "text": {"content": part[1:-1]},
                    "annotations": {"code": True}
                })
            else:
                # 处理粗体和斜体
                sub_parts = re.split(r'(\*\*[^*]+\*\*|\*[^*]+\*)', part)
                for sub_part in sub_parts:
                    if sub_part.startswith('**') and sub_part.endswith('**'):
                        rich_text.append({
                            "type": "text",
                            "text": {"content": sub_part[2:-2]},
                            "annotations": {"bold": True}
                        })
                    elif sub_part.startswith('*') and sub_part.endswith('*'):
                        rich_text.append({
                            "type": "text",
                            "text": {"content": sub_part[1:-1]},
                            "annotations": {"italic": True}
                        })
                    elif sub_part:
                        rich_text.append({
                            "type": "text",
                            "text": {"content": sub_part}
                        })
        
        return rich_text if rich_text else [{"type": "text", "text": {"content": text}}]
    
    def create_properties(self, doc: MarkdownDoc, database_id: str) -> dict:
        """创建 Notion 页面属性"""
        properties = {}
        
        # 标题（大多数数据库都有 Title 属性）
        properties["Name"] = {
            "title": [{"text": {"content": doc.title[:200]}}]
        }
        
        # 类型
        if doc.doc_type != "default":
            properties["Type"] = {"select": {"name": doc.doc_type}}
        
        # 标签
        if doc.tags:
            properties["Tags"] = {
                "multi_select": [{"name": tag[:50]} for tag in doc.tags[:20]]
            }
        
        # 重要性
        if doc.importance:
            # 转换为星星
            stars = "★" * doc.importance + "☆" * (5 - doc.importance)
            properties["Importance"] = {
                "select": {"name": stars}
            }
        
        # 来源
        if doc.source:
            properties["Source"] = {"select": {"name": doc.source}}
        
        # 状态
        if doc.status:
            properties["Status"] = {"select": {"name": doc.status}}
        
        # 文件路径（用于追踪）
        properties["File Path"] = {
            "rich_text": [{"text": {"content": str(doc.file_path)}}]
        }
        
        return properties

# ============================================================
# 同步管理器
# ============================================================

class SyncManager:
    """同步管理器"""
    
    # 文档类型到数据库的映射
    TYPE_TO_DATABASE = {
        "memory": os.getenv("NOTION_DATABASE_MEMORY", ""),
        "agents": os.getenv("NOTION_DATABASE_AGENTS", ""),
        "projects": os.getenv("NOTION_DATABASE_PROJECTS", ""),
        "flows": os.getenv("NOTION_DATABASE_FLOWS", ""),
        "knowledge": os.getenv("NOTION_DATABASE_KNOWLEDGE", ""),
    }
    
    def __init__(self, notion_token: str, root_path: str):
        self.notion = NotionClient(notion_token)
        self.parser = MarkdownParser()
        self.converter = MarkdownToNotionConverter(self.notion)
        self.root_path = Path(root_path)
        self.stats = {
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0
        }
        
        # 缓存已存在的页面
        self.existing_pages = {}
        self._load_existing_pages()
    
    def _load_existing_pages(self):
        """加载已存在的页面索引"""
        logger.info("加载已存在的 Notion 页面...")
        
        for doc_type, database_id in self.TYPE_TO_DATABASE.items():
            if not database_id:
                continue
            
            try:
                pages = self.notion.query_database(database_id)
                for page in pages:
                    page_id = page['id']
                    # 尝试从属性中获取文件路径
                    file_path = None
                    if "File Path" in page.get("properties", {}):
                        rich_text = page["properties"]["File Path"].get("rich_text", [])
                        if rich_text:
                            file_path = rich_text[0].get("plain_text", "")
                    
                    # 也尝试从标题中匹配
                    if not file_path:
                        title_parts = page["properties"].get("Name", {}).get("title", [])
                        if title_parts:
                            title = title_parts[0].get("plain_text", "")
                            # 存储标题作为后备
                    
                    self.existing_pages[page_id] = {
                        "database_id": database_id,
                        "file_path": file_path
                    }
                
                logger.info(f"  {doc_type}: {len(pages)} pages")
                
            except Exception as e:
                logger.warning(f"  无法加载 {doc_type} 数据库: {e}")
    
    def _get_database_id(self, doc: MarkdownDoc) -> str:
        """获取文档对应的 Database ID"""
        database_id = self.TYPE_TO_DATABASE.get(doc.doc_type, "")
        
        if not database_id:
            database_id = os.getenv("NOTION_DATABASE_DEFAULT", "")
        
        if not database_id:
            logger.warning(f"未配置 {doc.doc_type} 类型的数据库，使用默认数据库")
            database_id = DEFAULT_DATABASE_ID
        
        return database_id
    
    def _find_existing_page(self, file_path: Path) -> Optional[str]:
        """查找已存在的页面"""
        for page_id, info in self.existing_pages.items():
            if info.get("file_path") == str(file_path):
                return page_id
        return None
    
    def sync_file(self, file_path: Path) -> bool:
        """同步单个文件"""
        try:
            doc = self.parser.parse(file_path)
            database_id = self._get_database_id(doc)
            
            if not database_id:
                logger.error(f"未找到数据库配置，跳过: {file_path}")
                self.stats["skipped"] += 1
                return False
            
            # 检查是否已存在
            existing_page_id = self._find_existing_page(file_path)
            
            # 准备内容
            blocks = self.converter.markdown_to_blocks(doc.content)
            properties = self.converter.create_properties(doc, database_id)
            
            if existing_page_id:
                # 更新现有页面
                logger.info(f"更新: {doc.title}")
                self.notion.update_page(existing_page_id, properties, blocks)
                self.stats["updated"] += 1
            else:
                # 创建新页面
                logger.info(f"创建: {doc.title}")
                self.notion.create_page(database_id, properties, blocks)
                self.stats["created"] += 1
            
            return True
            
        except Exception as e:
            logger.error(f"同步失败 {file_path}: {e}")
            self.stats["errors"] += 1
            return False
    
    def sync_directory(self, subdir: str = "") -> int:
        """同步目录下的所有 Markdown 文件"""
        sync_path = self.root_path / subdir if subdir else self.root_path
        
        md_files = list(sync_path.glob("**/*.md"))
        # 排除 README.md 和节点模块
        md_files = [f for f in md_files if f.name != "README.md" and "node_modules" not in str(f)]
        
        logger.info(f"找到 {len(md_files)} 个 Markdown 文件")
        
        success_count = 0
        for md_file in md_files:
            if self.sync_file(md_file):
                success_count += 1
        
        return success_count
    
    def print_stats(self):
        """打印同步统计"""
        logger.info("=" * 50)
        logger.info("同步完成!")
        logger.info(f"  创建: {self.stats['created']}")
        logger.info(f"  更新: {self.stats['updated']}")
        logger.info(f"  跳过: {self.stats['skipped']}")
        logger.info(f"  错误: {self.stats['errors']}")
        logger.info("=" * 50)

# ============================================================
# 主程序
# ============================================================

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="AI联盟 Notion 同步工具")
    parser.add_argument("--token", help="Notion API Token")
    parser.add_argument("--path", default=".", help="要同步的目录路径")
    parser.add_argument("--subdir", default="", help="子目录（如 AI创业者联盟/Notion系统）")
    parser.add_argument("--dry-run", action="store_true", help="仅测试不实际同步")
    
    args = parser.parse_args()
    
    # 从环境变量或参数获取 token
    notion_token = args.token or os.getenv("NOTION_API_TOKEN")
    
    if not notion_token:
        logger.error("未设置 NOTION_API_TOKEN，请设置环境变量或传入 --token 参数")
        return 1
    
    # 创建同步管理器
    manager = SyncManager(notion_token, args.path)
    
    if args.dry_run:
        logger.info("Dry run 模式，仅解析文件不实际同步")
        # TODO: 实现 dry run 模式
        return 0
    
    # 执行同步
    if args.subdir:
        success = manager.sync_directory(args.subdir)
    else:
        success = manager.sync_directory()
    
    manager.print_stats()
    
    return 0 if manager.stats["errors"] == 0 else 1

if __name__ == "__main__":
    exit(main())