import csv, io, json, time, requests
from datetime import datetime, timezone
from collections import defaultdict

S=requests.Session()
S.headers.update({"User-Agent":"OneMain-Legislative-Coverage-Finder/3.0"})
CENSUS="https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Legislative/MapServer"

def get(url, **kwargs):
    for n in range(7):
        try:
            r=S.get(url,timeout=45,**kwargs)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            if n==6: raise
            wait=min(2**n,60)
            print(f"RETRY {wait}s {url}: {e}",flush=True)
            time.sleep(wait)

def census_district(lat,lng,layer):
    r=get(f"{CENSUS}/{layer}/query",params={
        "f":"json","geometry":f"{lng},{lat}",
        "geometryType":"esriGeometryPoint","inSR":"4326",
        "spatialRel":"esriSpatialRelIntersects",
        "outFields":"BASENAME,NAME,STATE","returnGeometry":"false"})
    fs=r.json().get("features",[])
    if not fs:return ""
    a=fs[0]["attributes"]
    return str(a.get("BASENAME") or a.get("NAME") or "").strip()

def norm(d):
    s=str(d or "").strip()
    # Census/Open States generally agree numerically; remove harmless leading zeros.
    return str(int(s)) if s.isdigit() else s.lower().replace("district","").strip()

branches=json.load(open("branches.json",encoding="utf-8"))["branches"]
district_branches=defaultdict(list)

# TIGERweb Legislative MapServer: layer 1 upper, layer 2 lower (2026 vintage).
for i,b in enumerate(branches,1):
    upper=census_district(b["lat"],b["lng"],1)
    lower=census_district(b["lat"],b["lng"],2)
    item={"name":b["name"],"address":f'{b["city"]}, {b["state"]}',
          "lat":b["lat"],"lng":b["lng"]}
    if upper: district_branches[(b["state"],"upper",norm(upper))].append(item)
    if lower: district_branches[(b["state"],"lower",norm(lower))].append(item)
    print(f"CENSUS {i}/{len(branches)} {b['state']} upper={upper} lower={lower}",flush=True)

states=sorted({b["state"] for b in branches})
people=[]
for i,state in enumerate(states,1):
    url=f"https://data.openstates.org/people/current/{state}.csv"
    r=get(url)
    rows=list(csv.DictReader(io.StringIO(r.text)))
    matched=0
    for row in rows:
        level=(row.get("current_chamber") or "").strip().lower()
        if level not in ("upper","lower"): continue
        district=(row.get("current_district") or "").strip()
        bs=district_branches.get((state,level,norm(district)),[])
        if not bs: continue
        people.append({
            "name":row.get("name","").strip(),
            "state":state,
            "level":level,
            "chamber":"State Senate" if level=="upper" else "State House / Assembly",
            "district":district,
            "party":row.get("current_party","").strip(),
            "branches":bs
        })
        matched+=1
    print(f"CSV {i}/{len(states)} {state}: {len(rows)} current legislators, {matched} with branch coverage",flush=True)

data={"updated":datetime.now(timezone.utc).date().isoformat(),
      "branch_count":len(branches),
      "legislators":sorted(people,key=lambda x:(x["state"],x["name"]))}
json.dump(data,open("coverage.json","w",encoding="utf-8"),indent=2)
print(f"DONE: {len(people)} legislators with OneMain branch coverage",flush=True)
