"""Compile and exercise the same controller logic embedded in sketch.ino."""
from pathlib import Path
import json,subprocess,tempfile
P=Path(__file__).resolve().parent
source=(P/'sketch.ino').read_text().split('// Arduino adapter.')[0].replace('#include <Arduino.h>','#include <cstdint>')
tests=r'''
#include <cassert>
#include <iostream>
int main() {
 int count=0;
 auto check=[&](bool ok,const char *name){ if(!ok){std::cerr<<"FAIL "<<name<<"\n";exit(1);}std::cout<<"PASS "<<name<<"\n";count++;};
 Inputs safe{false,true,true,false,false};
 Controller c;c.update(0,safe);
 check(c.state==IDLE&&!c.command,"boot output off");
 Inputs i=safe;i.start=true;c.update(10,i);
 check(c.state==IDLE&&!c.command,"reject start without part");
 i.part=true;c.update(20,i);
 check(c.state==IDLE&&!c.command,"held start cannot trigger on part insertion");
 i.start=false;c.update(30,i);i.start=true;c.update(40,i);
 check(c.state==RUNNING&&c.command,"fresh start begins valid cycle");
 c.update(3039,i);check(c.state==RUNNING&&c.command,"cycle stays on before deadline");
 c.update(3040,i);check(c.state==COMPLETE&&!c.command,"cycle switches off at deadline");
 c.update(5000,i);check(c.state==COMPLETE&&!c.command,"held start cannot repeat cycle");
 i.start=false;i.part=false;c.update(5010,i);
 check(c.state==IDLE&&!c.command,"unload returns idle");
 for(int fault=0;fault<3;fault++) {
  Controller f;f.update(0,safe);Inputs x{true,true,true,true,false};f.update(100,x);
  if(fault==0)x.permit=false;if(fault==1)x.cover=false;if(fault==2)x.part=false;
  f.update(101,x);check(f.state==FAULT&&!f.command,fault==0?"permit loss faults immediately":fault==1?"cover loss faults immediately":"part loss faults immediately");
  x={true,true,true,false,false};f.update(102,x);
  check(f.state==FAULT&&!f.command,"restored inputs do not auto-restart");
  x.reset=true;f.update(103,x);check(f.state==FAULT,"reset rejected while occupied");
  x.part=false;f.update(104,x);check(f.state==FAULT,"held reset cannot clear later");
  x.reset=false;f.update(105,x);x.reset=true;f.update(106,x);
  check(f.state==IDLE&&!f.command,"fresh reset after unload clears fault without output");
 }
 Controller occupied;Inputs x{true,true,true,true,false};occupied.update(0,x);
 check(occupied.state==FAULT&&!occupied.command,"occupied startup faults even with START held");
 Controller bootStart;x={false,true,true,true,false};bootStart.update(0,x);x.part=true;bootStart.update(10,x);
 check(bootStart.state==IDLE&&!bootStart.command,"START held at boot requires release");
 Controller wrap;wrap.update(0,safe);x={true,true,true,true,false};wrap.update(0xfffffff0u,x);wrap.update(0xfffffff0u+3000u,x);
 check(wrap.state==COMPLETE&&!wrap.command,"timer works across millis rollover");
 std::cout<<"TOTAL "<<count<<"\n";
}
'''
with tempfile.TemporaryDirectory() as d:
 p=Path(d);(p/'test.cpp').write_text(source+tests)
 subprocess.run(['c++','-std=c++11','-Wall','-Wextra',str(p/'test.cpp'),'-o',str(p/'check')],check=True)
 r=subprocess.run([str(p/'check')],check=True,text=True,capture_output=True)
 print(r.stdout)
 checks=[line[5:] for line in r.stdout.splitlines() if line.startswith('PASS ')]
 (P/'controller_test_results.json').write_text(json.dumps({'scope':'Native C++ tests of the exact Controller code in sketch.ino; Arduino GPIO adapter tested separately in Wokwi','passed':True,'count':len(checks),'checks':checks},indent=2)+'\n')
