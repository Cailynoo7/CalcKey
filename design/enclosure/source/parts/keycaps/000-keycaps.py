# cell: keycaps
b=part("base")
key_xy=b.key_xy

cap_w=param("keycap_reference_width",18.2)
cap_top=param("keycap_reference_top_width",14.4)
cap_h=param("keycap_reference_height",7.0)
cap_wall=param("keycap_reference_wall_thickness",1.2)
cap_roof=param("keycap_reference_roof_thickness",1.6)
socket_od=param("keycap_socket_outer_diameter",5.6)
socket_neck=param("keycap_socket_neck_width",4.9)
socket_neck_top=param("keycap_socket_neck_top",5.1)
socket_span=param("keycap_socket_span",4.1)
socket_arm=param("keycap_socket_arm",1.4)
socket_depth=param("keycap_socket_depth",3.3)
socket_inset=param("keycap_socket_mouth_inset",1.4)
socket_delta=param("keycap_socket_fit_delta",0)
socket_lead=param("keycap_socket_lead_in",0.0)
legend_size=param("keycap_legend_size",3.3)
legend_depth=param("keycap_legend_depth",0.35)
digit_legend_size=param("keycap_digit_legend_size",4.8)
operator_legend_size=param("keycap_operator_legend_size",4.8)
word_legend_size=param("keycap_word_legend_size",3.3)
legend_edge_margin=param("keycap_legend_edge_margin",1.0)

def legend_cut(label, size, depth, x=0, y=0):
    profile=Text(label,size,font="Arial",font_style=FontStyle.BOLD)
    bb=profile.bounding_box()
    profile=Pos(x-(bb.min.X+bb.max.X)/2,y-(bb.min.Y+bb.max.Y)/2)*profile
    bb=profile.bounding_box()
    assert max(abs(bb.min.X),abs(bb.max.X),abs(bb.min.Y),abs(bb.max.Y))<=cap_top/2-legend_edge_margin
    assert 0<depth<cap_roof-0.8
    print("Legend",label,"font",size,"ink bbox",[bb.min.X,bb.min.Y,bb.max.X,bb.max.Y],"roof remaining",cap_roof-depth)
    return Pos(0,0,cap_h-depth)*extrude(profile,depth+0.05)
hole_span=socket_span+socket_delta
hole_arm=socket_arm+socket_delta
socket_stop=socket_inset+socket_depth
cavity_h=cap_h-cap_roof
inner_bottom=cap_w-2*cap_wall
inner_top=cap_w+(cap_top-cap_w)*(cavity_h/cap_h)-2*cap_wall
assert 0<hole_arm<hole_span<socket_od and socket_stop<cavity_h
assert cavity_h>socket_inset and cap_roof>legend_depth+0.8
assert (socket_neck-hole_span-2*socket_lead)/2>=0.39
assert socket_inset<socket_neck_top<cavity_h
shell=loft([RectangleRounded(cap_w,cap_w,1.0),Pos(0,0,cap_h)*RectangleRounded(cap_top,cap_top,1.2)])
cavity=loft([Pos(0,0,-0.1)*RectangleRounded(inner_bottom,inner_bottom,0.3),Pos(0,0,cavity_h)*RectangleRounded(inner_top,inner_top,0.3)])
cap_blank=shell-cavity
post=Pos(0,0,socket_inset)*Cylinder(socket_od/2,cavity_h+0.2-socket_inset,align=(Align.CENTER,Align.CENTER,Align.MIN))
# Opposed flats let the printed sleeve enter the measured actuator opening.
for side in (-1,1):
    post-=Pos(side*(socket_neck/2+socket_od/2),0,socket_inset-0.01)*Box(socket_od,socket_od+1,socket_neck_top-socket_inset+0.01,align=(Align.CENTER,Align.CENTER,Align.MIN))
cap_blank+=post
cap_blank-=Pos(0,0,socket_inset-0.01)*extrude(Rectangle(hole_span,hole_arm),socket_depth+0.01)
cap_blank-=Pos(0,0,socket_inset-0.01)*extrude(Rectangle(hole_arm,hole_span),socket_depth+0.01)
if socket_lead>0:
    cap_blank-=loft([Pos(0,0,socket_inset-0.01)*Rectangle(hole_span+2*socket_lead,hole_arm+2*socket_lead),Pos(0,0,socket_inset+socket_lead)*Rectangle(hole_span,hole_arm)])
    cap_blank-=loft([Pos(0,0,socket_inset-0.01)*Rectangle(hole_arm+2*socket_lead,hole_span+2*socket_lead),Pos(0,0,socket_inset+socket_lead)*Rectangle(hole_arm,hole_span)])
assert cap_blank.is_valid and len(cap_blank.solids())==1
cap=cap_blank-legend_cut("Num",legend_size,legend_depth)
assert cap.is_valid and len(cap.solids())==1
print("One fused printable cap", "cross",hole_span,hole_arm,"socket depth",socket_depth,"neck entry min wall",(socket_neck-hole_span-2*socket_lead)/2)

cap.color=srgb("#f1f0e8")
publish("key_01",cap,"Key Num",material="petg",role="part")