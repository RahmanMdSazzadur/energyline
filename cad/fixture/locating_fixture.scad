// Fixture concept, mm. Replaceable contacts; low-force virtual clamp blocks.
$fn=32;
color([.65,.72,.59])cube([240,180,12]);
// Datum A: support pads. B: two contacts on long edge. C: one short-edge stop.
for(p=[[50,50],[190,50],[120,130]])color([.4,.55,.35])translate([p[0],p[1],12])cylinder(h=3,d=12);
for(x=[65,175])color([.75,.48,.25])translate([x-5,26,12])cube([10,4,12]);
color([.75,.48,.25])translate([26,85,12])cube([4,10,12]);
// Adjustable opposed clamp concept. No real force or safety rating is specified.
for(x=[10,214])color([.7,.4,.2])translate([x,75,12])cube([16,30,18]);
