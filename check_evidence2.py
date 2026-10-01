"""Check evidence exactly as the validator does - NO front matter stripping"""
import json
from pathlib import Path

CORPUS = Path("data/technology_store")
DATASET = Path("golden_dataset.json")

# Load corpus exactly as validator does - RAW text, no stripping
corpus_texts = {}
for md_file in sorted(CORPUS.glob("*.md")):
    text = md_file.read_text(encoding="utf-8")
    corpus_texts[md_file.name] = text
    print(f"Loaded {md_file.name}: {len(text)} chars")

# Load dataset
with open(DATASET, encoding="utf-8") as f:
    dataset = json.load(f)

# Check each context
problems = []
for pair in dataset["qa_pairs"]:
    for i, ctx in enumerate(pair["contexts"]):
        src = ctx["source_doc"]
        txt = ctx["text"]
        if src not in corpus_texts:
            problems.append(f"{pair['id']} ctx[{i+1}]: source {src} not found")
            continue
        corpus = corpus_texts[src]
        if txt in corpus:
            print(f"OK: {pair['id']} ctx[{i+1}] in {src}")
        else:
            problems.append(f"{pair['id']} ctx[{i+1}]: NOT in {src}: {txt[:60]!r}")
            # Find similar
            for line in corpus.split('\n'):
                if any(word in line for word in txt.split()[:4]):
                    if len(line) < 200:
                        print(f"  Similar: {line[:120]!r}")

print(f"\n=== {len(problems)} PROBLEMS ===")
for p in problems:
    print(p)
