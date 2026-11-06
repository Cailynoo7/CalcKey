# cell: keycap_17
master=part("keycaps")
legend_size=master.word_legend_size
legend_depth=param("keycap_17_legend_depth",0.35)
assert master.cap_roof>legend_depth+0.8
legend_cutter=master.legend_cut("Mode",legend_size,legend_depth)
cap=master.cap_blank-legend_cutter
assert cap.is_valid and len(cap.solids())==1
cap.color=srgb("#249baa")
publish("key_17",cap,"Key Mode",material="petg",role="part")
