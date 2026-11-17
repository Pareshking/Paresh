"""Live acceptance for one immutable R2 research pin.

With --as-of and --revision, exactly that revision. Without both, the dataset's
newest published revision (its current pointer), resolved first and then read
through the same pinned path (owner, 17 Nov 2026: use the latest copy, so
retention need not keep an old one only for this check).
"""
from __future__ import annotations
import argparse, json
from r2.consumers.r2_research import R2ResearchPin, read_pinned_dataset
from src.storage.r2 import R2Archive, R2Config
from src.storage.reader import R2DatasetIntegrityError, R2DatasetReader

def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("--dataset",required=True)
    p.add_argument("--as-of",default="")
    p.add_argument("--revision",default="")
    args=p.parse_args()
    if bool(args.as_of) != bool(args.revision):
        p.error("give --as-of and --revision together, or neither for the newest revision")
    reader=R2DatasetReader(R2Archive(R2Config.from_env()))
    if not args.as_of:
        ref=reader.resolve_current(args.dataset)
        args.as_of, args.revision = ref.as_of, ref.revision_sha256
    pin=R2ResearchPin(args.dataset,args.as_of,args.revision)
    try:
        data=read_pinned_dataset(reader,pin=pin)
    except (R2DatasetIntegrityError, ValueError) as exc:
        raise SystemExit(f"R2 research consumer acceptance failed: {exc}") from exc
    print(json.dumps({"dataset":args.dataset,"as_of":args.as_of,"revision_sha256":args.revision,"rows":len(data.frame),"columns":list(data.frame.columns),"source":"r2-immutable-revision","acceptance":"PASS"},sort_keys=True))
    return 0
if __name__=="__main__":
    raise SystemExit(main())
