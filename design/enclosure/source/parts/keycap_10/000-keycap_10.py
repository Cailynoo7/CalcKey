# cell: keycap_10
master=part("keycaps")
legend_size=master.digit_legend_size
legend_depth=param("keycap_10_legend_depth",0.35)
assert master.cap_roof>legend_depth+0.8
marker_d=param("keycap_10_marker_diameter",2.0)
marker_depth=param("keycap_10_marker_depth",0.35)
marker_y=param("keycap_10_marker_y",-4.6)
digit_y=param("keycap_10_digit_y",0.6)
assert marker_d>0 and 0<marker_depth<master.cap_roof-0.8
assert abs(marker_y)+marker_d/2<=master.cap_top/2-master.legend_edge_margin
marker_radius=((marker_d/2)**2+marker_depth**2)/(2*marker_depth)
marker=Pos(0,marker_y,master.cap_h+marker_radius-marker_depth)*Sphere(marker_radius)
legend_cutter=master.legend_cut("5",legend_size,legend_depth,y=digit_y)
cap=master.cap_blank-legend_cutter-marker
print("5 homing recess",marker_d,marker_depth,"remaining roof",master.cap_roof-marker_depth)
assert cap.is_valid and len(cap.solids())==1
cap.color=srgb("#f1f0e8")
publish("key_10",cap,"Key 5",material="petg",role="part")
