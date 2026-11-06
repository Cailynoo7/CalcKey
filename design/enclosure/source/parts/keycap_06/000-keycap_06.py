# cell: keycap_06
master=part("keycaps")
legend_size=master.digit_legend_size
legend_depth=param("keycap_06_legend_depth",0.35)
assert master.cap_roof>legend_depth+0.8
legend_cutter=master.legend_cut("8",legend_size,legend_depth)
cap=master.cap_blank-legend_cutter
assert cap.is_valid and len(cap.solids())==1
cap.color=srgb("#f1f0e8")
publish("key_06",cap,"Key 8",material="petg",role="part")
