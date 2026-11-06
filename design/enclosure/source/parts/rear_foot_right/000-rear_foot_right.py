
h=part("rear_foot_left")
edge_break=param("right_foot_edge_break",0.2)
foot=h.make_foot(edge_break)
assert foot.is_valid and len(foot.solids())==1
foot.color=srgb("#1e8995")
publish("rear_foot_right",foot,"Right folding foot",material="petg")
