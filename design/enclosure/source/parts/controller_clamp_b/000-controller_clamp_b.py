b=part("base")
index=param("controller_clamp_index_b",1)
shape=b.clamp_shapes[int(index)]
shape.color=srgb("#C4E4DA")
publish("controller_clamp_b",shape,"Controller pressure bridge B",material="pla")