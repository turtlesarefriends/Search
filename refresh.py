import os,re,json,time,requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from collections import defaultdict
from datetime import datetime,timezone

KEY=os.environ["OPENSTATES_API_KEY"]
S=requests.Session(); S.headers["User-Agent"]="OneMain-Legislative-Coverage-Finder/1.0"
STATES="al az ca co de fl ga hi id il in ia ks ky la me md mi mn ms mo mt ne nv nh nj nm ny nc nd oh ok or pa sc sd tn tx ut va wa wv wi wy".split()

def get(url,**kw):
    for n in range(4):
        try:
            r=S.get(url,timeout=35,**kw); r.raise_for_status(); return r
        except Exception:
            if n==3: raise
            time.sleep(2**n)

def discover():
    found={}
    for st in STATES:
        soup=BeautifulSoup(get(f"https://www.onemainfinancial.com/branches/{st}").text,"html.parser")
        # Follow all same-state branch/city links, then inspect their children.
        queue={urljoin("https://www.onemainfinancial.com",a["href"]).split("?")[0] for a in soup.select("a[href]") if f"/branches/{st}/" in a["href"].lower()}
        seen=set()
        while queue:
            u=queue.pop()
            if u in seen: continue
            seen.add(u)
            sp=BeautifulSoup(get(u).text,"html.parser")
            txt=" ".join(sp.stripped_strings)
            # US address ending in the state + ZIP.
            m=re.search(r"(\d{1,6}\s+[^|]{2,120}?,\s*[^,]{2,60},\s*"+st.upper()+r"\s+\d{5}(?:-\d{4})?)",txt)
            if m:
                addr=" ".join(m.group(1).split())
                h=sp.find("h1")
                name=(h.get_text(" ",strip=True) if h else "OneMain Financial Branch")
                found[addr]={"name":name,"address":addr,"url":u,"state":st.upper()}
            for a in sp.select("a[href]"):
                v=urljoin("https://www.onemainfinancial.com",a["href"]).split("?")[0]
                if f"/branches/{st}/" in v.lower() and v not in seen: queue.add(v)
            time.sleep(.08)
    return list(found.values())

def geocode(address):
    r=get("https://geocoding.geo.census.gov/geocoder/locations/onelineaddress",
          params={"address":address,"benchmark":"Public_AR_Current","format":"json"})
    m=r.json().get("result",{}).get("addressMatches",[])
    if not m:return None
    c=m[0]["coordinates"]; return c["y"],c["x"]

def people(lat,lon):
    r=get("https://v3.openstates.org/people.geo",
          params={"lat":lat,"lng":lon},headers={"X-API-KEY":KEY})
    return r.json().get("results",[])

def role(p):
    r=p.get("current_role") or {}
    cls=r.get("org_classification") or ""
    if cls in ("upper","upper_chamber"): level="upper"; chamber="State Senate"
    elif cls in ("lower","lower_chamber"): level="lower"; chamber="State House / Assembly"
    else: return None
    return level,chamber,str(r.get("district") or "")

def main():
    branches=discover()
    out={}
    failures=[]
    for i,b in enumerate(branches,1):
        try:
            ll=geocode(b["address"])
            if not ll: failures.append({"branch":b,"reason":"geocode"}); continue
            for p in people(*ll):
                rr=role(p)
                if not rr: continue
                level,chamber,district=rr
                k=p["id"]
                x=out.setdefault(k,{"name":p["name"],"state":b["state"],"level":level,"chamber":chamber,"district":district,"party":p.get("party",""),"branches":[]})
                x["branches"].append({"name":b["name"],"address":b["address"],"url":b["url"]})
            print(i,len(branches),b["address"])
            time.sleep(.1)
        except Exception as e:
            failures.append({"branch":b,"reason":str(e)})
    data={"updated":datetime.now(timezone.utc).date().isoformat(),"legislators":sorted(out.values(),key=lambda x:(x["state"],x["name"]))}
    os.makedirs("data",exist_ok=True)
    json.dump(data,open("data/coverage.json","w"),indent=2)
    json.dump(failures,open("data/failures.json","w"),indent=2)

if __name__=="__main__": main()
