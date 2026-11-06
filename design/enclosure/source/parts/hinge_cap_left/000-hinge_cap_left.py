
h=part("rear_foot_left")
p=part("hinge_axle_left")
cap_d=param("axle_cap_outer_diameter",5.0)
cap_length=param("axle_cap_length",4.4)
socket_depth=param("axle_cap_socket_depth",3.2)
socket_d=param("axle_cap_socket_diameter",2.6)
begin=p.span/2+p.end_gap
def make_cap(d):
    s=Pos(begin+cap_length/2,0,0)*Rot(0,90,0)*Cylinder(d/2,cap_length)
    s-=Pos(begin+(socket_depth-0.1)/2,0,0)*Rot(0,90,0)*Cylinder(socket_d/2,socket_depth+0.1)
    return s
cap=make_cap(cap_d)
assert (cap_d-socket_d)/2>=1.2 and cap_length-socket_depth>=1.2-1e-6
assert cap.is_valid and len(cap.solids())==1
cap.color=srgb("#354151")
publish("hinge_cap_left",cap,"Left axle end cap",material="petg")
