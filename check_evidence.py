"""Extract exact text substrings from corpus for fixing golden_dataset.json"""
import json
from pathlib import Path

CORPUS = Path("data/technology_store")
DATASET = Path("golden_dataset.json")

# Load corpus
corpus_texts = {}
for md_file in CORPUS.glob("*.md"):
    text = md_file.read_text(encoding="utf-8")
    # Strip front matter
    if text.startswith("---"):
        lines = text.splitlines()
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == "---":
                text = "\n".join(lines[i+1:])
                break
    corpus_texts[md_file.name] = text

# Load dataset
with open(DATASET, encoding="utf-8") as f:
    dataset = json.load(f)

# Check each context's text against corpus
problems = []
for pair in dataset["qa_pairs"]:
    for i, ctx in enumerate(pair["contexts"]):
        src = ctx["source_doc"]
        txt = ctx["text"]
        if src not in corpus_texts:
            problems.append(f"{pair['id']} ctx[{i+1}]: source {src} not found")
            continue
        if txt not in corpus_texts[src]:
            problems.append(f"{pair['id']} ctx[{i+1}]: text NOT found in {src}")
            # Try to find similar text
            corpus = corpus_texts[src]
            if txt[:50] in corpus:
                print(f"  Partial match found: {txt[:50]!r}")
            # Find what's different
            for line in corpus.split('\n'):
                if txt[:30] in line:
                    print(f"  Similar line: {line[:80]!r}")
        else:
            print(f"OK: {pair['id']} ctx[{i+1}] in {src}")

print("\n--- Problems ---")
for p in problems:
    print(p)
