// EnergyLine inert module concept. mm. Not manufacturing qualified.
$fn=48;
tray=[180,120,30]; wall=3; floor_t=4; cover_t=3;
centres=[[12,12],[168,12],[12,108],[168,108]];
module base_tray(){
 difference(){
  union(){difference(){cube(tray);translate([wall,wall,floor_t])cube([174,114,31]);}
   for(p=centres)translate([p[0],p[1],4])cylinder(h=26,r=5);}
  for(p=centres)translate([p[0],p[1],-1])cylinder(h=32,d=3.5);
 }
}
module lid(){difference(){cube([180,120,cover_t]);for(p=centres)translate([p[0],p[1],-1])cylinder(h=5,d=5.0);}}
color([.48,.65,.44])base_tray();
for(x=[12,54,96,138])color([.25,.4,.3])translate([x,20,4])cube([30,80,20]);
color([.8,.86,.73,.6])translate([0,0,45])lid(); // exploded cover, assembled z=30
