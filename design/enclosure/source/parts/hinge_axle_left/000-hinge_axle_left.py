
h=part("rear_foot_left")
head_d=param("axle_head_diameter",5.0)
head_t=param("axle_head_thickness",1.5)
end_gap=param("axle_end_gap",0.15)
cap_insertion=param("axle_cap_insertion",2.85)
span=h.width+2*h.side_gap+2*h.ear_t
start=-span/2-end_gap
shaft_length=span+2*end_gap+cap_insertion
def make_axle(t):
    s=Pos(start+shaft_length/2,0,0)*Rot(0,90,0)*Cylinder(h.pin_d/2,shaft_length)
    s+=Pos(start-t/2,0,0)*Rot(0,90,0)*Cylinder(head_d/2,t)
    return s
axle=make_axle(head_t)
assert axle.is_valid and len(axle.solids())==1
axle.color=srgb("#354151")
publish("hinge_axle_left",axle,"Left hinge axle",material="petg")
