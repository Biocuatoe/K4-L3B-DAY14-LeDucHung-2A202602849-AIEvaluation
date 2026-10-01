"""Debug exact string comparison"""
import json
from pathlib import Path

# Load corpus
corpus_path = Path("data/technology_store/02_orders_and_payments.md")
corpus_raw = corpus_path.read_bytes()
corpus_text = corpus_raw.decode("utf-8")

# Load dataset
with open("golden_dataset.json", encoding="utf-8") as f:
    ds = json.load(f)

for pair in ds["qa_pairs"]:
    if pair["id"] in ("M03", "H01"):
        txt = pair["contexts"][0]["text"]
        print(f"=== {pair['id']} ctx[0] ===")
        print(f"Dataset text ({len(txt)} chars):")
        print(repr(txt))
        print()
        
        # Find in corpus
        if txt in corpus_text:
            print("FOUND in corpus!")
        else:
            print("NOT found in corpus.")
            # Find the longest prefix that exists
            for i in range(len(txt), 0, -1):
                prefix = txt[:i]
                if prefix in corpus_text:
                    print(f"Longest matching prefix ({i} chars): {repr(prefix)}")
                    break
            # Find what comes after in corpus
            idx = corpus_text.find("cancelled from the account page")
            if idx >= 0:
                print(f"Corpus context around 'cancelled': {repr(corpus_text[idx:idx+100])}")
        print()

# Also check A03
for pair in ds["qa_pairs"]:
    if pair["id"] == "A03":
        for i, ctx in enumerate(pair["contexts"]):
            txt = ctx["text"]
            src = ctx["source_doc"]
            corpus_path = Path(f"data/technology_store/{src}")
            corpus_text = corpus_path.read_text(encoding="utf-8")
            print(f"=== A03 ctx[{i}] in {src} ===")
            print(f"Dataset text ({len(txt)} chars): {repr(txt)}")
            if txt in corpus_text:
                print("FOUND!")
            else:
                print("NOT found.")
                # Try each word
                words = txt.split()
                for w in words[:5]:
                    if w in corpus_text:
                        print(f"  Word '{w}' found")
            print()
