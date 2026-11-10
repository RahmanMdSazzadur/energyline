"""Generate a native KiCad schematic for the 5 V S3 mock interface."""
import csv
import json
import math
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 's3_interface'
NAMESPACE = uuid.UUID('a5304fa2-e348-4be5-99d9-31fbf4a83f91')
uid = lambda name: str(uuid.uuid5(NAMESPACE, name))
q = lambda text: json.dumps(str(text))
FOOTPRINTS = json.loads((ROOT/'pcb_components.json').read_text())


def pin(number, name, x, y, angle, length=1.27):
    return f'(pin passive line (at {x} {y} {angle}) (length {length}) (name {q(name)} (effects (font (size 1 1)))) (number {q(number)} (effects (font (size 1 1)))))'


def line(points):
    return '(polyline (pts ' + ' '.join(f'(xy {x} {y})' for x, y in points) + ') (stroke (width 0) (type default)) (fill (type none)))'


def rectangle(a,b):
    return f'(rectangle (start {a[0]} {a[1]}) (end {b[0]} {b[1]}) (stroke (width 0) (type default)) (fill (type none)))'


def definition(name,reference,graphics,pins):
    return f'''(symbol {q(name)} (pin_names (offset 0) (hide yes)) (in_bom yes) (on_board yes)
    (property "Reference" {q(reference)} (at 2.54 1.27 0) (effects (font (size 1 1))))
    (property "Value" {q(name)} (at 2.54 -1.27 0) (effects (font (size 1 1))))
    (symbol {q(name+'_0_1')} {graphics}) (symbol {q(name+'_1_1')} {''.join(pins)}))'''


class Design:
    def __init__(self):
        self.definitions={};self.pin_geometry={};self.items=[];self.parts=[];self.net_assertions={}
        self.sheet=uid('sheet')

    def add_definition(self,name,reference,graphics,pins):
        self.definitions[name]=definition(name,reference,graphics,[pin(*p) for p in pins])
        self.pin_geometry[name]={str(p[0]):(p[2],p[3]) for p in pins}

    def place(self,name,reference,value,x,y,angle=0):
        identity=uid(reference)
        self.items.append(f'''(symbol (lib_id "EnergyLine:{name}") (at {x} {y} {angle}) (unit 1)
        (in_bom yes) (on_board yes) (dnp no) (uuid {identity})
        (property "Reference" {q(reference)} (at {x+3.81} {y-2.54} 0) (effects (font (size 1.27 1.27)) (justify left)))
        (property "Value" {q(value)} (at {x+3.81} {y+1.27} 0) (effects (font (size 1.0 1.0)) (justify left)))
        (property "Footprint" {q(FOOTPRINTS[reference]["footprint"])} (at {x} {y} 0) (effects (font (size 1 1)) (hide yes)))
        (instances (project "S3_interface" (path "/{self.sheet}" (reference {q(reference)}) (unit 1)))))''')
        self.parts.append({'reference':reference,'value':value,'symbol':name,'x_mm':x,'y_mm':y,'angle':angle})
        geometry={}
        for number,(px,py) in self.pin_geometry[name].items():
            rad=math.radians(angle)
            geometry[number]=(round(x+px*math.cos(rad)-py*math.sin(rad),4),round(y-px*math.sin(rad)-py*math.cos(rad),4))
        return geometry

    def wire(self,a,b):
        if a==b:return
        self.items.append(f'(wire (pts (xy {a[0]} {a[1]}) (xy {b[0]} {b[1]})) (stroke (width 0) (type default)) (uuid {uid("wire"+str(a)+str(b))}))')

    def label(self,name,point):
        self.items.append(f'(label {q(name)} (at {point[0]} {point[1]} 0) (effects (font (size 1.0 1.0)) (justify left bottom)) (uuid {uid("label"+name+str(point))}))')

    def stub(self,pin_point,point,name):
        self.wire(pin_point,point);self.label(name,point)

    def junction(self,point):
        self.items.append(f'(junction (at {point[0]} {point[1]}) (diameter 0) (color 0 0 0 0) (uuid {uid("junction"+str(point))}))')

    def text(self,value,x,y,size=1.27):
        self.items.append(f'(text {q(value)} (at {x} {y} 0) (effects (font (size {size} {size})) (justify left)) (uuid {uid("text"+value+str(x)+str(y))}))')


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    d=Design()
    vertical=[('1','1',0,3.81,270),('2','2',0,-3.81,90)]
    d.add_definition('R','R',rectangle((-1.016,2.54),(1.016,-2.54)),vertical)
    d.add_definition('Fuse','F',rectangle((-.762,2.54),(.762,-2.54))+line([(0,2.54),(0,-2.54)]),vertical)
    d.add_definition('C','C',line([(-2.032,.635),(2.032,.635)])+line([(-2.032,-.635),(2.032,-.635)]),
                     [('1','1',0,3.81,270,3.175),('2','2',0,-3.81,90,3.175)])
    led_graphic=line([(-1.27,1.27),(1.27,1.27),(0,-1.27),(-1.27,1.27)])+line([(-1.27,-1.27),(1.27,-1.27)])
    led_graphic+=line([(1.8,1.3),(3.2,2.7),(2.5,2.7)])+line([(2.2,0),(3.6,1.4),(2.9,1.4)])
    d.add_definition('LED','D',led_graphic,[('2','A',0,3.81,270),('1','K',0,-3.81,90)])
    transistor=line([(-.8,-2.54),(-.8,2.54)])+line([(-.8,1.27),(2.54,3.81)])+line([(-.8,-1.27),(2.54,-3.81)])
    transistor+=line([(1.0,-3.4),(2.54,-3.81),(2.1,-2.3)])
    d.add_definition('NPN_CBE','Q',transistor,[('1','C',2.54,5.08,270),('2','B',-5.08,0,0,4.28),('3','E',2.54,-5.08,90)])
    switch=line([(-2.54,0),(2.54,2.54)])
    d.add_definition('Switch_SPST','SW',switch,[('1','1',-5.08,0,0,2.54),('2','2',5.08,0,180,2.54)])
    for count in (2,6):
        extent=(count-1)*1.27+1.27
        pins=[(str(i+1),str(i+1),-5.08,(count-1)*1.27-i*2.54,0,2.54) for i in range(count)]
        d.add_definition('Conn_'+str(count),'J',rectangle((-2.54,extent),(2.54,-extent)),pins)
    d.add_definition('TestPoint','TP','(circle (center 0 0) (radius 1.0) (stroke (width 0) (type default)) (fill (type none)))',[('1','1',0,-2.54,90,1.54)])

    d.text('S3 - 5 V mock clamp interface',15.24,15.24,2.0)
    d.text('Two dry-contact inputs, controller header and LED output. No real clamp or safety function.',15.24,21.59,1.1)
    d.text('POWER / PERMIT',20.32,30.48)
    j1=d.place('Conn_2','J1','5V DC IN',30.48,43.18)
    d.stub(j1['1'],(15.24,41.91),'+5V_IN');d.stub(j1['2'],(15.24,44.45),'GND')
    fuse=d.place('Fuse','F1','100mA',60.96,45.72)
    d.stub(fuse['1'],(60.96,35.56),'+5V_IN');d.stub(fuse['2'],(60.96,55.88),'+5V')
    c1=d.place('C','C1','100n',81.28,45.72)
    d.stub(c1['1'],(81.28,35.56),'+5V');d.stub(c1['2'],(81.28,55.88),'GND')
    sw=d.place('Switch_SPST','SW1','PERMIT (simulated)',132.08,40.64)
    d.stub(sw['1'],(121.92,40.64),'+5V');d.stub(sw['2'],(144.78,40.64),'PERMIT_OK')
    r6=d.place('R','R6','10k',160.02,55.88)
    d.stub(r6['1'],(160.02,45.72),'PERMIT_OK');d.stub(r6['2'],(160.02,66.04),'GND')

    d.text('CONTROLLER HEADER',20.32,80.01)
    j2=d.place('Conn_6','J2','5V GPIO interface',66.04,101.6)
    mapping=['+5V','GND','CLAMP_CMD','PART_N','COVER_N','PERMIT_OK']
    for number,name in enumerate(mapping,1):d.stub(j2[str(number)],(40.64,j2[str(number)][1]),name)
    d.text('J2 pin 1 supplies the controller from fused 5V.',20.32,120.65,1.0)
    d.text('Use one supply; do not parallel controller USB power.',20.32,125.73,1.0)
    d.text('5V logic only. PART_N and COVER_N are active low.',20.32,130.81,1.0)

    for index,(net,pull_y,connector_y,cap_y) in enumerate([('PART_N',76.2,88.9,100.33),('COVER_N',137.16,149.86,161.29)]):
        resistor=d.place('R','R'+str(index+4),'10k',111.76,pull_y)
        d.stub(resistor['1'],(111.76,round(pull_y-10.16,4)),'+5V')
        connector=d.place('Conn_2','J'+str(index+3),'Dry contact',139.7,connector_y)
        node=(111.76,connector['1'][1]);d.wire(resistor['2'],node);d.wire(node,connector['1']);d.label(net,(116.84,node[1]))
        cap=d.place('C','C'+str(index+2),'10n',111.76,cap_y)
        d.wire(node,cap['1']);d.junction(node)
        d.stub(cap['2'],(111.76,round(cap_y+10.16,4)),'GND')
        d.stub(connector['2'],(127,connector['2'][1]),'GND')
    d.text('Close each contact to GND when the part is present.',106.68,179.07,1.0)

    d.text('MOCK CLAMP OUTPUT',200.66,30.48)
    r1=d.place('R','R1','680',226.06,60.96)
    d.stub(r1['1'],(226.06,45.72),'PERMIT_OK')
    led=d.place('LED','D1','CLAMP LED',226.06,76.2);d.wire(r1['2'],led['2'])
    transistor=d.place('NPN_CBE','Q1','BC547B',223.52,99.06);d.wire(led['1'],transistor['1'])
    d.label('CLAMP_COLLECTOR',(226.06,88.9))
    r2=d.place('R','R2','4.7k',205.74,99.06,90)
    d.stub(r2['1'],(190.5,99.06),'CLAMP_CMD');d.wire(r2['2'],transistor['2'])
    r3=d.place('R','R3','100k',213.36,116.84)
    d.wire((213.36,99.06),r3['1']);d.junction((213.36,99.06))
    d.stub(r3['2'],(213.36,127),'GND');d.stub(transistor['3'],(226.06,114.3),'GND')
    tp=d.place('TestPoint','TP1','Collector',254,86.36)
    d.wire((226.06,88.9),tp['1']);d.junction((226.06,88.9))
    d.text('LED load only; no inductive actuator is fitted.',190.5,144.78,1.0)
    d.text('SW1 removes load power even if CLAMP_CMD is high.',190.5,149.86,1.0)
    d.text('R3 keeps Q1 off while the controller pin floats.',190.5,154.94,1.0)
    d.text('Confirm Q1 pinout against the chosen manufacturer.',190.5,160.02,1.0)

    library='(kicad_symbol_lib (version 20241209) (generator "energyline")\n'+ '\n'.join(d.definitions.values())+'\n)'
    (OUT/'EnergyLine.kicad_sym').write_text(library)
    cached=[]
    for name,value in d.definitions.items():cached.append(value.replace('(symbol '+q(name),'(symbol '+q('EnergyLine:'+name),1))
    schematic=f'''(kicad_sch (version 20250114) (generator "energyline") (uuid {d.sheet})
    (paper "A4") (title_block (title "S3 5V mock clamp interface") (rev "A") (comment 1 "Bench concept: not production or safety qualified"))
    (lib_symbols {''.join(cached)}) {''.join(d.items)}
    (sheet_instances (path "/" (page "1"))))'''
    (OUT/'S3_interface.kicad_sch').write_text(schematic)
    (OUT/'S3_interface.kicad_pro').write_text(json.dumps({'meta':{'filename':'S3_interface.kicad_pro','version':1}},indent=2)+'\n')
    (OUT/'sym-lib-table').write_text('(sym_lib_table (version 7) (lib (name "EnergyLine") (type "KiCad") (uri "${KIPRJMOD}/EnergyLine.kicad_sym") (options "") (descr "S3 bench interface symbols")))\n')
    with (OUT/'bom.csv').open('w',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(d.parts[0]));writer.writeheader();writer.writerows(d.parts)
    (OUT/'io_mapping.json').write_text(json.dumps({'controller_header':{str(i+1):net for i,net in enumerate(mapping)},'active_low_inputs':['PART_N','COVER_N'],'output_load':'LED only','supply_v':5,'safety_function':False},indent=2)+'\n')
    print('Created native KiCad project with',len(d.parts),'components.')


if __name__=='__main__':main()
