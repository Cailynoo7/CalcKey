# cell: keycap_03
master=part("keycaps")
legend_size=master.operator_legend_size
legend_depth=param("keycap_03_legend_depth",0.35)
assert master.cap_roof>legend_depth+0.8
legend_cutter=master.legend_cut("×",legend_size,legend_depth)
cap=master.cap_blank-legend_cutter
assert cap.is_valid and len(cap.solids())==1
cap.color=srgb("#f1f0e8")
publish("key_03",cap,"Key ×",material="petg",role="part")
