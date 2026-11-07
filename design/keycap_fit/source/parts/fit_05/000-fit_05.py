
cap_w=param("fit_05_width",18.2)
cap_top=param("fit_05_top_width",14.4)
cap_h=param("fit_05_height",7.0)
cap_wall=param("fit_05_wall",1.2)
cap_roof=param("fit_05_roof",1.6)
socket_od=param("fit_05_socket_outer_diameter",5.6)
socket_neck=param("fit_05_socket_neck_width",4.8)
socket_neck_top=param("fit_05_socket_neck_top",5.1)
socket_span=param("fit_05_socket_span",4.1)
socket_arm=param("fit_05_socket_arm",1.4)
socket_depth=param("fit_05_socket_depth",3.3)
socket_inset=param("fit_05_socket_mouth_inset",1.4)
socket_delta=param("fit_05_socket_fit_delta",0.05)
socket_lead=param("fit_05_socket_lead_in",0.1)
legend_size=param("fit_05_legend_size",3.1)
legend_depth=param("fit_05_legend_depth",0.35)
hole_span=socket_span+socket_delta
hole_arm=socket_arm+socket_delta
socket_stop=socket_inset+socket_depth
cavity_h=cap_h-cap_roof
inner_bottom=cap_w-2*cap_wall
inner_top=cap_w+(cap_top-cap_w)*(cavity_h/cap_h)-2*cap_wall
assert 0<hole_arm<hole_span<socket_od and socket_stop<cavity_h
assert cavity_h>socket_inset and cap_roof>legend_depth+0.8
assert (socket_neck-hole_span-2*socket_lead)/2>=0.19
assert socket_inset<socket_neck_top<cavity_h
shell=loft([RectangleRounded(cap_w,cap_w,1.0),Pos(0,0,cap_h)*RectangleRounded(cap_top,cap_top,1.2)])
cavity=loft([Pos(0,0,-0.1)*RectangleRounded(inner_bottom,inner_bottom,0.3),Pos(0,0,cavity_h)*RectangleRounded(inner_top,inner_top,0.3)])
cap_blank=shell-cavity
post=Pos(0,0,socket_inset)*Cylinder(socket_od/2,cavity_h+0.2-socket_inset,align=(Align.CENTER,Align.CENTER,Align.MIN))
for side in (-1,1):
    post-=Pos(side*(socket_neck/2+socket_od/2),0,socket_inset-0.01)*Box(socket_od,socket_od+1,socket_neck_top-socket_inset+0.01,align=(Align.CENTER,Align.CENTER,Align.MIN))
cap_blank+=post
cap_blank-=Pos(0,0,socket_inset-0.01)*extrude(Rectangle(hole_span,hole_arm),socket_depth+0.01)
cap_blank-=Pos(0,0,socket_inset-0.01)*extrude(Rectangle(hole_arm,hole_span),socket_depth+0.01)
cap_blank-=loft([Pos(0,0,socket_inset-0.01)*Rectangle(hole_span+2*socket_lead,hole_arm+2*socket_lead),Pos(0,0,socket_inset+socket_lead)*Rectangle(hole_span,hole_arm)])
cap_blank-=loft([Pos(0,0,socket_inset-0.01)*Rectangle(hole_arm+2*socket_lead,hole_span+2*socket_lead),Pos(0,0,socket_inset+socket_lead)*Rectangle(hole_arm,hole_span)])
assert cap_blank.is_valid and len(cap_blank.solids())==1
cap=cap_blank-Pos(0,0,cap_h-legend_depth)*extrude(Text("P5",legend_size,font="Arial"),legend_depth+0.05)
assert cap.is_valid and len(cap.solids())==1
print("One fused printable cap", "cross",hole_span,hole_arm,"socket depth",socket_depth,"neck entry min wall",(socket_neck-hole_span-2*socket_lead)/2)

cap.color=srgb("#249baa")
publish("fit_05",cap,"P5 fit cap",material="petg")
