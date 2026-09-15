import os, json, time, requests
from datetime import datetime, timezone

KEY=os.environ["OPENSTATES_API_KEY"]
S=requests.Session()
S.headers.update({"User-Agent":"OneMain-Legislative-Coverage-Finder/1.0","X-API-KEY":KEY})

def lookup(lat,lng):
    for n in range(5):
        r=S.get("https://v3.openstates.org/people.geo",
                params={"lat":lat,"lng":lng}, timeout=30)
        if r.status_code==429:
            time.sleep(2**n); continue
        r.raise_for_status()
        return r.json().get("results",[])
    raise RuntimeError("Open States rate limit persisted")

def current_role(person):
    r=person.get("current_role") or {}
    c=r.get("org_classification") or ""
    if c in ("upper","upper_chamber"):
        return "upper","State Senate",str(r.get("district") or "")
    if c in ("lower","lower_chamber"):
        return "lower","State House / Assembly",str(r.get("district") or "")
    return None

branches=json.load(open("branches.json",encoding="utf-8"))["branches"]
people={}
failures=[]

for i,b in enumerate(branches,1):
    try:
        for person in lookup(b["lat"],b["lng"]):
            role=current_role(person)
            if not role: continue
            level,chamber,district=role
            pid=person["id"]
            rec=people.setdefault(pid,{
                "name":person["name"],
                "state":b["state"],
                "level":level,
                "chamber":chamber,
                "district":district,
                "party":person.get("party",""),
                "branches":[]
            })
            rec["branches"].append({
                "name":b["name"],
                "address":f'{b["city"]}, {b["state"]}',
                "lat":b["lat"],"lng":b["lng"]
            })
        print(f"{i}/{len(branches)} {b['city']}, {b['state']}")
        time.sleep(.08)
    except Exception as e:
        print("FAILED",b,e)
        failures.append({"branch":b,"error":str(e)})

data={
    "updated":datetime.now(timezone.utc).date().isoformat(),
    "branch_count":len(branches),
    "legislators":sorted(people.values(),key=lambda x:(x["state"],x["name"]))
}
json.dump(data,open("coverage.json","w",encoding="utf-8"),indent=2)
json.dump(failures,open("failures.json","w",encoding="utf-8"),indent=2)
print("DONE:",len(people),"legislators;",len(failures),"branch failures")
