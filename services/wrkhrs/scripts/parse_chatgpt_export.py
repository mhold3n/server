#!/usr/bin/env python3
"""Script to parse and categorize ChatGPT export data."""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add the project root to sys.path to import the DomainClassifier
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from services.api.src.wrkhrs.domain_classifier import DomainClassifier  # noqa: E402

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def reconstruct_conversation(
    mapping: Dict[str, Any], current_node_id: Optional[str]
) -> List[Dict[str, Any]]:
    """Reconstruct the main branch of the conversation starting from the leaf node up to root."""
    if not current_node_id or current_node_id not in mapping:
        # Fallback to finding a leaf node if current_node isn't provided
        for node_id, node in mapping.items():
            if not node.get("children"):
                current_node_id = node_id
                break
        if not current_node_id:
            return []

    messages = []
    current_id = current_node_id

    while current_id:
        node = mapping.get(current_id)
        if not node:
            break

        message = node.get("message")
        if message:
            author = message.get("author", {}).get("role")
            content = message.get("content", {})
            parts = content.get("parts", [])

            # parts can be a mix of strings and dicts (for multimodal)
            text_parts = [p for p in parts if isinstance(p, str)]
            if text_parts and author:
                messages.append(
                    {"role": author, "content": "".join(text_parts).strip()}
                )

        current_id = node.get("parent")

    # Reverse to chronological order (root to leaf)
    return list(reversed(messages))


def process_exports(input_dir: str, output_dir: str):
    """Parse conversations and categorize them into RAG, LoRA, and Skipped."""
    input_path = Path(input_dir)
    output_path = Path(output_dir)

    output_path.mkdir(parents=True, exist_ok=True)

    lora_out = output_path / "training_coding.jsonl"
    rag_out = output_path / "context_rag.jsonl"
    skipped_out = output_path / "skipped_conversations.log"

    classifier = DomainClassifier()

    lora_count = 0
    rag_count = 0
    skipped_count = 0

    lora_target_domains = {"software_engineering", "systems_administration"}
    rag_target_domains = {"ai_ml"}

    # Also gather some basic keywords to override missing classifier rules
    rag_keywords = [
        "Birtha",
        "Claw",
        "mbmh",
        "OpenFOAM",
        "DOE",
        "architecture",
        "RAG",
        "LLM",
    ]

    json_files = list(input_path.glob("conversations-*.json"))

    if not json_files:
        logger.warning(f"No conversations-*.json files found in {input_dir}")
        return

    logger.info(f"Processing {len(json_files)} export files...")

    with lora_out.open("w") as flo, rag_out.open("w") as frac, skipped_out.open(
        "w"
    ) as fsk:
        for json_file in json_files:
            logger.info(f"Reading {json_file}...")
            with open(json_file, "r", encoding="utf-8") as jf:
                try:
                    conversations = json.load(jf)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse {json_file}: {e}")
                    continue

            for conv in conversations:
                title = conv.get("title", "Untitled")
                conv_id = conv.get("conversation_id", "unknown")
                mappings = conv.get("mapping", {})
                current_node = conv.get("current_node")

                messages = reconstruct_conversation(mappings, current_node)

                if not messages:
                    fsk.write(f"SKIPPED_EMPTY | {conv_id} | {title}\n")
                    skipped_count += 1
                    continue

                # Combine user and assistant text for classification
                full_text = f"{title}\n" + "\n".join([m["content"] for m in messages])

                if len(full_text) < 150:
                    fsk.write(f"SKIPPED_TOO_SHORT | {conv_id} | {title}\n")
                    skipped_count += 1
                    continue

                # Check for explicit keywords that strongly mandate RAG
                direct_rag = any(kw.lower() in full_text.lower() for kw in rag_keywords)

                primary_domain = classifier.get_primary_domain(
                    full_text, threshold=0.15
                )

                # Routing logic
                # LoRA (coding examples / debugging)
                if (
                    primary_domain in lora_target_domains
                    and len(messages) >= 3
                    and not direct_rag
                ):
                    # Save as a turn-based jsonl for LoRA format
                    record = {
                        "id": conv_id,
                        "title": title,
                        "domain": primary_domain,
                        "conversations": messages,
                    }
                    flo.write(json.dumps(record) + "\n")
                    lora_count += 1

                # RAG (architecture, conceptual ML, specific projects)
                elif primary_domain in rag_target_domains or direct_rag:
                    record = {
                        "id": conv_id,
                        "title": title,
                        "domain": primary_domain if primary_domain else "rag_override",
                        "content": full_text,
                    }
                    frac.write(json.dumps(record) + "\n")
                    rag_count += 1

                else:
                    domain_label = primary_domain if primary_domain else "none"
                    fsk.write(
                        f"SKIPPED_DOMAIN_{domain_label.upper()} | {conv_id} | {title}\n"
                    )
                    skipped_count += 1

    logger.info("--- Export Processing Complete ---")
    logger.info(f"LoRA Records Generated: {lora_count}")
    logger.info(f"RAG Records Generated: {rag_count}")
    logger.info(f"Skipped Conversations: {skipped_count}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Parse ChatGPT Export JSON into Training/Context datasets."
    )
    parser.add_argument(
        "--input",
        "-i",
        type=str,
        required=True,
        help="Directory containing conversations-*.json files",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="data/",
        help="Output directory for jsonl datasets",
    )
    args = parser.parse_args()

    process_exports(args.input, args.output)
