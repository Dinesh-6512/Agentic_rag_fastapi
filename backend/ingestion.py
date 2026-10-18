import os
import re
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

DEFAULT_DOCS_DIR = Path(__file__).parent / "knowledge_docs"
PROCESSED_CHUNKS_FILE = "processed_chunks.json"


def clean_text(raw_text: str) -> str:
    """
    Cleans raw document text by removing HTML comments, repeated horizontal lines,
    and normalizing consecutive whitespace/newlines.
    """
    # Remove HTML-style comments (e.g. <!-- ... -->)
    text = re.sub(r"<!--.*?-->", "", raw_text, flags=re.DOTALL)
    
    # Remove standalone markdown divider lines (e.g., ---, ***, ___)
    text = re.sub(r"^[ \t]*[-*_]{3,}[ \t]*$", "", text, flags=re.MULTILINE)
    
    # Replace Windows line breaks with Unix line breaks
    text = text.replace("\r\n", "\n")
    
    # Collapse 3 or more consecutive newlines into 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    
    return text.strip()


def extract_product_and_sections(cleaned_text: str) -> tuple[str, List[Dict[str, str]]]:
    """
    Parses a markdown document into its product name and section-level blocks.
    Returns (product_name, list_of_sections_with_content).
    """
    lines = cleaned_text.split("\n")
    product_name = "General Product"
    sections: List[Dict[str, str]] = []
    
    current_section = "Overview"
    current_lines: List[str] = []
    
    # Check top heading for product name
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("# ") and product_name == "General Product":
            # Extract title: e.g., "# Lumina Silent Wireless Mouse - User Manual"
            title_text = stripped[2:].strip()
            if "-" in title_text:
                product_name = title_text.split("-")[0].strip()
            else:
                product_name = title_text
            continue
            
        # Detect section headings (## Heading)
        if stripped.startswith("## "):
            # Save previous section if it has content
            if current_lines:
                section_text = "\n".join(current_lines).strip()
                if section_text:
                    sections.append({
                        "section": current_section,
                        "text": section_text
                    })
                current_lines = []
            current_section = stripped[3:].strip()
        else:
            current_lines.append(line)
            
    # Add final section
    if current_lines:
        section_text = "\n".join(current_lines).strip()
        if section_text:
            sections.append({
                "section": current_section,
                "text": section_text
            })
            
    return product_name, sections


def split_text_with_overlap(text: str, chunk_size: int = 450, overlap: int = 70) -> List[str]:
    """
    Splits text into chunks of target size with specified character overlap.
    Prefers breaking on line or sentence boundaries.
    """
    if len(text) <= chunk_size:
        return [text]
        
    chunks: List[str] = []
    start = 0
    text_len = len(text)
    
    while start < text_len:
        end = start + chunk_size
        
        # If this is the last chunk, take the remainder
        if end >= text_len:
            chunks.append(text[start:].strip())
            break
            
        # Try to find a natural break near the end of the chunk (newline or period)
        break_pos = -1
        # Check for newline
        nl_pos = text.rfind("\n", start + chunk_size // 2, end)
        if nl_pos != -1:
            break_pos = nl_pos + 1
        else:
            # Check for sentence end (.!?)
            for sep in [". ", "? ", "! "]:
                sep_pos = text.rfind(sep, start + chunk_size // 2, end)
                if sep_pos != -1:
                    break_pos = sep_pos + len(sep)
                    break
                    
        # Fallback to space
        if break_pos == -1:
            space_pos = text.rfind(" ", start + chunk_size // 2, end)
            if space_pos != -1:
                break_pos = space_pos + 1
            else:
                break_pos = end
                
        chunk = text[start:break_pos].strip()
        if chunk:
            chunks.append(chunk)
            
        # Advance with overlap, ensuring we start cleanly on a line or word boundary
        raw_next_start = break_pos - overlap
        if raw_next_start > start:
            # Prefer breaking at a line boundary near raw_next_start
            window_start = max(start, raw_next_start - 40)
            window_end = min(break_pos, raw_next_start + 40)
            near_nl = text.find("\n", window_start, window_end)
            if near_nl != -1 and near_nl > start:
                start = near_nl + 1
            else:
                # Fallback to nearest word boundary
                space_idx = text.find(" ", raw_next_start, break_pos)
                if space_idx != -1:
                    start = space_idx + 1
                else:
                    start = raw_next_start
        else:
            start = break_pos
        
    return chunks


def process_document(file_path: Path) -> List[Dict[str, Any]]:
    """
    Ingests a single document (.md or .txt), cleans it, splits it into chunks,
    and attaches metadata.
    """
    filename = file_path.name
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            raw_text = f.read()
    except UnicodeDecodeError:
        with open(file_path, "r", encoding="latin-1") as f:
            raw_text = f.read()
            
    cleaned_text = clean_text(raw_text)
    product_name, sections = extract_product_and_sections(cleaned_text)
    
    document_chunks: List[Dict[str, Any]] = []
    chunk_counter = 0
    
    for sec in sections:
        section_title = sec["section"]
        section_text = sec["text"]
        raw_chunks = split_text_with_overlap(section_text, chunk_size=450, overlap=70)
        
        for raw_chunk in raw_chunks:
            if not raw_chunk.strip():
                continue
                
            chunk_data = {
                "chunk_id": f"{file_path.stem}_chunk_{chunk_counter}",
                "chunk_index": chunk_counter,
                "text": raw_chunk,
                "metadata": {
                    "source_file": filename,
                    "document_name": filename,
                    "product_name": product_name,
                    "section": section_title,
                    "char_count": len(raw_chunk)
                }
            }
            document_chunks.append(chunk_data)
            chunk_counter += 1
            
    return document_chunks


def ingest_all_documents(docs_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    Ingests all approved .md and .txt manuals in the knowledge_docs directory,
    chunks them, and stores the processed chunks in a local JSON file.
    """
    if docs_dir is None:
        docs_dir = DEFAULT_DOCS_DIR
        
    docs_dir = Path(docs_dir)
    if not docs_dir.exists():
        docs_dir.mkdir(parents=True, exist_ok=True)
        return []
        
    all_chunks: List[Dict[str, Any]] = []
    valid_extensions = {".md", ".txt"}
    
    # Process all approved document files (excluding generated json)
    for file_path in sorted(docs_dir.iterdir()):
        if file_path.is_file() and file_path.suffix.lower() in valid_extensions:
            chunks = process_document(file_path)
            all_chunks.extend(chunks)
            
    # Save the processed chunks to the local project structure for the next step
    output_file = docs_dir / PROCESSED_CHUNKS_FILE
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, indent=2, ensure_ascii=False)
        
    return all_chunks


def load_processed_chunks(docs_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """
    Loads already processed chunks from the local JSON file.
    If not found, runs ingestion automatically.
    """
    if docs_dir is None:
        docs_dir = DEFAULT_DOCS_DIR
        
    output_file = Path(docs_dir) / PROCESSED_CHUNKS_FILE
    if output_file.exists():
        with open(output_file, "r", encoding="utf-8") as f:
            return json.load(f)
            
    return ingest_all_documents(docs_dir)


if __name__ == "__main__":
    chunks = ingest_all_documents()
    print(f"Successfully processed {len(chunks)} chunks from approved product manuals.")
