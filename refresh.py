import io,json,time,requests,zipfile,subprocess,sys
from datetime import datetime,timezone,date
from collections import defaultdict
try:
 import yaml
except ImportError:
 subprocess.check_call([sys.executable,"-m","pip","install","PyYAML"]); import yaml
S=requests.Session(); S.headers.update({"User-Agent":"OneMain-Legislative-Coverage-Finder/5.0"})
CENSUS="https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Legislative/MapServer"
def get(url,**kw):
 for n in range(6):
  try:
   r=S.get(url,timeout=60,**kw); r.raise_for_status(); return r
  except requests.RequestException as e:
   if n==5: raise
   w=min(2**n,30); print("RETRY",w,"s:",e,flush=True); time.sleep(w)
def census(lat,lng,layer):
 r=get(f"{CENSUS}/{layer}/query",params={"f":"json","geometry":f"{lng},{lat}","geometryType":"esriGeometryPoint","inSR":"4326","spatialRel":"esriSpatialRelIntersects","outFields":"BASENAME,NAME","returnGeometry":"false"})
 fs=r.json().get("features",[])
 if not fs:return ""
 a=fs[0]["attributes"]; return str(a.get("BASENAME") or a.get("NAME") or "").strip()
def norm(v):
 s=str(v or "").strip()
 return str(int(s)) if s.isdigit() else s.lower().replace("district","").strip()
def active_role(roles):
 today=date.today().isoformat(); c=[]
 for r in roles or []:
  typ=str(r.get("type") or "").lower()
  if typ not in ("upper","lower"):continue
  start=str(r.get("start_date") or ""); end=str(r.get("end_date") or "")
  active=(not start or start<=today) and (not end or end>=today)
  c.append((1 if active else 0,start,end,r))
 if not c:return None
 c.sort(key=lambda x:(x[0],x[1],x[2]),reverse=True); return c[0][3]
branches=json.load(open("branches.json",encoding="utf-8"))["branches"]; db=defaultdict(list)
for i,b in enumerate(branches,1):
 u,l=census(b["lat"],b["lng"],1),census(b["lat"],b["lng"],2)
 x={"name":b["name"],"address":f'{b["city"]}, {b["state"]}',"lat":b["lat"],"lng":b["lng"]}
 if u:db[(b["state"].lower(),"upper",norm(u))].append(x)
 if l:db[(b["state"].lower(),"lower",norm(l))].append(x)
 print(f"CENSUS {i}/{len(branches)}",flush=True)
print("Downloading current legislator repository from GitHub...",flush=True)
z=zipfile.ZipFile(io.BytesIO(get("https://github.com/openstates/people/archive/refs/heads/main.zip").content))
states={b["state"].lower() for b in branches}
members=[n for n in z.namelist() if "/data/" in n and "/legislature/" in n and n.endswith((".yml",".yaml"))]
people=[]
for j,n in enumerate(members,1):
 parts=n.split("/")
 try:k=parts.index("data"); st=parts[k+1].lower()
 except (ValueError,IndexError):continue
 if st not in states:continue
 try:person=yaml.safe_load(z.read(n)) or {}
 except Exception:continue
 role=active_role(person.get("roles"))
 if not role:continue
 level=str(role.get("type")).lower(); district=str(role.get("district") or "").strip()
 parties=person.get("party") or []; party=""
 for x in parties:
  end=str(x.get("end_date") or "")
  if not end or end>=date.today().isoformat():party=x.get("name","")
 if not party and parties:party=parties[-1].get("name","")
 people.append({"name":str(person.get("name") or "").strip(),"state":st.upper(),"level":level,"chamber":"State Senate" if level=="upper" else "State House / Assembly","district":district,"party":party,"branches":db.get((st,level,norm(district)),[])})
 if j%250==0:print(f"LEGISLATORS scanned {j}/{len(members)}",flush=True)
by={(p["name"].lower(),p["state"]):p for p in people}; missing=[]
for name,state,district in [("walter hall","WV","58"),("dean jeffries","WV","61"),("clay riley","WV","72")]:
 p=by.get((name,state))
 if not p or norm(p.get("district"))!=norm(district):missing.append(f"{name.title()} ({state}-{district})")
if missing:raise RuntimeError("VALIDATION FAILED — refusing to publish: "+", ".join(missing))
if len(people)<5000:raise RuntimeError(f"VALIDATION FAILED — only {len(people)} current legislators parsed")
data={"updated":datetime.now(timezone.utc).date().isoformat(),"branch_count":len(branches),"legislator_count":len(people),"legislators":sorted(people,key=lambda x:(x["state"],x["name"]))}
json.dump(data,open("coverage.json","w",encoding="utf-8"),indent=2)
print(f"DONE: {len(people)} current legislators",flush=True)
print("VALIDATED: Walter Hall WV-58, Dean Jeffries WV-61, Clay Riley WV-72",flush=True)
