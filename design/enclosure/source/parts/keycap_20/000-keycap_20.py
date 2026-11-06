# cell: keycap_20
master=part("keycaps")
legend_size=master.word_legend_size
legend_depth=param("keycap_20_legend_depth",0.35)
assert master.cap_roof>legend_depth+0.8
legend_cutter=master.legend_cut("AC",legend_size,legend_depth)
cap=master.cap_blank-legend_cutter
assert cap.is_valid and len(cap.solids())==1
cap.color=srgb("#ecb65b")
publish("key_20",cap,"Key AC",material="petg",role="part")
