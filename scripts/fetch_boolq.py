"""Download the first 100 BoolQ validation rows into data/boolq_100.jsonl."""

import json
import urllib.request
from pathlib import Path

URL = (
    "https://datasets-server.huggingface.co/rows"
    "?dataset=google/boolq&config=default&split=validation&offset=0&length=100"
)
OUT = Path(__file__).parent.parent / "data" / "boolq_100.jsonl"


def main() -> None:
    with urllib.request.urlopen(URL) as resp:
        rows = json.load(resp)["rows"]
    with OUT.open("w") as f:
        for r in rows:
            row = r["row"]
            record = {
                "id": f"boolq-val-{r['row_idx']}",
                "question": row["question"],
                "passage": row["passage"],
                "answer": row["answer"],
            }
            f.write(json.dumps(record) + "\n")
    print(f"wrote {len(rows)} tasks to {OUT}")


if __name__ == "__main__":
    main()
