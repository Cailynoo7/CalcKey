master=part("keycaps")
legend_size=param("keycap_18_legend_size",3.1)
legend_depth=param("keycap_18_legend_depth",0.35)
assert master.cap_roof>legend_depth+0.8
cap=master.cap_blank-Pos(0,0,master.cap_h-legend_depth)*extrude(Text("0",legend_size,font="Arial"),legend_depth+0.05)
assert cap.is_valid and len(cap.solids())==1
cap.color=srgb("#f1f0e8")
publish("key_18",cap,"Key 0",material="petg",role="part")
