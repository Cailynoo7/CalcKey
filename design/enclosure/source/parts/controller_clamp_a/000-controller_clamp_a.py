b=part("base")
index=param("controller_clamp_index_a",0)
shape=b.clamp_shapes[int(index)]
shape.color=srgb("#C4E4DA")
publish("controller_clamp_a",shape,"Controller pressure bridge A",material="pla")