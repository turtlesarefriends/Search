import os,json,time,requests,random
from datetime import datetime,timezone

KEY=os.environ["OPENSTATES_API_KEY"]
S=requests.Session()
S.headers.update({"User-Agent":"OneMain-Legislative-Coverage-Finder/1.0","X-API-KEY":KEY})
CHECKPOINT="checkpoint.json"

def lookup(lat,lng):
    wait=15
    while True:
        try:
            r=S.get("https://v3.openstates.org/people.geo",params={"lat":lat,"lng":lng},timeout=45)
            if r.status_code==429:
                retry=r.headers.get("Retry-After")
                delay=int(retry) if retry and retry.isdigit() else wait
                print(f"RATE LIMITED — waiting {delay}s",flush=True)
                time.sleep(delay)
                wait=min(wait*2,300)
                continue
            r.raise_for_status()
            return r.json().get("results",[])
        except requests.RequestException as e:
            print(f"NETWORK ERROR — waiting {wait}s: {e}",flush=True)
            time.sleep(wait); wait=min(wait*2,300)

def role(p):
    r=p.get("current_role") or {}
    c=r.get("org_classification") or ""
    if c in ("upper","upper_chamber"): return "upper","State Senate",str(r.get("district") or "")
    if c in ("lower","lower_chamber"): return "lower","State House / Assembly",str(r.get("district") or "")
    return None

branches=json.load(open("branches.json",encoding="utf-8"))["branches"]
if os.path.exists(CHECKPOINT):
    cp=json.load(open(CHECKPOINT,encoding="utf-8"))
    start=cp.get("next_index",0); people=cp.get("people",{})
    print(f"RESUMING AT {start+1}/{len(branches)}",flush=True)
else:
    start=0; people={}

for idx in range(start,len(branches)):
    b=branches[idx]
    results=lookup(b["lat"],b["lng"])
    for person in results:
        rr=role(person)
        if not rr: continue
        level,chamber,district=rr
        pid=person["id"]
        rec=people.setdefault(pid,{"name":person["name"],"state":b["state"],"level":level,
            "chamber":chamber,"district":district,"party":person.get("party",""),"branches":[]})
        branch={"name":b["name"],"address":f'{b["city"]}, {b["state"]}',"lat":b["lat"],"lng":b["lng"]}
        if branch not in rec["branches"]: rec["branches"].append(branch)

    # Persist locally every successful branch. GitHub workflow publishes checkpoint at job end.
    json.dump({"next_index":idx+1,"people":people},open(CHECKPOINT,"w",encoding="utf-8"))
    print(f"{idx+1}/{len(branches)} {b['city']}, {b['state']}",flush=True)
    time.sleep(1.25 + random.random()*.5)

data={"updated":datetime.now(timezone.utc).date().isoformat(),"branch_count":len(branches),
      "legislators":sorted(people.values(),key=lambda x:(x["state"],x["name"]))}
json.dump(data,open("coverage.json","w",encoding="utf-8"),indent=2)
if os.path.exists(CHECKPOINT): os.remove(CHECKPOINT)
print(f"DONE: {len(people)} legislators from {len(branches)} branches",flush=True)
