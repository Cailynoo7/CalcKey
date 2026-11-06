# cell: keycap_16
master=part("keycaps")
legend_size=master.operator_legend_size
legend_depth=param("keycap_16_legend_depth",0.35)
assert master.cap_roof>legend_depth+0.8
enter_size=param("keycap_16_enter_size",master.word_legend_size)
enter_y=param("keycap_16_enter_y",2.4)
equals_y=param("keycap_16_equals_y",-2.1)
enter_cutter=master.legend_cut("Enter",enter_size,legend_depth,y=enter_y)
equals_cutter=master.legend_cut("=",legend_size,legend_depth,y=equals_y)
cap=master.cap_blank-enter_cutter-equals_cutter
assert cap.is_valid and len(cap.solids())==1
cap.color=srgb("#249baa")
publish("key_16",cap,"Key Enter / =",material="petg",role="part")
