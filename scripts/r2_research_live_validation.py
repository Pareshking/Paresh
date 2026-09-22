"""Live acceptance for one explicit immutable R2 research pin."""
from __future__ import annotations
import argparse, json
from r2.consumers.r2_research import R2ResearchPin, read_pinned_dataset
from src.storage.r2 import R2Archive, R2Config
from src.storage.reader import R2DatasetReader

def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("--dataset",required=True)
    p.add_argument("--as-of",required=True)
    p.add_argument("--revision",required=True)
    args=p.parse_args()
    reader=R2DatasetReader(R2Archive(R2Config.from_env()))
    pin=R2ResearchPin(args.dataset,args.as_of,args.revision)
    data=read_pinned_dataset(reader,pin=pin)
    print(json.dumps({"dataset":args.dataset,"as_of":args.as_of,"revision_sha256":args.revision,"rows":len(data.frame),"columns":list(data.frame.columns),"source":"r2-immutable-revision","acceptance":"PASS"},sort_keys=True))
    return 0
if __name__=="__main__":
    raise SystemExit(main())
