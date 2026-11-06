
left=part("hinge_cap_left")
outer_d=param("right_cap_outer_diameter",5.0)
cap=left.make_cap(outer_d)
assert cap.is_valid and len(cap.solids())==1
cap.color=srgb("#354151")
publish("hinge_cap_right",cap,"Right axle end cap",material="petg")
