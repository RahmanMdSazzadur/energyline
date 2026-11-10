"""Run inside the KiCad container: official footprints, two-layer routing, build exports."""
from pathlib import Path
import json, csv, math, heapq, itertools
import xml.etree.ElementTree as ET
import pcbnew as k
P=Path('/project'); components=json.loads(Path('/project/pcb_components.json').read_text())
B=k.BOARD(); mm=k.FromMM
pt=lambda x,y:k.VECTOR2I(mm(x),mm(y))
root=ET.parse(P/'S3_interface.net.xml').getroot(); assignments={}; nets={}
for n in root.findall('./nets/net'):
 name=n.attrib['name']; net=k.NETINFO_ITEM(B,name); B.Add(net); nets[name]=net
 for pin in n.findall('node'):assignments[pin.attrib['ref'],pin.attrib['pin']]=name
values={c.attrib['ref']:c.findtext('value') for c in root.findall('./components/comp')}
footprints={}; pads=[]
for ref,c in components.items():
 lib,name=c['footprint'].split(':'); f=k.FootprintLoad('/usr/share/kicad/footprints/'+lib+'.pretty',name)
 assert f, c['footprint']
 if ref=='F1':
  for model in f.Models(): model.m_Filename='${KIPRJMOD}/models/Fuse_372_clearance_envelope.wrl'
 f.SetReference(ref); f.SetValue(values[ref]); f.SetFPID(k.LIB_ID(lib,name)); f.SetPosition(pt(50+c['x'],50+c['y']))
 f.SetOrientationDegrees(c['angle']); B.Add(f); footprints[ref]=f
 f.Value().SetVisible(False)
 f.SetAttributes(f.GetAttributes() & ~k.FP_EXCLUDE_FROM_BOM)
 for p in f.Pads():
  n=assignments[ref,p.GetNumber()];p.SetNet(nets[n]);pads.append((p,n))
for i,(x,y) in enumerate([(5,5),(75,5),(75,65),(5,65)],1):
 f=k.FootprintLoad('/usr/share/kicad/footprints/MountingHole.pretty','MountingHole_3.2mm_M3');f.SetReference('H'+str(i));f.SetValue('M3');f.SetPosition(pt(50+x,50+y));B.Add(f);f.SetAttributes(f.GetAttributes() | k.FP_BOARD_ONLY | k.FP_EXCLUDE_FROM_BOM | k.FP_EXCLUDE_FROM_POS_FILES);f.Value().SetVisible(False);f.Reference().SetVisible(False)
for a,b in [((50,50),(130,50)),((130,50),(130,120)),((130,120),(50,120)),((50,120),(50,50))]:
 s=k.PCB_SHAPE();s.SetShape(k.SHAPE_T_SEGMENT);s.SetStart(pt(*a));s.SetEnd(pt(*b));s.SetLayer(k.Edge_Cuts);s.SetWidth(mm(.05));B.Add(s)
def text(t,x,y,size=1,layer=k.F_SilkS):
 z=k.PCB_TEXT(B);z.SetText(t);z.SetPosition(pt(50+x,50+y));z.SetTextSize(pt(size,size));z.SetTextThickness(mm(.15));z.SetLayer(layer);B.Add(z)
text('ENERGYLINE / S3',39,5,1.5);text('5V BENCH INTERFACE  |  REV A',39,8,1)
text('POWER IN',13,11,.9);text('EXT PERMIT',58,11,.9)
text('PART',54,31,.9);text('COVER',54,43,.9);text('CLAMP LED',69,50,.85)
text('5V ONLY / LED LOAD',40,66,1);text('C',62,60,.8);text('B',64.54,60,.8);text('E',67.08,60,.8)
# Connector pin legends are explicit to prevent wiring mistakes.
for i,label in enumerate(['+5V','GND','CMD','PART','COVER','PERMIT']):text(label,16,38+i*2.54,.85)
text('+',7,16,.8);text('-',7,18.54,.8);text('GND',58,39,.8);text('GND',58,51,.8)
# Project design rules. No ignored checks or DRC exclusions.
pro=json.loads((P/'S3_interface.kicad_pro').read_text());pro.setdefault('board',{}).setdefault('design_settings',{}).setdefault('rules',{}).update({'min_clearance':.25,'min_track_width':.3,'min_via_diameter':.8,'min_through_hole_diameter':.3,'min_hole_clearance':.25,'min_copper_edge_clearance':.5})
(P/'S3_interface.kicad_pro').write_text(json.dumps(pro,indent=2))
# Grid A* router; conservative geometry is checked subsequently by native KiCad DRC.
S=.25; W=320; H=280
occupied=[{},{}]; obstacles={}; holecenters=[(5,5),(75,5),(75,65),(5,65)]
for p,n in pads:
 x=k.ToMM(p.GetPosition().x)-50;y=k.ToMM(p.GetPosition().y)-50
 sx=k.ToMM(p.GetSize().x)/2;sy=k.ToMM(p.GetSize().y)/2
 # Bounding boxes deliberately overestimate round pads.
 for ix in range(max(0,int((x-sx-.48)/S)),min(W,int((x+sx+.48)/S)+2)):
  for iy in range(max(0,int((y-sy-.48)/S)),min(H,int((y+sy+.48)/S)+2)):
   if abs(ix*S-x)<=sx+.48 and abs(iy*S-y)<=sy+.48:obstacles.setdefault((ix,iy),set()).add(n)

def free(x,y,l,n,via=False):
 if x<5 or y<5 or x>W-5 or y>H-5:return False
 if any(math.hypot(x*S-a,y*S-b)<3.6 for a,b in holecenters):return False
 if obstacles.get((x,y),{n})-{n}:return False
 radius=4 if via else 3
 for dx in range(-radius,radius+1):
  for dy in range(-radius,radius+1):
   if dx*dx+dy*dy > (3.5 if via else 2.7)**2:continue
   for lay in ([0,1] if via else [l]):
    other=occupied[lay].get((x+dx,y+dy))
    if other is not None and other!=n:return False
 if via:
  # Larger via needs extra separation from other-net pad bounding boxes.
  for dx in range(-1,2):
   for dy in range(-1,2):
    if obstacles.get((x+dx,y+dy),{n})-{n}:return False
 return True

def route(a,b,n):
 ax,ay=a;bx,by=b;starts=[(ax,ay,0),(ax,ay,1)];goals={(bx,by,0),(bx,by,1)}
 dist={v:0 for v in starts};prev={};Q=[];serial=itertools.count()
 h=lambda x,y:abs(x-bx)+abs(y-by)
 for v in starts:heapq.heappush(Q,(h(*v[:2]),next(serial),0,v))
 while Q:
  _,_,cost,v=heapq.heappop(Q)
  if cost!=dist[v]:continue
  if v in goals:
   path=[v]
   while v in prev:v=prev[v];path.append(v)
   return path[::-1]
  x,y,l=v
  for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)]:
   u=(x+dx,y+dy,l)
   if not free(*u,n):continue
   nc=cost+1+(0.08 if (l==0 and dy) or (l==1 and dx) else 0)
   if nc<dist.get(u,1e30):dist[u]=nc;prev[u]=v;heapq.heappush(Q,(nc+h(*u[:2]),next(serial),nc,u))
  u=(x,y,1-l)
  if free(x,y,l,n,True):
   nc=cost+24
   if nc<dist.get(u,1e30):dist[u]=nc;prev[u]=v;heapq.heappush(Q,(nc+h(x,y),next(serial),nc,u))
 raise RuntimeError('No route for '+n)

def track(a,b,l,n):
 if a==b:return
 t=k.PCB_TRACK(B);t.SetStart(pt(50+a[0],50+a[1]));t.SetEnd(pt(50+b[0],50+b[1]));t.SetWidth(mm(.35));t.SetLayer(k.F_Cu if l==0 else k.B_Cu);t.SetNet(nets[n]);B.Add(t)
by={}
for p,n in pads:
 xy=(k.ToMM(p.GetPosition().x)-50,k.ToMM(p.GetPosition().y)-50);by.setdefault(n,[]).append(xy)
edges=[]
for n,ps in by.items():
 tree=[ps[0]];left=ps[1:]
 while left:
  _,a,b=min((math.dist(a,b),a,b) for a in tree for b in left)
  edges.append((math.dist(a,b),n,a,b));tree.append(b);left.remove(b)
for length,n,a,b in sorted(edges):
 ga=tuple(round(v/S) for v in a);gb=tuple(round(v/S) for v in b)
 path=route(ga,gb,n)
 for x,y,l in path:occupied[l][x,y]=n
 track(a,(ga[0]*S,ga[1]*S),path[0][2],n);track((gb[0]*S,gb[1]*S),b,path[-1][2],n)
 # Merge collinear steps, leaving a segment only at corners/layer transitions.
 start=path[0];direction=None
 for j in range(1,len(path)):
  old=path[j-1];cur=path[j]
  d=(cur[0]-old[0],cur[1]-old[1],cur[2]-old[2])
  if d[2]:
   track((start[0]*S,start[1]*S),(old[0]*S,old[1]*S),old[2],n)
   v=k.PCB_VIA(B);v.SetPosition(pt(50+cur[0]*S,50+cur[1]*S));v.SetWidth(mm(.8));v.SetDrill(mm(.4));v.SetViaType(k.VIATYPE_THROUGH);v.SetLayerPair(k.F_Cu,k.B_Cu);v.SetNet(nets[n]);B.Add(v)
   occupied[0][cur[0],cur[1]]=n;occupied[1][cur[0],cur[1]]=n;start=cur;direction=None
  elif direction is not None and d!=direction:
   track((start[0]*S,start[1]*S),(old[0]*S,old[1]*S),old[2],n);start=old;direction=d
  else:direction=d
 last=path[-1];track((start[0]*S,start[1]*S),(last[0]*S,last[1]*S),last[2],n)
 print('Routed',n,flush=True)
B.SetCopperLayerCount(2);B.BuildConnectivity();k.SaveBoard(str(P/'S3_interface.kicad_pcb'),B)
with (P/'assembly_bom.csv').open('w') as f:
 w=csv.writer(f);w.writerow(['Reference','Value','Footprint','Assembly specification'])
 for ref,c in components.items():w.writerow([ref,values[ref],c['footprint'],c['spec']])
print('Saved routed board')
