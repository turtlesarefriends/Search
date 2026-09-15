import io,json,time,requests,zipfile,subprocess,sys
from datetime import datetime,timezone
from collections import defaultdict

try:
    import yaml
except ImportError:
    subprocess.check_call([sys.executable,"-m","pip","install","PyYAML"])
    import yaml

S=requests.Session()
S.headers.update({"User-Agent":"OneMain-Legislative-Coverage-Finder/4.0"})
CENSUS="https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Legislative/MapServer"

def get(url,**kwargs):
    for n in range(6):
        try:
            r=S.get(url,timeout=60,**kwargs); r.raise_for_status(); return r
        except requests.RequestException as e:
            if n==5: raise
            w=min(2**n,30); print(f"RETRY {w}s: {e}",flush=True); time.sleep(w)

def census(lat,lng,layer):
    r=get(f"{CENSUS}/{layer}/query",params={"f":"json","geometry":f"{lng},{lat}",
      "geometryType":"esriGeometryPoint","inSR":"4326","spatialRel":"esriSpatialRelIntersects",
      "outFields":"BASENAME,NAME","returnGeometry":"false"})
    fs=r.json().get("features",[])
    if not fs:return ""
    a=fs[0]["attributes"]
    return str(a.get("BASENAME") or a.get("NAME") or "").strip()

def norm(v):
    s=str(v or "").strip()
    return str(int(s)) if s.isdigit() else s.lower().replace("district","").strip()

branches=json.load(open("branches.json",encoding="utf-8"))["branches"]
db=defaultdict(list)
for i,b in enumerate(branches,1):
    u,l=census(b["lat"],b["lng"],1),census(b["lat"],b["lng"],2)
    x={"name":b["name"],"address":f'{b["city"]}, {b["state"]}',"lat":b["lat"],"lng":b["lng"]}
    if u: db[(b["state"].lower(),"upper",norm(u))].append(x)
    if l: db[(b["state"].lower(),"lower",norm(l))].append(x)
    print(f"CENSUS {i}/{len(branches)} {b['state']} upper={u} lower={l}",flush=True)

# Download the public Open States People GitHub repository as ONE archive.
# This bypasses both the API and data.openstates.org.
print("Downloading current legislator repository from GitHub...",flush=True)
z=zipfile.ZipFile(io.BytesIO(get("https://github.com/openstates/people/archive/refs/heads/main.zip").content))

people=[]
seen=set()
states={b["state"].lower() for b in branches}
members=[n for n in z.namelist() if "/data/" in n and "/legislature/" in n and n.endswith((".yml",".yaml"))]
for j,n in enumerate(members,1):
    parts=n.split("/")
    try:
        k=parts.index("data"); st=parts[k+1].lower()
    except (ValueError,IndexError): continue
    if st not in states: continue
    try: person=yaml.safe_load(z.read(n)) or {}
    except Exception as e:
        print(f"SKIP YAML {n}: {e}",flush=True); continue
    name=str(person.get("name") or "").strip()
    parties=person.get("party") or []
    current_party=""
    for party in parties:
        if not party.get("end_date"): current_party=party.get("name","")
    if not current_party and parties: current_party=parties[-1].get("name","")
    for role in person.get("roles") or []:
        level=str(role.get("type") or "").lower()
        if level not in ("upper","lower"): continue
        district=str(role.get("district") or "").strip()
        bs=db.get((st,level,norm(district)),[])
        if not bs: continue
        key=(person.get("id") or name,level,district)
        if key in seen: continue
        seen.add(key)
        people.append({"name":name,"state":st.upper(),"level":level,
          "chamber":"State Senate" if level=="upper" else "State House / Assembly",
          "district":district,"party":current_party,"branches":bs})
    if j%250==0: print(f"LEGISLATORS scanned {j}/{len(members)}",flush=True)

data={"updated":datetime.now(timezone.utc).date().isoformat(),"branch_count":len(branches),
      "legislators":sorted(people,key=lambda x:(x["state"],x["name"]))}
json.dump(data,open("coverage.json","w",encoding="utf-8"),indent=2)
print(f"DONE: {len(people)} legislators with OneMain branch coverage",flush=True)
