import os,json,time,requests
from datetime import datetime,timezone
from collections import defaultdict

KEY=os.environ["OPENSTATES_API_KEY"]
S=requests.Session()
S.headers.update({"User-Agent":"OneMain-Legislative-Coverage-Finder/2.0"})
CENSUS="https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Legislative/MapServer"
STATE_NAMES={"AL":"al","AK":"ak","AZ":"az","AR":"ar","CA":"ca","CO":"co","CT":"ct","DE":"de","FL":"fl","GA":"ga","HI":"hi","ID":"id","IL":"il","IN":"in","IA":"ia","KS":"ks","KY":"ky","LA":"la","ME":"me","MD":"md","MA":"ma","MI":"mi","MN":"mn","MS":"ms","MO":"mo","MT":"mt","NE":"ne","NV":"nv","NH":"nh","NJ":"nj","NM":"nm","NY":"ny","NC":"nc","ND":"nd","OH":"oh","OK":"ok","OR":"or","PA":"pa","RI":"ri","SC":"sc","SD":"sd","TN":"tn","TX":"tx","UT":"ut","VT":"vt","VA":"va","WA":"wa","WV":"wv","WI":"wi","WY":"wy"}

def census_district(lat,lng,layer):
    url=f"{CENSUS}/{layer}/query"
    params={"f":"json","geometry":f"{lng},{lat}","geometryType":"esriGeometryPoint",
            "inSR":"4326","spatialRel":"esriSpatialRelIntersects",
            "outFields":"BASENAME,NAME,STATE","returnGeometry":"false"}
    for n in range(6):
        try:
            r=S.get(url,params=params,timeout=30); r.raise_for_status()
            fs=r.json().get("features",[])
            return str((fs[0]["attributes"].get("BASENAME") or fs[0]["attributes"].get("NAME") or "")).strip() if fs else ""
        except requests.RequestException:
            time.sleep(2**n)
    return ""

def roster(state):
    # One roster pull per state (paginated), not one Open States call per branch.
    jurisdiction=f"ocd-jurisdiction/country:us/state:{STATE_NAMES[state]}/government"
    page=1; out=[]
    while True:
        r=S.get("https://v3.openstates.org/people",
                params={"jurisdiction":jurisdiction,"page":page,"per_page":100},
                headers={"X-API-KEY":KEY},timeout=45)
        if r.status_code==429:
            print("Open States roster rate limit; waiting 60s",flush=True); time.sleep(60); continue
        r.raise_for_status()
        j=r.json(); out.extend(j.get("results",[]))
        pag=j.get("pagination",{})
        if page >= pag.get("max_page",page): break
        page+=1; time.sleep(1)
    return out

branches=json.load(open("branches.json",encoding="utf-8"))["branches"]
district_branches=defaultdict(list)

# Census layers: 1 = 2026 upper, 2 = 2026 lower.
for i,b in enumerate(branches,1):
    upper=census_district(b["lat"],b["lng"],1)
    lower=census_district(b["lat"],b["lng"],2)
    item={"name":b["name"],"address":f'{b["city"]}, {b["state"]}',"lat":b["lat"],"lng":b["lng"]}
    if upper: district_branches[(b["state"],"upper",upper)].append(item)
    if lower: district_branches[(b["state"],"lower",lower)].append(item)
    print(f"CENSUS {i}/{len(branches)} {b['state']} upper={upper} lower={lower}",flush=True)
    time.sleep(.05)

people=[]
for si,state in enumerate(sorted({b["state"] for b in branches}),1):
    rs=roster(state)
    print(f"ROSTER {si} {state}: {len(rs)} people",flush=True)
    for person in rs:
        role=person.get("current_role") or {}
        c=role.get("org_classification") or ""
        if c in ("upper","upper_chamber"): level="upper"; chamber="State Senate"
        elif c in ("lower","lower_chamber"): level="lower"; chamber="State House / Assembly"
        else: continue
        district=str(role.get("district") or "").strip()
        bs=district_branches.get((state,level,district),[])
        if not bs: continue
        people.append({"name":person["name"],"state":state,"level":level,"chamber":chamber,
                       "district":district,"party":person.get("party",""),"branches":bs})
    time.sleep(2)

data={"updated":datetime.now(timezone.utc).date().isoformat(),"branch_count":len(branches),
      "legislators":sorted(people,key=lambda x:(x["state"],x["name"]))}
json.dump(data,open("coverage.json","w",encoding="utf-8"),indent=2)
print(f"DONE: {len(people)} legislators with branch coverage",flush=True)
